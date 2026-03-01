---
status: pending
priority: p2
issue_id: "037"
tags: [code-review, architecture, api-design, edge-functions]
dependencies: ["028"]
---

# 037 — Edge Function Response Envelopes Are Inconsistent

## Problem Statement
Each Edge Function wraps responses differently. Frontend must defensively handle `.job_id` vs `.job.id`, `.error` vs `.error.message`, raw data vs `{ strategy: data }` vs `{ data: data }` depending on which function was called. Silent bugs occur when the wrong envelope shape is assumed.

## Findings
- `backtest-strategy` success: `{ job_id, status, created_at }` (flat)
- `strategy-backtest` success: `{ job: { id, status, created_at } }` (nested)
- `strategies` success: `{ strategy: data }` or `{ strategies: data[] }` (wrapped)
- `ts-strategies` success: raw data object (no envelope)
- Error shapes: `{ error }`, `{ error, details, code }`, `{ error, hint }` across different functions

## Proposed Solutions

### Option A: Standardize on one envelope pattern (Recommended for v2)
Define in `_shared/response.ts`:
```typescript
export const ok = (data: unknown) => new Response(JSON.stringify({ data }), ...)
export const err = (msg: string, code?: string) => new Response(JSON.stringify({ error: msg, code }), ...)
```
Apply uniformly. Update all callers simultaneously.
- Effort: Large
- Risk: Medium (must update frontend callers)

### Option B: Frontend adapter layer (Recommended now)
Create `frontend/src/api/` module that knows each function's envelope shape and normalizes responses for the app.
- Effort: Medium
- Risk: Low (no backend changes)

## Recommended Action
Option B immediately; Option A with next major API version.

## Technical Details
- **Affected files:** All Edge Functions (Option A) or `frontend/src/api/` (Option B)

## Acceptance Criteria
- [ ] Frontend has single place to unwrap each function's response
- [ ] Consistent error handling across all function calls
- [ ] TypeScript type safety for all response shapes

## Work Log
- 2026-03-01: Identified by architecture-strategist review agent
