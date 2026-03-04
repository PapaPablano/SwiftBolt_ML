---
status: pending
priority: p2
issue_id: "176"
tags: [plan-review, live-trading, agent-native, api-design]
dependencies: []
---

# Fix Plan Phase 8.4: `?strategy_id=` filter missing from positions GET — agent forced to fetch all positions and filter client-side

## Problem Statement

The Phase 8.4 fix adds server-side `?status=` filtering to the positions GET endpoint. This is the right direction. However, the most common agent query — "what positions are currently open for strategy X?" — requires `?strategy_id=` filtering, which is not in the plan. Without it, an agent managing multiple strategies must fetch all open positions, filter client-side by `strategy_id`, and only then decide whether to send an execution request. This is a context-gathering anti-pattern that wastes tokens and introduces a latency round-trip.

## Findings

**Agent-Native Reviewer (P2-Finding 4):**

The primary agent use case for the positions endpoint is: "Before I submit an execution request for strategy X, how many open positions does it already have?" This requires `?strategy_id=` filtering.

The internal execution loop at lines 635–641 of `live-trading-executor/index.ts` already performs this exact query:
```typescript
const { data: positions } = await supabase
  .from("live_trading_positions")
  .select("*")
  .eq("user_id", user.id)
  .eq("strategy_id", strategyId)  // ← this filter already exists internally
  .eq("status", "open");
```

The `idx_live_positions_user_strategy` index (created in the Phase 2 migration) already covers `(user_id, strategy_id)` — this query is efficient. The filter only needs to be surfaced on the GET handler.

**Amendment to Phase 8.4 (4 lines):**
```typescript
const strategyIdFilter = url.searchParams.get("strategy_id");
if (strategyIdFilter) {
  query = query.eq("strategy_id", strategyIdFilter);
}
```

This should be applied alongside the `?status=` filter in the same phase, since they are both server-side position filters and share the same implementation pattern.

**Combined filter capability after fix:**
```
GET ?action=positions&status=open&strategy_id=<uuid>
```

This is the canonical agent pre-check query: "Are there open positions for this strategy? If yes, how many?"

## Proposed Solution

Extend Phase 8.4 in the plan to add `?strategy_id=` filtering to the positions GET handler alongside `?status=`. Document the combined filter pattern as the recommended pre-execution check for agents.

## Acceptance Criteria

- [ ] `?strategy_id=UUID` filter supported on GET `?action=positions`
- [ ] Filter applied server-side (not client-side) using `idx_live_positions_user_strategy` index
- [ ] `?status=` and `?strategy_id=` filters can be combined in a single request
- [ ] Plan documents `GET ?action=positions&status=open&strategy_id=<uuid>` as the recommended agent pre-execution check

## Work Log

- 2026-03-03: Finding from agent-native-reviewer (P2-Finding 4) during plan review. The plan adds `?status=` but omits the equally important `?strategy_id=` filter that enables agents to check per-strategy position counts before submitting execution requests.
