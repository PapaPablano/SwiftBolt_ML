---
status: resolved
priority: p1
issue_id: "026"
tags: [code-review, security, performance, edge-functions]
dependencies: []
---

# 026 — chart-read Has Hardcoded Debug Telemetry Firing on Every Request

## Problem Statement
`supabase/functions/chart-read/index.ts` makes up to 10 fire-and-forget POST requests to `http://127.0.0.1:7242/ingest/c38aa5cd-6eb1-473a-b1f0-0fdd8c2a440d` on every chart request. These are debug agent log calls left in production. They add network latency per request and send internal operational data (symbol names, error messages, stack traces) to an address that may resolve unpredictably in the edge runtime.

## Findings
- Lines 723-737, 779-794, 809-833, 854-877: `// #region agent log` blocks with fetch calls
- 5 timeframes × 2 log calls each = up to 10 network attempts per request
- `.catch(() => {})` suppresses errors silently — invisible latency
- Payload contains: symbol, timeframe, bar data shape, error messages, stack traces

## Proposed Solutions

### Option A: Delete All agent log Regions (Recommended)
Remove all `#region agent log ... #endregion` blocks entirely.
- Effort: XSmall (30 minutes)
- Risk: None — this is debug code that must not be in production

### Option B: Gate Behind Environment Variable
Wrap calls in `if (Deno.env.get('ENABLE_AGENT_TELEMETRY') === 'true')`.
- Effort: XSmall
- Risk: Low (could be accidentally enabled)

## Recommended Action
Option A. Debug code does not belong in production.

## Technical Details
- **Affected files:** `supabase/functions/chart-read/index.ts` (lines 723-877)

## Acceptance Criteria
- [x] No fetch calls to 127.0.0.1 in chart-read
- [x] chart-read response time improved (10 fewer network attempts per request)
- [x] No internal data sent to unresolved addresses

## Work Log
- 2026-03-01: Identified by architecture-strategist review agent
- 2026-03-01: Resolved — deleted all 4 `#region agent log ... #endregion` blocks (enqueue loop entry, before-rpc, after-rpc, and catch blocks)
