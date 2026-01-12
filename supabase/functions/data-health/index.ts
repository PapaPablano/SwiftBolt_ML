// data-health: Unified health snapshot endpoint for data freshness monitoring
// GET /data-health?symbol=AAPL&timeframe=d1
// GET /data-health (returns all symbols/timeframes)
//
// Returns JSON health object per symbol/timeframe combining:
// - market_intelligence_dashboard metrics
// - coverage_status data
// - latest job_runs status
// - latest forecast run_at
// - latest options snapshot time

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { corsHeaders, handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

interface HealthStatus {
  symbol: string;
  timeframe: string;
  coverage: {
    hasCoverage: boolean;
    fromTs: string | null;
    toTs: string | null;
    lastSuccessAt: string | null;
    lastRowsWritten: number | null;
    lastProvider: string | null;
  };
  freshness: {
    isStale: boolean;
    ageHours: number | null;
    slaHours: number;
    lastBarTs: string | null;
  };
  jobs: {
    latestStatus: string | null;
    latestRunAt: string | null;
    pendingJobs: number;
    failedJobsLast24h: number;
  };
  forecast: {
    latestRunAt: string | null;
    isStale: boolean;
    ageHours: number | null;
  };
  options: {
    latestSnapshotAt: string | null;
    isStale: boolean;
    ageHours: number | null;
  };
  market: {
    isOpen: boolean;
    hasPendingSplits: boolean;
    pendingSplitCount: number;
  };
  overallHealth: "healthy" | "warning" | "critical";
  checkedAt: string;
}

// Freshness SLA thresholds in hours per timeframe
const FRESHNESS_SLA: Record<string, number> = {
  m15: 0.5,   // 30 minutes during market hours
  h1: 2,     // 2 hours
  h4: 8,     // 8 hours
  d1: 24,    // 24 hours
  w1: 168,   // 1 week
};

const FORECAST_SLA_HOURS = 24; // Forecasts should be < 24h old
const OPTIONS_SLA_HOURS = 4;  // Options snapshots should be < 4h old during market hours

serve(async (req: Request): Promise<Response> => {
  if (req.method === "OPTIONS") {
    return handleCorsOptions();
  }

  if (req.method !== "GET") {
    return errorResponse("Method not allowed", 405);
  }

  try {
    const url = new URL(req.url);
    const symbolParam = url.searchParams.get("symbol")?.toUpperCase();
    const timeframeParam = url.searchParams.get("timeframe");
    
    const supabase = getSupabaseClient();
    const now = new Date();
    
    // Build health statuses
    const healthStatuses: HealthStatus[] = [];
    
    // Get coverage status data
    let coverageQuery = supabase.from("coverage_status").select("*");
    if (symbolParam) {
      coverageQuery = coverageQuery.eq("symbol", symbolParam);
    }
    if (timeframeParam) {
      coverageQuery = coverageQuery.eq("timeframe", timeframeParam);
    }
    const { data: coverageData, error: coverageError } = await coverageQuery;
    
    if (coverageError) {
      console.error("[data-health] Coverage query error:", coverageError);
    }
    
    // Get symbols for the query
    const symbolsToCheck = symbolParam 
      ? [symbolParam] 
      : [...new Set(coverageData?.map(c => c.symbol) || [])];
    
    const timeframesToCheck = timeframeParam 
      ? [timeframeParam] 
      : ["m15", "h1", "h4", "d1", "w1"];
    
    // Get latest job runs for these symbols
    const { data: jobRunsData } = await supabase
      .from("job_runs")
      .select("symbol, timeframe, status, created_at, finished_at")
      .in("symbol", symbolsToCheck)
      .order("created_at", { ascending: false })
      .limit(100);
    
    // Get pending and failed job counts
    const { data: pendingJobs } = await supabase
      .from("job_runs")
      .select("symbol, timeframe")
      .in("symbol", symbolsToCheck)
      .in("status", ["queued", "running"]);
    
    const twentyFourHoursAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString();
    const { data: failedJobs } = await supabase
      .from("job_runs")
      .select("symbol, timeframe")
      .in("symbol", symbolsToCheck)
      .eq("status", "failed")
      .gte("created_at", twentyFourHoursAgo);
    
    // Get latest forecast run_at per symbol
    const { data: forecastData } = await supabase
      .from("ml_forecasts")
      .select("symbol_id, run_at, symbols!inner(ticker)")
      .order("run_at", { ascending: false });
    
    // Get latest options snapshot per symbol
    const { data: optionsData } = await supabase
      .from("options_snapshots")
      .select("underlying_symbol, snapshot_at")
      .in("underlying_symbol", symbolsToCheck)
      .order("snapshot_at", { ascending: false });
    
    // Get pending corporate actions (splits)
    const { data: pendingSplits } = await supabase
      .from("corporate_actions")
      .select("symbol")
      .eq("bars_adjusted", false)
      .in("action_type", ["stock_split", "reverse_split"]);
    
    // Check market status
    const { data: marketStatus } = await supabase.rpc("is_market_open");
    const isMarketOpen = marketStatus ?? false;
    
    // Get latest bars per symbol/timeframe
    const latestBarsMap: Map<string, string> = new Map();
    for (const symbol of symbolsToCheck) {
      for (const tf of timeframesToCheck) {
        const { data: latestBar } = await supabase
          .from("ohlc_bars_v2")
          .select("ts")
          .eq("symbol_id", `(SELECT id FROM symbols WHERE ticker = '${symbol}')`)
          .eq("timeframe", tf)
          .eq("is_forecast", false)
          .order("ts", { ascending: false })
          .limit(1)
          .single();
        
        if (latestBar?.ts) {
          latestBarsMap.set(`${symbol}:${tf}`, latestBar.ts);
        }
      }
    }
    
    // Build health status for each symbol/timeframe combination
    for (const symbol of symbolsToCheck) {
      for (const tf of timeframesToCheck) {
        const coverage = coverageData?.find(c => c.symbol === symbol && c.timeframe === tf);
        const latestJob = jobRunsData?.find(j => j.symbol === symbol && j.timeframe === tf);
        const latestBarTs = latestBarsMap.get(`${symbol}:${tf}`);
        
        // Calculate freshness
        const slaHours = FRESHNESS_SLA[tf] || 24;
        let ageHours: number | null = null;
        let isStale = false;
        
        if (latestBarTs) {
          const barDate = new Date(latestBarTs);
          ageHours = (now.getTime() - barDate.getTime()) / (1000 * 60 * 60);
          isStale = ageHours > slaHours;
        } else {
          isStale = true;
        }
        
        // Get forecast info
        const forecast = forecastData?.find((f: any) => f.symbols?.ticker === symbol);
        let forecastAgeHours: number | null = null;
        let forecastIsStale = true;
        if (forecast?.run_at) {
          const forecastDate = new Date(forecast.run_at);
          forecastAgeHours = (now.getTime() - forecastDate.getTime()) / (1000 * 60 * 60);
          forecastIsStale = forecastAgeHours > FORECAST_SLA_HOURS;
        }
        
        // Get options info
        const optionsSnapshot = optionsData?.find(o => o.underlying_symbol === symbol);
        let optionsAgeHours: number | null = null;
        let optionsIsStale = true;
        if (optionsSnapshot?.snapshot_at) {
          const optionsDate = new Date(optionsSnapshot.snapshot_at);
          optionsAgeHours = (now.getTime() - optionsDate.getTime()) / (1000 * 60 * 60);
          optionsIsStale = isMarketOpen && optionsAgeHours > OPTIONS_SLA_HOURS;
        }
        
        // Count pending/failed jobs for this symbol/timeframe
        const pendingCount = pendingJobs?.filter(j => j.symbol === symbol && j.timeframe === tf).length || 0;
        const failedCount = failedJobs?.filter(j => j.symbol === symbol && j.timeframe === tf).length || 0;
        
        // Check for pending splits
        const symbolPendingSplits = pendingSplits?.filter(s => s.symbol === symbol) || [];
        
        // Determine overall health
        let overallHealth: "healthy" | "warning" | "critical" = "healthy";
        if (isStale && isMarketOpen) {
          overallHealth = "warning";
        }
        if (failedCount > 0 || symbolPendingSplits.length > 0) {
          overallHealth = "warning";
        }
        if ((isStale && ageHours && ageHours > slaHours * 3) || failedCount >= 3) {
          overallHealth = "critical";
        }
        
        healthStatuses.push({
          symbol,
          timeframe: tf,
          coverage: {
            hasCoverage: !!coverage,
            fromTs: coverage?.from_ts || null,
            toTs: coverage?.to_ts || null,
            lastSuccessAt: coverage?.last_success_at || null,
            lastRowsWritten: coverage?.last_rows_written || null,
            lastProvider: coverage?.last_provider || null,
          },
          freshness: {
            isStale,
            ageHours: ageHours !== null ? Math.round(ageHours * 10) / 10 : null,
            slaHours,
            lastBarTs: latestBarTs || null,
          },
          jobs: {
            latestStatus: latestJob?.status || null,
            latestRunAt: latestJob?.created_at || null,
            pendingJobs: pendingCount,
            failedJobsLast24h: failedCount,
          },
          forecast: {
            latestRunAt: forecast?.run_at || null,
            isStale: forecastIsStale,
            ageHours: forecastAgeHours !== null ? Math.round(forecastAgeHours * 10) / 10 : null,
          },
          options: {
            latestSnapshotAt: optionsSnapshot?.snapshot_at || null,
            isStale: optionsIsStale,
            ageHours: optionsAgeHours !== null ? Math.round(optionsAgeHours * 10) / 10 : null,
          },
          market: {
            isOpen: isMarketOpen,
            hasPendingSplits: symbolPendingSplits.length > 0,
            pendingSplitCount: symbolPendingSplits.length,
          },
          overallHealth,
          checkedAt: now.toISOString(),
        });
      }
    }
    
    // Calculate summary metrics
    const summary = {
      totalChecks: healthStatuses.length,
      healthy: healthStatuses.filter(h => h.overallHealth === "healthy").length,
      warning: healthStatuses.filter(h => h.overallHealth === "warning").length,
      critical: healthStatuses.filter(h => h.overallHealth === "critical").length,
      staleData: healthStatuses.filter(h => h.freshness.isStale).length,
      staleForecast: healthStatuses.filter(h => h.forecast.isStale).length,
      staleOptions: healthStatuses.filter(h => h.options.isStale).length,
      pendingSplits: [...new Set(healthStatuses.filter(h => h.market.hasPendingSplits).map(h => h.symbol))].length,
      marketOpen: isMarketOpen,
      checkedAt: now.toISOString(),
    };
    
    return jsonResponse({
      success: true,
      summary,
      healthStatuses: symbolParam || timeframeParam ? healthStatuses : healthStatuses.slice(0, 50), // Limit if no filters
    });
    
  } catch (error) {
    console.error("[data-health] Error:", error);
    return errorResponse(
      error instanceof Error ? error.message : "Internal server error",
      500
    );
  }
});
