# SwiftBolt ML - Comprehensive Statistical Audit Framework

**Date Generated:** January 23, 2026  
**Last Updated:** January 24, 2026 (ML forecast database constraint fix implemented)  
**Purpose:** Statistical validation of data processing pipeline, multi-timeframe predictions, and frontend data consistency  
**Scope:** End-to-end flow from data ingestion → multiframe predictions → charting application  
**Status:** Frontend optimizations ✅ COMPLETE | Multi-leg options ranking automation ✅ COMPLETE | ML forecast database fix ✅ COMPLETE

---

## Executive Summary

This audit validates the statistical integrity and operational efficiency of your SwiftBolt ML processing pipeline by:

1. **Identifying script competition** - Multiple scripts processing same data
2. **Validating statistical outputs** - Ensuring predictions meet quality thresholds
3. **Verifying data consistency** - Frontend charts reflect saved predictions
4. **Measuring latency** - From ingestion to frontend display
5. **Detecting bottlenecks** - Which processing steps consume most resources
6. **Data refresh automation** - Ensuring multi-leg strategies have current options data

---

## Part 1: Data Flow Architecture

### Current Pipeline Stages

```
┌─────────────────────────────────────────────────────────────┐
│ STAGE 1: DATA INGESTION                                     │
│ ─────────────────────────────────────────────────────────── │
│ Source: Alpaca / Finnhub / Polygon / Yahoo Finance         │
│ Operation: Fetch OHLCV data for configured symbols         │
│ Frequency: Real-time + scheduled batch                      │
│ Output: Raw market data → Supabase timeseries tables        │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 2: DATA VALIDATION & CLEANING                         │
│ ─────────────────────────────────────────────────────────── │
│ Operations:                                                  │
│  • Check for missing bars (gap detection)                   │
│  • Validate OHLC relationships (High ≥ Close, etc)         │
│  • Detect duplicates and stale data                         │
│  • Calculate technical indicators (RSI, MACD, BB, KDJ)      │
│ Output: Cleaned data + indicators → feature_engineering    │
│ Metrics to Validate:                                        │
│  • Missing bar % (target: <0.5%)                            │
│  • Outlier detection (±3σ threshold)                        │
│  • Data freshness (lag from market close)                   │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 3: MULTI-TIMEFRAME FEATURE ENGINEERING               │
│ ─────────────────────────────────────────────────────────── │
│ Timeframes: 15min, 1h, 4h, daily                            │
│ Operations:                                                  │
│  • Resample OHLCV to each timeframe                         │
│  • Calculate indicators per timeframe                        │
│  • Align time-series (forward-fill missing periods)        │
│  • Create feature matrix [features × timeframes × symbols] │
│ Output: Feature matrix → ml_features table                  │
│ Metrics to Validate:                                        │
│  • Temporal alignment (no time gaps)                        │
│  • Feature nullity (target: 0%)                             │
│  • Feature distributions (check for NaN, Inf)              │
│  • Cross-timeframe correlation validity                     │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 4: MODEL PREDICTION (Multi-Timeframe)                │
│ ─────────────────────────────────────────────────────────── │
│ Models Per Timeframe:                                       │
│  • XGBoost (short-term trend detection)                     │
│  • ARIMA-GARCH (volatility modeling)                        │
│  • Transformer (sequence patterns)                          │
│  • Ensemble (voting classifier)                             │
│ Operations:                                                  │
│  • Load trained models                                      │
│  • Generate predictions (up/down/neutral)                   │
│  • Calculate prediction probabilities                       │
│  • Create confidence scores                                 │
│ Output: Predictions → predictions table                     │
│ Metrics to Validate:                                        │
│  • Model prediction consistency (same input = same output)  │
│  • Probability calibration (P(class) ∈ [0,1])              │
│  • Cross-model agreement (ensembled models)                 │
│  • Temporal prediction validity (forward-looking)           │
│  • Prediction distribution (check for bias)                 │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 5: PREDICTION STORAGE & AGGREGATION                  │
│ ─────────────────────────────────────────────────────────── │
│ Operations:                                                  │
│  • Store predictions in timeseries_predictions table        │
│  • Aggregate multi-frame predictions to single score        │
│  • Calculate weighted consensus across timeframes           │
│ Output: Consensus predictions ready for frontend            │
│ Metrics to Validate:                                        │
│  • Storage completeness (all predictions saved)             │
│  • Timestamp consistency                                    │
│  • Aggregation logic correctness                            │
│  • Data integrity in database                              │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 6: FRONTEND CHART RENDERING                          │
│ ─────────────────────────────────────────────────────────── │
│ Operations:                                                  │
│  • Query predictions from Supabase                          │
│  • Fetch latest OHLCV data                                  │
│  • Render charts (TradingView Lightweight Charts)           │
│  • Display prediction overlays/markers                      │
│ Output: Real-time charting with prediction annotations      │
│ Metrics to Validate:                                        │
│  • Data freshness (chart lag)                               │
│  • Chart-DB consistency (displayed = stored)                │
│  • Rendering latency                                        │
│  • Multi-timeframe chart sync                               │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 7: DATA REFRESH AUTOMATION (✅ IMPLEMENTED)          │
│ ─────────────────────────────────────────────────────────── │
│ Operations:                                                  │
│  • Auto-queue options ranking for multi-leg strategy symbols│
│  • Trigger on strategy create/reopen                        │
│  • Ensure options data freshness for P&L calculations       │
│ Output: Automatic options data refresh                      │
│ Implementation:                                             │
│  • Database triggers on options_strategies table           │
│  • Migration: 20260123000000_multi_leg_options_ranking_trigger│
│  • Priority 2 ranking jobs (higher than watchlist)         │
│ Metrics to Validate:                                        │
│  • Multi-leg symbols with ranking jobs (target: 100%)      │
│  • Options data freshness (target: <1 hour)                │
│  • Trigger latency (target: <1 second)                      │
│  • Ranking job priority distribution                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Part 2: Statistical Validation Metrics

### 2.1 Data Quality Metrics

| Metric | Target | Acceptable Range | Impact if Failed |
|--------|--------|------------------|------------------|
| **Missing Data %** | <0.5% | <2% | Bias in predictions |
| **Data Freshness (lag)** | <60s | <5min | Stale predictions |
| **Duplicate Records** | 0 | 0-1% | Double-counting bias |
| **OHLC Validity** | 100% | >99% | Invalid indicators |
| **Indicator NaN %** | 0% | <1% | Feature incompleteness |

### 2.2 Feature Engineering Validation

| Metric | Target | Method | Acceptable Range |
|--------|--------|--------|------------------|
| **Temporal Alignment** | Perfect sync | Compare timestamps across timeframes | Zero gaps |
| **Cross-TF Correlation** | 0.6-0.9 | Pearson correlation between timeframe features | 0.4-0.95 |
| **Feature Stationarity** | ADF p-value | Augmented Dickey-Fuller test | p > 0.05 (non-stationary is OK for levels) |
| **Multicollinearity** | VIF < 5 | Variance Inflation Factor | VIF < 10 acceptable |
| **Feature Distribution** | Normal or known | Shapiro-Wilk test or visual inspection | p > 0.05 ideal |

### 2.3 Prediction Quality Metrics

| Metric | Calculation | Target | Notes |
|--------|-------------|--------|-------|
| **Prediction Consistency** | Same input → Same output | 100% | Determinism check |
| **Probability Calibration** | Brier Score | <0.2 | Predicted prob matches actual frequency |
| **Model Agreement** | Cohen's kappa (multi-model) | >0.6 | Ensemble coherence |
| **Prediction Variance** | σ(prob per symbol) | 0.15-0.35 | Not all predictions same confidence |
| **Directional Accuracy** | % correct direction | >52% | Better than random (50%) |
| **Prediction Bias** | Mean of (predicted - actual) | ±0.05 | No systematic over/under prediction |

### 2.4 Temporal Metrics

| Stage | Metric | Target Latency | Acceptable |
|-------|--------|----------------|------------|
| Ingestion → Storage | Data write latency | <10s | <30s |
| Storage → Features | Feature calc time | <15s per symbol | <45s |
| Features → Prediction | Model inference | <5s per symbol | <15s |
| Prediction → Storage | Write predictions | <5s | <15s |
| Storage → Frontend Query | Frontend fetch | <2s | <5s |
| **Total E2E Latency** | **Ingestion → Display** | **<40s** | **<90s** |

### 2.5 Database Integrity Metrics (✅ RESOLVED - 2026-01-24)

| Metric | Target | Status | Notes |
|--------|--------|--------|-------|
| **Constraint Alignment** | Schema matches code expectations | ✅ RESOLVED | Unique constraints must match ON CONFLICT clauses |
| **Upsert Success Rate** | 100% | ✅ RESOLVED | All forecasts now save successfully |
| **Schema Evolution** | Migrations applied correctly | ✅ RESOLVED | timeframe column constraint updated |
| **Data Persistence** | All predictions saved | ✅ RESOLVED | 40/40 forecasts saved in production test |

#### ML Forecast Database Constraint Fix (✅ COMPLETE)

**Problem Identified:**
- **Date**: 2026-01-24
- **Symptom**: All ML forecasts failing to save with PostgreSQL error `42P10`
- **Error**: `'there is no unique or exclusion constraint matching the ON CONFLICT specification'`
- **Impact**: 🔴 **CRITICAL** - Zero forecasts persisted despite successful Python processing

**Root Cause:**
- Python code: `upsert(..., on_conflict="symbol_id,timeframe,horizon")`
- Database constraint: `UNIQUE(symbol_id, horizon)` ← **Missing `timeframe`!**
- Schema evolution issue: `timeframe` column added but constraint not updated

**Solution Implemented:**
- **Migration**: `20260124000000_fix_ml_forecasts_unique_constraint.sql`
- **Action**: Updated unique constraint to `UNIQUE(symbol_id, timeframe, horizon)`
- **Status**: ✅ Applied and verified in production

**Verification Results:**
- ✅ Migration applied successfully
- ✅ Production test: 5/5 symbols processed, 40/40 forecasts saved
- ✅ Zero constraint violations
- ✅ All forecasts queryable in `ml_forecasts` table

**Related Documentation:**
- `ML_FORECAST_DATABASE_FIX.md` - Detailed fix documentation
- Migration: `supabase/migrations/20260124000000_fix_ml_forecasts_unique_constraint.sql`

---

## Part 3: Script Dependency & Competition Analysis

### 3.1 Script Identification Checklist

Locate and document these script categories:

#### Category A: Data Ingestion Scripts
- [ ] `fetch_market_data.py` - Primary data fetching
- [ ] `alpaca_polling.py` - Real-time polling
- [ ] `scheduled_batch_fetch.py` - Batch ingestion
- [ ] Any cron-based data collection scripts
- [ ] **Competition Check:** Do multiple scripts fetch same symbols simultaneously?

#### Category B: Feature Engineering Scripts
- [ ] `technical_indicators.py` - Indicator calculation
- [ ] `feature_engineering.py` - ML features
- [ ] `multi_timeframe_features.py` - Multi-TF logic
- [ ] `indicator_cache.py` - Indicator caching
- [ ] **Competition Check:** Are indicators calculated multiple times?

#### Category C: Prediction Scripts
- [ ] `predict_xgboost.py` - XGBoost predictions
- [ ] `predict_arima_garch.py` - ARIMA-GARCH predictions
- [ ] `predict_transformer.py` - Transformer predictions
- [ ] `ensemble_predictor.py` - Ensemble voting
- [ ] `multi_timeframe_predictor.py` - Multi-TF prediction logic
- [ ] **Competition Check:** Are multiple predictors running for same timeframe?

#### Category D: Storage & Aggregation Scripts
- [ ] `save_predictions.py` - Store predictions
- [ ] `aggregate_predictions.py` - Aggregate multi-TF
- [ ] `prediction_consensus.py` - Consensus calculation
- [ ] `update_frontend_cache.py` - Cache update
- [ ] **Competition Check:** Are predictions saved multiple times?

#### Category E: Frontend/Display Scripts (Client-Side)
- [x] **Request Deduplication** - Actor-based `RequestDeduplicator` in `APIClient.swift` (✅ IMPLEMENTED)
- [x] **State Management** - Deferred `didSet` updates to prevent cascading state changes (✅ IMPLEMENTED)
- [x] **Debouncing** - 0.1s debounce on chart loads and symbol changes (✅ IMPLEMENTED)
- [x] **Task Cancellation** - Proper cleanup of in-flight requests (✅ IMPLEMENTED)
- [ ] **Competition Check:** Are multiple sources feeding frontend? (✅ MITIGATED via deduplication)

### 3.2 Competition Detection Matrix

For each pair of scripts in same category:

```
Script A vs Script B:
┌─────────────────────────────────────┐
│ Do they operate on same data? YES/NO │
│ Do they write same tables? YES/NO    │
│ Run same time? YES/NO                │
│ Possible race condition? YES/NO       │
│ Should one replace other? YES/NO      │
└─────────────────────────────────────┘
```

### 3.2.1 Frontend Request Deduplication (✅ IMPLEMENTED)

**Problem Identified:** Multiple simultaneous API calls for the same endpoint (e.g., 4x validation calls, 2x chart loads, 2x strategy detail fetches)

**Solution Implemented:**
- **Actor-based Request Deduplication** (`APIClient.swift`)
  - `RequestDeduplicator` actor tracks in-flight requests by URL
  - Duplicate requests return existing task result instead of creating new network call
  - Thread-safe async/await compatible (Swift 6 compliant)
  - Automatic cleanup via `Task.detached` in defer blocks

**Impact:**
- ✅ Eliminates duplicate API calls at the network layer
- ✅ Reduces server load and improves response times
- ✅ Prevents race conditions from concurrent requests
- ✅ Works transparently for all API endpoints

**Metrics to Monitor:**
- Duplicate request rate (target: <5% of total requests)
- Request deduplication hit rate (target: >80% for common endpoints)
- Network request count per user action (target: 1 per action)

### 3.3 Recommended Script Architecture

**Optimized Single-Pipeline Approach:**

```
Data In (Single Entry Point)
  ↓
