// chart: Unified chart data endpoint — single round-trip for all chart data.
//
// GET /chart?symbol=AAPL&timeframe=d1&days=180
//
// Returns in one response:
//   - OHLC bars (from get_chart_data_v2 RPC, provider-aware)
//   - ML summary + indicators (intraday-first, daily fallback)
//   - Options ranks
//   - Futures metadata (resolved symbol, continuous/dated contract info)
//   - Freshness indicators + fire-and-forget stale refresh
//   - Pending splits warning
//   - Optional layers structure (?layers=true)
//
// This is the ONE chart read path for the app. Do not fragment it.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { getCorsHeaders, handleCorsOptions } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";
import type {
  ChartIndicators,
  ChartLayers,
  ChartMeta,
  DataQuality,
  FuturesMetadata,
  HorizonForecast,
  MLSummary,
  OHLCBar,
  UnifiedChartResponse,
} from "../_shared/chart-types.ts";
import {
  type BarInput,
  recomputePartialIndicators,
} from "../_shared/indicators.ts";
import { AlpacaClient } from "../_shared/providers/alpaca-client.ts";
import { TokenBucketRateLimiter } from "../_shared/rate-limiter/token-bucket.ts";
import { MemoryCache } from "../_shared/cache/memory-cache.ts";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const VALID_TIMEFRAMES = ["m15", "h1", "h4", "d1", "w1"] as const;
type Timeframe = typeof VALID_TIMEFRAMES[number];

const FRESHNESS_SLA_MINUTES: Record<string, number> = {
  m15: 15,   // 3x the 5-minute GH Actions ingestion cron interval
  m30: 60,
  h1: 120,
  h4: 480,
  d1: 1440,
  w1: 10080,
};

// Futures symbol pattern: e.g. GC1!, GCZ25, ES1!, ESZ25
const FUTURES_PATTERN = /^([A-Z]{1,6})(\d{1,2}!|[FGHJKMNQUVXZ]\d{2})$/i;

// Max bars the caller can request
const MAX_BAR_LIMIT = 2000;

// Market hours constants (UTC) — fallback if RPC fails
const MARKET_OPEN_HOUR_UTC = 14;
const MARKET_CLOSE_HOUR_UTC = 21;
const MARKET_WEEKDAY_START = 1;
const MARKET_WEEKDAY_END = 5;

const DAILY_FORECAST_HORIZONS = ["1D", "1W", "1M"] as const;
const INTRADAY_FORECAST_MAX_POINTS = 6;
const DAILY_FORECAST_MAX_POINTS = 6;
const INTRADAY_FORECAST_EXPIRY_GRACE_SECONDS = 2 * 60 * 60;

// ---------------------------------------------------------------------------
// Row types for DB results (snake_case from Postgres)
// ---------------------------------------------------------------------------

type BarRow = {
  ts: string;
  open: string | number;
  high: string | number;
  low: string | number;
  close: string | number;
  volume: string | number | null;
  provider?: string | null;
  data_status?: string | null;
  is_forecast?: boolean | null;
};

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

type DailyForecastRow = {
  overall_label?: string | null;
  confidence?: number | null;
  horizon?: string | null;
  run_at?: string | null;
  created_at?: string | null;
  points?: unknown[] | null;
  synthesis_data?: unknown;
  supertrend_factor?: number | null;
  supertrend_signal?: number | null;
  supertrend_performance?: number | null;
  supertrend_direction?: string | null;
  trend_label?: string | null;
  trend_confidence?: number | null;
  stop_level?: number | null;
  trend_duration_bars?: number | null;
  rsi?: number | null;
  adx?: number | null;
  macd_histogram?: number | null;
  kdj_j?: number | null;
  sr_levels?: Record<string, unknown> | null;
  sr_density?: number | null;
  target_price?: number | null;
  current_price?: number | null;
  adaptive_supertrend_factor?: number | null;
  adaptive_supertrend_signal?: number | null;
};

type IntradayForecastRow = {
  overall_label?: string | null;
  confidence?: number | null;
  horizon?: string | null;
  timeframe?: string | null;
  created_at?: string | null;
  expires_at?: string | null;
  points?: unknown[] | null;
  supertrend_direction?: string | null;
  target_price?: number | null;
  current_price?: number | null;
};

type IntradayPathRow = {
  overall_label?: string | null;
  confidence?: number | null;
  horizon?: string | null;
  created_at?: string | null;
  points?: unknown[] | null;
};

// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------

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

function normalizeForecastPoint(
  point: Record<string, unknown>,
):
  & { ts: number; value: number; lower: number; upper: number }
  & Record<string, unknown> {
  const out: Record<string, unknown> = {
    ...point,
    ts: toUnixSeconds(point["ts"] ?? point["time"]),
    value: Number(
      point["value"] ?? point["price"] ?? point["mid"] ?? point["midpoint"] ??
        0,
    ),
    lower: Number(
      point["lower"] ?? point["lower_band"] ?? point["min"] ??
        point["lower_bound"] ?? point["value"] ?? point["price"] ?? 0,
    ),
    upper: Number(
      point["upper"] ?? point["upper_band"] ?? point["max"] ??
        point["upper_bound"] ?? point["value"] ?? point["price"] ?? 0,
    ),
  };
  if (out["timeframe"] === "4h_trading") out["timeframe"] = "h4";
  return out as
    & { ts: number; value: number; lower: number; upper: number }
    & Record<string, unknown>;
}

function normalizeForecastPoints(
  points: unknown,
): Array<{ ts: number; value: number; lower: number; upper: number }> {
  if (!Array.isArray(points)) return [];
  return points.map((p) => normalizeForecastPoint(isRecord(p) ? p : {}));
}

