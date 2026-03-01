---
status: pending
priority: p3
issue_id: "013"
tags: [code-review, performance, memory-management, webview, swift]
dependencies: ["008"]
---

# 013: WKWebView script message handler causes retain cycle

## Problem Statement

`config.userContentController.add(context.coordinator, name: "strategyBuilder")` registers the Coordinator as a `WKScriptMessageHandler`. `WKUserContentController` holds a **strong** reference to message handlers, and the WKWebView holds a strong reference to its configuration. This creates a retain cycle: WebView → Config → UserContentController → Coordinator → (via closure) → NSViewRepresentable state. The WebView will never be deallocated.

## Findings

**File:** `client-macos/SwiftBoltML/Views/StrategyBuilderWebView.swift` lines 65-66, 174-175

```swift
func makeNSView(context: Context) -> WKWebView {
    let config = WKWebViewConfiguration()
    config.userContentController.add(context.coordinator, name: "strategyBuilder")
    // ↑ Strong reference — retain cycle
    let webView = WKWebView(frame: .zero, configuration: config)
    ...
}
```

Same pattern in `BacktestResultsWebViewRepresentable`.

The `context.coordinator` is a `class` (`AnyObject`) — `WKUserContentController.add(_:name:)` takes it strongly. The standard fix is a weak proxy wrapper.

**Source:** performance-oracle agent (P3)

## Proposed Solutions

### Option A: Weak proxy object (Recommended)

```swift
// Add this class to StrategyBuilderWebView.swift or a shared file:
final class WeakScriptHandler: NSObject, WKScriptMessageHandler {
    weak var delegate: WKScriptMessageHandler?
    init(_ delegate: WKScriptMessageHandler) { self.delegate = delegate }
    func userContentController(_ ucc: WKUserContentController,
                                didReceive message: WKScriptMessage) {
        delegate?.userContentController(ucc, didReceive: message)
    }
}

// In makeNSView:
config.userContentController.add(
    WeakScriptHandler(context.coordinator),
    name: "strategyBuilder"
)
```

Also remove the handler on cleanup:
```swift
func dismantleNSView(_ nsView: WKWebView, coordinator: Coordinator) {
    nsView.configuration.userContentController.removeScriptMessageHandler(
        forName: "strategyBuilder"
    )
}
```
- **Pros:** Standard Swift pattern for WKWebView; eliminates retain cycle
- **Effort:** Small | **Risk:** Very Low

### Option B: WKScriptMessageHandlerWithReply (macOS 11+)
Uses a different API that doesn't have the same retain semantics.
- **Pros:** More modern API
- **Cons:** Requires changing message handling pattern on both native and JS sides
- **Effort:** Medium | **Risk:** Low

## Recommended Action

Option A. Apply when consolidating to `FrontendWebViewRepresentable` (todo #008) — do both at once.

## Technical Details

**Affected files:**
- `client-macos/SwiftBoltML/Views/StrategyBuilderWebView.swift`

**Note:** `dismantleNSView` must also be added to properly unregister the handler when the view is removed.

## Acceptance Criteria

- [ ] `WeakScriptHandler` proxy class added
- [ ] `userContentController.add()` uses the proxy
- [ ] `dismantleNSView` removes the script message handler
- [ ] Navigating away from WebView view deallocates the WKWebView (verify with Instruments)

## Work Log

- 2026-02-28: Identified by performance-oracle review agent in PR #23 code review
