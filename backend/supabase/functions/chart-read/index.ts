import { serve } from "https://deno.land/std@0.208.0/http/server.ts";

import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

interface ChartReadRequest {
  symbol: string;
  timeframe?: string;
  days?: number;
  includeMLData?: boolean;
}

function normalizeTimeframe(timeframe: string): string {
  const tf = (timeframe ?? '').trim();
  switch (tf) {
    case '15m':
      return 'm15';
    case '1h':
      return 'h1';
    case '4h':
      return 'h4';
    case '1d':
      return 'd1';
    case '1w':
      return 'w1';
    default:
      return tf;
  }
}

const CANONICAL_TIMEFRAMES = ['m15', 'h1', 'h4', 'd1', 'w1'] as const;
type CanonicalTimeframe = typeof CANONICAL_TIMEFRAMES[number];

function isCanonicalTimeframe(value: string): value is CanonicalTimeframe {
  return (CANONICAL_TIMEFRAMES as readonly string[]).includes(value);
}

function alignedSliceTo(now: Date, timeframe: CanonicalTimeframe): Date {
  const d = new Date(now);
  d.setUTCSeconds(0, 0);

  if (timeframe === 'm15') {
    const minutes = d.getUTCMinutes();
    const aligned = minutes - (minutes % 15);
    d.setUTCMinutes(aligned);
    return d;
  }

  if (timeframe === 'h1') {
    d.setUTCMinutes(0);
    return d;
  }

  if (timeframe === 'h4') {
    d.setUTCMinutes(0);
    const hours = d.getUTCHours();
    d.setUTCHours(hours - (hours % 4));
    return d;
  }

  d.setUTCHours(0, 0, 0, 0);
  return d;
}

function refreshWindowMs(timeframe: CanonicalTimeframe): number {
  switch (timeframe) {
    case 'm15':
      return 2 * 60 * 60 * 1000;
    case 'h1':
      return 6 * 60 * 60 * 1000;
    case 'h4':
      return 24 * 60 * 60 * 1000;
    case 'd1':
      return 45 * 24 * 60 * 60 * 1000;
    case 'w1':
      return 365 * 24 * 60 * 60 * 1000;
  }
}

type ChartBarRow = {
  ts: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  provider: string;
  is_intraday: boolean;
  is_forecast: boolean;
  data_status: string | null;
  confidence_score: number | null;
  upper_band: number | null;
  lower_band: number | null;
};

function clampNumber(v: unknown, fallback: number): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function toUnixSeconds(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.floor(value);
  }

  if (typeof value === "string") {
    const parsed = new Date(value);
    const time = parsed.getTime();
    if (!Number.isNaN(time)) {
      return Math.floor(time / 1000);
    }
  }

  return Math.floor(Date.now() / 1000);
}

function normalizeForecastPoint(point: Record<string, unknown>): { ts: number; value: number; lower: number; upper: number } {
  return {
    ...point,
    ts: toUnixSeconds(point["ts"] ?? point["time"]),
    value: Number(point["value"] ?? point["mid"] ?? point["midpoint"] ?? 0),
    lower: Number(point["lower"] ?? point["min"] ?? point["lower_bound"] ?? point["value"] ?? 0),
    upper: Number(point["upper"] ?? point["max"] ?? point["upper_bound"] ?? point["value"] ?? 0),
  };
}

function normalizeForecastPoints(points: unknown): Array<{ ts: number; value: number; lower: number; upper: number }> {
  if (!Array.isArray(points)) {
    return [];
  }
  return points.map((point) => normalizeForecastPoint(isRecord(point) ? point : {}));
}

function sampleForecastPoints<T extends { ts: number }>(points: T[], maxPoints: number): T[] {
  if (!Array.isArray(points) || points.length === 0) {
    return [];
  }

  if (!Number.isFinite(maxPoints) || maxPoints <= 0) {
    return points.map((point) => ({ ...point }));
  }

  if (points.length <= maxPoints || maxPoints < 2) {
    return points.map((point) => ({ ...point }));
  }

  const lastIndex = points.length - 1;
  const indices = new Set<number>();

  for (let i = 0; i < maxPoints; i += 1) {
    const ratio = maxPoints === 1 ? 0 : i / (maxPoints - 1);
    const idx = Math.min(Math.round(ratio * lastIndex), lastIndex);
    indices.add(idx);
  }

  indices.add(0);
  indices.add(lastIndex);

  return Array.from(indices)
    .sort((a, b) => a - b)
    .map((idx) => ({ ...points[idx] }));
}

