---
status: pending
priority: p2
issue_id: "122"
tags: [code-review, live-trading, database, data-integrity, schema]
dependencies: []
---

# `live_trading_trades` missing CHECK constraints on financial fields — corrupted immutable records possible

## Problem Statement

`live_trading_trades.entry_price`, `exit_price`, and `quantity` have no positivity CHECK constraints (migration lines 130–133). A broker API returning a malformed fill price of 0 or -1 would insert a corrupted trade record that passes all DB-level validation. Since the immutability trigger prevents subsequent updates, the corrupted record is permanent. Additionally, `asset_type` (line 144) has a DEFAULT but no CHECK constraint, unlike the positions table which enforces `CHECK (asset_type IN ('STOCK', 'FUTURE'))`.

## Findings

Data Integrity Guardian P2-C. The positions table correctly has positivity checks — they were not carried over to the trades table.

## Proposed Solutions

**Option A (Recommended):** Add a migration that adds CHECK constraints to `live_trading_trades`: `entry_price > 0`, `exit_price > 0`, `quantity > 0 AND quantity <= 10000`, `asset_type IN ('STOCK', 'FUTURE')`. Also add the `close_reason` enum constraint (matches the positions table). Effort: Small — ALTER TABLE to add constraints.

## Acceptance Criteria

- [ ] `entry_price`, `exit_price`, `quantity` have positivity CHECK constraints
- [ ] `asset_type` has an enum CHECK constraint matching the positions table
- [ ] A malformed broker fill price of 0 or negative is rejected at the DB level
