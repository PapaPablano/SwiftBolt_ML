---
status: resolved
priority: p2
issue_id: "186"
tags: [plan-review, live-trading, financial-safety, frontend, state-machine]
dependencies: []
---

# Fix Plan: `disconnect_broker` has no safeguard for open positions — disconnecting while in a trade disables bracket monitoring

## Problem Statement

The `disconnect_broker` handler immediately revokes the broker token with no check for open positions. If a user disconnects while holding live positions, the next execution cycle's `ensureFreshToken` fails with 401. `checkBracketFills` cannot run. SL/TP bracket fills are not detected. The positions remain open in the DB but unmonitored, with no automatic SL/TP enforcement until the broker reconnects. The frontend "Disconnect Broker" button has no confirmation dialog and no warning about open positions.

## Findings

**Spec-Flow Analyzer (GAP-P2-4):**

`disconnect_broker` handler (lines 1378–1386 of `index.ts`):
```typescript
case "disconnect_broker":
  await supabase.from("broker_tokens").delete().eq("user_id", user.id);
  return corsResponse({ success: true }, 200, origin);
```

No check for open positions before deletion.

`LiveTradingDashboard.tsx` "Disconnect Broker" button (lines 323–336): renders unconditionally with no confirmation dialog or position count warning.

**Impact chain after disconnection with open positions:**

1. `broker_tokens` row deleted
2. Next execution cycle calls `ensureFreshToken` → DB returns null → function throws "No broker token"
3. `checkBracketFills` never runs
4. SL/TP bracket orders may fill at the broker but the executor never detects them
5. `live_trading_positions` rows remain `status = 'open'` indefinitely
6. P&L is never recorded for the filled bracket orders
7. User's account balance at TradeStation is changed, but DB shows position as still open

**Recommended fix — backend guard:**
```typescript
case "disconnect_broker": {
  const { count } = await supabase
    .from("live_trading_positions")
    .select("id", { count: "exact", head: true })
    .eq("user_id", user.id)
    .eq("status", "open");
  if (count && count > 0) {
    return corsResponse({
      success: false,
      error: `Cannot disconnect: ${count} open position(s). Close all positions first.`,
      open_position_count: count,
    }, 409, origin);
  }
  await supabase.from("broker_tokens").delete().eq("user_id", user.id);
  return corsResponse({ success: true }, 200, origin);
}
```

**Recommended fix — frontend guard:**
Show a confirmation dialog if open positions exist when the button is clicked, warning the user that disconnecting will disable SL/TP monitoring.

## Proposed Solution

Amend the plan to add a guard to `disconnect_broker` that checks for open positions and returns 409 if any exist. Add a frontend confirmation dialog with a clear warning about SL/TP monitoring loss.

## Acceptance Criteria

- [x] `disconnect_broker` backend checks for open positions and returns 409 if any exist
- [x] Frontend "Disconnect Broker" button shows confirmation dialog warning about SL/TP monitoring
- [x] If no open positions exist, disconnect proceeds as before
- [x] 409 response body includes `open_position_count` so the frontend can show a specific count

## Work Log

- 2026-03-03: Finding from spec-flow-analyzer (GAP-P2-4) during plan review. Disconnecting with open trades disables bracket fill monitoring — a real-money risk that warrants both a backend guard and a frontend warning.

- 2026-03-03: RESOLVED. Plan amended to address all findings.
