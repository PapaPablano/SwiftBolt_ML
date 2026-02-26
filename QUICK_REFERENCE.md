# SwiftBolt ML Strategy System - Quick Reference

**Last Updated:** February 25, 2026

---

## What's Already Built

### Technical Indicators ✅
- **SuperTrend** (adaptive + TradingView-validated)
- **KDJ (Stochastic)** - K, D, J lines
- **ADX** - Directional movement
- **ATR** - Volatility measurement
- **Support/Resistance** - Pivot detection + probability
- **Market Regime** - Trending/mean-reversion classification
- **Volatility Surface** - For options analysis

### Strategy System ✅
- **Database** - `strategy_user_strategies`, `strategy_backtest_jobs`, `strategy_backtest_results`
- **REST API** - CRUD for strategies (Supabase Edge Function)
- **React UI** - `StrategyUI.tsx` - create/edit strategies with parameter editor
- **Backtest Panel** - `StrategyBacktestPanel.tsx` - run backtests, view results

### Backtesting Framework ✅
- **Walk-Forward** - Time-series only (no lookahead bias)
- **Metrics** - Sharpe, Sortino, Max Drawdown, Win Rate, Profit Factor
- **Trade Logging** - Entry/exit, P&L, duration tracking
- **Equity Curve** - Full daily tracking
- **Transaction Costs** - Commission + slippage modeling

---

## What's Missing (Not Critical Path)

| Feature | Impact | Effort |
|---------|--------|--------|
| Real-time Signal Generation | High | Medium |
| Live Order Execution | High | High |
| Paper Trading Simulator | Medium | Low |
| Visual Strategy Builder | Medium | Medium |
| Strategy Template Library | Low | Low |
| Multi-leg Strategy UI | Low | Medium |

---

## Key File Locations

### Database
```
/supabase/migrations/20260221100000_strategy_builder_v2.sql
```

### Backend API
```
/backend/supabase/functions/strategies/index.ts
```

### Frontend
```
/frontend/src/components/StrategyUI.tsx
/frontend/src/components/StrategyBacktestPanel.tsx
```

### Python Backtesting
```
/ml/src/backtesting/walk_forward_tester.py
/ml/src/testing/backtest_framework.py
/ml/src/backtesting/backtest_engine.py
```

### Indicators
```
/ml/src/features/technical_indicators_tradingview.py
/ml/src/strategies/supertrend_ai.py
/ml/src/features/support_resistance_detector.py
```

### API Router
```
/ml/api/routers/backtest.py
```

---

## Data Flow

```
User Strategy Definition
    ↓
strategy_user_strategies (Postgres)
    ↓
[Backtest Request]
    ↓
Python: Walk-Forward Engine
  ├─ Load historical OHLCV
  ├─ Compute indicators (TradingView-validated)
  ├─ Evaluate conditions (entry/exit)
  ├─ Simulate trades (with costs)
  └─ Calculate metrics
    ↓
strategy_backtest_results (Postgres)
    ↓
React Frontend: Display Results
```

---

## API Endpoints

### Strategies CRUD
```
GET    /strategies              → List all
GET    /strategies?id=xxx       → Get one
POST   /strategies              → Create
PUT    /strategies?id=xxx       → Update
DELETE /strategies?id=xxx       → Delete
POST   /strategies?action=duplicate → Clone
```

### Backtesting
```
POST   /backtest-strategy          → Run backtest
GET    /strategy-backtest-results?job_id=xxx → Get results
```

---

## Strategy Config Schema

```json
{
  "entry_conditions": [
    {
      "type": "indicator",
      "name": "supertrend",
      "operator": "crosses_above",
      "params": { "length": 10, "multiplier": 3.0 }
    }
  ],
  "exit_conditions": [
    {
      "type": "stop_loss",
      "value": -0.02
    }
  ],
  "filters": [
    {
      "type": "regime",
      "name": "trending"
    }
  ],
  "parameters": {
    "length": 10,
    "multiplier": 3.0
  }
}
```

---

## Indicator Parameters (TradingView Defaults)

| Indicator | Period | Multiplier | Parameters |
|-----------|--------|-----------|------------|
| SuperTrend | 7 | 2.0 | Wilder's smoothing |
| KDJ | n=9 | m1=5, m2=5 | EMA smoothing |
| ADX | 14 | - | Wilder's smoothing |
| ATR | 14 | - | Wilder's smoothing |

---

## Backtest Metrics Returned

```python
{
    "accuracy": 0.62,              # Classification accuracy
    "precision": 0.61,             # Weighted
    "recall": 0.62,                # Weighted
    "f1_score": 0.61,              # Weighted

    "sharpe_ratio": 1.45,          # Annualized
    "sortino_ratio": 2.10,         # Downside volatility
    "max_drawdown": -0.18,         # 18% max loss
    "win_rate": 0.55,              # 55% winning trades
    "profit_factor": 1.8,          # Gross profit / gross loss

    "total_trades": 127,
    "winning_trades": 70,
    "losing_trades": 57,
    "avg_win_size": 0.025,         # 2.5%
    "avg_loss_size": 0.015,        # 1.5%

    "start_date": "2023-01-01",
    "end_date": "2026-02-25",
    "test_periods": 15             # Walk-forward windows
}
```

