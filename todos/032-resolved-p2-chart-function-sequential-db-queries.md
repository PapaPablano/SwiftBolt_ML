---
status: pending
priority: p2
issue_id: "032"
tags: [code-review, performance, edge-functions, chart]
dependencies: ["028"]
---

# 032 — /chart Makes 7 Sequential DB Queries That Should Run in Parallel

## Problem Statement
The `chart` Edge Function awaits 7 database round trips in strict serial order after symbol lookup. Queries 2-7 are fully independent and could run in parallel. At 20-50ms per query, six unnecessary serial waits add 120-300ms to every chart request — the highest-frequency endpoint in the system.

## Findings
- `supabase/functions/chart/index.ts` lines 231-451:
  1. Symbol lookup (must be first — provides symbol_id)
  2-8. `get_chart_data_v2`, `ml_forecasts_intraday`, `latest_forecast_summary`, `options_ranks`, `is_market_open`, `corporate_actions`, `job_runs` — all serial, all independent

## Proposed Solutions

### Option A: Promise.all after symbol lookup (Recommended)
```typescript
const symbolData = await resolveSymbol(supabase, symbol);
const [bars, forecast, optionsRanks, marketOpen, corpActions, activeJobs] =
  await Promise.all([
    getChartData(...), getForecast(...), getOptionsRanks(...),
    getMarketOpen(...), getCorporateActions(...), getActiveJobs(...)
  ]);
```
- Effort: Small (2-3 hours)
- Risk: Low

## Recommended Action
Option A.

## Technical Details
- **Affected files:** `supabase/functions/chart/index.ts`

## Acceptance Criteria
- [ ] Chart response time reduced by 120-300ms
- [ ] 6 independent queries run in parallel after symbol lookup
- [ ] Chart response data unchanged

## Work Log
- 2026-03-01: Identified by performance-oracle review agent (highest-leverage backend fix)
