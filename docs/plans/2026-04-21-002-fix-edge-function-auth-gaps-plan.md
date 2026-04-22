---
title: "fix: Close Edge Function auth gaps and CORS inconsistencies"
type: fix
status: completed
date: 2026-04-21
origin: docs/brainstorms/2026-04-21-unified-backend-rationalization-brainstorm.md
---

# fix: Close Edge Function Auth Gaps and CORS Inconsistencies

## Overview

Fix 5 security gaps discovered during the backend rationalization brainstorm review: two Edge Functions with `verify_jwt=false` and no compensating auth control (ga-strategy, get-unified-validation), one function with wildcard CORS (run-backfill-worker), one function with ambiguous optional auth (strategies), and undocumented SB_GATEWAY_KEY rotation/scoping.

## Problem Frame

Several Edge Functions bypass JWT verification (`verify_jwt=false` in `supabase/config.toml`) for legitimate reasons (cron-triggered jobs, anon-key client access), but two of them lack any compensating authentication control. This means any unauthenticated caller on the public internet can invoke `ga-strategy` (triggering expensive GA optimization runs) and `get-unified-validation` (reading ML forecast validation scores). These are real, exploitable vulnerabilities — not theoretical concerns. (see origin: `docs/brainstorms/2026-04-21-unified-backend-rationalization-brainstorm.md`, Security Issues Found During Review section)

## Requirements Trace

- S1. `ga-strategy` must enforce SB_GATEWAY_KEY for all requests (matches run-backfill-worker pattern)
- S2. `get-unified-validation` must enforce authentication — either re-enable JWT verification or add gateway-key enforcement
- S3. `run-backfill-worker` must use shared `cors.ts` CORS handler instead of wildcard `*`
- S4. `strategies` auth model must be explicitly documented and any RLS bypass with `user_id=null` must be safe
- S5. Create an auth matrix document listing every `verify_jwt=false` function and its compensating control

## Scope Boundaries

- **In scope:** Auth enforcement for ga-strategy and get-unified-validation, CORS fix for run-backfill-worker, strategies auth audit, auth matrix documentation
- **Out of scope:** SB_GATEWAY_KEY rotation mechanism (future work), service-role key removal from strategies (requires RLS redesign), full API registry (Phase 2 of rationalization)
- **Non-goal:** Changing auth model for functions that already have correct enforcement (ingest-live, intraday-live-refresh, strategy-backtest-worker, train-model)

## Context & Research

### Relevant Code and Patterns

- `supabase/functions/run-backfill-worker/index.ts` lines 30-60 — canonical SB_GATEWAY_KEY enforcement pattern: check env exists, case-insensitive header parse, strict equality, 401 on mismatch
- `supabase/functions/_shared/cors.ts` — `getCorsHeaders(origin)` with origin allowlist
- `supabase/functions/ingest-live/index.ts` — another example of correct gateway-key enforcement
- `supabase/config.toml` — lists all `verify_jwt=false` functions

**Functions with `verify_jwt=false` (from config.toml):**
- `ga-strategy` — NO gateway-key check (vulnerable)
- `get-unified-validation` — NO auth check (vulnerable)
- `options-chain` — client-facing, anon-key access (by design)
- `strategies` — optional Bearer token, service-role key (ambiguous)
- `strategy-backtest` — client-facing (needs verification)
- `strategy-backtest-worker` — HAS gateway-key (correct)
- `chart` — client-facing, anon-key access (by design)
- `intraday-live-refresh` — HAS gateway-key (correct)

### Institutional Learnings

- `apikey` header = anon key (Supabase routing), `Authorization` header = user JWT (auth). Never mix. (from `docs/solutions/integration-issues/backtest-auth-api-type-boundary-p1-bugs.md`)
- Auth is a class-level concern: grep all methods in a service for the endpoint URL and verify `Authorization` is set identically across verbs. (same source)

## Key Technical Decisions

- **Gateway-key for cron-only functions:** `ga-strategy` and `get-unified-validation` are invoked by scheduled jobs, not clients. Adding SB_GATEWAY_KEY enforcement (matching existing run-backfill-worker pattern) is the simplest fix that prevents public access while keeping cron jobs working.
- **get-unified-validation is client-facing — use `verify_jwt=true`:** Confirmed via `client-macos/SwiftBoltML/Services/APIClient.swift` line 1240 which calls `functionURL("get-unified-validation")`. Adding gateway-key would break the macOS app. Set `verify_jwt=true` in config.toml. Also add CORS handling (currently missing from this function entirely).
- **Auth matrix as living doc:** Create `docs/AUTH_MATRIX.md` documenting every `verify_jwt=false` function. This is a stepping stone toward the full API registry (R5 from rationalization Phase 2).

## Open Questions

