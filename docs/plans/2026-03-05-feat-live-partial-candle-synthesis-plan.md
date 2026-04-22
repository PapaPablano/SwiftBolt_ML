---
title: "feat: Live Partial Candle Synthesis for All Timeframes"
type: feat
status: completed
date: 2026-03-05
origin: docs/brainstorms/2026-03-05-live-partial-candle-synthesis-brainstorm.md
---

# feat: Live Partial Candle Synthesis for All Timeframes

## Overview

During market hours, the daily (d1), weekly (w1), hourly (h1), and 4-hour (h4) chart timeframes always show the **previous closed bar** as the most recent candle. This feature synthesizes an in-progress partial bar for the current period by aggregating 1-minute (m1) bars from Alpaca, injected at the end of each timeframe's bar series in the existing `/chart` Edge Function response. Price-derived indicators (RSI, MACD, EMA, Bollinger Bands, ATR) are recomputed server-side using the full bar series including the partial bar. Both the macOS SwiftUI client and the React frontend dashboard are updated to refresh at 60-second intervals during market hours.

**Approach chosen:** 1-minute ingest job + DB-side aggregation (see brainstorm: `docs/brainstorms/2026-03-05-live-partial-candle-synthesis-brainstorm.md`). A new `ingest-live` Edge Function runs every minute via pg_cron, writing `m1` bars to `ohlc_bars_v2`. The `/chart` function aggregates these into partial candles on demand.

---

## Problem Statement

The chart's right edge is always frozen at the close of the last completed bar. For a d1 chart, the current day is invisible until 4:00 PM ET when the session closes and the daily bar is committed. For h1/h4, the current period's candle is absent. This makes the platform feel stale for active monitoring and prevents users from seeing today's price action in the context of the full OHLC series.

---

## Technical Approach

### Architecture

```
NEW: ingest-live Edge Function
  └── pg_cron: */1 13-20 * * 1-5
  └── Internal gate: AlpacaClient.queryMarketClock() → skip if is_open=false
  └── watchlist_items → symbol list
  └── getMultiSymbolBars(symbols, timeframe='m1', start=today_market_open)
  └── PLUS: getQuote(symbols) → minuteBar (current in-progress minute)
  └── Upsert to ohlc_bars_v2 (timeframe='m1', is_intraday=true, data_status='live')

MODIFIED: /chart Edge Function
  └── Promise.all() gains a 6th parallel query: today's m1 bars for this symbol
  └── After Promise.all resolves, if isMarketOpen && timeframe != 'm15':
        └── Compute period boundaries for requested timeframe
        └── Aggregate m1 bars into partialBar { open, high, low, close, volume }
        └── Append partialBar with is_partial=true, data_status='live_partial'
        └── Recompute RSI(14), MACD(12,26,9), EMA(9,21), BB(20), ATR(14)
        └── Overlay computed values onto indicators response field

NEW: pg_cron cleanup job (midnight daily)
  └── DELETE FROM ohlc_bars_v2 WHERE timeframe='m1' AND ts < now() - interval '2 days'

MODIFIED: macOS ChartCache.swift
  └── saveBars(): filter out bars where is_partial=true before writing to disk
  └── ChartViewModel: during market hours, set 60s refresh for all timeframes

MODIFIED: React frontend
  └── useChartData hook: 60s polling interval during market hours
  └── visibilitychange listener: immediate refresh on tab focus
  └── Skip local state caching for bars with is_partial=true
```

### Key Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| m1 data source | `getMultiSymbolBars(m1)` + `getQuote → minuteBar` | Completed bars from DB path; current in-progress minute from snapshot |
| Market hours gate | `AlpacaClient.queryMarketClock()` inside `ingest-live` | Handles holidays, half-days, DST — not cron timing alone |
| Zero m1 bars fallback | Omit partial bar entirely | Safest for data integrity; chart ends at last closed bar |
| h4 block boundaries | 9:30–13:30 ET, 13:30–16:00 ET (market-open-relative) | Standard equities convention; second block is 2.5h |
| w1 synthesis order | d1 partial synthesized first, consumed by w1 synthesis | Avoids duplicate aggregation pass |
| Indicator recomputation input | Stored closed bars for that timeframe + partial bar appended | Gives meaningful RSI/MACD in the timeframe's context |
| `is_partial` surfacing | New `is_partial?: boolean` field on `OHLCBar` type | Typed — no position-in-array heuristics |

---

## Implementation Phases

### Phase 1: Type System & Schema Updates

**1.1 — Add `live_partial` to `data_status` enum (migration)**

File: `supabase/migrations/20260305000001_add_live_partial_data_status.sql`

