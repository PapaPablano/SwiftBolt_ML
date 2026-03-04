---
status: resolved
priority: p1
issue_id: "154"
tags: [plan-review, live-trading, database, migration, financial-safety]
dependencies: []
---

# Fix Plan Phase 2.4: `close_reason` CHECK constraint uses lowercase — executor writes uppercase, trades table INSERT will fail

## Problem Statement

The Phase 2.4 migration adds a CHECK constraint to `live_trading_trades.close_reason` using lowercase values (`stop_loss_hit`, `manual_close`, etc.). The original migration and the existing executor code write **uppercase** values to `live_trading_positions.close_reason` (`SL_HIT`, `MANUAL_CLOSE`, etc.). If the executor writes the same casing to `live_trading_trades`, every trade INSERT will be rejected by the new constraint, breaking the immutable audit trail.

## Findings

**Data Integrity Guardian (P1-D):**

Original migration `20260303110000_live_trading_tables.sql`, line 58–62, defines `live_trading_positions.close_reason`:

```sql
close_reason TEXT CHECK (close_reason IN (
  'SL_HIT', 'TP_HIT', 'EXIT_SIGNAL', 'MANUAL_CLOSE',
  'GAP_FORCED_CLOSE', 'PARTIAL_FILL_CANCELLED',
  'BROKER_ERROR', 'BRACKET_PLACEMENT_FAILED'
))
```

The plan's Phase 2.4 constraint for `live_trading_trades`:

```sql
CHECK (close_reason IN (
  'stop_loss_hit', 'take_profit_hit', 'exit_signal',
  'manual_close', 'emergency_close', 'circuit_breaker'
))
```

These are entirely different values. The executor writes to the `live_trading_positions` table using the uppercase values. The `live_trading_trades` table has `close_reason TEXT NOT NULL` with no constraint today. Adding a constraint with the wrong casing will reject every trade INSERT that matches an existing close reason, silently breaking the audit trail.

Additionally, `emergency_close` and `circuit_breaker` are new values introduced by Phase 5 and Phase 8.6. These need to be consistent with whatever casing the executor actually writes for those new paths.

## Proposed Solution

Option A (recommended — match existing casing):

```sql
ALTER TABLE live_trading_trades
  ADD CONSTRAINT live_trades_close_reason_valid
    CHECK (close_reason IN (
      'SL_HIT', 'TP_HIT', 'EXIT_SIGNAL', 'MANUAL_CLOSE',
      'GAP_FORCED_CLOSE', 'PARTIAL_FILL_CANCELLED',
      'BROKER_ERROR', 'BRACKET_PLACEMENT_FAILED',
      'EMERGENCY_CLOSE',     -- new: Phase 5 recovery scan
      'CIRCUIT_BREAKER'      -- new: Phase 8.6
    ));
```

Option B (normalize to lowercase throughout):

Change `live_trading_positions.close_reason` constraint to lowercase AND update all executor code that writes close_reason. More consistent with Postgres convention but much higher change surface — all existing trades in `live_trading_positions` would need a migration update.

Option A is strongly recommended to minimize blast radius.

## Acceptance Criteria

- [x] `live_trading_trades.close_reason` CHECK constraint values match the casing the executor writes
- [x] `EMERGENCY_CLOSE` and `CIRCUIT_BREAKER` added as valid values for new recovery/circuit-breaker paths
- [x] Existing `live_trading_positions.close_reason` CHECK values remain unchanged (or are verified consistent)
- [x] Trade inserts from all close paths pass the constraint without error

## Work Log

- 2026-03-03: Finding from data-integrity-guardian (P1-D) during plan review.
- 2026-03-03: Resolved — plan amended with corrected code snippets, acceptance criteria updated.

- 2026-03-03: RESOLVED. Plan amended to address all findings.
