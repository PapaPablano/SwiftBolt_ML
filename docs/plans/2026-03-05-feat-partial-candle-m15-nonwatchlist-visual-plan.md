---
title: "feat: Partial Candle Additions — m15 synthesis, non-watchlist on-demand, visual indicator"
type: feat
status: completed
date: 2026-03-05
origin: docs/solutions/integration-issues/live-partial-candle-synthesis-timeframe-coordination.md
---

# feat: Partial Candle Additions — m15 synthesis, non-watchlist on-demand, visual indicator

## Overview

Three targeted additions to PR #30 (live partial candle synthesis):

1. **m15 partial candle** — extend synthesis to the 15-minute timeframe (4 surgical changes to `chart/index.ts`, plus client-side polling update)
2. **Non-watchlist on-demand fetch** — when a symbol has no m1 bars in DB (not in `watchlist_items`), fetch a single Alpaca snapshot during the `/chart` request to synthesize a partial bar
3. **Visual partial candle indicator** — subtle per-bar color treatment and a pulsing dot marker in TradingView Lightweight Charts (React) and macOS ChartBridge to distinguish in-progress partial bars from closed bars

All three are additive to the existing PR #30 implementation and non-breaking.

---

## Problem Statement / Motivation

**m15 synthesis:** After PR #30, the 15-minute chart remains frozen at the last closed m15 bar even though m1 data is now being ingested every minute. The `intraday-live-refresh` function refreshes m15/h1/h4 bars every 15 minutes — meaning the m15 chart can lag up to 15 minutes. Synthesizing from m1 reduces this to ≤1 minute.

**Non-watchlist symbols:** Users can open chart views for any symbol (e.g., by searching), but only watchlist symbols get m1 ingest. These charts end at the previous closed bar for the entire trading day with no partial candle, creating an inconsistent experience. A single Alpaca snapshot during the chart request provides `minuteBar` (current partial m1) at negligible latency (~50–150ms).

**Visual indicator:** Currently there is no visual distinction between the partial in-progress candle and closed candles. Users cannot tell at a glance whether the rightmost candle is live or historical. The project precedent (StrategyBuilderWebStyle.swift line 1859) is `.opacity(0.55)` for partial data. TradingView Lightweight Charts supports per-bar color overrides.

---

## Proposed Solution

### Addition 1: m15 Partial Candle

Four changes to `supabase/functions/chart/index.ts`:

1. Extend `getPartialPeriodStart` type union to include `"m15"` and add floor-to-15-minute logic
2. Extend `synthesizePartialBar` type union to include `"m15"`
3. Add `"m15"` to the m1 bars fetch gate (Promise.all slot 8 condition)
4. Add `"m15"` to `PARTIAL_CANDLE_TFS` dispatch array

Two client-side changes:
- macOS `ChartViewModel.swift`: add `.m15` to `partialCandleTimeframes` set → 60s refresh
- React `TradingViewChart.tsx`: add `'15m'` to `PARTIAL_CANDLE_HORIZONS` (already present per research — verify)

No new migrations needed. m1 bars are already written to DB. No changes to `ingest-live`.

### Addition 2: Non-Watchlist On-Demand Snapshot

One change to `supabase/functions/_shared/providers/alpaca-client.ts`:
- Add `getSnapshot(symbol: string): Promise<AlpacaBar | null>` that fetches `/v2/stocks/snapshots?symbols=X` and returns `snapshot.minuteBar`. Use `maxRetries=0` to avoid latency impact.

One change to `supabase/functions/chart/index.ts`:
- After synthesis runs and `partialBar === null` (zero m1 rows) AND `isMarketOpen`, trigger `getSnapshot(symbol)` for timeframes in `PARTIAL_CANDLE_TFS`. Synthesize a single-point partial bar from the returned `minuteBar`.

No DB writes. No new migrations. This is a read-only on-demand path.

### Addition 3: Visual Partial Candle Indicator

**React (TradingView Lightweight Charts):**
- In `formattedBars` assembly, detect `bar.is_partial` and inject per-bar `color`, `borderColor`, `wickColor` (dimmed orange/amber) on the last bar
- Add a `setMarkers` call with a circle marker (`.` position `aboveBar`) on the partial bar's timestamp
- Use `series.update(lastBar)` instead of full `setData` on poll ticks (avoids chart flash)

**macOS (ChartBridge):**
- Add `color: String?` to `LightweightCandle` struct in `ChartBridge.swift`
- In `setCandles()`, detect `bar.isPartial ?? false` and pass a hex color string for partial bars
- The WebView JS bridge already accepts Lightweight Charts bar data — no JS-side changes needed if color field passes through

---

## Technical Considerations

### m15 Period Boundary

```typescript
// getPartialPeriodStart addition
if (tf === "m15") {
  const m = now.getUTCMinutes();
  return new Date(Date.UTC(y, mo, d, h, Math.floor(m / 15) * 15));
}
```

