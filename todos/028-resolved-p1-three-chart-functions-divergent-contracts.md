---
status: pending
priority: p1
issue_id: "028"
tags: [code-review, architecture, api-design, chart]
dependencies: []
---

# 028 — Three Coexisting Chart Functions With Divergent Contracts

## Problem Statement
Three Edge Functions independently implement chart data retrieval: `chart`, `chart-read`, and `chart-data-v2`. Each has a different response envelope, freshness SLA thresholds, RPC calls, and Deno std versions. CLAUDE.md declares `chart` as the canonical single endpoint — this rule is violated. Bug fixes must be applied three times; any client refactor must handle three response shapes.

## Findings
- `chart`: GET, uses `get_chart_data_v2` RPC, returns `{ bars[], forecast, optionsRanks, meta, freshness }`
- `chart-read`: GET or POST, uses `get_chart_data_v2_dynamic` RPC, returns `{ bars[], mlSummary, indicators, dataQuality }`, contains 10 debug telemetry calls (see #026)
- `chart-data-v2`: POST-only, returns `{ layers: { historical, intraday, forecast } }`, Deno std 0.168.0 (stale), declares `corsHeaders` at line 1669 but uses from line 621
- Freshness SLA divergence: `d1` = 24h in chart, 48h in chart-read, 72h in chart-data-v2
- `chart-data-v2` uses inline CORS and direct `createClient` rather than `_shared/`

## Proposed Solutions

### Option A: Retire chart-read and chart-data-v2, consolidate into chart (Recommended)
1. Identify unique features of `chart-read` (`dataQuality` block, `get_chart_data_v2_dynamic` RPC) and merge into `chart`
2. Redirect/remove `chart-read` and `chart-data-v2`
- Effort: Large (1-2 days)
- Risk: Medium (must audit all callers before removing)

### Option B: Feature-flag inside single function
Merge all three with a `?variant=` param.
- Effort: Large
- Risk: High (complexity explosion)

## Recommended Action
Option A, phased: retire `chart-data-v2` first (most divergent, outdated std), then absorb `chart-read` features into `chart`.

## Technical Details
- **Affected files:** `supabase/functions/chart-read/index.ts`, `supabase/functions/chart-data-v2/index.ts` (retire), `supabase/functions/chart/index.ts` (enhance)

## Acceptance Criteria
- [ ] Only `chart` function serves chart data
- [ ] `chart` includes dataQuality block from chart-read
- [ ] Consistent freshness SLA thresholds in one place
- [ ] `chart-read` and `chart-data-v2` retired
- [ ] No frontend code calls the retired endpoints

## Work Log
- 2026-03-01: Identified by architecture-strategist and API contract review agents
