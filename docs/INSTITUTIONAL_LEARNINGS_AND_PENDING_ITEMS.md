# SwiftBolt ML — Institutional Learnings & Known Patterns

## Security & Architecture Solutions (DOCUMENTED)

### 1. Security Solution: macOS SwiftUI Hardening (CRITICAL)
**File:** `docs/solutions/security-issues/swiftui-credential-and-injection-hardening.md`
**Status:** Resolved in PR #23
**Severity:** Critical (P1 security) + High (P2 lifecycle/quality)

#### Key Patterns to Apply Universally:

**Credential Management:**
- Never commit secrets to git via Info.plist or xcconfig
- Use Xcode build variables: `$(SUPABASE_URL)`, `$(SUPABASE_ANON_KEY)`
- Store actual values in gitignored `Secrets.xcconfig` (with `.example` template)
- Rotate keys via Supabase Dashboard → Settings → API

**JavaScript Injection Prevention:**
- NEVER use string interpolation in `evaluateJavaScript()`
- Always use `JSONSerialization` for safe payload encoding:
  ```swift
  let payload: [String: Any] = ["type": "symbolChanged", "symbol": symbol]
  guard let data = try? JSONSerialization.data(withJSONObject: payload),
        let json = String(data: data, encoding: .utf8) else { return }
  webView.evaluateJavaScript("window.postMessage(\(json), '*');")
  ```
- Add `limitsNavigationsToAppBoundDomains = true`
- Whitelist hosts in `decidePolicyFor` delegate

**WKWebView Lifecycle (THE CRITICAL PATTERN):**
- Store `Task` handles as properties; never fire-and-forget
- Cancel stored task before creating new one (re-entry pattern)
- Implement `WeakScriptHandler` proxy to prevent retain cycles
- Call `removeAllScriptMessageHandlers()` in `dismantleNSView`
- Use `.task` modifier instead of `Task {}` in view bodies
- Pattern for stored subscription:
  ```swift
  private var subscriptionTask: Task<Void, Never>?

  func subscribeToData() async {
      subscriptionTask?.cancel()  // Cancel previous before creating new
      subscriptionTask = Task { [weak self] in
          for await _ in changes {
              guard !Task.isCancelled else { break }
              // Process update
          }
      }
  }
  ```

**Swift Concurrency Rules:**
- Check `Task.isCancelled` inside `for await` loops
- Pair `subscribe()` with `unsubscribe()` in view lifecycle
- Debounce high-frequency realtime events (500ms typical)

**SwiftUI Performance:**
- `NumberFormatter`, `DateFormatter` are expensive allocations
- Create as file-level `private let` constants (not in view bodies)
- Lock locale/currency at init time, not per-format call
- Example:
  ```swift
  private let currencyFormatter: NumberFormatter = {
      let f = NumberFormatter()
      f.numberStyle = .currency
      f.currencyCode = "USD"
      f.locale = Locale(identifier: "en_US")
      f.maximumFractionDigits = 2
      return f
  }()
  ```

---

## Open P3 Items (Pending for Priority 3 Phase)

### 020: No Discovery Endpoint for Active Strategies
**File:** `todos/020-pending-p3-no-discovery-endpoint-for-active-strategies.md`
**Priority:** P3 | **Effort:** Small | **Risk:** Very Low

**Problem:**
- `POST /paper-trading-executor` has no corresponding GET to list active strategies
- Agents wanting to "run all active strategies" must access database directly
- No public API contract for discovering active strategies

**Current Implementation:**
- `supabase/functions/paper-trading-executor/index.ts` only handles POST requests
- Active strategies live in `strategy_user_strategies` table with `paper_trading_enabled=true`

**Recommended Solution:** Option B (add filter to existing strategies GET)
- Add `?paper_trading_enabled=true` query parameter to `GET /strategies`
- Less endpoint sprawl than creating new GET `/paper-trading-executor` route
- Reuses existing strategies endpoint authorization/validation

**Acceptance Criteria:**
- [ ] Agent can GET active paper-trading strategies (symbol + timeframe) in one HTTP call
- [ ] Response includes info to construct valid `POST /paper-trading-executor` payload
- [ ] No direct DB access required for discovery

---

### 021: Duplicate Backtest Edge Functions
**File:** `todos/021-pending-p3-duplicate-backtest-edge-functions.md`
**Priority:** P3 | **Effort:** Small | **Risk:** Low

**Problem:**
- Two functions exist: `backtest-strategy` (newer, canonical) and `strategy-backtest` (older)
- Both write to `strategy_backtest_jobs` table
- No clear indication which to use
- Creates discovery confusion for agents/developers/UI code

