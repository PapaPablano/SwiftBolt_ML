---
status: pending
priority: p2
issue_id: "019"
tags: [code-review, agent-native, paper-trading, data-integrity, ui]
dependencies: []
---

# 019: current_price in paper_trading_positions is never updated — Open P&L always stale

## Problem Statement

`PaperPosition.unrealizedPnl` computes Open P&L as `(current_price - entry_price) * quantity`. The `current_price` field is read from the `paper_trading_positions` table. However, no Edge Function or background job updates this column for open positions. The `paper-trading-executor` `closePosition` function writes `exit_price` to `paper_trading_trades` when closing — but it does not update `current_price` on open position rows during the execution cycle.

The result: the "Open P&L" metric in `MetricsGridView` is always `nil` or reflects a stale price from when the position was opened, making the primary real-time metric in the dashboard non-functional.

## Findings

**File:** `client-macos/SwiftBoltML/Services/PaperTradingService.swift` lines 22-28

```swift
var unrealizedPnl: Double? {
    guard let current = currentPrice else { return nil }
    // currentPrice comes from DB column `current_price` — never updated
    let diff = direction == "long"
        ? (current - entryPrice) * Double(quantity)
        : (entryPrice - current) * Double(quantity)
    return diff
}
```

**File:** `supabase/functions/paper-trading-executor/index.ts` — `executeStrategy` function processes entry/exit signals but does not write `current_price` to open positions during each cycle.

The `computeMetrics` in `PaperTradingService` calls `.compactMap(\.unrealizedPnl)` — if all positions have `currentPrice == nil`, `openPnl` is always `0.0`.

**Source:** agent-native-reviewer agent (Observation #10)

## Proposed Solutions

### Option A: Update current_price in executor during each cycle (Recommended)

In `paper-trading-executor`, after fetching the current bar's close price for each strategy's symbol, update `current_price` for all open positions on that symbol:

```typescript
// After fetching currentPrice for the symbol:
await supabase
  .from('paper_trading_positions')
  .update({ current_price: currentBar.close })
  .eq('symbol_id', symbolId)
  .eq('status', 'open');
```
- **Pros:** Open P&L becomes accurate after each execution cycle
- **Cons:** Requires executor to run for Open P&L to be current; still stale between cycles
- **Effort:** Small | **Risk:** Low

### Option B: Compute unrealizedPnl server-side and expose via stats endpoint
Rather than storing `current_price`, fetch the latest price in the stats computation.
- **Pros:** Always current if stats endpoint fetches live price
- **Cons:** Requires live price lookup; adds latency to stats endpoint
- **Effort:** Medium | **Risk:** Medium

### Option C: Realtime price update from native app
When the chart loads for a selected symbol, update `current_price` for matching open positions.
- **Pros:** Price is current while user is watching the symbol
- **Cons:** Only updates when user is in the app; no background update
- **Effort:** Small | **Risk:** Low (nice interim fix while Option A is implemented)

## Recommended Action

Option A as the primary fix. Until the executor runs again after a position is opened, the price will be stale — which is acceptable for a paper trading system where position health is evaluated per-cycle.

## Technical Details

**Affected files:**
- `supabase/functions/paper-trading-executor/index.ts` (add current_price update during cycle)
- `client-macos/SwiftBoltML/Services/PaperTradingService.swift` (unrealizedPnl will work correctly once DB has data)

## Acceptance Criteria

- [ ] After a paper trading execution cycle, open positions have `current_price` updated to the latest bar close
- [ ] `unrealizedPnl` returns a non-nil value for open positions after a cycle runs
- [ ] "Open P&L" metric in MetricsGridView shows the correct value
- [ ] Closing a position still uses the correct exit price (not current_price from positions table)

## Work Log

- 2026-02-28: Identified by agent-native-reviewer in PR #23 code review

## Resources

- [PR #23](https://github.com/PapaPablano/SwiftBolt_ML/pull/23)
- `supabase/functions/paper-trading-executor/index.ts`
