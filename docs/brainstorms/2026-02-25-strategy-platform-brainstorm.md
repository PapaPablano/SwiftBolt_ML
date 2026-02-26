# Strategy Platform with Visual Builder & Autonomous Bot
**Date:** 2026-02-25
**Status:** Brainstorm Complete

---

## What We're Building

An integrated **strategy trading platform** where analysts can:
1. **Build trading strategies visually** using a forms-based + visual hybrid UI
2. **Select from 30-40 technical indicators** (bullish/bearish, trend, momentum, volatility)
3. **Backtest strategies** against historical data with walk-forward validation
4. **Paper trade strategies** with real-time data to validate in live conditions
5. **Deploy as autonomous bots** that execute and continuously learn

**Out of scope (v2+):** Live money trading, parameter optimization engine, multi-strategy allocation

---

## Why This Approach

**Start with the interface.** A visual strategy builder is the hardest piece to get right UI-wise, and it's foundational. Without it, traders can't express their ideas.

**Validate before execution.** Paper trading lets you prove strategies work in live market conditions without risking capital. This is where most trading systems fail—they work on historical data but blow up live. We're building the safety net first.

**Keep strategies independent from ML forecasts.** SwiftBolt's ML models and indicator-based strategies will co-exist on the same chart but don't interfere. Analysts can objectively compare which approach works better for each symbol.

---

## Key Decisions

### 1. **MVP includes: Strategy Builder + Backtesting + Paper Trading**
- ✅ Analyst can build, validate, and simulate without risk
- ❌ Live money trading (v2)
- ❌ Auto-learning/parameter optimization (v2)

### 2. **30-40 Indicators (Extended Set)**
- Core: SuperTrend, RSI, MACD, KDJ, ADX, ATR, Bollinger Bands, Moving Averages, Stochastic
- Advanced: Support/Resistance, Market Regime, Volatility Profile, Ichimoku, CCI, DMI, ROC, Keltner Channel, Donchian Channel, etc.
- Organized by category (Trend, Momentum, Volatility, Volume, Pattern) in the menu

### 3. **Hybrid Condition Builder UX**
- **Primary:** Structured forms for easy editing (Condition A: indicator = RSI, value > 70, cross direction)
- **Secondary:** Visual preview showing AND/OR logic flow and condition hierarchy
- Works on mobile, intuitive for non-programmers, flexible for complex strategies

### 4. **Backtesting Engine: Walk-Forward Validation**
- Extend existing evaluation pipeline to support custom strategies
- Full metrics: Sharpe ratio, Sortino, Max Drawdown, Win Rate, Profit Factor, trade log
- Prevent lookahead bias (use existing STRICT_LOOKAHEAD_CHECK framework)

### 5. **Paper Trading Architecture**
- Use existing backtesting/evaluation framework but run on **real-time market data** instead of historical
- Store simulated trades in separate table: `paper_trading_trades`
- Compare paper trade P&L vs. real P&L to prove strategies are valid before live deployment

### 6. **Strategies are Separate from ML Forecasts**
- Each has its own data pipeline and visualization
- Strategies reference only indicators (prices, technical analysis)
- ML forecasts remain independent predictions
- Both visible on same chart for comparison (analyst chooses which to follow)

### 7. **Continuous Learning (v2 foundation)**
- Set up architecture now to support parameter tuning later
- Bot learns: indicator thresholds, entry/exit timing delays, position sizing
- Not in MVP but design DB schema to capture learnable parameters

---

## Data Model Sketch

**New tables (MVP):**
- `user_strategy_conditions` — Detailed condition definitions (indicator, operator, value, AND/OR logic)
- `paper_trading_positions` — Open positions in paper trading
- `paper_trading_trades` — Closed trades with entry/exit prices, P&L
- `strategy_execution_log` — When/how strategies were triggered
- `strategy_performance_metrics` — Backtest + paper trading stats per strategy/symbol/timeframe

---

## Resolved Questions

1. **Primary focus:** Visual builder UI (✓)
2. **Self-sustaining meaning:** Autonomous + continuously learning + profitable (✓)
3. **Execution path:** Paper trading first, live trading v2 (✓)
4. **ML integration:** Separate parallel systems, not entangled (✓)
5. **Indicator scope:** 30-40 indicators organized by category (✓)
6. **Condition builder UX:** Hybrid forms + visual (✓)
7. **Learning mechanism:** Parameter tuning + timing optimization (v2) (✓)
8. **MVP scope:** Builder + backtester + paper trader (✓)

---

## Resolved Questions (from brainstorm dialogue)

1. **UI Library:** Custom hybrid component that blends form controls with logical diagram (✓)
2. **Signal Display:** Overlay on chart as green/red markers on candles (✓)
3. **Strategy Refresh:** Auto on every candle close to keep signals current (✓)
4. **Risk Management:** Basic v1 (fixed position size, stop loss), advanced hedging in v2 (✓)

---

## Next Steps

✅ Brainstorm complete. Ready for planning phase.

**Recommended:** Run `/workflows:plan` to detail:
1. Architecture for condition builder (forms + visual layer)
2. Database schema for strategies and paper trading
3. Integration with existing backtesting/evaluation pipeline
4. Paper trading real-time execution loop
5. UI mockups and component breakdown (React + SwiftUI)
