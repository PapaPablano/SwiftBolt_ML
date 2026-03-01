---
status: pending
priority: p3
issue_id: "057"
tags: [code-review, architecture, ml, edge-functions]
dependencies: []
---

# 057 — walk-forward-optimize Edge Function Duplicates ML Pipeline Walk-Forward CV

## Problem Statement
`supabase/functions/walk-forward-optimize/index.ts` calls FastAPI to run walk-forward optimization. The Python ML pipeline also has its own walk-forward cross-validation at `ml/src/evaluation/walk_forward_cv.py`. It is unclear whether the Edge Function invokes the Python implementation or re-implements it. If they are separate implementations, the methodology may diverge — ML evaluation reports would use different parameters or logic than what the frontend-triggered optimization uses, creating inconsistent accuracy metrics.

## Findings
- `supabase/functions/walk-forward-optimize/index.ts`: calls FastAPI for walk-forward
- `ml/src/evaluation/walk_forward_cv.py`: Python walk-forward CV implementation
- No documentation establishing whether these share the same implementation or are independent
- CLAUDE.md: "Walk-forward validation only (no random splits)" — both must honor this

## Proposed Solutions

### Option A: Verify they share the same FastAPI endpoint
If `walk-forward-optimize` calls `/api/v1/walk-forward` which uses `walk_forward_cv.py` internally, there is no duplication — just verify this.
- Effort: XSmall (read the FastAPI route file)

### Option B: Document the relationship explicitly
Add a comment in `walk-forward-optimize/index.ts` naming the FastAPI endpoint and confirming it delegates to `walk_forward_cv.py`.
- Effort: XSmall
- Risk: None

## Recommended Action
Investigate first (Option A); if confirmed shared, document it (Option B).

## Technical Details
- **Affected files:** `supabase/functions/walk-forward-optimize/index.ts`, `ml/src/evaluation/walk_forward_cv.py`

## Acceptance Criteria
- [ ] Confirmed whether walk-forward-optimize calls the same Python implementation as the ML evaluation job
- [ ] If separate: consolidate or document the intentional divergence
- [ ] Walk-forward methodology documented in CLAUDE.md

## Work Log
- 2026-03-01: Identified by architecture-strategist review agent
