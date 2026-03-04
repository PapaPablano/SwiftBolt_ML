---
status: pending
priority: p1
issue_id: "085"
tags: [code-review, live-trading, architecture, state-machine]
dependencies: []
---

# Orphaned live position — missing `pending_bracket` status and synchronous bracket failure recovery

## Problem Statement

If an entry market order fills at TradeStation but the subsequent bracket order placement fails (network error, 4xx, Edge Function timeout), the position remains in the DB without a stop-loss or take-profit. Real capital is now deployed in an unprotected position. The plan defers cleanup to "a cleanup job (or manual review)" — but no such job is designed anywhere in the plan, and the function is manual-trigger only with no autonomous background processing.

This is the highest-consequence failure mode: a gap-down overnight could produce unbounded losses on an unprotected position.

## Findings

**Architecture Strategist (P1):** The plan's State Lifecycle Risks section acknowledges this but the mitigation is deferred. The `pending_entry` status is used for both "order placed, waiting for fill" AND "fill confirmed, bracket not yet placed" — no distinct state exists to represent the dangerous in-between.

**Security Sentinel (SEC-10 P2):** `checkBracketFills()` only fetches `status='open'` positions, not `pending_entry`. A position stuck in `pending_entry` after fill is never examined by the monitoring loop.

**SpecFlow Analysis:** Listed as the most critical gap — "orphan entry: entry fills but bracket placement fails."

**Current plan flow (Phase 3e):** Entry fills → immediately attempt bracket placement → on success, update status to `open`. On failure: plan says nothing.

## Proposed Solutions

### Option A: Add `pending_bracket` status + synchronous recovery (Recommended)
Add `pending_bracket` to the status enum. After entry fill: set `status='pending_bracket'`. Attempt bracket placement. On success: set `status='open'`. On failure: immediately place a market close order to exit the unprotected position, then set `status='cancelled'`. This is the only option that keeps real capital safe with zero orphan window.

**Pros:** Correct state machine, capital always protected, no need for monitoring job
**Cons:** Requires migration to add `pending_bracket` to CHECK constraint; must add `pending_bracket` to `checkBracketFills` monitoring loop
**Effort:** Medium
**Risk:** Low

### Option B: Synchronous close-on-bracket-fail without new status
Keep the current status enum but handle bracket failure with an immediate synchronous close in the same execution cycle. No new status value needed.

**Pros:** Smaller migration change
**Cons:** The dangerous state is invisible — a position that is closing cannot be distinguished from one that never entered. Dashboard shows confusing data.
**Effort:** Small
**Risk:** Medium (ops visibility gap)

### Option C: pg_cron cleanup job
Schedule a pg_cron job that runs every 60 seconds and closes any `pending_entry` position older than 5 minutes.

**Pros:** Decoupled from execution
**Cons:** Up to 5 minutes of unprotected live position. Requires pg_cron setup. Defers the real fix.
**Effort:** Medium
**Risk:** High (5-minute window is unacceptable for live trading)

## Recommended Action

Implement Option A. Update the Phase 1 migration to add `pending_bracket` to the status CHECK. Update Phase 3e pseudocode to: (1) set status='pending_bracket' after fill confirmation, (2) attempt bracket placement, (3) on success set status='open', on failure call immediate market close via TradeStation API and set status='cancelled' with `close_reason='bracket_placement_failed'`. Also update `checkBracketFills` to monitor `pending_bracket` positions.

## Technical Details

**Affected files:**
- `supabase/migrations/20260303110000_live_trading_tables.sql` — add `pending_bracket` to CHECK constraint
- `supabase/functions/live-trading-executor/index.ts` — Phase 3e execution flow
- `docs/plans/2026-03-03-feat-live-trading-executor-tradestation-plan.md` — update acceptance criteria

**Status enum change:**
```sql
CHECK (status IN ('pending_entry','pending_bracket','open','pending_close','closed','cancelled'))
```

**Execution flow change:**
```typescript
// After fill confirmed:
await supabase.from('live_trading_positions').update({ status: 'pending_bracket' }).eq('id', posId);
const bracketResult = await placeBracketOrders(tsToken, accountId, entryOrderId, slPrice, tpPrice, qty);
if (!bracketResult.success) {
  // IMMEDIATELY close the unprotected position
  await placeMarketOrder(tsToken, accountId, symbol, qty, oppositeAction);
  await supabase.from('live_trading_positions').update({ status: 'cancelled', close_reason: 'bracket_placement_failed' }).eq('id', posId);
  return;
}
await supabase.from('live_trading_positions').update({ status: 'open', broker_sl_order_id: ..., broker_tp_order_id: ... }).eq('id', posId);
```

## Acceptance Criteria

- [ ] `pending_bracket` status added to live_trading_positions CHECK constraint
- [ ] Position only reaches `status='open'` after both fill AND bracket confirmed
- [ ] Bracket placement failure triggers synchronous market close within the same execution cycle
- [ ] `checkBracketFills` monitors `pending_bracket` positions as well as `open` positions
- [ ] Dashboard surfaces `pending_bracket` positions as a distinct state (not silently merged with `open`)
- [ ] `close_reason='bracket_placement_failed'` recorded in closed position for audit

## Work Log

- 2026-03-03: Finding created from Architecture Strategist (P1), Security Sentinel (SEC-10), and SpecFlow analysis gap review.
