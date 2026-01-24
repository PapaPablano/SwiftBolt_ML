# ML and Forecasting System Flowchart
**Date**: January 23, 2026  
**Version**: 1.0  
**System**: SwiftBolt ML Platform

---

## 📊 System Overview

This document provides a comprehensive flowchart of the entire ML and forecasting system, including:
- GitHub Actions workflows
- Data processing pipelines
- Swift macOS app functions
- Supabase Edge Functions
- Database tables and data pools

---

## 🔄 High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA INGESTION LAYER                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────┴─────────────────────┐
        │                                           │
        ▼                                           ▼
┌───────────────┐                          ┌───────────────┐
│ Daily Data    │                          │ Intraday      │
│ Refresh       │                          │ Ingestion     │
│ Workflow      │                          │ Workflow      │
└───────────────┘                          └───────────────┘
        │                                           │
        ▼                                           ▼
┌───────────────────────────────────────────────────────────────┐
│                    SUPABASE DATABASE                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ ohlc_bars_v2 │  │ symbols      │  │ watchlists   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└───────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────────┐
│                    ML PROCESSING LAYER                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ ML           │  │ Intraday     │  │ Options      │       │
│  │ Orchestration│  │  │ Forecast     │  │ Processing  │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└───────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────────┐
│                    FORECAST STORAGE                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ ml_forecasts │  │ ml_forecasts │  │ options_ranks │       │
│  │              │  │ _intraday    │  │              │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└───────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────────┐
│                    EVALUATION & VALIDATION                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ forecast_    │  │ live_        │  │ model_       │       │
│  │ evaluations  │  │ predictions  │  │ weights      │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└───────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────────┐
│                    SWIFT MACOS APP                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ Edge         │  │ ViewModels   │  │ Views        │       │
│  │ Functions    │  │ & Services   │  │ & UI         │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└───────────────────────────────────────────────────────────────┘
```

---

## 🔧 GitHub Actions Workflows

### 1. Data Ingestion Workflows

#### Daily Data Refresh
```
Workflow: .github/workflows/daily-data-refresh.yml
Trigger: Schedule (daily 02:00 UTC) + Manual
Duration: 15-20 minutes

┌─────────────────────────────────────────┐
│  Daily Data Refresh Workflow            │
├─────────────────────────────────────────┤
│  1. Checkout & Setup                    │
│  2. Resolve Symbol Universe             │
│  3. Run Full Backfill (gap detection)   │
│  4. Validate OHLC Integrity             │
│  5. Final Summary                       │
└─────────────────────────────────────────┘
              │
              ▼
    ┌─────────────────┐
    │ ohlc_bars_v2    │
    │ (d1, w1)        │
    └─────────────────┘
```

**Output Tables**:
- `ohlc_bars_v2` (daily, weekly bars)
- `symbols` (symbol metadata)

---

#### Intraday Ingestion
```
Workflow: .github/workflows/intraday-ingestion.yml
Trigger: Schedule (every 15 min during market hours) + Manual
Duration: 5-10 minutes

┌─────────────────────────────────────────┐
│  Intraday Ingestion Workflow            │
├─────────────────────────────────────────┤
│  1. Checkout & Setup                    │
│  2. Fetch Intraday Data (m15, h1)       │
│  3. Validate OHLC Integrity             │
│  4. Job Summary                         │
└─────────────────────────────────────────┘
              │
              ▼
    ┌─────────────────┐
    │ ohlc_bars_v2    │
    │ (m15, h1)       │
    └─────────────────┘
```

**Output Tables**:
- `ohlc_bars_v2` (15-min, 1-hour bars)

---

### 2. ML Processing Workflows

#### ML Orchestration (Main Pipeline)
```
Workflow: .github/workflows/ml-orchestration.yml
Trigger: After Daily Data Refresh + Schedule (04:00 UTC) + Manual
Duration: 20-30 minutes

┌─────────────────────────────────────────┐
│  ML Orchestration Workflow             │
├─────────────────────────────────────────┤
│  ┌───────────────────────────────────┐  │
│  │ ml-forecast Job                   │  │
│  │  - Validate OHLC before training │  │
│  │  - Generate ML forecasts          │  │
│  │  - Store to ml_forecasts          │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │ options-processing Job             │  │
│  │  - Process options data            │  │
│  │  - Generate options_ranks          │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │ model-health Job                   │  │
│  │  - Run ML evaluation               │  │
│  │  - Populate live_predictions       │  │
│  │  - Unified validation              │  │
│  │  - Update model weights            │  │
│  │  - Check drift & staleness         │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

