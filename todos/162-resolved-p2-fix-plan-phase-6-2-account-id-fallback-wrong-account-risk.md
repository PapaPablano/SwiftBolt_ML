---
status: resolved
priority: p2
issue_id: "162"
tags: [plan-review, live-trading, financial-safety, reliability]
dependencies: []
---

# Fix Plan Phase 6.2: `account_id` fallback in per-account batching could route bracket fills to wrong account

## Problem Statement

The Phase 6.2 per-account bracket batching code falls back to the current executor's `accountId` when a position's `account_id` is NULL in the database. For users with multiple accounts (equity + futures), this fallback silently routes bracket fill checks to the wrong account, meaning a futures position's bracket orders would be queried against the equity account — and fill events would never be detected.

## Findings

**Learnings Researcher (Gotcha A):**

Phase 6.2's proposed grouping code:

```typescript
const byAccount = new Map<string, typeof positions>();
for (const pos of positions) {
  const acct = pos.account_id ?? accountId;  // ← fallback to current invocation's account
  if (!byAccount.has(acct)) byAccount.set(acct, []);
  byAccount.get(acct)!.push(pos);
}
```

Looking at the migration: `live_trading_positions.account_id TEXT NOT NULL` — the column is already NOT NULL. A null fallback should be unreachable given the DB constraint. However:

1. If any existing rows were inserted without `account_id` (before NOT NULL was added), they have a null-equivalent value in that field
2. If the fallback fires for a futures position while the executor's `accountId` is the equity account, the bracket fill check goes to the wrong account entirely

The correct defensive behavior is to **skip** positions with missing account_id (not fall back to current account), and log an alert for manual investigation.

## Proposed Solution

Change the fallback to skip-and-alert:

```typescript
const byAccount = new Map<string, typeof positions>();
for (const pos of positions) {
  if (!pos.account_id) {
    console.error(`[live-executor] ALERT: Position ${pos.id} has no account_id — skipping bracket fill check. Manual review required.`);
    continue;  // Skip, not fallback — wrong account is worse than no check
  }
  if (!byAccount.has(pos.account_id)) byAccount.set(pos.account_id, []);
  byAccount.get(pos.account_id)!.push(pos);
}
```

## Acceptance Criteria

- [x] Phase 6.2 code skips positions with null/missing `account_id` (with error log) instead of falling back to invocation's account
- [x] Comment explains why fallback is not used (wrong account risk > no check)
- [x] Plan notes that `account_id NOT NULL` constraint prevents this in production but the defensive code provides belt-and-suspenders

## Work Log

- 2026-03-03: Finding from learnings-researcher (Gotcha A) during plan review.

- 2026-03-03: RESOLVED. Plan amended to address all findings.
