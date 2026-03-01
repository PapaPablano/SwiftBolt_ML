---
status: pending
priority: p2
issue_id: "031"
tags: [code-review, performance, frontend, hooks]
dependencies: []
---

# 031 — useIndicators and usePivotLevels Both Poll the Same Endpoint

## Problem Statement
`ChartWithIndicators.tsx` mounts both `useIndicators` and `usePivotLevels`, each independently fetching the same `/api/v1/support-resistance` endpoint every 30 seconds. This doubles network load and FastAPI compute load for zero information gain — the endpoint already returns both datasets in one response.

## Findings
- `frontend/src/hooks/useIndicators.ts` line 68: fetches `/api/v1/support-resistance?symbol=...&timeframe=...`
- `frontend/src/hooks/usePivotLevels.ts` line 84-86: fetches identical URL
- Both poll every 30 seconds independently
- S/R endpoint returns both pivot levels and S/R zone data in one response

## Proposed Solutions

### Option A: Shared hook returning both datasets (Recommended)
Create `useSupportResistance(symbol, timeframe)` that fetches once and returns `{ srData, pivotLevels }`. Both existing hooks become consumers of this shared hook.
- Effort: Small (2 hours)
- Risk: Low

### Option B: SWR/React Query deduplication
Use a caching library that deduplicates identical in-flight requests.
- Effort: Medium (adds dependency)
- Risk: Low

## Recommended Action
Option A.

## Technical Details
- **Affected files:** `frontend/src/hooks/useIndicators.ts`, `frontend/src/hooks/usePivotLevels.ts`, `frontend/src/components/ChartWithIndicators.tsx`

## Acceptance Criteria
- [ ] Only one HTTP request to `/api/v1/support-resistance` per chart view per 30s poll
- [ ] Both SR zones and pivot levels still displayed correctly
- [ ] Single shared hook or deduplication in place

## Work Log
- 2026-03-01: Identified by performance-oracle review agent (highest-leverage frontend fix)
