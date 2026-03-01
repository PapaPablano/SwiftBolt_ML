---
status: pending
priority: p2
issue_id: "036"
tags: [code-review, architecture, frontend, api-design]
dependencies: []
---

# 036 — backtestService.ts Bypasses Edge Functions With Direct DB Queries

## Problem Statement
`frontend/src/lib/backtestService.ts` queries `strategy_user_strategies` directly via Supabase JS client rather than calling the `strategies` Edge Function. It also calls the FastAPI Docker service for buy-and-hold data. This creates three separate data paths (Edge Functions, PostgREST, FastAPI) for what should be a single API layer. Business logic in the Edge Function is silently bypassed.

## Findings
- `backtestService.ts` lines 12-52: direct `.from('strategy_user_strategies').select(...)` calls
- `backtestService.ts` line 140: calls `${API_BASE}/api/v1/chart-data/${symbol}/d1` (FastAPI) for buy-and-hold
- `strategies/index.ts` validation (is_active check, name validation) silently bypassed by direct DB
- Three backends per backtest results page: Edge Functions + PostgREST + FastAPI

## Proposed Solutions

### Option A: Typed API client module (Recommended)
Create `frontend/src/api/` directory with typed wrappers around Edge Function calls:
- `strategiesApi.ts` — wraps `strategies` Edge Function
- `backtestApi.ts` — wraps `backtest-strategy` Edge Function
- `chartApi.ts` — wraps `chart` Edge Function (including buy-and-hold data)
- Effort: Medium (3-4 hours)
- Risk: Low

### Option B: Direct Edge Function calls in backtestService
Replace direct DB calls with `supabase.functions.invoke('strategies', ...)`.
- Effort: Small
- Risk: Low

## Recommended Action
Option A (cleaner long-term architecture with a dedicated API layer).

## Technical Details
- **Affected files:** `frontend/src/lib/backtestService.ts`, new `frontend/src/api/` directory

## Acceptance Criteria
- [ ] No direct `.from('strategy_user_strategies')` calls in frontend
- [ ] Buy-and-hold data fetched via chart Edge Function, not FastAPI
- [ ] All strategy access via `strategies` Edge Function
- [ ] TypeScript types match Edge Function response shapes

## Work Log
- 2026-03-01: Identified by architecture-strategist and API contract review agents
