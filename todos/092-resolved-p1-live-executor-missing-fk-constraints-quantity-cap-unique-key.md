---
status: pending
priority: p1
issue_id: "092"
tags: [code-review, live-trading, database, schema, integrity]
dependencies: []
---

# DB schema issues: missing FK constraints, futures quantity cap too high, UNIQUE key too narrow

## Problem Statement

Three separate schema issues in the Phase 1 migrations would cause data integrity failures or undetectable data corruption:

1. **Missing FKs:** `live_trading_positions.strategy_id`, `live_trading_positions.symbol_id`, and `live_trading_trades.strategy_id` have no `REFERENCES` constraints. Orphaned positions after strategy deletion produce silent incorrect circuit breaker calculations.

2. **Quantity cap:** `CHECK (quantity <= 10000)` allows 10,000 futures contracts (e.g., @ES = $2.75B notional). This must be asset-type aware.

3. **UNIQUE constraint too narrow:** `UNIQUE (user_id, provider)` on `broker_tokens` prevents users from registering multiple TradeStation accounts (equities + futures under different credentials, or business vs personal accounts).

## Findings

**Data Integrity Guardian (DI-01 P1):** "Both `live_trading_positions.strategy_id` and `live_trading_positions.symbol_id` are declared `UUID NOT NULL` but carry no REFERENCES constraint. A position can be inserted referencing a strategy_id that has been deleted with no DB-level error."

**Data Integrity Guardian (DI-02 P1):** "For @ES futures: 10,000 contracts × $50 × ~5,500 index points = $2.75 billion notional. A realistic professional futures ceiling is 50 to 500 contracts."

**Data Integrity Guardian (DI-03 P1):** "UNIQUE (user_id, provider) prevents registering both equities and futures accounts under separate credentials... Once deployed and populated, changing a unique constraint requires a full table rewrite."

**Architecture Strategist (P3/P1):** "quantity <= 10000 DB constraint will fail as an unhandled DB error for large equity / tight stop scenarios" (also confirming the quantity cap issue).

## Proposed Solutions

**Issue 1 — FK constraints:**
```sql
-- In live_trading_positions:
strategy_id UUID NOT NULL REFERENCES strategy_user_strategies(id) ON DELETE RESTRICT,
symbol_id   UUID NOT NULL REFERENCES symbols(id) ON DELETE RESTRICT,

-- In live_trading_trades:
strategy_id UUID NOT NULL REFERENCES strategy_user_strategies(id) ON DELETE RESTRICT,
```
`ON DELETE RESTRICT` (not CASCADE) — never silently delete financial records.

**Issue 2 — Futures quantity cap:**
```sql
-- Replace single quantity CHECK with asset-type-conditional constraint:
quantity INT NOT NULL CHECK (quantity > 0 AND quantity <= 100000),  -- equities ceiling
CONSTRAINT live_futures_quantity_cap CHECK (
  asset_type = 'STOCK' OR (asset_type = 'FUTURE' AND quantity <= 500)
)
```

**Issue 3 — UNIQUE key:**
```sql
-- Replace UNIQUE (user_id, provider) with:
UNIQUE (user_id, provider, account_id),
CREATE INDEX idx_broker_tokens_user_provider ON broker_tokens (user_id, provider);
```
The executor query changes from `WHERE user_id=$1 AND provider='tradestation'` to `WHERE user_id=$1 AND provider='tradestation' AND account_id=$2`.

## Recommended Action

All three fixes must be in the Phase 1 migration files before any implementation begins. The UNIQUE constraint change is especially urgent — once deployed with user data, changing it requires a table rewrite. The FK constraints prevent orphaned financial records.

## Technical Details

**Affected files:**
- `supabase/migrations/20260303100000_broker_tokens.sql` — UNIQUE constraint change
- `supabase/migrations/20260303110000_live_trading_tables.sql` — FK constraints + quantity constraint

## Acceptance Criteria

- [ ] `strategy_id` and `symbol_id` have REFERENCES constraints with ON DELETE RESTRICT in both live_trading_positions and live_trading_trades
- [ ] `UNIQUE (user_id, provider, account_id)` replaces `UNIQUE (user_id, provider)` on broker_tokens
- [ ] Futures quantity capped at 500 via asset-type-conditional CHECK constraint
- [ ] Executor lookup query updated to include `account_id` in WHERE clause
- [ ] Pre-INSERT application-level check in `openLivePosition` catches quantity overflow before it reaches DB (returns `ExecutionResult { success: false, error: 'position_size_cap' }` rather than an unhandled constraint violation)

## Work Log

- 2026-03-03: Finding created from Data Integrity Guardian (DI-01, DI-02, DI-03) and Architecture Strategist.
