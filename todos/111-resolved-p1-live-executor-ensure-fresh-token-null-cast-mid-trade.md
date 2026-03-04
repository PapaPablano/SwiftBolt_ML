---
status: pending
priority: p1
issue_id: "111"
tags: [code-review, live-trading, typescript, runtime-error, type-safety]
dependencies: []
---

# `ensureFreshToken` casts `null` as `BrokerToken` after optimistic lock re-read — runtime crash mid-trade

## Problem Statement

In `tradestation-client.ts` lines 289–297, after the optimistic lock update finds another invocation already refreshed the token, the code re-reads with `.single()` and does `return freshToken as BrokerToken`. The Supabase `.single()` returns `{ data: T | null, error: ... }`. If the re-read finds no row (token was revoked between the two reads), `freshToken` is `null`. The `as BrokerToken` cast passes TypeScript compilation but causes a null dereference when the executor accesses `token.access_token` at line 481. This crashes the function mid-execution, potentially leaving a position in a transitional state. Same issue at line 250.

## Findings

TypeScript reviewer P1-2. The file-level `no-explicit-any` suppression (line 1 of tradestation-client.ts) also contributes — the Supabase client is `any`, so return types are `any` and the compiler cannot catch this.

## Proposed Solutions

Option A (Recommended): Add null checks after both `.single()` re-reads. If `freshToken` is null (token was revoked), throw with `{ status: 401 }` error same as the initial not-found path. Effort: Small.

## Acceptance Criteria

- [ ] `ensureFreshToken` checks for null after the optimistic lock re-read
- [ ] Null token after re-read throws an error with `status: 401` rather than returning a null cast
- [ ] The initial token read (line 250) also checks for null before casting
