// chart: Consolidated chart data endpoint for frontend consumption
// GET /chart?symbol=AAPL&timeframe=d1&start=2025-01-01&end=2025-12-31
//
// This is the ONE chart read path for the app. Returns:
// - OHLC bars from get_chart_data_v2 (provider-aware, no client-side merging needed)
// - Latest forecast data with confidence bands
// - Options ranks for the symbol
// - Freshness indicators (last_bar_ts, data_status, is_market_open, latest_forecast_run_at)
// - Pending splits warning flag
//
// The frontend should call this single endpoint to render charts without extra round trips.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

// Market hours constants (UTC)
// NYSE/NASDAQ: 9:30 AM - 4:00 PM ET = 14:30 - 21:00 UTC (approx)
const MARKET_OPEN_HOUR_UTC = 14;
const MARKET_CLOSE_HOUR_UTC = 21;
const MARKET_WEEKDAY_START = 1; // Monday
const MARKET_WEEKDAY_END = 5;   // Friday

interface ChartBar {
  ts: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  provider: string;
  dataStatus: string;
}

type ChartBarRow = {
  ts: string;
  open: string | number;
  high: string | number;
  low: string | number;
  close: string | number;
  volume: string | number | null;
  provider?: string | null;
  data_status?: string | null;
};

interface ForecastPoint {
  ts: string;
  value: number;
  lower: number;
  upper: number;
}

type ForecastPointRow = {
  ts: string;
  value: number;
  lower?: number | null;
  upper?: number | null;
};

interface ForecastData {
  label: string;
  confidence: number;
  horizon: string;
  runAt: string;
  points: ForecastPoint[];
}

interface OptionsRank {
  expiry: string;
  strike: number;
  side: string;
  mlScore: number;
  impliedVol: number;
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  openInterest: number;
  volume: number;
  runAt: string;
}

type OptionsRankRow = {
  expiry: string;
  strike: number;
  side: string;
  ml_score?: number | null;
  implied_vol?: number | null;
  delta?: number | null;
  gamma?: number | null;
  theta?: number | null;
  vega?: number | null;
  open_interest?: number | null;
  volume?: number | null;
  run_at?: string | null;
};

type ForecastRow = {
  overall_label?: string | null;
  confidence?: number | null;
  horizon?: string | null;
  run_at?: string | null;
  points?: ForecastPointRow[] | null;
};

interface ChartResponse {
  symbol: string;
  timeframe: string;
  bars: ChartBar[];
  forecast: ForecastData | null;
  optionsRanks: OptionsRank[];
  meta: {
    lastBarTs: string | null;
    dataStatus: "fresh" | "stale" | "updating";
    isMarketOpen: boolean;
    latestForecastRunAt: string | null;
    hasPendingSplits: boolean;
    pendingSplitInfo: string | null;
    totalBars: number;
    requestedRange: {
      start: string;
      end: string;
    };
  };
  freshness: {
    ageMinutes: number | null;
    slaMinutes: number;
    isWithinSla: boolean;
  };
}

// SLA thresholds in minutes per timeframe
const FRESHNESS_SLA_MINUTES: Record<string, number> = {
  m15: 30,    // 15m bars should be < 30 min stale during market hours
  h1: 120,    // 1h bars should be < 2 hours stale
  h4: 480,    // 4h bars should be < 8 hours stale
  d1: 1440,   // Daily bars should be < 24 hours stale
  w1: 10080,  // Weekly bars should be < 1 week stale
};

