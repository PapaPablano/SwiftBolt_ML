# ML Blueprint: Stock Price Prediction Pipeline

## Overview

This document describes the complete ML pipeline for stock price prediction in SwiftBolt ML, from data ingestion to UI display.

---

## 1. Data Sources

### Primary Data: OHLC Bars
| Source | Provider | Data Type | Timeframes |
|--------|----------|-----------|------------|
| Polygon.io (via Massive) | `massive-client.ts` | Historical OHLC | m15, h1, d1, w1 |
| Finnhub | `finnhub-client.ts` | Real-time quotes | Intraday |

### Data Flow
```
Polygon API → chart Edge Function → ohlc_bars table → ML Scripts
```

### Database Tables
| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `symbols` | Symbol registry | id, ticker, asset_type |
| `ohlc_bars` | Price history | symbol_id, timeframe, ts, open, high, low, close, volume |
| `ml_forecasts` | ML predictions | symbol_id, horizon, overall_label, confidence, points |
| `supertrend_signals` | Buy/sell signals | symbol, signal_date, signal_type, entry_price, stop_level |
| `job_queue` | Async job processing | job_type, symbol, status, payload |

---

## 2. Feature Engineering

### Script: `ml/src/features/technical_indicators.py`

**Function:** `add_technical_features(df)`

### Features Computed (20+ indicators)

| Category | Indicators | Formula/Period |
|----------|------------|----------------|
| **Returns** | returns_1d, returns_5d, returns_20d | `pct_change(periods=N)` |
| **Moving Averages** | sma_5, sma_20, sma_50 | Simple MA |
| **EMAs** | ema_12, ema_26 | Exponential MA |
| **MACD** | macd, macd_signal, macd_hist | EMA(12) - EMA(26) |
| **RSI** | rsi_14 | 14-period RSI |
| **Bollinger Bands** | bb_upper, bb_middle, bb_lower, bb_width | 20-period, 2 std |
| **Volume** | volume_sma_20, volume_ratio | Volume vs 20-day avg |
| **Volatility** | volatility_20d | 20-day rolling std of returns |
| **Price Position** | price_vs_sma20, price_vs_sma50 | Relative to MAs |
| **ATR** | atr_14 | 14-period Average True Range |

---

## 3. ML Models

### Model 1: Baseline Forecaster (Random Forest)

**Script:** `ml/src/models/baseline_forecaster.py`

**Class:** `BaselineForecaster`

| Parameter | Value |
|-----------|-------|
| Algorithm | Random Forest Classifier |
| n_estimators | 100 |
| max_depth | 10 |
| min_samples_split | 5 |

**Labels:**
- **Bullish**: Forward return > +2%
- **Neutral**: Forward return between -2% and +2%
- **Bearish**: Forward return < -2%

**Horizons:**
- 1D (1 day ahead)
- 1W (1 week ahead)

**Output:**
```python
{
    "horizon": "1D",
    "label": "Bullish",
    "confidence": 0.72,
    "points": [{"date": "2025-12-23", "value": 255.50}]
}
```

---

### Model 2: SuperTrend AI (K-Means Clustering)

**Script:** `ml/src/strategies/supertrend_ai.py`

**Class:** `SuperTrendAI`

| Parameter | Default | Description |
|-----------|---------|-------------|
| atr_length | 10 | ATR calculation period |
| min_mult | 1.0 | Minimum ATR multiplier |
| max_mult | 5.0 | Maximum ATR multiplier |
| step | 0.5 | Step between multipliers |
| perf_alpha | 10 | Performance smoothing |

**Algorithm:**
1. Test ATR multipliers from 1.0 to 5.0 (step 0.5)
2. Calculate performance score for each factor
3. Cluster factors using K-Means (3 clusters: Best, Average, Worst)
4. Select optimal factor from "Best" cluster
5. Generate SuperTrend line and signals

