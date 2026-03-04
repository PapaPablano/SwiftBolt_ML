---
title: "feat: Unify Strategy Platform — Live Trading tab + Condition Builder merge"
type: feat
status: completed
date: 2026-03-04
origin: docs/brainstorms/2026-03-03-live-trading-executor-tradestation-brainstorm.md
---

# feat: Unify Strategy Platform — Live Trading tab + Condition Builder merge

## Enhancement Summary

**Deepened on:** 2026-03-04
**Research agents used:** TypeScript Reviewer, Architecture Strategist, Security Sentinel, Code Simplicity Reviewer, Best Practices Researcher, SwiftUI Framework Docs Researcher, Security Learnings, Agent-Native Reviewer

### Key Improvements Discovered

1. **`.id(path)` is required** on `FrontendWebEmbedView` — without it, sidebar navigation between tabs does NOT reload the React app (critical breakage)
2. **Auth gap for Live Trading is HIGH severity** — silent session expiry in a financial trading surface creates false sense of connectivity; requires explicit implementation
3. **`initialTab` must be an enum type in Swift**, not `String`, to prevent URL injection from ever being possible
4. **`useEmbeddedSymbol` hook is duplicated** in App.tsx and StrategyPlatform.tsx — extract before adding a third call site
5. **Drop `theme` prop entirely** — update CSS classes directly; both call sites are always dark
6. **Tailwind dark mode via `.dark` wrapper** is the idiomatic pattern, not prop-based class string switching
7. **`URLComponents` + `URLQueryItem`** required for Swift URL construction — never string interpolation for URL query params
8. **4 agent-native parity gaps** in `liveTradingApi`: enable/disable, pause/resume, risk params config, and eligible_strategies pre-flight endpoint

### Critical Issues Requiring Plan Amendments

- **WKWebView tab identity**: `updateNSView` does NOT reload URL on path change — `.id(path)` must be added
- **Auth for Live Trading**: Plan must address or provide an explicit "sign in required" placeholder
- **Type safety**: `initialTab as PlatformTab` cast is unsafe; use `isPlatformTab()` type guard
- **URL construction**: `"/strategy-platform?tab=\(initialTab)"` string interpolation requires `URLComponents`

---

## Overview

PR #28 (Live Trading Executor via TradeStation) shipped a backend executor and React
dashboard components (`LiveTradingDashboard.tsx`, `LiveTradingStatusWidget.tsx`) but they
are surfaced only as a top-level tab in the standalone React `App`. They are **invisible** to
the macOS SwiftUI client and not integrated into the `StrategyPlatform` unified view.

Simultaneously, the macOS sidebar shows "Condition Builder" → a bare standalone condition
builder (`/strategy-builder`), when a full `StrategyPlatform` component already exists with
strategies, builder, backtest, and paper-trading tabs — **but is never registered as a route**.

This plan:
1. Registers `/strategy-platform` as a frontend route exposing `StrategyPlatform`
2. Adds a **"Live Trading"** tab to `StrategyPlatform` rendering `LiveTradingDashboard`
3. Fixes a macOS build error (deleted `PaperTradingDashboardView.swift` still referenced)
4. Replaces standalone sidebar web-view embeds with a unified `StrategyPlatformWebView`
5. Adds a native **"Live Trading"** sidebar entry in the macOS app

## Problem Statement

### 1. `StrategyPlatform` is an orphaned component

`frontend/src/components/StrategyPlatform.tsx` defines a tabbed unified view (strategies,
builder, backtest, paper-trading) but **App.tsx only routes `/strategy-builder` and
`/backtesting`** — `StrategyPlatform` is never rendered. The macOS "Condition Builder" sidebar
entry loads the bare standalone builder, missing 4 tabs of functionality already built.

### 2. Live Trading has no macOS or StrategyPlatform surface

`LiveTradingDashboard.tsx` (372 lines) and `LiveTradingStatusWidget.tsx` (79 lines) exist
in the frontend, and `liveTradingApi` with 6 endpoints is wired in `strategiesApi.ts`. Yet
`StrategyPlatform.tsx:71` shows only `'strategies' | 'builder' | 'backtest' | 'paper-trading'`
— no live trading tab. The macOS `ContentView.swift:3–7` has no `liveTrading` enum case.

### 3. macOS build error — deleted file still referenced

`PaperTradingDashboardView.swift` was deleted in the current branch but
`ContentView.swift:50` still references `PaperTradingDashboardView()`. The Xcode build will
fail with a "cannot find type" error.

### 4. Three separate embedded routes → maintenance burden

The macOS sidebar separately loads `/strategy-builder`, `/backtesting`, and now would need a
`/live-trading` embed. Maintaining three separate Swift view structs for what is logically one
platform is unnecessary duplication.

## Proposed Solution

### Architecture

Replace three separate macOS embedded routes with a **single `StrategyPlatformWebView`** that
loads `/strategy-platform?tab=<name>`, allowing each sidebar entry to specify its default tab.
React reads the `tab` query param on load to set the initial active tab via `useState` initializer.