**Output Tables**:
- `ml_forecasts` (daily/weekly/monthly forecasts)
- `options_ranks` (ML-scored options)
- `forecast_evaluations` (evaluation results)
- `live_predictions` (current accuracy scores)
- `model_weights` (ensemble weights)

---

#### Intraday Forecast
```
Workflow: .github/workflows/intraday-forecast.yml
Trigger: Schedule (every hour during market hours) + Manual
Duration: 10-15 minutes

┌─────────────────────────────────────────┐
│  Intraday Forecast Workflow             │
├─────────────────────────────────────────┤
│  1. Validate OHLC before forecasting   │
│  2. Generate intraday forecasts         │
│  3. Store to ml_forecasts_intraday     │
│  4. Job Summary                         │
└─────────────────────────────────────────┘
              │
              ▼
    ┌─────────────────────────┐
    │ ml_forecasts_intraday   │
    │ (m15, h1 forecasts)     │
    └─────────────────────────┘
```

**Output Tables**:
- `ml_forecasts_intraday` (15-min, 1-hour forecasts)

---

## 🗄️ Database Tables (Data Pools)

### Core Data Tables

#### `ohlc_bars_v2`
**Purpose**: Primary OHLC data storage  
**Timeframes**: m15, h1, h4, d1, w1  
**Sources**: 
- Daily Data Refresh (d1, w1)
- Intraday Ingestion (m15, h1)
- Alpaca API (via backfill scripts)

**Key Columns**:
- `symbol_id`, `timeframe`, `ts`, `open`, `high`, `low`, `close`, `volume`
- `provider`, `is_forecast`, `data_status`

---

#### `symbols`
**Purpose**: Symbol metadata and watchlist  
**Sources**: Manual entry, watchlist management

**Key Columns**:
- `id`, `ticker`, `name`, `sector`, `industry`

---

#### `watchlists`
**Purpose**: User watchlists  
**Sources**: Swift app, manual management

---

### ML Forecast Tables

#### `ml_forecasts`
**Purpose**: Daily/weekly/monthly ML forecasts  
**Sources**: ML Orchestration → ml-forecast job

**Key Columns**:
- `symbol_id`, `horizon` (1D, 1W, 1M)
- `overall_label` (Bullish/Neutral/Bearish)
- `confidence` (0-1)
- `points` (JSONB forecast points)
- `model_predictions`, `model_confidences`
- `ensemble_method`, `ensemble_weights`

**Workflow**: `ml-orchestration.yml` → `ml-forecast` job → `forecast_job.py`

---

#### `ml_forecasts_intraday`
**Purpose**: Intraday forecasts (15-min, 1-hour)  
**Sources**: Intraday Forecast workflow

**Key Columns**:
- `symbol_id`, `horizon` (15m, 1h), `timeframe` (m15, h1)
- `overall_label`, `confidence`, `target_price`
- `supertrend_component`, `sr_component`, `ensemble_component`

**Workflow**: `intraday-forecast.yml` → intraday forecast generation

---

### Evaluation Tables

#### `forecast_evaluations`
**Purpose**: Forecast accuracy evaluations  
**Sources**: ML Orchestration → model-health → evaluation_job

**Key Columns**:
- `forecast_id`, `symbol_id`, `horizon`
- `predicted_label`, `predicted_value`, `predicted_confidence`
- `realized_price`, `realized_return`, `realized_label`
- `direction_correct`, `price_error`, `price_error_pct`
- `rf_correct`, `gb_correct`, `model_agreement`

**Workflow**: `ml-orchestration.yml` → `model-health` → `evaluation_job.py`

---

#### `live_predictions`
**Purpose**: Current accuracy scores per symbol/timeframe  
**Sources**: ML Orchestration → model-health → populate_live_predictions

**Key Columns**:
- `symbol_id`, `timeframe` (m15, h1, h4, d1, w1)
- `signal` (BULLISH/BEARISH/NEUTRAL)
- `accuracy_score` (0-1)
- `metadata` (JSONB with evaluation counts)

**Workflow**: `ml-orchestration.yml` → `model-health` → `populate_live_predictions.py`

---

#### `model_weights`
**Purpose**: Ensemble model weights (RF + GB)  
**Sources**: ML Orchestration → model-health → trigger_weight_update RPC

**Key Columns**:
- `horizon` (1D, 1W, 1M)
- `rf_weight`, `gb_weight`
- `rf_accuracy_30d`, `gb_accuracy_30d`
- `last_updated`, `update_reason`

**Workflow**: `ml-orchestration.yml` → `model-health` → `trigger_weight_update()` RPC

---

#### `model_performance_history`
**Purpose**: Daily performance summaries  
**Sources**: ML Orchestration → model-health → evaluation_job

