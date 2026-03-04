---
status: pending
priority: p2
issue_id: "126"
tags: [code-review, live-trading, performance, database, scalability]
dependencies: []
---

# `action=summary` endpoint fetches all trades without pagination — unbounded query

## Problem Statement

The `action=summary` handler in `live-trading-executor/index.ts` (performance oracle P2-D) fetches all trades for a user without a LIMIT clause. For an active live trader with months of trade history, this query returns an unbounded result set, increasing memory usage, latency, and the risk of Edge Function timeout. The query could return thousands of rows when only the last 30 or 90 days are needed for the summary metrics.

## Findings

Performance Oracle P2-D.

## Proposed Solutions

**Option A (Recommended):** Add a `limit` query parameter (default 100, max 500) and/or a `since` date parameter to the summary handler. Apply `.limit()` and `.gte('exit_time', sinceDate)` to the Supabase query. Effort: Small.

## Acceptance Criteria

- [ ] Summary query has a default LIMIT (e.g., 500 rows or last 90 days)
- [ ] Callers can optionally specify a `limit` or `since` parameter
- [ ] The query cannot return an unbounded result set regardless of trade history size
