---
status: pending
priority: p1
issue_id: "024"
tags: [code-review, architecture, paper-trading, frontend]
dependencies: ["025"]
---

# 024 — PaperTradingDashboard Uses Hardcoded Mock Data

## Problem Statement
`frontend/src/components/PaperTradingDashboard.tsx` renders positions, trades, and performance metrics from hardcoded mock data arrays rather than live API calls. The `paper-trading-executor` Edge Function requires the service role key, making it inaccessible from browser-side code. There are no public endpoints to list positions or closed trades.

## Findings
- PaperTradingDashboard.tsx: position list, trade history, and metrics all hardcoded
- `paper-trading-executor/index.ts` reads `SUPABASE_SERVICE_ROLE_KEY` — not callable with anon key
- No `GET /paper-trading-positions` endpoint exists
- No `GET /paper-trading-trades` endpoint exists
- The executor writes to `paper_trading_positions` and `paper_trading_trades` tables but there is no read path for the frontend

## Proposed Solutions

### Option A: Add Read Handlers to paper-trading-executor (Recommended)
Add `action=list_positions` and `action=list_trades` GET handlers to the executor using the authenticated user's Supabase client.
- Effort: Medium (4-6 hours)
- Risk: Low

### Option B: New Dedicated Read Functions
Create `paper-trading-positions` and `paper-trading-trades` Edge Functions as read-only GET endpoints with `verify_jwt = true`.
- Effort: Medium
- Risk: Low

### Option C: Direct RLS-Protected PostgREST Queries
Enable anon/authenticated SELECT policies on the tables and query directly from frontend.
- Effort: Small
- Risk: Medium (bypasses business logic layer)

## Recommended Action
Option A — minimizes function proliferation while keeping business logic centralized.

## Technical Details
- **Affected files:** `supabase/functions/paper-trading-executor/index.ts`, `frontend/src/components/PaperTradingDashboard.tsx`
- **Tables:** `paper_trading_positions`, `paper_trading_trades`

## Acceptance Criteria
- [ ] PaperTradingDashboard displays live position data from API
- [ ] PaperTradingDashboard displays live trade history from API
- [ ] Performance metrics computed from real data
- [ ] All data filtered to authenticated user
- [ ] Pagination implemented (max 50 results per page)

## Work Log
- 2026-03-01: Identified by API contract review agent
