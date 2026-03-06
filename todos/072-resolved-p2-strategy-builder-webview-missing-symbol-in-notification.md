---
status: resolved
priority: p2
issue_id: "072"
tags: [code-review, swift, chart, notification, data-correctness]
dependencies: []
---

# StrategyBuilderWebView posts backtestTradesUpdated without symbol key

## Problem Statement

`StrategyBuilderWebView` posts the `.backtestTradesUpdated` notification with `userInfo: ["trades": trades]` — no `"symbol"` key. The guard in `WebChartView`'s subscriber uses `if let` (optional binding), so when the key is absent, the guard is skipped entirely and the trades are applied unconditionally. This means trades from a backtest run on symbol A can be overlaid onto symbol B's chart.

## Findings

**File:** `client-macos/SwiftBoltML/Views/StrategyBuilderWebView.swift` lines 215-219

```swift
NotificationCenter.default.post(
    name: .backtestTradesUpdated,
    object: nil,
    userInfo: ["trades": trades]    // ← no "symbol" key
)
```

**File:** `client-macos/SwiftBoltML/Views/WebChartView.swift` lines 258-266

```swift
if let tradeSymbol = notification.userInfo?["symbol"] as? String,   // ← if let, not guard let
   let currentSymbol = self.parent.viewModel.selectedSymbol?.ticker {
    guard tradeSymbol.uppercased() == currentSymbol.uppercased() else { return }
}
// Falls through when "symbol" key is absent → trades applied to wrong chart
```

The `BacktestingViewModel` correctly adds `"symbol"` and `"generation"` when it posts, but the existing React-based `StrategyBuilderWebView` was not updated.

## Proposed Solutions

### Option A: Add symbol to StrategyBuilderWebView post (Recommended)

Pass the current symbol from the WKWebView's message body or from the view's `symbol` property:

```swift
case "backtestComplete":
    let trades = body["trades"] as? [[String: Any]] ?? []
    let symbol = body["symbol"] as? String ?? ""
    NotificationCenter.default.post(
        name: .backtestTradesUpdated,
        object: nil,
        userInfo: ["trades": trades, "symbol": symbol]
    )
```

Ensure the React frontend includes `symbol` in the `backtestComplete` message.

**Pros:** Consistent with new `BacktestingViewModel` pattern. **Cons:** Requires frontend change too.

### Option B: Strengthen the guard in WebChartView to require symbol key

```swift
guard let tradeSymbol = notification.userInfo?["symbol"] as? String,
      let currentSymbol = self.parent.viewModel.selectedSymbol?.ticker,
      tradeSymbol.uppercased() == currentSymbol.uppercased() else {
    return  // Reject notifications without symbol key
}
```

**Pros:** Defensive, single-file change. **Cons:** Breaks StrategyBuilderWebView's existing flow until it adds the key.

### Option C: Both A and B together

**Pros:** Defense in depth. **Cons:** Two changes to coordinate.

## Acceptance Criteria

- [ ] Trades from StrategyBuilderWebView are only applied when symbol matches current chart symbol
- [ ] Symbol guard in WebChartView rejects notifications with missing or mismatched symbol
- [ ] No stale trade markers when switching symbols after a React-sourced backtest

## Work Log

- 2026-03-02: Identified during PR #25 review by Performance Oracle and Pattern Recognition

## Resources

- PR: https://github.com/PapaPablano/SwiftBolt_ML/pull/25
- File: `client-macos/SwiftBoltML/Views/StrategyBuilderWebView.swift` line 218
- File: `client-macos/SwiftBoltML/Views/WebChartView.swift` line 258
