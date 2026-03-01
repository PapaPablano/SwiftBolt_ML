# Chart Consolidation (028 → 037) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Merge `chart`, `chart-read`, and `chart-data-v2` into a single canonical `/chart` Edge Function; then standardize response envelopes across all Edge Functions (037).

**Architecture:** The unified `chart` function combines futures resolution (from v2), ML enrichment (from chart-read/v2), options data (from chart), and stale-data fire-and-forget refresh (from chart-read). The macOS client is updated to call a single endpoint. `chart-read` and `chart-data-v2` directories are deleted.

**Tech Stack:** Deno/TypeScript Edge Functions, Supabase PostgREST, Alpaca data, Swift/SwiftUI macOS client.

---

## Context: What Each Function Contributes

| Feature | Source |
|---------|--------|
| Futures symbol resolution (`GC1!` → `GCZ25`) | chart-data-v2 |
| Options ranks | chart |
| `dataQuality` block | chart-read / v2 |
| `mlSummary` + multi-horizon forecasts | chart-read / v2 |
| `indicators` (SuperTrend, RSI, ADX) | chart-read |
| Fire-and-forget stale refresh | chart-read (adapted) |
| Parallel DB queries | already done in 032 |
| `freshness` + `meta` blocks | chart |
| Weekly bar aggregation | chart-data-v2 |

## Unified Response Shape

```typescript
{
  symbol: string,
  symbol_id: string,
  timeframe: string,
  asset_type: "stock" | "future" | "etf" | "index",

  // Bars (flat, always present)
  bars: Array<{
    ts: string,           // ISO 8601
    open: number,
    high: number,
    low: number,
    close: number,
    volume: number,
    is_forecast?: boolean,
  }>,

  // Optional layered structure (?layers=true)
  layers?: {
    historical: { count: number, data: OHLCBar[] },
    intraday:   { count: number, data: OHLCBar[] },
    forecast:   { count: number, data: OHLCBar[] },
  },

  // Options (empty [] when include_options=false)
  optionsRanks: OptionsRank[],

  // ML enrichment (null when include_ml=false)
  mlSummary: {
    overallLabel: string | null,
    confidence: number,
    horizons: Array<{ horizon: string, points: ForecastPoint[] }>,
    srLevels: Record<string, unknown> | null,
  } | null,

  indicators: {
    supertrendFactor: number | null,
    supertrendSignal: number | null,   // -1 | 0 | 1
    trendLabel: string | null,
    trendConfidence: number | null,
    stopLevel: number | null,
    rsi: number | null,
    adx: number | null,
    macdHistogram: number | null,
  } | null,

  // Freshness (merged from all three)
  meta: {
    lastBarTs: string | null,
    dataStatus: "fresh" | "stale" | "refreshing",
    isMarketOpen: boolean,
    totalBars: number,
    requestedRange: { start: string, end: string },
  },
  dataQuality: {
    dataAgeHours: number | null,
    isStale: boolean,
    slaHours: number,
    sufficientForML: boolean,
    barCount: number,
  },
  freshness: {
    ageMinutes: number | null,
    slaMinutes: number,
    isWithinSla: boolean,
  },

  // Futures metadata (null for equities)
  futures: {
    requested_symbol: string,
    resolved_symbol: string,
    is_continuous: boolean,
    expiry_info: { month: number, year: number, display: string } | null,
  } | null,
}
```

---

## Task 1: Read current chart/index.ts in full

**Files:**
- Read: `supabase/functions/chart/index.ts`
- Read: `supabase/functions/chart-read/index.ts` (focus on: freshness check logic, stale refresh enqueue, mlSummary builder, indicators builder, dataQuality builder)
- Read: `supabase/functions/chart-data-v2/index.ts` (focus on: futures resolution block, weekly aggregation block, layers builder)

**Step 1:** Read all three files and note exact line ranges for each feature block to be extracted.

**Step 2:** Note all shared imports and types needed.

No code changes yet. This is understanding only.