const DAILY_FORECAST_MAX_POINTS = 6;
const INTRADAY_FORECAST_MAX_POINTS = 6;
const INTRADAY_FORECAST_EXPIRY_GRACE_SECONDS = 2 * 60 * 60;

const INTRADAY_TARGET_BARS = 250;
const TWO_YEARS_DAYS = 730;

const MAX_BARS_BY_TIMEFRAME: Record<string, number> = {
  m15: 2000,
  h1: 1500,
  h4: 1000,
  d1: 2000,
  w1: 2000,
};

const POSTGREST_MAX_ROWS = 1000;

function isMarketHoursApprox(now: Date): boolean {
  const et = new Date(now.toLocaleString('en-US', { timeZone: 'America/New_York' }));
  const day = et.getDay();
  if (day === 0 || day === 6) return false;
  const minutes = et.getHours() * 60 + et.getMinutes();
  const open = 9 * 60 + 30;
  const close = 16 * 60;
  return minutes >= open && minutes <= close;
}

function lastMarketCloseApprox(now: Date): Date {
  const et = new Date(now.toLocaleString('en-US', { timeZone: 'America/New_York' }));
  const close = new Date(et);
  close.setHours(16, 0, 0, 0);

  const day = et.getDay();
  const minutes = et.getHours() * 60 + et.getMinutes();
  const beforeClose = minutes < 16 * 60;

  let daysBack = 0;
  if (day === 0) {
    daysBack = 2;
  } else if (day === 6) {
    daysBack = 1;
  } else if (beforeClose) {
    daysBack = 1;
  }

  const adjusted = new Date(close.getTime() - daysBack * 24 * 60 * 60 * 1000);
  const adjustedDay = adjusted.getDay();
  if (adjustedDay === 0) {
    return new Date(adjusted.getTime() - 2 * 24 * 60 * 60 * 1000);
  }
  if (adjustedDay === 6) {
    return new Date(adjusted.getTime() - 1 * 24 * 60 * 60 * 1000);
  }
  return adjusted;
}

function effectiveTimeframeMaxAgeMs(timeframe: CanonicalTimeframe, now: Date): number {
  const base = timeframeMaxAgeMs(timeframe);
  if (timeframe === 'm15' || timeframe === 'h1' || timeframe === 'h4') {
    if (!isMarketHoursApprox(now)) {
      const lastClose = lastMarketCloseApprox(now);
      const overnightAllowance = now.getTime() - lastClose.getTime() + base;
      return Math.max(base, overnightAllowance);
    }
  }
  return base;
}

function timeframeMaxAgeMs(timeframe: string): number {
  switch (timeframe) {
    case "m15":
      return 25 * 60 * 1000;
    case "h1":
      return 2 * 60 * 60 * 1000;
    case "h4":
      return 5 * 60 * 60 * 1000;
    case "d1":
      return 48 * 60 * 60 * 1000;
    case "w1":
      return 14 * 24 * 60 * 60 * 1000;
    default:
      return 24 * 60 * 60 * 1000;
  }
}