### Resolved During Planning

- **What is the canonical gateway-key pattern?** `run-backfill-worker/index.ts` lines 30-60: read `SB_GATEWAY_KEY` from env, parse `authorization` header, compare with strict equality, return 401 on mismatch.
- **Which functions are already correctly protected?** `intraday-live-refresh` and `strategy-backtest-worker` have gateway-key enforcement with `verify_jwt=false`. `ingest-live` and `train-model` are protected by `verify_jwt=true` (Supabase default — absent from config.toml). `strategy-backtest` has `verify_jwt=false` but implements manual `getUser()` + 401 enforcement in code (lines 23-28).

### Deferred to Implementation

- Exact wording for 401 error response body — match existing pattern from run-backfill-worker.
- Whether `_shared/cors.ts` `getCorsHeaders()` needs to include `x-sb-gateway-key` in Allow-Headers (run-backfill-worker currently includes it in its local corsHeaders but the shared function does not).

## Implementation Units

- [x] **Unit 1: Add SB_GATEWAY_KEY enforcement to ga-strategy**

**Goal:** Prevent unauthenticated public access to ga-strategy.

**Requirements:** S1

**Dependencies:** None

**Files:**
- Modify: `supabase/functions/ga-strategy/index.ts`
- Test: `supabase/functions/ga-strategy/index_test.ts` (create if absent)

**Approach:**
- Add the SB_GATEWAY_KEY enforcement block from run-backfill-worker (lines 30-60) immediately after the CORS OPTIONS check in the serve handler.
- Return 401 with JSON error body on key mismatch.
- **Critical prerequisite:** No GitHub Actions workflow currently passes SB_GATEWAY_KEY (grep confirms zero matches in `.github/workflows/`). Before deploying the function fix, identify the workflow that calls ga-strategy, add `SB_GATEWAY_KEY` to repo secrets, and inject it as `Authorization: Bearer ${{ secrets.SB_GATEWAY_KEY }}` in the HTTP call. Deploy workflow change BEFORE or simultaneously with the function change.
- Update `supabase/config.toml` comment for ga-strategy from misleading "Auth enforced at the job queue level" to accurate "Auth enforced inside function via X-SB-Gateway-Key".

**Patterns to follow:**
- `supabase/functions/run-backfill-worker/index.ts` lines 30-60 — exact pattern to replicate

**Test scenarios:**
- Happy path: Request with valid SB_GATEWAY_KEY header → function executes normally
- Error path: Request with no Authorization header → 401 Unauthorized
- Error path: Request with invalid/wrong key → 401 Unauthorized
- Edge case: OPTIONS preflight request → CORS response (no auth check)
- Integration: Verify the GitHub Actions workflow that calls ga-strategy passes the key

**Verification:**
- `curl` to the function without auth returns 401
- Cron job continues to work with the gateway key

---

- [x] **Unit 2: Add auth enforcement to get-unified-validation**

**Goal:** Prevent unauthenticated public access to ML validation scores.

**Requirements:** S2

**Dependencies:** None (parallel with Unit 1)

**Files:**
- Modify: `supabase/functions/get-unified-validation/index.ts`
- Test: `supabase/functions/get-unified-validation/index_test.ts` (create if absent)

**Approach:**
- RESOLVED: This function IS client-facing — `APIClient.swift:1240` calls it directly. Do NOT add gateway-key.
- Set `verify_jwt=true` in `supabase/config.toml` for `get-unified-validation`.
- Add CORS handling: import `handleCorsOptions`, `getCorsHeaders` from `_shared/cors.ts`, add OPTIONS preflight handler, use `getCorsHeaders(origin)` on all responses. Currently this function has zero CORS headers — browser requests will fail without this.
- Verify React frontend also sends proper auth (grep `frontend/src/` for this endpoint).

**Patterns to follow:**
- `supabase/functions/ga-strategy/index.ts` — CORS import pattern (handleCorsOptions, getCorsHeaders)
- `supabase/config.toml` `verify_jwt=true` setting

**Test scenarios:**
- Happy path: Authorized request → returns validation data
- Error path: Unauthenticated request → 401
- Edge case: Request with anon key but no JWT (if verify_jwt=true) → depends on Supabase SDK behavior
- Integration: Verify all callers (cron or client) still work after enforcement

**Verification:**
- Unauthenticated `curl` returns 401
- Existing callers continue to receive data

---

- [x] **Unit 3: Fix wildcard CORS on run-backfill-worker**

**Goal:** Replace hardcoded `Access-Control-Allow-Origin: *` with shared CORS handler.

**Requirements:** S3

**Dependencies:** None (parallel with Units 1-2)

**Files:**
- Modify: `supabase/functions/run-backfill-worker/index.ts`