```sql
BEGIN;

-- Audit existing check constraints on ohlc_bars_v2 before modifying
-- SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
--   WHERE conrelid = 'ohlc_bars_v2'::regclass AND contype = 'c';

-- Drop old data_status constraint, re-add with 'live_partial'
ALTER TABLE ohlc_bars_v2
  DROP CONSTRAINT IF EXISTS ohlc_bars_v2_data_status_check;

ALTER TABLE ohlc_bars_v2
  ADD CONSTRAINT ohlc_bars_v2_data_status_check
  CHECK (data_status IS NULL OR data_status IN (
    'verified', 'live', 'provisional', 'live_partial'
  ));

COMMIT;
```

> ⚠️ Per institutional learnings: audit existing constraints with `pg_constraint` query before adding. Wrap in `BEGIN`/`COMMIT`. Use `DROP CONSTRAINT IF EXISTS <old_name>` AND `DROP CONSTRAINT IF EXISTS <new_name>` before `ADD CONSTRAINT`.

> Note: `live_partial` bars are synthesized in the Edge Function and **not written to the DB** — this migration is a defensive schema extension for future-proofing. m1 bars written by `ingest-live` use `data_status='live'`.

**1.2 — Add m1 retention cleanup cron (migration)**

File: `supabase/migrations/20260305000002_m1_retention_cleanup_cron.sql`

```sql
BEGIN;

-- Requires pg_cron extension (already enabled)
SELECT cron.schedule(
  'm1-bar-retention-cleanup',
  '0 5 * * *',  -- 5:00 AM UTC daily (midnight ET)
  $$
    DELETE FROM ohlc_bars_v2
    WHERE timeframe = 'm1'
      AND ts < now() - interval '2 days';
  $$
);

COMMIT;
```

**1.3 — TypeScript type updates**

File: `supabase/functions/_shared/chart-types.ts`

- Add `is_partial?: boolean` field to `OHLCBar` interface
- Add `'live_partial'` to `OHLCBar.data_status` union (if typed)
- Add `isMarketOpen?: boolean` to `ChartMeta` interface (already present from `is_market_open` RPC, verify)

File: `supabase/functions/_shared/data-validation.ts`

- `AlpacaHistoricalRule.validate()`: The current check `bar.data_status !== "verified"` rejects any non-verified bar. Since `ingest-live` writes `data_status='live'` (not `'live_partial'`), this may already be OK. Verify that the existing validator doesn't reject `data_status='live'` for m1 bars with `is_intraday=true`.

**1.4 — Swift model update**

File: `client-macos/SwiftBoltML/Models/ChartResponse.swift`

- Add `isPartial: Bool?` field to `OHLCBar` Swift struct (maps from JSON `is_partial`)
- Ensure it has a default of `false` if field is absent (backward compat)

**1.5 — TypeScript indicator module (shared)**

File: `supabase/functions/_shared/indicators.ts` *(new)*

Extract the following from `supabase/functions/strategy-backtest-worker/indicators.ts`:
- `computeSMAArray(closes: number[], period: number): number[]`
- `computeEMAArray(closes: number[], period: number): number[]`
- `computeRSI(closes: number[], period: number): number`
- `computeMACD(closes: number[]): { macdLine: number, signalLine: number, histogram: number }`
- `computeBollingerBands(closes: number[], period: number): { upper: number, middle: number, lower: number }`
- `computeATR(bars: OHLCBar[], period: number): number`

Do not remove from the backtest worker — copy (or re-export from `_shared`).

---

### Phase 2: `ingest-live` Edge Function

File: `supabase/functions/ingest-live/index.ts` *(new)*

**Pattern:** Mirrors `supabase/functions/intraday-live-refresh/index.ts` exactly for auth, error handling, and upsert pattern.

**Key differences from `intraday-live-refresh`:**
- Timeframe: `'m1'` only (not `['m15', 'h1', 'h4']`)
- Uses `AlpacaClient.queryMarketClock()` as internal gate (not just `is_market_open` RPC) to handle holidays/half-days
- Additionally calls `getQuote(symbols)` to get `minuteBar` for the current in-progress minute
- Upserts completed m1 bars from `getMultiSymbolBars()` AND the current partial minute's `minuteBar` from snapshot
- DEADLINE_MS: 55 seconds (same as `intraday-live-refresh`)

**Pseudocode:**

