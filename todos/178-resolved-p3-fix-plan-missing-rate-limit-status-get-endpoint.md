---
status: resolved
priority: p3
issue_id: "178"
tags: [plan-review, live-trading, agent-native, api-design, rate-limiting]
dependencies: []
---

# Fix Plan: Missing `GET ?action=rate_limit_status` endpoint — agent cannot check headroom before submitting execution requests

## Problem Statement

Phase 6.3 changes `checkRateLimit` from fail-open to fail-closed. This is the correct safety posture. However, it creates an agent experience problem: an agent submitting execution requests has no way to check its remaining rate limit budget before it hits 429. Adding a read-only `GET ?action=rate_limit_status` endpoint would allow agents to verify headroom before submitting, enabling graceful back-off rather than reactive 429 handling. The `live_order_rate_limits` table being created in Phase 2.1 already contains all the data needed for this endpoint.

## Findings

**Agent-Native Reviewer (P3-Finding 6):**

The existing GET handler at lines 1147–1252 of `live-trading-executor/index.ts` already has four named actions. Adding a fifth is a small addition. The table is already being created by the Phase 2.1 migration.

**Proposed endpoint:**
```typescript
if (action === "rate_limit_status") {
  const windowStart = new Date(
    Math.floor(Date.now() / RATE_LIMIT_WINDOW_MS) * RATE_LIMIT_WINDOW_MS,
  ).toISOString();

  const { data } = await supabase
    .from("live_order_rate_limits")
    .select("order_count")
    .eq("user_id", user.id)
    .eq("window_start", windowStart)
    .maybeSingle();

  const requestsUsed = data?.order_count ?? 0;
  return corsResponse({
    requests_used: requestsUsed,
    requests_remaining: Math.max(0, ORDER_RATE_LIMIT_PER_MINUTE - requestsUsed),
    limit: ORDER_RATE_LIMIT_PER_MINUTE,
    window_resets_at: new Date(
      Math.ceil(Date.now() / RATE_LIMIT_WINDOW_MS) * RATE_LIMIT_WINDOW_MS,
    ).toISOString(),
  }, 200, origin);
}
```

**Key properties of this endpoint:**
- Read-only (GET, no side effects)
- Does not count against the rate limit itself
- Uses the same `live_order_rate_limits` table created by Phase 2.1
- Returns `window_resets_at` so agents know when the window refreshes

**Agent usage pattern:**
```
1. GET ?action=rate_limit_status
   → { requests_used: 8, requests_remaining: 2, limit: 10, window_resets_at: "..." }
2. If requests_remaining > 0: proceed with execution POST
3. If requests_remaining == 0: wait until window_resets_at, then retry
```

This converts the rate limiter from a reactive failure (agent discovers it's throttled after submitting) to a proactive budget check (agent verifies headroom before committing to a trade signal).

## Proposed Solution

Add `GET ?action=rate_limit_status` to Phase 6 or Phase 8 of the plan. This can be added in the same pass as the other GET action additions in Phase 8.4 and Phase 7.3. The infrastructure (table + RPC) is already being created by Phase 2.1; only the handler branch is new.

## Acceptance Criteria

- [x] `GET ?action=rate_limit_status` returns `{ requests_used, requests_remaining, limit, window_resets_at }`
- [x] Endpoint is read-only and does not count against the rate limit
- [x] `window_resets_at` is a valid ISO 8601 timestamp marking when the current window expires
- [x] Plan documents this endpoint as the recommended pre-execution check for rate-limit-aware agents

## Work Log

- 2026-03-03: Finding from agent-native-reviewer (P3-Finding 6) during plan review. The Phase 2.1 migration creates the `live_order_rate_limits` table; this endpoint exposes it as a queryable resource with no additional DB work.

- 2026-03-03: RESOLVED. Plan amended to address all findings.