**Output:**
```python
{
    "target_factor": 2.5,
    "performance_index": 0.85,
    "current_trend": "bullish",
    "signal_strength": 8,  # 0-10 scale
    "stop_level": 248.50,
    "trend_duration_bars": 12,
    "signals": [
        {
            "date": "2025-12-19",
            "type": "BUY",
            "price": 250.00,
            "stop_level": 245.00,
            "confidence": 0.82
        }
    ]
}
```

---

## 4. Job Execution

### Trigger Methods

| Method | Schedule | Script |
|--------|----------|--------|
| GitHub Actions | Every 5 min | `.github/workflows/job-worker.yml` |
| Manual | On-demand | `python -m src.forecast_job --symbol AAPL` |
| UI Sync Button | User-triggered | `POST /refresh-data` → queues job |

### Job Worker Flow

**Script:** `ml/src/job_worker.py`

```
1. Poll job_queue for pending jobs
2. Claim job (set status = 'processing')
3. Fetch OHLC data from ohlc_bars
4. Add technical features
5. Run SuperTrend AI
6. Run Baseline Forecaster for each horizon
7. Save results to ml_forecasts table
8. Save signals to supertrend_signals table
9. Mark job complete
```

### Forecast Job Flow

**Script:** `ml/src/forecast_job.py`

```python
def process_symbol(symbol: str):
    # 1. Fetch data
    df = db.fetch_ohlc_bars(symbol, timeframe="d1", limit=500)
    
    # 2. Add features
    df = add_technical_features(df)
    
    # 3. SuperTrend AI
    supertrend = SuperTrendAI(df)
    st_df, st_info = supertrend.calculate()
    
    # 4. Baseline Forecaster
    for horizon in ["1D", "1W"]:
        forecaster = BaselineForecaster()
        forecast = forecaster.generate_forecast(df, horizon)
        db.upsert_forecast(symbol_id, horizon, forecast, supertrend_data)
```

---

## 5. Data Storage

### ml_forecasts Table Schema

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| symbol_id | UUID | FK to symbols |
| horizon | TEXT | "1D", "1W" |
| overall_label | TEXT | "Bullish", "Neutral", "Bearish" |
| confidence | FLOAT | 0.0 - 1.0 |
| points | JSONB | Forecast price points |
| supertrend_factor | FLOAT | Optimal ATR multiplier |
| supertrend_performance | FLOAT | Performance index |
| supertrend_signal | INT | -1, 0, 1 |
| trend_label | TEXT | Current trend |
| trend_confidence | INT | 0-10 signal strength |
| stop_level | FLOAT | SuperTrend stop price |
| trend_duration_bars | INT | Bars in current trend |
| run_at | TIMESTAMP | When forecast was generated |

---

## 6. API Endpoints

### Chart Data
```
GET /functions/v1/chart?symbol=AAPL&timeframe=d1
```
Returns: OHLC bars + ML summary

### Enhanced Prediction
```
GET /functions/v1/enhanced-prediction?symbol=AAPL
```
Returns:
- Multi-timeframe consensus
- Forecast explanation
- Data quality report

### Refresh Data (Coordinated Sync)
```
POST /functions/v1/refresh-data
Body: { "symbol": "AAPL", "refreshML": true }
```
Actions:
1. Fetch new bars (incremental)
2. Queue ML forecast job
3. Return status

---

## 7. UI Display

### Swift Views

| View | File | Data Source |
|------|------|-------------|
| **Chart** | `ChartView.swift` | `/chart` endpoint |
| **ML Forecast** | `ForecastExplainerView.swift` | `/enhanced-prediction` |
| **Multi-TF Consensus** | `MultiTimeframeConsensusView.swift` | `/enhanced-prediction` |
| **Data Health** | `DataHealthView.swift` | `/enhanced-prediction` |
| **SuperTrend Panel** | `SuperTrendPanelView.swift` | `ChartResponse.indicatorData` |

### ViewModel

**File:** `ViewModels/ChartViewModel.swift`

Key Properties:
- `chartData: ChartResponse` - OHLC bars + ML summary
- `isRefreshing: Bool` - Sync button state
- `refreshData()` - Triggers coordinated refresh

