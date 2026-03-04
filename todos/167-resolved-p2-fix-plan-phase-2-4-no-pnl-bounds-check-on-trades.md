---
status: resolved
priority: p2
issue_id: "167"
tags: [plan-review, live-trading, database, financial-safety]
dependencies: []
---

# Fix Plan Phase 2.4: No CHECK constraint on `pnl` bounds — multiplier bugs can silently write corrupt P&L

## Problem Statement

The Phase 2.4 migration adds price and quantity CHECK constraints to `live_trading_trades` but omits a sanity bound on the `pnl` column. An astronomically incorrect P&L value from a futures multiplier bug (e.g., applying the multiplier twice) would silently persist in the immutable audit trail with no constraint to catch it.

## Findings

**Data Integrity Guardian (P2-E):**

The `live_trading_trades.pnl` column at line 134 of the original migration is `DECIMAL(12,4) NOT NULL` with no constraint. A futures multiplier error (e.g., using 50x instead of 1x on an ES contract) could produce a P&L of $5,000,000 on a single micro-lot trade. This value would:

1. Pass all existing constraints silently
2. Be written to the immutable audit trail with no ability to correct it
3. Distort P&L summaries and circuit breaker calculations permanently

The Phase 7.2 discussion in the plan explicitly identifies multiplier errors as a risk — yet the Phase 2.4 migration adds no guard against them.

Given `live_max_position_pct = 10%` of capital, a single trade's max P&L should be bounded by approximately 10% of the account equity. For a conservative upper bound, ±$1,000,000 per trade covers even leveraged futures accounts with very high equity.

## Proposed Solution

Add to Phase 2.4 migration:

```sql
-- Sanity bounds on pnl: catches multiplier bugs before they enter the immutable audit trail
-- Assumes max 10% position size and maximum realistic account equity ~$10M
ALTER TABLE live_trading_trades
  ADD CONSTRAINT live_trades_pnl_sane
    CHECK (pnl BETWEEN -1000000 AND 1000000);

-- Also add pnl_pct bounds (max ±1000% return on a single trade is realistic upper bound)
ALTER TABLE live_trading_trades
  ADD CONSTRAINT live_trades_pnl_pct_sane
    CHECK (pnl_pct IS NULL OR pnl_pct BETWEEN -1000 AND 1000);
```

The bounds can be adjusted if needed — the goal is to catch orders-of-magnitude errors, not precision bounds. An error that should produce $200 P&L but instead produces $200,000 should fail the constraint and surface immediately rather than silently corrupting the audit trail.

## Acceptance Criteria

- [x] `live_trading_trades.pnl` has a CHECK constraint bounding it to a realistic range
- [x] Constraint is tight enough to catch multiplier-of-50x errors on micro lots
- [x] `pnl_pct` bounds added if the column is populated
- [x] Plan documents what the bounds represent (maximum 10% position, maximum plausible equity)

## Work Log

- 2026-03-03: Finding from data-integrity-guardian (P2-E) during plan review.

- 2026-03-03: RESOLVED. Plan amended to address all findings.