[fetch_market_data.py] ← Single responsibility
  ↓
[technical_indicators.py] ← Calculate once
  ↓
[multi_timeframe_features.py] ← Resample once
  ↓
[ensemble_predictor.py] ← Multi-model voting
  ├─→ [predict_xgboost.py]
  ├─→ [predict_arima_garch.py]
  └─→ [predict_transformer.py]
  ↓
[aggregate_predictions.py] ← Consensus once
  ↓
[save_predictions.py] ← Write once
  ↓
Frontend Display (Single Query)
```

### 3.3.1 Frontend Architecture Improvements (✅ IMPLEMENTED)

**State Management Optimization:**
- **Deferred `didSet` Updates** - All `@Published` property `didSet` handlers now use `Task { @MainActor in }` to defer updates to next run loop
  - Prevents "Publishing changes from within view updates" warnings
  - Eliminates cascading state update problems
  - Files: `AppViewModel.swift`, `ChartViewModel.swift`

**Debouncing & Cancellation:**
- **Chart Loading Debounce** - 0.1s debounce on `selectedSymbol` and `timeframe` changes
  - Prevents rapid successive chart loads
  - Cancels previous load tasks before starting new ones
  - File: `ChartViewModel.swift`

**Request Lifecycle Management:**
- **Task Tracking** - ViewModels track in-flight tasks and cancel them when superseded
  - `ValidationViewModel`: `refreshTask` prevents duplicate validation calls
  - `MultiLegViewModel`: `detailLoadTask` prevents duplicate strategy detail fetches
  - `ChartViewModel`: `loadTask` prevents concurrent chart loads

**Auto-Refresh Fix:**
- **Timestamp Calculation** - Fixed auto-refresh timer bug (was showing 63B seconds)
  - Properly handles `.distantPast` initialization
  - Correctly calculates time intervals using `Date().timeIntervalSince()`
  - File: `ChartViewModel.swift` (line ~1601)

### 3.3.2 Multi-Leg Strategy Options Ranking Automation (✅ IMPLEMENTED)

**Problem Identified:** 
- Multi-leg strategies require current options data for accurate P&L calculations
- Symbols used in multi-leg strategies (e.g., MU) were not automatically added to options ranking refresh
- Users had to manually add symbols to watchlist or trigger ranking jobs
- Result: Stale options data for multi-leg strategy evaluations

**Solution Implemented:**
- **Database Triggers** - Automatic options ranking job queuing when multi-leg strategies are created
  - Migration: `20260123000000_multi_leg_options_ranking_trigger.sql`
  - Applied via Supabase MCP: ✅ Successfully deployed
  - Location: `supabase/migrations/20260123000000_multi_leg_options_ranking_trigger.sql`

**Implementation Details:**
1. **Trigger on Strategy Create** (`trigger_queue_ranking_on_multi_leg_create`)
   - Fires: `AFTER INSERT ON options_strategies` when `status = 'open'`
   - Action: Automatically queues options ranking job for underlying symbol
   - Priority: 2 (higher than watchlist default priority 1)
   - Deduplication: Checks for existing pending/running jobs within last hour

2. **Trigger on Strategy Reopen** (`trigger_queue_ranking_on_multi_leg_reopen`)
   - Fires: `AFTER UPDATE ON options_strategies` when status changes from `closed/expired` → `open`
   - Action: Queues ranking job to refresh options data
   - Same deduplication logic as create trigger

3. **Helper Functions:**
   - `get_multi_leg_strategy_symbols()` - Returns all symbols with active multi-leg strategies
   - `queue_multi_leg_strategy_ranking_jobs()` - Can be called by scheduled jobs to refresh all multi-leg symbols

**Impact:**
- ✅ Automatic options data refresh for multi-leg strategy symbols
- ✅ No need to manually add symbols to watchlist
- ✅ Ensures current options prices for accurate P&L calculations
- ✅ Works even if symbol is not in watchlist
- ✅ Higher priority (2) ensures faster processing than watchlist jobs

**Verification Results:**
- ✅ All 4 functions created successfully
- ✅ Both triggers created on `options_strategies` table
- ✅ Test strategy created on MU: `1f94a5a6-4e81-449e-ba45-54de6ba0d8e2`
- ✅ Ranking job automatically queued: `aea1e522-2538-4771-bfda-ac1185176462`
- ✅ Job created at exact same timestamp as strategy (0.000000 seconds difference)
- ✅ Priority 2 confirmed (higher than watchlist default)

**Metrics to Monitor:**
- Multi-leg strategy symbols with ranking jobs queued (target: 100%)
- Time from strategy creation to ranking job queue (target: <1 second)
- Options data freshness for multi-leg strategies (target: <1 hour old)
- Ranking job priority distribution (multi-leg should be priority 2)

**Related Documentation:**
- `DATA_REFRESH_AUDIT.md` - Comprehensive data refresh audit
- `MIGRATION_APPLICATION_STATUS.md` - Migration deployment status

---

## Part 4: Multi-Timeframe Prediction Validation

### 4.1 Per-Timeframe Metrics

For each timeframe (15min, 1h, 4h, daily), validate:

```python
PER_TIMEFRAME_METRICS = {
    'timeframe': '15min|1h|4h|daily',
    'validation': {
        'prediction_count': 'Expected # of predictions',
        'avg_confidence': 'Mean prediction probability',
        'confidence_std': 'Should be 0.15-0.35',
        'direction_distribution': {
            'UP': '% of UP predictions',
            'DOWN': '% of DOWN predictions',
            'NEUTRAL': '% of NEUTRAL predictions'
        },
        'temporal_coverage': 'Records for all timestamps',
        'lookback_validity': 'Predictions are forward-looking',
    },
    'quality_scores': {
        'consistency_score': '0-100 (determinism)',
        'calibration_score': '0-100 (prob accuracy)',
        'ensemble_agreement': '0-100 (model agreement)',
        'overall_quality': '0-100 (composite)'
    }
}
```

### 4.2 Cross-Timeframe Coherence

Validate relationships between timeframes:

| Check | Formula | Target | Notes |
|-------|---------|--------|-------|
| **Trend Alignment** | % predictions same direction across TF | >70% | Higher TF more stable |
| **Signal Strength** | Correlation of confidence scores | >0.5 | Timeframes should agree |
| **Prediction Layering** | Daily more bullish than hourly? | Logical | Reflects market structure |
| **Disagreement Freq** | When TFs disagree on direction | <30% | Should be rare |

---

## Part 5: Frontend Data Consistency

### 5.1 Chart-Database Consistency Checks

```python
Frontend Consistency Validation:
├─ Query DB for latest predictions
├─ Fetch frontend chart data via API
├─ Compare:
│  ├─ Latest price matches: YES/NO
│  ├─ Prediction arrows overlay correctly: YES/NO
│  ├─ Timeframe switching reflects DB: YES/NO
│  ├─ Historical data consistency: YES/NO
│  └─ Indicators match calculated values: YES/NO
└─ Measure latency (DB update → Chart display)
```

### 5.2 Real-Time Update Validation

- **Update Frequency:** How often frontend receives predictions
- **Update Latency:** Delay from prediction save → frontend display
- **Multi-Timeframe Sync:** Do all TF charts update together?
- **Stale Data Detection:** Are old predictions being displayed?

### 5.3 Frontend Request Efficiency (✅ IMPLEMENTED)

**Before Implementation:**
- ❌ 4x duplicate validation API calls per symbol selection
- ❌ 2x chart loads (immediate + auto-refresh)
- ❌ 2x multi-leg strategy detail fetches
- ❌ 10+ "Publishing changes from within view updates" warnings
- ❌ Auto-refresh timer showing incorrect intervals (63B seconds)

**After Implementation:**
- ✅ 1x API call per endpoint per user action (via deduplication)
- ✅ 1x chart load per symbol selection (debounced + cancellation)
- ✅ 1x strategy detail fetch (task tracking prevents duplicates)
- ✅ 0 state management warnings (deferred updates)
- ✅ Correct auto-refresh intervals (proper timestamp calculation)

**Metrics to Validate:**
- API call count per symbol selection (target: ≤3 total calls)
- Chart load count per selection (target: 1)
- State update warnings (target: 0)
- Auto-refresh interval accuracy (target: ±5% of expected)

---

## Part 6: Local Analysis Script Output

After running the audit scripts locally, generate this summary document:

### 6.1 Executive Findings

```
═══════════════════════════════════════════════════════════
STATISTICAL AUDIT SUMMARY - [TIMESTAMP]
═══════════════════════════════════════════════════════════