---

## Task 2: Create shared types file for chart response

**Files:**
- Create: `supabase/functions/_shared/chart-types.ts`

**Step 1:** Create the file with all TypeScript interfaces:

```typescript
// supabase/functions/_shared/chart-types.ts

export interface OHLCBar {
  ts: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  is_forecast?: boolean;
  provider?: string;
}

export interface ForecastPoint {
  ts: number;
  value: number;
  lower?: number;
  upper?: number;
}

export interface HorizonForecast {
  horizon: string;
  points: ForecastPoint[];
  targets?: Record<string, number | null>;
}

export interface MLSummary {
  overallLabel: string | null;
  confidence: number;
  horizons: HorizonForecast[];
  srLevels: Record<string, unknown> | null;
  srDensity: number | null;
}

export interface ChartIndicators {
  supertrendFactor: number | null;
  supertrendSignal: number | null;
  trendLabel: string | null;
  trendConfidence: number | null;
  stopLevel: number | null;
  trendDurationBars: number | null;
  rsi: number | null;
  adx: number | null;
  macdHistogram: number | null;
  kdjJ: number | null;
}

export interface ChartMeta {
  lastBarTs: string | null;
  dataStatus: "fresh" | "stale" | "refreshing";
  isMarketOpen: boolean;
  totalBars: number;
  requestedRange: { start: string; end: string };
  latestForecastRunAt: string | null;
  hasPendingSplits: boolean;
}

export interface DataQuality {
  dataAgeHours: number | null;
  isStale: boolean;
  slaHours: number;
  sufficientForML: boolean;
  barCount: number;
}

export interface Freshness {
  ageMinutes: number | null;
  slaMinutes: number;
  isWithinSla: boolean;
}

export interface FuturesMetadata {
  requested_symbol: string;
  resolved_symbol: string;
  is_continuous: boolean;
  root_id: string | null;
  expiry_info: { month: number; year: number; display: string } | null;
}

export interface ChartLayers {
  historical: { count: number; data: OHLCBar[] };
  intraday: { count: number; data: OHLCBar[] };
  forecast: { count: number; data: OHLCBar[] };
}

export interface UnifiedChartResponse {
  symbol: string;
  symbol_id: string;
  timeframe: string;
  asset_type: string;
  bars: OHLCBar[];
  layers?: ChartLayers;
  optionsRanks: unknown[];
  mlSummary: MLSummary | null;
  indicators: ChartIndicators | null;
  meta: ChartMeta;
  dataQuality: DataQuality;
  freshness: Freshness;
  futures: FuturesMetadata | null;
}
```

**Step 2:** Commit:
```bash
git add supabase/functions/_shared/chart-types.ts
git commit -m "feat(chart): add shared chart response types"
```

---

## Task 3: Write the unified chart/index.ts — skeleton + request parsing

**Files:**
- Modify: `supabase/functions/chart/index.ts` (full rewrite)

**Step 1:** Replace the entire file with this skeleton (fill in imports from existing chart/index.ts):