function sampleForecastPoints<T extends { ts: number }>(
  points: T[],
  maxPoints: number,
): T[] {
  if (!Array.isArray(points) || points.length === 0) return [];
  if (!Number.isFinite(maxPoints) || maxPoints <= 0) {
    return points.map((p) => ({ ...p }));
  }
  if (points.length <= maxPoints || maxPoints < 2) {
    return points.map((p) => ({ ...p }));
  }
  const lastIndex = points.length - 1;
  const indices = new Set<number>();
  for (let i = 0; i < maxPoints; i++) {
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

// ---------------------------------------------------------------------------
// Weekly bar aggregation (from chart-data-v2)
// ---------------------------------------------------------------------------

function normalizeBarTimestamp(ts: string): Date | null {
  if (!ts) return null;
  const normalized = ts.includes("T") ? ts : ts.replace(" ", "T");
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}

function weekStartKey(date: Date): string {
  const day = date.getUTCDay();
  const offset = (day + 6) % 7; // Monday-based
  const monday = new Date(
    Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()),
  );
  monday.setUTCDate(monday.getUTCDate() - offset);
  return monday.toISOString().split("T")[0];
}

function aggregateWeeklyBars(bars: OHLCBar[]): OHLCBar[] {
  if (!bars.length) return [];
  const buckets = new Map<string, OHLCBar[]>();

  for (const bar of bars) {
    const date = normalizeBarTimestamp(bar.ts);
    if (!date) continue;
    const key = weekStartKey(date);
    const existing = buckets.get(key);
    if (existing) {
      existing.push(bar);
    } else {
      buckets.set(key, [bar]);
    }
  }

  const weeklyBars: OHLCBar[] = [];
  for (const [, weekBars] of buckets) {
    weekBars.sort((a, b) => {
      const aDate = normalizeBarTimestamp(a.ts) ?? new Date(0);
      const bDate = normalizeBarTimestamp(b.ts) ?? new Date(0);
      return aDate.getTime() - bDate.getTime();
    });
    const first = weekBars[0];
    const last = weekBars[weekBars.length - 1];
    const firstDate = normalizeBarTimestamp(first.ts);
    if (!firstDate) {
      console.warn(
        "[chart] Skipping weekly bar with unparseable timestamp:",
        first.ts,
      );
      continue; // skip this week bucket
    }
    const timeSuffix = `T${String(firstDate.getUTCHours()).padStart(2, "0")}:${
      String(firstDate.getUTCMinutes()).padStart(2, "0")
    }:00Z`;
    const ts = `${weekStartKey(firstDate)}${timeSuffix}`;
    const highs = weekBars.map((b) => b.high);
    const lows = weekBars.map((b) => b.low);
    weeklyBars.push({
      ts,
      open: first.open,
      high: Math.max(...highs),
      low: Math.min(...lows),
      close: last.close,
      volume: weekBars.reduce((sum, b) => sum + (b.volume ?? 0), 0),
      provider: first.provider,
    });
  }

  weeklyBars.sort((a, b) =>
    new Date(a.ts).getTime() - new Date(b.ts).getTime()
  );
  return weeklyBars;
}

// ---------------------------------------------------------------------------
// Partial candle synthesis helpers
// ---------------------------------------------------------------------------

/** Compute the period-start UTC timestamp for the current in-progress bar. */
function getPartialPeriodStart(
  tf: "d1" | "h1" | "h4" | "m15",
  now: Date,
): Date {
  const y = now.getUTCFullYear();
  const mo = now.getUTCMonth();
  const d = now.getUTCDate();
  const h = now.getUTCHours();
  const m = now.getUTCMinutes();
  if (tf === "d1") return new Date(Date.UTC(y, mo, d));
  if (tf === "h1") return new Date(Date.UTC(y, mo, d, h));
  if (tf === "m15") {
    // Floor to nearest 15-minute block within the current UTC hour
    return new Date(Date.UTC(y, mo, d, h, Math.floor(m / 15) * 15));
  }
  // h4: floor to nearest 4-hour block from midnight UTC
  return new Date(Date.UTC(y, mo, d, Math.floor(h / 4) * 4));
}

/** Aggregate 1-minute BarRows into a single in-progress OHLCBar. */
function synthesizePartialBar(
  m1Rows: BarRow[],
  tf: "d1" | "h1" | "h4" | "m15",
  now: Date,
): OHLCBar | null {
  const periodStart = getPartialPeriodStart(tf, now);
  const inPeriod = m1Rows.filter((b) => new Date(b.ts) >= periodStart);
  if (inPeriod.length === 0) return null;

  const open = Number(inPeriod[0].open);
  const close = Number(inPeriod[inPeriod.length - 1].close);
  const high = Math.max(...inPeriod.map((b) => Number(b.high)));
  const low = Math.min(...inPeriod.map((b) => Number(b.low)));
  const volume = inPeriod.reduce((s, b) => s + Number(b.volume ?? 0), 0);

  return {
    ts: periodStart.toISOString(),
    open,
    high,
    low,
    close,
    volume,
    provider: "alpaca",
    is_forecast: false,
    is_partial: true,
  };
}

// ---------------------------------------------------------------------------
// Build forecast targets helper (from chart-data-v2)
// ---------------------------------------------------------------------------

function toNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function parseRecord(value: unknown): Record<string, unknown> | null {
  if (isRecord(value)) return value;
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value);
      if (isRecord(parsed)) return parsed;
    } catch {
      return null;
    }
  }
  return null;
}

function buildForecastTargets(
  row: Record<string, unknown>,
  points: Array<{ ts: number; value: number; lower: number; upper: number }>,
): Record<string, number | null> | null {
  const synthesis = parseRecord(row["synthesis_data"]) ?? {};
  const tp1 = toNumber(
    synthesis["tp1"] ?? synthesis["target"] ?? row["target_price"],
  );
  const tp2 = toNumber(synthesis["tp2"]);
  const tp3 = toNumber(synthesis["tp3"]);
  const stopLoss = toNumber(
    synthesis["stop_loss"] ?? synthesis["stop"] ?? synthesis["sl"],
  );
  const qualityScore = toNumber(
    synthesis["quality_score"] ?? row["quality_score"],
  );
  const confluenceScore = toNumber(synthesis["confluence_score"]);

  const fallbackTp1 = tp1 ??
    (points.length > 0 ? points[points.length - 1].value : null);
  const hasAny = [
    fallbackTp1,
    tp2,
    tp3,
    stopLoss,
    qualityScore,
    confluenceScore,
  ]
    .some((v) => typeof v === "number" && Number.isFinite(v));

  if (!hasAny) return null;
  return {
    tp1: fallbackTp1,
    tp2,
    tp3,
    stop_loss: stopLoss,
    quality_score: qualityScore,
    confluence_score: confluenceScore,
  };
}

// ---------------------------------------------------------------------------
// Main handler
// ---------------------------------------------------------------------------

