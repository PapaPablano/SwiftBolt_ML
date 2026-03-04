---
status: pending
priority: p2
issue_id: "118"
tags: [code-review, live-trading, architecture, data-integrity, financial-accuracy]
dependencies: []
---

# Exit signal path writes immutable trade record with estimated fill price, not actual broker fill

## Problem Statement

When an exit signal fires via `closeLivePosition` (lines 1067–1110 of `live-trading-executor/index.ts`), a closing market order is placed but never polled for actual fill confirmation. The trade record is written using `latestPrice` (last bar close) as `exitPrice` rather than the actual broker fill price. Since `live_trading_trades` is immutable (trigger prevents UPDATE), any fill price error in the record is permanent. For futures during volatility or near open/close, the actual fill can differ materially from the last bar close.

## Findings

Architecture Strategist P2-A. The closing order ID is obtained but not used for fill verification before writing the trade record.

## Proposed Solutions

**Option A (Recommended):** After placing the closing market order in `closeLivePosition`, poll `getOrderStatus` with a short deadline (e.g., 5 seconds, 3 retries) to get the actual fill price. Use that price for the trade record. If the poll times out, write the record with the estimated price and a `fill_price_unconfirmed: true` flag. Effort: Medium.

**Option B:** Write the trade record with the estimated price but add a `fill_price_unconfirmed` boolean column to `live_trading_trades` that allows a reconciliation job to update it. Effort: Medium — requires schema change.

## Acceptance Criteria

- [ ] Exit signal path polls for actual broker fill price before writing the trade record
- [ ] If poll times out, record is flagged as having an unconfirmed fill price
- [ ] The actual fill price, not estimated price, is used when available
