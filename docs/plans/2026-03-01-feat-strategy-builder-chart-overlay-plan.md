---
title: "feat: Wire Native Strategy Builder to Backend with Chart Overlays"
type: feat
status: completed
date: 2026-03-01
origin: docs/brainstorms/2026-03-01-strategy-builder-chart-overlay-brainstorm.md
deepened: 2026-03-01
---

# Wire Native Strategy Builder to Backend with Chart Overlays

## Enhancement Summary

**Deepened on:** 2026-03-01
**Sections enhanced:** All phases restructured + new research insights
**Research agents used:** security-sentinel, performance-oracle, architecture-strategist, code-simplicity-reviewer, pattern-recognition-specialist, race-condition-reviewer, Supabase Auth researcher, WKWebView persistence researcher, Lightweight Charts researcher, institutional-learning checker

### Key Improvements
1. **Phases reduced from 7 to 4** — Merged condition mapper (was Phase 2), trade log (was Phase 5), and tab navigation (was Phase 7) into their natural parent phases. Estimated ~310 LOC delta vs ~1,000 in original plan.
2. **Reuse existing code** — `BacktestingModels.swift` already has all Codable types (`BacktestJobQueuedResponse`, `BacktestJobStatusResponse`, `BacktestResultPayload`, `BacktestResultTrade`, `BacktestResultEquityPoint`). `BacktestingViewModel.swift` already has polling logic. No re-creation needed.
3. **Race condition fixes** — Symbol guard on `.backtestTradesUpdated` notifications, generation counter for overlapping backtests, clear `pendingBacktestTrades` on symbol change.
4. **Auth pattern corrected** — Use `@Observable` AuthController with Supabase Swift SDK's `authStateChanges` async stream (not Combine publisher). Keychain is default storage.
5. **Exponential backoff polling** — 1s -> 2s -> 4s -> 8s -> 15s cap (not fixed 1s interval), reducing server load for slow backtests.
6. **Security hardening** — Validate condition indicator/operator strings against allowlist before JS interpolation; scope backtest job queries by `user_id`.

### New Considerations Discovered
- `BacktestingViewModel` already exists — plan must NOT create a conflicting `BacktestViewModel`
- `strategy-translator.ts` on the server already normalizes all 3 condition formats — Swift mapper can be ~15 lines (lowercase + operator switch), not a full 47-type mapping table
- ZStack opacity toggle confirmed safe on macOS: JS continues executing at opacity 0, Lightweight Charts canvas renders correctly
- ChartViewModel has 29 `@Published` properties causing cascading SwiftUI invalidation — new VMs should minimize published state
- `pendingCommands` buffer in ChartBridge leaks commands when chart never loads

---

## Overview

The macOS Swift app's strategy builder currently uses mock data with no persistence, no real backtesting, and no chart integration. This plan wires the existing native `IntegratedStrategyBuilder` UI to Supabase edge functions for strategy CRUD, real backtesting, and chart overlays (entry/exit markers + equity curve sub-panel). A Supabase Auth login flow is added to enable JWT-authenticated API calls.

(see brainstorm: docs/brainstorms/2026-03-01-strategy-builder-chart-overlay-brainstorm.md)

## Problem Statement

Users cannot:
1. Save strategies — `StrategyBuilderViewModel.saveStrategy()` writes to an in-memory array only (`StrategyBuilderWebStyle.swift:1156`)
2. Run real backtests — `BacktestWebStyle.runBacktest()` returns `BacktestResult.mock()` (`StrategyBuilderWebStyle.swift:894`)
3. See backtest results on the chart — the overlay pipeline exists (`ChartBridge.setBacktestTrades()` at line 711) but is never called from the native builder
4. Keep overlays across tabs — `WebChartView` is destroyed on tab switch (`ContentView.swift:36-61`)

