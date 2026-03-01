---
status: pending
priority: p2
issue_id: "008"
tags: [code-review, architecture, dry, swift, webview]
dependencies: []
---

# 008: Duplicate NSViewRepresentable implementations (~85% identical)

## Problem Statement

`StrategyBuilderWebView.swift` contains two near-identical `NSViewRepresentable` implementations: `StrategyBuilderWebViewRepresentable` and `BacktestResultsWebViewRepresentable`. They share the same WKWebView setup, navigation delegate pattern, JS injection logic, and error handling. The only differences are the JS message handler name and the URL path. Any bug fix or improvement (e.g., the security fixes in todos 002 and 007) must be applied twice.

## Findings

**File:** `client-macos/SwiftBoltML/Views/StrategyBuilderWebView.swift`

Identical between both:
- `makeNSView()`: identical WKWebViewConfiguration, identical userContentController setup
- `updateNSView()`: identical symbol change detection, identical `evaluateJavaScript` pattern
- Coordinator `webView(_:didFinish:)`: identical JS injection
- Coordinator `webView(_:didFail:...)`: identical error state setting

Different:
- Message handler name: `"strategyBuilder"` vs `"backtestResults"`
- URL path: `"/strategy-builder"` vs `"/backtest"`

**Source:** architecture-strategist agent (P2)

## Proposed Solutions

### Option A: Parameterized FrontendWebViewRepresentable (Recommended)

```swift
struct FrontendWebViewRepresentable: NSViewRepresentable {
    let path: String
    let messageHandlerName: String
    @Binding var loadState: WebViewLoadState
    var symbol: String?

    func makeCoordinator() -> Coordinator {
        Coordinator(loadState: $loadState, messageHandlerName: messageHandlerName)
    }

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.userContentController.add(context.coordinator, name: messageHandlerName)
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = context.coordinator
        if let url = URL(string: frontendURL(path: path)) {
            webView.load(URLRequest(url: url))
        }
        return webView
    }
    // ... single Coordinator handles both cases
}

// Usage:
FrontendWebViewRepresentable(
    path: "/strategy-builder",
    messageHandlerName: "strategyBuilder",
    loadState: $loadState,
    symbol: symbol
)
```
- **Pros:** Single source of truth; security fixes applied once; ~80 LOC reduction
- **Cons:** Slightly less explicit type names in debugging
- **Effort:** Small | **Risk:** Low

### Option B: Extract shared base Coordinator class
Keep separate Representable structs but extract a `WebViewCoordinatorBase` class they both inherit.
- **Pros:** Keeps explicit type names
- **Cons:** Inheritance is un-idiomatic in Swift; more boilerplate than Option A
- **Effort:** Small | **Risk:** Low

### Option C: Keep as-is until other fixes land
Apply security fixes (002, 007) to both structs individually, then consolidate.
- **Pros:** Minimal scope change in this PR; security fixes are the priority
- **Cons:** Tech debt accumulates; easy to forget to apply fixes in both places
- **Effort:** None for deduplication | **Risk:** Medium (divergence)

## Recommended Action

Option A. The consolidation is small enough to do alongside the security fixes rather than separately.

## Technical Details

**Affected files:**
- `client-macos/SwiftBoltML/Views/StrategyBuilderWebView.swift` (major refactor of bottom half)

**Lines to eliminate:** ~100 duplicated lines in the second NSViewRepresentable + Coordinator

## Acceptance Criteria

- [ ] Single `FrontendWebViewRepresentable` struct replaces both separate implementations
- [ ] `StrategyBuilderWebView` and `BacktestResultsWebView` SwiftUI views remain as-is (calling the shared representable)
- [ ] Both WebViews still load correct URLs and inject symbol correctly
- [ ] Message handlers are registered with correct names per instance
- [ ] Security fixes (002, 007) applied once to shared implementation

## Work Log

- 2026-02-28: Identified by architecture-strategist review agent in PR #23 code review

## Resources

- [PR #23](https://github.com/PapaPablano/SwiftBolt_ML/pull/23)