**Approach:**
- Replace the inline `corsHeaders` object (line 13) with import and call to `getCorsHeaders(req.headers.get("origin"))` from `_shared/cors.ts`.
- Remove the local `corsHeaders` constant.
- Update all references to `corsHeaders` in the response headers to use the shared function's return value.

**Patterns to follow:**
- `supabase/functions/_shared/cors.ts` — `getCorsHeaders()` / `handleCorsOptions()` pattern used by all other functions

**Test scenarios:**
- Happy path: Request from allowed origin → correct CORS headers returned
- Error path: Request from disallowed origin → no `Access-Control-Allow-Origin` header (or restrictive)
- Edge case: OPTIONS preflight from allowed origin → 204 with correct headers
- Integration: Gateway-key enforcement still works after CORS change

**Verification:**
- No wildcard `*` in response headers
- Existing cron callers still work (they don't rely on CORS)

---

- [x] **Unit 4: Audit and document strategies auth model**

**Goal:** Verify the strategies endpoint auth model is safe and document the decision.

**Requirements:** S4

**Dependencies:** None (parallel)

**Files:**
- Modify: `supabase/functions/strategies/index.ts` (add comments documenting auth model, possibly tighten)

**Approach:**
- Audit: Read strategies/index.ts auth handling. Document why optional Bearer token + service-role client is used.
- Verify: With `user_id=null`, confirm the anon RLS policy (`20260222150000_allow_anon_strategies.sql`) cannot leak other users' strategies.
- If safe: Add inline documentation explaining the auth model and why service-role is used.
- If unsafe: Add required Bearer token enforcement for mutation routes (POST/PUT/DELETE), keeping GET as optional auth.

**Patterns to follow:**
- `docs/solutions/integration-issues/backtest-auth-api-type-boundary-p1-bugs.md` — apikey vs Bearer token conventions

**Test scenarios:**
- Happy path: Authenticated user → sees only their strategies
- Happy path: Unauthenticated user → sees only anonymous strategies (user_id IS NULL)
- Error path: Unauthenticated POST → verify whether it creates strategy with user_id=null (desired?) or is rejected
- Edge case: Malformed Bearer token → user_id extraction fails → verify fallback behavior

**Verification:**
- Auth model is documented in code comments
- RLS policy confirmed safe for the null-user-id case
- No strategy data leakage between users

---

- [x] **Unit 5: Create auth matrix document**

**Goal:** Document every `verify_jwt=false` function and its compensating control.

**Requirements:** S5

**Dependencies:** Units 1-4 (needs the fixes applied to document correct state)

**Files:**
- Create: `docs/AUTH_MATRIX.md`
- Reference: `supabase/config.toml`

**Approach:**
- List every function from config.toml with `verify_jwt=false`.
- For each: state the auth mechanism (gateway-key, anon-key client, optional Bearer, etc.), who calls it (cron, client, both), and the rationale for disabling JWT.
- Include functions with `verify_jwt=true` (default) as a brief "protected by Supabase JWT" section.
- This is a living document — updated when functions are added or auth changes.

**Test expectation:** none — pure documentation with no behavioral change.

**Verification:**
- Every function in config.toml is represented in the matrix
- Each entry has: function name, verify_jwt setting, compensating control, caller type, rationale

## System-Wide Impact

- **Interaction graph:** ga-strategy is called by a GitHub Actions workflow. get-unified-validation may be called by clients or cron. Changes to auth enforcement must not break callers.
- **Error propagation:** New 401 responses must return JSON error bodies matching the existing pattern so callers can parse them.
- **API surface parity:** If get-unified-validation is client-facing, both React and Swift clients must be updated to send proper auth headers.
- **Unchanged invariants:** chart, options-chain, and other client-facing functions with verify_jwt=false remain unchanged — they are correctly accessible via anon key.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| ga-strategy cron caller doesn't send gateway key | Verify the GitHub Actions workflow passes SB_GATEWAY_KEY before deploying |
| get-unified-validation has unknown client callers | Grep both clients before choosing auth mechanism |
| strategies RLS policy for null user_id leaks data | Read the migration SQL and test with null user_id query |
| Deploying auth changes breaks existing callers | Deploy one function at a time, verify each before proceeding |

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-21-unified-backend-rationalization-brainstorm.md](docs/brainstorms/2026-04-21-unified-backend-rationalization-brainstorm.md) — Security Issues Found During Review section
- Institutional learnings: `docs/solutions/integration-issues/backtest-auth-api-type-boundary-p1-bugs.md` (apikey vs Bearer conventions)
- Institutional learnings: `docs/solutions/security-issues/swiftui-credential-and-injection-hardening.md` (credential management)
- Canonical pattern: `supabase/functions/run-backfill-worker/index.ts` lines 30-60
