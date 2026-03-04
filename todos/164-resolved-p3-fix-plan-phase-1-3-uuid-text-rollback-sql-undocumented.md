---
status: resolved
priority: p3
issue_id: "164"
tags: [plan-review, live-trading, database, migration, documentation]
dependencies: []
---

# Fix Plan Phase 1.3: UUID→TEXT rollback SQL not documented — reverse cast may fail after non-UUID strings inserted

## Problem Statement

The Phase 1.3 migration changes `live_trading_positions.symbol_id` from UUID to TEXT. The plan does not document rollback SQL. Rolling back this column type change after non-UUID strings have been inserted requires `ALTER COLUMN TYPE UUID USING symbol_id::uuid`, which will fail with a cast error if any non-UUID string is present. This is a one-way door that the plan does not acknowledge.

## Findings

**Data Integrity Guardian (P2-A) — classified P3 as documentation only:**

The forward migration (UUID→TEXT) uses an implicit cast that PostgreSQL performs automatically — safe with existing UUID data. However:

1. Once the new executor code writes raw symbol strings (`"AAPL"`, `"@ES"`) as `symbol_id`, a rollback to UUID fails unconditionally
2. The plan's Risk Analysis section doesn't mention this for Phase 1.3
3. The Deployment Verification checklist (`docs/DEPLOYMENT_VERIFICATION_PR28_LIVE_TRADING.md`) should note this is effectively irreversible once any trade is recorded post-migration

## Proposed Solution

Add to Phase 1.3 in the plan under a "Rollback" subsection:

```
### Rollback

Phase 1.3 is a one-way migration once any non-UUID strings are written to `symbol_id`.

Forward migration: safe (UUID strings are valid TEXT)

Rollback (before any non-UUID data written):
ALTER TABLE live_trading_positions
  ALTER COLUMN symbol_id TYPE UUID USING symbol_id::uuid;

Rollback (after non-UUID data written): NOT POSSIBLE without data deletion.

Recommendation: take a row-count snapshot before migration and verify 0 rows in live_trading_positions before applying if a rollback path must be preserved.
```

## Acceptance Criteria

- [x] Plan documents that UUID→TEXT is effectively irreversible once raw symbol strings are written
- [x] Rollback SQL provided with caveat that it fails after non-UUID inserts
- [x] Deployment checklist updated to note position count before/after migration

## Work Log

- 2026-03-03: Finding from data-integrity-guardian (P2-A, classified P3) during plan review.

- 2026-03-03: RESOLVED. Plan amended to address all findings.
