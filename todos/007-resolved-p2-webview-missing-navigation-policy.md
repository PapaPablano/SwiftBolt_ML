---
status: pending
priority: p2
issue_id: "007"
tags: [code-review, security, webview, wkwebview, sandboxing]
dependencies: []
---

# 007: WKWebView missing navigation policy — open to arbitrary redirects

## Problem Statement

Both WKWebView Coordinator classes in `StrategyBuilderWebView.swift` implement `WKNavigationDelegate` but do not implement `webView(_:decidePolicyFor:decisionHandler:)`. Any redirect, `window.location` assignment, or XSS-triggered navigation that escapes the intended origin will be followed silently — with the native message handler still registered. Additionally, `limitsNavigationsToAppBoundDomains` is not set, allowing cross-origin navigation.

## Findings

**File:** `client-macos/SwiftBoltML/Views/StrategyBuilderWebView.swift` — both Coordinator classes

Current Coordinator only implements:
- `webView(_:didFinish:)` — symbol injection
- `webView(_:didFail:withError:)` — error state
- `webView(_:didFailProvisionalNavigation:withError:)` — error state

**Missing:** `webView(_:decidePolicyFor:decisionHandler:)` which would gate all navigations.

**Attack surface:** If the React app running in the WebView has an XSS vulnerability, an attacker can use `window.location = "https://evil.com"` to navigate the WebView to their page — which then has access to `window.webkit.messageHandlers.strategyBuilder` and can call back into native Swift with arbitrary data.

**Source:** security-sentinel agent (P3-MEDIUM)

## Proposed Solutions

### Option A: Implement decidePolicyFor in both Coordinators (Recommended)

```swift
func webView(_ webView: WKWebView,
             decidePolicyFor navigationAction: WKNavigationAction,
             decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
    guard let host = navigationAction.request.url?.host else {
        decisionHandler(.cancel)
        return
    }
    let allowed = ["localhost", "127.0.0.1"]
    // Add production hostname when deploying, e.g.: allowed + ["app.swiftbolt.io"]
    if allowed.contains(host) {
        decisionHandler(.allow)
    } else {
        decisionHandler(.cancel)
    }
}
```

Also set `config.limitsNavigationsToAppBoundDomains = true` and add `WKAppBoundDomains` to `Info.plist`:
```xml
<key>WKAppBoundDomains</key>
<array>
    <string>localhost</string>
</array>
```
- **Pros:** Defense-in-depth; standard macOS WebView hardening
- **Effort:** Small | **Risk:** Very Low

### Option B: WKContentRuleList to block cross-origin resources
Use `WKContentRuleList` to block cross-origin script loads.
- **Pros:** Finer-grained control
- **Cons:** More complex; navigation policy is sufficient
- **Effort:** Medium | **Risk:** Low

## Recommended Action

Option A. This should be applied to both `StrategyBuilderCoordinator` and (the future merged) `BacktestResultsCoordinator`.

## Technical Details

**Affected files:**
- `client-macos/SwiftBoltML/Views/StrategyBuilderWebView.swift` (both Coordinator classes)
- `client-macos/SwiftBoltML/Info.plist` (add WKAppBoundDomains)

**Note:** WKAppBoundDomains requires `limitsNavigationsToAppBoundDomains = true` to be set on the `WKWebViewConfiguration`. Available macOS 11+.

## Acceptance Criteria

- [ ] Both Coordinators implement `decidePolicyFor` and reject non-localhost origins
- [ ] `limitsNavigationsToAppBoundDomains = true` set on WKWebViewConfiguration
- [ ] `WKAppBoundDomains` added to Info.plist
- [ ] WebView still loads localhost:5173 correctly
- [ ] Navigation to `google.com` from WebView is cancelled (test in dev)

## Work Log

- 2026-02-28: Identified by security-sentinel review agent in PR #23 code review

## Resources

- [PR #23](https://github.com/PapaPablano/SwiftBolt_ML/pull/23)
- [WKNavigationDelegate.decidePolicyFor](https://developer.apple.com/documentation/webkit/wknavigationdelegate/1455641-webview)
- [limitsNavigationsToAppBoundDomains](https://developer.apple.com/documentation/webkit/wkwebviewconfiguration/3585117-limitsnavigationstoappbounddomai)
