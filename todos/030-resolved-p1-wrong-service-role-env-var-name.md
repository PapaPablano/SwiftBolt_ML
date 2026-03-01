---
status: pending
priority: p1
issue_id: "030"
tags: [code-review, security, configuration, paper-trading]
dependencies: []
---

# 030 — paper-trading-executor Uses Wrong Service Role Key Env Var Name

## Problem Statement
`paper-trading-executor/index.ts` reads `Deno.env.get('SUPABASE_SERVICE_KEY')` but the Supabase platform injects the service role key as `SUPABASE_SERVICE_ROLE_KEY`. The executor silently gets `undefined`, falls back to anon key, and operates with reduced privileges. Position writes may fail or execute with wrong RLS context.

## Findings
- `paper-trading-executor/index.ts`: `Deno.env.get('SUPABASE_SERVICE_KEY')` (wrong name)
- Correct Supabase-injected env var: `SUPABASE_SERVICE_ROLE_KEY`
- Impact: executor Supabase client uses anon key instead of service role key
- RLS policies then apply to executor writes, potentially blocking position creation

## Proposed Solutions

### Option A: Fix the env var name (Recommended)
Change `SUPABASE_SERVICE_KEY` → `SUPABASE_SERVICE_ROLE_KEY`.
- Effort: XSmall (5 minutes)
- Risk: None

### Option B: Add both with fallback
`Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? Deno.env.get('SUPABASE_SERVICE_KEY')`
- Effort: XSmall
- Risk: None

## Recommended Action
Option A — simple typo fix.

## Technical Details
- **Affected files:** `supabase/functions/paper-trading-executor/index.ts`

## Acceptance Criteria
- [ ] Env var name changed to `SUPABASE_SERVICE_ROLE_KEY`
- [ ] Executor Supabase client confirmed to have service role access
- [ ] Paper trading position writes succeed correctly

## Work Log
- 2026-03-01: Identified by security-sentinel review agent (CRIT-03)
