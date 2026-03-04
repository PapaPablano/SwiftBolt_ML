---
status: pending
priority: p1
issue_id: "090"
tags: [code-review, live-trading, security, rate-limiting, edge-functions]
dependencies: []
---

# In-memory rate limiter resets on Edge Function cold starts

## Problem Statement

The paper-trading-executor uses a module-scope `Map<string, { count, resetAt }>` for rate limiting. This map is lost on every Edge Function cold start (each new Deno isolate gets a fresh map). An attacker with a valid JWT can bypass the rate limit entirely by triggering cold starts (send a burst, wait for isolate to cool, repeat). For a paper trading endpoint this is annoying. For a live trading endpoint it allows unlimited real market order submissions.

## Findings

**Security Sentinel (SEC-03 P1):** "Supabase Edge Functions are stateless — each invocation may spin up a new isolate. The rateLimitMap declared at module scope is lost between cold starts. For a live trading endpoint this is a P1 vulnerability — a user (or an attacker with a stolen JWT) can submit unlimited real market orders."

**Paper-trading-executor reference (lines 169–189):** Uses exactly this pattern. The live executor plan inherits it by copying the template.

## Proposed Solutions

### Option A: Postgres-backed rate limit using a timestamp table (Recommended)
Insert a row for each request into a `live_order_rate_limits(user_id, window_start, request_count)` table. Check count within the last 60 seconds using a DB query. This works across all Edge Function invocations/cold starts/instances.

```sql
CREATE TABLE IF NOT EXISTS live_order_rate_limits (
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  window_start TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, window_start)
);
CREATE INDEX idx_rate_limits_user_recent ON live_order_rate_limits (user_id, window_start DESC);
```

```typescript
// In executor: count requests in last 60s
const { count } = await supabase
  .from('live_order_rate_limits')
  .select('*', { count: 'exact', head: true })
  .eq('user_id', userId)
  .gte('window_start', new Date(Date.now() - 60_000).toISOString());
if (count >= LIVE_RATE_LIMIT) return rateLimitError();
await supabase.from('live_order_rate_limits').insert({ user_id: userId });
```

**Pros:** Works across all instances, persistent, auditable
**Cons:** Extra DB query per invocation (~50ms)
**Effort:** Small
**Risk:** Low

### Option B: Use Supabase Edge Runtime's Deno KV (when available)
Store rate limit data in Deno KV which persists across isolate restarts.

**Pros:** Fast, no DB round trip
**Cons:** Deno KV not available in all Supabase tiers. Non-standard.
**Effort:** Medium
**Risk:** Medium (availability uncertainty)

### Option C: Keep in-memory map with lower limit
Keep the map but set the limit very low (e.g., 3 requests/minute) as a defense against within-isolate abuse.

**Pros:** No changes needed
**Cons:** Does not solve the cold-start bypass. Useless for security.
**Effort:** None
**Risk:** High (not a real solution)

## Recommended Action

Implement Option A. Add the `live_order_rate_limits` table to the Phase 1 migration. Replace the in-memory map in `live-trading-executor` with a Postgres-backed count. Set limit to 10 invocations per minute per user per symbol (separate from TradeStation's API rate limit).

Do NOT copy the in-memory `rateLimitMap` pattern from `paper-trading-executor` into the live executor.

## Technical Details

**Affected files:**
- `supabase/migrations/20260303110000_live_trading_tables.sql` — add `live_order_rate_limits` table
- `supabase/functions/live-trading-executor/index.ts` — Postgres-backed rate limit check

**Clean up old entries:** Add a Supabase Cron job (or trigger) to DELETE from `live_order_rate_limits` WHERE `window_start < NOW() - INTERVAL '1 hour'` to prevent unbounded table growth.

## Acceptance Criteria

- [ ] `live_order_rate_limits` table added to migration
- [ ] Rate limit enforced via DB query, not in-memory map
- [ ] Rate limit check is atomic (count + insert in same transaction or via INSERT ... ON CONFLICT)
- [ ] Old rate limit rows cleaned up (either via cron or TTL pattern)
- [ ] No `rateLimitMap = new Map()` module-scope variable in `live-trading-executor`

## Work Log

- 2026-03-03: Finding created from Security Sentinel (SEC-03).
