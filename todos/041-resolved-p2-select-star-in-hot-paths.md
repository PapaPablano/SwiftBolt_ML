---
status: pending
priority: p2
issue_id: "041"
tags: [code-review, performance, edge-functions]
dependencies: []
---

# 041 — SELECT * Used in Hot Paths (Executor and Multi-Leg Detail)

## Problem Statement
`paper-trading-executor` and `multi-leg-detail` use `SELECT *` on wide-schema tables. The executor fetches 100 OHLC bars including columns it never uses (provider, data_status, is_forecast, adjusted_close). Each unnecessary column inflates the wire payload and serialization time on the most frequent execution path.

## Findings
- `paper-trading-executor/index.ts` line 568: `select("*")` on ohlc_bars_v2 (100 rows) — only needs ts, open, high, low, close, volume
- `paper-trading-executor/index.ts` lines 536, 349: `select("*")` on strategy_user_strategies, paper_trading_positions
- `multi-leg-detail/index.ts` lines 77, 96, 108, 124: `select("*")` on 4 tables

## Proposed Solutions
Replace with explicit column selects:
- `ohlc_bars_v2`: `select("ts, open, high, low, close, volume")`
- `strategy_user_strategies`: `select("id, name, config, is_active, paper_trading_enabled")`
- `paper_trading_positions`: `select("id, symbol, direction, entry_price, quantity, status, stop_loss, take_profit, user_id")`
- Effort: XSmall (30 minutes)
- Risk: None

## Acceptance Criteria
- [ ] No `select("*")` in executor or multi-leg-detail
- [ ] Only needed columns fetched
- [ ] No functional regression

## Work Log
- 2026-03-01: Identified by performance-oracle review agent. Note: also flagged in existing todo #012 for general SELECT * — this is the hot-path specific instance.