```typescript
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";
import { getCorsHeaders, handleCorsOptions } from "../_shared/cors.ts";
import type { UnifiedChartResponse } from "../_shared/chart-types.ts";

// Freshness SLA in minutes per timeframe
const FRESHNESS_SLA_MINUTES: Record<string, number> = {
  m15: 30,
  m30: 60,
  h1: 120,
  h4: 480,
  d1: 1440,
  w1: 10080,
};

// Futures contract pattern: ES1!, GCZ25, NQH26, etc.
const FUTURES_PATTERN = /^([A-Z]{1,6})(\d{1,2}!|[FGHJKMNQUVXZ]\d{2})$/i;

serve(async (req: Request): Promise<Response> => {
  const origin = req.headers.get("Origin");
  const corsHeaders = getCorsHeaders(origin);

  if (req.method === "OPTIONS") {
    return handleCorsOptions(origin);
  }

  const supabase = getSupabaseClient();
  const url = new URL(req.url);

  // ── 1. Parse request params ──────────────────────────────────────────────
  const symbol = (url.searchParams.get("symbol") ?? "").toUpperCase();
  const timeframe = url.searchParams.get("timeframe") ?? "d1";
  const days = Math.min(3650, Math.max(1, Number(url.searchParams.get("days") || 180)));
  const includeOptions = url.searchParams.get("include_options") !== "false";
  const includeForecast = url.searchParams.get("include_forecast") !== "false";
  const includeML = url.searchParams.get("include_ml") !== "false";
  const useLayers = url.searchParams.get("layers") === "true";
  const barsLimit = Math.min(2000, Math.max(1, Number(url.searchParams.get("bars_limit") || 2000)));
  const barsOffset = Math.max(0, Number(url.searchParams.get("bars_offset") || 0));

  if (!symbol) {
    return new Response(JSON.stringify({ error: "symbol is required" }), {
      status: 400,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const endDate = url.searchParams.get("end") ?? new Date().toISOString();
  const startDate = url.searchParams.get("start") ??
    new Date(Date.now() - days * 86_400_000).toISOString();

  try {
    // ── 2. Futures resolution ─────────────────────────────────────────────
    let resolvedSymbol = symbol;
    let futuresMetadata = null;

    if (FUTURES_PATTERN.test(symbol)) {
      // [COPY futures resolution block from chart-data-v2/index.ts]
      // Sets resolvedSymbol, futuresMetadata
    }

    // ── 3. Symbol lookup ──────────────────────────────────────────────────
    const { data: symbolData, error: symbolError } = await supabase
      .from("symbols")
      .select("id, ticker, asset_type, futures_root_id, is_continuous")
      .eq("ticker", resolvedSymbol)
      .single();

    if (symbolError || !symbolData) {
      return new Response(JSON.stringify({ error: `Symbol not found: ${symbol}` }), {
        status: 404,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const symbolId = symbolData.id;

    // ── 4. Parallel DB queries ────────────────────────────────────────────
    const [
      barsResult,
      optionsResult,
      mlForecastResult,
      intradayForecastResult,
      marketStatusResult,
      corpActionsResult,
      activeJobsResult,
    ] = await Promise.all([
      // [COPY bars query from chart/index.ts — already parallelized in 032]
      supabase.rpc("get_chart_data_v2", { /* params */ }),
      includeOptions
        ? supabase.from("options_ranks").select("*").eq("symbol_id", symbolId).limit(50)
        : Promise.resolve({ data: [] }),
      includeForecast
        ? supabase.from("latest_forecast_summary").select("*").eq("symbol_id", symbolId).single()
        : Promise.resolve({ data: null }),
      includeML
        ? supabase.from("ml_forecasts_intraday").select("*").eq("symbol_id", symbolId).single()
        : Promise.resolve({ data: null }),
      supabase.rpc("is_market_open"),
      supabase.from("corporate_actions").select("id").eq("symbol_id", symbolId).limit(1),
      supabase.from("job_runs").select("id")
        .eq("symbol", resolvedSymbol).eq("timeframe", timeframe)
        .in("status", ["queued", "running"]).limit(1),
    ]);

    // ── 5. Check freshness + fire-and-forget refresh if stale ─────────────
    // [COPY freshness check from chart-read/index.ts]
    // [If stale: enqueue job slice with fire-and-forget, don't await]

    // ── 6. Build response ─────────────────────────────────────────────────
    const response: UnifiedChartResponse = {
      symbol: resolvedSymbol,
      symbol_id: symbolId,
      timeframe,
      asset_type: symbolData.asset_type ?? "stock",
      bars: [], // [populate from barsResult]
      optionsRanks: optionsResult.data ?? [],
      mlSummary: null, // [build from mlForecastResult + intradayForecastResult]
      indicators: null, // [build from mlForecastResult]
      meta: { /* build */ },
      dataQuality: { /* build */ },
      freshness: { /* build */ },
      futures: futuresMetadata,
    };

    if (useLayers) {
      // [populate response.layers from bars separated by is_forecast flag]
    }

    return new Response(JSON.stringify(response), {
      status: 200,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });

  } catch (err) {
    console.error("[chart] Unexpected error:", err);
    return new Response(JSON.stringify({ error: "An internal error occurred" }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
```

