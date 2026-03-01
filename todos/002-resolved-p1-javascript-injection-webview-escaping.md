---
status: pending
priority: p1
issue_id: "002"
tags: [code-review, security, xss, webview, injection]
dependencies: []
---

# 002: JavaScript injection via insufficient escaping in WKWebView evaluateJavaScript

## Problem Statement

All four `evaluateJavaScript` call sites in `StrategyBuilderWebView.swift` use single-quote escaping to sanitize the `symbol` value before injecting it into a JS string literal. Single-quote escaping is incomplete — backslash, Unicode line terminators (`\u2028`/`\u2029`), and newlines can break out of the string and inject arbitrary JavaScript. Since `symbol` originates from a Supabase query result, a malformed ticker from a compromised upstream source could cause code execution in the WKWebView with access to the native JS bridge. **BLOCKS MERGE.**

## Findings

**Files:** `client-macos/SwiftBoltML/Views/StrategyBuilderWebView.swift` lines 80-81, 102-103, 189-190, 208-210 (4 call sites)

```swift
// Current vulnerable pattern (repeated 4 times):
let escaped = symbol.replacingOccurrences(of: "'", with: "\\'")
webView.evaluateJavaScript(
    "window.postMessage({ type: 'symbolChanged', symbol: '\(escaped)' }, '*');"
)
```

**Bypass payloads:**
- `AAPL\` — backslash escapes the closing quote, leaving JS string unclosed
- `AAPL'; alert(document.cookie);//` — classic injection
- `AAPL\u2028; maliciousCall();//` — Unicode line terminator injection

The `symbol` value comes from `appViewModel.selectedSymbol?.ticker` → Supabase query → Alpaca API. If the ticker data is ever malformed or the DB is written to directly, injected JS executes with full WKWebView DOM access + access to `window.webkit.messageHandlers` (the native bridge).

**Source:** security-sentinel agent

## Proposed Solutions

### Option A: JSONSerialization for structured data (Recommended)
Replace string interpolation with proper JSON encoding, which handles all escaping:

```swift
let payload: [String: Any] = ["type": "symbolChanged", "symbol": symbol]
if let data = try? JSONSerialization.data(withJSONObject: payload),
   let json = String(data: data, encoding: .utf8) {
    webView.evaluateJavaScript("window.postMessage(\(json), '*');")
}
```
- **Pros:** Eliminates injection surface; handles all characters; idiomatic
- **Cons:** None for this use case
- **Effort:** Small (4 call sites, same fix each time) | **Risk:** Very Low

### Option B: WKUserScript injection at page load
Pre-inject a JS shim at `WKUserScriptInjectionTime.atDocumentStart` that exposes a typed setter the native side calls with a structured object, rather than evaluating raw JS strings.
- **Pros:** No dynamic JS evaluation at all; cleanest architecture
- **Cons:** Requires changes to React app to listen differently
- **Effort:** Medium | **Risk:** Low

### Option C: Ticker allowlist validation before injection
Validate that `symbol` matches `^[A-Z]{1,5}$` before passing to WebView.
- **Pros:** Defense-in-depth on top of encoding
- **Cons:** Not a substitute for proper escaping; regex may be too restrictive for futures/crypto tickers
- **Effort:** Small | **Risk:** Medium (still need proper escaping)

## Recommended Action

Option A (JSONSerialization) at all 4 call sites, plus Option C as defense-in-depth.

## Technical Details

**Affected files:**
- `client-macos/SwiftBoltML/Views/StrategyBuilderWebView.swift` (4 call sites)

**Call site locations:**
1. `StrategyBuilderWebViewRepresentable.updateNSView()` ~line 80
2. `StrategyBuilderCoordinator.webView(_:didFinish:)` ~line 102
3. `BacktestResultsWebViewRepresentable.updateNSView()` ~line 189
4. `BacktestResultsCoordinator.webView(_:didFinish:)` ~line 208

## Acceptance Criteria

- [ ] All 4 `evaluateJavaScript` call sites use `JSONSerialization` for payload construction
- [ ] No string interpolation of user-derived data into JS source strings
- [ ] Existing WebView behavior (symbol propagation to React) still works after fix
- [ ] Test with ticker value containing `'`, `\`, newline, and Unicode line terminator

## Work Log

- 2026-02-28: Identified by security-sentinel review agent in PR #23 code review

## Resources

- [PR #23](https://github.com/PapaPablano/SwiftBolt_ML/pull/23)
- [WKWebView evaluateJavaScript security](https://developer.apple.com/documentation/webkit/wkwebview/1415017-evaluatejavascript)
- [Unicode line terminators in JavaScript](https://tc39.es/ecma262/#sec-line-terminator)
