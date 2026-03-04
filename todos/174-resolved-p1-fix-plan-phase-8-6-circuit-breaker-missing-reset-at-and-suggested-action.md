---
status: resolved
priority: p1
issue_id: "174"
tags: [plan-review, live-trading, agent-native, api-design, circuit-breaker]
dependencies: []
---

# Fix Plan Phase 8.6: Circuit breaker response missing `reset_at` and `suggested_action` — agent cannot determine retry strategy

## Problem Statement

The Phase 8.6 fix adds `reason` and `rule` to the circuit breaker response. This is an improvement, but the four circuit breaker rules have completely different recovery timelines that require different agent behavior. Without `reset_at` (when the block lifts) and `suggested_action` (what the agent should do), an agent receiving a circuit breaker rejection cannot choose the correct retry strategy and will either retry too early (wasting API calls) or wait unnecessarily long.

## Findings

**Agent-Native Reviewer (P1-Finding 2):**

The plan's proposed response shape:
```typescript
{ success: false, action: "circuit_breaker", rule: result.rule, reason: result.reason }
```

The four circuit breaker rules require completely different agent responses:

| Rule | Recovery timeline | Agent action |
|------|------------------|--------------|
| `market_hours` | Deterministic — next market open (9:30 ET) | Wait until `reset_at`, then retry |
| `daily_loss` | Midnight ET on current trading day | Wait until `reset_at`, then retry |
| `max_positions` | Non-deterministic — lifts when a position closes | Poll positions endpoint or wait |
| `position_size_cap` | Immediate — reduce `live_max_position_pct` | Reduce position size in strategy config |

Without `reset_at` and `suggested_action`, an agent receiving `rule: "market_hours"` cannot compute the retry time. An agent receiving `rule: "position_size_cap"` does not know it could resolve the block immediately with a config change.

**Key insight:** `checkMarketHours()` at lines 325–348 of `live-trading-executor/index.ts` already computes ET time and knows when the market opens — it just doesn't return `nextOpen`. Surfacing it in the circuit breaker response costs one additional field in the existing function.

**Required response shape:**

```typescript
{
  success: false,
  action: "circuit_breaker",
  rule: result.rule,
  reason: result.reason,
  reset_at: computeResetTimestamp(result.rule),
  // ISO 8601 timestamp or null (null for max_positions where reset is non-deterministic)
  suggested_action: circuitBreakerSuggestedAction(result.rule),
  // "wait_for_market_open" | "wait_for_daily_reset" | "wait_for_position_close" | "reduce_position_size"
}
```

```typescript
function computeResetTimestamp(rule: string): string | null {
  switch (rule) {
    case "market_hours": return nextMarketOpen().toISOString();     // from checkMarketHours logic
    case "daily_loss":   return endOfTradingDay().toISOString();    // midnight ET
    case "max_positions": return null;                              // depends on position closes
    case "position_size_cap": return null;                          // immediate if config changed
    default: return null;
  }
}

function circuitBreakerSuggestedAction(rule: string): string {
  switch (rule) {
    case "market_hours": return "wait_for_market_open";
    case "daily_loss":   return "wait_for_daily_reset";
    case "max_positions": return "wait_for_position_close";
    case "position_size_cap": return "reduce_position_size";
    default: return "contact_support";
  }
}
```

## Proposed Solution

Amend Phase 8.6 in the plan to require `reset_at` and `suggested_action` fields in the circuit breaker response. Extract `nextMarketOpen()` from `checkMarketHours()` as a reusable utility function so it can be used in both the check logic and the response payload.

## Acceptance Criteria

- [x] All four circuit breaker rules include `reset_at` (ISO 8601 or null) in the response
- [x] All four circuit breaker rules include `suggested_action` (typed string literal) in the response
- [x] `nextMarketOpen()` is extracted as a reusable utility from `checkMarketHours()`
- [x] Plan documents the valid `suggested_action` values and their meanings
- [x] `reset_at` is null for `max_positions` and `position_size_cap` (non-deterministic reset)

## Work Log

- 2026-03-03: Finding from agent-native-reviewer (P1-Finding 2) during plan review. The plan's proposed fix adds `rule` and `reason` but omits the recovery timing and suggested action that make circuit breaker responses agent-actionable.
- 2026-03-03: Resolved — plan amended with reset timing and suggested actions, acceptance criteria updated.