## Proposed Solution

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  macOS App (SwiftUI)                                        │
│                                                             │
│  ┌──────────────┐  ┌──────────────────────────────────────┐ │
│  │  Sidebar      │  │  Detail Pane (ZStack)                │ │
│  │  ─────────    │  │                                      │ │
│  │  Stocks ●     │  │  ┌──────────────────────────────┐   │ │
│  │  Strategy ○   │  │  │  WebChartView (always alive)  │   │ │
│  │  Portfolio ○  │  │  │  - Candlesticks               │   │ │
│  │  ...          │  │  │  - Backtest markers (overlay)  │   │ │
│  │               │  │  │  - Equity curve (sub-panel)    │   │ │
│  │               │  │  └──────────────────────────────┘   │ │
│  │               │  │                                      │ │
│  │               │  │  ┌──────────────────────────────┐   │ │
│  │               │  │  │  Active Tab Content            │   │ │
│  │               │  │  │  (Strategy Builder / Details)  │   │ │
│  │               │  │  └──────────────────────────────┘   │ │
│  └──────────────┘  └──────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
         │                         │
         │    JWT Bearer Token     │
         ▼                         ▼
┌────────────────────┐  ┌────────────────────────┐
│ strategies         │  │ backtest-strategy       │
│ Edge Function      │  │ Edge Function           │
│ (CRUD, requires    │  │ (POST job, GET poll,    │
│  auth)             │  │  anonymous OK)          │
└────────┬───────────┘  └────────┬───────────────┘
         │                       │
         ▼                       ▼
┌──────────────────────────────────────────────┐
│  Supabase Postgres                           │
│  - strategy_user_strategies (config JSONB)   │
│  - strategy_backtest_jobs (status lifecycle)  │
│  - strategy_backtest_results (trades, metrics)│
└──────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Auth + Service Layer

**Goal:** Add Supabase Auth login and create the service classes for strategy CRUD and backtest submission. This is the foundation everything else builds on.

**Why first:** The `strategies` edge function returns 401 without a valid JWT (`strategies/index.ts:47-53`). Strategy persistence and backtest submission both need authenticated HTTP calls.

#### Tasks

- [x] **1.1 Update `SupabaseService`** — `client-macos/SwiftBoltML/Services/SupabaseService.swift`
  - Remove `EphemeralAuthStorage` (lines 12-16) — Supabase Swift SDK uses Keychain by default, which is what we want
  - Set `autoRefreshToken: true` (currently `false` at line 38)
  - No manual auth header helper needed — the SDK's `functions.invoke()` and Postgrest client automatically include the JWT from the current session

  **Research insight (Supabase Swift SDK):** The SDK stores sessions in Keychain automatically when `EphemeralAuthStorage` is removed. `fetchWithAuth` is built into `functions.invoke()` — no manual `Authorization` header management required.

- [x] **1.2 Create `AuthController`** — `client-macos/SwiftBoltML/ViewModels/AuthController.swift`
  - Use `@Observable` (not `ObservableObject` with `@Published`) to minimize SwiftUI invalidation:
    ```swift
    @Observable
    final class AuthController {
        var isAuthenticated = false
        var currentUser: User?
        var errorMessage: String?
        private var authTask: Task<Void, Never>?
    }
    ```
  - `func startListening()` — subscribe to `SupabaseService.shared.client.auth.authStateChanges` async stream. Update `isAuthenticated` and `currentUser` on `.signedIn` / `.signedOut` events
  - `func signIn(email:password:)` using `client.auth.signIn(email:password:)`
  - `func signUp(email:password:)` using `client.auth.signUp(email:password:)`
  - `func signOut()` using `client.auth.signOut()`
  - Cancel `authTask` in `deinit` (per institutional learning: store Task handles, cancel before re-creating)
  - Inject via `@State` in app entry point (not `@EnvironmentObject` — `@Observable` uses `@Environment`)

  **Research insight (architecture-strategist):** Use `@Observable` not `ObservableObject`. The existing `ChartViewModel` has 29 `@Published` properties causing cascading invalidation — don't repeat this pattern. `@Observable` gives fine-grained observation (only re-renders views that read changed properties).

  **Research insight (Supabase Auth):** `authStateChanges` is an `AsyncStream<(event: AuthChangeEvent, session: Session?)>`. Listen for `.signedIn`, `.signedOut`, `.tokenRefreshed`. Keychain storage is automatic — no configuration needed.

