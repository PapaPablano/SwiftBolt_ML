---
status: pending
priority: p2
issue_id: "017"
tags: [code-review, agent-native, api, paper-trading, ux]
dependencies: []
---

# 017: No manual close-position endpoint — users and agents cannot close positions on demand

## Problem Statement

The `closePosition` function in `paper-trading-executor` is entirely internal — it is called only by `executeStrategy` during a scheduled cycle. There is no HTTP endpoint accepting a position ID to close it on demand. This means:
- Users have no "Close Position" button in `PaperTradingDashboardView` (none exists in `PositionRowView`)
- Agents cannot close a position programmatically; they must wait for an SL/TP trigger
- The agent-native parity score is directly impacted: write-side paper trading is agent-inaccessible

This was identified as a Critical gap by the agent-native reviewer.

## Findings

**File:** `supabase/functions/paper-trading-executor/index.ts` lines 468-523 — `closePosition()` is internal only

**File:** `client-macos/SwiftBoltML/Views/PaperTradingDashboardView.swift` — `PositionRowView` has no "Close" action

The paper trading executor currently routes:
- `POST /paper-trading-executor` → `executeStrategy` (runs a full cycle)

There is no route for `POST /paper-trading-executor` with `{ position_id, exit_price }` to close a specific position.

**Source:** agent-native-reviewer agent (Critical)

## Proposed Solutions

### Option A: Add route to existing paper-trading-executor (Recommended)

In `paper-trading-executor/index.ts`, add a new action route:

```typescript
// In the request router:
if (body.action === 'close_position') {
  const { position_id, exit_price } = body;
  // Reuse existing closePosition() with the provided exit_price
  // Apply same optimistic locking: UPDATE WHERE id=position_id AND status='open'
  await closePosition(supabase, position_id, exit_price, 'manual_close');
  return new Response(JSON.stringify({ success: true }), { headers: corsHeaders });
}
```

Add a corresponding "Close" button in `PositionRowView`:
```swift
Button("Close") {
    Task { await closePosition(position) }
}
.buttonStyle(.bordered)
.controlSize(.small)
```
- **Pros:** Reuses existing `closePosition` logic + optimistic lock; minimal new code; matches existing API surface
- **Effort:** Small | **Risk:** Low

### Option B: Dedicated `close-position` Edge Function
Create a new `supabase/functions/close-position/index.ts`.
- **Pros:** Clear separation; own deployment lifecycle
- **Cons:** More files; agents need to know a second endpoint
- **Effort:** Small | **Risk:** Low

### Option C: Direct database update via Supabase client
Update `paper_trading_positions` status directly to `'closed'` from the native app.
- **Pros:** Minimal backend change
- **Cons:** Bypasses executor audit trail and trade record creation; no entry in `paper_trading_trades` for the close
- **Effort:** XSmall | **Risk:** High (breaks data integrity)

## Recommended Action

Option A. The `closePosition` function already handles all the record-keeping correctly — just expose it as a route.

## Technical Details

**Affected files:**
- `supabase/functions/paper-trading-executor/index.ts` (add new route)
- `client-macos/SwiftBoltML/Views/PaperTradingDashboardView.swift` (add Close button to PositionRowView)
- `client-macos/SwiftBoltML/Services/PaperTradingService.swift` (add `closePosition(_ position: PaperPosition)` method)

## Acceptance Criteria

- [ ] `POST /paper-trading-executor` with `{ action: "close_position", position_id: "...", exit_price: 123.45 }` closes the position and creates a trade record
- [ ] `PositionRowView` has a "Close Position" button
- [ ] Closing a position refreshes the dashboard (position moves from open to trade history)
- [ ] Agent can close a position with a single HTTP POST call
- [ ] Optimistic lock prevents double-close (second call returns appropriate error)

## Work Log

- 2026-02-28: Identified by agent-native-reviewer in PR #23 code review

## Resources

- [PR #23](https://github.com/PapaPablano/SwiftBolt_ML/pull/23)
- `supabase/functions/paper-trading-executor/index.ts` (closePosition function)
