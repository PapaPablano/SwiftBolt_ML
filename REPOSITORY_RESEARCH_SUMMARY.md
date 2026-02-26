# SwiftBolt ML Codebase Research Summary

**Date:** February 25, 2026
**Focus:** Technical indicators, strategy system, trading bot/execution, backtesting infrastructure

---

## Executive Summary

SwiftBolt ML has a **sophisticated technical analysis and strategy framework** with indicators already implemented, a nascent strategy builder system, and comprehensive backtesting infrastructure. However, **live trading execution is NOT implemented**—the platform is currently a research/analysis workstation with historical backtesting capabilities.

---

## 1. TECHNICAL INDICATORS & ANALYSIS

### Location: `/ml/src/features/`

#### Implemented Indicators

**TradingView-Validated Indicators** (`technical_indicators_tradingview.py`)
- **SuperTrend** (period=7, multiplier=2.0) - Wilder's smoothing
  - Validated against TradingView exports with <$14 average error
  - Generates trend direction and signal strength
- **KDJ (Stochastic)** (n=9, m1=5, m2=5) - EMA smoothing
  - K/D/J calculations with excellent match to TradingView (0.00-0.36 error)
- **ADX (Average Directional Index)** (period=14) - Wilder's smoothing
  - Directional movement calculation
- **ATR (Average True Range)** - Wilder's smoothing
  - Multiple periods supported (7, 14)
  - Normalized to percentage of close

**Adaptive SuperTrend AI** (`supertrend_ai.py`)
- K-means clustering for adaptive ATR multiplier selection
- Outputs signal confidence (0-10 score)
- Extracts detailed signal metadata: entry/exit prices, stops, targets
- Performance-adaptive moving average (perf_ama)
- Risk:reward ratio calculation (default 2.0)
- Returns:
  - Trend direction (bullish/bearish)
  - Trend duration (bars held)
  - Stop levels and target prices
  - Signal confidence per bar
  - Full signal history with metadata

**Technical Indicators in Feature Engineering**
- **Support/Resistance Detection** (`support_resistance_detector.py`)
  - Polynomial SR indicators
  - Logistic SR probability
  - SR correlation analysis
- **Regime Indicators** (`regime_indicators.py`, `market_regime.py`)
  - Market regime classification (trending, mean-reversion, consolidation)
  - Regime-aware feature engineering
- **Volatility Analysis** (`volatility_analysis.py`)
  - Multi-timeframe volatility
  - Volatility surface for options
- **Multi-Timeframe Features** (`multi_timeframe.py`, `timeframe_consensus.py`)
  - Cross-timeframe feature aggregation
  - Timeframe consensus scoring

### Where Indicators Are Used

1. **Feature Engineering Pipeline** - indicators fed into ML models
2. **Edge Functions** (Supabase) - `/chart` endpoint returns indicators + forecasts
3. **Frontend Charts** (React/TradingView Lightweight Charts)
   - Components: `IndicatorPanel.tsx`, `TechnicalIndicatorsViewModel.swift`
4. **Strategy Builder** - indicators selectable as entry/exit conditions

---

## 2. STRATEGY SYSTEM

### Architecture

**Database Schema** (`20260221100000_strategy_builder_v2.sql`)

```sql
strategy_user_strategies
  ├─ id (UUID)
  ├─ user_id (UUID) - multi-tenant RLS
  ├─ name, description
  ├─ config (JSONB) - entry/exit conditions, filters, parameters
  ├─ is_active (boolean)
  └─ created_at, updated_at

strategy_backtest_jobs
  ├─ id, user_id, strategy_id
  ├─ symbol, start_date, end_date
  ├─ parameters (JSONB)
  ├─ status ('pending'|'running'|'completed'|'failed'|'cancelled')
  ├─ result_id (FK to strategy_backtest_results)
  └─ timestamps (started_at, completed_at)

strategy_backtest_results
  ├─ id, job_id
  ├─ metrics (JSONB) - Sharpe, returns, win rate, etc.
  ├─ trades (JSONB) - [{ entry_date, exit_date, pnl, ... }]
  └─ equity_curve (JSONB) - [{time, value}, ...]
```

