---
status: ready
priority: p2
issue_id: "064"
tags: [code-review, security, rate-limiting, input-validation]
dependencies: ["059"]
---

# 064 — Paper Trading Executor Needs Rate Limiting + Condition Validation

## Problem Statement

The paper-trading-executor has no rate limiting on POST endpoints and no server-side validation of strategy condition indicator names/operators. Combined with the deploy flow from Phase 5, an authenticated user could:
- Send thousands of execution requests per second
- Submit crafted conditions with arbitrary indicator names
- Manipulate condition evaluation by targeting internal cache keys (e.g., `*_prev` patterns)

## Findings

- **Security Sentinel:** HIGH — no rate limiting + no condition validation
- **Architecture Strategist:** Shared rate limiter already exists in `_shared/rate-limiter.ts`
- **Performance Oracle:** Unthrottled execution requests cause expensive indicator computations

## Proposed Solutions

### Option A: Rate Limiter + Indicator Allowlist (Recommended)
- Apply shared rate limiter: 10 requests/minute per user for POST /execute
- Add indicator name allowlist in executor (RSI, MACD, Volume_MA, Close, etc.)
- Reject conditions with unrecognized indicators before processing
- **Pros:** Defense in depth, minimal performance overhead
- **Cons:** Allowlist needs maintenance when new indicators added
- **Effort:** Small
- **Risk:** Low

## Technical Details

**Affected files:**
- `supabase/functions/paper-trading-executor/index.ts` (POST handler)
- `supabase/functions/_shared/rate-limiter.ts` (already exists)

## Acceptance Criteria

- [ ] POST /execute rate limited to 10 requests/minute per user
- [ ] Conditions with unrecognized indicator names rejected with 400 error
- [ ] Condition operators validated against allowed set
- [ ] Rate limit exceeded returns 429

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from plan technical review | Security Sentinel finding |
