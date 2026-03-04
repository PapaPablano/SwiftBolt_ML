---
status: resolved
priority: p2
issue_id: "170"
tags: [plan-review, live-trading, security, database, rpc]
dependencies: ["169"]
---

# Fix Plan Phase 2.2: `increment_rate_limit` SECURITY DEFINER missing `SET search_path = public, pg_temp`

## Problem Statement

The Phase 2.2 migration creates `increment_rate_limit` as a `SECURITY DEFINER` function without the standard PostgreSQL security hardening attribute `SET search_path = public, pg_temp`. Without this, a malicious user who can create objects in the database (or exploit a search_path injection via a compromised schema) could shadow `live_order_rate_limits` with a rogue table, causing the SECURITY DEFINER function to write rate limit data to the wrong location.

## Findings

**Security Sentinel (P2-Finding 2.1):**

PostgreSQL best practice for `SECURITY DEFINER` functions requires pinning the `search_path` to prevent search_path injection attacks:

```sql
-- Without search_path guard (vulnerable):
CREATE FUNCTION increment_rate_limit(...)
LANGUAGE plpgsql
SECURITY DEFINER AS $$ ... $$;

-- With search_path guard (hardened):
CREATE FUNCTION increment_rate_limit(...)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp AS $$ ... $$;
```

Without `SET search_path`, if an attacker can create a schema they control and manipulate the session's `search_path`, they could cause the SECURITY DEFINER function to resolve `live_order_rate_limits` to a table in their schema instead of `public`. The function runs with elevated privileges (service_role), so this could allow privilege escalation.

In practice, this risk is low in Supabase (RLS and role separation limit schema creation), but it is a standard OWASP and PostgreSQL hardening requirement for `SECURITY DEFINER` functions. The PostgreSQL documentation explicitly recommends this pattern.

## Proposed Solution

Add `SET search_path = public, pg_temp` to the `increment_rate_limit` function definition in Phase 2.2:

```sql
CREATE OR REPLACE FUNCTION increment_rate_limit(p_user_id UUID, p_window_start TIMESTAMPTZ)
RETURNS TABLE(order_count INT, window_start TIMESTAMPTZ)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
  ...
END;
$$;
```

`pg_temp` is included to prevent temporary table injection from the session's temp schema.

## Acceptance Criteria

- [x] `SET search_path = public, pg_temp` added to `increment_rate_limit` definition in Phase 2.2
- [x] Any other `SECURITY DEFINER` functions in the migration also audited for this guard

## Work Log

- 2026-03-03: Finding from security-sentinel (P2-Finding 2.1) during plan review. Standard PostgreSQL hardening requirement for SECURITY DEFINER functions. Companion to todo #169.

- 2026-03-03: RESOLVED. Plan amended to address all findings.
