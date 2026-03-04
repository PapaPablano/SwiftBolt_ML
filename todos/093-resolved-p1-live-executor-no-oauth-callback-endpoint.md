---
status: pending
priority: p1
issue_id: "093"
tags: [code-review, live-trading, agent-native, api-design, oauth]
dependencies: []
---

# No OAuth callback endpoint — initial broker_tokens row has no programmatic write path

## Problem Statement

The plan's executor (Phase 3a) reads and refreshes existing `broker_tokens` rows. The initial OAuth authorization (exchanging an auth code for tokens and inserting the first row) is delegated to "manual setup" with a future `LIVE_TRADING_SETUP.md` document. There is no `broker-token-connect` Edge Function or `POST { action: "connect_broker" }` endpoint.

This means: the UI's "live trading toggle is disabled unless broker_tokens row exists" (Phase 6) has no API to satisfy that precondition. Agents have no way to connect a broker account. The setup step is completely opaque.

## Findings

**Agent-Native Reviewer (P1):** "No API to write the initial broker_tokens row. No broker-token-connect or POST /broker-tokens endpoint exists in the plan. Manual processes break agent parity entirely."

**Agent-Native Reviewer (P1):** "The UI's 'disabled unless broker_tokens row exists' feature has no corresponding way for an agent to satisfy that precondition."

**Brainstorm document:** Describes OAuth callback design (access + refresh tokens stored after initial flow), but the plan's implementation phases never create the callback endpoint.

## Proposed Solutions

### Option A: New `broker-token-connect` Edge Function (Recommended)
A dedicated Edge Function at `supabase/functions/broker-token-connect/index.ts`:
- `POST { code: string, redirect_uri: string }` — exchange auth code for tokens via TradeStation
- `DELETE {}` — revoke tokens and cancel all open live positions (disconnect flow)
- `GET {}` — return connection status (connected: bool, expires_at, account_id) without exposing tokens

**Pros:** Clean separation of concerns, reusable for future brokers, dedicated auth surface
**Cons:** New function to deploy and maintain
**Effort:** Medium
**Risk:** Low

### Option B: Add broker connection actions to live-trading-executor
Add `action: "connect_broker"`, `action: "disconnect_broker"`, and `action: "broker_status"` paths to the existing executor.

**Pros:** Single function to deploy
**Cons:** Executor handles both execution and connection management — mixed concerns
**Effort:** Small
**Risk:** Low

### Option C: Manual-only initial setup, no programmatic path
Keep the manual setup approach and document it clearly.

**Pros:** No additional implementation work
**Cons:** Breaks agent-native parity. UI toggle has no satisfiable API precondition. No automated provisioning.
**Effort:** None
**Risk:** High (agent parity blocked)

## Recommended Action

Add Option B to Phase 3 or Phase 6 of the plan: `action: "connect_broker"`, `action: "disconnect_broker"`, `action: "broker_status"` paths in `live-trading-executor`. This is the minimum viable API surface. Option A is preferred for v1.1 when a second broker is added.

The `connect_broker` flow:
1. Frontend initiates OAuth redirect to TradeStation's `/authorize` endpoint
2. User authorizes in browser → TradeStation redirects to callback URL with `?code=...`
3. Frontend POSTs `{ code, redirect_uri }` to `live-trading-executor?action=connect_broker`
4. Edge Function exchanges code for tokens via TradeStation, validates account info, inserts `broker_tokens` row

## Technical Details

**Affected files:**
- `supabase/functions/live-trading-executor/index.ts` — add broker connection actions
- `docs/plans/2026-03-03-feat-live-trading-executor-tradestation-plan.md` — add to Phase 3 or Phase 6

**TradeStation token exchange endpoint:**
```
POST https://signin.tradestation.com/oauth/token
grant_type=authorization_code&code=...&redirect_uri=...&client_id=...&client_secret=...
```

## Acceptance Criteria

- [ ] `POST ?action=connect_broker` endpoint exchanges auth code for tokens and inserts `broker_tokens` row
- [ ] `DELETE ?action=disconnect_broker` revokes tokens (calls TradeStation revocation endpoint) and sets `revoked_at`
- [ ] `GET ?action=broker_status` returns `{ connected: bool, expires_at, account_id }` without exposing tokens
- [ ] Frontend OAuth flow documented in plan (redirect URL, PKCE if required)
- [ ] Agents can call `connect_broker` action to establish broker connection programmatically

## Work Log

- 2026-03-03: Finding created from Agent-Native Reviewer (P1 finding #1).