**Key Columns**:
- `evaluation_date`, `horizon`
- `total_forecasts`, `correct_forecasts`, `accuracy`
- `rf_accuracy`, `gb_accuracy`, `ensemble_accuracy`

---

### Options Tables

#### `options_ranks`
**Purpose**: ML-scored options contracts  
**Sources**: ML Orchestration → options-processing job

**Key Columns**:
- `underlying_symbol_id`, `expiry`, `strike`, `side`
- `ml_score` (0-1)
- `implied_vol`, `delta`, `gamma`
- `open_interest`, `volume`

**Workflow**: `ml-orchestration.yml` → `options-processing` job

---

## 🚀 Supabase Edge Functions

### Data Retrieval Functions

#### `chart-data-v2`
**Purpose**: Fetch OHLC data for charts  
**Swift Usage**: `APIClient.fetchChartDataV2()`

**Input**: `symbol`, `timeframe`, `limit`  
**Output**: OHLC bars from `ohlc_bars_v2`

---

#### `quotes`
**Purpose**: Fetch current quotes  
**Swift Usage**: `APIClient.fetchQuotes()`

---

#### `options-chain`
**Purpose**: Fetch options chain  
**Swift Usage**: `APIClient.fetchOptionsChain()`

---

#### `options-quotes`
**Purpose**: Fetch options quotes  
**Swift Usage**: `APIClient.fetchOptionsQuotes()`

---

### ML Functions

#### `ml-dashboard`
**Purpose**: Fetch ML dashboard data  
**Swift Usage**: `APIClient.fetchMLDashboard()`

**Output**: 
- Overview stats
- Recent forecasts
- Symbol performance
- Feature stats
- Validation metrics

---

#### `enhanced-prediction`
**Purpose**: Fetch enhanced prediction with explanation  
**Swift Usage**: `APIClient.fetchEnhancedPrediction()`

**Output**:
- Multi-timeframe consensus
- Forecast explanation
- Data quality report

---

#### `support-resistance`
**Purpose**: Fetch S/R levels  
**Swift Usage**: `APIClient.fetchSupportResistance()`

---

### Processing Functions

#### `trigger-ranking-job`
**Purpose**: Trigger options ranking job  
**Swift Usage**: `APIClient.triggerRankingJob()`

**Input**: `symbol`  
**Output**: Job status, ranks inserted

---

#### `refresh-data`
**Purpose**: Refresh data for a symbol  
**Swift Usage**: `APIClient.refreshData()`

**Input**: `symbol`, `refreshML`, `refreshOptions`

---

## 📱 Swift macOS App

### Services Layer

#### `APIClient.swift`
**Purpose**: Main API client for Supabase Edge Functions

**Key Functions**:
- `fetchChartDataV2()` → `chart-data-v2`
- `fetchQuotes()` → `quotes`
- `fetchOptionsChain()` → `options-chain`
- `fetchMLDashboard()` → `ml-dashboard`
- `fetchEnhancedPrediction()` → `enhanced-prediction`
- `fetchSupportResistance()` → `support-resistance`
- `triggerRankingJob()` → `trigger-ranking-job`
- `refreshData()` → `refresh-data`

---

#### `MarketDataService.swift`
**Purpose**: Market data management

**Key Functions**:
- `fetchMarketData()`
- `fetchForecasts()`
- `fetchOptionsData()`

---

#### `ChartBridge.swift`
**Purpose**: Chart data bridge

**Key Functions**:
- `loadChartData()`
- `updateChart()`

---

### ViewModels

#### `PredictionsViewModel.swift`
**Purpose**: ML predictions dashboard

**Key Properties**:
- `dashboardData: MLDashboardResponse?`
- `recentForecasts: [ForecastSummary]`
- `symbolPerformance: [SymbolPerformance]`

**Key Functions**:
- `loadDashboard()` → `APIClient.fetchMLDashboard()`

---

#### `AnalysisViewModel.swift`
**Purpose**: Symbol analysis

**Key Properties**:
- `multiTimeframeConsensus: MultiTimeframeConsensus?`
- `forecastExplanation: ForecastExplanation?`
- `dataQuality: DataQualityReport?`
- `supportResistance: SupportResistanceResponse?`

**Key Functions**:
- `loadEnhancedInsights()` → `APIClient.fetchEnhancedPrediction()`
- `loadSupportResistance()` → `APIClient.fetchSupportResistance()`

---

#### `ChartViewModel.swift`
**Purpose**: Chart data management

**Key Functions**:
- `loadChartData()` → `APIClient.fetchChartDataV2()`
- `updateChart()`

---

### Views

