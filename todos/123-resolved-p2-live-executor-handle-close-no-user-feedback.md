---
status: pending
priority: p2
issue_id: "123"
tags: [code-review, live-trading, frontend, ux, error-handling]
dependencies: []
---

# `handleClose` swallows errors with no user-facing feedback — silent failure on position close

## Problem Statement

In `LiveTradingDashboard.tsx` (lines 122–133), when `liveTradingApi.closePosition` fails, the catch block logs to console but shows no error to the user. The button reverts from "..." to "Close" silently. In a live trading context, a user who sees the close "complete" (button reset, no error) but the position still open will not know whether the close was attempted, rejected by the broker, or timed out. They may repeatedly hammer the button.

## Findings

TypeScript reviewer P2-6.

## Proposed Solutions

**Option A (Recommended):** Add a `closeError: string | null` state to the component. On catch, set it to an error message. Display an inline error adjacent to the failed position row. Clear it when the user dismisses or retries. Effort: Small.

## Acceptance Criteria

- [ ] A failed close operation shows an inline error message to the user
- [ ] The error message persists until the user dismisses it or successfully closes the position
- [ ] Repeated close attempts while an error is showing are clearly distinguished from the initial attempt
