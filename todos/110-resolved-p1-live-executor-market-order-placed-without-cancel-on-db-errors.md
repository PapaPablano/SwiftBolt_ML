---
status: pending
priority: p1
issue_id: "110"
tags: [code-review, live-trading, typescript, financial-safety, error-handling]
dependencies: []
---

# Market order placed at broker but not cancelled on non-duplicate DB insert failures

## Problem Statement

In `executeStrategy` (lines 775–829 of `live-trading-executor/index.ts`), the sequence is: (1) `placeMarketOrder` — order goes live at broker, (2) DB INSERT into `live_trading_positions`. The cancel call at line 819 only covers the `23505` duplicate key case (concurrent invocation). For all other `insertError` codes (network timeout, constraint violation, etc.), the code returns `{ success: false, error: { type: "database_error" } }` WITHOUT cancelling the already-placed market order. The position is now live at TradeStation with no DB record and no tracking.

## Findings

TypeScript reviewer P1-3. This is a financial safety issue — a live open position with no DB record cannot be monitored, SL/TP'd, or closed through the app.

## Proposed Solutions

Option A (Recommended): Wrap the cancel call so it fires for ALL `insertError` cases, not just `23505`. The 23505 path correctly returns `position_locked`; all other error paths should cancel the order and return `database_error`. Effort: Small — just move the cancel call outside the `23505`-only branch.

## Acceptance Criteria

- [ ] `cancelOrder` is called for every `insertError` case, not just `23505`
- [ ] The 23505 path still returns `position_locked` result
- [ ] All non-23505 DB errors return `database_error` result after cancelling the broker order