#### `PredictionsView.swift`
**Purpose**: ML predictions dashboard UI  
**ViewModel**: `PredictionsViewModel`

---

#### `MultiHorizonForecastView.swift`
**Purpose**: Multi-horizon forecast display  
**Data**: `ml_forecasts` (1D, 1W, 1M)

---

#### `MultiTimeframeForecastView.swift`
**Purpose**: Multi-timeframe forecast display  
**Data**: `ml_forecasts_intraday` (m15, h1)

---

#### `ForecastAccuracyTabView.swift`
**Purpose**: Forecast accuracy metrics  
**Data**: `forecast_evaluations`, `model_performance_history`

---

#### `ForecastQualityView.swift`
**Purpose**: Forecast quality metrics  
**ViewModel**: `ForecastQualityViewModel`

---

#### `AnalysisView.swift`
**Purpose**: Symbol analysis UI  
**ViewModel**: `AnalysisViewModel`

---

## 🔄 Complete Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    GITHUB ACTIONS WORKFLOWS                    │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────┐      ┌──────────────────┐
│ Daily Data       │      │ Intraday         │
│ Refresh          │      │ Ingestion        │
│ (02:00 UTC)      │      │ (Every 15 min)   │
└────────┬─────────┘      └────────┬─────────┘
         │                         │
         ▼                         ▼
┌─────────────────────────────────────────┐
│         SUPABASE DATABASE               │
│  ┌───────────────────────────────────┐  │
│  │ ohlc_bars_v2                      │  │
│  │ - d1, w1 (from Daily Refresh)     │  │
│  │ - m15, h1 (from Intraday)         │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│         ML ORCHESTRATION                │
│  ┌───────────────────────────────────┐  │
│  │ ml-forecast Job                   │  │
│  │  → forecast_job.py                │  │
│  │  → ml_forecasts                   │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │ options-processing Job             │  │
│  │  → options_ranks                   │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │ model-health Job                   │  │
│  │  → evaluation_job.py               │  │
│  │  → forecast_evaluations            │  │
│  │  → populate_live_predictions.py   │  │
│  │  → live_predictions                │  │
│  │  → trigger_weight_update()        │  │
│  │  → model_weights                   │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│         SUPABASE EDGE FUNCTIONS        │
│  ┌───────────────────────────────────┐  │
│  │ chart-data-v2                     │  │
│  │ ml-dashboard                      │  │
│  │ enhanced-prediction               │  │
│  │ support-resistance                │  │
│  │ options-chain                     │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│         SWIFT MACOS APP                │
│  ┌───────────────────────────────────┐  │
│  │ APIClient                         │  │
│  │  → fetchChartDataV2()             │  │
│  │  → fetchMLDashboard()             │  │
│  │  → fetchEnhancedPrediction()      │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │ ViewModels                         │  │
│  │  → PredictionsViewModel            │  │
│  │  → AnalysisViewModel               │  │
│  │  → ChartViewModel                   │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │ Views                              │  │
│  │  → PredictionsView                 │  │
│  │  → MultiHorizonForecastView        │  │
│  │  → AnalysisView                    │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

---

## 📋 Workflow Dependencies

```
Daily Data Refresh (02:00 UTC)
    │
    ├─→ ML Orchestration (04:00 UTC)
    │       │
    │       ├─→ ml-forecast
    │       │       └─→ ml_forecasts
    │       │
    │       ├─→ options-processing
    │       │       └─→ options_ranks
    │       │
    │       └─→ model-health
    │               ├─→ evaluation_job
    │               │       └─→ forecast_evaluations
    │               │
    │               ├─→ populate_live_predictions
    │               │       └─→ live_predictions
    │               │
    │               └─→ trigger_weight_update
    │                       └─→ model_weights
    │
    └─→ (No dependencies)

Intraday Ingestion (Every 15 min)
    │
    └─→ ohlc_bars_v2 (m15, h1)
            │
            └─→ Intraday Forecast (Every hour)
                    └─→ ml_forecasts_intraday
```

---

## 🔑 Key Processing Scripts

### Python Scripts (ml/src/)

#### `forecast_job.py`
**Purpose**: Generate ML forecasts  
**Input**: Symbol, OHLC data  
**Output**: `ml_forecasts` table  
**Called by**: `ml-orchestration.yml` → `ml-forecast` job

---

#### `evaluation_job.py`
**Purpose**: Evaluate forecasts against actuals  
**Input**: `ml_forecasts`, actual prices  
**Output**: `forecast_evaluations` table  
**Called by**: `ml-orchestration.yml` → `model-health` job

---

