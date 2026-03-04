---
status: pending
priority: p2
issue_id: "121"
tags: [code-review, live-trading, database, schema, data-integrity]
dependencies: []
---

# `live_trading_positions.user_id` uses ON DELETE CASCADE but `live_trading_trades.user_id` uses RESTRICT — user deletion creates untracked open broker orders

## Problem Statement

`live_trading_positions.user_id` references `auth.users` with `ON DELETE CASCADE` (migration line 30). `live_trading_trades.user_id` references `auth.users` with `ON DELETE RESTRICT` (migration line 126). Deleting an `auth.users` record cascades and deletes all position rows — including `pending_bracket` or `open` positions with active broker orders that are now untracked. The cascade then fails on the trades FK RESTRICT, creating a half-deleted state: positions gone, trades blocked, open broker orders untracked. For GDPR deletion flows, this would wipe position records without triggering the close workflow.

## Findings

Data Integrity Guardian P2-E.

## Proposed Solutions

**Option A (Recommended):** Change `live_trading_positions.user_id` to `ON DELETE RESTRICT` to match the trades table. Handle GDPR user deletion explicitly through a stored procedure that closes all open positions first (places market close orders and writes trades), then marks the positions as closed, then allows user deletion. Effort: Small migration change + Medium procedure.

**Option B:** Keep CASCADE but add a BEFORE DELETE trigger on `auth.users` that checks for open positions and blocks deletion if any exist. Effort: Small.

## Acceptance Criteria

- [ ] Both `live_trading_positions.user_id` and `live_trading_trades.user_id` use the same ON DELETE behavior
- [ ] Deleting an auth.users row with open broker positions either fails with an error or triggers a graceful close workflow
- [ ] No half-deleted state (positions gone, trades blocked) is possible
