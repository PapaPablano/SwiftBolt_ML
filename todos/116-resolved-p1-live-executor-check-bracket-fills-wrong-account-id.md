---
status: pending
priority: p1
issue_id: "116"
tags: [code-review, live-trading, architecture, data-integrity, broker-api]
dependencies: []
---

# `checkBracketFills` uses single account_id for all positions regardless of per-position account

## Problem Statement

`checkBracketFills` receives the `accountId` derived from the current request's token (equity or futures, depending on the request's symbol), and passes it to `getBatchOrderStatus` for all open bracket positions. However, a user may have bracket positions from a previous invocation that used a different account type (e.g., a futures position opened when `isFutures` was true). Each `live_trading_positions` row has its own `account_id` column, but `checkBracketFills` never reads it. Orders from the "other" account won't appear in `getBatchOrderStatus` results, so bracket fills for mixed-account users are silently missed.

## Findings

Architecture Strategist P1-D. Each position row stores its own `account_id` (schema line 53).

## Proposed Solutions

Option A (Recommended): In `checkBracketFills`, group positions by their `account_id` column and issue one `getBatchOrderStatus` call per distinct account ID, using the appropriate token for each. Effort: Medium.

Option B: As a near-term guard, add a log warning when a position's `account_id` does not match the current invocation's `accountId`, so the miss is at least visible. Effort: Small.

## Acceptance Criteria

- [ ] `checkBracketFills` groups positions by their stored `account_id`
- [ ] Each distinct `account_id` gets its own `getBatchOrderStatus` call
- [ ] Futures and equity bracket positions are both monitored regardless of which account type the current request used
