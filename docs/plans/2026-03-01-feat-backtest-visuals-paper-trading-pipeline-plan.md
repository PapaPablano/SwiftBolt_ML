---
title: "feat: Backtest Visuals + Paper Trading Pipeline"
type: feat
status: active
date: 2026-03-01
origin: docs/brainstorms/2026-03-01-backtest-visuals-paper-trading-pipeline-brainstorm.md
reviewed: 2026-03-01
review_todos: "059-068"
---

# feat: Backtest Visuals + Paper Trading Pipeline

## Overview

A unified strategy execution pipeline that enhances backtest visualization on charts, enriches the trade review panel, and bridges backtesting to paper trading via the React frontend. All three features share a unified `Trade` type with `direction` and `closeReason` fields, designed upfront to avoid migration pain (see brainstorm: Full Pipeline approach).

**Post-review simplification:** Original 5-phase plan consolidated to 3 phases after technical review (todos 059-068). Key changes: aggressive Phase 4 scope cut (no new npm deps), auth simplified to AuthContext + login modal, review screen simplified to confirmation modal, strategyTranslator promoted to Phase A.

## Problem Statement / Motivation

The current backtest experience has three major gaps:

1. **Chart visuals are minimal** — Only basic green/red arrow markers exist (`TradingViewChart.tsx:498-523`). No connecting lines, shaded trade regions, or P&L labels on the chart.

2. **Trade review lacks detail** — The trade table in `App.tsx:351-378` is capped at 20 rows, has no direction/closeReason columns, no sorting. `profitFactor`, `avgWin`, `avgLoss` are always 0 in the fallback path.

3. **No path from backtest to paper trading** — `PaperTradingDashboard.tsx` (607 lines) exists but is not routed in `App.tsx`. No deploy button, no way to activate strategies in the paper trading executor from the web dashboard.

## Proposed Solution

Three implementation phases (consolidated from original 5 after review):

1. **Phase A: Auth + Trade Type + Strategy Translator** — Auth, backend enhancements, canonical condition format translator
2. **Phase B: Chart Visuals + Table Improvements** — TradingView Series Primitives, uncap trade table, add new columns
3. **Phase C: Paper Trading Bridge** — Deploy button, confirmation modal, wire dashboard tab

## Technical Approach

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     React Frontend                          │
│                                                             │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────────┐ │
│  │ Strategy  │→ │  Backtest    │→ │  Paper Trading        │ │
│  │ Builder   │  │  Results     │  │  Deploy + Dashboard   │ │
│  └──────────┘  └──────────────┘  └───────────────────────┘ │
│       ↕              ↕                     ↕                │
│  TradingView    Enhanced Table     Supabase Auth            │
│  Primitives     (native HTML)      + paper-trading-executor │
└────────────────────────┬────────────────────────────────────┘
                         ↓
              Supabase Edge Functions
              (backtest-strategy, strategy-backtest-worker,
               paper-trading-executor)
                         ↓
              PostgreSQL (strategy tables, paper_trading_*)