OVERALL PIPELINE HEALTH: [GREEN/YELLOW/RED]
SCRIPT COMPETITION LEVEL: [NONE/MINOR/SIGNIFICANT]
PREDICTION QUALITY SCORE: [0-100]
FRONTEND CONSISTENCY: [GREEN/YELLOW/RED]
RECOMMENDED ACTIONS: [1-5 priority items]

───────────────────────────────────────────────────────────
```

### 6.2 Detailed Findings by Stage

#### Stage 1: Data Ingestion
```
✓ Data Freshness: [value] (target: <60s)
✓ Missing Data: [%] (target: <0.5%)
✓ Duplicate Records: [count] (target: 0)
⚠ Issues Found: [list]
→ Recommendations: [actions]
```

#### Stage 2: Validation & Cleaning
```
✓ OHLC Validity: [%] (target: 100%)
✓ Indicator NaN: [%] (target: 0%)
✓ Outliers Detected: [count] (method: ±3σ)
⚠ Issues Found: [list]
→ Recommendations: [actions]
```

#### Stage 3: Feature Engineering
```
✓ Temporal Alignment: [status]
✓ Feature Nullity: [%] (target: 0%)
✓ Cross-TF Correlation: [avg r-value]
⚠ Issues Found: [list]
→ Recommendations: [actions]
```

#### Stage 4: Model Predictions
```
✓ Prediction Consistency: [%] (target: 100%)
✓ Probability Calibration: [Brier score]
✓ Model Agreement: [Cohen's kappa]
✓ Directional Accuracy: [%] (target: >52%)
⚠ Issues Found: [list]
→ Recommendations: [actions]
```

#### Stage 5: Storage & Aggregation
```
✓ Storage Completeness: [%] (target: 100%)
✓ Timestamp Consistency: [status]
✓ Aggregation Logic: [verified/needs_review]
✓ Database Constraints: ✅ RESOLVED (2026-01-24) - ml_forecasts unique constraint fixed
⚠ Issues Found: [list]
→ Recommendations: [actions]
```

#### Stage 6: Frontend Consistency
```
✓ Chart-DB Consistency: [%] match
✓ Display Latency: [ms] (target: <2s)
✓ Multi-TF Sync: [status]
✓ Request Deduplication: [%] duplicate requests prevented (target: >80%)
✓ State Management: [count] warnings (target: 0)
✓ API Call Efficiency: [count] calls per symbol selection (target: ≤3)
⚠ Issues Found: [list]
→ Recommendations: [actions]
```

### 6.3 Script Competition Analysis

```
SCRIPT DEPENDENCY AUDIT
═════════════════════════

Active Scripts Identified: [N]

Script Category: [Category]
├─ Script A: [path] - [status] ✓/⚠/✗
│  ├─ Purpose: [description]
│  ├─ Frequency: [schedule]
│  └─ Last Run: [timestamp]
├─ Script B: [path] - [status]
└─ Script C: [path] - [status]

Competition Detected:
├─ Scripts A & B both fetch market data (RACE CONDITION)
├─ Scripts D & E both calculate indicators (DUPLICATE WORK)
└─ Scripts F & G both save predictions (POTENTIAL CONFLICT)

Recommendations:
1. Consolidate Scripts A & B into single fetcher
2. Cache indicators from single calculation
3. Implement locking on prediction writes
```

### 6.3.1 Frontend Request Competition (✅ MITIGATED)

```
FRONTEND REQUEST DEDUPLICATION AUDIT
═════════════════════════════════════

Implementation Status: ✅ COMPLETE

Mechanism: Actor-based RequestDeduplicator
├─ Location: APIClient.swift
├─ Thread Safety: Swift 6 actor (async-safe)
├─ Scope: All API endpoints via performRequest()
└─ Cleanup: Automatic via Task.detached in defer

Duplicate Request Prevention:
├─ Validation API: 4x → 1x calls (75% reduction)
├─ Chart Data: 2x → 1x loads (50% reduction)
├─ Strategy Detail: 2x → 1x fetches (50% reduction)
└─ Overall: ~60% reduction in duplicate requests

State Management Improvements:
├─ didSet Deferral: All @Published properties use Task { @MainActor in }
├─ Warnings Eliminated: 10+ → 0 "Publishing changes" warnings
├─ Debouncing: 0.1s debounce on chart loads
└─ Task Cancellation: Proper cleanup prevents race conditions

Metrics Achieved:
├─ API Calls per Symbol Selection: 4 → 1 (validation)
├─ Chart Loads per Selection: 2 → 1
├─ State Update Warnings: 10+ → 0
└─ Auto-Refresh Accuracy: Fixed (was showing 63B seconds)

Recommendations:
1. ✅ Request deduplication implemented
2. ✅ State management optimized
3. ✅ Debouncing and cancellation in place
4. → Monitor deduplication hit rate in production
5. → Track API call reduction metrics
```

### 6.4 Performance Bottleneck Analysis

```
LATENCY BREAKDOWN (E2E: X.XXs total)
═════════════════════════════════════

Data Ingestion:        [XXXms]  ███░░░░░░  [Y%]
Validation:            [XXXms]  ██░░░░░░░  [Y%]
Feature Engineering:   [XXXms]  █████░░░░  [Y%] ← BOTTLENECK?
Prediction:            [XXXms]  ████░░░░░  [Y%]
Storage:               [XXXms]  ██░░░░░░░  [Y%]
Frontend Query:        [XXXms]  █░░░░░░░░  [Y%]

Critical Path: [Identify slowest stage]
Optimization Opportunity: [Priority recommendation]
```

### 6.5 Multi-Timeframe Quality Report

```
MULTI-TIMEFRAME PREDICTION QUALITY
═══════════════════════════════════

Timeframe: 15min
  Prediction Count: X
  Avg Confidence: 0.XX (target: 0.50-0.70)
  Directional Accuracy: XX% (target: >52%)
  Consistency Score: XX/100
  Calibration Score: XX/100
  Overall Quality: XX/100 ✓/⚠/✗

Timeframe: 1h
  Prediction Count: X
  Avg Confidence: 0.XX
  Directional Accuracy: XX%
  ... [same metrics]

Timeframe: 4h
  ... [same metrics]

Timeframe: daily
  ... [same metrics]

Cross-Timeframe Analysis:
  Trend Alignment: XX% (target: >70%)
  Signal Strength: r=X.XX (target: >0.5)
  Disagreement Frequency: X% (target: <30%)
  Overall Coherence: [HIGH/MEDIUM/LOW]
```

### 6.6 Action Items & Recommendations

```
PRIORITY ACTIONS (Next 24 hours)
════════════════════════════════

[COMPLETED] ✅ Frontend Request Deduplication
  ✓ Issue: Multiple duplicate API calls causing inefficiency
    Action: Implemented actor-based RequestDeduplicator
    Impact: 60% reduction in duplicate requests, improved performance
    Effort: Completed

[COMPLETED] ✅ State Management Optimization
  ✓ Issue: SwiftUI "Publishing changes" warnings and cascading updates
    Action: Deferred all didSet updates to next run loop
    Impact: Eliminated warnings, prevented undefined behavior
    Effort: Completed

[COMPLETED] ✅ Request Lifecycle Management
  ✓ Issue: Concurrent requests causing race conditions
    Action: Added task tracking and cancellation in ViewModels
    Impact: Prevents duplicate loads, improves responsiveness
    Effort: Completed

[COMPLETED] ✅ Multi-Leg Strategy Options Ranking Automation
  ✓ Issue: Multi-leg strategies require current options data but symbols weren't auto-refreshed
    Action: Implemented database triggers to auto-queue options ranking jobs
    Impact: Ensures options data stays current for multi-leg P&L calculations
    Migration: 20260123000000_multi_leg_options_ranking_trigger.sql
    Status: Applied and verified via Supabase MCP
    Effort: Completed

[COMPLETED] ✅ ML Forecast Database Constraint Fix
  ✓ Issue: All ML forecasts failing to save with PostgreSQL error 42P10 (constraint mismatch)
    Action: Updated unique constraint from UNIQUE(symbol_id, horizon) to UNIQUE(symbol_id, timeframe, horizon)
    Impact: Enables multi-timeframe forecasting, all 40 forecasts now save successfully
    Migration: 20260124000000_fix_ml_forecasts_unique_constraint.sql
    Status: Applied and verified in production (GitHub Actions run #21306769498)
    Verification: 5/5 symbols processed, 40/40 forecasts saved, 0 errors
    Effort: Completed

[HIGH]
  ☐ Issue: [description]
    Action: [specific steps]
    Impact: [why it matters]
    Effort: [time estimate]

[MEDIUM]
  ☐ Issue: [description]
    Action: [specific steps]
    Impact: [why it matters]
    Effort: [time estimate]

Optimization Opportunities (Next Week)
  → Monitor request deduplication hit rate in production
  → Track API call reduction metrics over time
  → Monitor multi-leg strategy ranking job queue rate
  → Verify options data freshness for multi-leg strategies
  → Consolidate competing backend scripts (if any)
  → Cache frequently calculated values
  → Implement async processing for heavy computations
  → Add database indexes for prediction queries
```

---

## Part 7: How to Use This Audit Framework

### Phase 1: Review (You are here)
- ✓ Read this framework
- ✓ Understand the data flow
- ✓ Identify which metrics matter most to you

### Phase 2: Prepare
- [ ] Locate all Python scripts in your project
- [ ] List them by category (ingestion, features, prediction, storage, frontend)
- [ ] Document schedule/frequency of each
- [ ] Note which scripts you think might compete

### Phase 3: Analyze
- [ ] Run the local audit script (see Part 8 below)
- [ ] Collect metrics from database queries
- [ ] Test prediction consistency
- [ ] Measure latencies
- [ ] Validate frontend charts

### Phase 4: Report
- [ ] Generate audit summary document (auto-created by script)
- [ ] Review findings
- [ ] Prioritize recommendations
- [ ] Plan remediation

---

## Part 8: Next Steps

**Your Request:** "review and then review the scripts locally and write a local file auditing after analyzed"

**What we need:**

1. **Script Inventory** - Please provide a list of your active Python scripts with their file paths
2. **Database Access** - We need to query your Supabase/database for statistics
3. **Execution Plan** - Should we:
   - [ ] Start with data ingestion analysis?
   - [ ] Focus on feature engineering validation?
   - [ ] Check multi-timeframe prediction quality?
   - [ ] Validate frontend consistency?
   - [ ] Analyze all stages?

4. **Output Preference** - Where should local audit reports be saved?
   - [ ] `/Users/ericpeterson/SwiftBolt_ML/audit_results/`
   - [ ] `/Users/ericpeterson/SwiftBolt_ML/ml/audit_results/`
   - [ ] Elsewhere?

---

## Appendix: Recommended Tools & Queries

### Database Diagnostic Queries

```sql
-- Data freshness check
SELECT symbol, MAX(timestamp) as latest_data
FROM timeseries_data
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY symbol
ORDER BY latest_data DESC;

-- Missing data detection
SELECT symbol, timeframe,
       COUNT(*) as bar_count,
       (NOW() - MIN(timestamp))::interval / INTERVAL '1 minute' as minutes_span,
       COUNT(*) * 100.0 / ((NOW() - MIN(timestamp))::interval / INTERVAL '1 minute') as bar_percentage
FROM timeseries_data
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY symbol, timeframe;

-- Prediction quality metrics
SELECT timeframe,
       COUNT(*) as prediction_count,
       AVG(confidence) as avg_confidence,
       STDDEV(confidence) as confidence_std,
       COUNT(DISTINCT direction) as unique_directions
FROM predictions
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY timeframe;

-- Feature completeness
SELECT COUNT(*) FILTER (WHERE value IS NULL) as null_count,
       COUNT(*) FILTER (WHERE value = 'Infinity' OR value = '-Infinity') as infinity_count,
       COUNT(*) as total_records
FROM ml_features
WHERE timestamp > NOW() - INTERVAL '1 hour';

-- Multi-leg strategy options ranking status
SELECT 
    os.underlying_ticker,
    COUNT(DISTINCT os.id) as strategy_count,
    COUNT(DISTINCT rj.id) FILTER (WHERE rj.status IN ('pending', 'running')) as pending_ranking_jobs,
    MAX(rj.created_at) as last_ranking_job_created,
    MAX(rj.priority) as max_priority
FROM options_strategies os
LEFT JOIN ranking_jobs rj ON rj.symbol = os.underlying_ticker 
    AND rj.created_at > NOW() - INTERVAL '24 hours'
WHERE os.status = 'open'
GROUP BY os.underlying_ticker
ORDER BY strategy_count DESC;

-- Options data freshness for multi-leg strategies
SELECT 
    os.underlying_ticker,
    MAX(or_ranks.run_at) as last_ranked_at,
    NOW() - MAX(or_ranks.run_at) as age,
    COUNT(DISTINCT or_ranks.id) as total_ranks
FROM options_strategies os
LEFT JOIN options_ranks or_ranks ON or_ranks.underlying_symbol_id = os.underlying_symbol_id
WHERE os.status = 'open'
GROUP BY os.underlying_ticker
HAVING MAX(or_ranks.run_at) < NOW() - INTERVAL '2 hours' OR MAX(or_ranks.run_at) IS NULL
ORDER BY age DESC NULLS LAST;

-- Database constraint alignment check (ml_forecasts)
SELECT 
    indexname,
    indexdef,
    CASE 
        WHEN indexdef LIKE '%symbol_id%' AND indexdef LIKE '%timeframe%' AND indexdef LIKE '%horizon%' 
        THEN '✅ CORRECT' 
        ELSE '⚠️ MISMATCH' 
    END as constraint_status
FROM pg_indexes
WHERE tablename = 'ml_forecasts' 
AND indexname LIKE 'ux_%'
ORDER BY indexname;

-- ML forecast persistence verification
SELECT 
    COUNT(*) as total_forecasts,
    COUNT(DISTINCT symbol_id) as unique_symbols,
    COUNT(DISTINCT horizon) as unique_horizons,
    COUNT(DISTINCT timeframe) as unique_timeframes,
    MAX(created_at) as latest_forecast,
    NOW() - MAX(created_at) as age
FROM ml_forecasts
WHERE created_at > NOW() - INTERVAL '24 hours';
```

---

**Generated by SwiftBolt ML Audit Framework**  
*Next: Run the local analysis script to populate this framework with actual data*
