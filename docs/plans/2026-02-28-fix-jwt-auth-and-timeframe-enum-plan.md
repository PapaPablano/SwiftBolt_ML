---
title: "fix: JWT 401 cascade and timeframe enum mismatch"
type: fix
status: completed
date: 2026-02-28
deepened: 2026-02-28
---

# fix: JWT 401 Cascade and Timeframe Enum Mismatch

## Enhancement Summary

**Deepened on:** 2026-02-28
**Research agents used:** best-practices-researcher, security-sentinel, architecture-strategist, Context7 docs (Supabase Swift SDK), code-simplicity-reviewer, performance-oracle

### Key Improvements From Research

1. **Fix 1 must change** — the proposed Task-based sign-out has a confirmed race condition, a macOS Keychain bug in `signOut(scope: .local)`, and triggers a network call on startup. All 6 agents independently converged on the same better fix: `EphemeralAuthStorage` passed to `SupabaseClientOptions.auth.storage` eliminates the problem at construction time with zero async overhead.

2. **Fix 2 fallback should use `"d1"` not `selectedTimeframe`** — the `?? selectedTimeframe` fallback silently passes the original invalid display string if `Timeframe(from:)` fails, masking future bugs. `?? "d1"` is always a valid API token.

3. **`checkSupabaseConnectivity` is NOT a gate** — the architecture analysis confirmed a structural race: SwiftUI fires `.onAppear` (which triggers `bootstrapForDebug → selectSymbol → loadChart`) simultaneously with `.task { await checkSupabaseConnectivity() }`. There is no ordering guarantee. The fire-and-forget Task plan relied on this gate as mitigation, but the gate doesn't exist.

4. **`ChartViewModel` has its own orphaned `SupabaseClient`** — found during architecture review. `ChartViewModel.init` constructs a separate `SupabaseClient` with `emitLocalSessionAsInitialSession: true`. This is architecturally unsound and should also receive the `EphemeralAuthStorage` fix. Flagged as a follow-up.

5. **SwiftUI re-renders root cause identified** — the `objectWillChange` relay chain in `AppViewModel` (6 subscriptions, one per child view model) fires 10–20 emissions per symbol load. This is the direct cause of the "dozens of re-renders" in the logs. Out-of-scope for this fix but precisely diagnosed.