```

### Implementation Phases

---

#### Phase A: Auth + Trade Type + Strategy Translator

Combines original Phases 1 + 2. Auth for paper trading, unified Trade type, backend enhancements, and the canonical strategy condition translator.

##### A.1: Supabase Auth

**Tasks:**

1. Create `frontend/src/contexts/AuthContext.tsx` — lightweight React context wrapping `supabase.auth.onAuthStateChange()`, exposes `user`, `session`, `signIn()`, `signOut()`, `loading`. Handle `TOKEN_REFRESHED` events for session continuity.
2. Create inline login modal (not a separate AuthGate page) — email/password only, no magic link. Shown as a modal when unauthenticated user clicks "Deploy to Paper Trading".
3. Wrap `App` component in `<AuthProvider>` in `main.tsx`
4. Update `PaperTradingDashboard.tsx` to use `session.access_token` as Bearer token instead of anon key
5. Enable Supabase Auth email provider in dashboard (manual step, document in README)

**Key decisions:**
- Auth is required **only for paper trading features** — chart viewing and backtesting remain unauthenticated (see brainstorm: Decision 9)
- Email/password only — no magic link in v1 (simplification per review todo 063)
- Login is a modal, not a dedicated page (simplification per review todo 063)
- AuthContext handles `TOKEN_REFRESHED` events (review todo 068)

##### A.2: Fix Paper Trading Executor Auth (P1 Security — todo 059)

**CRITICAL: Must be done before any deploy flow is built.**

1. Add JWT authentication to all POST endpoints in `paper-trading-executor/index.ts` (currently POST operations have zero auth)
2. Add user ownership verification to `close_position` action — add `.eq("user_id", user.id)` to position query
3. Add rate limiting: 10 requests/minute per user for POST `/execute` using shared `_shared/rate-limiter.ts` (todo 064)
4. Add server-side indicator allowlist validation — reject conditions with unrecognized indicator names (todo 064)
5. Restrict CORS origins from wildcard `*` to production domain + localhost (todo 068)

##### A.3: Resolve Backtest Auth Ambiguity (P1 — todo 060)

`backtest-strategy/index.ts` already requires auth (lines 25-31), but the plan says backtesting should be unauthenticated. The frontend currently works by sending the anon key as a Bearer token (fragile).

**Decision: Make backtesting explicitly unauthenticated.**
- Modify `backtest-strategy/index.ts` to allow anonymous access (skip auth check or accept anon role)
- Document the decision in the endpoint code
- Remove fragile anon-key-as-jwt pattern from `backtestService.ts`

##### A.4: Unified Trade Type + Backend Enhancements

1. Extend `Trade` type in `frontend/src/types/strategyBacktest.ts`:

```typescript
export interface Trade {
  // ... existing fields ...
  direction: 'long' | 'short';
  closeReason: 'SL_HIT' | 'TP_HIT' | 'EXIT_SIGNAL' | 'END_OF_PERIOD';
  // duration computed inline where needed: new Date(exitTime) - new Date(entryTime)
}
```

2. Enhance `strategy-backtest-worker/index.ts` to emit `direction` and `close_reason` on each trade. The exit path at lines 448-464 already evaluates `exitByCondition` and `exitByRisk` separately — close reason is a simple branch:
   - `pnlPct >= takeProfit` → `TP_HIT`
   - `pnlPct <= -stopLoss` → `SL_HIT`
   - `exitByCondition && !exitByRisk` → `EXIT_SIGNAL`
   - End of data → `END_OF_PERIOD`

3. Compute and return `profit_factor`, `avg_win`, `avg_loss`, `buy_and_hold_return_pct` server-side (currently 0 on frontend, and buy-and-hold uses direct FastAPI calls — review todo 067)

4. Update `backtest-strategy/index.ts` to pass through new fields

5. Update `frontend/src/lib/backtestService.ts`:
   - Map `close_reason` → `closeReason`
   - Add fallback defaults when fields absent (FastAPI preset path): `direction: 'long'`, `closeReason: 'EXIT_SIGNAL'`
   - Use worker-provided `buy_and_hold_return_pct`, remove direct FastAPI calls

##### A.5: Canonical Strategy Condition Translator (promoted from Phase 5 — todo 061)

Three different condition formats exist:

| Field | Frontend | Backtest Worker | Paper Executor |
|---|---|---|---|
| Indicator | `type: 'rsi'` | `name: 'rsi'` | `indicator: 'RSI'` |
| Operator | `'>' / 'cross_up'` | `'above' / 'below'` | `'>' / 'cross_up'` |
| ID | none | none | `id: string` |
| Logical | implicit AND | implicit AND | `logicalOp: 'AND'\|'OR'` |

Create `frontend/src/lib/strategyTranslator.ts` as the single canonical translator:
- `toWorkerFormat(conditions: EntryExitCondition[]): WorkerCondition[]`
- `toExecutorFormat(conditions: EntryExitCondition[]): ExecutorCondition[]`
- `fromWorkerFormat(conditions: WorkerCondition[]): Trade['direction' | 'closeReason']` (optional, for mapping responses)

**Files to create:**
- `frontend/src/contexts/AuthContext.tsx`
- `frontend/src/lib/strategyTranslator.ts`

**Files to modify:**
- `frontend/src/main.tsx` — wrap in AuthProvider
- `frontend/src/App.tsx` — add login modal, conditionally show for paper trading
- `frontend/src/types/strategyBacktest.ts` — extend Trade interface
- `frontend/src/lib/backtestService.ts` — map new fields, use worker buy-and-hold, remove FastAPI calls
- `frontend/src/components/PaperTradingDashboard.tsx` — use session JWT
- `supabase/functions/strategy-backtest-worker/index.ts` — add direction, close_reason, profit_factor, avg_win, avg_loss, buy_and_hold_return_pct
- `supabase/functions/backtest-strategy/index.ts` — pass through new fields, make auth optional
- `supabase/functions/paper-trading-executor/index.ts` — add POST auth, ownership checks, rate limiting, indicator validation, CORS restriction

**Testing:**
- AuthContext: sign in, sign out, token refresh, session persistence
- backtestService: mapping tests for new fields, fallback when fields absent
- strategyTranslator: all format conversions with edge cases
- Executor: POST returns 401 without JWT, ownership verified on close_position

**Acceptance criteria:**
- [x] Users can sign up / sign in with email+password via login modal
- [x] Session persists across page reloads, handles token refresh
- [x] Paper trading API calls use user JWT (not anon key)
- [x] All executor POST operations return 401 without valid JWT
- [x] Users cannot close positions they do not own
- [x] Rate limiting on executor POST: 10 req/min per user
- [x] Conditions with unrecognized indicators rejected
- [x] CORS restricted to known origins
- [x] Backtesting works without authentication
- [x] `Trade` type includes `direction`, `closeReason`
- [x] Backtest worker returns direction, close_reason, profit_factor, avg_win, avg_loss, buy_and_hold_return_pct
- [x] Strategy translator converts between all 3 condition formats
- [x] Existing backtest functionality unchanged (backward compatible)

---

#### Phase B: Chart Visuals + Table Improvements

Combines original Phases 3 + simplified Phase 4. TradingView Series Primitives for trade regions, plus enhancing the existing trade table (no new npm dependencies).

##### B.1: Enhanced Chart Trade Visuals

1. Create `frontend/src/components/chart/TradeRegionPrimitive.ts` — implements `ISeriesPrimitive`:
   - `updateAllViews()` — reuses pooled `TradeRegionPaneView` objects (not re-allocating per frame)
   - Each view draws: filled rectangle (green/red), connecting line entry→exit, P&L text label
   - Semi-transparent fill (alpha ~0.15) so candles remain visible
   - **Viewport culling** in renderer: skip trades outside visible time range (review todo 065)
   - Progressive opacity reduction when >20 trades visible

```typescript
// Object pooling pattern (review todo 065)
updateAllViews(): void {
  const needed = this._trades.length;
  while (this._paneViews.length > needed) this._paneViews.pop();
  for (let i = 0; i < needed; i++) {
    if (this._paneViews[i]) {
      this._paneViews[i].update(this._trades[i]);
    } else {
      this._paneViews.push(new TradeRegionPaneView(this._trades[i]));
    }
  }
}

