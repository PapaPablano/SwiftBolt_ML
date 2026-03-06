---
status: pending
priority: p1
issue_id: "059"
tags: [code-review, security, paper-trading, authentication]
dependencies: []
---

# 059 — Paper Trading Executor POST Endpoints Have No Authentication

## Problem Statement

All POST operations on `paper-trading-executor/index.ts` skip authentication entirely. GET endpoints correctly authenticate using `getSupabaseClientWithAuth()`, but after the GET block ends at line 967, POST handling begins at line 970 with no auth check. The service-role client (lines 812-815) bypasses all RLS. Any unauthenticated caller can trigger `executePaperTradingCycle`, close positions via `close_position`, or create positions.

Additionally, the `close_position` action accepts a `position_id` with no ownership verification — any caller who knows a position UUID can close another user's position at any price.

## Findings

- **Security Sentinel:** CRITICAL — unauthenticated POST + missing ownership check = any internet user can manipulate any user's positions
- **Architecture Strategist:** Confirmed service-role client bypasses all 24 RLS policies
- **Learnings Researcher:** Found pattern from resolved issue 053 — multi-leg functions had similar service-role fallback bug

## Proposed Solutions

### Option A: Add JWT Auth to POST Handler (Recommended)
- Add the same auth block used for GET requests to all POST operations
- Add `.eq("user_id", user.id)` to the close_position position query
- **Pros:** Minimal change, consistent with GET auth pattern
- **Cons:** None
- **Effort:** Small
- **Risk:** Low

### Option B: Switch POST Operations to User-Auth Client
- Use `getSupabaseClientWithAuth(authHeader)` instead of service-role for user-initiated POSTs
- Reserve service-role for cron-triggered background execution only
- **Pros:** RLS enforced at database level, defense in depth
- **Cons:** Slightly more complex — need to ensure user JWT has sufficient permissions
- **Effort:** Medium
- **Risk:** Low

## Recommended Action

Option A first (immediate fix), then Option B as a hardening step.

## Technical Details

**Affected files:**
- `supabase/functions/paper-trading-executor/index.ts` (lines 970-1055)

**Key code locations:**
- POST handler starts at line 970 (no auth check)
- close_position at lines 974-1006 (no ownership check)
- Service-role client at lines 812-815

## Acceptance Criteria

- [ ] All POST operations return 401 without valid JWT
- [ ] `close_position` verifies the authenticated user owns the position
- [ ] Users cannot close positions belonging to other users
- [ ] Existing GET authentication continues to work

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from plan technical review | Critical security finding from Security Sentinel + Architecture Strategist |

## Resources

- Plan: `docs/plans/2026-03-01-feat-backtest-visuals-paper-trading-pipeline-plan.md`
- Similar resolved issue: `todos/053-resolved-p1-multi-leg-anonymous-fallback-uses-service-role.md`