The m1 fetch window uses `now - 8h` currently (generous for d1). For m15, only 15 minutes of m1 data are needed — tighten the window conditionally or rely on client-side filtering in `synthesizePartialBar` (it already filters to `>= periodStart`).

### On-Demand Snapshot Latency Budget

The on-demand path adds one Alpaca API call only when:
- `isMarketOpen === true` AND
- `partialBar === null` (no m1 rows in DB) AND
- `timeframe` ∈ `PARTIAL_CANDLE_TFS`

This is expected to be rare in steady state (watchlist symbols always have m1 data during market hours). For non-watchlist symbols, the 50–150ms Alpaca IEX latency is acceptable within the chart endpoint's total response budget. Use `maxRetries=0` — failure produces `null` → silent fallback to no partial bar.

### TradingView Per-Bar Color API

```typescript
// formattedBars assembly in TradingViewChart.tsx
const formattedBars = bars.map((bar, idx) => {
  const base = { time: ..., open: bar.open, high: bar.high, low: bar.low, close: bar.close };
  if (bar.is_partial) {
    return {
      ...base,
      color: 'rgba(255, 165, 0, 0.5)',       // amber, 50% opacity
      borderColor: 'rgba(255, 165, 0, 0.8)',
      wickColor: 'rgba(255, 165, 0, 0.6)',
    };
  }
  return base;
});

// Marker for live pulse dot
series.setMarkers([
  ...(existingStrategyMarkers),
  ...(partialBar ? [{
    time: partialBar.ts,
    position: 'aboveBar',
    color: '#FFA500',
    shape: 'circle',
    text: 'LIVE',
    size: 0.8,
  }] : []),
]);
```

### System-Wide Impact

- **Interaction graph**: m15 synthesis → no new data sources; uses existing m1 rows and `getPartialPeriodStart` dispatch. On-demand snapshot → new Alpaca call inside `/chart` request (only on cache-miss path). Visual indicator → purely client-side rendering, no server changes.
- **Error propagation**: Snapshot fetch failure → `null` → synthesis skipped → silent fallback (last closed bar). Does not affect other bars in the series.
- **State lifecycle risks**: On-demand snapshot result is never cached or written to DB. No orphaned state risk.
- **API surface parity**: `is_partial` flag already in `OHLCBar` TypeScript and Swift types. No new fields needed for additions 1 or 2. Addition 3 adds `color?: String` to `LightweightCandle` (Swift) — additive, non-breaking.

---

## Implementation Phases

### Phase 1: m15 Partial Candle — Edge Function + Clients

**Files to change:**

1. `supabase/functions/chart/index.ts`
   - `getPartialPeriodStart`: extend type to `"d1" | "h1" | "h4" | "m15"`, add m15 floor logic
   - `synthesizePartialBar`: extend type union
   - Promise.all slot 8 gate: `["d1", "w1", "h1", "h4", "m15"].includes(timeframe)`
   - `PARTIAL_CANDLE_TFS`: add `"m15"`
   - `synthTf` cast: update to `as "d1" | "h1" | "h4" | "m15"` (m15 maps to itself, not d1)

2. `client-macos/SwiftBoltML/ViewModels/ChartViewModel.swift`
   - Add `.m15` to `partialCandleTimeframes: Set<Timeframe>`

3. `frontend/src/components/TradingViewChart.tsx`
   - Verify `'15m'` is in `PARTIAL_CANDLE_HORIZONS` (research suggests it already is — confirm)

**Quality gates:**
- [ ] `deno lint supabase/functions/chart/` — 0 warnings
- [ ] `deno fmt supabase/functions/chart/` — no changes
- [ ] `deno check supabase/functions/chart/index.ts`

---

### Phase 2: Non-Watchlist On-Demand Snapshot

**Files to change:**

1. `supabase/functions/_shared/providers/alpaca-client.ts`
   - Add `getSnapshot(symbol: string): Promise<AlpacaBar | null>` — hits `/v2/stocks/snapshots?symbols=X`, returns `response.data[symbol]?.minuteBar ?? null`, `maxRetries=0`

2. `supabase/functions/chart/index.ts`
   - After synthesis block: `if (isMarketOpen && partialBar === null && PARTIAL_CANDLE_TFS.includes(timeframe) && m1Rows.length === 0)`
   - Call `await alpaca.getSnapshot(symbol)` → build `partialBar` from `minuteBar` fields
   - Wrap in try/catch: failure → `partialBar` stays `null`

**Quality gates:**
- [ ] `deno lint supabase/functions/_shared/providers/alpaca-client.ts`
- [ ] `deno lint supabase/functions/chart/`
- [ ] `deno check supabase/functions/chart/index.ts`

---

### Phase 3: Visual Partial Candle Indicator

**Files to change:**

