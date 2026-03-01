---
status: pending
priority: p1
issue_id: "053"
tags: [code-review, security, authentication, multi-leg, edge-functions]
dependencies: []
---

# 053 — Multi-Leg Functions Fall Back to Service Role Client When Auth Fails

## Problem Statement
Seven multi-leg Edge Functions (`multi-leg-create`, `multi-leg-delete`, `multi-leg-update`, `multi-leg-close-leg`, `multi-leg-close-strategy`, `multi-leg-detail`, `multi-leg-list`) silently switch to a service role Supabase client when authentication fails, and assign a null UUID (`000...000`) as the owner. This bypasses all RLS policies on options strategy data — unauthenticated callers can create, read, update, and delete real options positions.

## Findings
- `multi-leg-create/index.ts` lines 76-84:
  ```typescript
  if (userError || !user) {
    // For development/testing: use service role client which bypasses RLS
    supabase = getSupabaseClient();          // Bypasses ALL RLS
    userId = "00000000-0000-0000-0000-000000000000"; // Null UUID
  }
  ```
- Same pattern in all 7 multi-leg functions
- These functions manage real financial data: options legs, strikes, premiums, Greeks
- The code comment "For development/testing" indicates a debug artifact left in production

## Proposed Solutions

### Option A: Return 401 on auth failure (Recommended)
Remove the anonymous fallback entirely. Return 401 with `{ error: 'Authentication required' }` when `getUser()` fails.
- Effort: Small (1-2 hours across 7 functions)
- Risk: Low (unauthenticated callers currently shouldn't be using these endpoints)

### Option B: Gate behind feature flag
`if (Deno.env.get('ALLOW_ANON_DEMO') === 'true')` before the fallback.
- Effort: Small
- Risk: Low (but still keeps dead code in production)

## Recommended Action
Option A — no legitimate use case for unauthenticated access to financial position management.

## Technical Details
- **Affected files:** All 7 `supabase/functions/multi-leg-*/index.ts` files

## Acceptance Criteria
- [ ] All multi-leg functions return 401 when authentication is missing or invalid
- [ ] No service role fallback for unauthenticated callers
- [ ] No null UUID owner assignment
- [ ] Authenticated requests continue to work normally

## Work Log
- 2026-03-01: Identified by security-sentinel review agent (HIGH-02)
