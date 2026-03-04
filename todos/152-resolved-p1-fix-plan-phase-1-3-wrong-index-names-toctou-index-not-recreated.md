---
status: resolved
priority: p1
issue_id: "152"
tags: [plan-review, live-trading, database, migration, financial-safety]
dependencies: []
---

# Fix Plan Phase 1.3: Wrong index names — TOCTOU unique index not recreated after ALTER COLUMN

## Problem Statement

The fix plan's Phase 1.3 migration drops two indexes by names that do not exist in the original migration. Because both statements use `IF EXISTS`, they silently succeed and do nothing. The actual existing indexes (`idx_live_positions_active_unique` and `idx_live_positions_user_strategy`) remain, and the plan then creates new indexes under new names — potentially leaving two overlapping index definitions. More critically: the `idx_live_positions_active_unique` unique partial index (which prevents TOCTOU double-entry — previously identified as P1 #088) may end up in a corrupt or duplicate state.

## Findings

**Architecture Strategist (P1-4) + Data Integrity Guardian (P1-A + P1-B):**

Original migration `20260303110000_live_trading_tables.sql` creates:

```sql
-- Line 86
CREATE UNIQUE INDEX IF NOT EXISTS idx_live_positions_active_unique
  ON live_trading_positions (user_id, strategy_id, symbol_id)
  WHERE status IN ('pending_entry', 'pending_bracket', 'open');

-- Line 91
CREATE INDEX IF NOT EXISTS idx_live_positions_user_strategy
  ON live_trading_positions (user_id, strategy_id, symbol_id, status, created_at DESC);
```

The fix plan's Phase 1.3 migration drops:

```sql
DROP INDEX IF EXISTS idx_live_positions_strategy_symbol;         -- WRONG NAME
DROP INDEX IF EXISTS idx_live_positions_strategy_symbol_open;   -- WRONG NAME
```

Neither of these names exists. Both DROP statements are no-ops. The old UUID-typed indexes remain in place. The plan then creates new TEXT-typed indexes under the new (wrong) names, leaving the database with:
- `idx_live_positions_active_unique` (UUID-typed, old name, still exists)
- `idx_live_positions_strategy_symbol_open` (TEXT-typed, new name, duplicate unique constraint)

This is undefined behavior for the query planner and will cause schema drift detection tools to report unexpected differences.

## Proposed Solution

The migration must target the correct existing names:

```sql
-- Drop the actual existing indexes
DROP INDEX IF EXISTS idx_live_positions_active_unique;
DROP INDEX IF EXISTS idx_live_positions_user_strategy;

-- Recreate with TEXT-compatible definitions, using original names
CREATE UNIQUE INDEX IF NOT EXISTS idx_live_positions_active_unique
  ON live_trading_positions (user_id, strategy_id, symbol_id)
  WHERE status IN ('pending_entry', 'pending_bracket', 'open');

CREATE INDEX IF NOT EXISTS idx_live_positions_user_strategy
  ON live_trading_positions (user_id, strategy_id, symbol_id, status, created_at DESC);
```

Recreating under the original names prevents schema drift and ensures the TOCTOU double-entry prevention constraint is in place with the correct column types.

## Acceptance Criteria

- [x] DROP INDEX targets correct names (`idx_live_positions_active_unique`, `idx_live_positions_user_strategy`)
- [x] Recreated indexes use original names
- [x] `idx_live_positions_active_unique` unique partial index exists after migration with TEXT-typed `symbol_id`
- [x] No duplicate index definitions on the same column set
- [x] `EXPLAIN` on a sample query still uses the index

## Work Log

- 2026-03-03: Finding from architecture-strategist (P1-4) and data-integrity-guardian (P1-A, P1-B) during plan review.
- 2026-03-03: Resolved — plan amended with corrected code snippets, acceptance criteria updated.

- 2026-03-03: RESOLVED. Plan amended to address all findings.