serve(async (req: Request): Promise<Response> => {
  const origin = req.headers.get("origin");
  
  if (req.method === "OPTIONS") {
    return handleCorsOptions(origin);
  }

  if (req.method !== "GET") {
    return errorResponse("Method not allowed", 405, req.headers);
  }

  const startTime = Date.now();

  try {
    const url = new URL(req.url);
    const symbol = url.searchParams.get("symbol")?.toUpperCase();
    const timeframe = url.searchParams.get("timeframe") || "d1";
    const startParam = url.searchParams.get("start");
    const endParam = url.searchParams.get("end");
    const includeOptions = url.searchParams.get("include_options") !== "false";
    const includeForecast = url.searchParams.get("include_forecast") !== "false";
    const fieldsParam = url.searchParams.get("fields");
    const barLimitParam = url.searchParams.get("bars_limit");
    const barOffsetParam = url.searchParams.get("bars_offset");
    const optionsLimitParam = url.searchParams.get("options_limit");
    const optionsOffsetParam = url.searchParams.get("options_offset");

    if (!symbol) {
      return errorResponse("Symbol parameter is required", 400, req.headers);
    }

    const supabase = getSupabaseClient();
    const now = new Date();

    // Calculate date range (default: last 1 year for d1, 30 days for intraday)
    const defaultDays = ["m15", "h1", "h4"].includes(timeframe) ? 30 : 365;
    const endDate = endParam ? new Date(endParam) : now;
    const startDate = startParam 
      ? new Date(startParam) 
      : new Date(endDate.getTime() - defaultDays * 24 * 60 * 60 * 1000);

    // 1. Get symbol ID
    const { data: symbolRecord, error: symbolError } = await supabase
      .from("symbols")
      .select("id, ticker")
      .eq("ticker", symbol)
      .single();

    if (symbolError || !symbolRecord) {
      return errorResponse(`Symbol not found: ${symbol}`, 404, req.headers);
    }

    const symbolId = symbolRecord.id;

    // 2. Fetch bars using get_chart_data_v2 RPC (provider-aware)
    let barsData: ChartBarRow[] | null = null;
    const { data: rpcData, error: barsError } = await supabase.rpc("get_chart_data_v2", {
      p_symbol_id: symbolId,
      p_timeframe: timeframe,
      p_start_date: startDate.toISOString(),
      p_end_date: endDate.toISOString(),
    });

    if (barsError) {
      console.error("[chart] Bars query error:", barsError);
      // Fallback to direct query if RPC fails
      const { data: fallbackBars } = await supabase
        .from("ohlc_bars_v2")
        .select("ts, open, high, low, close, volume, provider, data_status")
        .eq("symbol_id", symbolId)
        .eq("timeframe", timeframe)
        .eq("is_forecast", false)
        .gte("ts", startDate.toISOString())
        .lte("ts", endDate.toISOString())
        .order("ts", { ascending: true });

      barsData = fallbackBars;
    } else {
      barsData = rpcData;
    }

    const allBars: ChartBar[] = (barsData || []).map((bar: ChartBarRow) => ({
      ts: bar.ts,
      open: Number(bar.open),
      high: Number(bar.high),
      low: Number(bar.low),
      close: Number(bar.close),
      volume: Number(bar.volume || 0),
      provider: bar.provider || "unknown",
      dataStatus: bar.data_status || "unknown",
    }));

    const barOffset = barOffsetParam ? Number(barOffsetParam) : 0;
    const barLimit = barLimitParam ? Number(barLimitParam) : allBars.length;
    const bars = allBars.slice(
      Math.max(0, barOffset),
      Math.max(0, barOffset) + Math.max(0, barLimit)
    );

    // Get last bar timestamp
    const lastBarTs = bars.length > 0 ? bars[bars.length - 1].ts : null;

    // 3. Fetch latest forecast if requested
    let forecastData: ForecastData | null = null;
    if (includeForecast) {
      const { data: forecast } = await supabase
        .from("latest_forecast_summary")
        .select("overall_label, confidence, horizon, run_at, points")
        .eq("symbol_id", symbolId)
        .limit(1)
        .single();

      const forecastRow = forecast as ForecastRow | null;

      if (forecastRow) {
        forecastData = {
          label: forecastRow.overall_label || "neutral",
          confidence: Number(forecastRow.confidence) || 0,
          horizon: forecastRow.horizon || "1D",
          runAt: forecastRow.run_at || "",
          points: (forecastRow.points || []).map((p: ForecastPointRow) => ({
            ts: p.ts,
            value: Number(p.value),
            lower: Number(p.lower || p.value * 0.95),
            upper: Number(p.upper || p.value * 1.05),
          })),
        };
      }
    }

    // 4. Fetch top options ranks if requested
    let optionsRanks: OptionsRank[] = [];
    if (includeOptions) {
      const { data: options } = await supabase
        .from("options_ranks")
        .select("expiry, strike, side, ml_score, implied_vol, delta, gamma, theta, vega, open_interest, volume, run_at")
        .eq("underlying_symbol_id", symbolId)
        .order("ml_score", { ascending: false })
        .range(
          Math.max(0, Number(optionsOffsetParam || 0)),
          Math.max(0, Number(optionsOffsetParam || 0)) +
            Math.max(1, Number(optionsLimitParam || 10)) - 1
        );

      if (options) {
        optionsRanks = (options as OptionsRankRow[]).map((opt) => ({
          expiry: opt.expiry,
          strike: Number(opt.strike),
          side: opt.side,
          mlScore: Number(opt.ml_score) || 0,
          impliedVol: Number(opt.implied_vol) || 0,
          delta: Number(opt.delta) || 0,
          gamma: Number(opt.gamma) || 0,
          theta: Number(opt.theta) || 0,
          vega: Number(opt.vega) || 0,
          openInterest: Number(opt.open_interest) || 0,
          volume: Number(opt.volume) || 0,
          runAt: opt.run_at || "",
        }));
      }
    }

    // 5. Check market status
    let isMarketOpen = false;
    try {
      const { data: marketStatus } = await supabase.rpc("is_market_open");
      isMarketOpen = marketStatus ?? false;
    } catch {
      // Default to checking current time if RPC fails
      const hour = now.getUTCHours();
      const dayOfWeek = now.getUTCDay();
      // Rough market hours check using constants
      isMarketOpen = dayOfWeek >= MARKET_WEEKDAY_START && dayOfWeek <= MARKET_WEEKDAY_END && 
                     hour >= MARKET_OPEN_HOUR_UTC && hour < MARKET_CLOSE_HOUR_UTC;
    }

    // 6. Check for pending splits
    const { data: pendingSplits } = await supabase
      .from("corporate_actions")
      .select("action_type, ex_date, ratio")
      .eq("symbol", symbol)
      .eq("bars_adjusted", false)
      .in("action_type", ["stock_split", "reverse_split"])
      .order("ex_date", { ascending: true })
      .limit(1);

    const hasPendingSplits = (pendingSplits?.length || 0) > 0;
    const pendingSplitInfo = hasPendingSplits && pendingSplits?.[0]
      ? `${pendingSplits[0].action_type} ${pendingSplits[0].ratio}:1 on ${pendingSplits[0].ex_date}`
      : null;

    // 7. Calculate freshness metrics
    const slaMinutes = FRESHNESS_SLA_MINUTES[timeframe] || 1440;
    let ageMinutes: number | null = null;
    let isWithinSla = true;

    if (lastBarTs) {
      const lastBarDate = new Date(lastBarTs);
      ageMinutes = Math.round((now.getTime() - lastBarDate.getTime()) / (1000 * 60));
      // Only consider stale during market hours for intraday
      if (isMarketOpen || !["m15", "h1", "h4"].includes(timeframe)) {
        isWithinSla = ageMinutes <= slaMinutes;
      }
    }

    // Determine data status
    let dataStatus: "fresh" | "stale" | "updating" = "fresh";
    if (!isWithinSla) {
      dataStatus = "stale";
    }
    // Check if there's an active job updating this data
    const { data: activeJobs } = await supabase
      .from("job_runs")
      .select("id")
      .eq("symbol", symbol)
      .eq("timeframe", timeframe)
      .in("status", ["queued", "running"])
      .limit(1);

    if (activeJobs && activeJobs.length > 0) {
      dataStatus = "updating";
    }

    // Build response
    const responseFields = fieldsParam
      ? new Set(fieldsParam.split(",").map((field) => field.trim()))
      : null;

    const response: ChartResponse = {
      symbol,
      timeframe,
      bars: responseFields && !responseFields.has("bars") ? [] : bars,
      forecast: responseFields && !responseFields.has("forecast") ? null : forecastData,
      optionsRanks: responseFields && !responseFields.has("options") ? [] : optionsRanks,
      meta: {
        lastBarTs,
        dataStatus,
        isMarketOpen,
        latestForecastRunAt: forecastData?.runAt || null,
        hasPendingSplits,
        pendingSplitInfo,
        totalBars: bars.length,
        requestedRange: {
          start: startDate.toISOString(),
          end: endDate.toISOString(),
        },
      },
      freshness: {
        ageMinutes,
        slaMinutes,
        isWithinSla,
      },
    };

    if (responseFields) {
      if (!responseFields.has("meta")) {
        response.meta = {
          lastBarTs: null,
          dataStatus: "fresh",
          isMarketOpen: false,
          latestForecastRunAt: null,
          hasPendingSplits: false,
          pendingSplitInfo: null,
          totalBars: bars.length,
          requestedRange: {
            start: startDate.toISOString(),
            end: endDate.toISOString(),
          },
        };
      }

      if (!responseFields.has("freshness")) {
        response.freshness = {
          ageMinutes: null,
          slaMinutes,
          isWithinSla: true,
        };
      }
    }

    const duration = Date.now() - startTime;
    console.log(`[chart] ${symbol}/${timeframe}: ${bars.length} bars, ${duration}ms`);

    return jsonResponse(response, 200, req.headers);

  } catch (error) {
    console.error("[chart] Error:", error);
    return errorResponse(
      error instanceof Error ? error.message : "Internal server error",
      500,
      req.headers
    );
  }
});
