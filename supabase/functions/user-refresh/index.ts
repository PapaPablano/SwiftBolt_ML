// user-refresh: Comprehensive data refresh triggered by user
// POST /user-refresh { symbol }
//
// This endpoint orchestrates ALL data updates for a symbol:
// 1. Check if backfill is needed (< 100 d1 bars) and queue if so
// 2. Fetch latest OHLC bars from provider
// 3. Queue ML forecast job (high priority)
// 4. Queue options ranking job
// 5. Calculate support/resistance levels
// 6. Return comprehensive status

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getProviderRouter } from "../_shared/providers/factory.ts";
import type { Timeframe } from "../_shared/providers/types.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

interface UserRefreshRequest {
  symbol: string;
}

interface RefreshStatus {
  step: string;
  status: "pending" | "running" | "completed" | "skipped" | "failed";
  message?: string;
  details?: Record<string, unknown>;
}

interface UserRefreshResponse {
  symbol: string;
  success: boolean;
  steps: RefreshStatus[];
  summary: {
    backfillNeeded: boolean;
    backfillQueued: boolean;
    barsUpdated: number;
    mlJobQueued: boolean;
    optionsJobQueued: boolean;
    srCalculated: boolean;
  };
  // Enhanced fields for UI consumption
  queuedJobs: string[];
  warnings: string[];
  nextExpectedUpdate: string | null;
  message: string;
  durationMs: number;
}

