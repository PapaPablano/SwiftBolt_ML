---
status: pending
priority: p2
issue_id: "076"
tags: [code-review, swift, cleanup, dead-code]
dependencies: []
---

# Remove dead code: allowedIndicators, ChartCommand.setBacktestTrades

## Problem Statement

Two dead code items remain from PR #25, totaling ~17 LOC. They add maintenance surface and in one case (`allowedIndicators`) create a false sense of security (the validation is never called).

**Note:** `fromSupabaseCondition()` was listed here originally but is now actively used by the todo 071 fix (strategy selection loads full config via `fromSupabaseCondition`). It has been removed from this todo's scope.

## Findings

### 1. `allowedIndicators` Set + `isValidIndicator()` — 12 lines, never called

**File:** `client-macos/SwiftBoltML/Services/StrategyService.swift` lines 83-89, 153-156

Built for "validate indicator names before JS interpolation" per the plan. But the actual JS call uses `JSONSerialization` (which already prevents injection), and this method is never invoked. It provides zero security benefit while suggesting protection that doesn't exist.

### 3. `ChartCommand.setBacktestTrades(tradesJSON:)` enum case — ~5 lines

**File:** `client-macos/SwiftBoltML/Services/ChartBridge.swift` line 43

This enum case was added to the command queue but explicitly bypassed with a comment: "Handled via direct JS evaluation in ChartBridge.setBacktestTrades()". The encode block at line 178-180 is never executed.

## Proposed Solutions

### Option A: Delete both items (Recommended)

- Remove `allowedIndicators` Set and `isValidIndicator()` from `StrategyService.swift`
- Remove `ChartCommand.setBacktestTrades(tradesJSON:)` case, its `CodingKey`, and its encode block

**Pros:** Cleaner codebase, removes misleading security stub. **Cons:** None — both are genuinely unreachable.

**Note:** The `percentFormatter.multiplier = 100` in `BacktestResultsView.swift` is redundant (`.percent` style already defaults multiplier to 100) but not incorrect — the value 0.15 × 100 = 15, displayed as "15%". Not a bug, just noisy.

## Acceptance Criteria

- [ ] `allowedIndicators` and `isValidIndicator()` removed
- [ ] `ChartCommand.setBacktestTrades` enum case and related CodingKey/encode removed
- [ ] No compiler warnings about unused code
- [ ] All existing tests pass

## Work Log

- 2026-03-02: Identified during PR #25 review by Code Simplicity reviewer and Architecture Strategist

## Resources

- PR: https://github.com/PapaPablano/SwiftBolt_ML/pull/25
- File: `client-macos/SwiftBoltML/Services/StrategyService.swift` lines 83-89, 117-156
- File: `client-macos/SwiftBoltML/Services/ChartBridge.swift` line 43