### Strategy Definition System

**Backend API** (`/backend/supabase/functions/strategies/index.ts`)
- CRUD operations on strategies
- Supports `POST /strategies` with config:
  ```json
  {
    "name": "SuperTrend Strategy",
    "description": "...",
    "config": {
      "entry_conditions": [{ type, name, operator, value, params }],
      "exit_conditions": [...],
      "filters": [...],
      "parameters": { "length": 10, "multiplier": 3.0 }
    },
    "is_active": true
  }
```

**Strategy UI** (`frontend/src/components/StrategyUI.tsx`)
- Create, edit, delete strategies
- Parameter editor (number, string, boolean types)
- Indicator selector with enable/disable
- Signal filter (buy/sell/both)
- Mock data with 2 example strategies:
  1. **SuperTrend Strategy** - trend following
  2. **RSI Oversold Strategy** - mean reversion

**What's Configured vs. What's Missing**

| Feature | Status | Details |
|---------|--------|---------|
| Strategy persistence | ✅ Implemented | Stored in Supabase, multi-tenant RLS |
| Parameter definition | ✅ Partial | UI supports basic types, no advanced constraints |
| Indicator selection | ✅ Partial | UI lists indicators, no validation against strategy type |
| Entry/exit conditions | ✅ Partial | Config schema exists, no builder UI yet |
| Signal generation | ⚠️ Framework only | Backtest framework exists, real-time signal not live |
| Live alerts | ❌ Missing | No real-time condition monitoring |

---

## 3. TRADING BOT / ORDER EXECUTION

### Status: **NOT IMPLEMENTED**

The codebase is **research-focused, not production-trading-focused**. There is:

- ❌ **No order execution code** - No Alpaca order placement
- ❌ **No live trading capability** - No position management
- ❌ **No paper trading** - No simulated live execution
- ❌ **No risk management** - No position sizing rules (framework exists but not enforced)
- ✅ **Backtest simulation** - Only historical/simulated trading

### Architecture Comments

The design intentionally separates:
1. **Data ingestion** - Alpaca → Supabase Edge Functions → Postgres
2. **ML forecasting** - Python ML pipeline (daily/intraday jobs)
3. **Analysis layer** - Frontend charts + strategy backtester
4. **Trading layer** - **NOT IMPLEMENTED**

Per `CLAUDE.md`: *"Client talks only to Edge Functions — never directly to Alpaca"*

This suggests a future trading layer would be:
- Supabase Edge Function for order submission
- Order state management in Postgres
- Position tracking tables
- Risk controls enforced pre-execution

---

## 4. UI FOR STRATEGY BUILDING

### Frontend Components

**React Dashboard** (`frontend/src/components/`)

| Component | Purpose | Status |
|-----------|---------|--------|
| `StrategyUI.tsx` | Main strategy manager | Implemented (mock data) |
| `StrategyBacktestPanel.tsx` | Backtest runner & results | Large file, partially implemented |
| `TradingViewChart.tsx` | Chart display | Implemented |
| `IndicatorPanel.tsx` | Indicator toggle/config | Implemented |
| `ChartWithIndicators.tsx` | Composite chart + indicators | Implemented |

**StrategyUI.tsx Features**
- Strategy list (left sidebar)
- Strategy details editor (center)
- Parameter editor (textbox, number, checkbox)
- Indicator selector (multi-select with enable/disable)
- Signal filter dropdown (Buy/Sell/Both)
- Status toggle (Active/Inactive)
- Mock backtest button (calls placeholder API)
- New strategy creation form