- [x] **1.3 Create `LoginView`** — `client-macos/SwiftBoltML/Views/LoginView.swift`
  - Email + password fields, Sign In / Sign Up buttons
  - Error display from `authController.errorMessage`
  - Wrap main `ContentView` in auth gate in `SwiftBoltMLApp.swift`:
    ```swift
    @State private var authController = AuthController()

    var body: some Scene {
        WindowGroup {
            if authController.isAuthenticated {
                ContentView().environment(authController)
            } else {
                LoginView().environment(authController)
            }
        }
    }
    ```
  - Call `authController.startListening()` in `.task { }` modifier

- [x] **1.4 Create `StrategyService`** — `client-macos/SwiftBoltML/Services/StrategyService.swift`
  - Uses `SupabaseService.shared.client.functions.invoke()` — auth headers are automatic
  - `func listStrategies() async throws -> [SupabaseStrategy]`
  - `func createStrategy(name:config:) async throws -> SupabaseStrategy`
  - `func updateStrategy(id:name:config:) async throws -> SupabaseStrategy`
  - `func deleteStrategy(id:) async throws`
  - `SupabaseStrategy` Codable struct matching edge function response:
    ```swift
    struct SupabaseStrategy: Codable, Identifiable {
        let id: UUID
        let userId: String
        var name: String
        var config: StrategyConfig  // the JSONB shape
        let createdAt: String
        var updatedAt: String
    }
    ```
  - Condition format mapping inline (~15 lines, not a separate file):
    ```swift
    // In StrategyService or as a private extension
    private func mapOperator(_ op: String) -> String {
        switch op.lowercased() {
        case "above", ">":  return ">"
        case "below", "<":  return "<"
        case "crosses_above", "cross_up":  return "cross_up"
        case "crosses_below", "cross_down": return "cross_down"
        default: return op.lowercased()
        }
    }
    ```

  **Research insight (code-simplicity-reviewer):** The server-side `strategy-translator.ts` (lines 51-60) already handles normalization between all 3 condition formats. The Swift mapper only needs to lowercase the indicator name + map the 4 operator variants. This is ~15 lines inline — not worth a standalone `StrategyConditionMapper.swift` file.

  **Research insight (security-sentinel):** Validate condition `indicator` and `operator` strings against an allowlist before including them in any JS calls. This prevents injection if a malicious strategy config is loaded from the server.

- [x] **1.5 Create `BacktestService`** — `client-macos/SwiftBoltML/Services/BacktestService.swift`
  - `func submitBacktest(symbol:strategyConfig:startDate:endDate:initialCapital:) async throws -> String` — returns `job_id`
  - `func pollBacktest(jobId:) async throws -> BacktestResultPayload` — uses exponential backoff polling
  - **Reuse existing Codable types from `BacktestingModels.swift`** — do NOT recreate:
    - `BacktestJobQueuedResponse` (has `jobId`)
    - `BacktestJobStatusResponse` (has `status`, `result`)
    - `BacktestResultPayload` (has `metrics`, `trades`, `equity_curve`)
    - `BacktestResultTrade` (has `entry_date`, `exit_date`, `entry_price`, `exit_price`, `pnl`, etc.)
    - `BacktestResultEquityPoint` (has `date`, `value`)

  **Research insight (pattern-recognition):** `BacktestingModels.swift` already contains all needed Codable types. The original plan proposed re-creating these in Phase 4 — completely unnecessary.

  **Polling with exponential backoff:**
  ```swift
  func pollBacktest(jobId: String) async throws -> BacktestResultPayload {
      var interval: TimeInterval = 1
      let maxInterval: TimeInterval = 15
      let timeout: TimeInterval = 120
      let start = Date()

      while Date().timeIntervalSince(start) < timeout {
          try await Task.sleep(for: .seconds(interval))
          let response = try await fetchJobStatus(jobId: jobId)
          switch response.status {
          case "completed": return response.result!
          case "failed": throw BacktestError.jobFailed(response.error ?? "Unknown")
          default: interval = min(interval * 2, maxInterval)
          }
      }
      throw BacktestError.timeout
  }
  ```

  **Research insight (performance-oracle):** Fixed 1s polling generates unnecessary load. Exponential backoff (1s -> 2s -> 4s -> 8s -> 15s cap) is standard for job-queue polling. Most backtests complete in 5-15s.