**Step 2:** Verify the skeleton compiles (deno check):
```bash
cd /Users/ericpeterson/SwiftBolt_ML
deno check supabase/functions/chart/index.ts
```

**Step 3:** Commit skeleton:
```bash
git add supabase/functions/chart/index.ts supabase/functions/_shared/chart-types.ts
git commit -m "feat(chart): add unified chart skeleton + shared types"
```

---

## Task 4: Implement futures resolution block

**Files:**
- Modify: `supabase/functions/chart/index.ts`
- Reference: `supabase/functions/chart-data-v2/index.ts` (futures resolution, lines ~650-714)

**Step 1:** Copy and adapt the futures resolution block from `chart-data-v2/index.ts` into the `// [COPY futures resolution block]` placeholder in the new chart function.

The block should:
1. Check if `FUTURES_PATTERN.test(symbol)` is true
2. Call `supabase.rpc("resolve_futures_symbol", { p_symbol: symbol, p_as_of: todayStr })`
3. Set `resolvedSymbol = resolved[0].resolved_symbol`
4. Build `futuresMetadata` object with `requested_symbol`, `resolved_symbol`, `is_continuous`, `root_id`, `expiry_info`
5. If resolution fails, fall back to using the original symbol as-is

**Step 2:** Test with a futures symbol manually (or trace through logic):
- Input: `symbol=GC1!` → should resolve to `GCZ25` (or current front month)
- Input: `symbol=AAPL` → should skip resolution, `futuresMetadata = null`

**Step 3:** Commit:
```bash
git add supabase/functions/chart/index.ts
git commit -m "feat(chart): add futures symbol resolution to unified endpoint"
```

---

## Task 5: Implement bars query + weekly aggregation

**Files:**
- Modify: `supabase/functions/chart/index.ts`
- Reference: `supabase/functions/chart/index.ts` (original bars RPC call, before rewrite)
- Reference: `supabase/functions/chart-data-v2/index.ts` (weekly aggregation block)

**Step 1:** Replace the bars RPC placeholder with the real query. Use `get_chart_data_v2` RPC for daily/weekly, `get_chart_data_v2_dynamic` for intraday (from chart-read):

```typescript
const { data: barsData, error: barsError } = await supabase.rpc("get_chart_data_v2", {
  p_symbol_id: symbolId,
  p_timeframe: timeframe === "w1" ? "d1" : timeframe, // fetch d1, aggregate to w1 if needed
  p_start_date: startDate,
  p_end_date: endDate,
});
```

**Step 2:** Add weekly aggregation (from chart-data-v2) if `timeframe === "w1"`:
- Group d1 bars by ISO week
- Take first open, last close, max high, min low, sum volume for each week
- Replace `barsData` with weekly bars

**Step 3:** Apply `barsOffset` and `barsLimit` slicing (already capped at 2000 from 055):
```typescript
const allBars = (barsData ?? []) as OHLCBar[];
const bars = allBars.slice(barsOffset, barsOffset + barsLimit);
```

**Step 4:** Set `response.bars = bars`

**Step 5:** Commit:
```bash
git add supabase/functions/chart/index.ts
git commit -m "feat(chart): implement bars query and weekly aggregation"
```

---

## Task 6: Implement freshness check + fire-and-forget refresh

**Files:**
- Modify: `supabase/functions/chart/index.ts`
- Reference: `supabase/functions/chart-read/index.ts` (freshness check + job enqueue)