1. `frontend/src/components/TradingViewChart.tsx`
   - In `formattedBars` map: pass `color/borderColor/wickColor` for bars where `bar.is_partial === true`
   - Extend `setMarkers` call to include a `'circle'` marker at the partial bar's timestamp (`text: 'LIVE'`, `color: '#FFA500'`, `size: 0.8`)
   - On poll ticks: use `series.update(lastBar)` for the partial bar instead of full `setData` (avoids chart flash on 60s refresh)

2. `client-macos/SwiftBoltML/Services/ChartBridge.swift`
   - Add `color: String?` to `LightweightCandle` struct
   - In `setCandles()` conversion: `color: bar.isPartial == true ? "#FFA50080" : nil`

**Quality gates:**
- [ ] `npm run build` in `frontend/` — no TypeScript errors
- [ ] macOS: no Swift compiler errors

---

## Acceptance Criteria

### Functional
- [ ] m15 chart shows a partial candle during market hours (synthesized from m1 bars for the current 15-minute period)
- [ ] m15 refresh interval is 60 seconds during market hours (matching h1/h4/d1 behavior)
- [ ] Symbol not in `watchlist_items`: `/chart?timeframe=d1` response includes `is_partial: true` bar during market hours (sourced from Alpaca snapshot)
- [ ] Symbol not in watchlist: if Alpaca snapshot fails, no partial bar appended, no error returned — silent fallback
- [ ] React chart: partial bar renders with amber/orange color treatment (distinct from normal green/red candles)
- [ ] React chart: a `LIVE` circle marker appears above the partial bar timestamp during market hours
- [ ] macOS chart: partial bar renders with reduced-opacity color (hex with alpha channel)
- [ ] Visual treatment removed (bar reverts to normal colors) when market closes and partial bar is absent

### Non-Functional
- [ ] On-demand snapshot fetch adds ≤200ms to `/chart` P95 latency for non-watchlist symbols
- [ ] On-demand fetch failure does not increase `/chart` error rate (absorbed as null, silent fallback)
- [ ] Full `setData` still used on initial chart load; `series.update()` only on poll tick refreshes

### Quality Gates
- [ ] `deno lint supabase/functions/chart/` — 0 warnings
- [ ] `deno lint supabase/functions/_shared/providers/alpaca-client.ts` — 0 warnings
- [ ] `deno fmt supabase/functions/` — no changes
- [ ] `deno check supabase/functions/chart/index.ts`
- [ ] `npm run build` — no TypeScript errors
- [ ] macOS: no Swift compiler errors for `LightweightCandle.color` field

---

## Dependencies & Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| m15 synthesis conflicts with `intraday-live-refresh` m15 bars | Low | Low — both upsert same conflict key | Upsert idempotency ensures last-write wins; no duplicates |
| On-demand snapshot latency spikes | Low | Medium — chart feels slow | `maxRetries=0`; 200ms P95 budget; failure returns null |
| TradingView per-bar color API breaking change between chart versions | Low | Medium — bars render without color | Wrap in try/catch; fallback to uniform series colors |
| `LightweightCandle.color` breaks Encodable bridge | Low | Low — optional field | `String?` encodes as `null` if nil; JS ignores null color |
| m15 period boundary edge: top-of-hour overlap with h1 | Low | None — each timeframe requested independently | Each chart view requests one timeframe; no overlap |

---

## Sources & References

### Origin
- **Solution document:** [docs/solutions/integration-issues/live-partial-candle-synthesis-timeframe-coordination.md](docs/solutions/integration-issues/live-partial-candle-synthesis-timeframe-coordination.md)
  - Key patterns carried forward: `getPartialPeriodStart`, `synthesizePartialBar`, `PARTIAL_CANDLE_TFS` dispatch, `pollTick` pattern, `is_partial` filter in cache writes

### Internal References

- `supabase/functions/chart/index.ts` — `PARTIAL_CANDLE_TFS` at line 756, `getPartialPeriodStart` at line 315, Promise.all slot 8 gate at line 689
- `supabase/functions/_shared/providers/alpaca-client.ts` — `getQuote()` at line 158, `AlpacaSnapshot.minuteBar` at line 63, timeframe mapping at line 571
- `frontend/src/components/TradingViewChart.tsx` — `setMarkers` usage at line 441, `formattedBars` at line 335, `PARTIAL_CANDLE_HORIZONS` at line 121
- `client-macos/SwiftBoltML/Services/ChartBridge.swift` — `LightweightCandle` struct at line 257, `setCandles()` at line 589
- `client-macos/SwiftBoltML/ViewModels/ChartViewModel.swift` — `partialCandleTimeframes` at line 1808
- `client-macos/SwiftBoltML/Models/OHLCBar.swift` — `isPartial: Bool?` at line 16
- `StrategyBuilderWebStyle.swift` line 1859 — `.opacity(r.isPartial ? 0.55 : 1.0)` visual precedent

### Related Work
- **PR #30** — https://github.com/PapaPablano/SwiftBolt_ML/pull/30 (base implementation this plan extends)
- `docs/solutions/security-issues/swiftui-credential-and-injection-hardening.md` — Task lifecycle patterns for macOS refresh
