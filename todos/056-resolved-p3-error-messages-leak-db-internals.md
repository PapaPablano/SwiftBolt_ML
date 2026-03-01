---
status: pending
priority: p3
issue_id: "056"
tags: [code-review, security, error-handling, edge-functions]
dependencies: []
---

# 056 — Raw Database Error Messages Returned to Callers

## Problem Statement
Multiple Edge Functions pass raw Supabase/PostgreSQL error messages directly to callers via `errorResponse(error.message)`. PostgreSQL error messages can reveal table names, column names, constraint names, index names, and RPC function signatures — useful information for an attacker mapping the schema.

## Findings
- `strategies/index.ts` line 120: `return errorResponse(error.message);`
- `strategy-backtest/index.ts` line 176: `return errorResponse(error.message);`
- Similar patterns in `backtest-strategy`, `multi-leg-create`, `multi-leg-update`
- Example leak: `"duplicate key value violates unique constraint \"strategy_user_strategies_user_id_name_key\""` reveals the constraint name and involved columns

## Proposed Solutions
Log internally, return opaque message:
```typescript
// Before
return errorResponse(error.message);

// After
console.error('[strategies] DB error:', error.message, error.details);
return errorResponse('An internal error occurred', 500);
```
Reserve detailed errors for 4xx (validation) responses where the message helps the caller fix their request.
- Effort: Small (1-2 hours across all affected files)
- Risk: None

## Acceptance Criteria
- [ ] No raw Postgres/PostgREST error messages in 5xx responses
- [ ] Internal errors logged server-side with full detail
- [ ] 4xx validation errors still provide helpful messages to callers
- [ ] Error codes (not messages) can be returned for programmatic handling

## Work Log
- 2026-03-01: Identified by security-sentinel review agent (MED-03)
