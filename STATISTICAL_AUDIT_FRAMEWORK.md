# SwiftBolt ML - Comprehensive Statistical Audit Framework

**Date Generated:** January 23, 2026  
**Purpose:** Statistical validation of data processing pipeline, multi-timeframe predictions, and frontend data consistency  
**Scope:** End-to-end flow from data ingestion → multiframe predictions → charting application

---

## Executive Summary

This audit validates the statistical integrity and operational efficiency of your SwiftBolt ML processing pipeline by:

1. **Identifying script competition** - Multiple scripts processing same data
2. **Validating statistical outputs** - Ensuring predictions meet quality thresholds
3. **Verifying data consistency** - Frontend charts reflect saved predictions
4. **Measuring latency** - From ingestion to frontend display
5. **Detecting bottlenecks** - Which processing steps consume most resources

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

#### Category E: Frontend/Display Scripts
- [ ] `chart_data_provider.py` - Data for charts
- [ ] `real_time_update.py` - Streaming updates
- [ ] `prediction_overlay.py` - Prediction rendering
- [ ] **Competition Check:** Are multiple sources feeding frontend?

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
⚠ Issues Found: [list]
→ Recommendations: [actions]
```

#### Stage 6: Frontend Consistency
```
✓ Chart-DB Consistency: [%] match
✓ Display Latency: [ms] (target: <2s)
✓ Multi-TF Sync: [status]
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

[CRITICAL]
  ☐ Issue: [description]
    Action: [specific steps]
    Impact: [why it matters]
    Effort: [time estimate]

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
  → Consolidate competing scripts
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
```

---

**Generated by SwiftBolt ML Audit Framework**  
*Next: Run the local analysis script to populate this framework with actual data*