**Current Implementation:**
- `supabase/functions/backtest-strategy/index.ts` — newer, auto-triggers worker, supports preset strategies
- `supabase/functions/strategy-backtest/index.ts` — older version, should be deprecated

**Recommended Solution:**
1. Add deprecation notice to `strategy-backtest` → redirects to `backtest-strategy`
2. Audit `BacktestingView` and other callers to ensure they use canonical endpoint
3. Document `backtest-strategy` as canonical in CLAUDE.md
4. Remove old function in future cleanup PR (after confirming no callers remain)

**Acceptance Criteria:**
- [ ] `strategy-backtest` has deprecation comment or 301 redirect
- [ ] All UI and agent callers use `backtest-strategy`
- [ ] CLAUDE.md documents `backtest-strategy` as the canonical backtest endpoint

---

### 022: WKScriptMessageHandler Stub Not Implemented
**File:** `todos/022-pending-p3-webview-script-message-handler-stub.md`
**Priority:** P3 | **Effort:** Small | **Risk:** Low

**Problem:**
- `StrategyBuilderWebView.Coordinator` receives JS events but handler body is empty
- React component sends `conditionUpdated`, `strategyActivated`, `backtestRequested` but native doesn't process
- Strategy changes in WebView not propagated to native Paper Trading Dashboard
- Shared workspace contract between WebView and native is silent

**Current Implementation:**
**File:** `client-macos/SwiftBoltML/Views/StrategyBuilderWebView.swift`
```swift
func userContentController(_ userContentController: WKUserContentController,
                            didReceive message: WKScriptMessage) {
    // Future: handle "conditionUpdated", "strategyActivated", "backtestRequested"
}
```

**Recommended Solution:** Implement minimum viable handling
```swift
func userContentController(_ userContentController: WKUserContentController,
                            didReceive message: WKScriptMessage) {
    guard let body = message.body as? [String: Any],
          let type = body["type"] as? String else { return }

    switch type {
    case "conditionUpdated":
        // Strategy was saved in WebView — reload native strategy list
        Task { @MainActor in
            await strategyViewModel?.loadStrategies()
        }
    case "backtestRequested":
        // User clicked "Run Backtest" in React — trigger natively or navigate
        if let strategyId = body["strategyId"] as? String {
            Task { @MainActor in
                await backtestViewModel?.runBacktest(strategyId: strategyId)
            }
        }
    default:
        break
    }
}
```

**Acceptance Criteria:**
- [ ] `conditionUpdated` event from React triggers reload of strategy data
- [ ] `backtestRequested` event initiates backtest via native service
- [ ] Handler gracefully handles unexpected message formats with guard let pattern

---

### 011: Silent Realtime Loop Exit — No Reconnection
**File:** `todos/011-pending-p3-silent-realtime-loop-exit-no-reconnect.md`
**Priority:** P3 | **Effort:** Medium | **Risk:** Low | **UX Impact:** High

**Problem:**
- When Supabase Realtime connection drops, `for await _ in changes` exits silently
- No reconnection attempt on dropped channel
- No user-visible indicator (beyond existing DNS-failure SupabaseConnectivityBanner)
- Cannot distinguish "no changes" from "disconnected"
- Positions dashboard goes stale without warning
- Critical for active traders who need live P&L updates

**Current Implementation:**
**File:** `client-macos/SwiftBoltML/Services/PaperTradingService.swift` lines 139-143
```swift
Task { [weak self] in
    for await _ in changes {
        await self?.loadData()
    }
    // Loop exits silently — dropped connection, exhausted channel, anything
    // No log, no reconnect, no UI update
}
```

**Recommended Solution:** Option A with `isLive` indicator
- Re-subscribe with exponential backoff (cap at 30 seconds)
- Expose `@Published var isLive` to UI
- Dashboard shows "reconnecting..." when connection drops
```swift
private func startSubscriptionLoop() async {
    var delay: UInt64 = 1_000_000_000  // 1 second
    while !Task.isCancelled {
        let channel = supabase.channel("paper_trading_positions")
        realtimeChannel = channel
        let changes = channel.postgresChange(AnyAction.self, ...)
        await channel.subscribe()

        for await _ in changes {
            guard !Task.isCancelled else { return }
            await reloadDebouncer.debounce { [weak self] in
                await self?.loadData()
            }
        }

        // Loop exited — channel dropped
        await MainActor.run { self.isLive = false }
        if !Task.isCancelled {
            try? await Task.sleep(nanoseconds: delay)
            delay = min(delay * 2, 30_000_000_000)  // cap at 30s
        }
    }
}
```

