---
title: "PR #25 P1 Bugs: Backtest Auth, API Two-Tier Contract, Type Boundary, and Struct Scope"
date: "2026-03-02"
category: "integration-issues"
tags: [swift, swiftui, backtest, auth, chart, notification-center, strategy-builder, type-mismatch, scope-error, supabase, wkwebview]
module: "client-macos"
symptom: "Backtests timed out for authenticated users; strategy editor loaded empty on selection; no trade markers appeared on chart after a successful backtest; compilation error in IntegratedStrategyBuilder"
root_cause: "Four independent defects in the macOS client: (1) BacktestService.fetchJobStatus used the anon key instead of the user JWT; (2) saveStrategyToSupabase was defined after the closing brace of IntegratedStrategyBuilder making it a free function at file scope; (3) strategy picker used the list-endpoint name-only response and never fetched full config; (4) BacktestingViewModel posted [BacktestResponse.Trade] over NotificationCenter but WebChartView cast it as [[String: Any]], which always silently fails"
related_todos: [069, 070, 071, 078]
pr: "25"
---

# PR #25 P1 Bugs: Backtest Auth, API Two-Tier Contract, Type Boundary, and Struct Scope

Four independent P1 defects discovered during PR #25 review. All four were in the macOS SwiftUI client. Together they caused: backtest polling failure for authenticated users, an empty strategy editor on load, no chart trade markers, and a compile error.

## Root Cause

**Bug 1 — fetchJobStatus used anon key:** The backtest job status GET poll used `Config.supabaseAnonKey` as a Bearer token while the submit POST correctly used the user's JWT. The server's user_id filter resolved as anonymous and returned no rows. Backtest jobs would submit successfully but polling would 401/return nothing indefinitely. Additionally the URL construction had a force-unwrap (`components.url!`).

**Bug 2 — Function outside struct body:** A misplaced closing `}` at line 195 ended the `IntegratedStrategyBuilder` struct early. `saveStrategyToSupabase` was placed in a `// MARK: - Supabase Helpers` section below that closing brace — making it a free function at file scope. A dangling `}` at the end of the block completed the invalid structure. The function referenced `strategyListVM` (a `@State` property on the struct), which was not in scope.

**Bug 3 — Strategy picker used list-only response:** The strategy list endpoint returns lightweight rows (name, id, status only). When the user selected a strategy, the code constructed `Strategy(name: supabaseStrategy.name)` — an empty local shell — and never called the detail endpoint (`GET ?id=`). Every previously-saved strategy appeared empty in the editor.

**Bug 4 — NotificationCenter trades type mismatch:** `BacktestingViewModel` posted `display.trades` (type `[BacktestResponse.Trade]`, a Swift `Decodable` struct) in `userInfo`. `WebChartView` cast it as `[[String: Any]]`. Swift does not bridge custom structs to dictionaries — the `as?` cast always returned `nil`, so `trades` was always `[]`. `ChartBridge.setBacktestTrades([])` was called after every backtest: no markers ever rendered.

## Solution

### Bug 1 — Use JWT in fetchJobStatus

Replace the hardcoded anon-key Bearer header with the live session access token, and replace the force-unwrap with `guard let`:

**Before:**
```swift
var request = URLRequest(url: components.url!)
request.httpMethod = "GET"
request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
```

**After:**
```swift
guard let url = components.url else {
    throw BacktestServiceError.invalidURL
}
var request = URLRequest(url: url)
request.httpMethod = "GET"
request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
if let session = try? await SupabaseService.shared.client.auth.session {
    request.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")
} else {
    request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
}
```

The `apikey` header still carries the anon key (required by Supabase for routing). The `Authorization` header now carries the user's JWT when a session exists, falling back to anon key only when unauthenticated.

---

### Bug 2 — Move helper functions inside struct body

The premature `}` closed the struct before the helper section. Remove it and place the single closing brace after all methods:

**Before (broken):**
```swift
struct IntegratedStrategyBuilder: View {
    @State private var strategyListVM = StrategyListViewModel()
    // ... body, headerBar ...
}   // ← struct closes here (line 195)

    // MARK: - Supabase Helpers   ← OUTSIDE struct!
    private func saveStrategyToSupabase(_ strategy: Strategy) async {
        await strategyListVM.createStrategy(...)  // strategyListVM not in scope
    }
}   // ← dangling brace
```

**After (fixed):**
```swift
struct IntegratedStrategyBuilder: View {
    @State private var strategyListVM = StrategyListViewModel()
    // ... body, headerBar ...

    // MARK: - Supabase Helpers   ← INSIDE struct
    private func saveStrategyToSupabase(_ strategy: Strategy) async {
        await strategyListVM.createStrategy(...)  // in scope ✓
    }
}   // ← single closing brace
```

---

### Bug 3 — Fetch full strategy config on selection

Replace the stub `Strategy(name:)` construction with an async fetch of the full strategy record, mapping all persisted fields back onto the local model:

