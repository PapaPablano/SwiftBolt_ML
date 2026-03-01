---
status: pending
priority: p2
issue_id: "033"
tags: [code-review, performance, edge-functions, forecasts]
dependencies: []
---

# 033 — get-multi-horizon-forecasts Makes N Serial RPC Calls (N+1 Pattern)

## Problem Statement
`get-multi-horizon-forecasts/index.ts` loops over horizons and serially awaits `get_forecast_cascade` RPC for each. For 4 daily horizons (1D/5D/10D/20D) this is 4 serial round trips adding 120-320ms of pure sequencing overhead.

## Findings
- `supabase/functions/get-multi-horizon-forecasts/index.ts` lines 453-473: `for (const horizon of horizons) { await supabase.rpc("get_forecast_cascade", ...) }`
- Await inside for-loop = serial execution
- Grows linearly as more horizons are added (30D, 60D etc.)

## Proposed Solutions

### Option A: Promise.all (Recommended)
```typescript
const results = await Promise.all(
  horizons.map(horizon =>
    supabase.rpc("get_forecast_cascade", { p_symbol: symbol, p_horizon: horizon })
  )
);
```
- Effort: XSmall (30 minutes)
- Risk: None

### Option B: Batch RPC
Create `get_forecast_cascade_batch(p_symbol, p_horizons[])` returning all at once.
- Effort: Medium (requires migration)
- Risk: Low

## Recommended Action
Option A immediately; Option B as long-term optimization.

## Technical Details
- **Affected files:** `supabase/functions/get-multi-horizon-forecasts/index.ts`

## Acceptance Criteria
- [ ] Cascade RPC calls run in parallel
- [ ] Response time reduced by 90-240ms for 4-horizon requests
- [ ] Response data unchanged

## Work Log
- 2026-03-01: Identified by performance-oracle review agent