#### `populate_live_predictions.py`
**Purpose**: Populate live accuracy scores  
**Input**: `forecast_evaluations`  
**Output**: `live_predictions` table  
**Called by**: `ml-orchestration.yml` → `model-health` job

---

#### `alpaca_backfill_ohlc_v2.py`
**Purpose**: Backfill OHLC data from Alpaca  
**Input**: Symbol, timeframe  
**Output**: `ohlc_bars_v2` table  
**Called by**: `intraday-ingestion.yml`, `daily-data-refresh.yml`

---

#### `smart_backfill_all.sh`
**Purpose**: Smart backfill with gap detection  
**Input**: Symbol universe  
**Output**: `ohlc_bars_v2` table  
**Called by**: `daily-data-refresh.yml`

---

## 📊 Data Pool Summary

### Input Data Pools
- **Alpaca API**: Real-time and historical OHLC data
- **Symbol Universe**: From `watchlists` and `symbols` tables

### Processing Data Pools
- **OHLC Data**: `ohlc_bars_v2` (m15, h1, h4, d1, w1)
- **Forecasts**: `ml_forecasts`, `ml_forecasts_intraday`
- **Evaluations**: `forecast_evaluations`
- **Accuracy**: `live_predictions`, `model_performance_history`
- **Weights**: `model_weights`

### Output Data Pools
- **Swift App**: Via Edge Functions
- **Options**: `options_ranks`
- **Dashboard**: ML dashboard data

---

## 🔄 Real-Time Flow (During Market Hours)

```
Every 15 minutes:
  Intraday Ingestion → ohlc_bars_v2 (m15, h1)

Every hour:
  Intraday Forecast → ml_forecasts_intraday (m15, h1)

Swift App (User Request):
  APIClient.fetchChartDataV2()
    → chart-data-v2 Edge Function
      → ohlc_bars_v2
        → ChartViewModel
          → ChartView

  APIClient.fetchMLDashboard()
    → ml-dashboard Edge Function
      → ml_forecasts, forecast_evaluations
        → PredictionsViewModel
          → PredictionsView
```

---

## 🌙 Nightly Flow (After Market Close)

```
02:00 UTC: Daily Data Refresh
  → ohlc_bars_v2 (d1, w1)

04:00 UTC: ML Orchestration
  → ml-forecast
    → ml_forecasts (1D, 1W, 1M)
  → options-processing
    → options_ranks
  → model-health
    → evaluation_job
      → forecast_evaluations
    → populate_live_predictions
      → live_predictions
    → trigger_weight_update
      → model_weights
```

---

## ✅ Summary

**Data Sources**:
- Alpaca API (OHLC data)
- Symbol universe (watchlists)

**Processing**:
- GitHub Actions workflows (automated)
- Python scripts (ML processing)

**Storage**:
- Supabase database (PostgreSQL)
- Multiple tables for different data types

**Access**:
- Supabase Edge Functions (API layer)
- Swift macOS app (user interface)

**Flow**:
1. Data ingestion (workflows)
2. ML processing (orchestration)
3. Evaluation & validation (feedback loop)
4. User access (Edge Functions → Swift app)

---

---

## 🧮 Processing & Calculation Components

### Python Processing Scripts (ml/src/scripts/)

#### Data Ingestion Scripts
- **`alpaca_backfill_ohlc_v2.py`**: Backfill OHLC data from Alpaca API → `ohlc_bars_v2`
- **`backfill_with_gap_detection.py`**: Detect and fill gaps in OHLC data
- **`smart_backfill_all.sh`**: Smart backfill orchestration with gap detection
- **`deep_backfill_ohlc_v2.py`**: Deep historical backfill
- **`refresh_underlying_history.py`**: Refresh underlying symbol history
- **`backfill_options.py`**: Backfill options chain data → `options_ranks`
- **`process_options_backfill_jobs.py`**: Process queued options backfill jobs
- **`process_backfill_queue.py`**: Process general backfill queue

#### Data Management Scripts
- **`resolve_universe.py`**: Resolve symbol universe from watchlists
- **`universe_utils.py`**: Utilities for symbol universe management
- **`get_watchlist_symbols.py`**: Get symbols from watchlists
- **`diagnose_ml_data.py`**: Diagnose ML data quality issues
- **`populate_live_predictions.py`**: Populate `live_predictions` from evaluations

#### Model & Performance Scripts
- **`ptq_accuracy_check.py`**: Post-training quantization accuracy check
- **`quantization_calibration.py`**: Model quantization calibration
- **`xgboost_inference_benchmark.py`**: XGBoost inference performance benchmark

---

### ML Models (ml/src/models/)

