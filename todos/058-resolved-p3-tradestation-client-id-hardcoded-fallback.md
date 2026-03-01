---
status: resolved
priority: p3
issue_id: "058"
tags: [code-review, security, configuration, edge-functions]
dependencies: []
---

# 058 — ts-strategies Contains Hardcoded TradeStation Client ID as Default Fallback

## Problem Statement
`ts-strategies/index.ts` uses a hardcoded TradeStation client ID as a fallback when the environment variable is not configured. If this is a real OAuth client ID, it may be usable by anyone to initiate OAuth flows impersonating the application. At minimum it sets a bad pattern of hardcoded credentials.

## Findings
- `ts-strategies/index.ts` lines 198 and 255:
  ```typescript
  const clientId = Deno.env.get('TRADESTATION_CLIENT_ID') || 'x3IYfpnSYevmXREQuW34LJUyeXaHBK'
  ```
- The fallback value appears to be a real client ID (34 chars, consistent with OAuth client ID format)
- Client IDs should be required env vars with no fallback — if unset, function should fail loudly

## Proposed Solutions

### Option A: Remove fallback, require env var (Recommended)
```typescript
const clientId = Deno.env.get('TRADESTATION_CLIENT_ID');
if (!clientId) {
  console.error('TRADESTATION_CLIENT_ID not configured');
  return errorResponse('TradeStation integration not configured', 503);
}
```
- Effort: XSmall (10 minutes)
- Risk: None (production should have it configured; if not, fail loudly)

### Option B: If this is a public/shared client ID by design
Add a code comment documenting that this is a known-public client ID for the development/sandbox environment.
- Effort: XSmall

## Recommended Action
Verify whether the hardcoded value is a production, sandbox, or public client ID. If production: rotate it and use Option A. If public sandbox: document it clearly.

## Technical Details
- **Affected files:** `supabase/functions/ts-strategies/index.ts` (lines 198, 255)

## Acceptance Criteria
- [x] No hardcoded OAuth client IDs in source
- [x] `TRADESTATION_CLIENT_ID` required env var with fail-closed behavior if missing
- [ ] If value was a real credential: confirm it has been rotated

## Work Log
- 2026-03-01: Identified by architecture-strategist and security-sentinel review agents
- 2026-03-01: Resolved — removed all 3 occurrences of the hardcoded fallback. Added `errorResponse()` helper function. The `action=exchange` and `action=refresh` blocks in `handleAuth` now return HTTP 503 via `errorResponse()` if the env var is missing. The inline token refresh in `handleExecute` now throws an Error (caught by the surrounding try/catch) if the env var is missing. Note: the hardcoded client ID `x3IYfpnSYevmXREQuW34LJUyeXaHBK` should be rotated if it was a real production credential.
