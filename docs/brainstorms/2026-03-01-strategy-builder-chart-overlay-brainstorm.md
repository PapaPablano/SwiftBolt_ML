# Brainstorm: Strategy Builder with Chart Overlay Integration

**Date:** 2026-03-01
**Status:** Ready for planning

## What We're Building

A unified strategy builder experience in the macOS Swift app where:

1. **Strategy conditions** (entry/exit rules based on technicals) are configured in a dedicated Strategy tab
2. **Backtesting** runs against real backend (Supabase edge functions), not mock data
3. **Backtest results** overlay directly onto the **main chart** — entry/exit markers + equity curve — just like ML forecasts do today
4. **Trade log** with full per-trade detail (entry/exit price, P&L, duration) + summary stats (win rate, max drawdown, Sharpe)
5. **Strategies persist** to Supabase (`strategy_user_strategies` table) so they survive restarts and can drive paper trading

## Why This Approach

**Native Swift wired to real backend** was chosen over bundling the React frontend because:

- The native `IntegratedStrategyBuilder` already has live indicator integration (30+ indicators via `UnifiedIndicatorsService`) — richer than the React version
- `ChartBridge` already supports `setBacktestTrades()` for drawing markers on the main chart — the overlay pipeline exists
- A single chart instance shared across tabs is trivial in native SwiftUI but complex when mixing WKWebView + native
- Avoids two rendering engines on the same screen
- No dev server or build bundling complexity

## Key Decisions

1. **Single chart, overlays only** — No separate backtest chart. Entry/exit markers and equity curve render as overlays on the main `WebChartView` candlestick chart, exactly like forecasts do today.

2. **Separate tab, shared chart** — Strategy builder is its own tab in the app. The chart instance is shared, so overlays persist when switching between tabs (Charts <-> Strategies).

3. **Native Swift UI, real backend** — Use the existing `IntegratedStrategyBuilder` condition picker UI. Wire it to Supabase edge functions (`strategies` for CRUD, `backtest-strategy` for job submission/polling).

4. **Supabase persistence** — Strategies save to `strategy_user_strategies` table via the existing `strategies` edge function. Enables future paper trading deployment from the Swift app.

5. **Condition format normalization** — The Swift `StrategyCondition` model (freeform strings like "above", "crosses_above") must be normalized to match the Supabase/React schema (typed operators: `>`, `<`, `cross_up`, `cross_down` and 47 `ConditionType` values).

6. **Full trade log** — Scrollable table of individual trades with entry/exit price, date, quantity, P&L, holding period. Plus summary stats: total return, win rate, max drawdown, number of trades.

## What Exists Today

### Working
- `ChartBridge.setBacktestTrades()` — sends trade data to chart.js for buy/sell markers
- `IntegratedStrategyBuilder` — native condition picker with 30+ indicators, live signals, category presets
- `backtest-strategy` edge function — real backtesting with job queue + worker
- `strategies` edge function — full CRUD for strategy persistence
- `chart.js` — Lightweight Charts with marker support

### Broken / Missing
- **No persistence** — `StrategyBuilderViewModel.saveStrategy()` is in-memory only
- **No real backtesting** — Native builder uses `BacktestResult.mock()` hardcoded data
- **No auth context** — Native builder has no JWT for edge function calls
- **Condition format mismatch** — Swift uses freeform strings, backend expects typed enums
- **No equity curve overlay** — `chart.js` draws trade markers but has no equity line series
- **No trade log view** — No SwiftUI table for per-trade backtest results

## Scope

### In Scope
- Wire `IntegratedStrategyBuilder` to `strategies` edge function (CRUD)
- Add auth/JWT to native strategy builder calls
- Normalize condition format (Swift <-> Supabase schema)
- Wire backtest submission to `backtest-strategy` edge function with polling
- Add equity curve line series to `chart.js` overlay system
- Build SwiftUI trade log table with summary stats
- Share chart instance across tabs so overlays persist

### Out of Scope
- Paper trading deployment from Swift (future follow-up)
- New indicators beyond existing 30+
- React frontend changes
- Real-time trade execution
- TradeStation integration (`TSStrategy` system)

## Open Questions

_None — all questions resolved during brainstorm._

## Resolved Questions

1. **Architecture direction?** — Native Swift wired to real backend (not embedded React)
2. **Where does the builder UI live?** — Separate tab, shares the same chart instance
3. **What chart overlays?** — Entry/exit markers + equity curve
4. **Trade log needed?** — Yes, full per-trade table + summary stats
5. **Persistence?** — Supabase via existing edge functions