```typescript
// supabase/functions/ingest-live/index.ts
const DEADLINE_MS = 55_000;
const MARKET_OPEN_UTC = 14; // 9:30 ET → ~14:30 UTC (use AlpacaClient.queryMarketClock() instead)

Deno.serve(async (req) => {
  // 1. Auth: X-SB-Gateway-Key + Authorization Bearer
  // 2. Internal market-clock gate:
  const clock = await alpaca.queryMarketClock();
  if (!clock.is_open) return new Response('market closed', { status: 200 });

  // 3. Symbol list from watchlist_items
  const symbols = await getWatchlistSymbols(supabase); // reuse intraday-live-refresh pattern

  // 4. Fetch completed m1 bars since market open today (bulk)
  const todayOpen = getTodayMarketOpenUTC(clock.next_open); // use clock data for DST-safe anchor
  const completedBars = await alpaca.getMultiSymbolBars({
    symbols,
    timeframe: 'm1',
    start: todayOpen,
    limit: 500, // max ~390 bars per trading day
  });

  // 5. Fetch current in-progress minute from snapshot
  const snapshots = await alpaca.getQuote(symbols); // returns AlpacaSnapshot[]
  // Extract minuteBar from each snapshot → treat as current partial m1 bar

  // 6. Merge: completed bars + current minuteBar (upsert overwrites with latest)
  const allBars = [...completedBars, ...snapshotMinuteBars];

  // 7. Upsert to ohlc_bars_v2
  // onConflict: 'symbol_id,timeframe,ts,provider,is_forecast'
  // data_status: 'live', is_intraday: true, provider: 'alpaca', is_forecast: false
  await batchUpsert(supabase, allBars, { deadline: start + DEADLINE_MS });

  return new Response(JSON.stringify({ ingested: allBars.length }), { status: 200 });
});
```

**DST-safe market open anchor:**
```typescript
// Use Alpaca clock's next_open to derive today's open time
// AlpacaClient.queryMarketClock() returns: { is_open, timestamp, next_open, next_close }
// When market is open: next_open is next day's open. Subtract 1 day to get today's open.
// This is DST-correct because Alpaca handles the calendar.
```

**Migration for pg_cron registration:**

File: `supabase/migrations/20260305000003_ingest_live_cron.sql`

```sql
BEGIN;

-- Reference: supabase/migrations/20260301110000_intraday_live_refresh_cron.sql
-- Fires every 1 minute during market hours (UTC 13-20, weekdays)
-- Internal market-clock check inside function handles holidays/half-days/DST edges

SELECT cron.schedule(
  'ingest-live-m1-bars',
  '*/1 13-20 * * 1-5',
  $$
    SELECT net.http_post(
      url := (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'supabase_url') || '/functions/v1/ingest-live',
      headers := jsonb_build_object(
        'Content-Type', 'application/json',
        'Authorization', 'Bearer ' || (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'service_role_key'),
        'x-sb-gateway-key', (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'sb_gateway_key')
      ),
      body := '{}'::jsonb
    );
  $$
);

COMMIT;
```

> ⚠️ Per institutional learnings: secret name must be `service_role_key` (not `sb_gateway_key`) for the Bearer token. `x-sb-gateway-key` header uses `sb_gateway_key`. Verify both exist in Vault before deploying.

---

### Phase 3: `/chart` Partial Candle Synthesis

File: `supabase/functions/chart/index.ts`

**3.1 — Add m1 bar query to `Promise.all`**

In the existing `Promise.all([...])` at line ~559, add a 7th entry:

```typescript
// New entry in Promise.all:
supabase
  .from('ohlc_bars_v2')
  .select('ts, open, high, low, close, volume, data_status')
  .eq('symbol_id', symbolId)
  .eq('timeframe', 'm1')
  .eq('is_intraday', true)
  .gte('ts', todayMarketOpenISO)  // pre-compute market open UTC for today
  .order('ts', { ascending: true })
  .limit(500)
```

Destructure result: `m1BarsResult` alongside existing results.

**3.2 — Synthesis block (insert after `Promise.all` resolves, before bar map)**

After existing line ~636 (end of `Promise.all`), before bar array mapping:

```typescript
// === PARTIAL CANDLE SYNTHESIS ===
const VALID_SYNTHESIS_TIMEFRAMES = ['h1', 'h4', 'd1', 'w1'];
const m1Bars = m1BarsResult.data ?? [];

let partialBar: OHLCBar | null = null;

if (isMarketOpen && VALID_SYNTHESIS_TIMEFRAMES.includes(timeframe) && m1Bars.length > 0) {
  const periodStart = getPeriodStart(timeframe, m1Bars[0].ts); // see helper below
  const periodBars = m1Bars.filter(b => new Date(b.ts) >= periodStart);

  if (periodBars.length > 0) {
    partialBar = {
      ts: periodStart.toISOString(),
      open: periodBars[0].open,
      high: Math.max(...periodBars.map(b => b.high)),
      low: Math.min(...periodBars.map(b => b.low)),
      close: periodBars[periodBars.length - 1].close,
      volume: periodBars.reduce((sum, b) => sum + b.volume, 0),
      data_status: 'live_partial',
      is_partial: true,
    };
  }
}
```

