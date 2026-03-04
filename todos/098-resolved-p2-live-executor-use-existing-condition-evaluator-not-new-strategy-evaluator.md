---
status: pending
priority: p2
issue_id: "098"
tags: [code-review, live-trading, architecture, duplication, refactoring]
dependencies: []
---

# Phase 2 proposes creating `_shared/strategy-evaluator.ts` — use existing `_shared/condition-evaluator.ts` instead

## Problem Statement

The plan's Phase 2a proposes extracting condition evaluation to a new `_shared/strategy-evaluator.ts`. However, `_shared/condition-evaluator.ts` already exists and is a more complete implementation than the inline version in `paper-trading-executor/index.ts`. It has a proper `IndicatorCache` class, `evaluateConditionTree` for AND/OR tree evaluation, and a `Condition` discriminated union. Creating a third implementation (after inline paper executor + proposed strategy-evaluator) adds duplication without benefit.

## Findings

**Architecture Strategist (P2):** "`_shared/condition-evaluator.ts` already exists and is a more complete implementation than the inline version in `paper-trading-executor/index.ts`. Creating `_shared/strategy-evaluator.ts` would be a second shared evaluator module that is functionally overlapping."

**TypeScript Reviewer (P2-6):** "The plan's `Condition` interface re-declares optional fields for everything, regressing from the discriminated union in `_shared/condition-evaluator.ts`. The plan should import the existing `Condition` from `_shared/condition-evaluator.ts` directly."

**TypeScript Reviewer (P2-3):** "New `Bar` definition in `strategy-evaluator.ts` collides with two existing ones; `time` type diverges (`string` vs `number | string`)."

## Proposed Solutions

### Option A: Delete Phase 2a from the plan — use existing condition-evaluator.ts (Recommended)
Update Phase 2a to: "update `paper-trading-executor/index.ts` to import from `_shared/condition-evaluator.ts` (replacing its inline implementations). Then have `live-trading-executor` import the same module."

This eliminates the duplication that already exists in the paper executor AND avoids introducing a third implementation.

**Pros:** One source of truth, uses the better implementation, eliminates paper executor duplication
**Cons:** Requires a non-trivial refactor of `paper-trading-executor` (replacing inline evaluator functions)
**Effort:** Medium (but the right work)
**Risk:** Low for live executor, requires careful testing for paper executor

### Option B: Create strategy-evaluator.ts as a thin re-export of condition-evaluator.ts
`_shared/strategy-evaluator.ts` just re-exports from `_shared/condition-evaluator.ts`.

**Pros:** Plan structure preserved, named import path matches plan
**Cons:** Unnecessary indirection, two files with the same content
**Effort:** Tiny
**Risk:** Low

## Recommended Action

Option A. Update Phase 2a in the plan to explicitly import from `_shared/condition-evaluator.ts` for both executors. The paper executor refactor (replacing inline `evaluateConditionList`, `computeRSI`, etc. with imports) must be deployed atomically with the paper executor re-deploy.

## Technical Details

**Affected files:**
- `supabase/functions/paper-trading-executor/index.ts` — replace inline evaluator with `_shared/condition-evaluator.ts` imports
- `supabase/functions/live-trading-executor/index.ts` — import from `_shared/condition-evaluator.ts`
- `docs/plans/2026-03-03-feat-live-trading-executor-tradestation-plan.md` — update Phase 2a

## Acceptance Criteria

- [ ] No new `_shared/strategy-evaluator.ts` file created
- [ ] `live-trading-executor` imports `evaluateConditionTree`, `IndicatorCache`, `Condition` from `_shared/condition-evaluator.ts`
- [ ] `paper-trading-executor` imports from `_shared/condition-evaluator.ts` (replacing inline duplicates)
- [ ] No new `Bar` type definition — use existing from `_shared/condition-evaluator.ts`
- [ ] `deno lint` passes on both executors after refactor

## Work Log

- 2026-03-03: Finding created from Architecture Strategist (P2) and TypeScript Reviewer (P2-3, P2-6).
