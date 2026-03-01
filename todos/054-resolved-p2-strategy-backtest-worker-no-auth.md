---
status: pending
priority: p2
issue_id: "054"
tags: [code-review, security, edge-functions, backtest]
dependencies: []
---

# 054 — strategy-backtest-worker Deployed with verify_jwt=false and No Key-Based Auth

## Problem Statement
`strategy-backtest-worker/index.ts` is deployed with `verify_jwt = false` in `config.toml` and ignores the request entirely (its `serve` callback takes no `req` parameter). Any caller who can reach the function URL can trigger job processing — and combined with the ability to queue jobs via `strategy-backtest` (which also has weak auth), an attacker can chain queue-then-trigger attacks.

## Findings
- `supabase/config.toml` line 32: `[functions.strategy-backtest-worker]` with `verify_jwt = false`
- `strategy-backtest-worker/index.ts` line 605: `serve(async (): Promise<Response> => {` — no `req` parameter, ignores all headers
- Function uses service role client to claim and process pending backtest jobs
- Compare: `run-backfill-worker` correctly validates `X-SB-Gateway-Key` (lines 35-57)

## Proposed Solutions

### Option A: Add gateway key check (Recommended)
Follow `run-backfill-worker` pattern:
```typescript
serve(async (req: Request): Promise<Response> => {
  const gatewayKey = Deno.env.get('SB_GATEWAY_KEY');
  if (!gatewayKey) return new Response('Server misconfiguration', { status: 500 });
  const callerKey = req.headers.get('X-SB-Gateway-Key');
  if (callerKey !== gatewayKey) return new Response('Unauthorized', { status: 401 });
  // ...existing logic
});
```
- Effort: Small (30 minutes)
- Risk: Low

### Option B: Trigger via internal Supabase cron instead of public endpoint
Make it a pg_cron or Supabase scheduled function rather than an HTTP endpoint.
- Effort: Medium
- Risk: Low

## Recommended Action
Option A immediately; Option B as longer-term architectural improvement.

## Technical Details
- **Affected files:** `supabase/functions/strategy-backtest-worker/index.ts`, `supabase/config.toml`

## Acceptance Criteria
- [ ] Worker validates X-SB-Gateway-Key header
- [ ] Requests without valid key return 401
- [ ] Fail-close if SB_GATEWAY_KEY not configured
- [ ] `backtest-strategy` still triggers worker correctly (passes key in internal call)

## Work Log
- 2026-03-01: Identified by security-sentinel review agent (HIGH-05)