### UI Components

```
┌─────────────────────────────────────────────────────┐
│ AAPL                    [↻] [⟳ Sync] [Indicators ▼] │
├─────────────────────────────────────────────────────┤
│                                                     │
│              Candlestick Chart                      │
│         (with SuperTrend overlay)                   │
│                                                     │
├─────────────────────────────────────────────────────┤
│ ML Forecast: BULLISH (72%)                          │
│ SuperTrend: ▲ BULL | Factor: 2.5 | Stop: $248.50   │
├─────────────────────────────────────────────────────┤
│ Multi-Timeframe Consensus                           │
│ ├─ m15: Neutral (52%)                              │
│ ├─ h1:  Bullish (68%)                              │
│ ├─ d1:  Bullish (72%)                              │
│ └─ w1:  Bullish (65%)                              │
├─────────────────────────────────────────────────────┤
│ Data Health: 100% ✓                                 │
└─────────────────────────────────────────────────────┘
```

---

## 8. Complete Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                        DATA INGESTION                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Polygon API ──→ chart Edge Function ──→ ohlc_bars (Supabase)   │
│       │                                        │                 │
│       └── backfill-ohlc.yml (every 6 hrs) ────┘                 │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                        ML PROCESSING                             │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  job_queue ──→ job_worker.py ──→ forecast_job.py                │
│                     │                                            │
│                     ├── add_technical_features()                 │
│                     ├── SuperTrendAI.calculate()                 │
│                     └── BaselineForecaster.generate_forecast()   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                        DATA STORAGE                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ml_forecasts ◄── upsert_forecast()                             │
│  supertrend_signals ◄── upsert_supertrend_signals()             │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                        API LAYER                                 │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  /chart ──────────────→ ChartResponse (bars + mlSummary)        │
│  /enhanced-prediction ─→ MultiTF + Explanation + DataQuality    │
│  /refresh-data ────────→ Sync + Queue Jobs                      │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                        SWIFT UI                                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ChartViewModel ──→ ChartView                                   │
│       │                 ├── AdvancedChartView (candlesticks)    │
│       │                 ├── SuperTrendPanelView                 │
│       │                 └── Indicator overlays                  │
│       │                                                          │
│  AnalysisViewModel ──→ AnalysisView                             │
│                            ├── ForecastExplainerView            │
│                            ├── MultiTimeframeConsensusView      │
│                            └── DataHealthView                   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 9. Key Files Reference

| Category | File Path |
|----------|-----------|
| **Feature Engineering** | `ml/src/features/technical_indicators.py` |
| **Random Forest Model** | `ml/src/models/baseline_forecaster.py` |
| **SuperTrend AI** | `ml/src/strategies/supertrend_ai.py` |
| **Job Worker** | `ml/src/job_worker.py` |
| **Forecast Job** | `ml/src/forecast_job.py` |
| **Database Layer** | `ml/src/data/supabase_db.py` |
| **Chart API** | `backend/supabase/functions/chart/index.ts` |
| **Enhanced Prediction API** | `backend/supabase/functions/enhanced-prediction/index.ts` |
| **Refresh Data API** | `backend/supabase/functions/refresh-data/index.ts` |
| **Chart ViewModel** | `client-macos/SwiftBoltML/ViewModels/ChartViewModel.swift` |
| **Chart View** | `client-macos/SwiftBoltML/Views/ChartView.swift` |
| **Analysis View** | `client-macos/SwiftBoltML/Views/AnalysisView.swift` |

---

## 10. Model Weights Summary

### Baseline Forecaster
| Hyperparameter | Value |
|----------------|-------|
| n_estimators | 100 |
| max_depth | 10 |
| min_samples_split | 5 |
| random_state | 42 |

### SuperTrend AI
| Parameter | Value |
|-----------|-------|
| ATR Period | 10 |
| Factor Range | 1.0 - 5.0 |
| Factor Step | 0.5 |
| K-Means Clusters | 3 |
| Cluster Selection | "Best" |
