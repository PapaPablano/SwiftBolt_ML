---
status: pending
priority: p2
issue_id: "184"
tags: [plan-review, live-trading, frontend, api-design]
dependencies: []
---

# Fix Plan Phase 8.5: `strategy_paused` structured response has no identified frontend consumer

## Problem Statement

Phase 8.5 improves the paused strategy response from `{ action: "no_action" }` to `{ action: "skipped", reason: "strategy_paused" }`. However, neither `LiveTradingDashboard.tsx` nor `LiveTradingStatusWidget.tsx` calls the executor's execute endpoint — execution is triggered by an external cron or webhook. The `results[]` array from the execution response is not read by any visible frontend component. The Phase 8.5 improvement has no consumer and delivers value only as a log signal unless a consumer is built or identified.

## Findings

**Spec-Flow Analyzer (GAP-P2-2):**

Grep of `frontend/src/`:
- `liveTradingApi.execute` is defined in `strategiesApi.ts`
- Neither `LiveTradingDashboard.tsx` nor `LiveTradingStatusWidget.tsx` imports or calls `liveTradingApi.execute`

The executor returns:
```typescript
return new Response(JSON.stringify({ success: true, results }), ...);
// results[] = [{ success: true, action: "skipped", reason: "strategy_paused", strategyId }]
```

If the caller is a cron job or webhook that discards the response body (only checks HTTP status), the `results[]` data is never read. Phase 8.5's structured paused response only helps if:
1. The cron reads `results[]` and logs it, OR
2. A frontend component calls `execute` and displays paused-strategy warnings, OR
3. An agent calls `execute` and reads the response

The plan does not identify which of these is the intended consumer.

**Recommended clarification:**

The plan should answer: "Who reads `results[]`?" If it's a Supabase cron job (SQL function), it probably discards the response. If it's an external webhook, the webhook handler needs to log or forward the paused-strategy data. If no consumer exists today, Phase 8.5's value is limited to improved log output (the structured data is still in the `console.log` that the Edge Function emits), which is still worthwhile but should be documented as such.

Additionally: if a strategy stays paused for multiple cycles, the cron will keep sending POST requests to the executor, consuming rate limit budget and DB connections for each no-op. A `results[]` consumer that detects all-skipped responses and suppresses future calls until a strategy is unpaused would meaningfully reduce waste.

## Proposed Solution

Amend Phase 8.5 in the plan to identify the caller of `liveTradingApi.execute` and document whether `results[]` is consumed. If no consumer exists, document Phase 8.5's value as "log observability only" and add a follow-up to build a consumer (cron-side log processing or frontend component).

## Acceptance Criteria

- [ ] Plan identifies who calls `liveTradingApi.execute` and whether they read `results[]`
- [ ] If no consumer exists, plan documents Phase 8.5 as log observability improvement only
- [ ] Plan optionally adds a note about rate limit waste for all-paused execution cycles
- [ ] If a UI component is expected to show paused strategy warnings, it is in scope for this PR or deferred with a clear note

## Work Log

- 2026-03-03: Finding from spec-flow-analyzer (GAP-P2-2) during plan review. The structured response improvement is valid but its value depends on whether results[] has a consumer.
