---
status: pending
priority: p3
issue_id: "022"
tags: [code-review, webview, native-bridge, swift, strategy-builder]
dependencies: []
---

# 022: WKScriptMessageHandler body is a stub — WebView events not propagated to native

## Problem Statement

`StrategyBuilderWebView.Coordinator` receives JS events from the React component (`conditionUpdated`, `strategyActivated`, `backtestRequested`) but the handler body is an empty comment. Condition changes made in the WebView are not propagated back to native state, meaning the native Paper Trading Dashboard has no awareness of when strategy conditions change in the WebView.

## Findings

**File:** `client-macos/SwiftBoltML/Views/StrategyBuilderWebView.swift` lines ~118-128

```swift
func userContentController(_ userContentController: WKUserContentController,
                            didReceive message: WKScriptMessage) {
    // Future: handle "conditionUpdated", "strategyActivated", "backtestRequested"
}
```

If the React app does its own Supabase writes when conditions change, the native layer is simply unaware and won't refresh. The shared-workspace contract between WebView and native is silent.

**Source:** agent-native-reviewer agent (Warning #6)

## Proposed Solution

Implement minimum viable handling for `conditionUpdated`:

```swift
func userContentController(_ userContentController: WKUserContentController,
                            didReceive message: WKScriptMessage) {
    guard let body = message.body as? [String: Any],
          let type = body["type"] as? String else { return }

    switch type {
    case "conditionUpdated":
        // Strategy was saved in WebView — reload native strategy list
        Task { @MainActor in
            await strategyViewModel?.loadStrategies()
        }
    case "backtestRequested":
        // User clicked "Run Backtest" in React — trigger natively or navigate
        if let strategyId = body["strategyId"] as? String {
            Task { @MainActor in
                await backtestViewModel?.runBacktest(strategyId: strategyId)
            }
        }
    default:
        break
    }
}
```

**Effort:** Small | **Risk:** Low

## Acceptance Criteria

- [ ] `conditionUpdated` event from React triggers a reload of strategy data in the native layer
- [ ] `backtestRequested` event initiates a backtest via the native backtest service
- [ ] Handler does not crash on unexpected message formats (guard let pattern)

## Work Log

- 2026-02-28: Identified by agent-native-reviewer in PR #23 code review