serve(async (req: Request): Promise<Response> => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const startTime = Date.now();

  try {
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL") ?? "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? ""
    );

    const body: UserRefreshRequest = await req.json();
    const symbol = body.symbol?.toUpperCase();

    if (!symbol) {
      return new Response(JSON.stringify({ error: "Symbol required" }), {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    console.log(`[user-refresh] Starting comprehensive refresh for ${symbol}`);

    const steps: RefreshStatus[] = [];
    const summary = {
      backfillNeeded: false,
      backfillQueued: false,
      barsUpdated: 0,
      mlJobQueued: false,
      optionsJobQueued: false,
      srCalculated: false,
    };

    // Step 1: Get symbol record
    const { data: symbolRecord, error: symbolError } = await supabase
      .from("symbols")
      .select("id, ticker, asset_type")
      .eq("ticker", symbol)
      .single();

    if (symbolError || !symbolRecord) {
      steps.push({
        step: "lookup_symbol",
        status: "failed",
        message: `Symbol not found: ${symbol}`,
      });
      return new Response(JSON.stringify({
        symbol,
        success: false,
        steps,
        summary,
        message: "Symbol not found",
        durationMs: Date.now() - startTime,
      }), {
        status: 404,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const symbolId = symbolRecord.id;
    steps.push({
      step: "lookup_symbol",
      status: "completed",
      message: `Found symbol: ${symbol}`,
      details: { symbolId, assetType: symbolRecord.asset_type },
    });

    // Step 2: Check data coverage and queue backfill if needed
    const { count: d1BarCount } = await supabase
      .from("ohlc_bars_v2")
      .select("*", { count: "exact", head: true })
      .eq("symbol_id", symbolId)
      .eq("timeframe", "d1")
      .eq("is_forecast", false);

    const barCount = d1BarCount || 0;
    summary.backfillNeeded = barCount < 100;

    if (summary.backfillNeeded) {
      // Check if backfill already queued
      const { data: existingBackfill } = await supabase
        .from("symbol_backfill_queue")
        .select("id, status")
        .eq("symbol_id", symbolId)
        .in("status", ["pending", "processing"])
        .single();

      if (existingBackfill) {
        steps.push({
          step: "check_backfill",
          status: "skipped",
          message: `Backfill already ${existingBackfill.status}`,
          details: { d1Bars: barCount, threshold: 100 },
        });
      } else {
        // Queue backfill
        const { error: backfillError } = await supabase
          .from("symbol_backfill_queue")
          .insert({
            symbol_id: symbolId,
            ticker: symbol,
            status: "pending",
            timeframes: ["d1", "h1", "w1"],
          });

        if (backfillError) {
          steps.push({
            step: "queue_backfill",
            status: "failed",
            message: backfillError.message,
          });
        } else {
          summary.backfillQueued = true;
          steps.push({
            step: "queue_backfill",
            status: "completed",
            message: `Queued deep backfill (${barCount} d1 bars < 100 threshold)`,
            details: { d1Bars: barCount, threshold: 100 },
          });
        }
      }
    } else {
      steps.push({
        step: "check_backfill",
        status: "skipped",
        message: `Sufficient data (${barCount} d1 bars)`,
        details: { d1Bars: barCount, threshold: 100 },
      });
    }

    // Step 3: Fetch latest bars from provider
    const timeframes: Timeframe[] = ["d1", "h1", "h4", "m15"];
    let totalNewBars = 0;

    try {
      const router = getProviderRouter();

      for (const timeframe of timeframes) {
        // Get latest bar timestamp
        const { data: latestBar } = await supabase
          .from("ohlc_bars_v2")
          .select("ts")
          .eq("symbol_id", symbolId)
          .eq("timeframe", timeframe)
          .eq("is_forecast", false)
          .order("ts", { ascending: false })
          .limit(1)
          .single();

        const now = Math.floor(Date.now() / 1000);
        const latestTs = latestBar?.ts ? new Date(latestBar.ts).getTime() / 1000 : now - 86400 * 30;

        // Fetch new bars
        const freshBars = await router.getHistoricalBars({
          symbol,
          timeframe,
          start: Math.floor(latestTs) + 1,
          end: now,
        });

        if (freshBars.length > 0) {
          const barsToInsert = freshBars.map((bar) => ({
            symbol_id: symbolId,
            timeframe,
            ts: new Date(bar.timestamp).toISOString(),
            open: bar.open,
            high: bar.high,
            low: bar.low,
            close: bar.close,
            volume: bar.volume,
            provider: "alpaca",
            is_forecast: false,
            data_status: "confirmed",
          }));

          await supabase
            .from("ohlc_bars_v2")
            .upsert(barsToInsert, { onConflict: "symbol_id,timeframe,ts,provider,is_forecast" });

          totalNewBars += freshBars.length;
        }
      }

      summary.barsUpdated = totalNewBars;
      steps.push({
        step: "fetch_bars",
        status: "completed",
        message: totalNewBars > 0 ? `Updated ${totalNewBars} bars` : "Data is current",
        details: { newBars: totalNewBars, timeframes },
      });
    } catch (barError) {
      steps.push({
        step: "fetch_bars",
        status: "failed",
        message: barError instanceof Error ? barError.message : "Unknown error",
      });
    }

    // Step 4: Queue ML forecast job (high priority)
    try {
      const { error: mlError } = await supabase.from("job_queue").insert({
        job_type: "forecast",
        symbol,
        status: "pending",
        priority: 1, // High priority for user-triggered
        payload: {
          symbol_id: symbolId,
          horizons: ["1D", "1W"],
          triggered_by: "user-refresh",
        },
      });

      if (mlError) {
        steps.push({
          step: "queue_ml_job",
          status: "failed",
          message: mlError.message,
        });
      } else {
        summary.mlJobQueued = true;
        steps.push({
          step: "queue_ml_job",
          status: "completed",
          message: "ML forecast job queued (high priority)",
        });
      }
    } catch (mlError) {
      steps.push({
        step: "queue_ml_job",
        status: "failed",
        message: mlError instanceof Error ? mlError.message : "Unknown error",
      });
    }

    // Step 5: Queue options ranking job
    try {
      const { error: optionsError } = await supabase.from("job_queue").insert({
        job_type: "ranking",
        symbol,
        status: "pending",
        priority: 1,
        payload: {
          symbol_id: symbolId,
          triggered_by: "user-refresh",
        },
      });

      if (optionsError) {
        steps.push({
          step: "queue_options_job",
          status: "failed",
          message: optionsError.message,
        });
      } else {
        summary.optionsJobQueued = true;
        steps.push({
          step: "queue_options_job",
          status: "completed",
          message: "Options ranking job queued",
        });
      }
    } catch (optionsError) {
      steps.push({
        step: "queue_options_job",
        status: "failed",
        message: optionsError instanceof Error ? optionsError.message : "Unknown error",
      });
    }

    // Step 6: Calculate S/R levels (synchronous - fast calculation)
    try {
      // Get recent bars for S/R calculation
      const { data: recentBars } = await supabase
        .from("ohlc_bars_v2")
        .select("ts, open, high, low, close, volume")
        .eq("symbol_id", symbolId)
        .eq("timeframe", "d1")
        .eq("is_forecast", false)
        .order("ts", { ascending: false })
        .limit(252); // 1 year of trading days

      if (recentBars && recentBars.length >= 20) {
        // Calculate basic pivot points
        const latestBar = recentBars[0];
        const pp = (latestBar.high + latestBar.low + latestBar.close) / 3;
        const r1 = 2 * pp - latestBar.low;
        const s1 = 2 * pp - latestBar.high;

        // Store in ml_forecasts as sr_levels (if forecast exists)
        const { data: existingForecast } = await supabase
          .from("ml_forecasts")
          .select("id")
          .eq("symbol_id", symbolId)
          .order("run_at", { ascending: false })
          .limit(1)
          .single();

        if (existingForecast) {
          await supabase
            .from("ml_forecasts")
            .update({
              sr_levels: {
                pivot: Math.round(pp * 100) / 100,
                r1: Math.round(r1 * 100) / 100,
                s1: Math.round(s1 * 100) / 100,
                calculated_at: new Date().toISOString(),
              },
            })
            .eq("id", existingForecast.id);
        }

        summary.srCalculated = true;
        steps.push({
          step: "calculate_sr",
          status: "completed",
          message: "Support/resistance levels calculated",
          details: {
            pivot: Math.round(pp * 100) / 100,
            r1: Math.round(r1 * 100) / 100,
            s1: Math.round(s1 * 100) / 100,
          },
        });
      } else {
        steps.push({
          step: "calculate_sr",
          status: "skipped",
          message: `Insufficient data for S/R (${recentBars?.length || 0} bars)`,
        });
      }
    } catch (srError) {
      steps.push({
        step: "calculate_sr",
        status: "failed",
        message: srError instanceof Error ? srError.message : "Unknown error",
      });
    }

    // Build response
    const failedSteps = steps.filter((s) => s.status === "failed");
    const success = failedSteps.length === 0;

    const messageParts: string[] = [];
    if (summary.barsUpdated > 0) messageParts.push(`${summary.barsUpdated} bars updated`);
    if (summary.backfillQueued) messageParts.push("backfill queued");
    if (summary.mlJobQueued) messageParts.push("ML job queued");
    if (summary.optionsJobQueued) messageParts.push("options job queued");
    if (summary.srCalculated) messageParts.push("S/R calculated");

    // Build queued jobs list for UI
    const queuedJobs: string[] = [];
    if (summary.backfillQueued) queuedJobs.push("backfill");
    if (summary.mlJobQueued) queuedJobs.push("ml_forecast");
    if (summary.optionsJobQueued) queuedJobs.push("options_ranking");

    // Build warnings list for UI
    const warnings: string[] = [];
    failedSteps.forEach((s) => {
      if (s.message) warnings.push(`${s.step}: ${s.message}`);
    });

    // Calculate next expected update time (market hours only)
    const now = new Date();
    const hour = now.getUTCHours();
    const dayOfWeek = now.getUTCDay();
    let nextExpectedUpdate: string | null = null;
    
    // During market hours (roughly 14:00-21:00 UTC = 9:00-4:00 ET), expect update in 15-30 min
    if (dayOfWeek >= 1 && dayOfWeek <= 5 && hour >= 14 && hour < 21) {
      const nextUpdate = new Date(now.getTime() + 15 * 60 * 1000);
      nextExpectedUpdate = nextUpdate.toISOString();
    }

    const response: UserRefreshResponse = {
      symbol,
      success,
      steps,
      summary,
      queuedJobs,
      warnings,
      nextExpectedUpdate,
      message: messageParts.length > 0 ? messageParts.join(", ") : "Data is current",
      durationMs: Date.now() - startTime,
    };

    console.log(`[user-refresh] Completed for ${symbol}: ${response.message} (${response.durationMs}ms)`);

    return new Response(JSON.stringify(response), {
      status: 200,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });

  } catch (error) {
    console.error("[user-refresh] Error:", error);
    return new Response(
      JSON.stringify({
        success: false,
        error: error instanceof Error ? error.message : "Internal server error",
      }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }
});
