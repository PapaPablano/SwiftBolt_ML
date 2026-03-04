---
status: pending
priority: p2
issue_id: "157"
tags: [plan-review, live-trading, database, security]
dependencies: []
---

# Fix Plan Phase 2.1: Missing `GRANT EXECUTE ON FUNCTION increment_rate_limit TO service_role`

## Problem Statement

The Phase 2.1 migration creates `increment_rate_limit` as a `SECURITY DEFINER` function but does not include a `GRANT EXECUTE` statement. In Supabase, the `service_role` key is what the Edge Function uses, but explicit grants are required for `service_role` to call `SECURITY DEFINER` functions reliably across all Supabase versions and permission configurations.

## Findings

**Data Integrity Guardian (P2-B):**

The `live_order_rate_limits` table has RLS enabled with no user-facing policies (service role writes only). The live-trading-executor runs as `service_role` and calls `increment_rate_limit` via `.rpc()`. While `service_role` generally has broad privileges, omitting the explicit grant can cause permission errors if:

1. The function is called via the `anon` key by mistake during local development
2. Supabase tightens default permissions in a future update
3. The function is called from a different Edge Function that uses a different role

The fix is a one-line addition to the migration:

```sql
GRANT EXECUTE ON FUNCTION increment_rate_limit(UUID, TIMESTAMPTZ, INT) TO service_role;
```

## Proposed Solution

Add immediately after the `CREATE OR REPLACE FUNCTION` block in the Phase 2.1 migration:

```sql
-- Ensure service_role can call this function (Edge Function uses service_role key)
GRANT EXECUTE ON FUNCTION increment_rate_limit(UUID, TIMESTAMPTZ, INT) TO service_role;
```

## Acceptance Criteria

- [ ] `GRANT EXECUTE` added to Phase 2.1 migration
- [ ] `service_role` can call `increment_rate_limit` via `.rpc()`
- [ ] Local Supabase `deno test` confirms RPC callable

## Work Log

- 2026-03-03: Finding from data-integrity-guardian (P2-B) during plan review.
