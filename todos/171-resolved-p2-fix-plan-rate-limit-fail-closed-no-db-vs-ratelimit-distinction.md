---
status: resolved
priority: p2
issue_id: "171"
tags: [plan-review, live-trading, reliability, typescript, api-design]
dependencies: []
---

# Fix Plan Phase 3.1/3.2: Rate limit fail-closed conflates DB errors with genuine rate limits — client retry misbehaves

## Problem Statement

The Phase 3 rate limiting implementation returns HTTP 429 for both genuine rate-limit exhaustion AND database errors (when the `increment_rate_limit` RPC fails). These two conditions require different client behavior: rate-limit exhaustion should trigger a hold-and-retry with backoff, while a DB error is transient and should be retried immediately with a short backoff. Returning the same status code for both causes the executor to apply an inappropriate 60-second wait when the underlying issue is a brief DB connectivity blip, potentially causing it to miss the next execution window.

## Findings

**Security Sentinel (P2-Finding 3.1/3.2):**

The plan's Phase 3 pseudo-code:

```typescript
const rateLimitResult = await checkRateLimit(supabase, userId);
if (!rateLimitResult.allowed) {
  return new Response(JSON.stringify({ error: "Rate limit exceeded" }), {
    status: 429,
    headers: { "Retry-After": "60" }
  });
}
```

The `checkRateLimit` function calls `increment_rate_limit` RPC. If the RPC throws (DB connection error, timeout, function not found), `rateLimitResult.allowed` could be `false` (fail-closed), and the caller receives 429 with `Retry-After: 60`.

**Problem:**
1. The executor sees 429 and waits 60 seconds before retrying.
2. If the DB error lasts < 5 seconds, the executor unnecessarily skips the execution window.
3. Logs show `"Rate limit exceeded"` — an operator investigating a DB outage will look in the wrong place.

**Correct behavior:**

| Condition | HTTP Status | Response body | Retry behavior |
|-----------|-------------|---------------|----------------|
| Genuine rate limit | 429 | `{ error: "rate_limited", retryAfterSec: 60 }` | Wait 60s |
| DB error (fail-closed) | 503 | `{ error: "rate_limit_unavailable", retryable: true }` | Retry in 5s |

**Structured log distinction:**
```typescript
// Rate-limited (expected, operational):
console.info("rate_limit_exceeded", { userId, windowStart, orderCount, limit });

// DB error (unexpected, needs alert):
console.error("rate_limit_rpc_failed", { userId, error: err.message });
```

## Proposed Solution

Update Phase 3 in the plan to distinguish between the two failure modes:

```typescript
interface RateLimitResult {
  allowed: boolean;
  reason?: "rate_limited" | "db_error";
  orderCount?: number;
}

async function checkRateLimit(supabase, userId): Promise<RateLimitResult> {
  try {
    const { data, error } = await supabase.rpc("increment_rate_limit", { ... });
    if (error) {
      console.error("rate_limit_rpc_failed", { userId, error: error.message });
      return { allowed: false, reason: "db_error" };  // fail-closed but distinguishable
    }
    const allowed = data.order_count <= ORDER_RATE_LIMIT_PER_MINUTE;
    return { allowed, reason: allowed ? undefined : "rate_limited", orderCount: data.order_count };
  } catch (err) {
    console.error("rate_limit_rpc_exception", { userId, error: err.message });
    return { allowed: false, reason: "db_error" };
  }
}

// In the handler:
const rateLimitResult = await checkRateLimit(supabase, userId);
if (!rateLimitResult.allowed) {
  if (rateLimitResult.reason === "db_error") {
    return new Response(
      JSON.stringify({ error: "rate_limit_unavailable", retryable: true }),
      { status: 503 }
    );
  }
  return new Response(
    JSON.stringify({ error: "rate_limited", retryAfterSec: 60 }),
    { status: 429, headers: { "Retry-After": "60" } }
  );
}
```

## Acceptance Criteria

- [x] Phase 3 distinguishes `"rate_limited"` (genuine) from `"db_error"` (fail-closed) in the RateLimitResult type
- [x] DB errors return HTTP 503 with `retryable: true`, not 429
- [x] Genuine rate limits return HTTP 429 with `Retry-After: 60`
- [x] Structured log events use different keys (`rate_limit_exceeded` vs `rate_limit_rpc_failed`) for operational alerting
- [x] Plan notes that fail-closed is intentional for safety, but must be distinguishable in logs

## Work Log

- 2026-03-03: Finding from security-sentinel (P2-Finding 3.1/3.2) during plan review. Not captured in any existing todo.

- 2026-03-03: RESOLVED. Plan amended to address all findings.
