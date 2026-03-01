---
status: resolved
priority: p3
issue_id: "049"
tags: [code-review, security, edge-functions, configuration]
dependencies: []
---

# 049 — trigger-backfill Key Fallback Chain Can Promote Service Role Key to Auth Token

## Problem Statement
`trigger-backfill/index.ts` falls back to the service role key when `SB_GATEWAY_KEY` is not configured. This means the service role key is accepted as an inbound auth credential — elevating it to a role it shouldn't serve.

## Findings
- `trigger-backfill/index.ts` lines 20-32: fallback chain ends with `supabaseServiceKey`
- If SB_GATEWAY_KEY not set: service role key becomes the accepted inbound token
- Service role key has broader privileges than a dedicated gateway key should have

## Proposed Solutions
Fail-close pattern (matches `run-backfill-worker`):
```typescript
const gatewayKey = Deno.env.get('SB_GATEWAY_KEY');
if (!gatewayKey) {
  console.error('SB_GATEWAY_KEY not configured');
  return new Response('Server misconfiguration', { status: 500 });
}
```
- Effort: XSmall (30 minutes)
- Risk: Low (requires SB_GATEWAY_KEY to be set in production — confirm it is)

## Acceptance Criteria
- [x] If SB_GATEWAY_KEY not configured, function returns 500 with log
- [x] No fallback to service role key as auth token
- [ ] Production has SB_GATEWAY_KEY configured

## Work Log
- 2026-03-01: Identified by security-sentinel review agent (LOW-04)
- 2026-03-01: Resolved — replaced the 4-step fallback chain (`SB_GATEWAY_KEY ?? ANON_KEY ?? SUPABASE_ANON_KEY ?? supabaseServiceKey`) with a fail-closed pattern that returns HTTP 500 if SB_GATEWAY_KEY is not set. Also simplified `expectedCallerKey` to directly use `gatewayKey`.
