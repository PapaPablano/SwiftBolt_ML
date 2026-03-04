---
status: pending
priority: p1
issue_id: "108"
tags: [code-review, live-trading, architecture, financial-safety, state-machine]
dependencies: []
---

# No recovery path for positions stuck in `pending_bracket` after executor timeout

## Problem Statement

If the Edge Function crashes or hits the 60-second wall clock limit after the entry market order fills but before `placeBracketOrders` completes, the position is left in `pending_bracket` state with `broker_sl_order_id = null` and `broker_tp_order_id = null` in the DB. The executor has no recovery logic — every subsequent invocation returns `no_action` for that position (guard at line 643–651 of `live-trading-executor/index.ts`). Meanwhile the broker has an open position with real market risk and no SL/TP protection. There is no age-based timeout, recovery scan, or alerting path.

## Findings

Architecture Strategist P1-A. The `checkBracketFills` function only processes positions with a non-null `broker_sl_order_id`, so positions stuck mid-bracket are also invisible to that path. `pending_close` exists as a schema status but the executor never transitions to it, meaning there is no graceful close path either.

## Proposed Solutions

Option A (Recommended): Add a stuck-position recovery scanner to `executeLiveTradingCycle` that runs before the per-strategy loop. Any position in `pending_entry` or `pending_bracket` with `order_submitted_at` older than 2 minutes is re-polled against TradeStation. If the entry fill is found, advance to the bracket placement flow. If no fill is found or the order is cancelled, mark the position `cancelled` and attempt a closing market order. Effort: Medium.

Option B: Add a monitoring alert (DB query) for `pending_bracket` positions older than 5 minutes, paired with a manual-close action endpoint. Doesn't fix automatically but provides visibility. Effort: Small.

## Acceptance Criteria

- [ ] A position in `pending_bracket` with `order_submitted_at > 2 minutes` is automatically detected and either completed or cancelled
- [ ] Stuck positions no longer block new strategy entries indefinitely
- [ ] A monitoring query exists for `pending_bracket` positions older than 5 minutes
- [ ] The recovery path handles the case where the entry order was never filled vs. where it was filled but bracket wasn't placed
