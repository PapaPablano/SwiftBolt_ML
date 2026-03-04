---
status: pending
priority: p1
issue_id: "089"
tags: [code-review, live-trading, security, oauth, rls, credentials]
dependencies: []
---

# OAuth credentials stored as plaintext + service role client bypasses RLS on broker_tokens

## Problem Statement

Two compounding security issues make broker credentials accessible to attackers. First, `access_token` and `refresh_token` are stored as plaintext TEXT columns in Postgres — anyone with SELECT access to `broker_tokens` (dashboard leak, misconfigured RLS, service role key exposure) has live credentials to place real orders on every user's brokerage account. Second, the plan uses the service role client for all DB operations (following the paper-trading-executor template), which bypasses ALL RLS policies — the `broker_tokens` RLS policies are completely inoperative for the executor.

A single bug in the service role path (e.g., using a body-supplied `userId` instead of the verified JWT claim) would expose any user's tokens to any caller.

## Findings

**Security Sentinel (SEC-01 P1):** "Both access_token and refresh_token are stored as plain TEXT. Anyone who gains SELECT access... has live credentials to submit real orders with real money on every user's brokerage account."

**Security Sentinel (SEC-02 P1):** "The plan states the executor 'reads broker_tokens table,' and the paper trading executor (which is the explicit template) uses the service role client for all DB operations. The service role key bypasses all RLS policies. The RLS policies in the migration are rendered completely inoperative for the executor."

**Paper-trading-executor template (line 884):** Uses `SUPABASE_SERVICE_ROLE_KEY` for all DB operations. The live executor must NOT copy this pattern for broker token reads.

## Proposed Solutions

### Option A: Use Supabase Vault for token columns + auth client for reads (Recommended)
Store tokens via `vault.secrets` (Supabase's pgsodium-backed encrypted column store). Store the Vault secret UUID in `broker_tokens`. Use `getSupabaseClientWithAuth(authHeader)` (anon-key client) for reading `broker_tokens` so RLS is enforced at DB level.

**Pros:** Tokens encrypted at rest by HSM-backed key. RLS enforced at DB level. Defense in depth.
**Cons:** Requires Vault setup; Vault API differs from standard table queries. Moderate complexity.
**Effort:** Medium
**Risk:** Low (after implementation)

### Option B: Encrypt tokens at application level before insert
Before inserting, encrypt with a per-user secret derived from `SUPABASE_SERVICE_ROLE_KEY + user_id`. Use `crypto.subtle` in Deno.

**Pros:** No Vault dependency, works with existing schema
**Cons:** Encryption key is still in Edge Function environment — not HSM-backed. Key management is manual.
**Effort:** Medium
**Risk:** Medium (weaker than Vault)

### Option C: Plaintext tokens (current plan) with auth client for reads
Keep plaintext tokens but switch `broker_tokens` reads from service role client to `getSupabaseClientWithAuth()` so RLS is enforced.

**Pros:** Minimal change to schema, RLS enforcement restored
**Cons:** Tokens still vulnerable to DB backup exposure
**Effort:** Small
**Risk:** Medium (tokens still in plaintext in DB backups/logs)

## Recommended Action

At minimum, implement Option C immediately (switch to auth client for broker_tokens reads). For production use with real accounts, implement Option A (Vault). Document plaintext storage as a known limitation in the migration with a `TODO: SECURITY` comment if deferring Vault to v1.1.

Additionally:
- Add an explicit assertion after token fetch: `if (tokenRow.user_id !== verifiedUserId) throw unauthorized`
- Add `REVOKE SELECT ON broker_tokens FROM anon` to the migration
- Block anon key access explicitly (related to SpecFlow concern about existing anon_strategies migration)

## Technical Details

**Affected files:**
- `supabase/migrations/20260303100000_broker_tokens.sql` — add REVOKE for anon, add Vault columns if using Option A
- `supabase/functions/live-trading-executor/index.ts` — use auth client for token reads, add user_id assertion
- `supabase/functions/_shared/tradestation-client.ts` — do not pass client_secret as function parameters

**Auth client pattern (already in codebase at `_shared/supabase-client.ts`):**
```typescript
// Use this for broker_tokens reads:
const supabaseAuth = getSupabaseClientWithAuth(req.headers.get('Authorization')!);
const tokenRow = await getBrokerToken(supabaseAuth, userId);
// Service role client stays for live_trading_positions writes only
```

**Migration addition:**
```sql
-- Block anon key from broker_tokens entirely
REVOKE ALL ON broker_tokens FROM anon;
-- Service role still works (bypasses RLS, but that's handled at app layer via user_id assertion)
```

## Acceptance Criteria

- [ ] `broker_tokens` reads use `getSupabaseClientWithAuth()`, NOT the service role client
- [ ] Explicit user_id assertion after token fetch: `assert(tokenRow.user_id === verifiedUserId)`
- [ ] `REVOKE ALL ON broker_tokens FROM anon` in migration
- [ ] If using Vault: `access_token` and `refresh_token` stored as vault secret UUIDs
- [ ] If not using Vault: `TODO: SECURITY` comment in migration documenting plaintext risk
- [ ] `TRADESTATION_CLIENT_SECRET` read inside `tradestation-client.ts` module, not passed as function parameter

## Work Log

- 2026-03-03: Finding created from Security Sentinel (SEC-01, SEC-02) combined into one actionable todo.
