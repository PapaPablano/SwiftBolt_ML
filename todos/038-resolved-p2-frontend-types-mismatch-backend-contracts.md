---
status: pending
priority: p2
issue_id: "038"
tags: [code-review, architecture, typescript, frontend]
dependencies: []
---

# 038 — Frontend TypeScript Types Don't Match Backend Response Contracts

## Problem Statement
Frontend type definitions diverge from actual backend response shapes. `OHLCBar.time: number` (Unix) vs backend `ts: string` (ISO 8601). `ForecastOverlay.price` vs backend `forecast.points[].value`. Two separate Condition type systems exist for the same domain concept. Operator translation (`>` → `above`) is implicit and fragile.

## Findings
- `frontend/src/types/chart.ts`: `OHLCBar.time: number` vs chart function `ts: string`
- `frontend/src/types/chart.ts`: `ForecastOverlay.price` vs chart `forecast.points[].value`
- `frontend/src/types/strategyBacktest.ts`: typed `Condition.operator: Operator`
- `frontend/src/lib/conditionBuilderUtils.ts`: separate Condition discriminated union (same domain)
- `strategies/index.ts`: `operator?: string` (untyped); worker normalizes `>` → `above` implicitly
- `supabase gen types` not being used

## Proposed Solutions

### Option A: Generate types from Supabase schema (Recommended)
Run `supabase gen types typescript` to generate DB types. Create typed Edge Function response interfaces that match actual shapes. Unify the two Condition type systems.
- Effort: Medium (4-6 hours)
- Risk: Low

### Option B: Manual audit and mapping layer
Reconcile each mismatch manually; add conversion functions for ts→time, value→price.
- Effort: Medium
- Risk: Medium (manual, prone to future drift)

## Recommended Action
Option A — automated generation prevents future drift.

## Technical Details
- **Affected files:** `frontend/src/types/`, `frontend/src/lib/conditionBuilderUtils.ts`, `supabase/functions/strategies/index.ts`

## Acceptance Criteria
- [ ] `OHLCBar.time` aligned with backend `ts` field (or mapping documented)
- [ ] `ForecastOverlay` fields match backend `forecast.points[]` shape
- [ ] Single Condition type used throughout frontend
- [ ] Operator normalization explicit and tested
- [ ] `supabase gen types` integrated into dev workflow

## Work Log
- 2026-03-01: Identified by architecture-strategist review agent
