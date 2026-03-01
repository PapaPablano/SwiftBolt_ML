---
title: macOS SwiftUI App — Credential Exposure, JavaScript Injection, and Task Lifecycle Hardening
date: 2026-02-28
category: security-issues
tags: hardcoded-credentials, javascript-injection, wkwebview, task-lifecycle, xcode-xcconfig, swiftui-performance, swift-concurrency, nsviewrepresentable, supabase, macos
components: >
  client-macos/SwiftBoltML (SupabaseService, PaperTradingService, StrategyBuilderWebView,
  PaperTradingDashboardView, ContentView), supabase/functions/paper-trading-executor,
  supabase/functions/strategies
symptoms: >
  Supabase credentials (URL + anon key) visible in git history via Info.plist;
  WKWebView evaluateJavaScript() vulnerable to injection via symbol string;
  Task accumulation on view re-appear causing stale subscriptions and memory growth;
  FRONTEND_URL env var accepts any scheme/host;
  NumberFormatter allocated on every SwiftUI render cycle;
  Unguarded print() statements shipping to production;
  switch default: hiding unhandled SidebarSection.devtools in release builds;
  paper_trading_enabled not settable via PUT /strategies;
  current_price never refreshed on open positions
severity: critical
status: resolved
branch: feat/macos-swiftui-overhaul
pr: "23"
---

# macOS SwiftUI App — Credential Exposure, JavaScript Injection, and Task Lifecycle Hardening

