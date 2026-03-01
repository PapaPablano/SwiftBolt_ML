---
status: pending
priority: p2
issue_id: "039"
tags: [code-review, security, rate-limiting, paper-trading]
dependencies: []
---

# 039 — No Per-User Rate Limiting on Financial and Compute-Heavy Endpoints

## Problem Statement
`paper-trading-executor`, `strategies`, `backtest-strategy`, `symbols-search`, and `quotes` have no per-user or per-IP rate limiting. The `_shared/rateLimiter.ts` utility exists but is not applied to these endpoints. A script can flood them, causing financial operation spam, compute exhaustion, and Alpaca API quota depletion.

## Findings
- `supabase/functions/_shared/rateLimiter.ts`: rate limiter utility exists but unused on key endpoints
- `paper-trading-executor`: no rate limit → unlimited position operations per minute
- `backtest-strategy`: no rate limit → can queue unlimited compute jobs
- `quotes`: no rate limit → unlimited Alpaca API calls (burns quota)
- `symbols-search`: no rate limit → can cause continuous DB scans

## Proposed Solutions

### Option A: Apply existing rateLimiter to critical endpoints (Recommended)
Import and instantiate `RateLimiter` from `_shared/rateLimiter.ts` with appropriate per-endpoint limits:
- `paper-trading-executor`: 10 req/min per user
- `backtest-strategy`: 5 req/min per user
- `quotes`: 30 req/min per IP
- `symbols-search`: 20 req/min per IP
- Effort: Small (1-2 hours for all four functions)
- Risk: Low

## Recommended Action
Option A.

## Technical Details
- **Affected files:** `supabase/functions/paper-trading-executor/index.ts`, `supabase/functions/backtest-strategy/index.ts`, `supabase/functions/quotes/index.ts`, `supabase/functions/symbols-search/index.ts`

## Acceptance Criteria
- [ ] paper-trading-executor: max 10 executions/min per authenticated user
- [ ] backtest-strategy: max 5 jobs/min per user
- [ ] quotes: max 30 req/min per IP
- [ ] symbols-search: max 20 req/min per IP
- [ ] Rate limit exceeded returns 429 with Retry-After header

## Work Log
- 2026-03-01: Identified by security-sentinel review agent (HIGH-01)
