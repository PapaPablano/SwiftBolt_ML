---
status: pending
priority: p2
issue_id: "134"
tags: [code-review, live-trading, agent-native, api-contract]
dependencies: []
---

# Paused strategy returns generic `no_action` — callers cannot distinguish from "no signal"

## Problem Statement

When a strategy has `live_trading_paused: true`, the executor logs a console warning and returns `{ success: true, action: "no_action" }` (lines 590-597 of `live-trading-executor/index.ts`). This response is identical to "conditions not met — no entry signal." An agent monitoring execution health cannot distinguish "strategy is configured but paused" from "strategy ran and found no trade opportunity." A user troubleshooting why their strategy isn't trading would see only `no_action` with no indication the strategy is paused.

## Findings

Agent-Native Reviewer, Warning #6.

## Proposed Solutions

Option A (Recommended): Return a distinct `action: "strategy_paused"` value with the `strategy_id` when the paused check fires. This requires no schema change — just changing the string returned. Update the `action` type documentation to include `strategy_paused`. Effort: Small.

## Acceptance Criteria

- [ ] A paused strategy returns `action: "strategy_paused"` with `strategy_id` included
- [ ] The new action value is distinct from `no_action`
- [ ] Frontend components that display execution results handle `strategy_paused` appropriately
