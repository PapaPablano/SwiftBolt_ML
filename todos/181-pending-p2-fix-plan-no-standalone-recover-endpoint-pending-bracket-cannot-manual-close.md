---
status: pending
priority: p2
issue_id: "181"
tags: [plan-review, live-trading, state-machine, api-design, financial-safety]
dependencies: []
---

# Fix Plan: No standalone `recover_positions` endpoint — `pending_bracket` positions cannot be manually closed

## Problem Statement

The `recoverStuckPositions` function proposed in Phase 5 only runs when triggered by a full execution cycle POST (symbol + timeframe). There is no standalone endpoint to trigger recovery without executing strategies. Additionally, the `close_position` handler only accepts `status = 'open'` positions — `pending_bracket` positions return 404. The UI shows `pending_bracket` positions to users but provides no close button for them. A position stuck in `pending_bracket` on a low-volume symbol with no signals for hours has no manual escape path.

## Findings

**Spec-Flow Analyzer (GAP-P1-4):**

The `close_position` handler at line 1280 of `index.ts`:
```typescript
.eq("status", "open")  // ← pending_bracket returns 404
```

`LiveTradingDashboard.tsx` at line 118 shows positions filtered to `['open', 'pending_entry', 'pending_bracket']` — users see `pending_bracket` positions — but the close button (line 253) is only rendered for `status === 'open'`. No UI exists for escaping `pending_bracket`.

**Recovery scan dependency on execution cycle:**

`recoverStuckPositions` is called inside `executeLiveTradingCycle`. `executeLiveTradingCycle` is triggered by a POST with `symbol` and `timeframe`. If the relevant strategy's symbol generates no signals for hours (low-volume, after-hours), `recoverStuckPositions` never fires for that symbol's positions.

**Two required additions:**

**1. Standalone recovery endpoint:**
```typescript
case "recover_positions":
  // No symbol/timeframe needed — runs recovery for all user positions
  await recoverStuckPositions(supabase, token.access_token, accountId, userId);
  return corsResponse({ success: true, action: "recover_positions" }, 200, origin);
```

**2. Emergency Close UI for `pending_bracket`:**
The `LiveTradingDashboard` should show an "Emergency Close" button for `pending_bracket` positions that calls the `recover_positions` endpoint (or a direct close endpoint) rather than `close_position` (which only works for `status = 'open'`).

Alternatively, extend `close_position` to accept `pending_bracket` positions:
```typescript
.in("status", ["open", "pending_bracket"])
```
And handle bracket cancellation before the market close order for `pending_bracket` positions.

## Proposed Solution

Amend the plan to add:
1. `POST action: "recover_positions"` endpoint that triggers `recoverStuckPositions` without requiring a full execution cycle
2. Either extend `close_position` to accept `pending_bracket` positions OR add an "Emergency Close" button that calls the recovery endpoint
3. Document that `pending_bracket` positions can only be closed via recovery (if option 2 is deferred)

## Acceptance Criteria

- [ ] A mechanism exists for users/agents to trigger position recovery without executing a full strategy cycle
- [ ] `pending_bracket` positions have a documented escape path (either via recovery endpoint or extended `close_position`)
- [ ] Plan documents which positions each close path handles (`open` vs `pending_bracket` vs `pending_entry`)

## Work Log

- 2026-03-03: Finding from spec-flow-analyzer (GAP-P1-4) during plan review. Without a standalone recovery trigger, stuck positions on low-volume symbols are unresolvable without waiting for the next strategy signal.
