---
status: pending
priority: p1
issue_id: "132"
tags: [code-review, live-trading, agent-native, pagination, data-correctness]
dependencies: []
---

# `total` field in positions/trades list responses always returns page size, not real count — pagination broken

## Problem Statement

In `live-trading-executor/index.ts` lines 1170 and 1192, both `positions` and `trades` list responses include `total: positions?.length ?? 0`. Since the queries use `.range(offset, offset + limit - 1)`, `positions.length` is at most `limit` (50). The `total` field will never exceed 50, so any consumer (agent or UI) that uses it to detect whether additional pages exist will always conclude there are no more records after page 1. For an agent processing all historical trades for P&L analysis, this means silently stopping after 50 records and returning incorrect calculations.

## Findings

Agent-Native Reviewer, Critical Finding #4. The `total` field is incorrect on both the `/positions` and `/trades` response shapes. Pagination parameters (`limit`, `offset`) exist but are useless without an accurate `total`.

## Proposed Solutions

Option A (Recommended): Use Supabase's `{ count: "exact" }` option in both select calls: `.select("...", { count: "exact" })`. The response includes a `count` field alongside `data`. Return `total: count ?? 0` in the JSON response. Effort: Small.

## Acceptance Criteria

- [ ] `GET ?action=positions` response includes `total` equal to the actual database count (not page size)
- [ ] `GET ?action=trades` response includes `total` equal to the actual database count
- [ ] An agent can determine whether additional pages exist by comparing `total` to `offset + limit`