**StrategyBacktestPanel.tsx Features**
- Date range selector
- Backtest execution
- Results display: equity curve, trades, metrics
- Real-time updates placeholder
- Large component (70+ KB) suggesting comprehensive feature set

### SwiftUI Client

**macOS Client** (`client-macos/SwiftBoltML/`)

No dedicated strategy UI found in SwiftUI client. The client focuses on:
- Chart viewing (`ChartViewModel.swift`)
- Real-time forecasts (`ChartViewModel+RealtimeForecasts.swift`)
- Technical indicators (`TechnicalIndicatorsViewModel.swift`, `IndicatorsViewModel.swift`)
- Options analysis (`OptionsChainViewModel.swift`)
- Backtesting (`BacktestingViewModel.swift`)

**Implication:** Strategy building is web-only (React), not available in macOS app.

---

## 5. BACKTESTING INFRASTRUCTURE

### Comprehensive Walk-Forward Backtesting

**Location:** `/ml/src/backtesting/`, `/ml/src/testing/`

#### Walk-Forward Tester (`walk_forward_tester.py`)

- **Implements proper time-series backtesting with ZERO lookahead bias**
- **Horizon-aware window configuration**

Configuration for different horizons:
```python
HORIZON_WINDOWS = {
    "1D":  {"train": 126,  "test": 10,  "step": 2},   # 6mo train, 2wk test
    "1W":  {"train": 252,  "test": 25,  "step": 5},   # 1yr train, 5wk test
    "1M":  {"train": 504,  "test": 60,  "step": 20},  # 2yr train, 3mo test
    ...
}
```

**Key Metrics Calculated**
- **Classification metrics:** Accuracy, Precision, Recall, F1
- **Financial metrics:** Sharpe ratio, Sortino ratio, Max drawdown, Profit factor
- **Trade metrics:** Win rate, Avg win/loss, Total trades
- **Period tracking:** Test periods with start/end dates

**Features**
- Prevents lookahead bias (guards in `ml/src/features/lookahead_checks.py`)
- Per-window forecaster instantiation (no state leakage)
- Configurable train/test/step windows
- Returns `BacktestMetrics` dataclass with all results

#### Production Backtest Framework (`backtest_framework.py`)

- **Transaction cost modeling** - commission + slippage
- **Position sizing rules** - max 10% per position (configurable)
- **Realistic execution simulation** - applies slippage before position sizing
- **Trade logging** - entry/exit dates, prices, P&L, duration
- **Walk-forward optimization** - prevents overfitting
- **Equity curve tracking** - with daily returns

**Example Usage**
```python
framework = BacktestFramework()
result = framework.run_backtest(data, signal_generator)
print(result.summary())  # Sharpe, returns, win rate, max DD, etc.

# Walk-forward
results = framework.walk_forward_backtest(data, model_trainer, n_splits=5)
aggregated = framework.aggregate_walk_forward_results(results)
```

#### Backtest Engine for Options (`backtest_engine.py`)

- Specialized for options strategies
- Black-Scholes model integration
- Contract-level position tracking
- Performance metrics calculation
- Trade logging (entry, exit, P&L)

### Backtesting API Endpoint

**Router:** `/ml/api/routers/backtest.py`

- `POST /backtest-strategy` - Execute backtest synchronously
  - Input: symbol, strategy name, dates, timeframe, initial capital, params
  - Output: Results (trades, equity curve, metrics)
- `GET /strategy-backtest-results` - Fetch stored results by job ID
  - Backend expects Supabase tables: `strategy_backtest_jobs`, `strategy_backtest_results`

**Job Queue Support**
- Tables support queuing: status ('pending'|'running'|'completed'|'failed')
- Function `claim_pending_backtest_job()` for worker claiming
- Not actively used in current implementation

### Trade Logging

**TradeLogger** (`backtesting/trade_logger.py`)
- Records each trade: entry/exit price, date, size, P&L
- Exportable to DataFrame for analysis
- Integrated into backtest frameworks

