---
status: resolved
priority: p1
issue_id: "168"
tags: [plan-review, live-trading, security, cors, deployment]
dependencies: []
---

# Fix Plan CORS: Staged deployment required — 20+ callers must be updated before shared utility change

## Problem Statement

The fix plan's CORS work (Phase 1.1 / #159) treats the caller audit as an informational note rather than a hard acceptance criterion. Deploying the CORS fix to `_shared/cors.ts` simultaneously with callers that still pass no `origin` argument will break every function that calls `handleCorsOptions()`, `handlePreflight()`, or `errorResponse()` — 20+ Edge Functions in production. The plan must require staged deployment: callers first, shared utility second.

## Findings

**Security Sentinel (P1-CORS Staged Deployment):**

Grep of `supabase/functions/` reveals 20+ call sites that invoke shared CORS helpers without passing `origin`:

```typescript
// Current call sites (all broken after signature change):
handleCorsOptions(req)          // should be handleCorsOptions(req, origin)
handlePreflight(req)            // should be handlePreflight(req, origin)
errorResponse("...", 400)       // should be errorResponse("...", 400, origin)
```

If `_shared/cors.ts` is updated first (to require `origin` for the allowlist check), all callers that don't pass `origin` will either:
1. Throw a TypeScript compile error (blocking deploy), OR
2. Receive `undefined` as origin → treated as unknown → CORS header may be omitted → preflight fails for all callers.

Because Supabase deploys all functions together via `supabase functions deploy`, there is no atomic "update shared + all callers in one deploy." Staging is required:

**Required deployment order:**
1. **Stage A:** Update all 20+ call sites to pass `req.headers.get("Origin")` as the `origin` argument (backward-compatible if shared utility signature is additive with default).
2. **Stage B:** Update `_shared/cors.ts` to enforce the allowlist (remove the echo-origin fallback).
3. **Stage C:** Deploy.

The plan currently has no acceptance criterion requiring Stage A to complete before Stage B is deployed. This is a P1 because mis-ordering the deploy would take all live trading Edge Functions offline for CORS preflight requests.

## Proposed Solution

Update Phase 1.1 acceptance criteria to include:

```markdown
### Acceptance Criteria — Phase 1.1 CORS Fix

- [ ] All call sites that invoke `handleCorsOptions`, `handlePreflight`, or `errorResponse`
      are updated to pass the `origin` argument before the shared utility signature changes
- [ ] Caller audit count documented: [N] functions updated
- [ ] `_shared/cors.ts` signature change deployed only after caller updates are confirmed
- [ ] Integration test: preflight from allowed origin returns correct `Access-Control-Allow-Origin`
- [ ] Integration test: preflight from disallowed origin returns 403 (no CORS headers)
```

Additionally, add a `_shared/cors.ts` shim with a default parameter so Stage A and Stage B can deploy together:

```typescript
// Transitional signature: origin defaults to "" so old callers don't crash
export function getCorsHeaders(origin: string = ""): Record<string, string> {
  // ... allowlist check
}
```

This allows all callers to be updated in one PR without requiring the shared utility to change first.

## Acceptance Criteria

- [x] Plan's Phase 3.1 adds a required acceptance criterion: caller audit must be complete before shared utility changes
- [x] Plan documents all 20 affected call sites in Phase 3.1a table and requires they be updated in the same PR
- [x] Plan notes that `supabase functions deploy` is atomic — caller updates and cors.ts fix deploy together (no transitional shim needed)
- [x] Deployment order documented in plan's Risk Analysis section and Migration Ordering section

## Work Log

- 2026-03-03: Finding from security-sentinel during plan review. Not captured in todo #159 (which addresses the echo-origin bug itself but not the staged deployment requirement).
- 2026-03-03: RESOLVED. Plan amended: Phase 3.1a added with full 20-function caller audit table, deployment pattern for each caller, acceptance criterion added to P1 section, risk analysis updated, migration ordering updated. Key insight: `supabase functions deploy` is atomic — no staged deployment needed, but all 20 caller updates must be in the same PR as the `getCorsHeaders` fix.