serve(async (req: Request): Promise<Response> => {
  if (req.method === "OPTIONS") {
    return handleCorsOptions();
  }

  if (req.method !== "POST") {
    return errorResponse("Method not allowed", 405);
  }

  try {
    const body = (await req.json()) as ChartReadRequest;

    const symbol = (body.symbol ?? "").trim().toUpperCase();
    const timeframe = normalizeTimeframe(body.timeframe ?? "d1");
    const days = typeof body.days === "number" ? Math.max(1, Math.min(36500, Math.floor(body.days))) : 60;
    const includeMLData = body.includeMLData !== false;

    if (!symbol) {
      return errorResponse("Symbol is required", 400);
    }

    if (!isCanonicalTimeframe(timeframe)) {
      return errorResponse(`Invalid timeframe: ${timeframe}`, 400);
    }

    const supabase = getSupabaseClient();

    const { data: symbolData, error: symbolError } = await supabase
      .from("symbols")
      .select("id")
      .eq("ticker", symbol)
      .single();

    if (symbolError || !symbolData) {
      return jsonResponse({ error: `Symbol ${symbol} not found` }, 404);
    }

    const symbolId = symbolData.id as string;

    const refresh = {
      attempted: true,
      timeframe,
      symbol,
      enqueuedTimeframes: [] as string[],
      insertedSlices: 0,
      error: null as string | null,
    };

    const isIntradayTf = ['m15', 'h1', 'h4'].includes(timeframe);
    const isDailyWeeklyTf = ['d1', 'w1'].includes(timeframe);

    try {
      const now = new Date();
      const enqueueTimeframes: CanonicalTimeframe[] = [...CANONICAL_TIMEFRAMES];

      for (const tf of enqueueTimeframes) {
        const jobType = (tf === 'm15' || tf === 'h1' || tf === 'h4') ? 'fetch_intraday' : 'fetch_historical';
        const windowDays = jobType === 'fetch_intraday' ? 7 : 730;

        const { data: jobDefRow, error: jobDefError } = await supabase
          .from('job_definitions')
          .upsert(
            {
              job_type: jobType,
              symbol,
              timeframe: tf,
              batch_version: 1,
              window_days: windowDays,
              priority: 200,
              enabled: true,
            },
            {
              onConflict: 'symbol,timeframe,job_type,batch_version',
              ignoreDuplicates: false,
            },
          )
          .select('id')
          .single();

        if (jobDefError || !jobDefRow?.id) {
          throw new Error(`Failed to upsert job_definition for ${symbol}/${tf}: ${jobDefError?.message ?? 'unknown error'}`);
        }

        const sliceTo = alignedSliceTo(now, tf);
        const sliceFrom = new Date(sliceTo.getTime() - refreshWindowMs(tf));

        const { data: enqueueResult, error: enqueueError } = await supabase
          .rpc('enqueue_job_slices', {
            p_job_def_id: jobDefRow.id,
            p_symbol: symbol,
            p_timeframe: tf,
            p_job_type: jobType,
            p_slices: [{
              slice_from: sliceFrom.toISOString(),
              slice_to: sliceTo.toISOString(),
            }],
            p_triggered_by: 'chart-read',
          });

        if (enqueueError) {
          throw new Error(`Failed to enqueue slice for ${symbol}/${tf}: ${enqueueError.message}`);
        }

        const insertedCount = Array.isArray(enqueueResult)
          ? Number(enqueueResult?.[0]?.inserted_count ?? 0)
          : Number((enqueueResult as { inserted_count?: unknown } | null)?.inserted_count ?? 0);

        refresh.enqueuedTimeframes.push(tf);
        refresh.insertedSlices += insertedCount;
      }
    } catch (enqueueErr) {
      console.error('[chart-read] Refresh enqueue failed:', enqueueErr);
      refresh.error = enqueueErr instanceof Error ? enqueueErr.message : 'Refresh enqueue failed';
    }

    // Read path: intraday uses latest-N (250); daily/weekly uses last 2 years range.
    let bars: Array<{
      ts: string;
      open: number;
      high: number;
      low: number;
      close: number;
      volume: number;
      upper_band: number | null;
      lower_band: number | null;
      confidence_score: number | null;
    }> = [];

    if (isIntradayTf) {
      const maxBars = INTRADAY_TARGET_BARS;
      const { data: rows, error: chartError } = await supabase.rpc("get_chart_data_v2_dynamic", {
        p_symbol_id: symbolId,
        p_timeframe: timeframe,
        p_max_bars: maxBars,
        p_include_forecast: false,
      });

      if (chartError) {
        console.error("[chart-read] RPC error:", chartError);
        return jsonResponse({ error: "Failed to fetch chart data", details: chartError.message, code: chartError.code ?? null }, 500);
      }

      const chartRows = Array.isArray(rows) ? (rows as ChartBarRow[]) : [];
      bars = chartRows
        .filter((r) => !r.is_forecast)
        .map((r) => {
          const close = typeof r.close === "number" ? r.close : null;
          const safeClose = close ?? 0;
          const safeOpen = typeof r.open === "number" ? r.open : safeClose;
          const safeHigh = typeof r.high === "number" ? r.high : safeClose;
          const safeLow = typeof r.low === "number" ? r.low : safeClose;
          const safeVol = typeof r.volume === "number" ? r.volume : 0;
          return {
            ts: r.ts,
            open: safeOpen,
            high: safeHigh,
            low: safeLow,
            close: safeClose,
            volume: safeVol,
            upper_band: r.upper_band ?? null,
            lower_band: r.lower_band ?? null,
            confidence_score: r.confidence_score ?? null,
          };
        });
    } else {
      const requestedMaxBars = MAX_BARS_BY_TIMEFRAME[timeframe] ?? 1000;
      const maxBars = Math.min(requestedMaxBars, POSTGREST_MAX_ROWS);
      const startIso2y = new Date(Date.now() - TWO_YEARS_DAYS * 24 * 60 * 60 * 1000).toISOString();

      const { data: dbRows, error: dbError } = await supabase
        .from("ohlc_bars_v2")
        .select("ts, open, high, low, close, volume, upper_band, lower_band, confidence_score")
        .eq("symbol_id", symbolId)
        .eq("timeframe", timeframe)
        .eq("provider", "alpaca")
        .eq("is_forecast", false)
        .gte("ts", startIso2y)
        .order("ts", { ascending: true })
        .limit(maxBars);

      if (dbError) {
        console.error("[chart-read] DB read error:", dbError);
        return jsonResponse({ error: "Failed to fetch chart data", details: dbError.message }, 500);
      }

      const safeRows = Array.isArray(dbRows) ? dbRows : [];
      bars = safeRows.map((r) => {
        const record = r as Record<string, unknown>;
        const close = typeof record.close === "number" ? (record.close as number) : 0;
        const open = typeof record.open === "number" ? (record.open as number) : close;
        const high = typeof record.high === "number" ? (record.high as number) : close;
        const low = typeof record.low === "number" ? (record.low as number) : close;
        const volume = typeof record.volume === "number" ? (record.volume as number) : 0;
        return {
          ts: String(record.ts ?? ""),
          open,
          high,
          low,
          close,
          volume,
          upper_band: typeof record.upper_band === "number" ? (record.upper_band as number) : null,
          lower_band: typeof record.lower_band === "number" ? (record.lower_band as number) : null,
          confidence_score: typeof record.confidence_score === "number" ? (record.confidence_score as number) : null,
        };
      }).filter((b) => b.ts);
    }

    const oldestBar = bars.length > 0 ? bars[0].ts : null;
    const newestBar = bars.length > 0 ? bars[bars.length - 1].ts : null;

    const dataQuality = {
      dataAgeHours: newestBar
        ? Math.round((Date.now() - new Date(newestBar).getTime()) / (1000 * 60 * 60))
        : null,
      isStale: newestBar
        ? (Date.now() - new Date(newestBar).getTime()) > effectiveTimeframeMaxAgeMs(timeframe, new Date())
        : true,
      hasRecentData: newestBar
        ? (Date.now() - new Date(newestBar).getTime()) < (4 * 60 * 60 * 1000)
        : false,
      historicalDepthDays: oldestBar && newestBar
        ? Math.round((new Date(newestBar).getTime() - new Date(oldestBar).getTime()) / (1000 * 60 * 60 * 24))
        : 0,
      sufficientForML: bars.length >= 250,
      barCount: bars.length,
    };

    let mlSummary: unknown = null;
    let indicators: unknown = null;

    if (includeMLData) {
      try {
        const isIntraday = ["m15", "h1", "h4"].includes(timeframe);

        if (isIntraday) {
          const horizonMap: Record<string, string> = {
            m15: "15m",
            h1: "1h",
            h4: "1h",
          };

          const horizon = horizonMap[timeframe] ?? "1h";
          const expiryCutoffIso = new Date(Date.now() - INTRADAY_FORECAST_EXPIRY_GRACE_SECONDS * 1000).toISOString();

          const pathHorizon = "7d";
          const { data: intradayPath } = await supabase
            .from("ml_forecast_paths_intraday")
            .select("*")
            .eq("symbol_id", symbolId)
            .eq("timeframe", timeframe)
            .eq("horizon", pathHorizon)
            .gte("expires_at", expiryCutoffIso)
            .order("created_at", { ascending: false })
            .limit(1)
            .single();

          const { data: intradayForecast } = await supabase
            .from("ml_forecasts_intraday")
            .select("*")
            .eq("symbol_id", symbolId)
            .eq("horizon", horizon)
            .gte("expires_at", expiryCutoffIso)
            .order("created_at", { ascending: false })
            .limit(1)
            .single();

          if (intradayForecast) {
            const conf = clampNumber(intradayForecast.confidence, 0.5);

            const horizons: Array<{ horizon: string; points: Array<{ ts: number; value: number; lower: number; upper: number }> }> = [];

            if (intradayPath && Array.isArray(intradayPath.points) && intradayPath.points.length > 0) {
              const normalizedPathPoints = normalizeForecastPoints(intradayPath.points);
              const sampledPathPoints = sampleForecastPoints(normalizedPathPoints, INTRADAY_FORECAST_MAX_POINTS);
              if (sampledPathPoints.length > 0) {
                horizons.push({
                  horizon: pathHorizon,
                  points: sampledPathPoints,
                });
              }
            }

            if (Array.isArray(intradayForecast.points) && intradayForecast.points.length > 0) {
              const normalizedForecastPoints = normalizeForecastPoints(intradayForecast.points);
              const sampledForecastPoints = sampleForecastPoints(normalizedForecastPoints, INTRADAY_FORECAST_MAX_POINTS);
              if (sampledForecastPoints.length > 0) {
                horizons.push({
                  horizon,
                  points: sampledForecastPoints,
                });
              }
            }

            mlSummary = {
              overallLabel: intradayForecast.overall_label,
              confidence: conf,
              horizons,
              srLevels: null,
              srDensity: null,
            };

            indicators = {
              supertrendFactor: null,
              supertrendPerformance: null,
              supertrendSignal: intradayForecast?.supertrend_direction === "BULLISH" ? 1 :
                intradayForecast?.supertrend_direction === "BEARISH" ? -1 : 0,
              trendLabel: intradayPath?.overall_label ?? intradayForecast.overall_label,
              trendConfidence: Math.round(conf * 10),
              stopLevel: null,
              trendDurationBars: null,
              rsi: null,
              adx: null,
              macdHistogram: null,
              kdjJ: null,
            };
          }
        } else {
          const { data: dailyForecast } = await supabase
            .from("ml_forecasts")
            .select("*")
            .eq("symbol_id", symbolId)
            .order("created_at", { ascending: false })
            .limit(1)
            .single();

          if (dailyForecast && dailyForecast.points) {
            const normalizedPoints = normalizeForecastPoints(dailyForecast.points);
            const sampledPoints = sampleForecastPoints(normalizedPoints, DAILY_FORECAST_MAX_POINTS);

            mlSummary = {
              overallLabel: dailyForecast.overall_label,
              confidence: dailyForecast.confidence,
              horizons: [{
                horizon: dailyForecast.horizon,
                points: sampledPoints,
              }],
              srLevels: dailyForecast.sr_levels || null,
              srDensity: dailyForecast.sr_density || null,
            };

            indicators = {
              supertrendFactor: dailyForecast.supertrend_factor,
              supertrendPerformance: dailyForecast.supertrend_performance,
              supertrendSignal: dailyForecast.supertrend_signal,
              trendLabel: dailyForecast.trend_label,
              trendConfidence: dailyForecast.trend_confidence,
              stopLevel: dailyForecast.stop_level,
              trendDurationBars: dailyForecast.trend_duration_bars,
              rsi: dailyForecast.rsi,
              adx: dailyForecast.adx,
              macdHistogram: dailyForecast.macd_histogram,
              kdjJ: dailyForecast.kdj_j,
            };
          }
        }
      } catch (mlError) {
        console.error("[chart-read] ML enrichment error:", mlError);
      }
    }

    const response = {
      symbol,
      assetType: "stock",
      timeframe,
      bars,
      mlSummary,
      indicators,
      supertrend_ai: null,
      metadata: {
        total_bars: bars.length,
        requested_days: isDailyWeeklyTf ? TWO_YEARS_DAYS : days,
        max_bars: isIntradayTf ? INTRADAY_TARGET_BARS : Math.min((MAX_BARS_BY_TIMEFRAME[timeframe] ?? 1000), POSTGREST_MAX_ROWS),
      },
      dataQuality,
      refresh,
    };

    return jsonResponse(response, 200);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error("[chart-read] Error:", error);
    return jsonResponse({ error: "Internal server error", details: message }, 500);
  }
});
