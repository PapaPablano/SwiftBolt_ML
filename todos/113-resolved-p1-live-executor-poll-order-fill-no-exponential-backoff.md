---
status: pending
priority: p1
issue_id: "113"
tags: [code-review, live-trading, performance, reliability, broker-api]
dependencies: []
---

# `pollOrderFill` uses fixed 1-second polling — no exponential backoff, 15-second max wall time

## Problem Statement

The fill poll loop in `live-trading-executor/index.ts` polls at a fixed 1-second interval for up to 15 iterations (`POLL_TIMEOUT_MS = 15_000`), consuming exactly 15 seconds of the 60-second Edge Function budget. Market orders fill in milliseconds in normal conditions, but the first poll fires after a full 1-second wait regardless. Under rate limiting or broker latency, 15 calls at 1-second intervals with no backoff creates unnecessary API pressure and wastes execution budget. TradeStation may also rate-limit the order status endpoint at this polling cadence.

## Findings

Performance Oracle P1-A. The current approach makes 15 API calls over 15 seconds maximum. With exponential backoff starting at 200ms, the fill would be confirmed in 200ms under normal conditions (99% of fills) while the max is still bounded.

## Proposed Solutions

Option A (Recommended): Replace fixed 1-second interval with exponential backoff starting at 200ms (200ms, 400ms, 800ms, 1600ms, 3200ms...), capped at 5000ms per iteration. Keep the overall 15-second timeout. Effort: Small.

## Acceptance Criteria

- [ ] `pollOrderFill` uses exponential backoff starting at 200ms
- [ ] Maximum per-poll wait is capped (e.g., 5000ms)
- [ ] Overall timeout is preserved (15 seconds)
- [ ] First poll fires at 200ms delay, not 1000ms
