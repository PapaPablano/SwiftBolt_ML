---
status: pending
priority: p2
issue_id: "187"
tags: [plan-review, live-trading, database, migration, state-machine]
dependencies: ["154"]
---

# Fix Plan Phase 5 + 2.4: `EMERGENCY_CLOSE` missing from `live_trading_positions` CHECK constraint — Phase 5 writes will fail

## Problem Statement

The existing `live_trading_positions.close_reason` CHECK constraint (in `20260303110000_live_trading_tables.sql`) does not include `'EMERGENCY_CLOSE'`. Phase 5's recovery scan calls `closeLivePosition` with `"emergency_close"` (or `"EMERGENCY_CLOSE"`) as the close reason, which will violate the CHECK constraint on `live_trading_positions` and cause the emergency close DB write to fail — leaving the position stuck despite a successful broker-side close order.

## Findings

**Spec-Flow Analyzer (GAP-P2-5):**

The migration at `20260303110000_live_trading_tables.sql` line 58–62 defines `close_reason` CHECK for `live_trading_positions`:
```sql
CHECK (close_reason IN ('SL_HIT', 'TP_HIT', 'EXIT_SIGNAL', 'MANUAL_CLOSE',
                        'GAP_FORCED_CLOSE', 'PARTIAL_FILL_CANCELLED',
                        'BROKER_ERROR', 'BRACKET_PLACEMENT_FAILED'))
```

`'EMERGENCY_CLOSE'` is not in this list.

Phase 5's `recoverStuckPositions` calls `closeLivePosition(..., "emergency_close")` or `"EMERGENCY_CLOSE"` (case TBD per todo #154). Either case fails the CHECK constraint.

**Impact:** The emergency close broker order succeeds (TradeStation closes the position), but the DB write fails with a CHECK constraint violation. The position remains `status = 'pending_bracket'` in the DB. The recovery scan will attempt to close it again on the next cycle, placing another broker-side close order on a position that is already closed at the broker — creating an untracked double-close order.

**Required migration addition (to Phase 5 migration or separate):**

```sql
ALTER TABLE live_trading_positions
  DROP CONSTRAINT live_trading_positions_close_reason_check,
  ADD CONSTRAINT live_trading_positions_close_reason_check
    CHECK (close_reason IN (
      'SL_HIT', 'TP_HIT', 'EXIT_SIGNAL', 'MANUAL_CLOSE',
      'GAP_FORCED_CLOSE', 'PARTIAL_FILL_CANCELLED',
      'BROKER_ERROR', 'BRACKET_PLACEMENT_FAILED',
      'EMERGENCY_CLOSE'  -- ← add this
    ));
```

Note: This is a companion to todo #154 (which addresses the case mismatch between Phase 2.4's lowercase constraint and the executor's SCREAMING_SNAKE_CASE writes). This issue is specifically about the missing `EMERGENCY_CLOSE` value on the `live_trading_positions` constraint — not the `live_trading_trades` constraint addressed by #154.

## Proposed Solution

Amend the plan's Phase 5 (or the Phase 2 migration) to include `'EMERGENCY_CLOSE'` in the `live_trading_positions.close_reason` CHECK constraint. This should be resolved in the same migration pass that addresses #154 (the case mismatch), since both require modifying the same CHECK constraint.

## Acceptance Criteria

- [ ] `'EMERGENCY_CLOSE'` added to `live_trading_positions.close_reason` CHECK constraint
- [ ] Phase 5's recovery scan uses the same casing as the CHECK constraint (coordinate with #154)
- [ ] Test: attempt to INSERT a position with `close_reason = 'EMERGENCY_CLOSE'` — should succeed
- [ ] No duplicate constraint names — old constraint is dropped before new one is added

## Work Log

- 2026-03-03: Finding from spec-flow-analyzer (GAP-P2-5) during plan review. Companion to #154. The missing EMERGENCY_CLOSE value means Phase 5 emergency closes will fail at the DB write even when the broker-side order succeeds.