#### Forecasters
- **`ensemble_forecaster.py`**: Random Forest + Gradient Boosting ensemble
- **`enhanced_ensemble_integration.py`**: Enhanced 5-model ensemble (RF, GB, Prophet, LSTM, ARIMA-GARCH)
- **`extended_ensemble_forecaster.py`**: Extended ensemble with more models
- **`baseline_forecaster.py`**: Baseline forecasting (naive, moving average)
- **`prophet_forecaster.py`**: Facebook Prophet time series forecaster
- **`lstm_forecaster.py`**: LSTM neural network forecaster
- **`arima_garch_forecaster.py`**: ARIMA-GARCH volatility forecaster
- **`gradient_boosting_forecaster.py`**: XGBoost gradient boosting forecaster
- **`lightgbm_forecaster.py`**: LightGBM gradient boosting forecaster
- **`multi_model_ensemble.py`**: Multi-model ensemble manager
- **`walk_forward_ensemble.py`**: Walk-forward optimized ensemble

#### Options Models
- **`options_ranker.py`**: ML-based options ranking
- **`enhanced_options_ranker.py`**: Enhanced options ranking with more features
- **`options_momentum_ranker.py`**: Momentum-based options ranking
- **`options_pricing.py`**: Options pricing models (Black-Scholes, etc.)
- **`volatility_surface.py`**: Volatility surface modeling
- **`heston_model.py`**: Heston stochastic volatility model

#### Calculators & Analyzers
- **`extrinsic_calculator.py`**: Calculate options extrinsic value
- **`pop_calculator.py`**: Probability of Profit calculator
- **`pcr_analyzer.py`**: Put/Call Ratio analyzer
- **`earnings_analyzer.py`**: Earnings analysis and impact
- **`forecast_explainer.py`**: Explain forecast reasoning
- **`composite_signal_calculator.py`**: Composite trading signal calculation

#### Ensemble & Weight Management
- **`ensemble_manager.py`**: Manage multiple ensemble models
- **`ensemble_loader.py`**: Load saved ensemble models
- **`weight_optimizer.py`**: Optimize ensemble weights
- **`regime_conditioner.py`**: Market regime conditioning
- **`residual_corrector.py`**: Residual error correction
- **`uncertainty_quantifier.py`**: Quantify forecast uncertainty
- **`conformal_interval.py`**: Conformal prediction intervals

#### Performance & Monitoring
- **`performance_monitor.py`**: Monitor model performance
- **`ranking_monitor.py`**: Monitor options ranking performance
- **`ranking_calibrator.py`**: Calibrate ranking scores
- **`forecast_options_integration.py`**: Integrate forecasts with options

---

### Feature Engineering (ml/src/features/)

#### Technical Indicators
- **`technical_indicators.py`**: Core technical indicators (RSI, MACD, ADX, etc.)
- **`technical_indicators_tradingview.py`**: TradingView-aligned indicators
- **`technical_indicators_corrected.py`**: Corrected indicator calculations
- **`temporal_indicators.py`**: Time-based indicators
- **`regime_indicators.py`**: Market regime indicators
- **`adaptive_thresholds.py`**: Adaptive indicator thresholds

#### Support & Resistance
- **`support_resistance_detector.py`**: Detect S/R levels
- **`sr_feature_builder.py`**: Build S/R features
- **`sr_polynomial.py`**: Polynomial S/R detection
- **`polynomial_sr_indicator.py`**: Polynomial regression S/R
- **`logistic_sr_indicator.py`**: Logistic regression S/R
- **`pivot_levels_detector.py`**: Pivot point detection
- **`sr_probability.py`**: S/R probability calculations
- **`sr_correlation_analyzer.py`**: S/R correlation analysis

#### Volatility & Market Analysis
- **`volatility_analysis.py`**: Volatility analysis features
- **`market_regime.py`**: Market regime detection
- **`multi_timeframe.py`**: Multi-timeframe feature aggregation

#### Feature Management
- **`feature_cache.py`**: Cache computed features

---

### Services (ml/src/services/)

#### Forecast Services
- **`forecast_service_v2.py`**: V2 forecast service
- **`forecast_bar_writer.py`**: Write forecast bars to database

#### Validation Services
- **`validation_service.py`**: Unified validation service
- **`test_validation_service.py`**: Test validation service

---

### Evaluation (ml/src/evaluation/)

- **`walk_forward_cv.py`**: Walk-forward cross-validation
- **`purged_walk_forward_cv.py`**: Purged walk-forward CV (no data leakage)
- **`statistical_tests.py`**: Statistical significance tests
- **`options_ranking_validation.py`**: Validate options ranking accuracy

---

### Backtesting (ml/src/backtesting/)