**Step 1:** After bars query, compute data age:
```typescript
const slaMinutes = FRESHNESS_SLA_MINUTES[timeframe] ?? 1440;
const lastBarTs = bars.length > 0 ? bars[bars.length - 1].ts : null;
const ageMinutes = lastBarTs
  ? (Date.now() - new Date(lastBarTs).getTime()) / 60_000
  : null;
const isStale = ageMinutes !== null && ageMinutes > slaMinutes;
const hasActiveJob = (activeJobsResult.data?.length ?? 0) > 0;
```

**Step 2:** If stale and no active refresh job, fire-and-forget enqueue:
```typescript
if (isStale && !hasActiveJob) {
  // Fire-and-forget — do NOT await
  supabase.rpc("enqueue_job_slices", {
    p_symbol: resolvedSymbol,
    p_timeframe: timeframe,
    p_job_type: "backfill",
    p_slices: [{ from: startDate, to: endDate }],
    p_triggered_by: "chart_stale_refresh",
  }).catch(err => console.error("[chart] Failed to enqueue stale refresh:", err));
}
```

**Step 3:** Set `dataStatus` in response meta:
```typescript
const dataStatus = hasActiveJob ? "refreshing" : isStale ? "stale" : "fresh";
```

**Step 4:** Populate `freshness`, `dataQuality`, `meta` blocks in response.

**Step 5:** Commit:
```bash
git add supabase/functions/chart/index.ts
git commit -m "feat(chart): add stale-data detection and fire-and-forget refresh"
```

---

## Task 7: Implement ML enrichment (mlSummary + indicators)

**Files:**
- Modify: `supabase/functions/chart/index.ts`
- Reference: `supabase/functions/chart-read/index.ts` (mlSummary builder, ~lines 400-600)
- Reference: `supabase/functions/chart-data-v2/index.ts` (indicators builder)

**Step 1:** Build `mlSummary` from forecast query results. From chart-read, the pattern is:
- Prefer intraday forecasts if available (`ml_forecasts_intraday`)
- Fall back to daily (`latest_forecast_summary`)
- Structure into `{ overallLabel, confidence, horizons: [...], srLevels }`

**Step 2:** Build `indicators` from adaptive supertrend fields in the forecast data:
```typescript
const indicators: ChartIndicators = {
  supertrendFactor: forecastData?.adaptive_supertrend_factor ?? null,
  supertrendSignal: forecastData?.adaptive_supertrend_signal ?? null,
  trendLabel: forecastData?.trend_label ?? null,
  trendConfidence: forecastData?.trend_confidence ?? null,
  stopLevel: forecastData?.stop_level ?? null,
  trendDurationBars: forecastData?.trend_duration_bars ?? null,
  rsi: forecastData?.rsi ?? null,
  adx: forecastData?.adx ?? null,
  macdHistogram: forecastData?.macd_histogram ?? null,
  kdjJ: forecastData?.kdj_j ?? null,
};
```

**Step 3:** Add forecast bars to the main `bars` array (with `is_forecast: true` flag) if `includeForecast`.

**Step 4:** Build optional `layers` structure if `useLayers`:
```typescript
if (useLayers) {
  response.layers = {
    historical: { count: historicalBars.length, data: historicalBars },
    intraday: { count: intradayBars.length, data: intradayBars },
    forecast: { count: forecastBars.length, data: forecastBars },
  };
}
```

**Step 5:** Commit:
```bash
git add supabase/functions/chart/index.ts
git commit -m "feat(chart): add ML enrichment, indicators, and layered bars structure"
```

---

## Task 8: Test the unified endpoint manually

**Step 1:** Start local Supabase:
```bash
cd /Users/ericpeterson/SwiftBolt_ML
npx supabase start
npx supabase functions serve chart
```

**Step 2:** Test equity:
```bash
curl "http://localhost:54321/functions/v1/chart?symbol=AAPL&timeframe=d1&days=30" \
  -H "Authorization: Bearer <anon-key>" | jq '{symbol, timeframe, barCount: (.bars | length), hasMlSummary: (.mlSummary != null), dataStatus: .meta.dataStatus}'
```
Expected: `{ symbol: "AAPL", timeframe: "d1", barCount: 30, hasMlSummary: true/false, dataStatus: "fresh"/"stale" }`

