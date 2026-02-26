# SwiftBolt ML Architecture Overview

---

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SWIFTBOLT ML ECOSYSTEM                              │
└─────────────────────────────────────────────────────────────────────────────┘

MARKET DATA LAYER
═════════════════════════════════════════════════════════════════════════════

    ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
    │   Alpaca     │         │  TradingView │         │   Options    │
    │  (Equities)  │         │   (Charts)   │         │   (Chains)   │
    └──────┬───────┘         └──────┬───────┘         └──────┬───────┘
           │                         │                         │
           └─────────────────────────┼─────────────────────────┘
                                    │
                    (Supabase Edge Functions)
                           /ingest/*
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  SUPABASE POSTGRES                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ohlc_bars_v2  ───┬──→  ml_forecasts  ───┬──→  forecast_validation_metrics│
│  (OHLCV Cache)    │    (Daily/1H/15m)    │     (Walk-forward Results)      │
│                   │                       │                                 │
│  quotes           │    options_ranks      │     strategy_user_strategies   │
│  (Price Ticks)    │    (Option Scores)    │     (Strategy Definitions)      │
│                   │                       │                                 │
│  options_snapshots│    watchlists/items   │     strategy_backtest_jobs     │
│                   │    (User Collections) │     (Backtest Queue)           │
│                   └──→                    │                                 │
│                                           └──→  strategy_backtest_results  │
│                                                (Backtest Results Storage)   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

ML PIPELINE LAYER
═════════════════════════════════════════════════════════════════════════════

    ┌──────────────────────────────────────────────────────────────┐
    │  Python ML Jobs (Daily/Intraday)                             │
    │                                                               │
    │  ┌────────────────────────────────────────────────────────┐  │
    │  │ unified_forecast_job.py / intraday_forecast_job.py     │  │
    │  │                                                        │  │
    │  │  1. Fetch OHLCV from Postgres                        │  │
    │  │  2. Engineer Features (Indicators)                   │  │
    │  │  3. Run Ensemble Models (LSTM+ARIMA-GARCH)           │  │
    │  │  4. Generate Forecasts (1D/5D/10D/20D)               │  │
    │  │  5. Write to ml_forecasts                            │  │
    │  │                                                        │  │
    │  │  Key Feature Computation:                            │  │
    │  │  ├─ Technical Indicators                             │  │
    │  │  │  ├─ SuperTrend (TradingView validated)            │  │
    │  │  │  ├─ KDJ / ADX / ATR                              │  │
    │  │  │  └─ Support/Resistance Detection                 │  │
    │  │  ├─ Market Regime Classification                     │  │
    │  │  ├─ Volatility Analysis                             │  │
    │  │  ├─ Multi-Timeframe Consensus                       │  │
    │  │  └─ Options Greeks Aggregation                       │  │
    │  │                                                        │  │
    │  │  Validation: Walk-Forward (NO lookahead bias)       │  │
    │  │  Evaluation: evaluation_job_daily.py                │  │
    │  └────────────────────────────────────────────────────────┘  │
    │                                                               │
    │  Outputs: ml_forecasts + forecast_validation_metrics       │
    └──────────────────────────────────────────────────────────────┘

STRATEGY LAYER
═════════════════════════════════════════════════════════════════════════════

    ┌──────────────────────────────────────┐  ┌──────────────────────────┐
    │  Strategy Builder & Repository       │  │  Backtesting Framework   │
    │                                      │  │                          │
    │  ┌─────────────────────────────────┐ │  │  ┌────────────────────┐  │
    │  │ Strategy Definition (JSONB)      │ │  │  │ Walk-Forward      │  │
    │  │                                   │ │  │  │ Validation        │  │
    │  │ - Entry Conditions               │ │  │  │                   │  │
    │  │ - Exit Conditions                │ │  │  │ Train/Test Split  │  │
    │  │ - Filters (Regime, ATR, etc.)    │ │  │  │ Zero Lookahead    │  │
    │  │ - Parameters                     │ │  │  │                   │  │
    │  └──────────────┬────────────────────┘ │  │  │ Metrics:          │  │
    │                 │                       │  │  │ - Sharpe/Sortino  │  │
    │  ┌──────────────▼────────────────────┐ │  │  │ - Max Drawdown    │  │
    │  │ Postgres Storage                  │ │  │  │ - Win Rate        │  │
    │  │ strategy_user_strategies          │ │  │  │ - Profit Factor   │  │
    │  │ strategy_backtest_jobs            │ │  │  │                   │  │
    │  │ strategy_backtest_results         │ │  │  │ Trade Logging     │  │
    │  └────────────────────────────────────┘ │  │  │ Equity Curve      │  │
    │                                          │  │  └────────────────────┘  │
    └──────────────────────────────────────────┘  └──────────────────────────┘

CLIENT LAYER
═════════════════════════════════════════════════════════════════════════════

    ┌──────────────────────────────┐     ┌──────────────────────────────┐
    │   React Web Dashboard        │     │   SwiftUI macOS Client       │
    │                              │     │                              │
    │  ┌────────────────────────┐  │     │  ┌────────────────────────┐  │
    │  │ StrategyUI Component   │  │     │  │ ChartViewModel         │  │
    │  │                        │  │     │  │ IndicatorsViewModel    │  │
    │  │ - Strategy list        │  │     │  │ OptionsChainViewModel  │  │
    │  │ - Parameter editor     │  │     │  │ BacktestingViewModel   │  │
    │  │ - Indicator selector   │  │     │  │ WalkForwardViewModel   │  │
    │  │ - Create/Edit/Delete   │  │     │  │ ValidationViewModel    │  │
    │  └────────────────────────┘  │     │  │ AnalysisViewModel      │  │
    │                              │     │  └────────────────────────┘  │
    │  ┌────────────────────────┐  │     │                              │
    │  │ StrategyBacktestPanel  │  │     │  Features:                   │
    │  │                        │  │     │  - Real-time charts          │
    │  │ - Date range selector  │  │     │  - Live forecasts            │
    │  │ - Backtest runner      │  │     │  - Options analysis          │
    │  │ - Results display      │  │     │  - Volatility surface        │
    │  │ - Equity curve chart   │  │     │  - Multi-leg options         │
    │  │ - Trades table         │  │     │  - Stress testing            │
    │  │ - Metrics summary      │  │     │  - News sentiment            │
    │  └────────────────────────┘  │     │                              │
    │                              │     │  ⚠️  NO strategy building UI  │
    │  ┌────────────────────────┐  │     │                              │
    │  │ TradingViewChart       │  │     │                              │
    │  │ IndicatorPanel         │  │     │                              │
    │  │ ChartWithIndicators    │  │     │                              │
    │  └────────────────────────┘  │     │                              │
    │                              │     │                              │
    │  Uses Lightweight Charts     │     │                              │
    │  + TradingView Lightweight   │     │  Xcode Project              │
    │                              │     │                              │
    └──────────────────────────────┘     └──────────────────────────────┘

API GATEWAY LAYER
═════════════════════════════════════════════════════════════════════════════

    ┌────────────────────────────────────────────────────────────────┐
    │  Supabase Edge Functions                                       │
    ├────────────────────────────────────────────────────────────────┤
    │                                                                 │
    │  GET  /chart              → OHLCV + indicators + forecasts    │
    │  POST /strategies         → Create/update/delete strategies   │
    │  GET  /strategies         → List user strategies              │
    │  POST /backtest-strategy  → Run backtest (async)              │
    │  GET  /strategy-backtest-results  → Fetch results by job_id  │
    │                                                                 │
    │  + 30+ other functions (options, quotes, watchlist, etc.)    │
    │                                                                 │
    └────────────────────────────────────────────────────────────────┘

NOT IMPLEMENTED (Future)
═════════════════════════════════════════════════════════════════════════════

    ❌ Live Order Execution
    ❌ Position Tracking
    ❌ Paper Trading
    ❌ Real-time Signal Generation
    ❌ Order State Management
    ❌ Risk Management Enforcement
    ❌ Portfolio Monitoring
```

---

## Data Flow Diagram: Strategy Backtest

```
User Creates Strategy
        │
        ▼
┌──────────────────────────┐
│ React StrategyUI.tsx     │
│ - Parameter editor       │
│ - Indicator selector     │
│ - Signal filter (Buy/All)│
└──────────────┬───────────┘
               │
               │ POST /strategies
               │
               ▼
┌──────────────────────────────────────────┐
│ Edge Function: strategies/index.ts       │
│ - Validate config                        │
│ - Insert into strategy_user_strategies   │
└──────────────┬───────────────────────────┘
               │
               │ Returns strategy ID
               │
               ▼
┌──────────────────────────────────────────┐
│ React StrategyBacktestPanel.tsx          │
│ - Select date range                      │
│ - Click "Backtest" button                │
└──────────────┬───────────────────────────┘
               │
               │ POST /backtest-strategy
               │ {symbol, start_date, end_date, params}
               │
               ▼
┌──────────────────────────────────────────┐
│ FastAPI Router: backtest.py              │
│ - run_backtest_endpoint()                │
│ - Call ml/scripts/run_backtest.py        │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│ Python Backtest Engine                                       │
│                                                              │
│ 1. Load historical OHLCV data                               │
│ 2. Initialize WalkForwardBacktester                         │
│ 3. For each train/test window:                              │
│    ├─ Extract training data (train_window bars)             │
│    ├─ Extract test data (test_window bars)                  │
│    ├─ Fresh forecaster instance (no state leak)             │
│    ├─ Train model on training data                          │
│    ├─ For each test bar:                                    │
│    │  ├─ Compute technical indicators                       │
│    │  │  ├─ SuperTrend (period=7, mult=2.0)                │
│    │  │  ├─ KDJ (n=9, m1=5, m2=5)                          │
│    │  │  ├─ ADX (period=14)                                │
│    │  │  └─ Support/Resistance detection                    │
│    │  ├─ Evaluate entry conditions                          │
│    │  ├─ Evaluate exit conditions                           │
│    │  ├─ Generate signal (BUY/SELL/HOLD)                    │
│    │  ├─ Apply position sizing (max 10%)                    │
│    │  ├─ Simulate execution (with slippage)                 │
│    │  ├─ Record trade (if entry/exit)                       │
│    │  └─ Update equity curve                                │
│    │                                                         │
│    ├─ Collect: predictions, actuals, returns               │
│    └─ Calculate window metrics                              │
│                                                              │
│ 4. Aggregate across all windows:                            │
│    ├─ Classification metrics (accuracy, precision, F1)      │
│    ├─ Financial metrics (Sharpe, Sortino, Max DD)           │
│    ├─ Trade stats (win rate, profit factor, avg win/loss)   │
│    ├─ Full trade log (entry/exit/P&L/duration)             │
│    └─ Equity curve time series                              │
│                                                              │
│ 5. Return BacktestMetrics dataclass                         │
└──────────────┬───────────────────────────────────────────────┘
               │
               │ Metrics + Trades + Equity Curve
               │
               ▼
┌──────────────────────────────────────────┐
│ Postgres Storage                         │
│ INSERT strategy_backtest_results:        │
│ {metrics JSONB, trades JSONB,            │
│  equity_curve JSONB}                     │
│                                          │
│ UPDATE strategy_backtest_jobs:           │
│ {status='completed', result_id=...}      │
└──────────────┬───────────────────────────┘
               │
               │ Fetch by job_id
               │
               ▼
┌──────────────────────────────────────────┐
│ React StrategyBacktestPanel              │
│ Display:                                 │
│ - Equity curve chart                     │
│ - Drawdown chart                         │
│ - Trades table (entry/exit/P&L)          │
│ - Metrics summary                        │
│   ├─ Sharpe: 1.45                        │
│   ├─ Sortino: 2.10                       │
│   ├─ Max DD: -18%                        │
│   ├─ Win Rate: 55%                       │
│   ├─ Profit Factor: 1.8                  │
│   └─ Total Trades: 127                   │
└──────────────────────────────────────────┘
```

---

## Feature Engineering Pipeline

```
OHLCV Data (Postgres: ohlc_bars_v2)
│
├─ Compute Technical Indicators
│  ├─ TradingView-Validated
│  │  ├─ SuperTrend (period=7, mult=2.0)
│  │  ├─ KDJ (n=9, m1=5, m2=5)
│  │  ├─ ADX (period=14)
│  │  └─ ATR (period=14)
│  │
│  ├─ Adaptive SuperTrend
│  │  ├─ Test factors 1.0-5.0
│  │  ├─ K-means cluster performance
│  │  └─ Select best cluster mean
│  │
│  └─ Custom Indicators
│     ├─ Support/Resistance (pivot detection)
│     ├─ SR Probability (logistic/polynomial)
│     ├─ Market Regime (trending/mean-reversion)
│     └─ Volatility Surface (options)
│
├─ Multi-Timeframe Features
│  ├─ Aggregate 1m, 5m, 15m, 1h, 4h, 1d
│  ├─ Cross-timeframe consensus
│  └─ Regime alignment
│
├─ Feature Caching
│  ├─ Redis (optional, if enabled)
│  └─ Database fallback
│
├─ Lookahead Bias Guards
│  ├─ STRICT_LOOKAHEAD_CHECK=1 enables
│  └─ Validates no future data used
│
└─ Output Feature Vector
   → Passed to ML models (LSTM, ARIMA-GARCH, XGBoost, TabPFN)
   → Ensemble combines models → Forecast
   → Forecast stored in ml_forecasts
```

---

## Indicator Output Example

```
┌─ SuperTrend Calculation ─────────────────────────────────────┐
│                                                               │
│  Input: OHLCV DataFrame                                      │
│  ├─ open, high, low, close, volume                          │
│  └─ timestamp                                                │
│                                                               │
│  Step 1: Calculate ATR                                       │
│  ├─ True Range = max(H-L, abs(H-C[t-1]), abs(L-C[t-1]))    │
│  └─ ATR = EMA(TR, period=10)                                │
│                                                               │
│  Step 2: Calculate Bands                                     │
│  ├─ HL2 = (H + L) / 2                                       │
│  ├─ Upper = HL2 + (ATR * factor)                            │
│  └─ Lower = HL2 - (ATR * factor)                            │
│                                                               │
│  Step 3: SuperTrend Logic                                    │
│  ├─ Final Upper = min(Upper, Final_Upper[t-1]) if C[t-1]>FU│
│  ├─ Final Lower = max(Lower, Final_Lower[t-1]) if C[t-1]<FL│
│  └─ SuperTrend = Final_Lower if trend=UP, else Final_Upper │
│                                                               │
│  Step 4: K-means Clustering (Adaptive SuperTrend)            │
│  ├─ Test factors: [1.0, 1.5, 2.0, 2.5, 3.0, ...]           │
│  ├─ Calculate performance for each                          │
│  └─ K-means (k=3) → Best/Average/Worst clusters            │
│  └─ Select mean of Best cluster                             │
│                                                               │
│  Output DataFrame Columns:                                  │
│  ├─ supertrend (price level)                                │
│  ├─ supertrend_trend (1=up, 0=down)                        │
│  ├─ supertrend_signal (1=BUY, -1=SELL, 0=no change)       │
│  ├─ signal_confidence (0-10)                               │
│  ├─ perf_ama (performance-adaptive MA)                      │
│  ├─ target_factor (optimal ATR mult)                        │
│  └─ atr (Average True Range)                                │
│                                                               │
│  Output Info Dict:                                          │
│  ├─ current_trend ("BULLISH" or "BEARISH")                 │
│  ├─ current_stop_level (price)                             │
│  ├─ trend_duration_bars (bars held)                        │
│  ├─ signals (array of signal metadata):                    │
│  │  ├─ date, type, price, confidence                       │
│  │  ├─ stop_level, target_price, risk/reward               │
│  │  └─ atr_at_signal                                       │
│  └─ signal_strength (0-10 score)                           │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## Key Integration Points

### 1. Forecast → Strategy Evaluation
```
ml_forecasts (LSTM+ARIMA ensemble)
    ↓
Strategy condition evaluates:
    ├─ If forecast.direction = 'bullish' AND supertrend_signal = 1
    ├─ AND market_regime = 'trending'
    └─ → ENTRY SIGNAL
```

### 2. Backtest → Live Integration (Future)
```
Current (Backtest Only):
  Historical Data → Indicators → Strategy Evaluation → Trades

Future (Paper/Live):
  Live Data Stream
    ├─ Push to Postgres (realtime table)
    ├─ Trigger indicator computation
    ├─ Evaluate active strategies
    ├─ Generate signals
    ├─ (Paper): Simulate execution
    ├─ (Live): Submit orders via Edge Function
    └─ Track positions & P&L
```

### 3. Multi-Tenant Architecture
```
All tables with user_id column have RLS policies:
  ├─ SELECT: WHERE auth.uid() = user_id
  ├─ INSERT: WITH CHECK auth.uid() = user_id
  ├─ UPDATE: USING auth.uid() = user_id
  └─ DELETE: USING auth.uid() = user_id

Ensures:
  - Users see only their own strategies
  - Users see only their own backtest results
  - No cross-user data leakage
```

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React + TypeScript + Tailwind CSS, SwiftUI |
| **Charts** | TradingView Lightweight Charts |
| **Backend** | Supabase (Postgres + Edge Functions) |
| **ML** | Python (NumPy, Pandas, Scikit-learn, PyTorch) |
| **ML Models** | LSTM, ARIMA-GARCH, XGBoost, TabPFN, TabPFN-Ensemble |
| **Database** | PostgreSQL + RLS policies |
| **APIs** | Alpaca (data), Finnhub (sentiment), Databento (alternative) |
| **Deployment** | Docker, Supabase Functions (Deno), FastAPI |
| **Testing** | pytest, pytest-cov, TradingView validation |

---

## Performance Characteristics

### Backtesting Speed
- **1 year of daily data:** ~5-10 seconds (walk-forward)
- **5 years of daily data:** ~30-60 seconds (15 windows)
- **Intraday (15m, 1000 bars):** ~2-5 seconds

### Database Queries
- Strategy CRUD: <100ms
- Backtest job claim: <50ms
- Forecast fetch: <200ms (with indicators)

### Indicator Computation
- SuperTrend (1000 bars): ~10ms
- KDJ (1000 bars): ~5ms
- ADX (1000 bars): ~8ms
- Regime detection (1000 bars): ~15ms

---

## Scalability Notes

### Current Limits
- Single Postgres instance (Supabase cloud)
- In-memory backtesting (fits single machine)
- No distributed computing

### For Scale (Future)
- Add connection pooling (PgBouncer)
- Horizontal scaling: queue-based worker pattern
- Distributed backtesting: Ray or Dask
- Time-series database (TimescaleDB) for 100M+ rows

---

## Summary

SwiftBolt ML implements a **complete research-to-backtest pipeline** with:
- ✅ Production-grade indicators (TradingView-validated)
- ✅ Sophisticated feature engineering
- ✅ ML ensemble forecasting
- ✅ Strategy definition & persistence
- ✅ Walk-forward backtesting (zero lookahead bias)
- ✅ Multi-tenant web & desktop UIs

But **lacks**:
- ❌ Live signal generation
- ❌ Order execution
- ❌ Position tracking
- ❌ Real-time portfolio monitoring

**Natural next step:** Paper trading simulation, not live execution.
