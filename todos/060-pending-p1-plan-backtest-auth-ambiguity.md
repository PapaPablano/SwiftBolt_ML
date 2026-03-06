---
status: pending
priority: p1
issue_id: "060"
tags: [code-review, architecture, authentication, plan-amendment]
dependencies: []
---

# 060 — Plan Auth Ambiguity: Backtest Endpoint Already Requires Auth

## Problem Statement

The plan states "chart viewing and backtesting remain unauthenticated," but `backtest-strategy/index.ts` (lines 25-31) already calls `supabase.auth.getUser()` and returns 401 on failure. The frontend currently works by passing the Supabase anon key as a Bearer token, which Supabase treats as a valid JWT with the `anon` role. This is fragile — if the anon key is rotated or GoTrue changes behavior, backtesting breaks.

The plan must explicitly decide: should backtesting require auth or not?

## Findings

- **Architecture Strategist:** "The current behavior (anon key JWT works by coincidence, not design) is fragile"
- **Security Sentinel:** Confirmed `backtest-strategy/index.ts` has mandatory auth check
- **Learnings Researcher:** Found issue 048 — `ga-strategy` had `verify_jwt=false` without documentation, similar pattern

## Proposed Solutions

### Option A: Make Backtesting Explicitly Unauthenticated (Recommended)
- Modify `backtest-strategy/index.ts` to allow anonymous access (skip auth check or accept anon role)
- Document the decision in the endpoint
- **Pros:** Matches plan intent, removes fragile anon-key-as-jwt dependency
- **Cons:** Backtest results not tied to a user (acceptable for v1)
- **Effort:** Small
- **Risk:** Low

### Option B: Require Auth for Backtesting Too
- Phase 1 auth also covers backtest calls
- Frontend sends user JWT for backtest requests
- **Pros:** Consistent auth model, backtest results tied to user
- **Cons:** Adds friction to exploration (must sign in before backtesting)
- **Effort:** Small (add auth header in backtestService.ts)
- **Risk:** Low

## Recommended Action

Option A for v1 (keep exploration frictionless), document the decision.

## Technical Details

**Affected files:**
- `supabase/functions/backtest-strategy/index.ts` (lines 25-31)
- `frontend/src/lib/backtestService.ts` (line 171 — sends anon key as Bearer)

## Acceptance Criteria

- [ ] Explicit decision documented in plan and code
- [ ] Backtesting works reliably (not dependent on anon key behavior)
- [ ] If option A: backtest-strategy allows anonymous requests
- [ ] If option B: backtestService sends user JWT

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from plan technical review | Architecture Strategist identified auth ambiguity |

## Resources

- Plan: `docs/plans/2026-03-01-feat-backtest-visuals-paper-trading-pipeline-plan.md`
- Related: `todos/048-resolved-p3-ga-strategy-verify-jwt-false-undocumented.md`