**Acceptance criteria:**
- [x] User can sign in with email/password, session persists across restarts (Keychain)
- [x] Token auto-refreshes via `authStateChanges` stream
- [x] `StrategyService` CRUD operations work with JWT auth
- [x] `BacktestService` submits jobs and polls with exponential backoff
- [x] Condition format mapping handles all 4 operator variants
- [x] Condition indicator/operator strings validated against allowlist

---

### Phase 2: Strategy Persistence + Backtest Execution

**Goal:** Wire the `IntegratedStrategyBuilder` to Supabase for strategy CRUD and real backtesting, replacing all mock data.

**Why second:** With auth and services in place, this connects the existing UI to the real backend. No new views needed yet — just wiring.

#### Tasks

- [x] **2.1 Create `StrategyListViewModel`** — `client-macos/SwiftBoltML/ViewModels/StrategyListViewModel.swift`
  - Use `@Observable` (not `ObservableObject`):
    ```swift
    @Observable
    final class StrategyListViewModel {
        var strategies: [SupabaseStrategy] = []
        var selectedStrategy: SupabaseStrategy?
        var isLoading = false
        var error: String?
    }
    ```
  - Replaces in-memory `StrategyBuilderViewModel`
  - On appear: load from Supabase via `StrategyService.listStrategies()`
  - Save/delete trigger Supabase calls with optimistic UI update

  **Research insight (architecture-strategist):** Minimize `@Observable` properties. The existing `ChartViewModel` has 29 `@Published` properties — every change triggers full view re-evaluation. Keep new VMs lean.

- [x] **2.2 Wire backtest to existing `BacktestingViewModel`** — `client-macos/SwiftBoltML/ViewModels/BacktestingViewModel.swift`
  - **Do NOT create a new `BacktestViewModel`** — this name collides with the existing `BacktestingViewModel`
  - Instead, add a method to the existing `BacktestingViewModel`:
    ```swift
    func runStrategyBacktest(strategyConfig: StrategyConfig, symbol: String, dateRange: ...) async
    ```
  - This calls `BacktestService.submitBacktest()` then `BacktestService.pollBacktest()`
  - Reuse existing `@Published var isRunning`, `@Published var result` properties
  - Store `Task` handle as property; cancel before re-creating (per institutional learning)
  - Remove leftover `_e2eLog` debug code (lines 5-18) — gate any remaining diagnostics behind `#if DEBUG`

  **Research insight (pattern-recognition):** `BacktestingViewModel` already exists at `ViewModels/BacktestingViewModel.swift` with polling logic (lines 131-203), `pollIntervalSeconds: 2`, `maxPolls: 300`. Extend it rather than creating a parallel class.

  **Research insight (performance-oracle):** The existing `_e2eLog` writes to a hardcoded file path — this is diagnostic code that should be behind `#if DEBUG`.

- [x] **2.3 Wire `IntegratedStrategyBuilder` to new services**
  - Replace `@StateObject private var viewModel = StrategyBuilderViewModel()` with `StrategyListViewModel`
  - Save button calls `strategyListViewModel.save(strategy)` -> Supabase
  - Strategy picker dropdown loads from `strategyListViewModel.strategies`
  - Delete button calls `strategyListViewModel.delete(id:)`
  - Wire "Run Backtest" button to `backtestingViewModel.runStrategyBacktest()`
  - Thread `appViewModel.selectedSymbol` as the default backtest symbol

