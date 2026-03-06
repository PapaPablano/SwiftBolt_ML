---
status: ready
priority: p2
issue_id: "061"
tags: [code-review, architecture, data-model, plan-amendment]
dependencies: []
---

# 061 — Three-Way Condition Format Mismatch Across Frontend/Worker/Executor

## Problem Statement

The plan identifies a strategy config translation gap between frontend and executor, but there are actually three different condition formats:

| Field | Frontend (`StrategyConfig`) | Backtest Worker | Paper Executor |
|---|---|---|---|
| Indicator key | `type: 'rsi'` | `name: 'rsi'` | `indicator: 'RSI'` |
| Operator | `'>' / '<' / 'cross_up'` | `'above' / 'below' / 'equals'` | `'>' / '<' / 'cross_up'` |
| ID | none | none | `id: string` |
| Logical grouping | implicit AND | implicit AND | `logicalOp: 'AND' \| 'OR'` |

The plan's `strategyTranslator.ts` in Phase 5 only addresses frontend→executor. The worker already has `normalizeConfig` (lines 44-58) for frontend→worker. Having translation logic scattered across three locations is a maintenance risk.

## Findings

- **Architecture Strategist:** "The most significant architectural concern in the plan" — promote translator to Phase 2 as foundational data contract
- **Simplicity Reviewer:** "Two config formats is a design smell — unify or keep translator minimal"

## Proposed Solutions

### Option A: Promote strategyTranslator to Phase 2 as Canonical Translator (Recommended)
- Move translation logic from Phase 5 to Phase 2
- Create a single `strategyTranslator.ts` that handles all three format conversions
- Remove inline `normalizeConfig` from the backtest worker, use shared translator
- **Pros:** Single source of truth, tested early, de-risks Phase 5
- **Cons:** More Phase 2 scope
- **Effort:** Medium
- **Risk:** Low

### Option B: Keep Translation Scattered, Add Fallback Defaults
- Keep `normalizeConfig` in worker, add `strategyTranslator.ts` in Phase 5
- Add fallback defaults in `backtestService.ts` when fields are absent
- **Pros:** Minimal plan change
- **Cons:** Two translation locations, potential for drift
- **Effort:** Small
- **Risk:** Medium (maintenance)

## Technical Details

**Affected files:**
- `supabase/functions/strategy-backtest-worker/index.ts` (lines 28-58 — Condition type + normalizeConfig)
- `supabase/functions/paper-trading-executor/index.ts` (lines 117-127 — Condition type)
- `frontend/src/types/strategyBacktest.ts` (EntryExitCondition type)
- `frontend/src/lib/strategyTranslator.ts` (proposed)

## Acceptance Criteria

- [ ] Single canonical location for condition format translation
- [ ] All three consumers use the same translation logic
- [ ] Fallback defaults for `direction` and `closeReason` when absent (FastAPI preset path)
- [ ] Unit tests for all format conversions

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from plan technical review | Architecture Strategist identified three-way mismatch |
