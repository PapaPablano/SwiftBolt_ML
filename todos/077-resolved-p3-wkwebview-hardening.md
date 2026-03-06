---
status: resolved
priority: p3
issue_id: "077"
tags: [code-review, security, swift, wkwebview]
dependencies: []
---

# WKWebView hardening: navigation policy, WeakScriptHandler, force unwraps, debug print

## Problem Statement

Four low-severity cleanup items from the PR review, all related to the WKWebView bridge and service layer robustness. None are blocking issues but should be addressed for production quality.

## Findings

### 1. No WKWebView navigation policy

**File:** `client-macos/SwiftBoltML/Views/WebChartView.swift` (makeNSView)

No `decidePolicyFor navigationAction` delegate. JavaScript in the WebView could navigate to external URLs. Chart JS is bundled (low-risk), but a policy provides defense-in-depth.

```swift
// Add to Coordinator:
func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
             decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
    decisionHandler(navigationAction.request.url?.isFileURL == true ? .allow : .cancel)
}
```

*(Known pattern from PR #23: `todos/007-resolved-p2-webview-missing-navigation-policy.md`)*

### 2. WeakScriptHandler retain cycle

**File:** `client-macos/SwiftBoltML/Views/WebChartView.swift`

The script message handler creates a strong reference cycle: `WKWebView → UserContentController → Coordinator`. Use a weak proxy:

```swift
final class WeakScriptHandler: NSObject, WKScriptMessageHandler {
    weak var delegate: WKScriptMessageHandler?
    init(_ d: WKScriptMessageHandler) { delegate = d }
    func userContentController(_ ucc: WKUserContentController, didReceive msg: WKScriptMessage) {
        delegate?.userContentController(ucc, didReceive: msg)
    }
}
// In makeNSView: config.userContentController.add(WeakScriptHandler(coordinator), name: "chart")
// In dismantleNSView: nsView.configuration.userContentController.removeScriptMessageHandler(forName: "chart")
```

*(Known pattern from PR #23: `todos/013-pending-p3-webview-script-handler-retain-cycle.md`)*

### 3. Force unwraps on URLComponents.url

**Files:**
- `client-macos/SwiftBoltML/Services/StrategyService.swift` line 185
- `client-macos/SwiftBoltML/Services/BacktestService.swift` line 110

```swift
var request = URLRequest(url: components.url!)  // 4 instances
```

Replace with:
```swift
guard let url = components.url else { throw ...Error.invalidURL }
var request = URLRequest(url: url)
```

### 4. print() outside #if DEBUG in ChartBridge

**File:** `client-macos/SwiftBoltML/Services/ChartBridge.swift` line 718

```swift
print("[ChartBridge] setBacktestTrades JSON error: \(error.localizedDescription)")
```

Replace with `Self.logger.error(...)` or wrap in `#if DEBUG`.

## Acceptance Criteria

- [ ] Navigation policy added — restricts WKWebView to file:// URLs
- [ ] WeakScriptHandler proxy used to break retain cycle
- [ ] `removeScriptMessageHandler` called in `dismantleNSView`
- [ ] All `components.url!` replaced with guard-based unwrap
- [ ] ChartBridge `print()` replaced with `os.log` Logger call

## Work Log

- 2026-03-02: Identified during PR #25 review (Security, Learnings Researcher); cross-referenced with PR #23 solutions

## Resources

- PR: https://github.com/PapaPablano/SwiftBolt_ML/pull/25
- Related: `todos/007-resolved-p2-webview-missing-navigation-policy.md`
- Related: `todos/013-pending-p3-webview-script-handler-retain-cycle.md`
