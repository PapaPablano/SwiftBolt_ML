---
status: pending
priority: p3
issue_id: "067"
tags: [code-review, architecture, api-contract]
dependencies: []
---

# 067 — Compute Buy-and-Hold Return in Backtest Worker (Remove Direct FastAPI Calls)

## Problem Statement

`backtestService.ts` makes direct calls to the FastAPI backend (lines 219-231, 356-368) for buy-and-hold return data. This violates the documented architecture rule: "Client talks only to Edge Functions." The Phase 2 backend enhancement is a natural time to also compute buy-and-hold return server-side.

## Findings

- **Architecture Strategist:** "The plan does not address this pre-existing violation. Phase 2's backend enhancements would be a natural time to fix it."

## Proposed Solutions

### Option A: Compute in Backtest Worker (Recommended)
- Add `buy_and_hold_return_pct` to worker output
- Calculate: `(last_close - first_close) / first_close * 100`
- Remove direct FastAPI calls from `backtestService.ts`
- **Pros:** Clean architecture, eliminates vendor dependency in frontend
- **Cons:** Slightly more Phase 2 scope
- **Effort:** Small
- **Risk:** Low

## Acceptance Criteria

- [ ] Backtest worker returns `buy_and_hold_return_pct` in result
- [ ] No direct FastAPI calls remain in `backtestService.ts`
- [ ] Buy-and-hold comparison in results panel uses worker-provided value

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from plan technical review | Architecture Strategist finding |
