---
status: pending
priority: p1
issue_id: "086"
tags: [code-review, live-trading, concurrency, oauth, security]
dependencies: []
---

# Token refresh race condition — concurrent refresh invalidates second caller's refresh token

## Problem Statement

When two concurrent invocations of the live executor both read an expired `broker_tokens` row, both call the TradeStation refresh endpoint with the same `refresh_token`. The first successful response invalidates the refresh token on TradeStation's side (OAuth 2.0 refresh tokens are single-use). The second invocation's refresh call receives a 400/401. That invocation now holds a stale access token and an invalidated refresh token — the user is permanently locked out until they complete the OAuth flow again manually.

This is especially dangerous because: (a) multiple concurrent invocations are explicitly supported via the semaphore pattern, and (b) once a refresh token is invalidated there is no automated recovery path.

## Findings

**Architecture Strategist (P1):** "Two concurrent invocations both read an expired token within milliseconds of each other — entirely plausible when multiple symbols are being evaluated in a batch — both will call TS_AUTH_URL with the same refresh_token. Recovery requires manual re-authorization."

**Performance Oracle (P1-B):** "Token refresh write contention → use optimistic locking with `WHERE expires_at = $original`."

**Current plan (Phase 3a):** `ensureFreshToken()` is a read-then-write with no atomicity guard. If `expires_at < now + 5 minutes`, call refresh endpoint and UPDATE row. No concurrency protection.

## Proposed Solutions

### Option A: Optimistic locking with conditional UPDATE (Recommended)
Use a conditional UPDATE as the concurrency guard:
```sql
UPDATE broker_tokens SET access_token=$new, refresh_token=$new_refresh, expires_at=$new_exp
WHERE user_id=$uid AND provider='tradestation' AND expires_at = $old_expires_at
RETURNING *
```
If zero rows are updated, another invocation already refreshed — re-read the row and use the already-refreshed token. This matches the existing optimistic locking pattern in `paper-trading-executor` for position closes.

**Pros:** No external locks needed, follows established codebase pattern, atomic at DB level
**Cons:** Requires re-read on contention (extra DB round trip)
**Effort:** Small
**Risk:** Low

### Option B: Postgres advisory lock
`SELECT pg_try_advisory_xact_lock(user_id hash)` before entering the refresh path.

**Pros:** Prevents any concurrent refresh attempt
**Cons:** Holds lock for duration of HTTP call to TradeStation (can block Edge Function slots). Requires raw SQL.
**Effort:** Medium
**Risk:** Medium (lock contention at scale)

### Option C: Supabase Realtime presence channel for distributed lock
Use a presence channel as a distributed mutex.

**Pros:** Works across Edge Function instances
**Cons:** Complex, adds Realtime dependency, overkill for this use case
**Effort:** Large
**Risk:** High

## Recommended Action

Implement Option A. The plan's `ensureFreshToken()` in Phase 3a and `_shared/tradestation-client.ts` must perform the conditional UPDATE. If the update affects zero rows, re-read `broker_tokens` and return the current token (another invocation already refreshed it).

## Technical Details

**Affected files:**
- `supabase/functions/_shared/tradestation-client.ts` — `ensureFreshToken()` / `refreshBrokerToken()`
- `docs/plans/2026-03-03-feat-live-trading-executor-tradestation-plan.md` — Phase 3a code spec

**Pseudocode:**
```typescript
async function ensureFreshToken(supabase, userId): Promise<BrokerToken> {
  const token = await getBrokerToken(supabase, userId);
  if (Date.now() < new Date(token.expires_at).getTime() - 5 * 60 * 1000) {
    return token; // still valid
  }
  // Attempt refresh
  const refreshed = await callTradeStationRefresh(token.refresh_token);
  // Conditional UPDATE — only succeeds if this invocation wins the race
  const { data, count } = await supabase
    .from('broker_tokens')
    .update({ access_token: refreshed.access_token, refresh_token: refreshed.refresh_token, expires_at: refreshedExpiresAt })
    .eq('user_id', userId)
    .eq('expires_at', token.expires_at)  // <-- optimistic lock condition
    .select();
  if (count === 0) {
    // Another invocation already refreshed — return the fresh token
    return await getBrokerToken(supabase, userId);
  }
  return data[0];
}
```

## Acceptance Criteria

- [ ] `ensureFreshToken()` uses conditional UPDATE with `WHERE expires_at = $old_expires_at`
- [ ] If UPDATE returns 0 rows, re-reads and returns current token (not cached stale value)
- [ ] Two concurrent invocations with an expired token never both call the TradeStation refresh endpoint
- [ ] Unit test: mock concurrent calls — assert TradeStation refresh called exactly once

## Work Log

- 2026-03-03: Finding created from Architecture Strategist (P1) and Performance Oracle (P1-B).