### New Considerations Discovered
- `signOut(scope: .local)` has a confirmed macOS Keychain bug (supabase-swift Discussion #32552) — sessions are not reliably cleared. Never use this as the primary cleanup mechanism.
- `AuthClientConfiguration` in the Swift SDK takes `localStorage: any AuthLocalStorage` (not `persistSession: Bool` — that flag only exists in supabase-js).
- `autoRefreshToken: Bool` exists in the Swift SDK and should be `false` for anon-only apps.
- `IntegratedStrategyBuilder` picker includes `"30m"` and `"5m"` which have no matching `Timeframe` enum cases — latent bug, out of scope here.
- The `Timeframe(from:)` normaliser is a zero-cost pure function (<1µs). No performance concerns.

---

## Overview

Two bugs are preventing core features from loading on every app launch:

1. **JWT 401 cascade** — `chart-data-v2`, `SymbolSync`, `log-validation-audit`, and the Supabase Realtime WebSocket all fail with `{"code":401,"message":"Invalid JWT"}`. The Supabase SDK is restoring a stale auth session from a previous run and sending its expired JWT instead of the anon key before the token refresh completes.

2. **Timeframe enum `"1D"` → `"d1"` mismatch** — `UnifiedIndicatorsService.selectedTimeframe` is initialised to the display string `"1D"`. This value is passed raw to `APIClient.fetchTechnicalIndicators`, which forwards it to the FastAPI backend at `localhost:8000/api/v1/technical-indicators?timeframe=1D`. The DB enum expects lowercase `d1`, causing a 400 error on every chart load and preventing technical indicators from rendering.

---

## Problem Statement

### Bug 1 — JWT 401 Cascade

**Root cause (confirmed by research):** `SupabaseService.shared.client` is initialised at app start. The Supabase Swift SDK automatically restores any previously-stored auth session from its internal persistent storage (Keychain on macOS). If that session's access token (JWT) is expired and the refresh token is also expired or malformed, the SDK sends the stale JWT on API calls that fire before the async refresh completes, producing 401s on:

- `chart-data-v2` (loads chart OHLCV + forecasts)
- `sync-user-symbols` (SymbolSync)
- `log-validation-audit`
- Realtime WebSocket handshake

The SDK itself logs the symptom:
```
Initial session emitted after attempting to refresh the local stored session.
This is incorrect behavior and will be fixed in the next major release...
```

The app has **no intentional user sign-in flow** — all API calls are meant to use the static `supabaseAnonKey`. The stale session is a leftover from development testing.

**Impact:** `chart-data-v2` never loads (fallback to `chart-read` works but is missing ML forecasts and v2 features). SymbolSync never completes. Audit log silently drops every event. Realtime WebSocket fails.

**Relevant files:**
- `client-macos/SwiftBoltML/Services/SupabaseService.swift:1–18` — SDK init (fix site)
- `client-macos/SwiftBoltML/Services/APIClient.swift:738` — chart-data-v2 auth headers
- `client-macos/SwiftBoltML/Services/APIClient.swift:1138` — fetchConsolidatedChart auth headers
- `client-macos/SwiftBoltML/Services/SymbolSyncService.swift:46` — sync-user-symbols auth header
- `client-macos/SwiftBoltML/ViewModels/AppViewModel.swift:152–155` — connectivity check at startup

### Research Insights — Bug 1

**SDK internals (confirmed from source):**
- `client.auth.session` is `async throws`. On macOS it reads from `KeychainLocalStorage`. If the token is expired it attempts a network refresh — this can add 100–800ms to startup on a slow connection.
- `signOut(scope: .local)` does NOT reliably clear Keychain entries on macOS. The session may be restored on the next launch. See [supabase-swift Discussion #32552](https://github.com/orgs/supabase/discussions/32552).
- The Swift SDK does not have a `persistSession: Bool` flag (unlike supabase-js). Session persistence is controlled entirely through the `localStorage` parameter on `AuthClientConfiguration`.
- `autoRefreshToken: Bool` controls the background token-refresh timer. For anon-only apps this should be `false`.

**Race condition in the proposed Task approach:**
The Task runs fire-and-forget. The SDK restores the persisted session immediately at `SupabaseClient(...)` construction — before the Task body executes. Every call site that touches `SupabaseService.shared.client` in the same launch cycle (which `PaperTradingService`, `APIClient`, and all view models do immediately via `onAppear`) will have a `client` whose in-memory auth state still holds the stale JWT. The Task wins the race only if no API calls fire for hundreds of milliseconds — which never happens in practice.

**`checkSupabaseConnectivity()` is NOT a gate:**
Architecture analysis confirmed that `.onAppear { bootstrapForDebug() }` fires synchronously during the layout pass, while `.task { await checkSupabaseConnectivity() }` runs as a concurrent async task. There is no ordering guarantee. `SupabaseConnectivity.isReachable` defaults to `true` (line 11 of the source), so the short-circuit in `APIClient.performRequest` does not block chart calls fired during the connectivity check window.

---

### Bug 2 — Timeframe Enum Format Mismatch

**Root cause (confirmed by research):** The `Timeframe` enum in `Timeframe.swift` has two distinct string representations for daily timeframe:

| Property | Value for `.d1` |
|---|---|
| `.rawValue` / `.apiToken` | `"d1"` ← what DB/FastAPI expects |
| `.displayName` / `.toHorizonString()` | `"1D"` ← UI label only |

`UnifiedIndicatorsService.selectedTimeframe` (`String`) is initialised to `"1D"` (display format) at line 11 of `UnifiedIndicatorsService.swift`. When `loadIndicators` calls `APIClient.fetchTechnicalIndicators(symbol:timeframe:)`, it passes this raw string. The FastAPI receives `timeframe=1D` and fails:

```
invalid input value for enum timeframe: "1D"
```

A safe normalisation path already exists: `Timeframe(from: "1D")?.apiToken` → returns `"d1"`. The `Timeframe(from:)` initialiser (lines 62–78 of `Timeframe.swift`) is a robust parser that accepts both formats. It is not being called at this site.

**Relevant files:**
- `client-macos/SwiftBoltML/Services/UnifiedIndicatorsService.swift:11` — `selectedTimeframe = "1D"` initial value (fix site)
- `client-macos/SwiftBoltML/Services/UnifiedIndicatorsService.swift:~184` — call to `fetchTechnicalIndicators` (fix site)
- `client-macos/SwiftBoltML/Services/APIClient.swift:1734–1767` — `fetchTechnicalIndicators` passes `timeframe` raw to FastAPI
- `client-macos/SwiftBoltML/Models/Timeframe.swift:62–78` — `Timeframe(from:)` normaliser (already exists, unused here)
- `client-macos/SwiftBoltML/Views/IntegratedStrategyBuilder.swift:124–127` — Picker bound directly to `$indicatorsService.selectedTimeframe` with display strings

### Research Insights — Bug 2

**Latent bug in `IntegratedStrategyBuilder` picker:**
The picker at line 124–127 uses `["1D", "4H", "1H", "30m", "15m", "5m"]` as selection tags. Of these, `"30m"` and `"5m"` have no corresponding `Timeframe` enum cases. If `Timeframe(from:)` is asked to parse `"5m"` it will return `nil`, causing the fallback to fire. If the fallback is `?? selectedTimeframe`, the invalid display string is passed to the API unchanged. If the fallback is `?? "d1"`, the API gets a valid but wrong timeframe. Either way, the result is incorrect. These picker values must be reconciled with the `Timeframe` enum as a follow-up (add `.m5`/`.m30` cases, or remove those picker options).

**Performance of `Timeframe(from:)`:** Zero-cost — it is a pure function with a string switch, runs in under 1µs. No caching needed.

---

## Proposed Solution

### Fix 1 — Disable Session Persistence via `EphemeralAuthStorage`

**CHANGED from original plan.** The Task-based sign-out approach is replaced with a storage-level fix that eliminates the problem before it can occur.

Add a private `EphemeralAuthStorage` conformance and pass it to `SupabaseClientOptions`. The SDK will never read from or write to Keychain, so no stale JWT can survive across launches.

```swift
// SupabaseService.swift

import Supabase
import Foundation

/// A no-op `AuthLocalStorage` adapter.
/// The app uses the anon key only and has no user login flow.
/// This prevents the SDK from persisting sessions to Keychain,
/// which eliminates the stale-JWT 401 cascade on cold launch.
private final class EphemeralAuthStorage: AuthLocalStorage, @unchecked Sendable {
    func store(key: String, value: Data) throws {}    // intentional no-op
    func retrieve(key: String) throws -> Data? { nil }
    func remove(key: String) throws {}               // intentional no-op
}

/// Singleton wrapper around the Supabase Swift SDK client.
final class SupabaseService {
    static let shared = SupabaseService()

    let client: SupabaseClient

    private init() {
        let url = Config.supabaseURL
        let anonKey = Config.supabaseAnonKey
        client = SupabaseClient(
            supabaseURL: url,
            supabaseKey: anonKey,
            options: SupabaseClientOptions(
                auth: .init(
                    storage: EphemeralAuthStorage(),
                    autoRefreshToken: false   // no user session to refresh
                )
            )
        )
    }
}
```

**Why this is strictly better than the Task approach:**

| Concern | Task-based sign-out | `EphemeralAuthStorage` |
|---|---|---|
| Race condition with first API call | Always present — Task runs concurrently | Impossible — no session is ever loaded |
| macOS Keychain clearing reliability | Broken (`signOut(scope:.local)` bug #32552) | N/A — no Keychain writes |
| Network call on startup | Possible (session refresh attempt in `auth.session`) | None |
| Swift 6 strict concurrency | Warning — unstructured Task in `init` | Clean — synchronous init |
| Code size | +6 lines (Task + nil check + signOut + error swallow) | +10 lines (EphemeralAuthStorage) |
| SRP | `init` does session management (violation) | `init` only creates client (correct) |

**Note on `ChartViewModel`:** Architecture review found that `ChartViewModel.init` constructs a separate `SupabaseClient` instance with `emitLocalSessionAsInitialSession: true`. This second client has its own session state and does not benefit from the `SupabaseService` fix. Apply the same `EphemeralAuthStorage` options there too, or (preferred) remove the second client and inject `SupabaseService.shared.client`. Tracked as a follow-up.

---

### Fix 2 — Normalise Timeframe at `UnifiedIndicatorsService` Call Site

Two one-line changes:

**Change 1 — Initial value** (`UnifiedIndicatorsService.swift:11`):
```swift
// Before:
@Published var selectedTimeframe: String = "1D"

// After:
@Published var selectedTimeframe: String = "d1"
```

**Change 2 — Call site normalisation** (`UnifiedIndicatorsService.swift:~184`):
```swift
// Before:
APIClient.shared.fetchTechnicalIndicators(symbol: symbol, timeframe: selectedTimeframe, ...)

// After:
let apiTimeframe = Timeframe(from: selectedTimeframe)?.apiToken ?? "d1"
APIClient.shared.fetchTechnicalIndicators(symbol: symbol, timeframe: apiTimeframe, ...)
```

**Why `?? "d1"` not `?? selectedTimeframe`:**
If `selectedTimeframe` is `"30m"` (a picker value with no `Timeframe` case), `Timeframe(from:)` returns `nil` and the fallback fires. Using `?? selectedTimeframe` passes `"30m"` to the API unchanged, producing a 400 error that looks identical to the original bug. Using `?? "d1"` (a known-valid API token) prevents a new 400 while making the fallback case visible in the picker (daily timeframe shows instead of nothing). The incorrect picker values are a separate follow-up.

**Option B (typed `Timeframe` property):**
Architecturally stronger — changes `selectedTimeframe: String` to `selectedTimeframe: Timeframe = .d1`. Blocked by the `IntegratedStrategyBuilder` picker using `"30m"` and `"5m"` which have no `Timeframe` cases. This refactor must wait until those cases are added or those picker options are removed. Defer to a follow-up.

---

## Technical Considerations

- `EphemeralAuthStorage` conforms to `AuthLocalStorage` with `@unchecked Sendable`. The `@unchecked` is safe because it has no mutable state.
- `autoRefreshToken: false` prevents the SDK from starting a background refresh timer. This is correct for anon-only apps and eliminates a background task that would never succeed.
- The `chart-read` fallback continues to work (confirmed in logs) — no regression risk.
- The timeframe normalisation path (`Timeframe(from:)`) handles `"1D"`, `"d1"`, `"1d"`, `"daily"` etc. It is production-tested. Cost is <1µs per call.
- **`log-validation-audit` failures**: silent fire-and-forget audit calls. After fixing the JWT, they will succeed. No user-visible change.
- **Realtime WebSocket**: `PaperTradingService.subscribeToPositions()` uses `supabase.channel(...)` which is authenticated via the anon key embedded in `SupabaseClient`. With no stale session overriding the auth header, the Realtime handshake should succeed cleanly.

---

## System-Wide Impact

- **Auth chain**: `SupabaseService.init` → `SupabaseClient(options: EphemeralAuthStorage)` → SDK never reads/writes Keychain → all requests use anon key from `supabaseKey`. Clean and synchronous.
- **Realtime channel**: `PaperTradingService.realtimeChannel` is created after `SupabaseService` is ready. No async gap — the client is fully initialised before any property is accessed.
- **State lifecycle**: `EphemeralAuthStorage` has no mutable state. It does not affect any cached chart data, Keychain values, or `Config.*` properties.
- **Timeframe fix scope**: `UnifiedIndicatorsService` is the only service that initialises `selectedTimeframe` to `"1D"`. `ChartViewModel`, `SymbolSyncService`, and `APIClient` all use `Timeframe.d1.apiToken` → `"d1"` correctly. No other call sites are affected by Fix 2.
- **`IntegratedStrategyBuilder` picker**: the picker's `"1D"` tag is a display string bound to `$indicatorsService.selectedTimeframe`. After Fix 2 changes the initial value to `"d1"`, the picker's `"1D"` tag will no longer match `selectedTimeframe`'s default value, meaning no row will appear selected on first open. Fix: change the `"1D"` tag to `"d1"` or map the picker to `apiToken` values. Trivial one-line change, include in this PR.
- **Integration test scenario**: Cold launch → select AAPL → switch to daily timeframe → verify `technical-indicators` returns 200 and indicators render. Verify no 401s in console. Verify SDK session warning is gone.

---

## Acceptance Criteria

- [ ] No `{"code":401,"message":"Invalid JWT"}` errors appear in the console on cold launch
- [ ] `chart-data-v2` returns 200 on first load (no fallback to `chart-read` required)
- [ ] `sync-user-symbols` (SymbolSync) completes successfully on launch
- [ ] `log-validation-audit` calls return 200 (not silent 401)
- [ ] Supabase Realtime WebSocket connects on first attempt
- [ ] `/api/v1/technical-indicators` returns 200 with `timeframe=d1` (not 400 with `timeframe=1D`)
- [ ] Technical indicator overlays render on the chart for daily timeframe
- [ ] No regression: `chart-read` fallback still works if `chart-data-v2` is unavailable
- [ ] Supabase SDK session warning does not appear (EphemeralAuthStorage means no session to restore)
- [ ] Build succeeds with no new warnings (`xcodebuild ... build`)

---

## Implementation Tasks

- [ ] **SupabaseService.swift**: Add `EphemeralAuthStorage` private class; update `SupabaseClient` init to pass `options: SupabaseClientOptions(auth: .init(storage: EphemeralAuthStorage(), autoRefreshToken: false))`
- [ ] **UnifiedIndicatorsService.swift:11**: Change `selectedTimeframe` initial value from `"1D"` to `"d1"`
- [ ] **UnifiedIndicatorsService.swift:~184**: Change normalisation fallback to `Timeframe(from: selectedTimeframe)?.apiToken ?? "d1"`
- [ ] **IntegratedStrategyBuilder.swift:124–127**: Change picker tag `"1D"` to `"d1"` so the picker's default selection matches `selectedTimeframe`'s new initial value
- [ ] Build and verify: `xcodebuild ... build` succeeds with no new errors/warnings
- [ ] Manual test: cold launch with logging → confirm no 401s, confirm indicators render, confirm no SDK session warning

## Out of Scope

- **Excessive SwiftUI re-renders** — Root cause confirmed: 6 `objectWillChange` relay subscriptions in `AppViewModel.init` (lines 99–138) emit 10–20 times per symbol load. Fix: remove the relay subscriptions and inject child view models directly. Separate PR.
- **`ChartViewModel` second `SupabaseClient` instance** — Needs `EphemeralAuthStorage` applied as well, or the instance should be removed in favour of injecting `SupabaseService.shared.client`. Follow-up PR.
- **`IntegratedStrategyBuilder` picker `"30m"`/`"5m"` with no `Timeframe` cases** — Latent bug. Add `.m5`/`.m30` cases or remove those picker options. Follow-up PR.
- **Option B typed `Timeframe` property on `UnifiedIndicatorsService`** — Correct long-term fix. Blocked by picker remediation above. Follow-up PR.
- **`APIClient` method signatures should accept `Timeframe` not `String`** — Correct architectural fix. Prevents recurrence of format mismatch bugs. Separate refactor PR.
- **WebContent sandbox errors** — Expected in debug builds, not real bugs.
- **FastAPI `localhost:8000` timeout** — Server must be running locally; no client-side fix needed.

---

## Dependencies & Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| `EphemeralAuthStorage` not conforming to `AuthLocalStorage` protocol on SDK 2.39.0 | Low | Verified protocol shape from SDK source: three throwing methods `store/retrieve/remove` |
| `autoRefreshToken: false` breaks Realtime WebSocket auth | Low | Realtime auth uses the `supabaseKey` (anon JWT) directly, not the user session refresh cycle |
| `IntegratedStrategyBuilder` picker shows no selection after default changes to `"d1"` | Medium | Included in tasks: change picker tag `"1D"` → `"d1"` in same PR |
| `Timeframe(from:)` returns `nil` for edge-case display strings | Low | Fallback `?? "d1"` returns valid API token; indicators may load with wrong timeframe but no crash or 400 |
| `ChartViewModel`'s own `SupabaseClient` still uses Keychain storage | Medium | This client is used only for chart calls that go through `APIClient`; if its auth session is also stale, those calls may still 401. Follow-up PR applies `EphemeralAuthStorage` there too. |

---

## Sources & References

### Internal

- `client-macos/SwiftBoltML/Services/SupabaseService.swift:1–18` — SDK init (fix site)
- `client-macos/SwiftBoltML/Services/UnifiedIndicatorsService.swift:11` — bad initial value (fix site)
- `client-macos/SwiftBoltML/Services/UnifiedIndicatorsService.swift:~184` — API call site
- `client-macos/SwiftBoltML/Services/APIClient.swift:1734–1767` — `fetchTechnicalIndicators`
- `client-macos/SwiftBoltML/Models/Timeframe.swift:62–78` — `Timeframe(from:)` normaliser (already exists)
- `client-macos/SwiftBoltML/Services/APIClient.swift:738` — `chart-data-v2` auth headers
- `client-macos/SwiftBoltML/Services/SymbolSyncService.swift:46` — `sync-user-symbols` auth
- `client-macos/SwiftBoltML/Views/IntegratedStrategyBuilder.swift:124–127` — picker bound to `selectedTimeframe`
- `client-macos/SwiftBoltML/ViewModels/AppViewModel.swift:99–138` — `objectWillChange` relay chain (re-render root cause)
- `client-macos/SwiftBoltML/ViewModels/ChartViewModel.swift:279` — second `SupabaseClient` with `emitLocalSessionAsInitialSession: true`
- `docs/solutions/security-issues/swiftui-credential-and-injection-hardening.md` — credential loading context

### Related SDK Behaviour

- Supabase Swift SDK 2.39.0: `AuthLocalStorage` protocol — three throwing methods: `store(key:value:)`, `retrieve(key:) -> Data?`, `remove(key:)`. No `persistSession: Bool` flag (unlike supabase-js).
- `autoRefreshToken: Bool` in `AuthClientConfiguration` — controls background token-refresh timer. Safe to set `false` for anon-only apps.
- **Known macOS Keychain bug**: `signOut(scope: .local)` does not reliably clear Keychain session entries on macOS. See [supabase-swift Discussion #32552](https://github.com/orgs/supabase/discussions/32552).
- The `EphemeralAuthStorage` pattern sidesteps the Keychain bug entirely by never writing to it.
