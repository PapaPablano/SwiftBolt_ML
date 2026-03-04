---
status: pending
priority: p2
issue_id: "142"
tags: [code-review, live-trading, architecture, maintainability]
dependencies: []
---

# `executeStrategy` is a 313-line monolith — untestable bracket failure path

## Problem Statement

`/Users/ericpeterson/SwiftBolt_ML/supabase/functions/live-trading-executor/index.ts` `executeStrategy` (lines 620–933) handles eight distinct phases in a single function:
1. Open position lookup
2. Exit signal evaluation
3. Entry signal evaluation
4. Four sequential circuit breaker checks
5. Direction/SL/TP computation
6. Quantity calculation
7. Market order placement → DB insert → fill polling
8. Bracket placement → bracket failure emergency close (30+ lines at 892–932)

The bracket failure emergency close path is buried at the end of a 313-line function, making it effectively impossible to test in isolation. Each new feature (trailing stops, partial close, etc.) makes it harder to modify safely.

Additionally, `evaluateStrategySignals` is called twice — once for the exit path (line 653) and once for the entry path (line 675) — processing the same bars data twice per execution tick.

## Findings

**Code Simplicity Reviewer (P2-4):** "Each phase is long enough to extract — the bracket failure recovery is 30+ lines (892–932). The function should be split at minimum into: `runCircuitBreakers`, `computeEntryParams`, and `submitEntry`."

**Code Simplicity Reviewer (P2-6):** "Both signals could be computed once at the top of `executeStrategy` and destructured. The current structure forces the function to process bars twice."

## Proposed Solutions

**Option A (Recommended):** Split into three focused functions:
- `runCircuitBreakers(supabase, userId, balance, strategy)` → `CircuitBreakerResult | null`
- `computeEntryParams(strategy, latestPrice, isFutures, tsSymbol)` → `{ direction, tradeAction, closeAction, sl, tp, qty }`
- `submitEntryWithBracket(supabase, token, accountId, position, params)` → covers order → insert → poll → bracket → emergency close

Also evaluate signals once at top of `executeStrategy`:
```typescript
const { entry, exit } = evaluateStrategySignals(
  strategy.config.entry_conditions ?? [],
  strategy.config.exit_conditions ?? [],
  bars,
);
```

**Option B:** Extract just the bracket failure path as `handleBracketFailure(...)` — smallest change, highest safety payoff.

## Acceptance Criteria

- [ ] `executeStrategy` is ≤150 lines after extraction
- [ ] Bracket failure emergency close path is independently callable/testable
- [ ] `evaluateStrategySignals` called exactly once per execution tick
- [ ] Behavior unchanged — pure refactor

## Work Log

- 2026-03-03: Finding from code-simplicity-reviewer.