**Step 3:** Test futures:
```bash
curl "http://localhost:54321/functions/v1/chart?symbol=GC1!&timeframe=d1&days=30" \
  -H "Authorization: Bearer <anon-key>" | jq '{symbol, futures}'
```
Expected: `futures` field is non-null with `resolved_symbol` like `"GCZ25"`

**Step 4:** Test weekly aggregation:
```bash
curl "http://localhost:54321/functions/v1/chart?symbol=AAPL&timeframe=w1&days=90" \
  -H "Authorization: Bearer <anon-key>" | jq '.bars | length'
```
Expected: ~13 bars (90 days / 7 days per week)

**Step 5:** Test with layers:
```bash
curl "http://localhost:54321/functions/v1/chart?symbol=AAPL&timeframe=d1&layers=true" \
  -H "Authorization: Bearer <anon-key>" | jq 'has("layers")'
```
Expected: `true`

---

## Task 9: Update macOS ChartViewModel.swift

**Files:**
- Modify: `client-macos/SwiftBoltML/ViewModels/ChartViewModel.swift`
- Reference: Current `fetchChart()`, `fetchChartRead()`, `fetchChartV2()` methods

**Step 1:** Read `ChartViewModel.swift` to understand the current 3-function fallback chain and the response types it expects.

**Step 2:** Create a new `UnifiedChartResponse` Swift Codable struct that matches the response shape:
```swift
struct UnifiedChartResponse: Codable {
    let symbol: String
    let symbolId: String
    let timeframe: String
    let assetType: String
    let bars: [ChartBar]
    let optionsRanks: [OptionsRank]
    let mlSummary: MLSummary?
    let indicators: ChartIndicators?
    let meta: ChartMeta
    let dataQuality: DataQuality
    let freshness: FreshnessData
    let futures: FuturesMetadata?

    // Optional layered structure
    let layers: ChartLayers?

    enum CodingKeys: String, CodingKey {
        case symbol, timeframe, bars, optionsRanks, mlSummary, indicators, meta, dataQuality, freshness, futures, layers
        case symbolId = "symbol_id"
        case assetType = "asset_type"
    }
}
```

**Step 3:** Replace the 3-function fallback chain with a single `fetchChart()` method:
```swift
func fetchChart(symbol: String, timeframe: String, days: Int = 180) async throws -> UnifiedChartResponse {
    let url = "\(supabaseUrl)/functions/v1/chart?symbol=\(symbol)&timeframe=\(timeframe)&days=\(days)"
    var request = URLRequest(url: URL(string: url)!)
    request.setValue("Bearer \(supabaseAnonKey)", forHTTPHeaderField: "Authorization")
    request.setValue(supabaseAnonKey, forHTTPHeaderField: "apikey")

    let (data, response) = try await URLSession.shared.data(for: request)
    guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
        throw ChartError.fetchFailed
    }
    return try JSONDecoder().decode(UnifiedChartResponse.self, from: data)
}
```

**Step 4:** Update `loadChart()` or equivalent to call `fetchChart()` and map to view model state.

**Step 5:** Remove `fetchChartRead()` and `fetchChartV2()` methods.

**Step 6:** Build in Xcode to verify no compile errors.

**Step 7:** Commit:
```bash
git add client-macos/
git commit -m "feat(macos): update ChartViewModel to use unified /chart endpoint"
```

---

## Task 10: Delete chart-read and chart-data-v2

**Files:**
- Delete: `supabase/functions/chart-read/` (entire directory)
- Delete: `supabase/functions/chart-data-v2/` (entire directory)
- Modify: `supabase/config.toml` (remove chart-read and chart-data-v2 function entries)

**Step 1:** Remove entries from config.toml:
```bash
# Find and remove [functions.chart-read] and [functions.chart-data-v2] sections
```

