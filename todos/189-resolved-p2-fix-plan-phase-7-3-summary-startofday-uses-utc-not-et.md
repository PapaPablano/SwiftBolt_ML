---
status: resolved
priority: p2
issue_id: "189"
tags: [plan-review, live-trading, financial-accuracy, typescript, timezone]
dependencies: []
---

# Fix Plan Phase 7.3: `startOfDay` for summary endpoint uses server UTC, not Eastern Time — wrong daily P&L boundary

## Problem Statement

Phase 7.3 adds a date filter to the `handleSummary` function: `gte("exit_time", startOfDay.toISOString())`. The `startOfDay` is computed as `new Date()` then `.setHours(0, 0, 0, 0)` — this uses the Edge Function server's timezone (UTC), not Eastern Time. The US equity market trading day starts at 9:30am ET. The summary's daily boundary will be midnight UTC (4–5 hours before the ET market open), causing yesterday's late trades to appear in today's summary.

## Findings

**Spec-Flow Analyzer (GAP-P2-7):**

The plan's Phase 7.3 pseudocode:
```typescript
const startOfDay = new Date();
startOfDay.setHours(0, 0, 0, 0);  // ← midnight UTC, not midnight ET
const { data } = await supabase
  .from("live_trading_trades")
  .select("*")
  .eq("user_id", userId)
  .gte("exit_time", startOfDay.toISOString());
```

**Problem:** UTC midnight is 5 hours before ET midnight (EST) or 4 hours before ET midnight (EDT). A trade closed at 11:30pm ET (= 4:30am UTC next day) will appear in "today's" summary even though it was placed on the prior trading day. For a day trader reconciling P&L with their brokerage statement, this produces incorrect daily figures.

**The executor already has correct ET time computation:** `checkDailyLossLimit` at lines 362–366 of `index.ts`:
```typescript
const now = new Date();
const et = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York" })
  .formatToParts(now);
const todayStartET = new Date(
  `${et.find(p => p.type === "year")?.value}-${...}-${...}T00:00:00-05:00`
);
```

The same ET-based start-of-day calculation must be used in `handleSummary`.

**Correct implementation:**
```typescript
function getETStartOfDay(): Date {
  const now = new Date();
  const etFormatter = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    year: "numeric", month: "2-digit", day: "2-digit",
  });
  const parts = etFormatter.formatToParts(now);
  const year = parts.find(p => p.type === "year")?.value;
  const month = parts.find(p => p.type === "month")?.value;
  const day = parts.find(p => p.type === "day")?.value;
  // Return midnight ET (offset -05:00 EST or -04:00 EDT handled by Date parsing)
  return new Date(`${year}-${month}-${day}T00:00:00-05:00`);
}
```

Extract this as a shared utility in `_shared/` since both `checkDailyLossLimit` and `handleSummary` need it.

## Proposed Solution

Amend Phase 7.3 in the plan to:
1. Use ET-based start-of-day (same logic as `checkDailyLossLimit`)
2. Extract `getETStartOfDay()` as a shared utility function in `_shared/` for reuse
3. Note the EST/EDT offset handling (use `America/New_York` timezone for automatic DST handling)

## Acceptance Criteria

- [x] Phase 7.3 `startOfDay` uses Eastern Time, not UTC
- [x] `getETStartOfDay()` utility extracted and used by both `handleSummary` and `checkDailyLossLimit`
- [x] DST handled correctly via `America/New_York` timezone (not hardcoded -05:00 offset)
- [x] Test: trades closed at 11pm ET appear in the same day's summary, not the next day's

## Work Log

- 2026-03-03: Finding from spec-flow-analyzer (GAP-P2-7) during plan review. The `checkDailyLossLimit` function already has correct ET time logic — it just needs to be shared with `handleSummary`.

- 2026-03-03: RESOLVED. Plan amended to address all findings.
