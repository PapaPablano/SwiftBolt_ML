---
status: pending
priority: p2
issue_id: "102"
tags: [code-review, live-trading, agent-native, api-design]
dependencies: ["093"]
---

# Missing GET endpoints — positions, trades, broker status, strategies list omits live fields

## Problem Statement

Phase 6 describes a `LiveTradingDashboard` but no GET routes are designed for it. No API returns open live positions, trade history, or broker connection status. The strategies list GET omits the new live config fields. This means the dashboard has no data source, agents cannot query live trading state, and the `live_trading_enabled` toggle state is invisible to programmatic callers.

## Findings

**Agent-Native Reviewer (P2 #5):** "No GET route designed anywhere in the plan — no action on live-trading-executor, no separate live-positions Edge Function."

**Agent-Native Reviewer (P2 #6):** "Phase 6 states the toggle 'is disabled unless broker_tokens row exists.' The UI needs to know whether a row exists. No GET endpoint for checking broker connection status is defined."

**Agent-Native Reviewer (P2 #7):** "`handleGet` in `strategies/index.ts` uses explicit column list: `'id, name, is_active, paper_trading_enabled, created_at, updated_at'`. Phase 5 does not update this SELECT list. `GET /strategies` would never return `live_trading_enabled`."

## Proposed Solutions

### Fix 1 — GET routes on live-trading-executor (mirror paper executor):
Add to Phase 3 (or Phase 6):
- `GET ?action=positions` — open live positions for the authenticated user
- `GET ?action=trades` — trade history with P&L
- `GET ?action=summary` — performance metrics summary
- `GET ?action=broker_status` — `{ connected: bool, provider, expires_at, account_id }` (no tokens)

The paper executor's GET handler (lines 905–1035) is the exact template to follow.

### Fix 2 — Update strategies handleGet SELECT list:
In `strategies/index.ts` `handleGet`, add to the column list:
```typescript
"id, name, is_active, paper_trading_enabled, live_trading_enabled, live_risk_pct, live_daily_loss_limit_pct, live_max_positions, live_max_position_pct, live_trading_paused, created_at, updated_at"
```

## Technical Details

**Affected files:**
- `supabase/functions/live-trading-executor/index.ts` — add GET action handlers
- `supabase/functions/strategies/index.ts` — update handleGet SELECT list

## Acceptance Criteria

- [ ] `GET ?action=positions` returns open live positions with status, P&L estimate, entry details
- [ ] `GET ?action=trades` returns closed trades with actual P&L
- [ ] `GET ?action=summary` returns total P&L, win rate, trade count for the day/period
- [ ] `GET ?action=broker_status` returns connection status without exposing tokens
- [ ] `GET /strategies` response includes all 5 live config fields and `live_trading_paused`
- [ ] All GET endpoints respect JWT auth (only the authenticated user's data)

## Work Log

- 2026-03-03: Finding created from Agent-Native Reviewer (P2 #5, #6, #7).
