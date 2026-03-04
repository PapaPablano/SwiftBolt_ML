---
status: pending
priority: p1
issue_id: "115"
tags: [code-review, live-trading, database, rate-limiting, architecture]
dependencies: []
---

# `increment_rate_limit` RPC not defined in any migration — non-atomic fallback always executes

## Problem Statement

The `checkRateLimit` function in `live-trading-executor/index.ts` (lines 120–151) calls `supabase.rpc("increment_rate_limit", ...)` as the primary path, but no migration in the PR defines this PostgreSQL function. The executor always falls back to the manual read-then-write path. The fallback is not atomic: two concurrent invocations can both read `request_count = 9`, both increment to 10, and both write 10, meaning the rate limiter effectively allows 2x the intended request limit. Since this governs real-money order submission, a non-atomic rate limiter is a financial risk.

## Findings

Architecture Strategist P1-C. Security Sentinel FINDING-03 (TOCTOU).

## Proposed Solutions

Option A (Recommended): Add a migration that creates the `increment_rate_limit` PostgreSQL function using atomic `INSERT ... ON CONFLICT DO UPDATE SET request_count = live_order_rate_limits.request_count + 1 RETURNING request_count`. This makes the RPC the primary path and allows the non-atomic fallback to be removed. Effort: Small (SQL function is a one-liner).

Option B: Wrap the fallback's check-and-increment in a `FOR UPDATE` SELECT lock to make it serialized. Effort: Small but adds lock contention.

## Acceptance Criteria

- [ ] `increment_rate_limit` PostgreSQL function is defined in a migration
- [ ] The function atomically increments the count and returns it in one statement
- [ ] The non-atomic manual fallback is removed from the executor
- [ ] Rate limit is enforced correctly under concurrent requests