---

## Backtest Engine Features

- ✅ Walk-forward validation (zero lookahead bias)
- ✅ Transaction costs (commission + slippage)
- ✅ Position sizing (max % per position)
- ✅ Trade logging (full history)
- ✅ Equity curve tracking
- ✅ Metrics calculation (financial + classification)
- ❌ Multi-leg strategies (schema exists, not in backtest)
- ❌ Portfolio optimization
- ❌ Real-time execution

---

## SuperTrend AI Output

The adaptive SuperTrend indicator returns:

```json
{
  "dataframe_columns": [
    "supertrend",              // Support/resistance level
    "supertrend_trend",        // 1 = bullish, 0 = bearish
    "perf_ama",               // Performance-adaptive MA
    "target_factor",          // Optimal ATR multiplier
    "atr",                    // Average True Range
    "supertrend_signal",      // 1 = BUY, -1 = SELL, 0 = HOLD
    "signal_confidence"       // 0-10 confidence score
  ],
  "info": {
    "target_factor": 2.5,
    "performance_index": 0.75,
    "signal_strength": 7,     // 0-10
    "current_trend": "BULLISH",
    "current_stop_level": 150.25,
    "trend_duration_bars": 42,
    "signals": [              // Historical signals with metadata
      {
        "date": "2026-02-25T10:30:00",
        "type": "BUY",
        "price": 151.50,
        "confidence": 8,
        "stop_level": 150.25,
        "target_price": 154.00,
        "atr_at_signal": 1.75,
        "risk_amount": 1.25,
        "reward_amount": 2.50
      }
    ]
  }
}
```

---

## Current State Assessment

### For Research & Backtesting: ⭐⭐⭐⭐⭐
- Production-ready indicators
- Comprehensive backtesting framework
- Multi-timeframe support
- Options analysis integrated

### For Live Trading: ❌ Not Ready
- No order execution
- No position tracking
- No real-time signal generation
- No risk enforcement

### For Strategy Development: ⭐⭐⭐⭐
- Good UI for parameter exploration
- Strong backtesting infrastructure
- Indicator library available
- Missing: visual condition builder

---

## Next Steps (Priority Order)

1. **Paper Trading** (Low effort, high value)
   - Extend backtest framework to accept live data
   - Track simulated positions
   - Compare live performance vs. backtest

2. **Visual Condition Builder** (Medium effort)
   - Drag-drop UI for entry/exit conditions
   - Live chart preview showing signals
   - Use existing condition schema, add frontend

3. **Real-Time Signal Generation** (Medium effort)
   - Parallel indicator calculation job
   - Evaluate active strategy conditions
   - Send alerts when conditions met

4. **Live Order Execution** (High effort, future)
   - Alpaca API integration
   - Order state management
   - Position P&L tracking
   - Pre-execution risk checks

---

## Testing Strategy

### Current Validation
- Indicators validated against TradingView exports
- Walk-forward metrics calculated with proper time-ordering
- Trade logging verified (entry/exit tracked)

### Recommended Before Going Live
- Paper trade 30+ days
- Validate signals match backtest conditions
- Monitor drawdown vs. forecast
- Test risk management rules

---

## Environment Variables

```bash
# Core
SUPABASE_URL=https://...
SUPABASE_SERVICE_KEY=...
ALPACA_API_KEY=...
ALPACA_API_SECRET=...

# ML Config
USE_UNIFIED_FORECAST=true
USE_SEPARATE_EVALUATIONS=true
STRICT_LOOKAHEAD_CHECK=0  # Set to 1 for safety checks

# Features
ENABLE_ADAPTIVE_SUPERTREND=true
ADAPTIVE_ST_METRIC_OBJECTIVE=sharpe
ADAPTIVE_ST_MIN_BARS=60
```

---

## Troubleshooting

### Backtest Returns No Results
- Check: Sufficient data? (need train_window + test_window + buffer)
- Check: Date range valid? (start_date < end_date)
- Check: Indicators computed? (lookahead guards may reject)

### Strategy Config Rejected
- Ensure: entry_conditions array not empty
- Ensure: operators are valid strings
- Ensure: parameters match indicator signatures

### Indicator Values Unexpected
- Verify: Using TradingView parameter defaults
- Compare: Against TradingView exports
- Check: Data quality (NaNs, gaps)

---

## Documentation Files Created

This research session generated:

1. **REPOSITORY_RESEARCH_SUMMARY.md** (This Directory)
   - Comprehensive overview
   - What's built vs. missing
   - Architectural insights
   - Recommendations for expansion

2. **STRATEGY_SYSTEM_TECHNICAL_GUIDE.md** (This Directory)
   - Code paths and file locations
   - API specifications
   - Data structures
   - Integration points
   - End-to-end execution flow

3. **QUICK_REFERENCE.md** (This File)
   - At-a-glance summary
   - Key locations
   - API endpoints
   - Configuration
   - Troubleshooting

---

## Key Takeaway

**SwiftBolt ML is a sophisticated research platform with production-grade backtesting and technical analysis. It's not a trading platform yet—it's a strategy validation platform.**

The next logical step is **paper trading**, not live execution. This lets users validate strategies in simulated real-time before risking capital.