- [x] **2.4 Validate strategy before backtest**
  - Require at least 1 entry condition
  - Warn (not block) if no exit conditions — positions will close on SL/TP only
  - Validate date range: start < end, start not in future, range >= 30 days

**Acceptance criteria:**
- [x] Strategies persist to Supabase `strategy_user_strategies` table
- [x] Strategies load on app launch (after auth)
- [x] Create, update, delete work end-to-end
- [x] Real backtest jobs submitted to edge function
- [x] Polling works with exponential backoff, spinner + elapsed time
- [x] Timeout after 120s with error message
- [x] Cancel stops polling gracefully
- [x] Loading and error states displayed
- [x] Symbol defaults from Charts tab selection

---

### Phase 3: Chart Overlays + ZStack Persistence

**Goal:** Keep the chart alive across tab switches (ZStack) and render backtest entry/exit markers as overlays on the main chart. Equity curve sub-panel deferred to follow-up.

**Why third:** With real backtest results flowing, we can now visualize them. The ZStack change is required to keep overlays visible when switching tabs.

#### Tasks

- [x] **3.1 Keep `WebChartView` alive across tab switches** — `client-macos/SwiftBoltML/Views/ContentView.swift`
  - Restructure `NavigationSplitView` detail pane as a `ZStack`
  - `WebChartView` always mounted (opacity 1 when chart-related tabs, opacity 0 otherwise)
  - Use `.allowsHitTesting(false)` when hidden so it doesn't intercept clicks
  - Do NOT use `.hidden()` or `.frame(width: 0, height: 0)` — these can pause WKWebView JS execution
  - Active tab content rendered on top when non-chart tabs are selected

  **Research insight (WKWebView persistence):** ZStack opacity toggle is confirmed safe on macOS. JS continues executing at opacity 0, Lightweight Charts canvas renders correctly. `.hidden()` modifier WILL pause JS execution — avoid it.

- [x] **3.2 Send backtest trade markers to chart via NotificationCenter**
  - On backtest completion in `BacktestingViewModel`, post `.backtestTradesUpdated` notification with trade data
  - **Add symbol guard** in `WebChartView` coordinator's notification handler:
    ```swift
    // In WebChartView coordinator, when handling .backtestTradesUpdated:
    guard let trades = notification.userInfo?["trades"] as? [BacktestResultTrade],
          let backtestSymbol = notification.userInfo?["symbol"] as? String,
          backtestSymbol == self.parent.viewModel.selectedSymbol else { return }
    ```
  - **Add generation counter** to prevent stale results from overlapping backtests:
    ```swift
    let generation = notification.userInfo?["generation"] as? Int ?? 0
    guard generation >= self.lastBacktestGeneration else { return }
    self.lastBacktestGeneration = generation
    ```
  - Transform trades to the format expected by `chart.js setBacktestTrades()` and call via `ChartBridge`
  - Use `JSONSerialization` for safe encoding (per institutional learning — no string interpolation in `evaluateJavaScript()`)

  **Research insight (architecture-strategist):** Do NOT share `ChartBridge` directly between ViewModels. Use the existing `NotificationCenter` pub-sub pattern (`.backtestTradesUpdated` already exists in `WebChartView.swift:249-261`). But add the missing symbol guard and generation counter.

  **Research insight (race-condition-reviewer, HIGH severity):** Current `WebChartView` coordinator subscribes to `.backtestTradesUpdated` with NO symbol guard and NO generation counter. Without these:
  - Changing symbol during a backtest displays markers on wrong candlesticks
  - Rapid re-runs can show stale results from a previous backtest