**PR:** [#23 feat/macos-swiftui-overhaul](https://github.com/PapaPablano/SwiftBolt_ML/pull/23)
**Resolved:** 2026-02-28
**Severity:** Critical (P1 security) + High (P2 lifecycle/quality)

---

## Problem Statement

A code review of the macOS SwiftUI overhaul (PR #23) surfaced three P1 and seven P2 issues spanning security, Swift concurrency, and SwiftUI code quality. The most critical:

1. **Credentials committed to git** — `Info.plist` stored `SUPABASE_URL` and `SUPABASE_ANON_KEY` as plain strings, exposing them to anyone with repo access
2. **JavaScript injection** — `injectSymbol()` used manual string interpolation into `evaluateJavaScript()`, allowing a crafted ticker symbol to break out of the JS string context
3. **Task accumulation** — `PaperTradingService.subscribeToPositions()` created a new `Task` on each call without cancelling the previous one

---

## Solution

### Root Cause #1: Hardcoded Credentials in Info.plist

**Problem:** `Info.plist` contained literal values for `SUPABASE_URL` and `SUPABASE_ANON_KEY` committed to version control, exposing credentials to anyone with repository access.

**Fix:** Replace hardcoded strings with Xcode build variable references, resolved at build time from a gitignored `Secrets.xcconfig`.

**Info.plist** (after):
```xml
<key>SUPABASE_URL</key>
<string>$(SUPABASE_URL)</string>
<key>SUPABASE_ANON_KEY</key>
<string>$(SUPABASE_ANON_KEY)</string>
```

**Secrets.xcconfig** (gitignored local file, from template `Secrets.xcconfig.example`):
```xcconfig
// Secrets.xcconfig — GITIGNORED, never commit
// See Secrets.xcconfig.example for setup instructions.
// Rotate keys at: Supabase Dashboard → Settings → API

SUPABASE_URL = https://your-project-ref.supabase.co
SUPABASE_ANON_KEY = your-anon-key-here
```

**project.pbxproj** wiring — add `baseConfigurationReference` to both Debug and Release build configurations pointing at `Secrets.xcconfig`. This makes Xcode substitute `$(SUPABASE_URL)` at build time, so the final binary contains the real value but the source file (and git history) never does.

**Key insight:** `Config.swift` already had an env → Keychain → plist priority chain, so replacing the plist values was sufficient — no code logic changes needed.

---

### Root Cause #2: JavaScript Injection Vulnerability in `injectSymbol()`

**Problem:** The function used manual single-quote escaping when injecting a symbol string into `evaluateJavaScript()`. Any ticker containing a backslash, unicode line terminator (`\u2028`/`\u2029`), or quote character could break the JavaScript string context.

**Fix:** Use `JSONSerialization` to serialize the entire payload as a JSON object, then embed the resulting string directly — no character escaping needed.

```swift
/// Injects the selected symbol into the React app via window.postMessage.
/// Uses JSONSerialization to safely encode all characters (backslash, quotes, Unicode).
private func injectSymbol(_ symbol: String, into webView: WKWebView) {
    let payload: [String: Any] = ["type": "symbolChanged", "symbol": symbol]
    guard let data = try? JSONSerialization.data(withJSONObject: payload),
          let json = String(data: data, encoding: .utf8) else { return }
    webView.evaluateJavaScript("window.postMessage(\(json), '*');")
}
```

`JSONSerialization` handles all escaping correctly by design — the resulting `json` string is already a valid JSON literal that JavaScript can safely parse.

Additional security measures added in the same rewrite:
- `config.limitsNavigationsToAppBoundDomains = true`
- `decidePolicyFor` navigation delegate rejecting any host not in `allowedHosts: Set<String> = ["localhost", "127.0.0.1"]`
- `WeakScriptHandler` proxy to prevent `WKUserContentController` retain cycle
- `dismantleNSView` removes all script message handlers on teardown

---

### Root Cause #3: Task Accumulation and Lifecycle Leak

**Problem:** `PaperTradingService.subscribeToPositions()` created a `Task` for the realtime subscription loop but never stored or cancelled it. On re-navigation (view re-appear), a second Task was created while the first continued running.

**Fix:** Store the Task handle as a property, cancel before creating a new one, and debounce reloads:

```swift
@MainActor
final class PaperTradingService: ObservableObject {
    private var realtimeChannel: RealtimeChannelV2?
    /// Stored task handle so the subscription loop can be cancelled on re-entry or view disappear.
    private var subscriptionTask: Task<Void, Never>?
    /// Debouncer prevents full reload on every realtime event during burst updates.
    private let reloadDebouncer = Debouncer(frequency: .slow) // 500ms

    func subscribeToPositions() async {
        // Cancel any existing subscription loop before creating a new one.
        subscriptionTask?.cancel()
        await realtimeChannel?.unsubscribe()

        let channel = supabase.channel("paper_trading_positions")
        realtimeChannel = channel

        // Scope subscription to current user for defense-in-depth (RLS enforces server-side)
        let userId = supabase.auth.currentUser?.id.uuidString
        let changes = channel.postgresChange(
            AnyAction.self, schema: "public",
            table: "paper_trading_positions",
            filter: userId.map { "user_id=eq.\($0)" }
        )
        await channel.subscribe()

        subscriptionTask = Task { [weak self] in
            for await _ in changes {
                guard !Task.isCancelled else { break }
                await self?.reloadDebouncer.debounce { [weak self] in
                    await self?.loadData()
                }
            }
        }
    }

    func unsubscribe() async {
        subscriptionTask?.cancel()
        subscriptionTask = nil
        await realtimeChannel?.unsubscribe()
        realtimeChannel = nil
    }
}
```

---

### Root Cause #4: Two Duplicate `NSViewRepresentable` Structs

**Problem:** `StrategyBuilderWebViewRepresentable` and `BacktestResultsWebViewRepresentable` were ~85% identical — same `makeNSView`, `updateNSView`, `Coordinator`, navigation delegate, and script handler logic.

**Fix:** Single parameterized `FrontendWebViewRepresentable` with `path` and `messageName` parameters:

```swift
private struct FrontendWebViewRepresentable: NSViewRepresentable {
    let path: String
    let messageName: String
    let symbol: String?
    @Binding var loadState: WebViewLoadState
    // ... single implementation handles both Strategy Builder and Backtesting
}

// Outer views become 8-line wrappers:
struct StrategyBuilderWebView: View {
    let symbol: String?
    var body: some View {
        FrontendWebEmbedView(path: "/strategy-builder", messageName: "strategyBuilder",
                             navigationTitle: "Condition Builder",
                             loadingLabel: "Loading Strategy Builder…", symbol: symbol)
    }
}
```

---

### Root Cause #5: `NumberFormatter` Allocated on Every Render Cycle

**Problem:** `formatCurrency()` created a `NumberFormatter` on every call. Since SwiftUI re-evaluates view bodies frequently, this caused high-frequency allocations and, in non-US locales, produced `($123.45)` (accounting format) instead of `-$123.45`.

**Fix:** File-level constant with fixed locale:

```swift
private let currencyFormatter: NumberFormatter = {
    let f = NumberFormatter()
    f.numberStyle = .currency
    f.currencyCode = "USD"
    f.locale = Locale(identifier: "en_US")  // Ensures -$1.23 not ($1.23) on non-US devices
    f.maximumFractionDigits = 2
    return f
}()

private func formatCurrency(_ value: Double) -> String {
    currencyFormatter.string(from: NSNumber(value: value)) ?? "$0.00"
}
```

---

### Additional P2 Fixes

**FRONTEND_URL validation** — `frontendURL()` now validates scheme (`http`/`https`) and host against `allowedHosts` before accepting the env var:
```swift
private func frontendURL(path: String) -> String {
    if let env = ProcessInfo.processInfo.environment["FRONTEND_URL"], !env.isEmpty,
       let components = URLComponents(string: env),
       ["http", "https"].contains(components.scheme ?? ""),
       allowedHosts.contains(components.host ?? "") {
        let base = env.hasSuffix("/") ? String(env.dropLast()) : env
        return base + path
    }
    return "http://localhost:5173" + path
}
```

**Debug print guards** — Removed bare `print()` calls from `onChange`; moved all debug logging inside `#if DEBUG`.

**Exhaustive switch** — `SidebarSection.devtools` moved to a `#if DEBUG` conditional case in the enum itself, making the switch exhaustive without a `default:` catch-all in release builds:
```swift
enum SidebarSection: Hashable {
    case stocks, portfolio, multileg, predictions, tradestation
    case strategyPlatform(StrategyPlatformSection)
    #if DEBUG
    case devtools
    #endif
}
```

**SupabaseService access** — Changed `public class` → `final class`, removed unnecessary `public` on `shared` and `client` (module-internal is correct for a singleton).

**Backend parity:**
- `POST paper-trading-executor { action: "close_position", position_id, exit_price }` — manual close route for native clients
- Executor now writes `current_price` to all open positions each cycle so native dashboard shows live P&L
- `PUT /strategies` now accepts `paper_trading_enabled` in the update payload

---

## Related Documentation

- [docs/plans/2026-02-27-macos-swiftui-overhaul-plan.md](../../plans/2026-02-27-macos-swiftui-overhaul-plan.md) — Architecture plan covering actor migration, WebView embedding strategy, real-time subscription lifecycle
- [docs/plans/2026-02-25-feat-strategy-platform-visual-builder-plan.md](../../plans/2026-02-25-feat-strategy-platform-visual-builder-plan.md) — React component embedding via WKWebView
- [client-macos/SwiftBoltML/Resources/WebChart/swift-bolt-code-review.md](../../../client-macos/SwiftBoltML/Resources/WebChart/swift-bolt-code-review.md) — Prior WKWebView lifecycle review (cache clearing, dismantling patterns)

**Apple Developer References:**
- [WKWebView — Apple Developer Docs](https://developer.apple.com/documentation/webkit/wkwebview)
- [WKScriptMessageHandler](https://developer.apple.com/documentation/webkit/wkscriptmessagehandler) — Safe message passing without `eval()`
- [Task — Swift Concurrency](https://developer.apple.com/documentation/swift/task)
- [WWDC21 10019: Meet async/await in Swift](https://developer.apple.com/videos/play/wwdc2021/10019/)
- [Build Configuration Files — Xcode Help](https://help.apple.com/xcode/mac/current/#/dev745c5c974)

---

## Prevention Strategies

### Checklist for Future WKWebView Integrations

1. **One `NSViewRepresentable` per WebView type** — never duplicate `makeNSView`/`updateNSView` across components; parameterise instead
2. **No string interpolation into `evaluateJavaScript()`** — always use `JSONSerialization` or `WKScriptMessageHandler` for bidirectional communication
3. **Set `limitsNavigationsToAppBoundDomains = true`** and implement `decidePolicyFor` to whitelist hosts
4. **Add `WeakScriptHandler` proxy** when adding a script message handler to break the `WKUserContentController` retain cycle
5. **Implement `dismantleNSView`** to call `removeAllScriptMessageHandlers()` on teardown
6. **Test lifecycle** by rapidly toggling views on/off; check that tasks cancel and memory doesn't grow

### Swift Concurrency — Task Lifecycle Rules

- Store every `Task` as a property; never let it be a local fire-and-forget
- Cancel the stored task before creating a new one (re-entry pattern)
- Prefer `.task` view modifier over `Task { }` in `onAppear` — `.task` cancels automatically on view disappear
- Check `Task.isCancelled` inside `for await` loops to allow clean exit
- Always pair subscribe/unsubscribe in `onAppear`/`onDisappear` (or `.task`)

### Xcode Secrets Management — The Rule

> **Never put a secret in a file that is committed to git.**

The correct setup:
```
.gitignore:        Secrets.xcconfig
Committed:         Secrets.xcconfig.example  (template with placeholders)
project.pbxproj:   baseConfigurationReference → Secrets.xcconfig
Info.plist:        $(SUPABASE_URL), $(SUPABASE_ANON_KEY)  (build variable references)
```

CI/CD environments inject secrets via environment variables or a secrets manager — never via committed config files.

### SwiftUI Performance Rules

- `NumberFormatter`, `DateFormatter`, `ISO8601DateFormatter` are expensive — create once as file-level `private let` constants, not inside view bodies or closures called per render
- If the formatter needs locale/currency locked, set it at initialisation time
- Profile with Instruments → Allocations to verify formatter calls aren't appearing in the hot path

### Code Review Checklist (Swift PRs)

- [ ] No API keys, tokens, or base URLs in committed `Info.plist` / `xcconfig`
- [ ] No string interpolation in `evaluateJavaScript()` calls
- [ ] All `Task { }` blocks stored and cancelled; no fire-and-forget
- [ ] No duplicate `NSViewRepresentable` structs with >70% similarity
- [ ] All expensive objects (formatters, caches) created at file or `@StateObject` level
- [ ] All `print()` / `debugPrint()` inside `#if DEBUG`
- [ ] No `switch` with bare `default:` on enums defined in the same module
- [ ] Singleton access modifiers are `internal` or narrower — not `public`
