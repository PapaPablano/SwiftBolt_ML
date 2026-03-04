---
status: pending
priority: p1
issue_id: "112"
tags: [code-review, live-trading, typescript, error-handling, reliability]
dependencies: []
---

# `checkBracketFills` uncaught `getBatchOrderStatus` throw crashes entire execution cycle

## Problem Statement

`getBatchOrderStatus` (tradestation-client.ts line 377) throws on a non-OK HTTP response (429, 500, etc.). The call at line 965 of `live-trading-executor/index.ts` is not wrapped in try/catch. If the broker's order API returns an error during bracket fill monitoring, the throw propagates up through `executeLiveTradingCycle` and aborts the entire cycle — including new entry evaluation. Bracket fill monitoring and new entry evaluation are independent failure domains that should not share a blast radius.

## Findings

TypeScript reviewer P1-4. The result is that a transient broker API hiccup during fill monitoring prevents new strategies from executing their cycle entirely.

## Proposed Solutions

Option A (Recommended): Wrap the `getBatchOrderStatus` call in `checkBracketFills` in try/catch. Log the error and return early from `checkBracketFills` only (don't propagate). New entry evaluation continues unaffected. Effort: Small.

## Acceptance Criteria

- [ ] `getBatchOrderStatus` call in `checkBracketFills` is wrapped in try/catch
- [ ] A broker API error in `checkBracketFills` logs a structured error but does not abort the parent execution cycle
- [ ] New strategy entries still execute even when `checkBracketFills` encounters a broker error