- [x] **3.3 Clear backtest overlays on symbol change**
  - In `WebChartView` coordinator, when `selectedSymbol` changes:
    - Call `chartBridge.setBacktestTrades([])` to clear markers
    - Clear `pendingBacktestTrades` buffer (line 23 in WebChartView — currently not cleared on symbol change)
    - Reset `lastBacktestGeneration` counter

  **Research insight (race-condition-reviewer):** `pendingBacktestTrades` buffer (WebChartView line 23) is never cleared on symbol change. Old trades from a previous symbol leak into the new chart.

- [x] **3.4 Thread symbol from `AppViewModel` to Strategy tab**
  - Pass `appViewModel.selectedSymbol` to `IntegratedStrategyBuilder` as a binding
  - Backtest form pre-populates with this symbol
  - When user changes symbol in Charts, Strategy tab picks it up

**Acceptance criteria:**
- [x] Chart remains alive when switching between Charts and Strategy tabs
- [x] Buy/sell arrow markers appear on candlesticks at correct entry/exit dates
- [x] Markers only display when backtest symbol matches current chart symbol
- [x] Overlapping backtests don't show stale results (generation counter)
- [x] Overlays persist across tab switches
- [x] Overlays clear when symbol changes
- [x] `pendingBacktestTrades` cleared on symbol change
- [x] No string interpolation in `evaluateJavaScript()`

---

### Phase 4: Trade Log & Summary Stats

**Goal:** SwiftUI table showing per-trade details and summary metrics from the backtest results.

**Why fourth:** The data is flowing from Phase 2, overlays are rendering from Phase 3. This adds the detailed reporting view.

#### Tasks

- [x] **4.1 Create `BacktestResultsView`** — `client-macos/SwiftBoltML/Views/BacktestResultsView.swift`
  - **Summary stats grid** (2x4 card layout):
    - Total Return %, Win Rate %, Max Drawdown %, Sharpe Ratio
    - Total Trades, Profit Factor, Avg Win, Avg Loss
  - **Trade log table** (`Table` view):
    - Columns: Entry Date, Exit Date, Direction, Entry Price, Exit Price, P&L ($), P&L (%), Shares, Close Reason, Duration
    - Sortable by any column
    - Color-coded rows: green for winning trades, red for losing
    - Duration calculated from `entry_date` / `exit_date`
  - Use file-level `private let currencyFormatter` and `private let percentFormatter` (per institutional learning — no allocations in view body)

  **Research insight (performance-oracle):** `NumberFormatter` allocations in SwiftUI view bodies cause performance degradation. Declare formatters at file scope as `private let`. This pattern is documented in `docs/solutions/security-issues/swiftui-credential-and-injection-hardening.md`.

- [x] **4.2 Integrate into `IntegratedStrategyBuilder` Backtest tab**
  - Replace `BacktestWebStyle` mock results with `BacktestResultsView`
  - Show results when backtest result is available
  - Show empty state when no backtest has been run
  - Tab structure (already exists at `IntegratedStrategyBuilder.swift:22-30`):
    - Tab 1: **Editor** — condition builder (existing)
    - Tab 2: **Live Indicators** — indicator cards (existing)
    - Tab 3: **Backtest** — date range picker, "Run Backtest" button, `BacktestResultsView`

**Acceptance criteria:**
- [x] Summary stats display all metrics from backtest results
- [x] Trade log shows all trades with correct data
- [x] Columns are sortable
- [x] Win/loss trades are color-coded
- [x] No formatter allocations in view body

---

## Deferred Items (Post-MVP)

These were identified during research as valuable but not required for the core feature:

1. **Equity curve sub-panel** — `chart.js createSubChart("equity", { height: 120 })` with area series. The existing RSI/MACD pattern can be followed. Defer because markers alone provide the key visual feedback.
2. **Sidebar consolidation** — Remove duplicate "Strategy Platform" section (`.strategyPlatform(.builder)`, `.strategyPlatform(.backtesting)`). Low-risk cleanup that doesn't block functionality.
3. **Operator format unification** — Standardize all condition picker UIs to use Supabase symbols (`">"`, `"<"`, `"cross_up"`, `"cross_down"`) at the source. The server-side translator handles mismatches for now.
4. **Batch JS commands in ChartBridge** — Current `enqueueJS` serial queue has 50-125ms overhead per command. Batching multiple commands into a single `evaluateJavaScript` call would improve overlay rendering performance.
5. **Scope backtest jobs by user_id** — Currently `backtest-strategy` allows anonymous access. Adding `user_id` filtering prevents cross-user job visibility.

