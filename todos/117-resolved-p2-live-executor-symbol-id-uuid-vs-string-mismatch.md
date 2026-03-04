---
status: pending
priority: p2
issue_id: "117"
tags: [code-review, live-trading, database, typescript, runtime-error]
dependencies: []
---

# `symbol_id UUID` column type vs. raw symbol string passed by executor — runtime type error

## Problem Statement

`live_trading_positions.symbol_id` is declared as `UUID NOT NULL` in the migration (line 32). However, the executor passes raw symbol strings like `"AAPL"`, `"@ES"` directly as `symbol_id` in queries at lines 535, 547, 582, and 796 of `live-trading-executor/index.ts`. This either causes a runtime Postgres type error on the first live trade attempt, or silently coerces the value depending on PostgREST behavior. `live_trading_trades.symbol` correctly uses `TEXT NOT NULL`, making the positions table the outlier.

## Findings

Architecture Strategist P2-F. The mismatch will surface as a runtime error in production, not a compile error, and only on the first actual trade attempt.

## Proposed Solutions

**Option A (Recommended):** Change `live_trading_positions.symbol_id` column from `UUID` to `TEXT NOT NULL` to align with how the executor uses it and with `live_trading_trades.symbol TEXT`. Add a CHECK constraint `CHECK (symbol_id ~ '^[@A-Z]{1,10}$')` for validation. Requires a migration to alter the column type. Effort: Small.

**Option B:** Resolve the symbol string to a UUID via a `symbols` table lookup before inserting. Effort: Large — requires a symbols table that doesn't currently exist.

## Acceptance Criteria

- [ ] `live_trading_positions.symbol_id` column accepts the raw symbol strings the executor passes
- [ ] No runtime type error occurs on the first live trade
- [ ] A CHECK or validation constraint ensures only valid symbol strings are stored
