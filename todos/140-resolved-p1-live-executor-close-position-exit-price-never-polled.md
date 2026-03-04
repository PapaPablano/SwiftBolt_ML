---
status: pending
priority: p1
issue_id: "140"
tags: [code-review, live-trading, financial-accuracy, data-integrity]
dependencies: []
---

# `closeLivePosition` records `current_price` as exit price without polling actual fill

## Problem Statement

`/Users/ericpeterson/SwiftBolt_ML/supabase/functions/live-trading-executor/index.ts` lines 1305–1306: for manual close, `latestPrice = pos.current_price ?? pos.entry_price` is used as the recorded `exit_price` in `live_trading_trades`. However a market order will fill at a different price — potentially significantly different in fast-moving or illiquid markets. The actual fill price is never polled after a manual close market order (unlike the entry flow which calls `pollOrderFill` and uses the confirmed fill price). This means:

1. The `exit_price` stored in the database is inaccurate
2. The P&L recorded in `live_trading_trades` is wrong
3. Performance analytics (win rate, total P&L) are based on incorrect data

## Findings

**Code Simplicity Reviewer (P3-8):** "This is a correctness issue, not just complexity — the fix is to poll after the close order, or at minimum note this as a known approximation."

## Proposed Solutions

**Option A (Recommended):** After placing the close market order, poll `pollOrderFill` exactly as the entry flow does, then use the confirmed fill price for recording. This mirrors the existing pattern already established in `executeStrategy`.

**Option B:** Record the `current_price` as a "requested close price" field and mark the exit_price as pending, with a separate reconciliation job that backfills confirmed fill prices from the broker API.

**Option C:** Add an explicit comment in code and in the `live_trading_trades` schema documentation that `exit_price` for manual closes is an approximation (not a confirmed fill). This is a documentation-only fix — no data accuracy improvement.

## Acceptance Criteria

- [ ] `closeLivePosition` polls for actual fill price after market order placement
- [ ] `exit_price` recorded in `live_trading_trades` matches broker-confirmed fill price
- [ ] P&L calculation uses actual fill prices for both entry and exit

## Work Log

- 2026-03-03: Finding from code-simplicity-reviewer.
