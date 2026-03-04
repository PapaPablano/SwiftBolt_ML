---
status: pending
priority: p2
issue_id: "166"
tags: [plan-review, live-trading, database, gdpr, documentation]
dependencies: []
---

# Fix Plan Phase 2.3: GDPR deletion path unaddressed — RESTRICT FK chain blocks user data purge

## Problem Statement

The Phase 2.3 fix changes `live_trading_positions.user_id` FK from `ON DELETE CASCADE` to `ON DELETE RESTRICT`. The rationale is correct (financial records must not be silently deleted). However, the plan does not acknowledge the downstream consequence: `live_trading_trades.position_id` already has `ON DELETE NO ACTION` (RESTRICT) by default. Together, these create a two-level FK chain that makes it impossible to delete a user's data through normal mechanisms, with no documented procedure for handling GDPR right-to-erasure requests.

## Findings

**Data Integrity Guardian (P2-D):**

The FK chain from the original migration:

```
auth.users(id)
  ← live_trading_positions.user_id [RESTRICT after fix]
    ← live_trading_trades.position_id [NO ACTION = RESTRICT]
```

An operator attempting to delete a user (GDPR right to erasure, account deletion request) will encounter:
1. `live_trading_positions.user_id` FK violation → cannot delete user while positions exist
2. `live_trading_trades.position_id` FK violation → cannot delete positions while trades exist

The deletion must be performed in reverse dependency order: delete trades first, then positions, then the user. This is intentional for financial records (audit trail preservation), but the plan does not document this procedure or acknowledge that the system has no automated GDPR purge path.

## Proposed Solution

Add to Phase 2.3 in the plan:

**Documentation note:** Add a comment to the migration explaining the intentional RESTRICT chain:

```sql
-- Changing CASCADE → RESTRICT: financial records must never be silently deleted.
-- GDPR deletion requires manual ordered purge:
--   1. DELETE FROM live_trading_trades WHERE user_id = $1;
--   2. DELETE FROM live_trading_positions WHERE user_id = $1;
--   3. DELETE FROM auth.users WHERE id = $1;
-- Note: live_trading_trades.position_id has ON DELETE NO ACTION (RESTRICT default),
--       so step 1 must precede step 2.
-- The system has no automated GDPR purge path — this is intentional (financial audit).
```

**Optional:** If a GDPR deletion procedure is needed, create a `SECURITY DEFINER` function that performs the ordered deletion and logs the purge event to a compliance audit table.

## Acceptance Criteria

- [ ] Phase 2.3 migration comment explains the intentional RESTRICT FK chain
- [ ] Manual deletion order documented (trades → positions → user)
- [ ] Plan acknowledges there is no automated GDPR purge path (intentional for financial records)

## Work Log

- 2026-03-03: Finding from data-integrity-guardian (P2-D) during plan review.