- **`backtest_engine.py`**: Core backtesting engine
- **`walk_forward_tester.py`**: Walk-forward backtesting
- **`performance_metrics.py`**: Calculate backtest performance metrics
- **`trade_logger.py`**: Log backtest trades
- **`run_baseline_benchmark.py`**: Run baseline model benchmarks

---

### Monitoring (ml/src/monitoring/)

- **`forecast_validator.py`**: Validate forecast quality
- **`forecast_quality.py`**: Monitor forecast quality metrics
- **`forecast_staleness.py`**: Detect stale forecasts
- **`confidence_calibrator.py`**: Calibrate confidence scores
- **`drift_detector.py`**: Detect model drift
- **`price_monitor.py`**: Monitor price movements
- **`greeks_validator.py`**: Validate options Greeks

---

### Validation (ml/src/validation/)

- **`unified_framework.py`**: Unified validation framework
- **`unified_output.py`**: Unified validation output
- **`greeks_validator.py`**: Validate options Greeks

---

### Optimization (ml/src/optimization/)

- **`portfolio_optimizer.py`**: Portfolio optimization
- **`efficient_frontier.py`**: Efficient frontier calculation
- **`position_sizing.py`**: Optimal position sizing
- **`parameter_optimizer.py`**: Hyperparameter optimization
- **`walk_forward.py`**: Walk-forward optimization

---

### Risk Management (ml/src/risk/)

- **`portfolio_manager.py`**: Portfolio risk management
- **`risk_limits.py`**: Risk limit enforcement
- **`stress_testing.py`**: Stress testing scenarios
- **`scenario_builder.py`**: Build stress test scenarios

---

### Strategies (ml/src/strategies/)

- **`supertrend_ai.py`**: SuperTrend AI strategy
- **`strategy_builder.py`**: Build trading strategies

---

### Training (ml/src/training/)

- **`ensemble_training_job.py`**: Train ensemble models
- **`model_training.py`**: Core model training
- **`data_preparation.py`**: Prepare training data
- **`weight_optimizer.py`**: Optimize ensemble weights
- **`diagnose_threshold.py`**: Diagnose classification thresholds
- **`test_training.py`**: Test training pipeline
- **`wandb_integration.py`**: Weights & Biases integration

---

### Market Analysis (ml/src/market_analysis/)

- **`options_chain.py`**: Options chain analysis
- **`greeks_aggregation.py`**: Aggregate options Greeks
- **`liquidity_analyzer.py`**: Analyze options liquidity

---

### Attribution (ml/src/attribution/)

- **`brinson_attribution.py`**: Brinson attribution analysis
- **`factor_analysis.py`**: Factor-based attribution

---

### Rebalancing (ml/src/rebalancing/)

- **`cost_optimizer.py`**: Optimize rebalancing costs
- **`tax_aware_rebalancer.py`**: Tax-aware rebalancing

---

### Simulation (ml/src/simulation/)

- **`monte_carlo.py`**: Monte Carlo simulation

---

### Visualization (ml/src/visualization/)

- **`greeks_surfaces.py`**: Visualize Greeks surfaces
- **`volatility_surfaces.py`**: Visualize volatility surfaces
- **`payoff_diagrams.py`**: Generate payoff diagrams

---

### Streaming (ml/src/streaming/)

- **`live_greeks.py`**: Live options Greeks streaming
- **`alert_manager.py`**: Manage trading alerts
- **`websocket_client.py`**: WebSocket client for real-time data

---

### Strategy Discovery (ml/src/strategy_discovery/)

- **`genetic_optimizer.py`**: Genetic algorithm optimization
- **`strategy_dna.py`**: Strategy DNA encoding
- **`fitness_evaluator.py`**: Evaluate strategy fitness

---

### Trading (ml/src/trading/)

- **`broker_interface.py`**: Broker API interface
- **`order_manager.py`**: Manage trading orders
- **`paper_trading.py`**: Paper trading simulation

---

## 🗄️ SQL Functions & Stored Procedures

### Forecast Functions
- **`get_pending_evaluations(horizon)`**: Get forecasts pending evaluation
- **`update_model_weights()`**: Update ensemble weights based on performance
- **`get_model_weights(horizon)`**: Get current model weights
- **`trigger_weight_update()`**: RPC to trigger weight update
- **`get_ml_dashboard()`**: Get ML dashboard data

### Data Functions
- **`get_chart_data_v2(symbol, timeframe, ...)`**: Get chart data (if exists)
- **`detect_gaps(symbol_id, timeframe, ...)`**: Detect data gaps
- **`fill_gaps(symbol_id, timeframe, ...)`**: Fill detected gaps