---

## System-Wide Impact

### Interaction Graph

- Auth login -> Supabase Auth -> JWT stored in Keychain -> All edge function calls include Bearer token automatically
- "Run Backtest" button -> `BacktestService.submitBacktest()` -> `backtest-strategy` edge function -> `strategy-backtest-worker` -> DB -> `BacktestService.pollBacktest()` (exponential backoff) -> `BacktestingViewModel.result` -> NotificationCenter `.backtestTradesUpdated` (with symbol + generation) -> `WebChartView` coordinator (symbol guard + generation check) -> `ChartBridge.setBacktestTrades()` -> chart.js renders markers
- Strategy save -> `StrategyService.createStrategy()` (inline operator mapping) -> `strategies` edge function -> DB
- Symbol change in watchlist -> `AppViewModel.selectedSymbol` -> `WebChartView` coordinator clears markers + resets generation counter + clears `pendingBacktestTrades`

### Error Propagation

- Auth errors (401) from edge functions -> `StrategyService` / `BacktestService` throw -> ViewModel sets `error` message -> UI displays alert
- Backtest poll timeout (120s) -> `BacktestService` throws `BacktestError.timeout` -> ViewModel error state
- Network offline -> URLSession throws -> Service layer rethrows -> ViewModel error state
- Invalid condition format -> inline `mapOperator()` falls through to `default: return op.lowercased()` -> server translator handles remaining normalization

### State Lifecycle Risks

- **Tab switch during backtest poll:** Poll task stored as property, continues in background. Chart alive in ZStack receives results via NotificationCenter.
- **Auth token expiry during poll:** `autoRefreshToken: true` + `authStateChanges` stream handles refresh automatically.
- **Stale overlays after symbol change:** Explicit clear in `WebChartView` coordinator + generation counter prevents stale data.
- **Overlapping backtests:** Generation counter incremented on each new backtest. Stale results from earlier runs are ignored.
- **`pendingBacktestTrades` leak:** Cleared on symbol change (currently not done — must be added in Phase 3.3).

### Security Considerations

**Research insight (security-sentinel):**
- **Condition injection:** Validate indicator names and operators against an allowlist before any JS interpolation. A malicious strategy config from Supabase could contain `"; alert(1)//` as an operator string.
- **Anon key exposure:** The app currently embeds the Supabase anon key. With auth added, RLS policies on `strategy_user_strategies` scope data to the authenticated user. Backtest results should also be scoped by `user_id`.
- **Keychain security:** Supabase Swift SDK uses Keychain by default for session storage. This is OS-level encrypted storage — adequate for access tokens.

## Alternative Approaches Considered

1. **Bundle React build into app** — Rejected because it creates a chart-sharing problem (WKWebView chart vs native chart) and adds WebView overhead. (see brainstorm: Why This Approach)
2. **Local-first storage** — Rejected in favor of Supabase persistence to enable future paper trading deployment.
3. **Equity curve on main chart** — Rejected due to Y-axis scale mismatch. Sub-panel follows established RSI/MACD pattern (deferred to post-MVP).
4. **Persist + replay overlay state** — Rejected in favor of keeping chart alive via ZStack, which is simpler and preserves all chart state (not just backtest overlays).
5. **Share ChartBridge directly between VMs** — Rejected in favor of NotificationCenter pub-sub (per architecture-strategist). Direct sharing creates tight coupling and doesn't support symbol guards.
6. **Create new `BacktestViewModel`** — Rejected because `BacktestingViewModel` already exists with polling logic. Adding a second class with a near-identical name causes confusion.