---

## 6. WHAT'S ALREADY BUILT vs. WHAT'S MISSING

### Summary Table

| Area | Already Built | Missing |
|------|---------------|---------|
| **Indicators** | SuperTrend (adaptive), KDJ, ADX, ATR, Support/Resistance, Volatility, Regime | Simple MA/EMA (if needed) |
| **Strategy Definition** | Database schema, REST API, UI form builder, parameter config | Advanced condition builder, template library |
| **Backtesting** | Walk-forward (proper time-series), metrics, trade logging, equity curve | Paper trading, live simulation |
| **Signal Generation** | In-sample during backtest | Real-time live signals |
| **Live Trading** | **NONE** | Order execution, position tracking, risk management, order state mgmt |
| **Market Data** | Alpaca ingestion via Edge Functions | Direct real-time feed to strategy engine |
| **UI** | React strategy builder, chart display, indicator toggles | Strategy condition builder (visual drag-drop), live execution UI |
| **Monitoring** | Backtest metrics | Portfolio P&L, risk monitoring, alert system |

---

## 7. ARCHITECTURAL INSIGHTS

### Current Data Flow (Research Mode)

```
Alpaca
  ↓ (via Edge Function: ingest)
Supabase Postgres (ohlc_bars_v2, quotes)
  ↓ (Python ML job)
ML Pipeline (features → forecast)
  ↓
ml_forecasts table (daily/intraday)
  ↓ (Edge Function: /chart)
React/SwiftUI Clients
  ↓
User Views Charts + Indicators
```

### Where Strategy System Fits

```
Strategy Definition (UI) → Supabase
  ↓
Backtest Job Queue (strategy_backtest_jobs)
  ↓
Python Backtest Engine (historical replay)
  ↓
Backtest Results → Supabase (strategy_backtest_results)
  ↓
Frontend Results Display
```

### Future Live Trading Integration (Not Implemented)

Would need:
```
Live Signal Generator (from active strategy)
  ↓
Risk Check + Position Sizing
  ↓
Order Submission (Edge Function → Alpaca)
  ↓
Position Tracking Table
  ↓
P&L Monitoring + Risk Management
```

---

## 8. KEY FILES & LOCATIONS

### Core Strategy Infrastructure
- **DB Schema:** `/supabase/migrations/20260221100000_strategy_builder_v2.sql` (+ v2.1 fixes)
- **Backend API:** `/backend/supabase/functions/strategies/index.ts`
- **Frontend UI:** `/frontend/src/components/StrategyUI.tsx`, `StrategyBacktestPanel.tsx`

### Technical Indicators
- **TradingView Validated:** `/ml/src/features/technical_indicators_tradingview.py`
- **Adaptive SuperTrend:** `/ml/src/strategies/supertrend_ai.py`
- **Support/Resistance:** `/ml/src/features/support_resistance_detector.py`
- **Market Regime:** `/ml/src/features/market_regime.py`

### Backtesting
- **Walk-Forward Framework:** `/ml/src/backtesting/walk_forward_tester.py`
- **Production Framework:** `/ml/src/testing/backtest_framework.py`
- **Options Engine:** `/ml/src/backtesting/backtest_engine.py`
- **API Router:** `/ml/api/routers/backtest.py`

### Options Strategy (Advanced)
- **Options Strategy GA:** `/ml/src/options_strategy_ga.py` (genetic algorithm optimization)
- **Options Ranking:** `/ml/src/options_ranking_job.py`, `models/options_ranker.py`

---

## 9. NOTABLE PATTERNS & CONVENTIONS

### Backtesting Best Practices
1. **Walk-forward only** (no random splits) - enforced per CLAUDE.md
2. **Lookahead guards** (`STRICT_LOOKAHEAD_CHECK` env flag)
3. **Fresh forecaster per window** - prevents state leakage
4. **Horizon-aware config** - window sizes match forecast horizons

