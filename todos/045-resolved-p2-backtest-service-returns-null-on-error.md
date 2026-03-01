---
status: pending
priority: p2
issue_id: "045"
tags: [code-review, architecture, frontend, error-handling]
dependencies: []
---

# 045 — backtestService Returns null on All Errors (No Type Discrimination)

## Problem Statement
`backtestService.ts` returns `null` on any failure, losing all error context. Frontend cannot distinguish network errors, auth failures, validation errors, or server errors. Error messages are console-logged only — users see nothing when a backtest fails.

## Findings
- `backtestService.ts` lines 97-106: `console.error(...); return null;` on all error paths
- Frontend checks `if (!result)` with no error message to display
- All error types (400, 401, 404, 500, network) collapsed to `null`

## Proposed Solutions
Return a discriminated union:
```typescript
type BacktestResponse =
  | { success: true; jobId: string; status: string }
  | { success: false; error: { code: 'network' | 'auth' | 'validation' | 'server'; message: string } }
```
Update all callers to use `if (!result.success)` and display `result.error.message`.
- Effort: Small (2-3 hours)
- Risk: Low

## Acceptance Criteria
- [ ] All error paths return typed error object, not null
- [ ] Frontend displays appropriate message per error type
- [ ] Network errors distinguished from auth/validation/server errors
- [ ] No silent failures visible only in console

## Work Log
- 2026-03-01: Identified by API contract review agent
