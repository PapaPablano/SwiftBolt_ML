---
status: pending
priority: p2
issue_id: "143"
tags: [code-review, live-trading, frontend, duplication]
dependencies: []
---

# `LiveTradingStatusWidget` reimplements PnL math already available from `summary` endpoint

## Problem Statement

`/Users/ericpeterson/SwiftBolt_ML/frontend/src/components/LiveTradingStatusWidget.tsx` lines 30–40: the widget fetches all positions, filters to open ones, and manually computes total unrealized PnL by iterating with direction/multiplier math. This duplicates PnL logic already implemented in the live-trading-executor's `handleSummary` handler. The widget makes two parallel API calls (`positions` + `brokerStatus`) and performs client-side math that diverges from server-side math whenever the executor's PnL formula changes.

Additionally, the widget label shows `$totalPnl` with no label distinguishing realized vs unrealized, so the semantic distinction is already opaque to the user.

## Findings

**Code Simplicity Reviewer (P2-7):** "If it instead called `summary` + `brokerStatus`, it would get `total_trades`, `win_rate`, and `total_pnl` (realized) without the client-side PnL loop."

## Proposed Solutions

**Option A (Recommended):** Replace `positions` API call with `summary` API call. Use `summary.total_pnl` (realized) and display as "Today's P&L" with a clear label. Remove the client-side PnL loop.

**Option B:** Keep the positions call but label the display as "Unrealized P&L" and source the calculation from a shared utility function (same function used server-side) to prevent divergence.

**Option C:** Keep current behavior as-is but add a comment documenting that the widget computes unrealized PnL client-side and must be kept in sync with server-side formula.

## Acceptance Criteria

- [ ] PnL calculation logic exists in exactly one place (server or shared utility)
- [ ] Widget label accurately describes what's being shown (realized vs unrealized)
- [ ] No behavior regression on broker connection status display

## Work Log

- 2026-03-03: Finding from code-simplicity-reviewer.
