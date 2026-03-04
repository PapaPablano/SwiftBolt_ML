---
status: pending
priority: p1
issue_id: "088"
tags: [code-review, live-trading, concurrency, database, race-condition]
dependencies: []
---

# TOCTOU double-entry race — no DB unique constraint for active positions per strategy/symbol

## Problem Statement

The plan enforces "one position per strategy per symbol" only in application code (step 6b of the execution cycle checks open positions before placing an entry). With concurrent invocations, two calls can both pass this check before either has inserted a position row, resulting in two market entry orders for the same strategy + symbol — doubling the intended position size and risk exposure.

## Findings

**Architecture Strategist (P1):** "If two concurrent invocations of `live-trading-executor` for the same user/strategy/symbol both pass the `getOpenPosition` check (reading zero open positions before either has inserted), both will place market entry orders. With real money, this means 2x the intended position size and 2x the risk exposure."

**Security Sentinel (SEC-11 P2):** "The described mitigation [broker_sl_order_id IS NOT NULL check] is a non-atomic read-modify-write pattern — two invocations can both read NULL before either inserts."

**Current plan (Phase 3d, step 6b):** "Check for existing open position (getOpenPosition) — if already open, skip." This is a pure application-level check with no DB enforcement.

## Proposed Solutions

### Option A: DB partial unique index on active positions (Recommended)
Add a partial unique index:
```sql
CREATE UNIQUE INDEX uix_live_positions_active
  ON live_trading_positions (strategy_id, symbol_id)
  WHERE status IN ('pending_entry', 'pending_bracket', 'open', 'pending_close');
```
The second concurrent INSERT hits a unique constraint violation, which the executor catches and treats as a no-op (position already exists for this strategy+symbol). The application-level check remains as an optimization to avoid unnecessary DB round trips.

**Pros:** Atomic enforcement at DB level, uses established pattern (similar to `paper_trading_positions`), no distributed lock needed
**Cons:** Must handle constraint violation in application code (catch and return gracefully)
**Effort:** Small
**Risk:** Low

### Option B: Postgres advisory lock per (strategy_id, symbol_id)
Acquire a session-level advisory lock before the position check.

**Pros:** Prevents concurrent entry entirely
**Cons:** Holds lock across multiple DB queries + HTTP call — can cause deadlocks if Edge Function invocation terminates without releasing lock. Requires raw SQL.
**Effort:** Medium
**Risk:** Medium

### Option C: Keep code-only check, add retry loop
If the INSERT fails due to any error, retry the position check and skip if a position now exists.

**Pros:** No schema change
**Cons:** Race window still exists, just narrower. Not atomic. Two entries can still succeed before either is in DB.
**Effort:** Small
**Risk:** High (doesn't actually solve the TOCTOU)

## Recommended Action

Implement Option A. Add the partial unique index to the Phase 1 migration. Update Phase 3d to catch unique constraint violations (Postgres error code `23505`) and treat them as "position already open — skip entry" rather than propagating as errors.

## Technical Details

**Affected files:**
- `supabase/migrations/20260303110000_live_trading_tables.sql` — add partial unique index
- `supabase/functions/live-trading-executor/index.ts` — catch `23505` in INSERT path

**Index SQL:**
```sql
-- Add after CREATE TABLE live_trading_positions:
CREATE UNIQUE INDEX uix_live_positions_active
  ON live_trading_positions (strategy_id, symbol_id)
  WHERE status IN ('pending_entry', 'pending_bracket', 'open', 'pending_close');
```

**Application handler:**
```typescript
const { error } = await supabase.from('live_trading_positions').insert(position);
if (error?.code === '23505') {
  // Another invocation already entered this position — not an error
  return { success: true, action: 'skipped', reason: 'position_already_active' };
}
```

## Acceptance Criteria

- [ ] `uix_live_positions_active` partial unique index added to migration
- [ ] `pending_bracket` status (from todo #085) included in the index's WHERE clause
- [ ] Executor handles Postgres `23505` constraint violation as a graceful skip, not an error
- [ ] Test: two concurrent invocations for the same strategy+symbol — assert only one market order placed

## Work Log

- 2026-03-03: Finding created from Architecture Strategist (P1) and Security Sentinel (SEC-11).
