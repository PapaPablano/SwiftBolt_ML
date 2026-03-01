---
status: pending
priority: p2
issue_id: "043"
tags: [code-review, security, input-validation, edge-functions]
dependencies: []
---

# 043 — symbols-search Missing Max Length and Character Allowlist on q Param

## Problem Statement
`symbols-search/index.ts` passes the `q` query parameter directly to `.ilike()` with no length cap or character allowlist. While PostgREST parameterizes the value (no SQL injection), an arbitrarily long query string causes unnecessary DB load, and `%` and `_` characters in user input act as LIKE wildcards altering query behavior.

## Findings
- `symbols-search/index.ts`: `q` passed to `.ilike('ticker', \`%${q}%\`)` with no validation
- No max length check (could send 10,000-char string)
- `%` and `_` in user input behave as LIKE wildcards, enabling unintended wildcard queries

## Proposed Solutions
Add validation at handler start:
```typescript
const q = url.searchParams.get('q') ?? '';
if (q.length > 20) return errorResponse('Query too long', 400);
if (!/^[A-Z0-9. -]{1,20}$/i.test(q)) return errorResponse('Invalid characters', 400);
```
- Effort: XSmall (30 minutes)
- Risk: None

## Acceptance Criteria
- [ ] q param enforced max 20 characters
- [ ] q param only allows alphanumeric, dot, space, hyphen
- [ ] Invalid q returns 400 with clear error message
- [ ] Valid ticker searches unaffected

## Work Log
- 2026-03-01: Identified by security-sentinel review agent (HIGH-03)
