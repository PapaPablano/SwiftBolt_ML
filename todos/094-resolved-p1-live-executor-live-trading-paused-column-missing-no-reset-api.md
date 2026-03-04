---
status: pending
priority: p1
issue_id: "094"
tags: [code-review, live-trading, agent-native, database, circuit-breaker]
dependencies: []
---

# `live_trading_paused` column missing from DB schema with no reset API

## Problem Statement

The brainstorm document (line 49) specifies: "if realized P&L < -X% of starting equity, halt and set `live_trading_paused = true` on the strategy." The plan's `checkDailyLossLimit` circuit breaker (Phase 3b) returns a `CircuitBreakerResult` but:

1. The Phase 1 migration SQL never adds `live_trading_paused BOOLEAN` to `strategy_user_strategies`
2. There is no API endpoint to reset the paused state
3. The only resolution is direct DB manipulation — breaking agent-native parity

## Findings

**Agent-Native Reviewer (P1):** "`live_trading_paused` column is referenced in the brainstorm as the daily-loss-limit response action, but disappears from the plan's migration SQL and no reset API is planned. If the circuit breaker fires, the only resolution is direct DB manipulation."

**SpecFlow Analysis:** "Circuit breaker state must be persisted in DB — Edge Function cold starts reset any in-memory state. The daily loss limit flag must survive function restarts."

**Agent-Native Reviewer (P1):** "No `live_trading_paused` toggle defined in Phase 6 (UI) and no `reset_circuit_breaker` action defined anywhere in the plan."

## Proposed Solutions

### Option A: Add column to migration + reset action to executor (Recommended)
1. Add `live_trading_paused BOOLEAN DEFAULT FALSE NOT NULL` to the Phase 1 migration that modifies `strategy_user_strategies`
2. In `checkDailyLossLimit`, when limit is breached: `UPDATE strategy_user_strategies SET live_trading_paused = true WHERE id = strategy.id`
3. Add `POST { action: "reset_circuit_breaker", strategy_id: uuid }` path to the executor
4. Add the toggle to Phase 6 frontend (visible only when `live_trading_paused = true`)

**Pros:** Persistent across cold starts, resettable programmatically, agent-accessible
**Cons:** Requires migration change (add column)
**Effort:** Small
**Risk:** Low

### Option B: Use a separate `live_trading_pauses` table with timestamps
Instead of a boolean column, maintain a log of pause events.

**Pros:** Auditable history of circuit breaker triggers
**Cons:** More complex schema, requires join on every strategy read
**Effort:** Medium
**Risk:** Low

## Recommended Action

Implement Option A. The column addition to `strategy_user_strategies` must be in the Phase 1 migration. The `checkDailyLossLimit` function must set it when the circuit breaker fires. A `reset_circuit_breaker` action must be added to Phase 3's executor handler.

## Technical Details

**Affected files:**
- `supabase/migrations/20260303110000_live_trading_tables.sql` — add `live_trading_paused` column migration
- `supabase/functions/live-trading-executor/index.ts` — set flag in `checkDailyLossLimit`, add reset action
- `supabase/functions/strategies/index.ts` — expose `live_trading_paused` in handleGet SELECT list
- `docs/plans/2026-03-03-feat-live-trading-executor-tradestation-plan.md` — add to Phase 1 + Phase 3

**Migration:**
```sql
ALTER TABLE strategy_user_strategies
  ADD COLUMN IF NOT EXISTS live_trading_paused BOOLEAN NOT NULL DEFAULT FALSE;
```

**Executor reset action:**
```typescript
case 'reset_circuit_breaker': {
  const { strategy_id } = body;
  await supabase.from('strategy_user_strategies')
    .update({ live_trading_paused: false })
    .eq('id', strategy_id)
    .eq('user_id', userId);  // RLS via code
  return successResponse({ reset: true });
}
```

## Acceptance Criteria

- [ ] `live_trading_paused BOOLEAN DEFAULT FALSE` added to `strategy_user_strategies` in migration
- [ ] `checkDailyLossLimit` sets `live_trading_paused = true` in DB when circuit breaker fires
- [ ] Every execution cycle checks `live_trading_paused` and returns `circuit_breaker` error immediately if true
- [ ] `POST { action: "reset_circuit_breaker", strategy_id }` resets the flag
- [ ] `GET /strategies` list includes `live_trading_paused` in the SELECT list
- [ ] Phase 6 frontend shows circuit breaker status and a "Reset" button when paused

## Work Log

- 2026-03-03: Finding created from Agent-Native Reviewer (P1 finding #2) and SpecFlow analysis.
