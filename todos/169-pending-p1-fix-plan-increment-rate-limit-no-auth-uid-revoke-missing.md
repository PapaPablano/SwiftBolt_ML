---
status: pending
priority: p1
issue_id: "169"
tags: [plan-review, live-trading, security, database, rpc]
dependencies: []
---

# Fix Plan Phase 2.2: `increment_rate_limit` missing `REVOKE EXECUTE` and `auth.uid()` validation — any authenticated user can target another user's rate limit

## Problem Statement

The Phase 2.2 migration creates `increment_rate_limit` as a `SECURITY DEFINER` RPC but omits two critical security controls: (1) `REVOKE EXECUTE FROM PUBLIC` so that only the service role can call it, and (2) an `auth.uid() = p_user_id` check inside the function body. Without these, any authenticated Supabase user can call this RPC via PostgREST and write arbitrary rows to `live_order_rate_limits` for any `user_id`, effectively burning another user's rate limit quota or bypassing their own.

## Findings

**Security Sentinel (P1-Finding 2.2/6.1):**

The plan's Phase 2.2 RPC definition:

```sql
CREATE OR REPLACE FUNCTION increment_rate_limit(p_user_id UUID, p_window_start TIMESTAMPTZ)
RETURNS TABLE(order_count INT, window_start TIMESTAMPTZ)
LANGUAGE plpgsql
SECURITY DEFINER AS $$
BEGIN
  INSERT INTO live_order_rate_limits (user_id, window_start, order_count)
  VALUES (p_user_id, p_window_start, 1)
  ON CONFLICT (user_id, window_start)
  DO UPDATE SET order_count = live_order_rate_limits.order_count + 1;

  RETURN QUERY SELECT order_count, window_start FROM live_order_rate_limits
    WHERE user_id = p_user_id AND window_start = p_window_start;
END;
$$;
```

Missing from the plan:

**Problem 1: No REVOKE EXECUTE**

By default, `CREATE FUNCTION` grants EXECUTE to `PUBLIC` in PostgreSQL. This means every Supabase role (`anon`, `authenticated`, service_role) can call `increment_rate_limit` via PostgREST.

Attack vector:
```bash
# Any authenticated user can call this via the REST API:
POST /rest/v1/rpc/increment_rate_limit
Authorization: Bearer <any_valid_jwt>
{"p_user_id": "<victim_uuid>", "p_window_start": "2026-03-03T00:00:00Z"}
```

This increments the victim's `order_count`, causing the rate limiter to reject the victim's legitimate trades.

**Problem 2: No `auth.uid()` validation**

Even with REVOKE, defense-in-depth requires the function body to reject calls where `p_user_id != auth.uid()`:

```sql
IF auth.uid() IS DISTINCT FROM p_user_id THEN
  RAISE EXCEPTION 'unauthorized: user_id mismatch';
END IF;
```

Without this, if REVOKE is misconfigured or bypassed, the function silently accepts cross-user writes.

**Correct implementation:**

```sql
CREATE OR REPLACE FUNCTION increment_rate_limit(p_user_id UUID, p_window_start TIMESTAMPTZ)
RETURNS TABLE(order_count INT, window_start TIMESTAMPTZ)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp  -- see todo #170
AS $$
BEGIN
  -- Defense in depth: reject cross-user calls
  IF auth.uid() IS DISTINCT FROM p_user_id THEN
    RAISE EXCEPTION 'unauthorized: caller % cannot increment rate limit for %',
      auth.uid(), p_user_id
      USING ERRCODE = 'insufficient_privilege';
  END IF;

  INSERT INTO live_order_rate_limits (user_id, window_start, order_count)
  VALUES (p_user_id, p_window_start, 1)
  ON CONFLICT (user_id, window_start)
  DO UPDATE SET order_count = live_order_rate_limits.order_count + 1;

  RETURN QUERY SELECT order_count, window_start FROM live_order_rate_limits
    WHERE user_id = p_user_id AND window_start = p_window_start;
END;
$$;

-- Revoke public access; only service_role should call this RPC
REVOKE EXECUTE ON FUNCTION increment_rate_limit(UUID, TIMESTAMPTZ) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION increment_rate_limit(UUID, TIMESTAMPTZ) FROM anon;
REVOKE EXECUTE ON FUNCTION increment_rate_limit(UUID, TIMESTAMPTZ) FROM authenticated;
GRANT EXECUTE ON FUNCTION increment_rate_limit(UUID, TIMESTAMPTZ) TO service_role;
```

Note: The live-trading-executor Edge Function runs with the service_role key, so GRANT to service_role is sufficient.

## Proposed Solution

Update Phase 2.2 in the plan to include both security controls in the RPC definition. The `auth.uid()` check provides defense-in-depth for the case where the executor accidentally calls with a wrong `user_id`; the REVOKE EXECUTE prevents any non-service-role caller from reaching the function at all.

## Acceptance Criteria

- [ ] `REVOKE EXECUTE FROM PUBLIC, anon, authenticated` added to Phase 2.2 RPC definition
- [ ] `GRANT EXECUTE TO service_role` added
- [ ] `auth.uid() = p_user_id` validation added inside function body with clear exception message
- [ ] Plan notes that the executor must use service_role key (not anon key) to call this RPC

## Work Log

- 2026-03-03: Finding from security-sentinel (P1-Finding 2.2/6.1) during plan review. The GRANT EXECUTE gap was partially noted in todo #157 but the `auth.uid()` cross-user write attack was not captured anywhere.
