---
status: pending
priority: p1
issue_id: "153"
tags: [plan-review, live-trading, database, migration]
dependencies: []
---

# Fix Plan Phase 2.1: `RETURNING ... INTO` after `INSERT ON CONFLICT DO UPDATE` is invalid PL/pgSQL

## Problem Statement

The `increment_rate_limit` function in the Phase 2.1 migration uses `RETURNING request_count INTO v_count` after an `INSERT ... ON CONFLICT ... DO UPDATE` statement inside a PL/pgSQL block. This is invalid PostgreSQL syntax. The migration will fail to create the RPC, and Phase 6.3 (which removes the fallback and depends entirely on this RPC) will cause the rate limiter to fail-closed on every invocation.

## Findings

**Data Integrity Guardian (P1-C):**

The plan's proposed SQL:

```sql
INSERT INTO live_order_rate_limits (user_id, window_start, request_count)
VALUES (p_user_id, p_window_start, 1)
ON CONFLICT (user_id, window_start)
DO UPDATE SET request_count = live_order_rate_limits.request_count + 1
RETURNING request_count INTO v_count;  -- ← INVALID in PL/pgSQL
```

`RETURNING ... INTO` variable assignment after `INSERT ... ON CONFLICT ... DO UPDATE` is not supported in PL/pgSQL block syntax. Running this migration against Supabase Postgres 15 produces a syntax error at `CREATE OR REPLACE FUNCTION` time, meaning `increment_rate_limit` is never created.

## Proposed Solution

Use a two-statement pattern (upsert then re-read):

```sql
CREATE OR REPLACE FUNCTION increment_rate_limit(
  p_user_id      UUID,
  p_window_start TIMESTAMPTZ,
  p_max_requests INT
) RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_count INT;
BEGIN
  -- Atomic upsert: increment or insert
  INSERT INTO live_order_rate_limits (user_id, window_start, request_count)
  VALUES (p_user_id, p_window_start, 1)
  ON CONFLICT (user_id, window_start)
  DO UPDATE SET request_count = live_order_rate_limits.request_count + 1;

  -- Re-read the post-update count (safe: primary key guarantees single row)
  SELECT request_count INTO v_count
  FROM live_order_rate_limits
  WHERE user_id = p_user_id AND window_start = p_window_start;

  RETURN v_count <= p_max_requests;
END;
$$;
```

The two-statement form is safe because:
1. The `SECURITY DEFINER` function runs with full table access
2. The primary key on `(user_id, window_start)` guarantees the SELECT reads exactly the row that was just upserted
3. Both statements run in the same transaction — no interleaving with other sessions possible

## Acceptance Criteria

- [ ] `increment_rate_limit` function uses two-statement form (upsert + SELECT)
- [ ] `CREATE OR REPLACE FUNCTION` succeeds without syntax errors on Postgres 15
- [ ] Function returns TRUE when under the limit, FALSE when at or over the limit
- [ ] GRANT EXECUTE included (see todo #157)

## Work Log

- 2026-03-03: Finding from data-integrity-guardian (P1-C) during plan review.