**3.3 — Period boundary helper**

```typescript
// supabase/functions/chart/index.ts (local helper or in _shared/trading-time.ts)

function getPeriodStart(timeframe: string, firstBarTs: string): Date {
  const now = new Date();
  // Market opens at 9:30 ET. Use Alpaca clock or compute from today.
  const marketOpenET = getMarketOpenUTCToday(); // already exists in trading-time.ts

  switch (timeframe) {
    case 'd1':
      return marketOpenET;

    case 'h1': {
      // Floor to current clock hour in UTC
      const h = new Date(now);
      h.setUTCMinutes(0, 0, 0);
      return h;
    }

    case 'h4': {
      // Two blocks: 9:30–13:30 ET, 13:30–16:00 ET (market-open-relative)
      // H4_BLOCKS defined as offsets in minutes from market open
      const H4_BLOCK_MINUTES = [0, 240]; // 9:30 and 13:30 ET
      const elapsedMin = (now.getTime() - marketOpenET.getTime()) / 60_000;
      const blockIdx = H4_BLOCK_MINUTES.filter(b => b <= elapsedMin).length - 1;
      const blockStart = new Date(marketOpenET.getTime() + H4_BLOCK_MINUTES[Math.max(0, blockIdx)] * 60_000);
      return blockStart;
    }

    case 'w1': {
      // Monday of current week at market open ET
      const monday = new Date(marketOpenET);
      const dayOfWeek = monday.getDay(); // 0=Sun, 1=Mon...
      monday.setDate(monday.getDate() - (dayOfWeek === 0 ? 6 : dayOfWeek - 1));
      return monday;
    }

    default:
      return marketOpenET;
  }
}
```

**3.4 — Append partial bar to response**

After the existing `allBars` array is built (post-`get_chart_data_v2` RPC, post-weekly aggregation):

```typescript
if (partialBar !== null) {
  // Remove any existing bar at the partial period's timestamp (shouldn't exist, but defensive)
  const filtered = allBars.filter(b => b.ts !== partialBar!.ts);
  allBars = [...filtered, partialBar];
}
```

**3.5 — w1 synthesis uses d1 partial bar**

For `timeframe === 'w1'`:
1. `get_chart_data_v2` already returns `d1` bars (chart function already fetches d1 for w1)
2. The partial d1 bar (`partialBar`) is computed first via the m1 synthesis block
3. For w1 aggregation (existing code at line ~673), inject the `partialBar` into the d1 series before weekly aggregation:

```typescript
// Existing: d1 bars fetched; week aggregation groups by week
// Modification: before weekly aggregation, append partialBar (if timeframe='w1' and partialBar exists)
if (timeframe === 'w1' && partialBar !== null) {
  allBarsBeforeAggregation = [...allBarsBeforeAggregation, partialBar];
}
// Then existing weekly aggregation runs normally, grouping by week
// The partial d1 bar's ts falls in the current week → produces a live_partial w1 bar
```

The resulting w1 bar (from aggregating closed d1 bars + partial d1) should inherit `is_partial: true`.

---

### Phase 4: Price-Derived Indicator Recomputation

File: `supabase/functions/chart/index.ts`

After synthesis (Phase 3), if `partialBar !== null`, recompute price-derived indicators:

```typescript
if (partialBar !== null && indicators !== null) {
  // Build close price series: all closed bars + partial bar close
  const closes = allBars.map(b => b.close); // includes partial bar as last element
  const ohlcBars = allBars; // for ATR (needs high/low/close)

  // Import from _shared/indicators.ts
  const rsi = computeRSI(closes, 14);
  const macd = computeMACD(closes); // {macdLine, signalLine, histogram}
  const bb = computeBollingerBands(closes, 20);
  const atr = computeATR(ohlcBars, 14);

  // Overlay onto existing indicators (preserve ML-computed fields)
  indicators = {
    ...indicators,
    rsi: rsi ?? indicators.rsi,
    macd_histogram: macd.histogram ?? indicators.macd_histogram,
    bollinger_upper: bb.upper,
    bollinger_lower: bb.lower,
    atr: atr ?? indicators.atr,
    // supertrend_factor, trend_label, kdj_j, sr_levels: UNCHANGED (ML pipeline cadence)
  };
}
```