**Before:**
```swift
ForEach(strategyListVM.strategies) { supabaseStrategy in
    Button(supabaseStrategy.name) {
        // Load full strategy from local model for now
        selectedStrategy = Strategy(name: supabaseStrategy.name)
    }
}
```

**After:**
```swift
ForEach(strategyListVM.strategies) { supabaseStrategy in
    Button(supabaseStrategy.name) {
        Task {
            do {
                let full = try await StrategyService.shared.getStrategy(id: supabaseStrategy.id)
                var strategy = Strategy(name: full.name)
                strategy.description = full.description
                strategy.entryConditions = full.config.entryConditions.map { fromSupabaseCondition($0) }
                strategy.exitConditions = full.config.exitConditions.map { fromSupabaseCondition($0) }
                strategy.isActive = full.isActive
                if let p = full.config.parameters["stop_loss"], case .double(let v) = p { strategy.stopLoss = v }
                if let p = full.config.parameters["take_profit"], case .double(let v) = p { strategy.takeProfit = v }
                if let p = full.config.parameters["position_size"], case .double(let v) = p { strategy.positionSize = v }
                selectedStrategy = strategy
            } catch {
                selectedStrategy = Strategy(name: supabaseStrategy.name)
            }
        }
    }
}
```

The `catch` branch retains graceful degradation: a network failure shows the strategy with its name rather than crashing.

> **Note:** The `fromSupabaseCondition()` free function in `StrategyService.swift` was previously flagged as dead code (todo 076). It is now used here. Remove it from the dead-code removal list.

---

### Bug 4 — Serialize trades to `[[String: Any]]` before posting

Swift does not bridge custom structs to `[String: Any]`. Serialize each `BacktestResponse.Trade` to a dictionary at the post site so the receiver's `as? [[String: Any]]` cast succeeds:

**Before:**
```swift
// BacktestingViewModel.swift
NotificationCenter.default.post(
    name: .backtestTradesUpdated,
    object: nil,
    userInfo: [
        "trades": display.trades,   // ← [BacktestResponse.Trade] — struct, not dict
        "symbol": sym,
        "generation": generation
    ]
)

// WebChartView.swift
let trades = notification.userInfo?["trades"] as? [[String: Any]] ?? []
// ↑ always returns [] — struct cannot be cast to [[String: Any]]
```

**After:**
```swift
// BacktestingViewModel.swift — serialize before posting
let tradesPayload: [[String: Any]] = display.trades.map { trade in
    var dict: [String: Any] = [
        "date": trade.date,
        "symbol": trade.symbol,
        "action": trade.action,
        "quantity": trade.quantity,
        "price": trade.price
    ]
    if let v = trade.pnl { dict["pnl"] = v }
    if let v = trade.entryPrice { dict["entryPrice"] = v }
    if let v = trade.exitPrice { dict["exitPrice"] = v }
    if let v = trade.duration { dict["duration"] = v }
    if let v = trade.fees { dict["fees"] = v }
    return dict
}
NotificationCenter.default.post(
    name: .backtestTradesUpdated,
    object: nil,
    userInfo: [
        "trades": tradesPayload,   // ← [[String: Any]] ✓
        "symbol": sym,
        "generation": generation
    ]
)
```

Optional fields are only inserted when non-nil, matching the sparse representation ChartBridge's JS consumer expects.

## Prevention Strategies

### Auth header inconsistency across HTTP methods

- When reviewing a service class, read ALL methods that reference the same endpoint URL before approving any one of them. Auth is a class-level concern, not a method-level one.
- Flag any method that sets `Authorization` inline rather than through a shared `addAuthHeaders` helper. The presence of `request.setValue("Bearer \(anonKey)")` should trigger a full audit of sibling methods.
- Require auth header injection in exactly one place per service class. `StrategyService.addAuthHeaders()` (lines 268-272) is the established pattern — new services should follow it.
- Write a unit test per service that asserts every public method calling a JWT-protected endpoint uses a JWT token, not the anon key. Use a `URLProtocol` stub to capture outgoing requests and inspect headers.
- In CI, grep for the anon key constant and flag any file that references it alongside a protected endpoint URL.

### Method placed outside struct/class body

- When adding a method to the bottom of a long file, always scroll past the new code to confirm the enclosing type's closing `}` follows immediately. A diff that shows a new `func` with no enclosing type visible in its context window is a red flag.
- `// MARK:` comments do not establish scope in Swift. Treat any MARK that appears near — but not visibly inside — a type definition as suspect.
- Flag dangling `}` at end of file as a mandatory fix. A well-formed Swift file ends with the last `}` of the last type, with nothing after it.
- Keep service files under 300 lines. Extract into `TypeName+Category.swift` extension files when a file grows large. Extensions make scope explicit in syntax rather than relying on brace counting.
- Prefer explicit `extension IntegratedStrategyBuilder { ... }` blocks over dumping all helpers into one long struct body.

