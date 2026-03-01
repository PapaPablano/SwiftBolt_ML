---
status: pending
priority: p2
issue_id: "004"
tags: [code-review, security, ssrf, webview, validation]
dependencies: []
---

# 004: FRONTEND_URL environment variable accepted without scheme/host validation

## Problem Statement

`frontendURL(path:)` in `StrategyBuilderWebView.swift` reads `FRONTEND_URL` from the process environment and appends it to the WKWebView load URL without validating scheme or host. A malicious or misconfigured `FRONTEND_URL` value (e.g., `file://`, `javascript:`, `data:`, or an arbitrary remote host) would cause the WebView to load attacker-controlled content that has full access to the registered native JS message handlers.

## Findings

**File:** `client-macos/SwiftBoltML/Views/StrategyBuilderWebView.swift` lines 278-286

```swift
private func frontendURL(path: String) -> String {
    let base: String
    if let env = ProcessInfo.processInfo.environment["FRONTEND_URL"], !env.isEmpty {
        base = env.hasSuffix("/") ? String(env.dropLast()) : env
    } else {
        base = "http://localhost:5173"
    }
    return base + path  // no scheme or host validation
}
```

On macOS, `FRONTEND_URL` can be set via: compromised shell profile, malicious Launch Agent, CI/CD pipeline leak, or `.env` file. The two WebView coordinators register `window.webkit.messageHandlers.strategyBuilder` unconditionally — any page loaded in the WebView can call back into native Swift.

**Source:** security-sentinel agent (P2-HIGH)

## Proposed Solutions

### Option A: Allowlist validation (Recommended)

```swift
private func frontendURL(path: String) -> String {
    let allowedSchemes: Set<String> = ["http", "https"]
    let allowedHosts: Set<String> = ["localhost", "127.0.0.1"]
    // Add production domain when known, e.g.: allowedHosts.insert("app.swiftbolt.io")

    if let env = ProcessInfo.processInfo.environment["FRONTEND_URL"],
       !env.isEmpty,
       let components = URLComponents(string: env),
       let scheme = components.scheme,
       let host = components.host,
       allowedSchemes.contains(scheme),
       allowedHosts.contains(host) {
        let base = env.hasSuffix("/") ? String(env.dropLast()) : env
        return base + path
    }
    return "http://localhost:5173" + path
}
```
- **Pros:** Blocks all non-localhost/non-HTTPS origins; safe default
- **Cons:** Needs updating when production domain is known
- **Effort:** Small | **Risk:** Very Low

### Option B: Remove env var support; use build configuration
Instead of runtime env var, use Xcode build configurations (Debug/Release) to set the frontend URL at compile time.
- **Pros:** No runtime injection surface
- **Cons:** Less flexible for development; requires rebuild to change URL
- **Effort:** Small | **Risk:** Low

### Option C: Hardcode localhost for development; require explicit build var for production
- **Pros:** Simple
- **Cons:** Same injection risk if using build var
- **Effort:** Small | **Risk:** Medium

## Recommended Action

Option A with the production hostname added to the allowlist once known.

## Technical Details

**Affected files:**
- `client-macos/SwiftBoltML/Views/StrategyBuilderWebView.swift` (`frontendURL` function)

## Acceptance Criteria

- [ ] `frontendURL()` validates scheme is `http` or `https`
- [ ] `frontendURL()` validates host against an allowlist
- [ ] Invalid `FRONTEND_URL` silently falls back to `http://localhost:5173`
- [ ] `file://`, `javascript:`, and arbitrary remote hosts are rejected
- [ ] App still loads correct URL in development (localhost:5173) and production

## Work Log

- 2026-02-28: Identified by security-sentinel review agent in PR #23 code review

## Resources

- [PR #23](https://github.com/PapaPablano/SwiftBolt_ML/pull/23)
