---
status: pending
priority: p2
issue_id: "097"
tags: [code-review, live-trading, circuit-breaker, timezone]
dependencies: []
---

# Daily loss circuit breaker computes "today" in UTC — DST boundary errors during EDT

## Problem Statement

`checkDailyLossLimit` queries `WHERE exit_time >= today 00:00 ET`. Edge Functions run with UTC as the only available clock (no TZ environment variable). If hardcoded as UTC-5 (EST), trades closing between midnight ET and 1am ET during EDT (summer, UTC-4) are excluded from the daily count — the circuit breaker undercounts losses on summer days.

## Findings

**Architecture Strategist (P2):** "DST transitions occur on the second Sunday of March and the first Sunday of November. If hardcoded as UTC-5, trades that close between midnight ET and 1am ET during EDT will be excluded from the daily count."

**Correct approach:** Use Postgres's timezone database via `AT TIME ZONE 'America/New_York'` in the SQL query, executed server-side.

## Proposed Solutions

### Option A: Postgres AT TIME ZONE in DB query (Recommended)
```sql
SELECT COALESCE(SUM(pnl), 0) AS daily_pnl
FROM live_trading_trades
WHERE user_id = $1
  AND strategy_id = $2
  AND (exit_time AT TIME ZONE 'America/New_York')::date
      = (NOW() AT TIME ZONE 'America/New_York')::date;
```
Must be called via `supabase.rpc()` or raw Postgres REST, not a simple `.from().eq()` query.

**Pros:** Correct DST handling via IANA timezone database on Postgres server
**Cons:** Requires raw SQL or RPC function; cannot use PostgREST filter shorthand
**Effort:** Small
**Risk:** Low

### Option B: Compute ET offset in TypeScript
Check if today is in DST by computing whether the date is between second Sunday of March and first Sunday of November.

**Pros:** No DB change needed
**Cons:** DST calculation logic is error-prone, must be maintained manually, no use of standard timezone database
**Effort:** Medium
**Risk:** Medium

## Recommended Action

Implement Option A. Create a Postgres function `get_daily_live_pnl(user_id uuid, strategy_id uuid)` that returns the sum of today's closed P&L in ET. Call it via `supabase.rpc()` in the executor.

## Technical Details

**Migration addition:**
```sql
CREATE OR REPLACE FUNCTION get_daily_live_pnl(p_user_id UUID, p_strategy_id UUID)
RETURNS DECIMAL AS $$
  SELECT COALESCE(SUM(pnl), 0)
  FROM live_trading_trades
  WHERE user_id = p_user_id
    AND strategy_id = p_strategy_id
    AND (exit_time AT TIME ZONE 'America/New_York')::date
        = (NOW() AT TIME ZONE 'America/New_York')::date;
$$ LANGUAGE SQL STABLE SECURITY DEFINER;
```

## Acceptance Criteria

- [ ] Daily loss query uses `AT TIME ZONE 'America/New_York'` in Postgres, not UTC comparison
- [ ] DST transitions (March, November) do not cause day boundary miscalculation
- [ ] Unit test: mock trades closing at 23:30 ET and 00:30 ET — assert both counted in the same trading day

## Work Log

- 2026-03-03: Finding created from Architecture Strategist (P2).
