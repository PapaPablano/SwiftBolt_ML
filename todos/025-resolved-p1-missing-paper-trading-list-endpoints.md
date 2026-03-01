---
status: pending
priority: p1
issue_id: "025"
tags: [code-review, architecture, paper-trading, api-gap]
dependencies: []
---

# 025 — Missing GET Endpoints for Paper Trading Positions and Trades

## Problem Statement
The paper trading executor creates and closes positions and records trades, but there is no API surface to read this data back. `paper_trading_positions` and `paper_trading_trades` tables are write-only from the frontend's perspective.

## Findings
- No GET endpoint for listing open positions (`paper_trading_positions WHERE status='open'`)
- No GET endpoint for listing closed trades (`paper_trading_trades`)
- `paper-trading-executor` accepts only POST (execution actions)
- Dashboard requires: open positions with unrealized P&L, closed trades with realized P&L, performance summary metrics

## Proposed Solutions

### Option A: Extend paper-trading-executor with GET handlers (Recommended)
- `GET ?action=positions` → paginated list of open positions with current_price
- `GET ?action=trades` → paginated list of closed trades with P&L
- `GET ?action=summary` → aggregated metrics (win rate, total P&L, drawdown)
- Effort: Medium (4-6 hours)
- Risk: Low

### Option B: Separate read function
Create `paper-trading-read/index.ts` with GET endpoints.
- Effort: Medium
- Risk: Low (adds another function)

## Recommended Action
Option A (extend executor to avoid function proliferation).

## Technical Details
- **Affected files:** `supabase/functions/paper-trading-executor/index.ts`
- **Tables:** `paper_trading_positions`, `paper_trading_trades`

## Acceptance Criteria
- [ ] GET positions endpoint returns user's open positions with current P&L
- [ ] GET trades endpoint returns user's closed trades with realized P&L
- [ ] GET summary endpoint returns win rate, total return, max drawdown
- [ ] All endpoints require valid JWT and filter by authenticated user_id
- [ ] Pagination with limit/offset params

## Work Log
- 2026-03-01: Identified by API contract review agent
