---
status: pending
priority: p2
issue_id: "160"
tags: [plan-review, live-trading, performance, reliability]
dependencies: []
---

# Fix Plan Phase 6.2/7.4: Per-account batching should be implemented AFTER date filter, not before

## Problem Statement

The fix plan implements Phase 6.2 (per-account `checkBracketFills` batching) before Phase 7.4 (date filter on `getBatchOrderStatus`). This ordering means that for the period between 6.2 deployment and 7.4 deployment, users with multiple accounts receive more unbounded order history fetches than they did before. The efficiency guard (Phase 7.4) should precede the scaling change (Phase 6.2).

## Findings

**Architecture Strategist (P2-6):**

Phase 6.2 groups open positions by `account_id` and makes one `getBatchOrderStatus` call per distinct account. For a user with equity + futures accounts (two accounts), this changes 1 unbounded fetch to 2 unbounded fetches.

Phase 7.4 adds a `since` date filter (last 48 hours) to `getBatchOrderStatus`, bounding each fetch. Without Phase 7.4, Phase 6.2 doubles the data transfer and latency every cycle.

The correct sequence:
1. Phase 7.4 — add date filter to `getBatchOrderStatus` (bounds each fetch)
2. Phase 6.2 — per-account batching (now safe to have N fetches because each is bounded)

This crosses the plan's groupings (6.2 is in "Reliability", 7.4 is in "Financial Accuracy") but the dependency is real.

## Proposed Solution

In the fix plan, add a dependency note to Phase 6.2:

> **Prerequisite:** Phase 7.4 must be deployed before Phase 6.2. Phase 6.2 increases the number of `getBatchOrderStatus` calls from 1 to N (one per account). Without the date filter from Phase 7.4, this multiplies the unbounded payload problem.

And reorder the implementation so Phase 7.4 is implemented first (or deploy them together in a single deploy).

## Acceptance Criteria

- [ ] Plan documents the dependency: 7.4 must precede 6.2
- [ ] Implementation sequence updated so date filter is in place before per-account batching goes live
- [ ] OR both phases deployed atomically in the same deploy

## Work Log

- 2026-03-03: Finding from architecture-strategist (P2-6) during plan review.