## Acceptance Criteria

### Functional
- [x] User can sign in with email/password, session persists across restarts
- [x] Strategies save to Supabase and load on app launch
- [x] Backtests run against real backend with exponential backoff polling
- [x] Entry/exit markers overlay on main chart at correct positions
- [x] Trade log table with sortable columns and color-coded P&L
- [x] Summary stats display all backtest metrics
- [x] Chart overlays persist across tab switches
- [x] Symbol context flows from Charts to Strategy
- [x] Backtest markers only display for matching symbol

### Non-Functional
- [x] No string interpolation in `evaluateJavaScript()` — use `JSONSerialization`
- [x] No `NumberFormatter`/`DateFormatter` allocations in view bodies
- [x] Task handles stored as properties, cancelled before re-creating
- [x] All diagnostic `print()` inside `#if DEBUG`
- [x] Condition indicator/operator validated against allowlist before JS interpolation
- [x] `@Observable` used for new ViewModels (not `ObservableObject` with `@Published`)
- [x] NotificationCenter notifications include symbol guard + generation counter

## Dependencies & Risks

| Risk | Mitigation |
|---|---|
| Auth adds friction to first-time use | Keep login simple (email/password), add "Skip for now" option that disables persistence features |
| Backtest worker may not be deployed | Test with `GET /functions/v1/backtest-strategy?id=test` to verify worker is running |
| Condition type coverage gaps | Server-side `strategy-translator.ts` handles normalization; Swift only maps 4 operators |
| `BacktestingViewModel` naming confusion | Extend existing class, do not create parallel `BacktestViewModel` |
| 29 `@Published` properties in ChartViewModel | Use `@Observable` for all new VMs to avoid same pattern |
| `pendingBacktestTrades` leak on symbol change | Clear buffer explicitly in Phase 3.3 |

## Sources & References

### Origin
- **Brainstorm document:** [docs/brainstorms/2026-03-01-strategy-builder-chart-overlay-brainstorm.md](docs/brainstorms/2026-03-01-strategy-builder-chart-overlay-brainstorm.md)
  - Key decisions: Native Swift + backend (not React), single chart with overlays, separate tab sharing chart via ZStack, Supabase persistence, full trade log

### Internal References
- `ChartBridge.setBacktestTrades()`: `client-macos/SwiftBoltML/Services/ChartBridge.swift:711`
- `chart.js setBacktestTrades()`: `client-macos/SwiftBoltML/Resources/WebChart/chart.js:2257`
- `chart.js createSubChart()`: `client-macos/SwiftBoltML/Resources/WebChart/chart.js:2497`
- `SupabaseService`: `client-macos/SwiftBoltML/Services/SupabaseService.swift:22`
- `IntegratedStrategyBuilder`: `client-macos/SwiftBoltML/Views/IntegratedStrategyBuilder.swift`
- `ContentView` tabs: `client-macos/SwiftBoltML/Views/ContentView.swift:9-19`
- `BacktestingModels.swift` (existing Codable types): `client-macos/SwiftBoltML/Models/BacktestingModels.swift`
- `BacktestingViewModel` (existing polling): `client-macos/SwiftBoltML/ViewModels/BacktestingViewModel.swift:131-203`
- `strategy-translator.ts` (condition format reference): `supabase/functions/_shared/strategy-translator.ts:51-60`
- `WebChartView` notification handler: `client-macos/SwiftBoltML/Views/WebChartView.swift:249-261`
- `pendingBacktestTrades` buffer: `client-macos/SwiftBoltML/Views/WebChartView.swift:23`
- Institutional learning (JS injection safety): `docs/solutions/security-issues/swiftui-credential-and-injection-hardening.md`

### Edge Function Contracts
- `strategies` CRUD: `supabase/functions/strategies/index.ts` — GET/POST/PUT/DELETE, requires JWT
- `backtest-strategy`: `supabase/functions/backtest-strategy/index.ts` — POST (queue job), GET (poll status), anonymous OK