**Acceptance Criteria:**
- [ ] Loop exit triggers reconnection attempt with exponential backoff
- [ ] `PaperTradingService` exposes `@Published var isLive: Bool`
- [ ] Dashboard shows "reconnecting..." indicator when `isLive == false`
- [ ] After reconnection, `isLive` returns to `true` and data refreshes
- [ ] Manual `unsubscribe()` cleanly exits loop without triggering reconnection

**Depends On:** P1 task #003 (Task handle storage — already resolved in PR #23)

---

### 012: select("*") Should Use Explicit Columns
**File:** `todos/012-pending-p3-supabase-select-star-explicit-columns.md`
**Priority:** P3 | **Effort:** XSmall | **Risk:** Very Low

**Problem:**
- `PaperTradingService` queries use `.select("*")` instead of explicit column lists
- Transfers all columns including any future migrations
- Payload bloat; accidental exposure of future columns risk
- Makes data contract implicit rather than explicit/auditable

**Current Implementation:**
**File:** `client-macos/SwiftBoltML/Services/PaperTradingService.swift` lines 154-155, 165
```swift
// fetchOpenPositions
.select("*")   // Transfers all columns

// fetchTradeHistory
.select("*")   // Transfers all columns
```

**Data Contracts:**
- `PaperPosition` decodes: `id, user_id, strategy_id, symbol_id, ticker, timeframe, entry_price, current_price, quantity, entry_time, direction, stop_loss_price, take_profit_price, status`
- `PaperTrade` decodes: `id, user_id, strategy_id, symbol_id, ticker, timeframe, entry_price, exit_price, quantity, direction, entry_time, exit_time, pnl, pnl_pct, trade_reason, created_at`

**Recommended Solution:** Option A (explicit columns)
```swift
// fetchOpenPositions
.select("id,user_id,strategy_id,symbol_id,ticker,timeframe,entry_price,current_price,quantity,entry_time,direction,stop_loss_price,take_profit_price,status")

// fetchTradeHistory
.select("id,user_id,strategy_id,symbol_id,ticker,timeframe,entry_price,exit_price,quantity,direction,entry_time,exit_time,pnl,pnl_pct,trade_reason,created_at")
```

**Acceptance Criteria:**
- [ ] Both queries use explicit column list matching CodingKeys
- [ ] No decoding errors after change (all required keys present)
- [ ] Optional fields still decode correctly as nil when absent
- [ ] Payload size slightly reduced

---

## Additional Code Quality Issues (Resolved in PR #23 or Pending)

### 013: WebView Script Handler Retain Cycle
**Status:** Pending | **Pattern:** WeakScriptHandler proxy already documented in solution

### 014: Debug Print Statements in Release Builds
**Status:** Partially resolved in PR #23 | **Pattern:** Guard all `print()` with `#if DEBUG`

### 015: SupabaseService Public Visibility
**Status:** Resolved in PR #23 | **Change:** `public class` → `final class`, removed public access on `shared` and `client`

### 016: Trough Variable Clarity in Drawdown Calculation
**Status:** Pending | **Scope:** Unclear from context

---

## Edge Function Patterns (Established & Production-Ready)

### Paper Trading Execution Pipeline
**Location:** `supabase/functions/paper-trading-executor/index.ts`
**Status:** Production-ready with 20 unit tests

**Established Patterns:**
1. **Optimistic Locking:** `WHERE status='open'` prevents concurrent position closes
   - Atomic update per execution cycle
   - Tested race condition prevention

2. **Indicator Caching:** `Map<string, number>` for cross-strategy reuse
   - 3-5x performance improvement over per-strategy calculation
   - Shared across all executing strategies in same cycle

3. **Semaphore Pattern:** Limits concurrent executor runs to 5
   - Prevents cascade overload
   - Configurable max concurrency

4. **Real-time Price Updates:** Executor writes `current_price` to all open positions
   - Dashboard refreshes with live P&L
   - Enables real-time monitoring

5. **Close Position Action:** `POST /paper-trading-executor { action: "close_position", position_id, exit_price }`
   - Manual close route for native clients
   - Calculates P&L on close

### Strategy Management
**Location:** `supabase/functions/strategies/index.ts`

