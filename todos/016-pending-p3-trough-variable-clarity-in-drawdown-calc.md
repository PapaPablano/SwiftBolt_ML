---
status: pending
priority: p3
issue_id: "016"
tags: [code-review, clarity, swift, trading]
dependencies: []
---

# 016: Misleading `trough` variable name in drawdown calculation

## Problem Statement

In `computeMetrics()`, the variable `trough` is assigned and immediately compared in each loop iteration, but is never read outside the loop body. Its name is misleading — in drawdown analysis, "trough" typically refers to the lowest equity level (an absolute value), but here it represents the current drawdown from peak (a delta value, always ≤ 0). This makes the financial logic harder to read and verify.

## Findings

**File:** `client-macos/SwiftBoltML/Services/PaperTradingService.swift` lines 186-192

```swift
var peak = 0.0, trough = 0.0, maxDD = 0.0, running = 0.0
for trade in trades.reversed() {
    running += trade.pnl
    if running > peak { peak = running }
    trough = running - peak        // always ≤ 0; confusingly named
    if trough < maxDD { maxDD = trough }
}
```

`trough` is only used as a temporary in the conditional — it could be inlined as a local `let`. The name suggests "the lowest equity point" but the value is actually "current drawdown from peak," which financial code typically calls `drawdown`.

**Source:** code-simplicity-reviewer agent

## Proposed Solution

```swift
var peak = 0.0, maxDD = 0.0, running = 0.0
for trade in trades.reversed() {
    running += trade.pnl
    if running > peak { peak = running }
    let drawdown = running - peak   // clearly named; scoped to iteration
    if drawdown < maxDD { maxDD = drawdown }
}
```

- Removes `trough` variable from the outer `var` declaration
- Names the concept correctly (`drawdown`)
- No functional change
- **Effort:** XSmall | **Risk:** Very Low

## Acceptance Criteria

- [ ] `trough` variable removed; replaced with `let drawdown` scoped to loop body
- [ ] `maxDD` final value unchanged (verified by running existing metrics tests or manual calculation)

## Work Log

- 2026-02-28: Identified by code-simplicity-reviewer agent in PR #23 code review
