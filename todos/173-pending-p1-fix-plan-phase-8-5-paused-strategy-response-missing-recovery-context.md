---
status: pending
priority: p1
issue_id: "173"
tags: [plan-review, live-trading, agent-native, api-design]
dependencies: []
---

# Fix Plan Phase 8.5: Paused strategy response missing `paused_at` and `suggested_action` — agent cannot determine recovery path

## Problem Statement

The Phase 8.5 fix upgrades the paused strategy response from `{ action: "no_action" }` to `{ action: "skipped", reason: "strategy_paused", strategyId }`. This is a necessary improvement but still insufficient for agent-native use. An agent receiving this response cannot determine how long the strategy has been paused, or what action to take next — forcing an extra round-trip to the strategies endpoint to investigate, when the executor already has this information.

## Findings

**Agent-Native Reviewer (P1-Finding 1):**

The plan's proposed fix:
```typescript
return { success: true, action: "skipped", reason: "strategy_paused", strategyId: strategy.id };
```

This tells an agent *what happened* but provides no recovery path. An agent has three reasonable next actions:
1. Unpause the strategy (if pause was unintentional)
2. Check why it was paused (if pause was deliberate, investigate root cause)
3. Wait and retry (if pause is expected to be short)

Without `paused_at` and `suggested_action`, the agent has no basis to choose between these. It must make a separate call to GET `/strategies/{id}` to read `live_trading_paused_at`, adding a round trip that could be avoided with richer executor output.

**Required addition to Phase 8.5 response:**

```typescript
return {
  success: true,
  action: "skipped",
  reason: "strategy_paused",
  strategyId: strategy.id,
  paused_at: strategy.live_trading_paused_at ?? null,  // ISO 8601 timestamp or null
  suggested_action: "unpause_strategy",               // literal — not business logic, just context
};
```

**Schema dependency:** This requires either:
- (a) A `live_trading_paused_at TIMESTAMPTZ` column on `strategy_user_strategies` — add to Phase 2 migration, OR
- (b) Document that `paused_at` is null until the column is added and flag as a follow-up

Option (a) is strongly preferred: the column costs one line in the migration and makes the paused-since duration computable for both agents and human operators.

## Proposed Solution

Amend Phase 8.5 in the plan:

1. Add `live_trading_paused_at TIMESTAMPTZ` column to the `strategy_user_strategies` table in the Phase 2 migration (set to `NOW()` when `live_trading_paused` is set to `true`, null when unpaused)
2. Return `paused_at` and `suggested_action: "unpause_strategy"` in the Phase 8.5 response

## Acceptance Criteria

- [ ] Phase 8.5 response includes `paused_at` (ISO 8601 or null) and `suggested_action: "unpause_strategy"`
- [ ] `live_trading_paused_at` column exists in the strategy table (either added to Phase 2 migration or documented as a follow-up with null fallback)
- [ ] Plan documents what `suggested_action` values are valid (string literal set, not free-form)

## Work Log

- 2026-03-03: Finding from agent-native-reviewer (P1-Finding 1) during plan review.
