---
status: pending
priority: p3
issue_id: "051"
tags: [code-review, performance, edge-functions]
dependencies: []
---

# 051 — multi-leg-detail Makes 4 Sequential SELECT * Queries (Should Be Parallel)

## Problem Statement
`multi-leg-detail/index.ts` makes 4 sequential database calls with `SELECT *` on options_strategies, options_legs, options_multi_leg_alerts, and options_strategy_metrics. Queries 2-4 are independent after strategyId is known. Six unnecessary serial waits add 60-150ms to the detail endpoint.

## Findings
- `multi-leg-detail/index.ts` lines 75-130: four sequential awaited `SELECT *` queries
- Queries 2, 3, 4 have no dependency on each other

## Proposed Solutions
```typescript
const strategy = await getStrategy(supabase, strategyId);
const [legs, alerts, metrics] = await Promise.all([
  getLegs(supabase, strategyId),
  getAlerts(supabase, strategyId),
  getMetrics(supabase, strategyId),
]);
```
Also narrow each `SELECT *` to needed columns.
- Effort: Small (1 hour)
- Risk: None

## Acceptance Criteria
- [ ] Queries 2-4 run in parallel via Promise.all
- [ ] Only needed columns fetched (no SELECT *)
- [ ] Response data unchanged

## Work Log
- 2026-03-01: Identified by performance-oracle review agent
