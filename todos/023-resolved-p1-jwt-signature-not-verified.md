---
status: pending
priority: p1
issue_id: "023"
tags: [code-review, security, authentication, edge-functions]
dependencies: []
---

# 023 — JWT Signature Not Verified in strategies & backtest-strategy

## Problem Statement
`strategies/index.ts` and `backtest-strategy/index.ts` decode the JWT payload with `atob(parts[1])` but never verify the cryptographic signature. Any caller can forge a JWT with an arbitrary `sub` claim and gain access to another user's strategies. Both functions also fall back to a shared demo user ID (`00000000-0000-0000-0000-000000000001`) when no token is provided, creating a shared namespace where unauthenticated users share each other's data.

## Findings
- `supabase/functions/strategies/index.ts` lines 44-51: decodes JWT without signature check
- `supabase/functions/backtest-strategy/index.ts` lines 38-40: demo user fallback on missing auth
- `supabase/functions/strategy-backtest/index.ts`: same pattern
- Only `ts-strategies/index.ts` uses the correct `supabase.auth.getUser(token)` pattern
- RLS policies on `strategy_user_strategies` rely on the user_id passed by the Edge Function — spoofed ID bypasses RLS

## Proposed Solutions

### Option A: Use getUser() (Recommended)
Replace manual JWT decode with `const { data: { user } } = await supabaseWithAuth.auth.getUser()`. Return 401 if user is null. Remove the demo user fallback entirely.
- Pros: Cryptographically verified, consistent with ts-strategies
- Effort: Small (2-4 hours across 3 files)
- Risk: Low

### Option B: Enable verify_jwt at function level
Set `verify_jwt = true` in supabase/config.toml and read `x-supabase-user-id` header.
- Pros: Platform-level verification, no code change needed
- Effort: Small
- Risk: Low

## Recommended Action
Option A — most consistent with existing ts-strategies pattern.

## Technical Details
- **Affected files:** `supabase/functions/strategies/index.ts`, `supabase/functions/backtest-strategy/index.ts`, `supabase/functions/strategy-backtest/index.ts`

## Acceptance Criteria
- [ ] All three functions use `supabase.auth.getUser()` to validate tokens
- [ ] No demo user fallback; return 401 on missing/invalid auth
- [ ] A forged JWT with arbitrary sub claim is rejected with 401
- [ ] Existing authenticated requests continue to work

## Work Log
- 2026-03-01: Identified by architecture-strategist and security-sentinel review agents