```
macOS Sidebar                       React Frontend
─────────────────────               ─────────────────────────────────────
"Strategy Builder" ──────────────▶  /strategy-platform?tab=builder
                                      └─ StrategyPlatform (5 tabs)
"Paper Trading"    ──────────────▶  /strategy-platform?tab=paper-trading
"Backtesting"      ──────────────▶  /strategy-platform?tab=backtest
"Live Trading" (new) ────────────▶  /strategy-platform?tab=live-trading
```

Tab content within `StrategyPlatform`:

| Tab | Component |
|-----|-----------|
| `strategies` | StrategiesTab (CRUD saved strategies) |
| `builder` | BuilderTab (entry + exit `StrategyConditionBuilder`) |
| `backtest` | `StrategyBacktestPanel` |
| `paper-trading` | `PaperTradingDashboard` |
| `live-trading` (**new**) | `LiveTradingDashboard` |

## Technical Approach

### Phase 0 — Extract `useEmbeddedSymbol` hook ⭐ NEW

**File:** `frontend/src/hooks/useEmbeddedSymbol.ts` (new file)

The `useEmbeddedSymbol` hook is identically duplicated in `App.tsx:29` and
`StrategyPlatform.tsx:30`. The plan adds a third call site via the embed wrapper. Extract
before adding more duplication:

```typescript
// frontend/src/hooks/useEmbeddedSymbol.ts
import { useState, useEffect } from 'react';

/**
 * Listens for window.postMessage({ type: 'symbolChanged', symbol })
 * from the macOS native bridge (FrontendWebViewRepresentable.injectSymbol).
 */
export function useEmbeddedSymbol(fallback = 'AAPL'): string {
  const [symbol, setSymbol] = useState(fallback);
  useEffect(() => {
    const handler = (e: MessageEvent) => {
      // Only accept messages from same origin or native WKWebView bridge (origin='')
      if (e.origin !== '' && e.origin !== window.location.origin) return;
      if (e.data?.type === 'symbolChanged' && typeof e.data.symbol === 'string') {
        setSymbol(e.data.symbol);
      }
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, []);
  return symbol;
}
```

> **Security note (from Security Sentinel + learnings):** Added `e.origin` check. In WKWebView,
> the native bridge delivers postMessage with `e.origin === ''` or the page's own origin. The
> guard blocks cross-origin senders in browser contexts without affecting native bridge delivery.

Update both `App.tsx` and `StrategyPlatform.tsx` to import from this shared hook. Remove the
local definitions.

---

### Phase 1 — Frontend: Register `/strategy-platform` route

**File:** `frontend/src/App.tsx`

Add the route and delete the two legacy embedded route functions — they become dead code once
the Swift side is updated to use `StrategyPlatformWebView`.

```typescript
import { StrategyPlatform } from './components/StrategyPlatform';
import { useEmbeddedSymbol } from './hooks/useEmbeddedSymbol';

// Near top of App(), before main App state:
const pathname = window.location.pathname;
if (pathname === '/strategy-platform') {
  const params = new URLSearchParams(window.location.search);
  const rawTab = params.get('tab') ?? '';
  const initialTab = isPlatformTab(rawTab) ? rawTab : undefined;
  return <StrategyPlatform initialTab={initialTab} />;
}
// Legacy routes kept while both Swift structs still reference them:
// if (pathname === '/strategy-builder') return <EmbeddedConditionBuilder />;
// if (pathname === '/backtesting') return <EmbeddedBacktesting />;
// → DELETE these once Phase 4 (StrategyPlatformWebView) ships and Xcode build passes
```

> **Simplification (from Code Simplicity Reviewer):** No `StrategyPlatformEmbed` wrapper
> function needed — the inline URL param read is 3 lines. `StrategyPlatform` already calls
> `useEmbeddedSymbol` internally.

> **Legacy route cleanup:** The macOS app is the sole consumer of the React routes. Once Phase 4
> ships and the Swift side is updated, delete `EmbeddedConditionBuilder`, `EmbeddedBacktesting`,
> and their route guards to eliminate ~38 lines of dead code.

---

### Phase 2 — Frontend: Add `initialTab` prop + Live Trading tab to `StrategyPlatform`

**File:** `frontend/src/components/StrategyPlatform.tsx`

**Step 2a — Type-safe `PlatformTab` + `isPlatformTab` type guard:**

```typescript
// Derive type FROM the TABS array — single source of truth
const TABS = [
  { id: 'strategies',   label: 'Strategies' },
  { id: 'builder',      label: 'Builder' },
  { id: 'backtest',     label: 'Backtest' },
  { id: 'paper-trading', label: 'Paper Trading' },
  { id: 'live-trading', label: 'Live Trading' },  // ← new
] as const;

type PlatformTab = typeof TABS[number]['id'];

/** Narrows a raw URL param string to PlatformTab without unsafe cast. */
function isPlatformTab(value: string): value is PlatformTab {
  return TABS.some(t => t.id === value);
}
```

> **Type safety fix (from TypeScript Reviewer):** `TABS` typed `as const` → `PlatformTab` is
> derived automatically. Adding a new tab updates the type. The `isPlatformTab` type guard
> eliminates the `as PlatformTab` cast that silences the compiler without providing safety.

**Step 2b — `initialTab` prop as `PlatformTab | undefined`:**