> The partial bar's close is included as the series' last data point, giving a meaningful indicator value in the context of the timeframe (e.g., h1 RSI uses the last 14 hourly bars + the in-progress hour's current close).

---

### Phase 5: macOS Client Updates

**5.1 — `ChartCache.swift` — Skip caching partial bars**

File: `client-macos/SwiftBoltML/Services/ChartCache.swift`

In `saveBars(symbol:timeframe:bars:)`:

```swift
// Before: saveBars writes all bars
// After: filter out partial bars before disk write

func saveBars(symbol: String, timeframe: Timeframe, bars: [OHLCBar]) {
    let cacheable = bars.filter { !($0.isPartial ?? false) }
    guard !cacheable.isEmpty else { return }
    // ... existing JSON encoding and file write using `cacheable`
}
```

**5.2 — `ChartResponse.swift` — Swift model update**

File: `client-macos/SwiftBoltML/Models/ChartResponse.swift`

```swift
struct OHLCBar: Codable {
    // ... existing fields ...
    let isPartial: Bool?

    enum CodingKeys: String, CodingKey {
        // ... existing ...
        case isPartial = "is_partial"
    }
}
```

**5.3 — `ChartViewModel.swift` — Market hours 60s refresh**

File: `client-macos/SwiftBoltML/ViewModels/ChartViewModel.swift`

Current auto-refresh interval is timeframe-dependent (long for d1, short for m15). Add market hours awareness:

```swift
private func refreshInterval(for timeframe: Timeframe, isMarketOpen: Bool) -> TimeInterval {
    if isMarketOpen {
        return 60  // 1 minute for all timeframes during market hours
    }
    // Existing logic: 2h for intraday, 14h for daily
    switch timeframe {
    case .m15, .h1, .h4: return 2 * 3600
    case .d1: return 14 * 3600
    case .w1: return 24 * 3600
    }
}
```

After each chart load, extract `meta.isMarketOpen` from the response and restart the auto-refresh timer with the new interval.

> Per institutional learnings: store the timer `Task` as a property and cancel before creating a new one. Do not accumulate Task closures.

---

### Phase 6: React Frontend Updates

File: `frontend/src/hooks/useChartData.ts` *(new or extend existing)*

The React frontend currently does not poll the Supabase `/chart` Edge Function. Add a hook that:
1. Loads chart bars on mount
2. Checks `meta.isMarketOpen` from the response
3. During market hours: sets a 60-second polling interval
4. On `visibilitychange` (tab focus restored): fires an immediate refresh
5. On unmount: clears interval and removes event listener

```typescript
// frontend/src/hooks/useChartData.ts
import { useEffect, useRef, useState } from 'react';

export function useChartData(symbol: string, timeframe: string) {
  const [bars, setBars] = useState<OHLCBar[]>([]);
  const [isMarketOpen, setIsMarketOpen] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval>>();

  const fetchBars = async () => {
    const res = await fetchChartEndpoint(symbol, timeframe);
    if (!res) return;

    // Strip partial bars from any local state (they should not be memo-ized)
    const closedBars = res.bars.filter(b => !b.is_partial);
    const partialBar = res.bars.find(b => b.is_partial);

    setBars([...closedBars, ...(partialBar ? [partialBar] : [])]);
    setIsMarketOpen(res.meta.isMarketOpen ?? false);
  };

  useEffect(() => {
    fetchBars();

    // visibilitychange: immediate refresh on tab restore
    const onVisible = () => { if (document.visibilityState === 'visible') fetchBars(); };
    document.addEventListener('visibilitychange', onVisible);

    return () => {
      clearInterval(intervalRef.current);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [symbol, timeframe]);

  // Dynamic polling: 60s during market hours, none otherwise
  useEffect(() => {
    clearInterval(intervalRef.current);
    if (isMarketOpen) {
      intervalRef.current = setInterval(fetchBars, 60_000);
    }
  }, [isMarketOpen, symbol, timeframe]);

  return { bars, isMarketOpen };
}
```

---

## System-Wide Impact

### Interaction Graph

```
pg_cron (*/1 13-20 * * 1-5)
  → ingest-live Edge Function
    → AlpacaClient.queryMarketClock() [gate]
    → AlpacaClient.getMultiSymbolBars(m1) [bulk]
    → AlpacaClient.getQuote(symbols) [snapshot, minuteBar]
    → ohlc_bars_v2 UPSERT (timeframe='m1', data_status='live')

Client 60s timer
  → GET /chart?symbol=X&timeframe=d1
    → get_chart_data_v2 RPC [existing d1 bars]
    → ohlc_bars_v2 SELECT (timeframe='m1', today) [NEW]
    → is_market_open RPC [existing]
    → Synthesis: m1 bars → partialBar
    → Indicators: computeRSI, computeMACD, etc. from _shared/indicators.ts
    → Response with is_partial=true bar appended

pg_cron (0 5 * * *)
  → DELETE FROM ohlc_bars_v2 WHERE timeframe='m1' AND ts < now() - 2 days
```

### Error Propagation

| Error | Layer | Behavior |
|---|---|---|
| Alpaca API 429 in `ingest-live` | `ingest-live` | Existing `fetchWithRetry` retries 3x; if all fail, no m1 bar for that minute. Next cron run fills gap. |
| Alpaca API down entirely | `ingest-live` | Zero m1 bars written. `/chart` queries m1 → empty result → `partialBar = null` → synthesis skipped → chart ends at last closed bar (safe fallback) |
| `is_market_open` RPC fails in `/chart` | `/chart` | Existing UTC fallback heuristic (weekday + 13:30–21:00 UTC). On holidays, heuristic may return true → synthesis runs → zero m1 bars → partial bar omitted → safe |
| `queryMarketClock()` fails in `ingest-live` | `ingest-live` | Return early, skip ingest. No m1 bars written. |
| m1 query in `/chart` fails | `/chart` | `m1Bars = []` → synthesis skipped → no partial bar. Non-fatal. |
| macOS network error on 60s refresh | `ChartViewModel` | Existing retry/error handling. Cache still serves closed bars. |

### State Lifecycle Risks

- **Partial bar in macOS cache:** Mitigated by filtering `is_partial=true` bars in `saveBars()`. If this filter is missing, a stale partial bar could be served from disk on next app launch.
- **w1 partial bar composition:** The partial d1 bar is synthesized before w1 aggregation. If d1 synthesis produces `null` (zero m1 bars), the w1 chart ends at last week's closed bar — acceptable fallback.
- **Two concurrent `ingest-live` runs:** If a cron invocation takes >60s, the next fires before the first completes. Both write to `ohlc_bars_v2` via upsert — idempotent by `(symbol_id, timeframe, ts, provider, is_forecast)`. No orphaned rows; last write wins on each row.
- **Official d1 close vs. m1-aggregate discrepancy:** When 4:00 PM ET arrives and the official d1 bar is committed by the ingest pipeline, the next chart request will return the official bar (no partial). The close price may differ slightly from the final m1 aggregation due to trade corrections. This produces a 1-request "jump" which is acceptable.

### API Surface Parity

- `/chart` response: `OHLCBar` gains `is_partial?: boolean` — **additive, non-breaking** (existing clients receive `undefined` for the field). No caller update required per CLAUDE.md versioning protocol.
- `data_status` values extended with `'live_partial'` — additive, non-breaking.
- No new endpoints. Single GET `/chart` contract preserved (see brainstorm).

### Integration Test Scenarios

1. **Happy path:** Market is open, symbol is in watchlist. `ingest-live` ran at minute N. Chart request at minute N+5. m1 bars for today exist. Partial d1 bar synthesized. `is_partial=true` bar is last in `bars[]`. RSI computed from 14 closed d1 bars + partial.

2. **Zero m1 bars (Alpaca down):** `ingest-live` failed for 10 minutes. Chart request arrives. m1 query returns empty. `partialBar = null`. `bars[]` ends at yesterday's closed d1. `meta.isMarketOpen=true`. No crash, no degenerate bar.

3. **Market closed (holiday):** `ingest-live` internal gate: `queryMarketClock().is_open = false`. No m1 bars written. Client still refreshes at 60s (because previous response had `isMarketOpen=true`). Next response has `isMarketOpen=false` → client reverts to long interval.

4. **DST transition day:** `queryMarketClock()` returns correct UTC time. `getTodayMarketOpenUTC()` derived from Alpaca clock data (not hardcoded offset). d1 synthesis anchor is correct. h4 blocks re-derived from `marketOpenET` → also correct.

5. **Symbol not in watchlist:** User opens a chart for a symbol not in `watchlist_items`. `ingest-live` never wrote m1 bars for it. Chart `/chart` query for m1 returns empty. No partial bar synthesized. Chart ends at last closed bar. No error shown to user.

---

## Acceptance Criteria

### Functional

- [x] `ingest-live` Edge Function fetches m1 bars from Alpaca and upserts to `ohlc_bars_v2`
- [x] `ingest-live` internal gate: function no-ops when `AlpacaClient.queryMarketClock()` returns `is_open=false`
- [x] `/chart` response includes a partial bar (with `is_partial: true`) as the last element in `bars[]` during market hours, for all four timeframes: h1, h4, d1, w1
- [x] Partial bar OHLC correct: `open=first_m1_open`, `high=max(highs)`, `low=min(lows)`, `close=last_m1_close`, `volume=sum(volumes)`
- [x] h4 period boundaries: Block 1 = 9:30–13:30 ET, Block 2 = 13:30–16:00 ET
- [x] w1 partial bar incorporates this week's closed d1 bars + today's partial d1
- [x] RSI, MACD histogram, EMA overlays in `/chart` response reflect the partial bar when `is_partial=true` bar is present
- [x] ML-computed indicators (SuperTrend, trend label, KDJ-J, S/R levels) are unchanged by partial synthesis
- [x] When market is closed or no m1 bars exist, `/chart` returns the normal closed bar series with no partial bar appended
- [x] macOS `ChartCache.saveBars()` never writes bars with `is_partial=true` to disk
- [x] macOS client refreshes every 60 seconds while `meta.isMarketOpen=true`
- [x] macOS client reverts to timeframe-appropriate long intervals when `isMarketOpen=false`
- [x] React chart refreshes every 60 seconds during market hours
- [x] React chart fires an immediate refresh on `visibilitychange` (tab focused)
- [x] pg_cron cleanup job deletes m1 bars older than 2 days at midnight UTC
- [x] `data_status='live_partial'` value is accepted by the `ohlc_bars_v2` CHECK constraint

### Non-Functional

- [x] `ingest-live` completes within 55 seconds (DEADLINE_MS guard)
- [x] No additional latency added to `/chart` for timeframes without partial synthesis (m15 during market hours)
- [x] `ohlc_bars_v2` table size remains bounded (m1 retention cleanup verified)
- [x] Two concurrent `ingest-live` runs are safe (upsert idempotency)

### Quality Gates

- [x] TypeScript: `deno check supabase/functions/ingest-live/index.ts`
- [x] Lint: `deno lint supabase/functions/ingest-live/` (no warnings)
- [x] Lint: `deno lint supabase/functions/chart/` (no warnings)
- [x] Lint: `deno lint supabase/functions/_shared/indicators.ts`
- [x] macOS build: no Swift compiler errors for new `isPartial` field
- [x] React: `npm run build` in `frontend/` — no TypeScript errors

---

## Dependencies & Prerequisites

### Must be deployed before this plan

1. **`intraday-live-refresh` function is live** — confirms pg_cron auth pattern (Vault `service_role_key`) works
2. **Vault secrets exist:** `supabase_url`, `service_role_key`, `sb_gateway_key` — verify against migration `20260205100100_backfill_cron_x_sb_gateway_key.sql`
3. **`market_calendar` table populated** — `is_market_open()` RPC depends on it

### Internal dependencies (within this plan)

- Phase 1 (types + schema) → must complete before Phase 2, 3, 4
- Phase 2 (`ingest-live`) → must be deployed before Phase 3 is testable end-to-end
- Phase 3 (synthesis) → must complete before Phase 4 (indicators use synthesized bar)
- Phase 3 → must complete before Phase 5 + 6 (clients depend on `is_partial` field)

---

## Deployment Order

```
1. Apply migration 20260305000001_add_live_partial_data_status.sql
2. Apply migration 20260305000002_m1_retention_cleanup_cron.sql
3. Deploy _shared/indicators.ts (new shared module)
4. Deploy supabase/functions/ingest-live/index.ts
5. Apply migration 20260305000003_ingest_live_cron.sql (registers pg_cron job)
6. Verify ingest-live fires and writes m1 bars (check ohlc_bars_v2 WHERE timeframe='m1')
7. Deploy supabase/functions/chart/index.ts (modified)
8. Verify /chart returns is_partial bar for open timeframe
9. Deploy macOS client (ChartCache + ChartViewModel + ChartResponse changes)
10. Deploy React frontend (useChartData hook + chart component refresh)
```

---

## Risk Analysis & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Vault secret name mismatch | Medium | High — cron auth fails silently | Test `ingest-live` manually with correct headers before cron deploy |
| Alpaca rate limits on 20+ symbols/min | Low | Medium — m1 gap for one minute | Multi-symbol batch reduces calls; Alpaca free tier = 200 req/min |
| pg_cron fires before `ingest-live` cold start completes | Low | Low — next run recovers | 55s DEADLINE_MS guard prevents overlap issues |
| Half-day market: synthesis continues past early close | Low | Medium — stale partial bar shows | Internal `queryMarketClock()` gate handles actual close time |
| DST transition: wrong 9:30 ET anchor | 2 days/year | Medium | Derive anchor from `queryMarketClock().next_open` (DST-aware) |
| macOS cache serves stale partial bar on relaunch | Low | Low — users just see stale data briefly | `saveBars()` filter for `is_partial` prevents writing to disk |
| Official d1 close differs from m1 aggregate | Low | Low — 1-request visible jump | Acceptable; official bar replaces partial on next refresh after 4 PM |
| ohlc_bars_v2 bloat | Low | Medium | pg_cron cleanup at midnight; 2-day retention |

---

## Future Considerations

- **Sub-minute (tick) updates:** If 1-minute resolution feels too coarse, the next evolution is Supabase Realtime subscriptions on `ohlc_bars_v2` where `timeframe='m1'`, pushing row inserts to clients. This avoids polling but requires significant WebSocket infrastructure changes.
- **Extended hours trading (pre-market/after-hours):** Currently out of scope. If added: `is_market_open` would need an "extended hours" mode, and the period boundary logic would need to define pre-market d1 open as the Alpaca session open (4:00 AM ET).
- **Non-watchlist symbol synthesis:** If a user opens a chart for a symbol not in `watchlist_items`, the on-demand Alpaca fetch approach (Approach A from brainstorm) could be used as a fallback: if no m1 bars exist in DB, fetch a single snapshot directly during the `/chart` request.

---

## Documentation Plan

- Update `CLAUDE.md` with the `ingest-live` function description and the `m1` timeframe in the supported timeframes list
- Add a comment block in `chart/index.ts` above the synthesis block explaining the h4 block boundary constants

---

## Sources & References

### Origin

- **Brainstorm document:** [docs/brainstorms/2026-03-05-live-partial-candle-synthesis-brainstorm.md](docs/brainstorms/2026-03-05-live-partial-candle-synthesis-brainstorm.md)
  - Key decisions carried forward: (1) 1-minute ingest + DB aggregation approach, (2) all four timeframes in scope, (3) server-side indicator recomputation, (4) ML indicators unchanged

### Internal References

- `supabase/functions/intraday-live-refresh/index.ts` — auth pattern, pg_cron integration, watchlist query, upsert conflict key
- `supabase/functions/strategy-backtest-worker/indicators.ts` — RSI, MACD, EMA, Bollinger Bands, ATR implementations
- `supabase/functions/_shared/providers/alpaca-client.ts` — `getMultiSymbolBars()`, `getQuote()`, `queryMarketClock()`, `convertTimeframe('m1')`
- `supabase/functions/chart/index.ts` — `Promise.all` at line ~559, insertion point at line ~636
- `client-macos/SwiftBoltML/Services/ChartCache.swift` — `saveBars()` at line ~30
- `client-macos/SwiftBoltML/ViewModels/ChartViewModel.swift` — auto-refresh timer
- `supabase/migrations/20260205100100_backfill_cron_x_sb_gateway_key.sql` — Vault auth pattern for pg_cron
- `supabase/migrations/20260301110000_intraday_live_refresh_cron.sql` — cron schedule reference

### Institutional Learnings

- `docs/solutions/database-issues/live-trading-migration-constraint-sequencing.md` — CHECK constraint migration safety (dual constraint bug, IS NULL OR guard, transaction wrapper)
- `docs/plans/2026-03-01-feat-alpaca-data-pipeline-refresh-plan.md` — Alpaca multi-symbol batching, Vault secret names, pg_cron schedule bounds
- `docs/solutions/security-issues/swiftui-credential-and-injection-hardening.md` — macOS Task lifecycle (cancel before re-create, stored Task property)

### SpecFlow Findings Incorporated

- Gap 1 (half-days): Addressed by `queryMarketClock()` internal gate in `ingest-live`
- Gap 2 (DST): Addressed by deriving market open from `clock.next_open` instead of hardcoded UTC offset
- Gap 5 (bar-just-closed race): Accepted; m1 close price lags by ≤1 cron interval — partial bar's close reflects last completed m1 bar
- Gap 6 (zero m1 fallback): Omit partial bar entirely (no degenerate candle)
- Gap 7 (upsert key): Reuse existing `(symbol_id, timeframe, ts, provider, is_forecast)` unique constraint
- Gap 8 (`live_partial` type): Phase 1.3 adds `is_partial` to `OHLCBar`; `live_partial` allowed in CHECK constraint
- Gap 9 (`AlpacaHistoricalRule`): `ingest-live` writes `data_status='live'` (not `'live_partial'`) — verify validator allows this for m1 bars
- Gap 10 (h4 boundaries): Phase 3.3 defines constants: Block 1 = 9:30 ET + 0min, Block 2 = 9:30 ET + 240min
- Gap 11 (w1 depends on d1 partial): Phase 3.5 specifies d1 synthesis first, w1 consumes the result
- Gap 14 (client–cron synchronization): Accepted; minor lag (≤60s) is acceptable UX trade-off
- Gap 15 (Swift cache): Phase 5.1 filters `is_partial` bars in `saveBars()`
- Gap 16 (browser tab background): Phase 6 adds `visibilitychange` listener for immediate refresh
- Gap 18 (non-watchlist symbols): Out of scope; silently produces no partial bar (chart ends at last closed bar)
- Gap 20 (concurrent cron runs): Upsert idempotency handles overlapping runs safely
