---
status: pending
priority: p1
issue_id: "095"
tags: [code-review, live-trading, agent-native, api-design]
dependencies: []
---

# No `close_position` action for live positions + live config fields silently discarded in handleUpdate

## Problem Statement

Two agent-native parity gaps that prevent programmatic management of live trading:

**Gap 1:** The plan has no `close_position` action for live positions. The paper-trading-executor has `POST { action: "close_position", position_id, exit_price }` for manual closes. The live executor plan has nothing equivalent — users cannot manually exit a live position without going to the TradeStation UI. The orphaned `pending_entry` cleanup mitigation (mentioned in the plan) also has no execution pathway.

**Gap 2:** The strategies `handleUpdate` function in `strategies/index.ts` uses an explicit allow-list pattern (each field individually gated with `if (body.X !== undefined) updates.X = body.X`). Phase 5 adds new live config fields to the `StrategyRow` interface but does not list them in the `handleUpdate` allow-list. Calling `PUT /strategies` with `{ "live_risk_pct": 0.01 }` returns 200 OK but silently discards the field.

## Findings

**Agent-Native Reviewer (P1 finding #3):** "No `close_position` action defined for live positions. Users cannot manually exit a live position except through TradeStation directly. The orphaned `pending_entry` cleanup has no execution pathway."

**Agent-Native Reviewer (P1 finding #4):** "Phase 5 only maps fields into `StrategyRow` interface, the `handleUpdate` additions are not explicit. Current `handleUpdate` only gates on `body.paper_trading_enabled`; new live fields are not listed in the update payload block."

**Reference:** `supabase/functions/strategies/index.ts` lines 160–165 — explicit allow-list pattern.

## Proposed Solutions

### Gap 1 — close_position action:
Add `action: "close_position"` to `live-trading-executor`:
1. Fetch the position and verify `user_id` matches
2. Cancel any outstanding bracket orders via `DELETE /orderexecution/orders/{sl_order_id}` and `DELETE /orderexecution/orders/{tp_order_id}`
3. Place a closing market order via TradeStation
4. Poll for close fill (with timeout)
5. Update position status, insert immutable `live_trading_trades` record

**Critical difference from paper trading:** `exit_price` must come from the actual TradeStation fill, NOT from the request body. A user-supplied exit price would allow self-reported P&L manipulation.

### Gap 2 — handleUpdate allow-list:
In `strategies/index.ts` `handleUpdate`, explicitly add:
```typescript
if (body.live_trading_enabled !== undefined) updates.live_trading_enabled = body.live_trading_enabled;
if (body.live_risk_pct !== undefined) updates.live_risk_pct = body.live_risk_pct;
if (body.live_daily_loss_limit_pct !== undefined) updates.live_daily_loss_limit_pct = body.live_daily_loss_limit_pct;
if (body.live_max_positions !== undefined) updates.live_max_positions = body.live_max_positions;
if (body.live_max_position_pct !== undefined) updates.live_max_position_pct = body.live_max_position_pct;
```

## Technical Details

**Affected files:**
- `supabase/functions/live-trading-executor/index.ts` — add `close_position` action
- `supabase/functions/strategies/index.ts` — add 5 fields to `handleUpdate` allow-list
- `docs/plans/2026-03-03-feat-live-trading-executor-tradestation-plan.md` — Phase 3 and Phase 5

## Acceptance Criteria

- [ ] `POST { action: "close_position", position_id }` closes live position via TradeStation market order
- [ ] `exit_price` comes from actual broker fill — NOT caller-supplied
- [ ] Bracket orders cancelled before placing close order
- [ ] Immutable `live_trading_trades` record inserted on close
- [ ] All 5 live config fields (`live_trading_enabled`, `live_risk_pct`, `live_daily_loss_limit_pct`, `live_max_positions`, `live_max_position_pct`) explicitly listed in `handleUpdate` allow-list
- [ ] `PUT /strategies` with any live config field returns persisted value in subsequent GET

## Work Log

- 2026-03-03: Finding created from Agent-Native Reviewer (P1 findings #3 and #4), consolidated into one todo.
