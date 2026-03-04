---
status: pending
priority: p1
issue_id: "087"
tags: [code-review, live-trading, architecture, performance, edge-functions]
dependencies: []
---

# Edge Function 60-second wall-clock timeout exceeded by 30s poll loop + overhead budget

## Problem Statement

Supabase Edge Functions have a hard 60-second wall-clock limit. The plan's execution cycle includes a 30-second `pollOrderFill` loop plus 5–7 external HTTP round trips before polling even begins (JWT verification, DB reads, proactive token refresh, account balance fetch, strategy/bar queries, circuit breaker queries, entry order placement). The total budget exceeds 60 seconds on the path where a token refresh is triggered, causing silent invocation termination with an unprotected open position.

## Findings

**Architecture Strategist (P1):** "The total execution budget for a single cycle call [includes] 5–7 external HTTP round trips before the 30-second poll even begins. Supabase Edge Functions have a hard 60-second wall-clock limit with no configurable extension."

**Pre-30s overhead estimate:**
- JWT verify + DB token read: ~200ms
- Proactive token refresh (if triggered): ~500ms + TradeStation HTTP ~400ms
- Account balance fetch: ~300ms
- DB strategy query + bar query: ~300ms
- Circuit breaker queries: ~200ms
- Entry order placement: ~300ms
- Fill poll startup: 0ms
**Total pre-poll:** ~2–3 seconds (fast path), ~4–5 seconds (refresh triggered)

**30s poll:** 30 × 1000ms = 30 seconds

**Post-fill overhead:** bracket placement (~400ms), DB updates (~200ms) = ~600ms

**Total fast path:** ~33 seconds. Safe.
**Total with token refresh:** ~35 seconds. Safe.
**Total with slow TradeStation API:** ~45+ seconds. Risky.
**Total if any step is slow (p99):** Exceeds 60 seconds.

The real risk is the p99 case — one slow TradeStation API response or a connection retry brings the cycle over 60 seconds.

## Proposed Solutions

### Option A: Cap poll at 10-15 seconds, require re-invocation for slow fills (Recommended)
Reduce `pollOrderFill` timeout from 30s to 10–15s. If fill not confirmed, persist position as `pending_entry` and return. The caller must re-invoke the executor to check pending positions. This keeps the total budget well under 60 seconds and matches how paper trading's manual-trigger model naturally works.

**Pros:** Stays safely within 60s limit, aligns with manual-trigger pattern, positions are recoverable on re-invocation
**Cons:** User must re-invoke to confirm fills — adds complexity to the ops workflow
**Effort:** Small
**Risk:** Low

### Option B: Split into two invocations (Phase 1: signal + entry, Phase 2: fill confirmation + bracket)
Invocation 1: signal evaluation → entry order placement → return immediately with `{ orderId, positionId }`. Invocation 2 (separate call): poll for fill confirmation on `pending_entry` positions → bracket placement.

**Pros:** Clean separation of concerns, each invocation well under 60s
**Cons:** Requires caller to sequence two calls; more complex orchestration
**Effort:** Medium
**Risk:** Medium

### Option C: Use Supabase Background Tasks (Deno.cron / waitUntil)
Use `ctx.waitUntil()` in Deno to run the poll loop after the response is returned.

**Pros:** No user-visible timeout
**Cons:** Limited Supabase support, unreliable for financial operations, no error surfacing
**Effort:** Medium
**Risk:** High (unreliable for real-money operations)

## Recommended Action

Implement Option A. Cap `pollOrderFill` at 10–15 seconds. Add an explicit note in Phase 3d acceptance criteria that the total cycle budget must be validated against the 60-second limit during implementation. Include a budget table in the plan showing the allocation per step.

## Technical Details

**Affected files:**
- `supabase/functions/live-trading-executor/index.ts` — `pollOrderFill` timeout parameter
- `docs/plans/2026-03-03-feat-live-trading-executor-tradestation-plan.md` — Phase 3d acceptance criteria

**Budget allocation (recommended):**
- Pre-execution (token, balance, queries): 10s budget
- Entry order placement: 5s budget
- Fill poll: 15s budget
- Post-fill (bracket, DB updates): 10s budget
- Safety margin: 20s
- **Total: 60s**

## Acceptance Criteria

- [ ] `pollOrderFill` timeout capped at 15 seconds maximum
- [ ] Budget table added to Phase 3d showing per-step time allocation
- [ ] If fill not confirmed within poll window, position stays in `pending_entry` and executor returns gracefully (not with error)
- [ ] Re-invocation handles `pending_entry` positions from previous cycles (checks existing position before placing new entry)

## Work Log

- 2026-03-03: Finding created from Architecture Strategist (P1).