### Options Functions
- **`get_options_ranks(symbol, ...)`**: Get ranked options
- **`calculate_ml_score(...)`**: Calculate ML score for options

### Multi-Leg Functions
- **`create_multi_leg_strategy(...)`**: Create multi-leg strategy
- **`evaluate_multi_leg_strategy(...)`**: Evaluate strategy performance
- **`update_multi_leg_strategy(...)`**: Update strategy

---

## 📱 Swift Calculation Services

### Technical Indicators (client-macos/SwiftBoltML/Services/)
- **`SuperTrendAIIndicator.swift`**: SuperTrend AI calculation
- **`PolynomialRegressionIndicator.swift`**: Polynomial regression S/R
- **`LogisticRegressionIndicator.swift`**: Logistic regression S/R
- **`PivotLevelsIndicator.swift`**: Pivot levels calculation

### Market Data Services
- **`MarketDataService.swift`**: Market data processing
- **`ChartBridge.swift`**: Chart data bridge and processing

---

## 📊 Analysis Scripts (scripts/analysis/)

- **`earnings_analyzer.py`**: Analyze earnings impact
- **`extrinsic_calculator.py`**: Calculate extrinsic value
- **`pcr_analyzer.py`**: Put/Call Ratio analysis
- **`pop_calculator.py`**: Probability of Profit calculation

---

## 🔄 Processing Flow Summary

### Data Ingestion → Processing → Storage

```
Alpaca API / Data Sources
    ↓
[Backfill Scripts]
    ├─→ alpaca_backfill_ohlc_v2.py
    ├─→ backfill_with_gap_detection.py
    └─→ smart_backfill_all.sh
    ↓
ohlc_bars_v2 (Database)
    ↓
[Feature Engineering]
    ├─→ technical_indicators.py
    ├─→ support_resistance_detector.py
    └─→ feature_cache.py
    ↓
[ML Models]
    ├─→ ensemble_forecaster.py
    ├─→ enhanced_ensemble_integration.py
    └─→ forecast_synthesizer.py
    ↓
ml_forecasts (Database)
    ↓
[Evaluation]
    ├─→ evaluation_job.py
    └─→ walk_forward_cv.py
    ↓
forecast_evaluations (Database)
    ↓
[Validation]
    ├─→ validation_service.py
    └─→ populate_live_predictions.py
    ↓
live_predictions (Database)
```

### Options Processing Flow

```
Options Chain Data
    ↓
[Options Processing]
    ├─→ backfill_options.py
    └─→ options_ranker.py
    ↓
[ML Scoring]
    ├─→ enhanced_options_ranker.py
    └─→ options_momentum_ranker.py
    ↓
options_ranks (Database)
```

### Training Flow

```
Historical OHLC Data
    ↓
[Data Preparation]
    └─→ data_preparation.py
    ↓
[Model Training]
    ├─→ model_training.py
    └─→ ensemble_training_job.py
    ↓
[Weight Optimization]
    └─→ weight_optimizer.py
    ↓
Trained Models (Saved)
```

### Backtesting Flow

```
Historical Data + Strategy
    ↓
[Backtesting]
    ├─→ backtest_engine.py
    └─→ walk_forward_tester.py
    ↓
[Performance Metrics]
    └─→ performance_metrics.py
    ↓
Backtest Results
```

---

## 🎯 Calculation Categories

### Price & Forecast Calculations
- Ensemble forecasting (RF + GB + Prophet + LSTM + ARIMA-GARCH)
- Forecast synthesis (3-layer: SuperTrend + S/R + ML)
- Confidence calibration
- Uncertainty quantification
- Conformal prediction intervals

### Options Calculations
- Options pricing (Black-Scholes, Heston)
- Greeks calculation (Delta, Gamma, Theta, Vega)
- ML scoring for options
- Extrinsic value calculation
- Probability of Profit (POP)
- Put/Call Ratio (PCR)

### Technical Indicators
- Momentum: RSI, MACD, KDJ, MFI
- Trend: ADX, SuperTrend AI
- Volatility: Bollinger Bands, ATR
- Volume: Volume Ratio, OBV
- Support/Resistance: Polynomial, Logistic, Pivot Levels

### Risk & Portfolio Calculations
- Portfolio optimization (Efficient Frontier)
- Position sizing
- Risk limits
- Stress testing (Monte Carlo)
- Attribution analysis (Brinson, Factor)

### Performance Calculations
- Walk-forward validation
- Statistical significance tests
- Model drift detection
- Forecast quality metrics
- Backtest performance metrics

---

**Last Updated**: January 23, 2026  
**Status**: ✅ Complete System Documentation (Expanded)
