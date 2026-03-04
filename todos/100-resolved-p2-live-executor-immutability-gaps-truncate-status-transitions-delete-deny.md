---
status: pending
priority: p2
issue_id: "100"
tags: [code-review, live-trading, database, immutability, security]
dependencies: []
---

# Immutability gaps — TRUNCATE not blocked, status transitions unconstrained, missing DELETE denial

## Problem Statement

Three gaps in the DB-level immutability enforcement for live trading financial records:

1. **TRUNCATE bypass:** Row-level triggers (`FOR EACH ROW`) don't fire on `TRUNCATE`. A superuser can silently wipe the entire `live_trading_trades` audit trail.

2. **Status transitions unconstrained:** The `status` CHECK ensures only valid values, but nothing prevents invalid transitions (e.g., `closed → open`, `cancelled → open`). A DB bug or direct SQL could produce impossible state sequences.

3. **Missing explicit DELETE denial:** `live_trading_positions` has no DELETE RLS policy — defaults to deny by omission, but this is implicit and fragile. A future `FOR ALL` policy could accidentally re-introduce deletes.

## Findings

**Data Integrity Guardian (DI-05 P2):** "Row-level triggers don't fire on TRUNCATE. A superuser executing TRUNCATE live_trading_trades would silently wipe the entire financial audit trail."

**Data Integrity Guardian (DI-06 P2):** "Nothing at the database level prevents: jumping from pending_entry directly to closed; moving from closed back to open (a financial integrity violation); transitioning from cancelled to open."

**Data Integrity Guardian (DI-07 P2):** "The omission [of DELETE policy] is implicit and fragile. An explicit USING (FALSE) policy cannot be accidentally widened."

## Proposed Solutions

### Fix 1 — TRUNCATE trigger:
```sql
CREATE OR REPLACE FUNCTION prevent_live_trade_truncate()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'live_trading_trades cannot be truncated — immutable financial ledger';
  RETURN NULL;
END;
$$;

CREATE TRIGGER live_trades_no_truncate
  BEFORE TRUNCATE ON live_trading_trades
  FOR EACH STATEMENT EXECUTE FUNCTION prevent_live_trade_truncate();
```

### Fix 2 — Status transition trigger:
```sql
CREATE OR REPLACE FUNCTION enforce_live_position_status_transitions()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF (OLD.status = 'pending_entry' AND NEW.status NOT IN ('pending_bracket', 'open', 'cancelled')) OR
     (OLD.status = 'pending_bracket' AND NEW.status NOT IN ('open', 'cancelled')) OR
     (OLD.status = 'open' AND NEW.status NOT IN ('pending_close', 'closed', 'cancelled')) OR
     (OLD.status = 'pending_close' AND NEW.status NOT IN ('closed', 'cancelled')) OR
     (OLD.status IN ('closed', 'cancelled') AND NEW.status != OLD.status)
  THEN
    RAISE EXCEPTION 'Invalid live position status transition: % → %', OLD.status, NEW.status;
  END IF;
  RETURN NEW;
END;
$$;
```

### Fix 3 — Explicit DELETE denial:
```sql
CREATE POLICY "live_positions_no_delete" ON live_trading_positions
  FOR DELETE USING (FALSE);

CREATE POLICY "live_trades_no_delete" ON live_trading_trades
  FOR DELETE USING (FALSE);
```

## Technical Details

**Affected files:**
- `supabase/migrations/20260303110000_live_trading_tables.sql` — all three fixes
- `docs/plans/2026-03-03-feat-live-trading-executor-tradestation-plan.md` — update Phase 1 acceptance criteria

Note: `pending_bracket` in the transition trigger depends on todo #085 being implemented first.

## Acceptance Criteria

- [ ] `BEFORE TRUNCATE` statement-level trigger on `live_trading_trades`
- [ ] Status transition trigger enforces: pending_entry → (pending_bracket|open|cancelled), open → (pending_close|closed|cancelled), closed/cancelled are terminal
- [ ] Explicit `USING (FALSE)` DELETE policies on both `live_trading_positions` and `live_trading_trades`
- [ ] `REVOKE DELETE ON live_trading_trades FROM authenticated, anon` in migration

## Work Log

- 2026-03-03: Finding created from Data Integrity Guardian (DI-05, DI-06, DI-07).
