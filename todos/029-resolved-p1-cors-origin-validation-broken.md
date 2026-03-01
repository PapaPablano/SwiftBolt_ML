---
status: pending
priority: p1
issue_id: "029"
tags: [code-review, security, cors, edge-functions]
dependencies: []
---

# 029 — CORS getCorsHeaders Echoes Any Origin Without Allowlist Validation

## Problem Statement
The shared `getCorsHeaders` utility echoes any Origin header back as `Access-Control-Allow-Origin` without checking it against an allowlist. Any website can make credentialed cross-origin requests to financial Edge Functions on behalf of a logged-in user, bypassing browser same-origin protection.

## Findings
- `supabase/functions/_shared/cors.ts`: `getCorsHeaders` echoes origin without allowlist check
- `paper-trading-executor`, `strategies`, `backtest-strategy`, `quotes`, `chart` all use this utility
- With credentialed requests (`withCredentials: true`) the echoed origin enables cross-site reads

## Proposed Solutions

### Option A: Allowlist-based CORS (Recommended)
```typescript
const ALLOWED_ORIGINS = (Deno.env.get('ALLOWED_ORIGINS') ?? '').split(',');
export function getCorsHeaders(req: Request) {
  const origin = req.headers.get('Origin') ?? '';
  const allowed = ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
  return { 'Access-Control-Allow-Origin': allowed, ... };
}
```
- Effort: Small (1 hour)
- Risk: Low

### Option B: Wildcard for read-only, allowlist for credentialed
- Effort: Small-Medium
- Risk: Low

## Recommended Action
Option A.

## Technical Details
- **Affected files:** `supabase/functions/_shared/cors.ts`
- **Env var to add:** `ALLOWED_ORIGINS` (comma-separated)

## Acceptance Criteria
- [ ] getCorsHeaders only echoes origin if it is in the allowlist
- [ ] Non-allowlisted origins receive safe CORS response
- [ ] Local dev origin (localhost:5173) in allowlist
- [ ] All Edge Functions automatically protected via shared utility

## Work Log
- 2026-03-01: Identified by security-sentinel review agent (CRIT-01)