**Established Patterns:**
1. PUT handler accepts `paper_trading_enabled` toggle (added in PR #23)
2. Response includes full strategy object with nested relations
3. Caller must check `is_active` and `paper_trading_enabled` to determine execution eligibility

---

## Frontend API Integration Patterns (React)

### Chart Data API — Single Endpoint Pattern
**Contract:** `GET /chart?symbol=AAPL&timeframe=1d`
**Response:** OHLCV + indicators + forecasts + accuracy badges in one round trip

**Established Patterns:**
1. **Cache-first reads:** Return cached data, refresh if stale
2. **Single endpoint per view:** No fragmentation into multiple chart endpoints
3. **No direct vendor calls:** All market data and forecasts go through Edge Functions
4. **Complete contract in one response:** Prevent N+1 queries from client

### Backtest Service
**Location:** `frontend/src/lib/backtestService.ts`
**Canonical Endpoint:** `POST /backtest-strategy` (see P3 issue #021)

**Established Patterns:**
1. Request payload: `{ strategyId, symbol, timeframe, startDate, endDate }`
2. Response: Strategy + results with comprehensive performance metrics
3. UI polling pattern: Check `strategy_backtest_jobs` status by ID
4. Two distinct functions exist — consolidation pending (issue #021)

### Component Decomposition (React)
**Pattern:** Extract data from presentation
**Example:** IndicatorMenu decomposed into:
- `IndicatorLibrary.ts` (280L data + types)
- `IndicatorCategories.ts` (42L metadata)
- `IndicatorMenu.tsx` (376L component logic only)

---

## Backend Parity Fixes (Resolved in PR #23)

✅ **FIXED:**
- `POST paper-trading-executor { action: "close_position", position_id, exit_price }` — native close route
- Executor writes `current_price` to all open positions each cycle for live P&L
- `PUT /strategies` accepts `paper_trading_enabled` in payload for toggling execution

---

## Summary for Code Reviewers

### Critical Patterns to Check in All PRs

1. **No secrets in committed config**
   - Validate `.gitignore` includes secrets files
   - Check Info.plist uses build variables `$(VAR)` not literal values

2. **No string interpolation in JS evaluation**
   - Always use `JSONSerialization` for safe encoding
   - Pattern: `webView.evaluateJavaScript("window.postMessage(\(json), '*');")` after serialization

3. **All Tasks stored and cancelled**
   - No fire-and-forget `Task {}` in view bodies
   - Cancel previous before creating new one (re-entry pattern)

4. **Explicit column selection**
   - No `.select("*")` without justification
   - Makes data contracts explicit and auditable

5. **WKWebView isolation**
   - `limitsNavigationsToAppBoundDomains = true`
   - Whitelist hosts in `decidePolicyFor`
   - Implement `WeakScriptHandler` proxy
   - Remove handlers in `dismantleNSView`

6. **Formatter caching**
   - `NumberFormatter` created once at file level
   - Lock locale/currency at init time

7. **Realtime lifecycle**
   - Subscribe/unsubscribe paired in view lifecycle
   - Connection drops handled (or tracked for future P3 work)
   - Check `Task.isCancelled` in `for await` loops

8. **Edge Function discovery**
   - One canonical function per operation (see issue #021)
   - Public GET endpoints for agent discovery (see issue #020)

---

## Architecture Decisions Made

- **Single GET /chart endpoint:** No fragmentation of chart read paths
- **Edge Functions as public API surface:** Clients never call Alpaca, Finnhub, etc. directly
- **Optimistic locking for race conditions:** Tested and verified in paper trading executor
- **Discriminated unions for type safety:** All operator conditions use unions, not `Any`
- **Backtest-strategy as canonical:** strategy-backtest deprecated (P3 issue #021)
- **One NSViewRepresentable per WebView type:** Never duplicate >70% identical code
- **File-level formatter constants:** Never allocate formatters in view bodies

---

## Known Limitations / Planned Work

**P3 Phase (In Progress):**
- [ ] Realtime reconnection with exponential backoff (issue #011)
- [ ] WebView-to-native message handling wired (issue #022)
- [ ] Strategy discovery endpoint exposed (issue #020)
- [ ] Column selection replaced with explicit lists (issue #012)
- [ ] Backtest endpoint duplicates consolidated (issue #021)

**Not Yet Addressed:**
- Sentiment features disabled (zero-variance fix pending)
- Some debug print statements still present in release code
- SupabaseService visibility cleanup only partial

---

## References

**Security Solution Document:**
- `docs/solutions/security-issues/swiftui-credential-and-injection-hardening.md`

**Todo Items:**
- `todos/020-pending-p3-no-discovery-endpoint-for-active-strategies.md`
- `todos/021-pending-p3-duplicate-backtest-edge-functions.md`
- `todos/022-pending-p3-webview-script-message-handler-stub.md`
- `todos/011-pending-p3-silent-realtime-loop-exit-no-reconnect.md`
- `todos/012-pending-p3-supabase-select-star-explicit-columns.md`

**Related PR:**
- PR #23: feat/macos-swiftui-overhaul (all P1/P2 resolved)
