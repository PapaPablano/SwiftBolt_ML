---
status: pending
priority: p2
issue_id: "099"
tags: [code-review, live-trading, performance, rate-limiting, database]
dependencies: []
---

# Rate limit budget exceeded by polling + semaphore too low + missing DB indexes

## Problem Statement

Three performance issues that compound each other:

1. **Poll rate limit:** 5 concurrent strategies × 30 polls at 1 req/sec × 2 orders (SL+TP) = 300 requests in 30s = 60% of TradeStation's 250 req/5min window consumed in a single cycle.

2. **Semaphore too small:** The plan copies `MAX_CONCURRENT = 5` from paper executor. But the paper executor's operations take ~100ms each. The live executor's fill poll holds a semaphore slot for up to 30 seconds — 5 slots × 30s = 150s of total blocked time, severely limiting throughput for multi-symbol strategies.

3. **Missing indexes:** `live_trading_trades(user_id, exit_time)` has no index, making the daily P&L query a full table scan. `live_trading_positions(broker_sl_order_id)` and `(broker_tp_order_id)` have no indexes, making bracket order lookups slow.

## Findings

**Architecture Strategist (P2):** "5 concurrent strategies × 150 status poll requests in 30 seconds = consuming 60% of the 5-minute rate limit bucket in a single execution cycle."

**Performance Oracle (P2-C):** "Semaphore of 5 is too low for broker-backed functions where 30s poll blocks the slot. Paper trading completes in ~100ms per strategy; live trading ties up a slot for 30s."

**Performance Oracle (P2-B):** "Missing index on `live_trading_trades (user_id, exit_time)` makes the daily P&L query a full table scan."

**Performance Oracle (P2-D):** "Missing indexes on `broker_sl_order_id` and `broker_tp_order_id` — bracket order status lookups require full scans."

## Proposed Solutions

### Fix 1 — Exponential backoff for fill polling:
Replace 1 req/sec constant poll with exponential backoff: 200ms, 400ms, 800ms, 1.6s, 3.2s, then settle at 2s intervals. For liquid equities, fills typically occur within 500ms — the first or second poll catches most fills. This cuts rate limit consumption by ~70% on fast-fill paths.

### Fix 2 — Separate semaphore for fill polling:
Use two semaphores: `EVALUATION_SEMAPHORE` (concurrency=10, fast path) and `FILL_POLL_SEMAPHORE` (concurrency=2, slow path). The slow-path semaphore prevents blocking all slots with 30-second polls while still processing new signals.

### Fix 3 — Add missing indexes to migration:
```sql
-- daily P&L query (most critical)
CREATE INDEX idx_live_trades_user_exit_time ON live_trading_trades (user_id, exit_time DESC);
-- bracket order lookup
CREATE INDEX idx_live_positions_sl_order ON live_trading_positions (broker_sl_order_id) WHERE broker_sl_order_id IS NOT NULL;
CREATE INDEX idx_live_positions_tp_order ON live_trading_positions (broker_tp_order_id) WHERE broker_tp_order_id IS NOT NULL;
```

## Technical Details

**Affected files:**
- `supabase/migrations/20260303110000_live_trading_tables.sql` — add three indexes
- `supabase/functions/live-trading-executor/index.ts` — exponential backoff in `pollOrderFill`, dual semaphore

## Acceptance Criteria

- [ ] `pollOrderFill` uses exponential backoff (200ms, 400ms, 800ms, 1.6s, 2s cap)
- [ ] Separate semaphore for fill-poll path prevents blocking all slots
- [ ] `idx_live_trades_user_exit_time` index in migration
- [ ] `idx_live_positions_sl_order` and `idx_live_positions_tp_order` partial indexes in migration
- [ ] Peak rate limit consumption ≤30% of 250 req/5min window for 5 concurrent strategies

## Work Log

- 2026-03-03: Finding created from Architecture Strategist (P2), Performance Oracle (P2-B, P2-C, P2-D).