```typescript
interface StrategyPlatformProps {
  symbol?: string;
  initialTab?: PlatformTab;  // typed, not string
}

export function StrategyPlatform({ symbol: symbolProp, initialTab }: StrategyPlatformProps) {
  const embeddedSymbol = useEmbeddedSymbol(symbolProp ?? 'AAPL');

  // Lazy initializer — only evaluated on mount (correct React pattern)
  // initialTab is already validated at the call site; no runtime check needed here
  const [activeTab, setActiveTab] = useState<PlatformTab>(initialTab ?? 'strategies');
  // ...
}
```

> **React pattern note:** `useState` with a direct value (not a function) is correct here because
> `initialTab` is already a `PlatformTab` at this point — no computation needed. The URL param
> parsing and narrowing belong in the caller (App.tsx), not in StrategyPlatform. See
> [React useState reference](https://react.dev/reference/react/useState).

> **Re-render note:** `useState` reads its argument only on initial mount. `initialTab` changing
> after mount has no effect. If a caller ever needs to reset the tab, use `key` prop to force
> remount — do **not** add a `useEffect` to sync `initialTab` → `activeTab` (causes flash).

**Step 2c — Live Trading tab content:**

```typescript
import { LiveTradingDashboard } from './LiveTradingDashboard';

// In tab content switch:
case 'live-trading':
  return <LiveTradingDashboard onBack={() => setActiveTab('strategies')} />;
```

> **Prop check:** `LiveTradingDashboard` accepts `onBack?: () => void`. Wire it to navigate
> back to the strategies tab. Confirm the exact prop name before implementing.

> **Auth handling:** `LiveTradingDashboard` uses `useAuth()` internally. In the embedded WebView
> context, `useAuth()` may return null if no Supabase session is present. See Phase 2d.

**Step 2d — Auth gate for Live Trading tab:** ⭐ REQUIRED

> **From Architecture Strategist + Security Sentinel (HIGH severity):** Silent session expiry
> in a live trading surface creates a false sense of connectivity — the user may believe their
> stop-loss is being monitored when it is not.

Add a `useEmbeddedSession` hook that listens for auth tokens injected by the Swift host:

```typescript
// frontend/src/hooks/useEmbeddedSession.ts
import { useState, useEffect } from 'react';

/**
 * Receives a Supabase session token injected by the macOS WKWebView host.
 * The Swift side calls evaluateJavaScript to postMessage the token after didFinish.
 * Falls back to null (unauthenticated) if no token is injected.
 */
export function useEmbeddedSession(): string | null {
  const [token, setToken] = useState<string | null>(null);
  useEffect(() => {
    const handler = (e: MessageEvent) => {
      if (e.origin !== '' && e.origin !== window.location.origin) return;
      if (e.data?.type === 'sessionToken' && typeof e.data.token === 'string') {
        setToken(e.data.token);
      }
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, []);
  return token;
}
```

In the Live Trading tab render, show an explicit locked state when unauthenticated rather than
allowing `LiveTradingDashboard` to silently fail with 401s:

```typescript
case 'live-trading': {
  // Auth state derived from injected token or fallback useAuth
  const embeddedToken = useEmbeddedSession();
  if (!embeddedToken) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 text-gray-400">
        <span className="text-4xl">🔒</span>
        <p className="text-sm">Live Trading requires sign-in.</p>
        <p className="text-xs text-gray-500">Sign in through the main app to access this feature.</p>
      </div>
    );
  }
  return <LiveTradingDashboard onBack={() => setActiveTab('strategies')} />;
}
```

**Alternatively (simpler short-term):** Swift injects the session token after `webView.didFinish`
using `JSONSerialization` (following the existing `injectSymbol` pattern):

```swift
// FrontendWebViewRepresentable Coordinator, in webView(_:didFinish:):
private func injectSession(_ token: String, into webView: WKWebView) {
    let payload: [String: Any] = ["type": "sessionToken", "token": token]
    guard let data = try? JSONSerialization.data(withJSONObject: payload),
          let json = String(data: data, encoding: .utf8) else { return }
    webView.evaluateJavaScript("window.postMessage(\(json), '*');")
}
```

The Swift side reads the token from `SupabaseService.shared.client.auth.currentSession?.accessToken`.

---

### Phase 3 — Frontend: Fix StrategyConditionBuilder dark theme

**File:** `frontend/src/components/StrategyConditionBuilder.tsx`

> **Simplification (from Code Simplicity Reviewer + Architecture Strategist):** Both call sites
> (`EmbeddedConditionBuilder` in App.tsx and `BuilderTab` in StrategyPlatform.tsx) are always
> wrapped in a dark background (`bg-gray-950`). There is no light-mode call site. **Do NOT add
> a `theme` prop** — simply update the hardcoded CSS classes to dark-mode values unconditionally.

> **Tailwind idiomatic pattern (from Best Practices Researcher):** The recommended Tailwind v3
> approach for forced dark mode on a component is to wrap it in `<div className="dark">` and use
> `dark:` variants on all descendant elements. This keeps the component portable — it renders
> light by default in non-dark contexts and dark when a `.dark` ancestor is present.

Preferred approach — **add `.dark` wrapper in `BuilderTab`**, use `dark:` variants in `StrategyConditionBuilder`:

```tsx
// In StrategyPlatform.tsx BuilderTab — wrap with dark ancestor:
function BuilderTab(...) {
  return (
    <div className="dark">  {/* forces dark: variants for all descendants */}
      <StrategyConditionBuilder theme="dark" ... />
    </div>
  );
}
```

```tsx
// In StrategyConditionBuilder.tsx — use dark: variants unconditionally:
// Before: className="bg-white border-gray-200 text-gray-700"
// After:  className="bg-gray-50 dark:bg-gray-900 border-gray-200 dark:border-gray-700 text-gray-900 dark:text-white"
```

Verify `tailwind.config.ts` has `darkMode: 'class'`. If not, add it.

> **`ConditionBuilderProps` location:** The interface is declared in
> `frontend/src/lib/conditionBuilderUtils.ts:44`, not in `StrategyConditionBuilder.tsx`. Any
> interface change must happen there.

---

### Phase 4 — macOS: Create `StrategyPlatformWebView` + fix build error

**File:** `client-macos/SwiftBoltML/Views/StrategyBuilderWebView.swift`

**Step 4a — Define a typed enum for tab values:**

> **Security + type safety (from Security Learnings + Framework Docs Researcher):** Keep
> `initialTab` as an enum type, not a `String`. This prevents URL injection from ever being
> possible and makes invalid tabs a compile error, not a runtime fallback.

```swift
// MARK: - Strategy Platform Tab

enum StrategyPlatformTab: String, CaseIterable {
    case builder      = "builder"
    case backtest     = "backtest"
    case paperTrading = "paper-trading"
    case liveTrading  = "live-trading"
    case strategies   = "strategies"
}
```

**Step 4b — `StrategyPlatformWebView` struct using `URLComponents`:**

> **URL construction (from Framework Docs Researcher):** Use `URLComponents` + `URLQueryItem`
> for query string construction — never raw string interpolation. `URLQueryItem` auto-encodes
> values and prevents double-encoding.

```swift
// MARK: - Strategy Platform WebView

/// Embeds the unified React Strategy Platform via WKWebView.
/// initialTab controls which tab is active on load via the React `?tab=` param.
///
/// IMPORTANT: initialTab values are static enum cases. Do NOT widen this to String
/// as the rawValue is interpolated into the URL path.
struct StrategyPlatformWebView: View {
    let symbol: String?
    var initialTab: StrategyPlatformTab = .builder

    private var path: String {
        // URLComponents handles encoding. Tab rawValues are ASCII alphanumerics + hyphens only.
        var components = URLComponents()
        components.path = "/strategy-platform"
        components.queryItems = [URLQueryItem(name: "tab", value: initialTab.rawValue)]
        return components.url?.absoluteString
            ?? "/strategy-platform?tab=\(initialTab.rawValue)"
    }

    var body: some View {
        FrontendWebEmbedView(
            path: path,
            messageName: "strategyPlatform",
            navigationTitle: "Strategy Platform",
            loadingLabel: "Loading…",
            symbol: symbol
        )
        .id(path)  // ← CRITICAL: forces WKWebView recreation when tab changes
    }
}
```

> **Critical fix (from Architecture Strategist + Framework Docs Researcher):** The `.id(path)`
> modifier is **required**. Without it, when the user navigates from "Strategy Builder" to
> "Backtesting" in the sidebar, SwiftUI calls `updateNSView` (which only injects the symbol) —
> it does NOT reload the URL. The React app stays on whatever tab was last shown. `.id(path)`
> forces SwiftUI to call `dismantleNSView` + `makeNSView` (fresh WKWebView + reload) whenever
> the path changes. The existing teardown code in `dismantleNSView` (removes script handlers)
> fires correctly on each transition.

**Step 4c — Fix `ContentView.swift` build error:**

```swift
// Before (line 50, build error — file deleted):
case .strategyPlatform(.paperTrading):
    PaperTradingDashboardView()

// After:
case .strategyPlatform(.paperTrading):
    StrategyPlatformWebView(
        symbol: appViewModel.selectedSymbol?.ticker,
        initialTab: .paperTrading
    )
```

---

### Phase 5 — macOS: Full sidebar + enum updates

**File:** `client-macos/SwiftBoltML/Views/ContentView.swift`

**Step 5a — Extend `StrategyPlatformSection` enum:**

```swift
enum StrategyPlatformSection: Hashable {
    case builder
    case paperTrading
    case backtesting
    case liveTrading   // ← new
}
```

> **Swift enum Hashable note:** Swift synthesizes `Hashable` and `Equatable` automatically when
> all associated values conform. Adding `liveTrading` (no associated value) is safe. No manual
> conformance needed. Xcode enforces exhaustiveness, so the compiler will error until Step 5b
> adds the matching switch arm — add both atomically.

**Step 5b — Update all four detail switch arms:**

```swift
case .strategyPlatform(.builder):
    StrategyPlatformWebView(
        symbol: appViewModel.selectedSymbol?.ticker,
        initialTab: .builder
    )
case .strategyPlatform(.paperTrading):
    StrategyPlatformWebView(
        symbol: appViewModel.selectedSymbol?.ticker,
        initialTab: .paperTrading
    )
case .strategyPlatform(.backtesting):
    StrategyPlatformWebView(
        symbol: appViewModel.selectedSymbol?.ticker,
        initialTab: .backtest
    )
case .strategyPlatform(.liveTrading):          // ← new arm
    StrategyPlatformWebView(
        symbol: appViewModel.selectedSymbol?.ticker,
        initialTab: .liveTrading
    )
```

**Step 5c — Sidebar labels: rename + add Live Trading:**

```swift
Section {
    NavigationLink(value: SidebarSection.strategyPlatform(.builder)) {
        Label("Strategy Builder", systemImage: "checklist")
        // renamed from "Condition Builder"
    }
    NavigationLink(value: SidebarSection.strategyPlatform(.paperTrading)) {
        Label("Paper Trading", systemImage: "dollarsign.circle")
    }
    NavigationLink(value: SidebarSection.strategyPlatform(.backtesting)) {
        Label("Backtesting", systemImage: "clock.arrow.2.circlepath")
    }
    NavigationLink(value: SidebarSection.strategyPlatform(.liveTrading)) {  // ← new
        Label("Live Trading", systemImage: "bolt.fill")
    }
} header: {
    Text("Strategy Platform")
}
```

---

### Phase 6 — Agent-Native Parity for Live Trading API ⭐ NEW

> **From Agent-Native Reviewer:** `liveTradingApi` only exposes 7 of 13 live trading
> capabilities. The planned Live Trading tab will add UI for enable/disable, pause/resume, and
> risk params — without corresponding agent-accessible methods, this violates agent-native
> parity.

**File:** `frontend/src/api/strategiesApi.ts`

Add missing wrapper methods to `liveTradingApi`:

```typescript
export const liveTradingApi = {
  // ... existing 6 methods ...

  /** Enable or disable live trading for a strategy. */
  setLiveTradingEnabled: (strategyId: string, enabled: boolean, token: string) =>
    invokeFunction('strategies', {
      method: 'PUT',
      body: { id: strategyId, live_trading_enabled: enabled },
      token,
    }),

  /** Pause or resume live trading for a strategy (overrides circuit breaker). */
  setPaused: (strategyId: string, paused: boolean, token: string) =>
    invokeFunction('strategies', {
      method: 'PUT',
      body: { id: strategyId, live_trading_paused: paused },
      token,
    }),

  /** Update live risk parameters for a strategy. */
  updateRiskParams: (
    strategyId: string,
    params: {
      live_risk_pct?: number;            // 0.1–20% per trade
      live_daily_loss_limit_pct?: number; // 0.1–20% of equity
      live_max_positions?: number;        // 1–50 concurrent
      live_max_position_pct?: number;     // 0.1–50% of equity per position
    },
    token: string
  ) =>
    invokeFunction('strategies', {
      method: 'PUT',
      body: { id: strategyId, ...params },
      token,
    }),

  /** Get strategies eligible for live execution (live_trading_enabled=true, not paused). */
  eligibleStrategies: (symbol: string, timeframe: string, token: string) =>
    invokeFunction('live-trading-executor', {
      method: 'GET',
      params: { action: 'eligible_strategies', symbol, timeframe },
      token,
    }),

  /** Get current rate limit consumption. Useful for agents to know when to back off. */
  rateLimitStatus: (token: string) =>
    invokeFunction('live-trading-executor', {
      method: 'GET',
      params: { action: 'rate_limit_status' },
      token,
    }),
};
```

> **UI/API asymmetry fix (from Agent-Native Reviewer):** The `LiveTradingDashboard` close
> button is gated on `pos.status === 'open'` but the executor accepts `status IN ('open',
> 'pending_bracket')`. Update the UI condition to match:
> ```typescript
> // LiveTradingDashboard.tsx — update close button condition:
> // Before: pos.status === 'open'
> // After:  pos.status === 'open' || pos.status === 'pending_bracket'
> ```

---

### Phase 7 — Live Trading UX Hardening ⭐ NEW

> **From Best Practices Researcher:** These patterns prevent the most common trading dashboard
> failure modes: stale data, silent disconnections, and background resource waste.

**File:** `frontend/src/components/LiveTradingDashboard.tsx`

**Stale data indicator:**

```tsx
// Add last-updated timestamp display near P&L figures
function StaleIndicator({ lastUpdatedAt }: { lastUpdatedAt: Date }) {
  const [age, setAge] = useState(0);
  useEffect(() => {
    const timer = setInterval(
      () => setAge(Math.floor((Date.now() - lastUpdatedAt.getTime()) / 1000)),
      1000
    );
    return () => clearInterval(timer);
  }, [lastUpdatedAt]);
  return (
    <span className={age > 10 ? 'text-yellow-400 text-xs' : 'text-gray-500 text-xs'}>
      {age < 5 ? 'Live' : `${age}s ago`}
    </span>
  );
}
```

**Pause polling when hidden (macOS WKWebView resource management):**

```typescript
// In LiveTradingDashboard — use Page Visibility API
useEffect(() => {
  const onVisibilityChange = () => {
    if (document.hidden) stopPolling();
    else startPolling();
  };
  document.addEventListener('visibilitychange', onVisibilityChange);
  return () => document.removeEventListener('visibilitychange', onVisibilityChange);
}, []);
```

**Broker connection status bar** (persistent, not modal):

```tsx
type ConnectionStatus = 'live' | 'delayed' | 'disconnected' | 'market_closed';

const STATUS_CONFIG: Record<ConnectionStatus, { label: string; dotClass: string }> = {
  live:          { label: 'Live',          dotClass: 'bg-green-400 animate-pulse' },
  delayed:       { label: 'Delayed',       dotClass: 'bg-yellow-400' },
  disconnected:  { label: 'Disconnected',  dotClass: 'bg-red-500' },
  market_closed: { label: 'Market Closed', dotClass: 'bg-gray-500' },
};
```

**Explicit unauthenticated state** (financial safety — from Security Sentinel):

The live trading surface must render an unambiguous locked state when the session is not
available — never show stale or empty position data that could be mistaken for "connected":

```tsx
if (!session?.access_token) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-3 p-8">
      <div className="w-12 h-12 rounded-full bg-red-900/30 flex items-center justify-center">
        <span className="text-red-400 text-xl">⚠</span>
      </div>
      <p className="text-red-400 font-medium">Live Trading Not Active</p>
      <p className="text-gray-500 text-sm text-center">
        You are not signed in. Live positions are NOT being monitored.
      </p>
    </div>
  );
}
```

## System-Wide Impact

### Interaction Graph

```
User clicks "Live Trading" sidebar
  → ContentView detail switch → StrategyPlatformWebView(initialTab: .liveTrading)
    → FrontendWebEmbedView(path: "/strategy-platform?tab=live-trading")
      → .id(path) forces fresh WKWebView on each sidebar navigation
        → WKWebView loads bundled React app
          → App.tsx pathname === '/strategy-platform'
            → isPlatformTab("live-trading") → true → initialTab = 'live-trading'
              → StrategyPlatform renders with activeTab = 'live-trading'
                → useEmbeddedSession() waits for injected JWT token
                  → Swift injectSession() fires in webView(_:didFinish:)
                    → React receives sessionToken message
                      → LiveTradingDashboard mounts with valid session
                        → liveTradingApi.positions/summary/brokerStatus called
                          → live-trading-executor Edge Function validates JWT
```

### Error & Failure Propagation

- **`.id(path)` on each sidebar navigation**: `dismantleNSView` removes script handlers →
  `makeNSView` creates fresh WKWebView → re-registers handler → loads URL from scratch.
  This is the correct behavior: each sidebar click gets a fresh React app at the correct tab.
- **No session injected / session expired**: `useEmbeddedSession` returns `null` → Live Trading
  tab shows explicit "not active" locked state (see Phase 7). No 401 errors reach the user silently.
- **Unknown tab param from future enum value**: `isPlatformTab()` type guard returns false →
  defaults to `undefined` → `StrategyPlatform` uses `'strategies'` fallback — graceful.
- **Swift enum exhaustiveness**: Adding `liveTrading` without the switch arm is a compile error.
  The plan adds both atomically in Phase 5.

### State Lifecycle Risks

- **Tab resets on each sidebar click** (due to `.id(path)`): React state resets on each
  WKWebView reload. Acceptable — `StrategyPlatform` persists strategies via Supabase; the tab
  restores to the correct view via the URL param.
- **Session token re-injection**: Swift's `webView(_:didFinish:)` injects the session after
  each fresh load. The token is the current session at load time. If the Supabase session expires
  while the tab is open, `liveTradingApi` calls will get 401s. The `StaleIndicator` and the
  polling error handler should surface this as a visible "session expired" state.
- **`LiveTradingDashboard` polling timer**: Starts on mount, cancels on unmount. With `.id(path)`,
  this is always clean — old instance fully unmounts before new one mounts.

### API Surface Parity

- `liveTradingApi` now covers: positions, trades, summary, brokerStatus, closePosition, execute,
  disconnectBroker, **setLiveTradingEnabled**, **setPaused**, **updateRiskParams**,
  **eligibleStrategies**, **rateLimitStatus** (Phase 6 additions).
- `save_broker_token` (OAuth callback) is intentionally NOT in `liveTradingApi` — it is a
  human-in-the-loop step requiring OAuth redirect. Document as human-only in system prompt.
- `recoverPositions` (admin/emergency action) is intentionally deferred.

### Integration Test Scenarios

1. **Tab deep link:** Load `/strategy-platform?tab=live-trading` → `activeTab` = `'live-trading'`, `LiveTradingDashboard` renders unauthenticated state (no session injected).
2. **Unknown tab param:** Load `/strategy-platform?tab=nonexistent` → `isPlatformTab()` returns false → defaults to `strategies` tab.
3. **macOS sidebar navigation:** Click "Backtesting" → `.id(path)` changes → `dismantleNSView` → `makeNSView` → fresh WKWebView loads `/strategy-platform?tab=backtest`.
4. **Sidebar back-and-forth:** Click "Strategy Builder" → "Backtesting" → "Strategy Builder" → each click produces a fresh WKWebView at the correct tab (not the previously visible tab).
5. **Build check:** `xcodebuild -scheme SwiftBoltML` passes with no `PaperTradingDashboardView` error.
6. **Theme consistency:** `StrategyConditionBuilder` in "Builder" tab renders dark backgrounds — no white flash.
7. **Agent parity:** Calling `liveTradingApi.eligibleStrategies('AAPL', '1D', token)` returns only live-enabled, non-paused strategies.

## Acceptance Criteria

### Functional

- [x] `/strategy-platform` route is registered in `App.tsx` and renders `StrategyPlatform`
- [x] `StrategyPlatform` accepts `initialTab?: PlatformTab` and sets active tab from URL `?tab=` param
- [x] `isPlatformTab()` type guard is used — no `as PlatformTab` casts
- [x] `StrategyPlatform` has a "Live Trading" tab (5th tab) rendering `LiveTradingDashboard`
- [x] All 5 tabs render without JavaScript console errors
- [x] Live Trading tab shows explicit locked state when session is null (existing `useAuth()` guard in `LiveTradingDashboard`)
- [x] Live Trading tab shows explicit locked state when session expires mid-session
- [x] Condition builder in "Builder" tab uses dark theme — `<div className="dark">` wrapper in `BuilderTab`
- [x] macOS: `PaperTradingDashboardView()` reference replaced with `StrategyPlatformWebView`
- [x] macOS: "Condition Builder" sidebar label renamed to "Strategy Builder"
- [x] macOS: Sidebar navigation between tabs reloads the React app to the correct tab (`.id(path)` on `StrategyPlatformWebView`)
- [x] macOS: "Paper Trading" sidebar entry loads strategy platform with paper-trading tab active
- [x] macOS: "Backtesting" sidebar entry loads strategy platform with backtest tab active
- [x] macOS: "Live Trading" sidebar entry appears and loads strategy platform with live-trading tab
- [x] macOS: All four `StrategyPlatformSection` cases handled exhaustively in detail switch
- [x] `liveTradingApi` includes wrappers for `setLiveTradingEnabled`, `setPaused`, `updateRiskParams`, `eligibleStrategies`, `rateLimitStatus`
- [x] `LiveTradingDashboard` Close button shows for both `open` and `pending_bracket` positions

### Non-Functional

- [x] `useEmbeddedSymbol` extracted to `frontend/src/hooks/useEmbeddedSymbol.ts` — no duplication
- [x] `useEmbeddedSymbol` listener validates `e.origin` before accepting messages
- [x] `StrategyPlatformTab` is a Swift enum (not `String`) — `initialTab` is type-safe
- [x] Swift URL construction uses `URLComponents` + `URLQueryItem` (not string interpolation)
- [x] `StrategyPlatformWebView` delegates to `FrontendWebEmbedView` — no new `NSViewRepresentable`
- [ ] Legacy `/strategy-builder` and `/backtesting` routes removed once Phase 4 ships (deferred — routes kept for backward compat)

### Quality Gates

- [x] `npx tsc --noEmit` in `frontend/` passes (TypeScript compilation clean, exit 0)
- [ ] `xcodebuild -scheme SwiftBoltML -destination 'platform=macOS'` passes
- [ ] `npm run lint` in `frontend/` passes (ESLint not installed; TypeScript check substituted)
- [ ] Deno lint on `supabase/functions/` passes

## Alternative Approaches Considered

### A. Keep separate embedded routes per tab (rejected)

Keep `/strategy-builder`, `/backtesting`, add `/live-trading` as separate routes.

**Rejected:** `StrategyPlatform` already exists as the right abstraction. Three separate routes
become four, each requiring its own Swift view struct.

### B. Single unified "Strategy Platform" sidebar entry (partially adopted)

Replace all four sidebar entries with one "Strategy Platform" entry; user navigates tabs inside.

**Partially adopted:** Separate sidebar entries preserved for macOS navigation granularity.
Underlying implementation is unified via `StrategyPlatformWebView`.

### C. Auth token injection via postMessage (adopted in Phase 2d)

Inject the Supabase session JWT from Swift → WKWebView using `JSONSerialization` after
`webView(_:didFinish:)`. See Phase 2d. Originally deferred; elevated to required due to
financial safety concerns (Architecture Strategist HIGH finding).

### D. Cached WKWebView instances via `@Observable` store (deferred)

Keep WKWebView instances alive in a class-based store to preserve React state across sidebar
navigation. See [Best Practices Research — NavigationSplitView caching].

**Deferred:** With `.id(path)` providing clean recreation and Supabase persistence providing
state recovery, cached instances are not needed for initial launch. Revisit if load latency
becomes a UX concern.

## Implementation Phases

### Phase 0 — Extract `useEmbeddedSymbol` hook (15 min)
- Create `frontend/src/hooks/useEmbeddedSymbol.ts` with `e.origin` validation
- Remove duplicate definitions from `App.tsx` and `StrategyPlatform.tsx`

### Phase 1 — Frontend route + legacy cleanup (20 min)
- `App.tsx`: Add `/strategy-platform` route, inline URL param read
- Delete `EmbeddedConditionBuilder`, `EmbeddedBacktesting`, their route guards after Phase 4

### Phase 2 — StrategyPlatform: type-safe tabs + Live Trading (60 min)
- `TABS as const` → `PlatformTab` derived type + `isPlatformTab` guard
- `initialTab?: PlatformTab` prop + `useState` lazy initializer
- Live Trading tab + `useEmbeddedSession` auth gate + explicit locked state

### Phase 3 — StrategyConditionBuilder dark theme (20 min)
- Update CSS classes to `dark:` variants, no new prop
- Wrap `BuilderTab` in `<div className="dark">`
- Verify `tailwind.config.ts` has `darkMode: 'class'`

### Phase 4 — macOS: `StrategyPlatformTab` enum + `StrategyPlatformWebView` + build fix (30 min)
- Add `StrategyPlatformTab` enum to `StrategyBuilderWebView.swift`
- Add `StrategyPlatformWebView` struct with `.id(path)` and `URLComponents`
- Fix `ContentView.swift:50` build error
- Add `injectSession()` method to `FrontendWebViewRepresentable` Coordinator

### Phase 5 — macOS: Full sidebar + enum (20 min)
- Add `liveTrading` to `StrategyPlatformSection` enum
- Add matching switch arm + update all three existing arms
- Rename "Condition Builder" → "Strategy Builder", add "Live Trading" NavigationLink

### Phase 6 — Agent-native parity (25 min)
- Add 5 new methods to `liveTradingApi` in `strategiesApi.ts`
- Fix `LiveTradingDashboard` close button condition to include `pending_bracket`

### Phase 7 — Live Trading UX (30 min)
- Add `StaleIndicator` component
- Add `document.hidden` pause/resume for polling
- Add `ConnectionStatusBar` component
- Confirm explicit unauthenticated locked state is visually clear

## Dependencies & Prerequisites

- PR #27 merged ✅ (Advanced Backtester Upgrade)
- PR #28 merged ✅ (Live Trading Executor — `LiveTradingDashboard`, `liveTradingApi`, executor Edge Function)
- `StrategyPlatform.tsx` exists ✅ (already written, just not routed)
- `LiveTradingDashboard.tsx` exists ✅ (PR #28 shipped it)
- `FrontendWebEmbedView` is reusable ✅ — no new NSViewRepresentable plumbing needed
- `tailwind.config.ts` must have `darkMode: 'class'` — verify before Phase 3

## Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| `.id(path)` not applied → wrong tab on sidebar nav | N/A if followed | High | Phase 4 adds it explicitly with explanation |
| Session never injected → Live Trading always locked | Low | Medium | Phase 2d adds `injectSession()` in Swift didFinish |
| `StrategyConditionBuilder` interface in wrong file | Low | Low | Interface is in `conditionBuilderUtils.ts:44` — update there |
| `LiveTradingDashboard` `onBack` prop name mismatch | Low | Low | Verify prop name before implementing Phase 2c |
| Swift `StrategyPlatformTab.backtest` → rawValue `"backtest"` vs React `"backtest"` | Low | High | Both sides use `"backtest"` as confirmed in TABS array |
| URL query param silently dropped by WKWebView | Low | High | Framework docs confirm query params pass through to React; `decidePolicyFor` sees full URL |

## Sources & References

### Origin
- **Brainstorm:** `docs/brainstorms/2026-03-03-live-trading-executor-tradestation-brainstorm.md`

### Security
- `docs/solutions/security-issues/swiftui-credential-and-injection-hardening.md` — JSONSerialization for evaluateJavaScript; WeakScriptHandler; dismantleNSView cleanup

### External Documentation
- [React useState lazy initializer](https://react.dev/reference/react/useState)
- [Tailwind CSS Dark Mode — class strategy](https://tailwindcss.com/docs/dark-mode)
- [Apple NSViewRepresentable](https://developer.apple.com/documentation/swiftui/nsviewrepresentable) — makeNSView/updateNSView contract
- [Apple NavigationSplitView](https://developer.apple.com/documentation/swiftui/navigationsplitview)
- [Apple WKNavigationType docs](https://developer.apple.com/documentation/webkit/wknavigationtype) — initial load is `.other`
- [URLComponents + URLQueryItem](https://www.advancedswift.com/a-guide-to-urls-in-swift/)
- [WWDC22: Use SwiftUI with AppKit](https://developer.apple.com/videos/play/wwdc2022/10075/)

### Related Work
- PR #27 `feat/advanced-backtester-engine-upgrade` (merged 2026-03-04)
- PR #28 `feat: Live Trading Executor via TradeStation` (merged 2026-03-04)
- `frontend/src/components/StrategyPlatform.tsx:71` — current `PlatformTab` type
- `frontend/src/App.tsx:93–94` — existing pathname routes
- `frontend/src/api/strategiesApi.ts:34–71` — `liveTradingApi`
- `client-macos/SwiftBoltML/Views/ContentView.swift:3–7` — `StrategyPlatformSection` enum
- `client-macos/SwiftBoltML/Views/StrategyBuilderWebView.swift:55` — `FrontendWebEmbedView` pattern
