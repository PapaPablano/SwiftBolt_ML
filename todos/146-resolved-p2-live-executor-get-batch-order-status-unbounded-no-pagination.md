---
status: pending
priority: p2
issue_id: "146"
tags: [code-review, live-trading, performance, reliability]
dependencies: []
---

# `getBatchOrderStatus` fetches full account order history without pagination

## Problem Statement

`/Users/ericpeterson/SwiftBolt_ML/supabase/functions/_shared/tradestation-client.ts` lines 377–410: `getBatchOrderStatus` calls `GET /brokerage/accounts/{accountId}/orders` with no query parameters, fetching the complete order history for the account. For an active trading account with months of orders, this can be a very large payload. The response is filtered client-side to the required bracket order IDs (line 394–407). Two problems:

1. **No pagination handling**: The TradeStation API may paginate the response. If bracket order IDs fall off the first page, their fill status will never be detected and the position will never close.
2. **Unbounded payload growth**: As order history accumulates, each `checkBracketFills` call downloads more data, increasing latency and memory pressure within the 60-second edge function wall clock.

## Findings

**Architecture Strategist (P2-C):** "`getBatchOrderStatus` fetches all account orders rather than only the specific bracket order IDs... The payload size grows without bound as order history accumulates... the TradeStation API may paginate the order history, meaning some bracket orders may fall off the first page and be missed entirely."

## Proposed Solutions

**Option A (Recommended):** Pass a `since` date filter parameter (e.g., last 48 hours) to limit the query. Bracket orders are GTC but the position will be closed within a trading day in normal operation. 48 hours is a safe window that covers most edge cases while bounding payload size.

**Option B:** If TradeStation supports fetching orders by ID list (common in broker APIs), use that endpoint instead. This is O(N bracket orders) rather than O(account history).

**Option C:** Add pagination handling — follow `NextPage` tokens until all orders are fetched. This is correct but increases latency proportionally to account history size.

## Acceptance Criteria

- [ ] `getBatchOrderStatus` does not fetch unbounded order history
- [ ] Bracket orders placed within the last 48+ hours are reliably included in the response
- [ ] Pagination is handled (either via date filter or explicit page traversal)

## Work Log

- 2026-03-03: Finding from architecture-strategist (P2-C).
