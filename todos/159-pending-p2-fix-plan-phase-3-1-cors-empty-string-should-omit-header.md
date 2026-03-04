---
status: pending
priority: p2
issue_id: "159"
tags: [plan-review, live-trading, security, cors]
dependencies: []
---

# Fix Plan Phase 3.1: CORS fix should omit header for unknown origins, not return empty string

## Problem Statement

The fix plan's Phase 3.1 changes the CORS fallback from `allowed[0]` to `""` (empty string). An empty string is technically not a valid CORS grant and most browsers treat it as a failed check — but the RFC-compliant approach is to omit the `Access-Control-Allow-Origin` header entirely. Some CDN/proxy layers behave differently with a present-but-empty header vs an absent header.

Additionally, this is a systemic change across all Edge Functions (not just live trading), and the plan must audit all callers before deploying.

## Findings

**Architecture Strategist (P2-5):**

The CORS fix in `cors.ts` is consumed by every Edge Function via `getCorsHeaders`. The plan correctly identifies the bypass (echoing `allowed[0]` to unknown origins), but the proposed fix of returning `""` leaves a header with an empty value on every response to an unknown origin. RFC 6454 specifies that an absent `Access-Control-Allow-Origin` header means no grant — that's the intended semantic.

The correct fix conditionally omits the header key:

```typescript
// cors.ts — getCorsHeaders()
const headers: Record<string, string> = {
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
  "Access-Control-Max-Age": "86400",
};

if (origin && allowed.includes(origin)) {
  headers["Access-Control-Allow-Origin"] = origin;
}
// If origin not in allowlist, header is omitted entirely (no CORS grant)

return headers;
```

**Caller audit required:** Before deploying, verify that no Edge Function depends on the `allowed[0]` fallback behavior for wildcard access. Check that `ALLOWED_ORIGINS` env var is correctly configured in Supabase secrets for all environments.

## Proposed Solution

Update Phase 3.1 in the plan:

1. Change the fix from empty-string to conditional header omission (as shown above)
2. Add an explicit note: "This change affects ALL Edge Functions. Run `grep -r 'getCorsHeaders' supabase/functions/` and verify all callers handle the case where CORS headers are absent for unknown origins."
3. Add to deployment checklist: verify `ALLOWED_ORIGINS` is set in Supabase Secrets before deploying

## Acceptance Criteria

- [ ] Phase 3.1 uses conditional header omission (not empty string)
- [ ] Plan includes caller audit step before deployment
- [ ] Deployment checklist includes `ALLOWED_ORIGINS` verification

## Work Log

- 2026-03-03: Finding from architecture-strategist (P2-5) during plan review.