serve(async (req: Request): Promise<Response> => {
  const origin = req.headers.get("origin");
  const corsHeaders = getCorsHeaders(origin);

  if (req.method === "OPTIONS") {
    return handleCorsOptions(origin);
  }

  if (req.method !== "GET") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const startTime = Date.now();

  try {
    // -------------------------------------------------------------------------
    // Step 0 — Parse request parameters
    // -------------------------------------------------------------------------
    const url = new URL(req.url);
    const rawSymbol = url.searchParams.get("symbol");
    if (!rawSymbol) {
      return new Response(
        JSON.stringify({ error: "Symbol parameter is required" }),
        {
          status: 400,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        },
      );
    }
    const symbol = rawSymbol.toUpperCase().trim();

    const rawTimeframe = url.searchParams.get("timeframe");
    if (!rawTimeframe) {
      return new Response(
        JSON.stringify({
          error: "timeframe is required (m15, h1, h4, d1, w1)",
        }),
        {
          status: 400,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        },
      );
    }
    const timeframe = rawTimeframe as Timeframe;
    if (!(VALID_TIMEFRAMES as readonly string[]).includes(timeframe)) {
      return new Response(
        JSON.stringify({
          error: `Invalid timeframe: ${timeframe}. Must be one of: ${
            VALID_TIMEFRAMES.join(", ")
          }`,
        }),
        {
          status: 400,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        },
      );
    }

    const daysParam = url.searchParams.get("days");
    const TIMEFRAME_DEFAULT_DAYS: Record<string, number> = {
      m15: 10, // ~2 weeks trading, ~260 bars
      h1: 30, // ~6 weeks trading, ~210 bars
      h4: 90, // ~3 months, ~270 bars
      d1: 1825, // 5 years
      w1: 1825, // 5 years
    };
    const rawDays = daysParam
      ? Math.min(3650, Math.max(1, Number(daysParam)))
      : (TIMEFRAME_DEFAULT_DAYS[timeframe] ?? 1825);
    const startParam = url.searchParams.get("start");
    const endParam = url.searchParams.get("end");

    const includeOptions = url.searchParams.get("include_options") !== "false";
    const includeForecast =
      url.searchParams.get("include_forecast") !== "false";
    const includeML = url.searchParams.get("include_ml") !== "false";
    const useLayers = url.searchParams.get("layers") === "true";

    const barLimitParam = url.searchParams.get("bars_limit");
    const barOffsetParam = url.searchParams.get("bars_offset");
    const barOffset = barOffsetParam ? Math.max(0, Number(barOffsetParam)) : 0;
    const barLimit = barLimitParam
      ? Math.min(MAX_BAR_LIMIT, Math.max(1, Number(barLimitParam)))
      : MAX_BAR_LIMIT;

    // ── Cursor-based backward pagination ──────────────────────────────────
    // When `before` is present the caller wants the N most-recent bars
    // whose timestamp is strictly less than `before`.  `pageSize` controls
    // how many bars to return (default 400, max 1000).
    const beforeParam = url.searchParams.get("before");
    const pageSizeParam = url.searchParams.get("pageSize");
    const pageSize = pageSizeParam
      ? Math.min(1000, Math.max(1, Number(pageSizeParam)))
      : 400;

    // Parse `before` as either a unix-epoch integer (seconds) or ISO 8601.
    let beforeDate: Date | null = null;
    if (beforeParam) {
      const asNum = Number(beforeParam);
      if (Number.isFinite(asNum) && asNum > 1_000_000_000) {
        // Treat numbers > 1e9 as unix seconds; smaller values are ambiguous.
        beforeDate = new Date(
          asNum > 1e12 ? asNum : asNum * 1000, // auto-detect ms vs s
        );
      } else {
        const parsed = new Date(beforeParam);
        if (!Number.isNaN(parsed.getTime())) beforeDate = parsed;
      }
    }
    const isCursorMode = beforeDate !== null;

    const now = new Date();
    const todayStr = now.toISOString().split("T")[0];

    const endDate = isCursorMode
      ? beforeDate!
      : endParam
      ? new Date(endParam)
      : now;
    const startDate = isCursorMode
      ? new Date(0) // fetch as far back as needed; the LIMIT caps the count
      : startParam
      ? new Date(startParam)
      : new Date(endDate.getTime() - rawDays * 24 * 60 * 60 * 1000);

    // -------------------------------------------------------------------------
    // Step 1 — Futures resolution (before symbol lookup)
    // -------------------------------------------------------------------------
    const supabase = getSupabaseClient();
    let resolvedSymbol = symbol;
    let futuresMetadata: FuturesMetadata | null = null;

    const futuresMatch = FUTURES_PATTERN.exec(symbol);
    if (futuresMatch) {
      // futuresMatch[1] = root (e.g. "ES"), futuresMatch[2] = suffix (e.g. "1!" or "H26")
      const futuresRoot = futuresMatch[1].toUpperCase();
      const isContinuousSuffix = /^\d+!$/.test(futuresMatch[2]); // e.g. "1!", "2!"
      console.log(
        `[chart] Detected futures symbol: ${symbol} (root=${futuresRoot})`,
      );
      try {
        const { data: resolved, error: resolveError } = await supabase.rpc(
          "resolve_futures_symbol",
          { p_symbol: symbol, p_as_of: todayStr },
        );
        if (!resolveError && Array.isArray(resolved) && resolved.length > 0) {
          const result = resolved[0] as {
            resolved_symbol: string;
            is_continuous: boolean;
          };
          resolvedSymbol = result.resolved_symbol;
          futuresMetadata = {
            requested_symbol: symbol,
            resolved_symbol: resolvedSymbol,
            is_continuous: result.is_continuous,
            root_id: null, // filled in after symbol lookup below
            expiry_info: null, // filled in after symbol lookup below
          };
          console.log(`[chart] Resolved ${symbol} → ${resolvedSymbol}`);
        } else {
          // RPC unavailable or returned nothing — fall back to the root symbol.
          // "ES1!" → "ES", "GCZ25" → "GC"
          resolvedSymbol = futuresRoot;
          futuresMetadata = {
            requested_symbol: symbol,
            resolved_symbol: resolvedSymbol,
            is_continuous: isContinuousSuffix,
            root_id: null,
            expiry_info: null,
          };
          console.log(
            `[chart] resolve_futures_symbol unavailable, falling back to root: ${resolvedSymbol}`,
          );
        }
      } catch (err) {
        console.error(`[chart] Error resolving futures symbol:`, err);
        // Fall back to root symbol
        resolvedSymbol = futuresRoot;
        futuresMetadata = {
          requested_symbol: symbol,
          resolved_symbol: resolvedSymbol,
          is_continuous: isContinuousSuffix,
          root_id: null,
          expiry_info: null,
        };
      }
    }

    // -------------------------------------------------------------------------
    // Step 2 — Symbol lookup (sequential — everything else depends on symbol_id)
    // -------------------------------------------------------------------------
    const { data: symbolData, error: symbolError } = await supabase
      .from("symbols")
      .select("id, ticker, asset_type, name, is_active")
      .eq("ticker", resolvedSymbol)
      .single();

    if (symbolError || !symbolData) {
      return new Response(
        JSON.stringify({ error: `Symbol not found: ${resolvedSymbol}` }),
        {
          status: 404,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        },
      );
    }

    const symbolId = symbolData.id as string;
    const assetType = (symbolData.asset_type as string) || "unknown";

    // Populate futures metadata from symbol row when available.
    // Note: futures-specific columns (futures_root_id, is_continuous, expiry_month, expiry_year)
    // are stored in futures_contracts/futures_roots tables, not the symbols table.
    // Expiry info is resolved via the resolve_futures_symbol RPC in Step 1 above.
    if (!futuresMetadata && assetType === "future") {
      // Symbol is a future but didn't match futures pattern — populate minimal metadata
      futuresMetadata = {
        requested_symbol: symbol,
        resolved_symbol: resolvedSymbol,
        is_continuous: false,
        root_id: null,
        expiry_info: null,
      };
    }

    // -------------------------------------------------------------------------
    // Step 3 — Parallel DB queries (all independent after symbol_id is known)
    // -------------------------------------------------------------------------
    const isIntraday = ["m15", "h1", "h4"].includes(timeframe);
    // For 4h charts we use the 1h intraday forecast row
    const intradayHorizonTf = timeframe === "h4" ? "h1" : timeframe;
    const expiryCutoffIso = new Date(
      Date.now() - INTRADAY_FORECAST_EXPIRY_GRACE_SECONDS * 1000,
    ).toISOString();

    const [
      barsResult,
      optionsResult,
      dailyForecastResult,
      intradayForecastResult,
      marketStatusResult,
      corporateActionsResult,
      activeJobsResult,
      m1BarsResult,
    ] = await Promise.all([
      // 1. OHLC bars via get_chart_data_v2 RPC (provider-aware)
      // The RPC now accepts p_limit to enforce the cap inside Postgres,
      // bypassing the PostgREST default 1000-row limit on RPC results.
      // In cursor mode we skip the RPC (it doesn't support strict-less-than
      // + DESC ordering) and go straight to the fallback path below.
      isCursorMode
        ? Promise.resolve({
          data: null,
          error: { message: "cursor_mode_skip" },
        })
        : supabase.rpc("get_chart_data_v2", {
          p_symbol_id: symbolId,
          p_timeframe: timeframe === "w1" ? "d1" : timeframe, // weekly: fetch d1 then aggregate
          p_start_date: startDate.toISOString(),
          p_end_date: endDate.toISOString(),
          p_limit: barLimit,
        }),

      // 2. Options ranks
      includeOptions
        ? supabase
          .from("options_ranks")
          .select(
            "expiry, strike, side, ml_score, implied_vol, delta, gamma, theta, vega, open_interest, volume, run_at",
          )
          .eq("underlying_symbol_id", symbolId)
          .order("ml_score", { ascending: false })
          .limit(50)
        : Promise.resolve({ data: null, error: null }),

      // 3. Daily forecast summary (latest_forecast_summary view)
      includeForecast || includeML
        ? supabase
          .from("latest_forecast_summary")
          .select(
            "overall_label, confidence, horizon, run_at, points, sr_levels, sr_density, supertrend_factor, supertrend_signal, supertrend_direction, trend_label, trend_confidence, stop_level, trend_duration_bars, rsi, adx, macd_histogram, kdj_j, adaptive_supertrend_factor, adaptive_supertrend_signal",
          )
          .eq("symbol_id", symbolId)
          .limit(1)
          .single()
        : Promise.resolve({ data: null, error: null }),

      // 4. Intraday forecast (ml_forecasts_intraday)
      (includeForecast || includeML) && isIntraday
        ? supabase
          .from("ml_forecasts_intraday")
          .select("*")
          .eq("symbol_id", symbolId)
          .eq("timeframe", intradayHorizonTf)
          .gte("expires_at", expiryCutoffIso)
          .order("created_at", { ascending: false })
          .limit(1)
          .maybeSingle()
        : Promise.resolve({ data: null, error: null }),

      // 5. Market open status
      supabase.rpc("is_market_open"),

      // 6. Corporate actions (pending splits)
      supabase
        .from("corporate_actions")
        .select("id")
        .eq("symbol", resolvedSymbol)
        .eq("bars_adjusted", false)
        .in("action_type", ["stock_split", "reverse_split"])
        .limit(1),

      // 7. Active ingest jobs
      supabase
        .from("job_runs")
        .select("id")
        .eq("symbol", resolvedSymbol)
        .eq("timeframe", timeframe)
        .in("status", ["queued", "running"])
        .limit(1),

      // 8. m1 bars for partial candle synthesis (d1/w1/h1/h4/m15)
      // Fetch up to 8h back so all timeframes are covered (m15 only needs 15m but
      // the filter in synthesizePartialBar slices to the current period).
      ["d1", "w1", "h1", "h4", "m15"].includes(timeframe)
        ? supabase
          .from("ohlc_bars_v2")
          .select("ts, open, high, low, close, volume")
          .eq("symbol_id", symbolId)
          .eq("timeframe", "m1")
          .eq("is_intraday", true)
          .eq("is_forecast", false)
          .gte(
            "ts",
            new Date(now.getTime() - 8 * 60 * 60 * 1000).toISOString(),
          )
          .order("ts", { ascending: true })
          .limit(600)
        : Promise.resolve({ data: null, error: null }),
    ]);

    // ── Extract market status early (needed for partial candle synthesis) ─────
    let isMarketOpen = false;
    try {
      isMarketOpen = marketStatusResult.data ?? false;
    } catch {
      const hour = now.getUTCHours();
      const dow = now.getUTCDay();
      isMarketOpen = dow >= MARKET_WEEKDAY_START &&
        dow <= MARKET_WEEKDAY_END &&
        hour >= MARKET_OPEN_HOUR_UTC &&
        hour < MARKET_CLOSE_HOUR_UTC;
    }

    // -------------------------------------------------------------------------
    // Step 4 — Process bars + weekly aggregation
    // -------------------------------------------------------------------------
    let barsData: BarRow[] = [];
    if (barsResult.error) {
      if (!isCursorMode) {
        console.error("[chart] Bars RPC error:", barsResult.error);
      }
      if (isCursorMode) {
        // Cursor-based backward pagination: fetch `pageSize` bars with ts < before,
        // ordered DESC so we get the most recent page, then reverse to ascending.
        const effectiveTf = timeframe === "w1" ? "d1" : timeframe;
        const { data: cursorBars } = await supabase
          .from("ohlc_bars_v2")
          .select("ts, open, high, low, close, volume, provider, data_status")
          .eq("symbol_id", symbolId)
          .eq("timeframe", effectiveTf)
          .eq("is_forecast", false)
          .lt("ts", beforeDate!.toISOString())
          .order("ts", { ascending: false })
          .limit(pageSize);
        // Reverse to ascending order so response shape is consistent
        barsData = ((cursorBars ?? []) as BarRow[]).reverse();
      } else {
        // Standard fallback: direct table query
        const { data: fallbackBars } = await supabase
          .from("ohlc_bars_v2")
          .select("ts, open, high, low, close, volume, provider, data_status")
          .eq("symbol_id", symbolId)
          .eq("timeframe", timeframe === "w1" ? "d1" : timeframe)
          .eq("is_forecast", false)
          .gte("ts", startDate.toISOString())
          .lte("ts", endDate.toISOString())
          .order("ts", { ascending: true })
          .limit(MAX_BAR_LIMIT);
        barsData = (fallbackBars ?? []) as BarRow[];
      }
    } else {
      barsData = (barsResult.data ?? []) as BarRow[];
    }

    // Map raw rows to OHLCBar
    let allBars: OHLCBar[] = barsData.map((bar) => ({
      ts: bar.ts,
      open: Number(bar.open),
      high: Number(bar.high),
      low: Number(bar.low),
      close: Number(bar.close),
      volume: Number(bar.volume || 0),
      provider: bar.provider || "unknown",
      is_forecast: bar.is_forecast === true,
    }));

    // ── Partial candle synthesis (before weekly aggregation) ─────────────────
    // When the market is open and m1 bars exist, synthesize the in-progress bar
    // for the current period and append it as the last bar.
    const PARTIAL_CANDLE_TFS = ["d1", "w1", "h1", "h4", "m15"];
    if (
      isMarketOpen &&
      PARTIAL_CANDLE_TFS.includes(timeframe) &&
      m1BarsResult.data &&
      m1BarsResult.data.length > 0
    ) {
      const m1Rows = m1BarsResult.data as BarRow[];
      // For w1: synthesize a d1 partial bar — weekly aggregation below will roll it up.
      // For all others (including m15): synthesize directly.
      const synthTf = (timeframe === "w1" ? "d1" : timeframe) as
        | "d1"
        | "h1"
        | "h4"
        | "m15";
      const partialBar = synthesizePartialBar(m1Rows, synthTf, now);
      if (partialBar) {
        const partialTsMs = new Date(partialBar.ts).getTime();
        // Remove existing bar at the same period boundary (replace with partial)
        allBars = allBars.filter(
          (b) => new Date(b.ts).getTime() !== partialTsMs,
        );
        allBars.push(partialBar);
      }
    }

    // ── On-demand snapshot fallback for non-watchlist symbols ─────────────────
    // If the symbol has no m1 bars in DB (not in watchlist_items or ingest hasn't
    // run yet), fetch a single Alpaca snapshot to get the current minuteBar.
    // Fail-open: any error → no partial bar appended (silent fallback).
    const noM1Data = !m1BarsResult.data || m1BarsResult.data.length === 0;
    const lastBarIsPartial = allBars.length > 0 &&
      allBars[allBars.length - 1].is_partial === true;
    if (
      isMarketOpen &&
      noM1Data &&
      !lastBarIsPartial &&
      PARTIAL_CANDLE_TFS.includes(timeframe)
    ) {
      try {
        const snapshotRateLimiter = new TokenBucketRateLimiter({
          alpaca: { maxPerSecond: 200, maxPerMinute: 10000 },
          finnhub: { maxPerSecond: 10, maxPerMinute: 600 },
          massive: { maxPerSecond: 10, maxPerMinute: 600 },
          yahoo: { maxPerSecond: 10, maxPerMinute: 600 },
          tradier: { maxPerSecond: 10, maxPerMinute: 600 },
        });
        const alpaca = new AlpacaClient(
          Deno.env.get("ALPACA_API_KEY")!,
          Deno.env.get("ALPACA_API_SECRET")!,
          snapshotRateLimiter,
          new MemoryCache(10),
        );
        const minuteBar = await alpaca.getSnapshot(resolvedSymbol);
        if (minuteBar) {
          // minuteBar.t is the start of the current 1-minute period
          const synthTf = (timeframe === "w1" ? "d1" : timeframe) as
            | "d1"
            | "h1"
            | "h4"
            | "m15";
          const periodStart = getPartialPeriodStart(synthTf, now);
          const snapshotBar: OHLCBar = {
            ts: periodStart.toISOString(),
            open: minuteBar.o,
            high: minuteBar.h,
            low: minuteBar.l,
            close: minuteBar.c,
            volume: minuteBar.v,
            provider: "alpaca",
            is_forecast: false,
            is_partial: true,
          };
          const partialTsMs = periodStart.getTime();
          allBars = allBars.filter(
            (b) => new Date(b.ts).getTime() !== partialTsMs,
          );
          allBars.push(snapshotBar);
        }
      } catch {
        // Snapshot fetch failed — chart ends at last closed bar (acceptable)
      }
    }

    // Weekly aggregation: w1 is fetched as d1 then aggregated here
    // (includes the partial d1 bar above when market is open)
    if (timeframe === "w1") {
      const historicalOnly = allBars.filter((b) => !b.is_forecast);
      allBars = aggregateWeeklyBars(historicalOnly);
      // Mark the last weekly bar as partial if market is open and it covers today
      if (isMarketOpen && allBars.length > 0) {
        const lastW1 = allBars[allBars.length - 1];
        const weekStart = new Date(lastW1.ts).getTime();
        const weekEnd = weekStart + 7 * 24 * 60 * 60 * 1000;
        if (now.getTime() >= weekStart && now.getTime() < weekEnd) {
          allBars[allBars.length - 1] = { ...lastW1, is_partial: true };
        }
      }
    }

    // Apply pagination (offset + limit, both capped)
    const paginatedBars = allBars.slice(barOffset, barOffset + barLimit);

    // Freshness must use ACTUAL bars only — forecast bars extend into the future
    // and would make stale data look "fresh", preventing refresh jobs from firing.
    const actualBars = allBars.filter((b) => !b.is_forecast);
    const lastActualBarTs = actualBars.length > 0
      ? actualBars[actualBars.length - 1].ts
      : null;
    // lastBarTs includes forecasts (for meta.lastBarTs display)
    const lastBarTs = allBars.length > 0
      ? allBars[allBars.length - 1].ts
      : null;

    // -------------------------------------------------------------------------
    // Step 5 — Freshness check + fire-and-forget stale refresh
    // -------------------------------------------------------------------------
    const slaMinutes = FRESHNESS_SLA_MINUTES[timeframe] ?? 1440;
    const ageMinutes = lastActualBarTs
      ? (Date.now() - new Date(lastActualBarTs).getTime()) / 60_000
      : null;
    const isStale = ageMinutes !== null && ageMinutes > slaMinutes;
    const hasActiveJob = (activeJobsResult.data?.length ?? 0) > 0;

    if (isStale && !hasActiveJob) {
      // Fire-and-forget: intentionally NOT awaited. Wrap in Promise.resolve so we can
      // attach a .catch handler regardless of whether the RPC builder is a native Promise.
      Promise.resolve(
        supabase.rpc("enqueue_job_slices", {
          p_job_def_id: null,
          p_symbol: resolvedSymbol,
          p_timeframe: timeframe,
          p_job_type: "backfill",
          p_slices: JSON.stringify([{
            from: startDate.toISOString(),
            to: endDate.toISOString(),
          }]),
          p_triggered_by: "chart_stale_refresh",
        }),
      ).catch((err: unknown) =>
        console.error("[chart] Failed to enqueue stale refresh:", err)
      );
    }

    const dataStatus: "fresh" | "stale" | "refreshing" = hasActiveJob
      ? "refreshing"
      : isStale
      ? "stale"
      : "fresh";

    // Step 6 — Market status extracted earlier (see early extraction block above)

    // -------------------------------------------------------------------------
    // Step 7 — ML enrichment: mlSummary + indicators
    // -------------------------------------------------------------------------
    let mlSummary: MLSummary | null = null;
    let indicators: ChartIndicators | null = null;
    let latestForecastRunAt: string | null = null;

    if (includeML) {
      try {
        if (intradayForecastResult.error) {
          console.error(
            "[chart] Intraday forecast query error:",
            intradayForecastResult.error.message,
          );
        }
        const intradayForecastData = intradayForecastResult.data as
          | IntradayForecastRow
          | null;

        if (dailyForecastResult.error) {
          console.error(
            "[chart] Daily forecast query error:",
            dailyForecastResult.error.message,
          );
        }
        const dailyForecastData = dailyForecastResult.data as
          | DailyForecastRow
          | null;

        // Secondary parallel fetch: both ML sub-queries run concurrently
        const [intradayPathResult, dailyForecastsResult] = await Promise.all([
          isIntraday && intradayForecastData
            ? supabase
              .from("ml_forecast_paths_intraday")
              .select("*")
              .eq("symbol_id", symbolId)
              .eq("timeframe", intradayHorizonTf)
              .eq("horizon", "7d")
              .gte("expires_at", expiryCutoffIso)
              .order("created_at", { ascending: false })
              .limit(1)
              .maybeSingle()
            : Promise.resolve({ data: null, error: null }),
          includeML
            ? supabase
              .from("ml_forecasts")
              .select("*")
              .eq("symbol_id", symbolId)
              .in("horizon", [...DAILY_FORECAST_HORIZONS])
              .order("created_at", { ascending: false })
              .limit(10)
            : Promise.resolve({ data: [], error: null }),
        ]);

        if (intradayPathResult.error) {
          console.error(
            "[chart] ml_forecast_paths_intraday query error:",
            intradayPathResult.error.message,
          );
        }
        if (dailyForecastsResult.error) {
          console.error(
            "[chart] ml_forecasts query error:",
            dailyForecastsResult.error.message,
          );
        }

        if (isIntraday && intradayForecastData) {
          // --- Intraday branch ---
          const conf = clampNumber(intradayForecastData.confidence, 0.5);
          latestForecastRunAt = intradayForecastData.created_at ?? null;

          const horizons: HorizonForecast[] = [];

          const intradayPathData = intradayPathResult.data as
            | IntradayPathRow
            | null;

          if (
            intradayPathData &&
            Array.isArray(intradayPathData.points) &&
            intradayPathData.points.length > 0
          ) {
            const pts = sampleForecastPoints(
              normalizeForecastPoints(intradayPathData.points),
              INTRADAY_FORECAST_MAX_POINTS,
            );
            if (pts.length > 0) horizons.push({ horizon: "7d", points: pts });
          }

          if (
            Array.isArray(intradayForecastData.points) &&
            intradayForecastData.points.length > 0
          ) {
            const pts = sampleForecastPoints(
              normalizeForecastPoints(intradayForecastData.points),
              INTRADAY_FORECAST_MAX_POINTS,
            );
            if (pts.length > 0) {
              horizons.push({
                horizon: intradayForecastData.horizon ??
                  (timeframe === "m15" ? "15m" : "1h"),
                points: pts,
              });
            }
          }

          mlSummary = {
            overallLabel: intradayForecastData.overall_label ??
              intradayPathData?.overall_label ?? null,
            confidence: conf,
            horizons,
            srLevels: null,
            srDensity: null,
          };

          const supertrendSignalRaw = intradayForecastData.supertrend_direction;
          indicators = {
            supertrendFactor: null,
            supertrendSignal: supertrendSignalRaw === "BULLISH"
              ? 1
              : supertrendSignalRaw === "BEARISH"
              ? -1
              : 0,
            trendLabel: intradayPathData?.overall_label ??
              intradayForecastData.overall_label ?? null,
            trendConfidence: Math.round(conf * 10),
            stopLevel: null,
            trendDurationBars: null,
            rsi: null,
            adx: null,
            macdHistogram: null,
            kdjJ: null,
          };

          // Also merge daily horizons onto intraday mlSummary
          if (dailyForecastData) {
            const dailyForecasts = dailyForecastsResult.data;

            if (Array.isArray(dailyForecasts)) {
              const latestByHorizon = new Map<
                string,
                Record<string, unknown>
              >();
              for (const row of dailyForecasts) {
                const h = typeof row?.horizon === "string" ? row.horizon : null;
                if (!h || latestByHorizon.has(h)) continue;
                latestByHorizon.set(h, row);
              }

              const dailySeries: HorizonForecast[] = [];
              for (const horizon of DAILY_FORECAST_HORIZONS) {
                const row = latestByHorizon.get(horizon);
                if (!row || !row["points"]) continue;
                const pts = sampleForecastPoints(
                  normalizeForecastPoints(row["points"]),
                  DAILY_FORECAST_MAX_POINTS,
                );
                if (pts.length === 0) continue;
                const targets = buildForecastTargets(row, pts);
                dailySeries.push({
                  horizon,
                  points: pts,
                  ...(targets ? { targets } : {}),
                });
              }

              if (dailySeries.length > 0) {
                const existingHorizons = new Set(
                  mlSummary.horizons.map((h) => h.horizon.toUpperCase()),
                );
                for (const ds of dailySeries) {
                  if (!existingHorizons.has(ds.horizon.toUpperCase())) {
                    mlSummary.horizons.push(ds);
                  }
                }
              }
            }
          }
        } else if (dailyForecastData) {
          // --- Daily / weekly branch ---
          latestForecastRunAt = dailyForecastData.run_at ?? null;
          const conf = clampNumber(dailyForecastData.confidence, 0.5);

          // Use pre-fetched daily forecasts from the secondary Promise.all above
          const dailyForecasts = dailyForecastsResult.data;

          if (Array.isArray(dailyForecasts) && dailyForecasts.length > 0) {
            const latestByHorizon = new Map<string, Record<string, unknown>>();
            for (const row of dailyForecasts) {
              const h = typeof row?.horizon === "string" ? row.horizon : null;
              if (!h || latestByHorizon.has(h)) continue;
              latestByHorizon.set(h, row);
            }

            const horizonSeries: HorizonForecast[] = [];
            let bestForecastRow: Record<string, unknown> = {};

            for (const horizon of DAILY_FORECAST_HORIZONS) {
              const row = latestByHorizon.get(horizon);
              if (!row || !row["points"]) continue;
              const pts = sampleForecastPoints(
                normalizeForecastPoints(row["points"]),
                DAILY_FORECAST_MAX_POINTS,
              );
              if (pts.length === 0) continue;
              const targets = buildForecastTargets(row, pts);
              horizonSeries.push({
                horizon,
                points: pts,
                ...(targets ? { targets } : {}),
              });

              // Pick the row with highest confidence as the best overall row
              if (
                Object.keys(bestForecastRow).length === 0 ||
                clampNumber(row["confidence"], -1) >
                  clampNumber(bestForecastRow["confidence"], -1)
              ) {
                bestForecastRow = row;
              }
            }

            if (horizonSeries.length > 0) {
              mlSummary = {
                overallLabel:
                  typeof bestForecastRow["overall_label"] === "string"
                    ? bestForecastRow["overall_label"]
                    : null,
                confidence: clampNumber(bestForecastRow["confidence"], conf),
                horizons: horizonSeries,
                srLevels:
                  (bestForecastRow["sr_levels"] as Record<string, unknown>) ??
                    null,
                srDensity: typeof bestForecastRow["sr_density"] === "number"
                  ? bestForecastRow["sr_density"]
                  : null,
              };

              indicators = {
                supertrendFactor:
                  typeof bestForecastRow["supertrend_factor"] === "number"
                    ? bestForecastRow["supertrend_factor"]
                    : (dailyForecastData.adaptive_supertrend_factor ?? null),
                supertrendSignal:
                  typeof bestForecastRow["supertrend_signal"] === "number"
                    ? bestForecastRow["supertrend_signal"]
                    : (dailyForecastData.adaptive_supertrend_signal ?? null),
                trendLabel: typeof bestForecastRow["trend_label"] === "string"
                  ? bestForecastRow["trend_label"]
                  : (dailyForecastData.trend_label ?? null),
                trendConfidence:
                  typeof bestForecastRow["trend_confidence"] === "number"
                    ? bestForecastRow["trend_confidence"]
                    : (dailyForecastData.trend_confidence ?? null),
                stopLevel: typeof bestForecastRow["stop_level"] === "number"
                  ? bestForecastRow["stop_level"]
                  : (dailyForecastData.stop_level ?? null),
                trendDurationBars:
                  typeof bestForecastRow["trend_duration_bars"] === "number"
                    ? bestForecastRow["trend_duration_bars"]
                    : (dailyForecastData.trend_duration_bars ?? null),
                rsi: typeof bestForecastRow["rsi"] === "number"
                  ? bestForecastRow["rsi"]
                  : (dailyForecastData.rsi ?? null),
                adx: typeof bestForecastRow["adx"] === "number"
                  ? bestForecastRow["adx"]
                  : (dailyForecastData.adx ?? null),
                macdHistogram:
                  typeof bestForecastRow["macd_histogram"] === "number"
                    ? bestForecastRow["macd_histogram"]
                    : (dailyForecastData.macd_histogram ?? null),
                kdjJ: typeof bestForecastRow["kdj_j"] === "number"
                  ? bestForecastRow["kdj_j"]
                  : (dailyForecastData.kdj_j ?? null),
              };
            }
          } else {
            // Fallback: use the single latest_forecast_summary row
            const pts = sampleForecastPoints(
              normalizeForecastPoints(dailyForecastData.points ?? []),
              DAILY_FORECAST_MAX_POINTS,
            );
            if (pts.length > 0) {
              mlSummary = {
                overallLabel: dailyForecastData.overall_label ?? null,
                confidence: conf,
                horizons: [{
                  horizon: dailyForecastData.horizon ?? "1D",
                  points: pts,
                }],
                srLevels: dailyForecastData.sr_levels ?? null,
                srDensity: dailyForecastData.sr_density ?? null,
              };
              indicators = {
                supertrendFactor:
                  dailyForecastData.adaptive_supertrend_factor ??
                    dailyForecastData.supertrend_factor ?? null,
                supertrendSignal:
                  dailyForecastData.adaptive_supertrend_signal ??
                    dailyForecastData.supertrend_signal ?? null,
                trendLabel: dailyForecastData.trend_label ?? null,
                trendConfidence: dailyForecastData.trend_confidence ?? null,
                stopLevel: dailyForecastData.stop_level ?? null,
                trendDurationBars: dailyForecastData.trend_duration_bars ??
                  null,
                rsi: dailyForecastData.rsi ?? null,
                adx: dailyForecastData.adx ?? null,
                macdHistogram: dailyForecastData.macd_histogram ?? null,
                kdjJ: dailyForecastData.kdj_j ?? null,
              };
            }
          }
        }

        // Ensure null (not undefined) when no ML data found
        if (mlSummary === null) mlSummary = null;
        if (indicators === null) indicators = null;
      } catch (mlError) {
        console.error("[chart] ML enrichment error:", mlError);
        mlSummary = null;
        indicators = null;
      }
    }

    // -------------------------------------------------------------------------
    // Step 8 — Append forecast bars to paginatedBars (if requested)
    // -------------------------------------------------------------------------
    const bars = [...paginatedBars];

    if (includeForecast && mlSummary && mlSummary.horizons.length > 0) {
      const existingTs = new Set(bars.map((b) => b.ts));
      const todayDate = new Date(todayStr);

      for (const horizonForecast of mlSummary.horizons) {
        for (const pt of horizonForecast.points) {
          const tsIso = new Date(pt.ts * 1000).toISOString();
          if (new Date(tsIso) <= todayDate) continue; // skip past/today points
          if (existingTs.has(tsIso)) continue;
          existingTs.add(tsIso);
          bars.push({
            ts: tsIso,
            open: pt.value,
            high: typeof pt.upper === "number" ? pt.upper : pt.value,
            low: typeof pt.lower === "number" ? pt.lower : pt.value,
            close: pt.value,
            volume: 0,
            provider: "ml_forecast",
            is_forecast: true,
          });
        }
      }

      bars.sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());
    }

    // ── Partial candle: recompute price-derived indicators ────────────────────
    // If the last bar is synthetic (is_partial=true), update RSI and MACD
    // histogram using the live price so the indicator panel reflects today's move.
    const lastBar = bars.length > 0 ? bars[bars.length - 1] : null;
    if (lastBar?.is_partial) {
      try {
        const closedBars = bars.filter((b) => !b.is_partial && !b.is_forecast);
        if (closedBars.length >= 14) {
          const barInput: BarInput = {
            closes: [...closedBars.map((b) => b.close), lastBar.close],
            highs: [...closedBars.map((b) => b.high), lastBar.high],
            lows: [...closedBars.map((b) => b.low), lastBar.low],
            volumes: [...closedBars.map((b) => b.volume), lastBar.volume],
            opens: [...closedBars.map((b) => b.open), lastBar.open],
          };
          const recomputed = recomputePartialIndicators(barInput);
          if (indicators !== null) {
            indicators = {
              ...indicators,
              rsi: recomputed.rsi ?? indicators.rsi,
              macdHistogram: recomputed.macdHistogram ??
                indicators.macdHistogram,
            };
          } else if (
            recomputed.rsi !== null || recomputed.macdHistogram !== null
          ) {
            indicators = {
              supertrendFactor: null,
              supertrendSignal: null,
              trendLabel: null,
              trendConfidence: null,
              stopLevel: null,
              trendDurationBars: null,
              rsi: recomputed.rsi,
              adx: null,
              macdHistogram: recomputed.macdHistogram,
              kdjJ: null,
            };
          }
        }
      } catch (indicatorErr) {
        console.warn(
          "[chart] Partial indicator recompute failed:",
          indicatorErr,
        );
      }
    }

    // -------------------------------------------------------------------------
    // Step 9 — Options ranks
    // -------------------------------------------------------------------------
    let optionsRanks: unknown[] = [];
    if (includeOptions && optionsResult.data) {
      optionsRanks = (optionsResult.data as OptionsRankRow[]).map((opt) => ({
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

    // -------------------------------------------------------------------------
    // Step 10 — Corporate actions / pending splits
    // -------------------------------------------------------------------------
    const hasPendingSplits = (corporateActionsResult.data?.length ?? 0) > 0;

    // -------------------------------------------------------------------------
    // Step 11 — DataQuality block (from chart-read)
    // -------------------------------------------------------------------------
    const paginatedActualBars = bars.filter((b) => !b.is_forecast);
    const newestActualBarTs = paginatedActualBars.length > 0
      ? paginatedActualBars[paginatedActualBars.length - 1].ts
      : null;
    const slaHours = slaMinutes / 60;

    const dataQuality: DataQuality = {
      dataAgeHours: newestActualBarTs
        ? Math.round(
          (Date.now() - new Date(newestActualBarTs).getTime()) /
            (1000 * 60 * 60),
        )
        : null,
      isStale, // also in freshness.isStale — kept here for backward compatibility with DataQuality contract
      slaHours,
      sufficientForML: paginatedActualBars.length >= 250,
      barCount: paginatedActualBars.length,
    };

    // -------------------------------------------------------------------------
    // Step 12 — Freshness block
    // -------------------------------------------------------------------------
    const isWithinSla = ageMinutes !== null ? ageMinutes <= slaMinutes : true;
    const freshness = {
      ageMinutes: ageMinutes !== null ? Math.round(ageMinutes) : null,
      slaMinutes,
      isWithinSla,
      // Enriched freshness metadata for client staleness indicators
      lastUpdated: lastActualBarTs ?? null,
      isStale: ageMinutes !== null ? ageMinutes > slaMinutes : false,
      ageSeconds: lastActualBarTs
        ? Math.round((Date.now() - new Date(lastActualBarTs).getTime()) / 1000)
        : null,
      slaSeconds: slaMinutes * 60,
    };

    // -------------------------------------------------------------------------
    // Step 13 — Meta block
    // -------------------------------------------------------------------------
    const meta: ChartMeta = {
      lastBarTs: lastActualBarTs,
      dataStatus,
      isMarketOpen,
      totalBars: bars.length,
      requestedRange: isCursorMode
        ? {
          start: bars.length > 0 ? bars[0].ts : beforeDate!.toISOString(),
          end: beforeDate!.toISOString(),
        }
        : {
          start: startDate.toISOString(),
          end: endDate.toISOString(),
        },
      latestForecastRunAt,
      hasPendingSplits,
    };

    // -------------------------------------------------------------------------
    // Step 14 — Optional layers structure
    // -------------------------------------------------------------------------
    let layers: ChartLayers | undefined;
    if (useLayers) {
      const historicalBars = bars.filter((b) => !b.is_forecast);
      const forecastBarsOnly = bars.filter((b) => b.is_forecast === true);
      layers = {
        historical: { count: historicalBars.length, data: historicalBars },
        intraday: { count: 0, data: [] }, // populated client-side or via separate intraday pass
        forecast: { count: forecastBarsOnly.length, data: forecastBarsOnly },
      };
    }

    // -------------------------------------------------------------------------
    // Step 15 — Build final response
    // -------------------------------------------------------------------------
    const response: UnifiedChartResponse = {
      symbol: resolvedSymbol,
      symbol_id: symbolId,
      timeframe,
      asset_type: assetType,
      bars,
      optionsRanks,
      mlSummary,
      indicators,
      meta,
      dataQuality,
      freshness,
      futures: futuresMetadata,
      ...(useLayers ? { layers } : {}),
    };

    const duration = Date.now() - startTime;
    console.log(
      `[chart] ${resolvedSymbol}/${timeframe}: ${bars.length} bars, ${duration}ms, status=${dataStatus}`,
    );

    return new Response(JSON.stringify(response), {
      status: 200,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("[chart] Unhandled error:", error);
    return new Response(
      JSON.stringify({ error: "An internal error occurred" }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      },
    );
  }
});
