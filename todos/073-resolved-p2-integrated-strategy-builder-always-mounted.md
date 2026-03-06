---
status: resolved
priority: p2
issue_id: "073"
tags: [code-review, swift, performance, memory]
dependencies: []
---

# IntegratedStrategyBuilder always mounted in ZStack — unnecessary memory waste

## Problem Statement

`ContentView` keeps `IntegratedStrategyBuilder` always mounted in a ZStack at opacity 0 when the user is on other tabs. Unlike `DetailView`/`WebChartView` (which requires always-mounted to preserve the WKWebView JS context), `IntegratedStrategyBuilder` has no persistent runtime that needs this treatment. It permanently holds `BacktestingViewModel`, `StrategyListViewModel`, `UnifiedIndicatorsService`, a 1Hz timer task, and Combine subscriptions in memory — even when the user is on the Portfolio tab.

## Findings

**File:** `client-macos/SwiftBoltML/Views/ContentView.swift` lines 46-49

```swift
// Always mounted (correct for WKWebView)
DetailView()
    .opacity(activeSection == .stocks ? 1 : 0)

// Always mounted (not needed — has no persistent JS runtime)
IntegratedStrategyBuilder(symbol: appViewModel.selectedSymbol?.ticker)
    .opacity(activeSection == .tradestation ? 1 : 0)
    .allowsHitTesting(activeSection == .tradestation)
```

**Additional impact:** `BacktestingViewModel.startTimer()` (line ~309) fires a `Task` every second, incrementing `elapsedSeconds` and triggering SwiftUI diffs via `@Published` — even when the strategy tab is invisible. Since `BacktestingViewModel` uses `ObservableObject`, any `@Published` change triggers all observers.

**Estimated memory footprint:** ~50-150MB for always-alive indicator service + VMs + timers.

## Proposed Solutions

### Option A: Conditional mount (Recommended)

```swift
if activeSection == .tradestation {
    IntegratedStrategyBuilder(symbol: appViewModel.selectedSymbol?.ticker)
}
```

**Pros:** Minimal change, recovers all wasted memory. **Cons:** Strategy edits in progress are lost on tab switch.

### Option B: Hoist state to ContentView

Keep `IntegratedStrategyBuilder` conditionally mounted but hoist `@StateObject private var backtestingViewModel` and `@State private var selectedStrategy` up to `ContentView`. Pass them as bindings.

**Pros:** State survives tab switches without always-mounting the full view hierarchy. **Cons:** Propagates state up, increases ContentView complexity.

### Option C: Keep always-mounted but cancel timer when not visible

Add a `.onChange(of: activeSection)` to pause/resume the timer task.

**Pros:** Addresses timer waste without changing mount semantics. **Cons:** Doesn't address overall VM memory or Combine subscription overhead.

## Acceptance Criteria

- [ ] `IntegratedStrategyBuilder` is not kept alive when user is on non-strategy tabs
- [ ] Memory footprint when on Portfolio/Predictions tab is reduced
- [ ] Strategy list reloads correctly when tab is revisited
- [ ] No backtest timer ticking in background when strategy tab is invisible

## Work Log

- 2026-03-02: Identified during PR #25 review by Performance Oracle

## Resources

- PR: https://github.com/PapaPablano/SwiftBolt_ML/pull/25
- File: `client-macos/SwiftBoltML/Views/ContentView.swift` line 46