### Strategy Config Schema
```json
{
  "entry_conditions": [
    { "type": "indicator", "name": "supertrend", "operator": "crosses_above", "value": 0 }
  ],
  "exit_conditions": [
    { "type": "stop_loss", "value": -0.02 }
  ],
  "filters": [
    { "type": "regime", "name": "trending" }
  ],
  "parameters": { "length": 10 }
}
```

### Indicator Integration Points
1. **Features pipeline** - indicators as engineered features
2. **Chart endpoint** - includes indicators in response
3. **Strategy builder** - indicators as selectable conditions
4. **Real-time updates** - websocket for live indicator values

---

## 10. RECOMMENDATIONS FOR STRATEGY SYSTEM EXPANSION

### High-Priority Features

1. **Visual Condition Builder**
   - Drag-drop entry/exit condition assembly
   - Live chart preview showing signals
   - Use existing condition schema, add UI layer

2. **Real-Time Signal Generation**
   - Current: backtest-only signals
   - Needed: Run live conditions against real-time data
   - Architecture: Update strategy evaluation job (like `unified_forecast_job.py`)

3. **Paper Trading Simulator**
   - Extend `backtest_framework.py` to accept live data
   - Track simulated positions in Postgres
   - User can "paper trade" strategy before going live

4. **Strategy Template Library**
   - Pre-built strategies: Mean Reversion, Trend Following, Momentum
   - Configurable parameters per template
   - One-click activate

5. **Multi-Leg Strategy Support**
   - Already has tables (`multi_leg_*`), jobs (`multi_leg_options_ranking_trigger`)
   - Extend UI to support multi-leg condition combos

### Medium-Priority Features

6. **Strategy Backtester API Enhancement**
   - Currently accepts symbol + date range
   - Add: instrument type (stock/option), rolling backtest parameters
   - Return: detailed trade analysis, factor attribution

7. **Risk Management Enforcement**
   - Pre-built rules: max % drawdown, max % loss per trade, daily loss limit
   - Optional in strategy config
   - Enforced during backtest and (future) live trading

8. **Strategy Versioning**
   - Track config changes over time
   - Compare performance across versions
   - Rollback capability

### Low-Priority (Future)

9. **Machine Learning Strategy Optimizer**
   - Hyperparameter optimization (genetic algorithm already exists for options)
   - Could be applied to strategy parameters
   - Bayesian optimization for parameter search

10. **Live Order Execution** (Not in Roadmap Yet)
    - Alpaca order submission via Edge Function
    - Position tracking + P&L
    - Risk controls pre-execution

---

## 11. TESTING & VALIDATION

### Existing Test Coverage

- **ML Model Tests:** `/ml/tests/` - unit + integration tests
- **Backtesting Tests:** Walk-forward validation metrics validated against TradingView exports
- **Indicator Validation:** `validate_against_tradingview()` function in `technical_indicators_tradingview.py`

### Backtesting Validation

The codebase performs rigorous validation:
- **TradingView comparison** - SuperTrend, KDJ, ADX validated against exports
- **Walk-forward metrics** - accuracy, precision, recall, Sharpe, Sortino
- **Trade logging** - entry/exit prices, P&L, duration tracked
- **Error handling** - insufficient data, training failures logged

---

## Conclusion

**SwiftBolt ML has a robust foundation for a strategy research platform** with:
- ✅ Production-grade backtesting with walk-forward validation
- ✅ TradingView-validated technical indicators
- ✅ Strategy persistence and CRUD API
- ✅ Strategy UI form builder (React)
- ✅ Options analysis integration

**But is NOT ready for live trading** because:
- ❌ No order execution
- ❌ No position tracking
- ❌ No risk management enforcement
- ❌ No real-time signal generation

The **natural next step** would be to implement **paper trading** (extend backtest framework to live data) before attempting live order execution. This would allow users to validate strategies in simulated real-time before risking capital.
