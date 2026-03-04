---
status: pending
priority: p2
issue_id: "135"
tags: [code-review, live-trading, agent-native, circuit-breaker, api-contract]
dependencies: []
---

# Circuit breaker responses omit blocking reason and values — agents cannot explain the block to users

## Problem Statement

When a circuit breaker fires (market_hours, daily_loss, max_positions, position_size_cap), the executor returns `{ type: "circuit_breaker", rule: "daily_loss" }` but does not include the `reason` string or the actual values that triggered the block (e.g., current daily P&L vs. the limit, current position count vs. max). The `reason` field is available on the `CircuitBreakerResult` type internally (lines 90-96 of `tradestation-client.ts`) but is not propagated to the API response. An agent receiving `{ type: "circuit_breaker", rule: "daily_loss" }` can only say "daily loss limit hit" — it cannot say "you've lost $150 of your $500 daily limit."

## Findings

Agent-Native Reviewer, Warning #7.

## Proposed Solutions

Option A (Recommended): Pass the `reason` string from `CircuitBreakerResult` through to the `LiveExecutionError` discriminated union's `circuit_breaker` variant. Include the current value and limit in the reason message (e.g., "Daily loss -$150 exceeds limit -$100"). Effort: Small.

## Acceptance Criteria

- [ ] Circuit breaker errors include a `reason` field with human-readable context
- [ ] The reason includes the current value and the configured limit where applicable
- [ ] All four circuit breaker rules (market_hours, daily_loss, max_positions, position_size_cap) include reasons