### Two-tier API (list vs detail) — only list endpoint used

- Any time a UI component renders fields that are not present in the list response schema, the reviewer must ask: "Where is this data coming from?" If the answer is the list response, it is a defect.
- When reviewing a feature that shows detail after selecting from a list, check whether a detail endpoint exists. Read the Edge Function or API contract docs.
- Encode the split in Swift types: define `StrategyListItem` (name, id, status) and `StrategyDetail` (adds conditions, config) as distinct types. A function accepting `StrategyDetail` cannot be called with a `StrategyListItem` — the compiler enforces the fetch.
- Document the split explicitly in the Edge Function comment: `// GET /strategies — list items only (name, id). Use GET /strategies?id= for full config.`

### NotificationCenter userInfo type mismatch

- Any `NotificationCenter.post(userInfo:)` with a Swift struct, array of structs, or class instance is a defect. `userInfo` values must be property-list-compatible types or explicitly bridged.
- On the receiver side, `as? [[String: Any]]` on a value posted as a Swift type always silently returns nil. Require the reviewer to trace the post site and confirm types are compatible.
- The canonical correct approach: either (a) serialize the struct to `[[String: Any]]` at the post site (done here), or (b) post the typed value as `object:` and cast it back to the concrete type — never to a dictionary — on the receiver side.
- For intra-module typed communication, prefer Combine `PassthroughSubject<[BacktestResponse.Trade], Never>` over NotificationCenter. Checked at compile time.
- Write a unit test that posts the notification with the real payload and asserts the receiver's handler was called with a non-empty, non-nil value. Silent `as?` failures make these bugs invisible without explicit assertions.

### Reviewing service classes with multiple methods on the same endpoint

1. Find all methods referencing the endpoint URL (grep for the URL string constant).
2. Confirm Authorization headers are set identically across all methods.
3. Confirm response types are decoded consistently, or that intentional differences (list vs detail) use distinct Swift types.
4. Check that error handling is symmetric — if POST has error reporting, GET on the same endpoint should too.
5. Confirm shared state (loading flags, caches) is updated consistently across all paths.

## Related Issues & Cross-References

### Todos fixed in this session

| Todo | Status | Description |
|------|--------|-------------|
| `todos/069-resolved-p1-backtest-polling-uses-anon-key.md` | ✅ Resolved | fetchJobStatus JWT fix |
| `todos/070-resolved-p1-save-strategy-function-outside-struct.md` | ✅ Resolved | struct brace fix |
| `todos/071-resolved-p1-strategy-selection-loads-empty-shell.md` | ✅ Resolved | getStrategy(id:) wired in |
| `todos/078-resolved-p1-backtest-trades-type-mismatch-chart-markers.md` | ✅ Resolved | trades serialization fix |

### Related open todos

| Todo | Status | Description |
|------|--------|-------------|
| `todos/072-pending-p2-strategy-builder-webview-missing-symbol-in-notification.md` | Pending | StrategyBuilderWebView posts `.backtestTradesUpdated` without `"symbol"` key — the fix in WebChartView uses `if let`, so React-originated backtests bypass the symbol guard |
| `todos/075-pending-p2-update-delete-strategy-not-wired.md` | Pending | Save always calls createStrategy, never updateStrategy. Depends on todo 071. |
| `todos/076-pending-p2-dead-code-removal.md` | Pending | `fromSupabaseCondition()` is now used by the fix in todo 071 — remove it from the dead-code list before implementing 076 |
| `todos/077-pending-p3-wkwebview-hardening.md` | Pending | WeakScriptHandler + navigation policy for WebChartView |

### Known pattern: preset backtest path not yet fixed

The type mismatch fix (bug 4) was applied to `runStrategyBacktest()` (the custom-strategy path). The preset backtest path in `BacktestingViewModel.startPolling()` / `runBacktest()` around lines 272-280 still posts `display.trades` as a raw struct array. It needs the same serialization treatment.

### Established auth patterns in the codebase

Two auth patterns exist in the Swift services — use the right one based on whether auth is required or optional:

```swift
// Optional auth (submitBacktest pattern) — falls back gracefully:
if let session = try? await SupabaseService.shared.client.auth.session {
    request.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")
} else {
    request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
}

// Required auth (StrategyService.addAuthHeaders pattern) — throws on failure:
private func addAuthHeaders(_ request: inout URLRequest) async throws {
    let session = try await SupabaseService.shared.client.auth.session
    request.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")
    request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
}
```

### WeakScriptHandler + navigation policy (established pattern, PR #23)

Both patterns live in `StrategyBuilderWebView.swift` (lines 231-243 and 173-185) and are the reference implementation. Still needed in `WebChartView.swift` (todo 077).

### Related solution doc

`docs/solutions/security-issues/swiftui-credential-and-injection-hardening.md` — documents all PR #23 fixes including credential handling, JS injection prevention, WKWebView integration checklist, and the `NumberFormatter` per-render allocation pattern.
