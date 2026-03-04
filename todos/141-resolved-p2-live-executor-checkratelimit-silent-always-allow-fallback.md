---
status: pending
priority: p2
issue_id: "141"
tags: [code-review, live-trading, reliability, rate-limiting]
dependencies: ["115"]
---

# `checkRateLimit` silent fallback always allows on RPC error

## Problem Statement

`/Users/ericpeterson/SwiftBolt_ML/supabase/functions/live-trading-executor/index.ts` lines 111–152: `checkRateLimit` has two paths:
1. RPC call to `increment_rate_limit` (the primary path, but see todo #115 — RPC is missing from migrations)
2. A manual `select` + `upsert` fallback path if the RPC errors

The critical bug: if the RPC errors and falls to the manual path, the manual upsert has no error handling and the function always returns `true` (allowed). This means **if the RPC doesn't exist (which is currently the case per todo #115), every rate limit check silently succeeds** regardless of actual request count.

Combined with todo #115 (RPC not defined in migrations), the rate limiter is currently non-functional in production.

## Findings

**Code Simplicity Reviewer (P2-5):** "If the RPC doesn't exist, this silently succeeds every time since the manual upsert has no error handling and the function always returns `true` when the upsert path is reached... Two paths with different failure modes, both in production, is a latent reliability bug."

## Proposed Solutions

**Option A (Recommended — consolidate to manual path):** Remove the RPC call entirely. Use the manual `select` + `upsert` path as the sole implementation, with proper error handling that throws on DB failure. This eliminates the silent always-allow mode.

**Option B:** Fix the RPC migration (see todo #115), then treat RPC errors as fatal (throw instead of fall-through) so silent bypass is impossible.

**Option C:** Keep the two-path structure but add proper error handling to the manual path so DB failure causes the check to fail closed (deny) rather than silently allow.

## Acceptance Criteria

- [ ] Rate limiter never silently allows all requests on backend error
- [ ] On DB error, rate limit check fails closed (denies) or throws
- [ ] Single code path for rate limiting (eliminates dual-path confusion)

## Work Log

- 2026-03-03: Finding from code-simplicity-reviewer. Related to todo #115 (RPC missing from migrations).
