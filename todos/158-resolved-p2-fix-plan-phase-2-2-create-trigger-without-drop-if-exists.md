---
status: resolved
priority: p2
issue_id: "158"
tags: [plan-review, live-trading, database, migration, reliability]
dependencies: []
---

# Fix Plan Phase 2.2: `CREATE TRIGGER` without `DROP TRIGGER IF EXISTS` — fails on re-run

## Problem Statement

The Phase 2.2 migration uses `CREATE TRIGGER live_positions_updated_at ...` without a preceding `DROP TRIGGER IF EXISTS`. On any re-run (local dev reset, `supabase db reset`, partial apply followed by rollback), the migration will fail with `trigger "live_positions_updated_at" for relation "live_trading_positions" already exists`. This violates the idempotency requirement for migrations deployed during market hours.

## Findings

**Data Integrity Guardian (P2-C):**

The existing migration `20260225130000_paper_trading_immutability_v1.sql` (line 61–62) uses the codebase-standard pattern:

```sql
DROP TRIGGER IF EXISTS <name> ON <table>;
CREATE TRIGGER <name> ...
```

The plan deviates from this convention. All existing trigger creation in this codebase uses the drop-then-create pattern. The live trading fix plan should match.

## Proposed Solution

Add `DROP TRIGGER IF EXISTS` before each `CREATE TRIGGER` in Phase 2.2:

```sql
-- Drop first to ensure idempotency (matches paper trading migration convention)
DROP TRIGGER IF EXISTS live_positions_updated_at ON live_trading_positions;
CREATE TRIGGER live_positions_updated_at
  BEFORE UPDATE ON live_trading_positions
  FOR EACH ROW EXECUTE FUNCTION update_live_positions_updated_at();
```

Note: The trigger function itself uses `CREATE OR REPLACE FUNCTION` which is already idempotent. Only the `CREATE TRIGGER` statement is non-idempotent.

## Acceptance Criteria

- [x] `DROP TRIGGER IF EXISTS live_positions_updated_at ON live_trading_positions` added before the `CREATE TRIGGER`
- [x] Migration can be applied multiple times without error (idempotent)
- [x] Matches the drop-then-create convention used in existing migrations

## Work Log

- 2026-03-03: Finding from data-integrity-guardian (P2-C) during plan review.

- 2026-03-03: RESOLVED. Plan amended to address all findings.