// Viewport culling in renderer
draw(target: CanvasRenderingTarget2D): void {
  const visibleRange = this._source.chart.timeScale().getVisibleLogicalRange();
  if (!visibleRange) return;
  if (this._trade.exitLogical < visibleRange.from ||
      this._trade.entryLogical > visibleRange.to) return;
  // ... actual drawing
}
```

2. Update `TradingViewChart.tsx` (lines 498-523):
   - After setting markers, attach `TradeRegionPrimitive` to candle series
   - `useEffect` cleanup: `detachPrimitive()` before `attachPrimitive()` on re-render
   - Update BUY/SELL marker colors based on trade outcome (win → green, loss → red)

##### B.2: Enhanced Trade Table (No New Dependencies)

**Simplified approach** (review todo 062): Enhance the existing HTML table instead of adding TanStack Table.

1. In `App.tsx` results section (lines 340-380):
   - Remove `.slice(0, 20)` cap — show all trades with scrollable container (`overflow-y: auto; max-height: 400px`)
   - Add columns: Direction (LONG/SHORT badge), Close Reason (SL/TP/Signal/End tag), Hold Duration
   - Add `useState` for sort column + direction, `Array.sort()` for click-to-sort headers
   - Cumulative P&L column (already partially exists)

2. Extract equity curve from `App.tsx:110-134` into `frontend/src/components/backtest/EquityCurveChart.tsx` (pure refactor, no new functionality)

3. Update `BacktestResultsPanel.tsx` (compact sidebar):
   - Add direction badge and close reason tag to each trade row
   - Remove `.slice(0, 15)` cap, show all trades with scrolling

**Files to create:**
- `frontend/src/components/chart/TradeRegionPrimitive.ts`
- `frontend/src/components/backtest/EquityCurveChart.tsx`

**Files to modify:**
- `frontend/src/components/TradingViewChart.tsx` — attach primitive, update marker colors, cleanup on re-render
- `frontend/src/App.tsx` — uncap trade table, add columns, sortable headers, extract equity chart
- `frontend/src/components/BacktestResultsPanel.tsx` — add direction/closeReason, uncap

**Testing:**
- TradeRegionPrimitive: coordinate calculation, color logic, viewport culling, cleanup
- Trade table: renders all trades, sort works, direction/closeReason columns display correctly

**Acceptance criteria:**
- [x] Green shaded region between entry/exit bars for winning trades
- [x] Red shaded region between entry/exit bars for losing trades
- [x] Connecting line from entry price to exit price within each region
- [x] P&L label on each trade region showing dollar + percentage
- [x] BUY/SELL markers colored by trade outcome (not always green/red)
- [x] Regions semi-transparent (candles readable underneath)
- [x] Chart maintains 60fps with 100+ trades during pan/zoom (viewport culling)
- [x] Trade table shows ALL trades (not capped at 15-20) with scrolling
- [x] Direction and Close Reason columns visible in trade table
- [x] Click column header to sort
- [x] Works for both daily and intraday timeframes
- [x] Equity curve extracted to own component (EquityCurveChart.tsx)

---

#### Phase C: Paper Trading Deployment Bridge

Simplified from original Phase 5. Deploy button, confirmation modal (not full review screen), wire existing dashboard as tab.

**Tasks:**

1. Add "Deploy to Paper Trading" button in `StrategyBacktestPanel.tsx`:
   - Only visible after a backtest completes
   - If not authenticated: triggers login modal (from Phase A)
   - If authenticated: opens confirmation modal

2. Create confirmation modal (inline, not a separate component):
   - Shows: strategy name, entry/exit conditions summary, SL/TP values
   - Backtest summary: total return, win rate, sharpe ratio, max DD
   - "Confirm Deploy" and "Cancel" buttons
   - On confirm: POST to `paper-trading-executor` `/execute` endpoint using `strategyTranslator.toExecutorFormat()` + user JWT

3. Create `frontend/src/components/PaperTradingStatusWidget.tsx`:
   - Compact widget in Strategy panel sidebar
   - Shows: active strategies count, open positions count, current unrealized P&L
   - Polls GET `/summary` every 30 seconds (with `document.visibilityState` check — no polling in background tabs)
   - Click to navigate to Paper Trading tab
   - Only visible when authenticated

4. Wire `PaperTradingDashboard.tsx` as top-level tab in `App.tsx`:
   - Add `'paper-trading'` to `AppTab` type
   - Add "Paper Trading" button in tab navigation
   - Fix existing issues:
     - `bg-white` → `bg-gray-950` (dark theme consistency)
     - `className="p4"` → `className="p-4"` (typo)
     - Use `session.access_token` as Bearer token

**Files to create:**
- `frontend/src/components/PaperTradingStatusWidget.tsx`

**Files to modify:**
- `frontend/src/App.tsx` — add paper-trading tab, update AppTab type
- `frontend/src/components/StrategyBacktestPanel.tsx` — add deploy button + confirmation modal
- `frontend/src/components/PaperTradingDashboard.tsx` — dark theme, fix typo, use JWT

**Testing:**
- Deploy flow: button appears after backtest, login modal if unauthenticated, confirmation modal, POST succeeds
- Status widget: polls correctly, pauses in background, shows data
- Dashboard tab: renders, dark theme, JWT auth

**Acceptance criteria:**
- [x] "Deploy to Paper Trading" button appears after backtest completes
- [x] Confirmation modal shows strategy summary + backtest stats
- [x] Deploy requires confirmation (not one-click)
- [ ] Strategy config correctly translated to executor format via strategyTranslator
- [ ] Compact status widget shows active strategies/positions/P&L
- [x] Status widget pauses polling when tab is in background
- [x] Full Paper Trading tab in main navigation
- [x] Dashboard uses dark theme (matches rest of app)
- [x] All paper trading API calls use user JWT
- [x] Unauthenticated users see login modal when trying to deploy

---

## System-Wide Impact

### Interaction Graph

- **Backtest flow**: StrategyBacktestPanel → backtest-strategy EF → strategy-backtest-worker EF → response parsed by backtestService.ts → state flows to TradingViewChart (markers + primitives) and App.tsx (results section)
- **Deploy flow**: StrategyBacktestPanel → confirmation modal → strategyTranslator → paper-trading-executor EF → paper_trading_positions DB → PaperTradingDashboard (polling)
- **Auth flow**: AuthProvider wraps App → session state via useContext → JWT passed to EF calls → Supabase RLS enforces row-level access

### Error Propagation

- Backtest worker errors → caught by backtest-strategy → returned as error response → displayed in StrategyBacktestPanel
- Paper trading executor errors → returned as HTTP error → displayed in confirmation modal or dashboard
- Auth errors → session invalidation → login modal on next protected action
- Chart primitive errors → wrapped in try/catch, logged, primitive hidden (chart continues working)

### State Lifecycle Risks

- **Partial deploy**: If executor POST succeeds but frontend state update fails → strategy active but UI doesn't reflect it. Mitigate: dashboard polls independently.
- **Stale backtest data**: Old chart primitives must be fully cleaned up before applying new ones. Mitigate: `detachPrimitive()` in useEffect cleanup.
- **Auth token expiry**: JWT expires during paper trading session. Mitigate: AuthContext handles `TOKEN_REFRESHED` event, updates stored token.

### API Surface Parity

- `strategy-backtest-worker` response shape changes (additive: new fields). Existing callers unaffected.
- `paper-trading-executor` POST routes now require JWT auth (**breaking change for unauthenticated callers** — this is intentional security fix).
- `backtest-strategy` auth requirement removed (now allows anonymous — **breaking change** if anything depended on auth, but only the frontend calls it).
- `Trade` type extended (additive). Existing components continue to work.

### Integration Test Scenarios

1. **Full backtest → chart visual flow**: Run backtest → verify worker returns direction/closeReason → verify trade regions render with correct colors → verify P&L labels
2. **Backtest → deploy → monitor flow**: Run backtest → click deploy → login if needed → confirmation modal → confirm → executor creates positions → dashboard shows active strategy
3. **Auth-gated deploy**: Attempt deploy while unauthenticated → login modal → sign in → return to confirmation → deploy succeeds with JWT
4. **Executor auth enforcement**: POST without JWT → 401. POST with JWT but wrong user → cannot close other user's positions.
5. **Trade table completeness**: Run backtest with 50+ trades → all trades visible with scrolling → sort by P&L works → direction/closeReason columns display

## Dependencies & Risks

| Dependency | Risk | Mitigation |
|---|---|---|
| TradingView Series Primitives API | Canvas rendering quirks | Viewport culling + object pooling (todo 065). Start with simple rectangle, iterate. |
| Supabase Auth email provider | Requires Supabase dashboard config | Document setup steps; works with local Supabase for dev |
| strategy-backtest-worker changes | Deployed Edge Function must be updated | Deploy worker before frontend changes go live |
| Paper trading executor auth changes | Breaking change for unauthenticated callers | Intentional — fixes critical security vulnerability (todo 059) |
| Three-way condition format | Translation bugs | Canonical translator with unit tests (todo 061) |

## Success Metrics

- Backtest chart shows shaded trade regions with P&L labels for 100% of trades at 60fps
- Trade table displays ALL trades (not capped) with direction, closeReason, and sortable columns
- Paper trading deploy flow works end-to-end: backtest → confirm → deploy → monitor
- Auth sign-up/sign-in flow works for paper trading access
- Executor POST endpoints fully authenticated with rate limiting

## Scope Boundaries (Out of Scope)

Per brainstorm decisions + review simplification:
- Live TradeStation trading from React frontend (stays macOS-only)
- Shared indicator computation library (each system keeps its own)
- Real-time WebSocket streaming of paper trading positions (polling for v1)
- Mobile responsive design for paper trading dashboard
- OAuth providers or magic link (email/password only for v1)
- Short selling in backtest (long-only for now, `direction: 'long'` always)
- Calendar heatmap, monthly breakdown, drawdown chart, CSV export (deferred to v2 — review todo 062)
- TanStack Table, @uiwjs/react-heat-map (no new npm dependencies — review todo 062)
- Full-page review screen (simplified to confirmation modal — review todo 063)

## Review Findings Incorporated

| Todo | Finding | Resolution |
|---|---|---|
| 059 (P1) | Executor POST endpoints unauthenticated | Added to Phase A.2 — JWT auth + ownership checks |
| 060 (P1) | Backtest auth ambiguity | Added to Phase A.3 — make backtesting explicitly unauthenticated |
| 061 (P2) | Three-way condition format | Promoted translator to Phase A.5 |
| 062 (P2) | Phase 4 over-engineered | Aggressively simplified — enhance existing table, no new deps |
| 063 (P2) | Auth + deploy over-engineered | AuthContext + login modal, confirmation modal, keep status widget |
| 064 (P2) | Rate limiting + validation | Added to Phase A.2 |
| 065 (P2) | Chart primitive performance | Viewport culling + object pooling added to Phase B.1 |
| 066 (P3) | Missing test strategy | Testing subsection added per phase |
| 067 (P3) | Buy-and-hold in worker | Added to Phase A.4 — compute server-side, remove FastAPI calls |
| 068 (P3) | Token refresh + CORS | TOKEN_REFRESHED in AuthContext, CORS restriction in Phase A.2 |

## Sources & References

### Origin

- **Brainstorm document:** [docs/brainstorms/2026-03-01-backtest-visuals-paper-trading-pipeline-brainstorm.md](docs/brainstorms/2026-03-01-backtest-visuals-paper-trading-pipeline-brainstorm.md) — Key decisions carried forward: Full Pipeline approach, React-only paper trading, Review-then-deploy, Unified Trade type, Backend-first trade data

### Internal References

- Chart marker rendering: `frontend/src/components/TradingViewChart.tsx:498-523`
- Trade type definition: `frontend/src/types/strategyBacktest.ts:92-102`
- Backtest worker trade output: `supabase/functions/strategy-backtest-worker/index.ts:456-459`
- Backtest worker exit logic: `supabase/functions/strategy-backtest-worker/index.ts:448-464`
- Backtest strategy auth: `supabase/functions/backtest-strategy/index.ts:25-31`
- Paper trading executor: `supabase/functions/paper-trading-executor/index.ts` (1055 lines)
- Paper trading dashboard: `frontend/src/components/PaperTradingDashboard.tsx` (607 lines, not routed)
- App navigation: `frontend/src/App.tsx:87` (AppTab type)
- Backtest results section: `frontend/src/App.tsx:278-397`
- Compact results panel: `frontend/src/components/BacktestResultsPanel.tsx`
- Strategy panel: `frontend/src/components/StrategyBacktestPanel.tsx`
- Worker condition format: `supabase/functions/strategy-backtest-worker/index.ts:28-34`
- Executor condition format: `supabase/functions/paper-trading-executor/index.ts:117-127`

### External References

- TradingView Lightweight Charts Primitives: https://tradingview.github.io/lightweight-charts/docs/plugins/series-primitives
- Supabase Auth JS: https://supabase.com/docs/reference/javascript/auth-signinwithpassword

### Related Work

- PR #22: Strategy platform implementation (131 tests, foundation for this work)
- PR #23: macOS SwiftUI overhaul (all P1/P2 resolved)
- Review todos: 059-068 (created during technical review)