**Step 2:** Delete directories:
```bash
rm -rf supabase/functions/chart-read
rm -rf supabase/functions/chart-data-v2
```

**Step 3:** Verify no remaining references:
```bash
grep -r "chart-read\|chart-data-v2" supabase/ frontend/ client-macos/ --include="*.ts" --include="*.swift" --include="*.tsx"
```
Expected: no results (or only in comments/docs).

**Step 4:** Commit:
```bash
git add -A supabase/functions/chart-read supabase/functions/chart-data-v2 supabase/config.toml
git commit -m "chore(chart): delete retired chart-read and chart-data-v2 functions"
```

---

## Task 11: Mark todo 028 resolved + deploy

**Step 1:** Rename todo file:
```bash
mv todos/028-pending-p1-three-chart-functions-divergent-contracts.md \
   todos/028-resolved-p1-three-chart-functions-divergent-contracts.md
```

**Step 2:** Deploy to Supabase:
```bash
npx supabase functions deploy chart
```

**Step 3:** Run smoke test against production:
```bash
curl "https://cygflaemtmwiwaviclks.supabase.co/functions/v1/chart?symbol=AAPL&timeframe=d1" \
  -H "Authorization: Bearer <anon-key>" | jq '.meta.dataStatus'
```

**Step 4:** Final commit:
```bash
git add todos/
git commit -m "chore(todos): mark 028 chart consolidation as resolved"
```

---

## Task 12 (037): Standardize response envelopes across all Edge Functions

This task begins after 028 is complete.

**Goal:** All Edge Functions return `{ data: T }` on success and `{ error: string, code?: string }` on failure.

**Files:**
- Create: `supabase/functions/_shared/response.ts`
- Modify: Every Edge Function that doesn't yet use the standard envelope

**Step 1:** Create `_shared/response.ts`:
```typescript
// Standard response helpers for all Edge Functions
import { getCorsHeaders } from "./cors.ts";

export function okResponse(data: unknown, origin: string | null, status = 200): Response {
  return new Response(JSON.stringify({ data }), {
    status,
    headers: { ...getCorsHeaders(origin), "Content-Type": "application/json" },
  });
}

export function errResponse(
  message: string,
  origin: string | null,
  status = 400,
  code?: string,
): Response {
  return new Response(JSON.stringify({ error: message, ...(code ? { code } : {}) }), {
    status,
    headers: { ...getCorsHeaders(origin), "Content-Type": "application/json" },
  });
}
```

**Step 2:** Audit all Edge Functions — identify which use custom response shapes vs the shared `errorResponse`:
```bash
grep -r "new Response(JSON.stringify" supabase/functions/ --include="*.ts" -l
```

**Step 3:** Update each function to use `okResponse`/`errResponse` from `_shared/response.ts`. Prioritize user-facing functions first: `strategies`, `backtest-strategy`, `paper-trading-executor`, `quotes`, `chart`.

**Step 4:** Update macOS client and frontend to unwrap `{ data: ... }` envelope where needed (the chart response will need the `.data` unwrap added in ChartViewModel).

**Note:** The `chart` function from 028 should be built with the standard envelope from the start.

**Step 5:** Commit per function group:
```bash
git commit -m "feat(api): standardize response envelope across Edge Functions (037)"
```

---

## Summary Checklist

- [ ] Task 1: Read all 3 chart functions
- [ ] Task 2: Create `_shared/chart-types.ts`
- [ ] Task 3: Write unified chart skeleton
- [ ] Task 4: Implement futures resolution
- [ ] Task 5: Implement bars query + weekly aggregation
- [ ] Task 6: Implement freshness check + fire-and-forget refresh
- [ ] Task 7: Implement ML enrichment (mlSummary + indicators)
- [ ] Task 8: Manual endpoint testing
- [ ] Task 9: Update macOS ChartViewModel.swift
- [ ] Task 10: Delete chart-read and chart-data-v2
- [ ] Task 11: Mark 028 resolved + deploy
- [ ] Task 12: Standardize response envelopes (037)
