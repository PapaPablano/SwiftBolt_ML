---
status: pending
priority: p2
issue_id: "119"
tags: [code-review, live-trading, financial-accuracy, architecture]
dependencies: []
---

# SL/TP computed from bar close price, bracket orders submitted with stale pre-fill values

## Problem Statement

In `executeStrategy` (live-trading-executor/index.ts lines 729–875), SL and TP prices are calculated from `latestPrice` (the last bar close) before the market order is placed. After the fill is received (`fill.fillPrice`), `entry_price` is updated to the fill price (line 858), but `stop_loss_price` and `take_profit_price` remain at the pre-fill bar-close-based values. The bracket orders at lines 866–874 are placed using these original stale SL/TP values — not recalculated from `fill.fillPrice`. For assets with slippage, the stored SL/TP won't match the actual broker bracket order prices.

## Findings

Architecture Strategist P2-D. The DB's `live_position_levels` CHECK constraint could technically be violated if the fill price deviates significantly from the bar close.

## Proposed Solutions

**Option A (Recommended):** After `pollOrderFill` returns `fill.fillPrice`, recalculate `sl` and `tp` from `fill.fillPrice` using the same percentage-based formula. Update both `stop_loss_price` and `take_profit_price` in the same atomic UPDATE that transitions to `status: 'open'`. Effort: Small — move SL/TP calculation to after fill confirmation.

## Acceptance Criteria

- [ ] SL/TP prices are computed from actual fill price, not estimated bar close
- [ ] DB-stored `stop_loss_price` and `take_profit_price` match the actual bracket order prices
- [ ] The `live_position_levels` CHECK constraint cannot be violated by fill slippage
