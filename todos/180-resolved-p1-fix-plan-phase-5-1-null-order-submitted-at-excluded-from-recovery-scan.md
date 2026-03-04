---
status: resolved
priority: p1
issue_id: "180"
tags: [plan-review, live-trading, database, state-machine, financial-safety]
dependencies: []
---

# Fix Plan Phase 5.1: `order_submitted_at IS NULL` positions silently excluded from recovery scan — stuck forever

## Problem Statement

The recovery scan query uses `.lt("order_submitted_at", threshold)`. In PostgreSQL, `NULL < value` evaluates to `NULL` (not `TRUE`), so PostgREST's `.lt()` filter silently excludes rows where `order_submitted_at IS NULL`. Since the column is nullable in the migration, any position inserted without this field will never be found by the recovery scan and will remain permanently stuck with no automated resolution path.

## Findings

**Spec-Flow Analyzer (GAP-P1-2):**

The migration at `20260303110000_live_trading_tables.sql` line 65 defines `order_submitted_at TIMESTAMPTZ` — nullable, no `NOT NULL` constraint.

The plan's Phase 5.1 recovery query:
```typescript
const { data: stuckPositions } = await supabase
  .from("live_trading_positions")
  .select("*")
  .in("status", ["pending_entry", "pending_bracket"])
  .lt("order_submitted_at", threshold.toISOString());
```

In PostgreSQL: `NULL < '2026-03-03T12:00:00Z'` → `NULL` (not TRUE) → row excluded by WHERE clause.

**Two fixes available:**

**Option A — Add `IS NULL` to the recovery query (no migration needed):**
```typescript
const { data: stuckPositions } = await supabase
  .from("live_trading_positions")
  .select("*")
  .in("status", ["pending_entry", "pending_bracket"])
  .or(`order_submitted_at.lt.${threshold.toISOString()},order_submitted_at.is.null`);
```

This catches positions that were inserted without `order_submitted_at` — treat them as "submitted at unknown time, assume stuck."

**Option B — Add NOT NULL DEFAULT NOW() constraint (migration required):**
```sql
-- In Phase 1.3 or Phase 2 migration:
ALTER TABLE live_trading_positions
  ALTER COLUMN order_submitted_at SET NOT NULL,
  ALTER COLUMN order_submitted_at SET DEFAULT NOW();
```

This prevents NULL insertion going forward and ensures the `.lt()` filter works correctly. Existing NULL rows would need backfilling before the constraint is applied.

**Recommended:** Option A (query fix) for immediate correctness + Option B (constraint) as a secondary hardening measure. Both can be done in the same PR.

**When does order_submitted_at end up NULL?**

The current insertion code at lines 791–814 of `index.ts` sets `order_submitted_at: orderSubmittedAt` before insert — so it is populated in the happy path. However, any alternative code path, future refactor, or recovery-path re-insert that doesn't explicitly set this field will produce a NULL row that the recovery scan will never find.

## Proposed Solution

Amend Phase 5.1 in the plan:
1. Change the recovery query to include `.or("order_submitted_at.is.null")` alongside the `.lt()` filter
2. Add `ALTER COLUMN order_submitted_at SET NOT NULL DEFAULT NOW()` to the Phase 1.3 or Phase 2 migration as a hardening measure

## Acceptance Criteria

- [x] Recovery query uses `.or("order_submitted_at.lt.X,order_submitted_at.is.null")` pattern
- [x] NULL positions are treated as "stuck since unknown time" and included in recovery
- [x] Plan optionally adds NOT NULL DEFAULT NOW() constraint to prevent future NULL insertions
- [x] Test case documented: insert a position with NULL `order_submitted_at`, verify recovery scan finds it

## Work Log

- 2026-03-03: Finding from spec-flow-analyzer (GAP-P1-2) during plan review. PostgreSQL NULL comparison semantics silently drop rows from the recovery scan.
- 2026-03-03: Resolved — plan amended with NULL handling in recovery query, acceptance criteria updated.
