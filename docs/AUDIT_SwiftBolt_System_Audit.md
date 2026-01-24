# SwiftBolt_ML System Architecture Audit

**Date**: January 21, 2026  
**Auditor**: AI Assistant  
**Focus**: GitHub Actions Workflows vs Local Scripts, Data Pipeline Overlaps, Dashboard Consolidation

---

## Executive Summary

Your SwiftBolt_ML system is **well-structured overall** but suffers from:
1. **Data Pipeline Fragmentation** - Multiple ingestion paths that could conflict
2. **Dashboard/Model Misalignment** - Statistical validation doesn't match live forecasts
3. **Backend Script Accumulation** - 35+ scripts doing overlapping work
4. **Consolidation Opportunities** - 4-5 legacy workflows still running independently
5. **Swift App Data Tracking Gap** - Multi-timeframe symbol tracking partially deployed

---

## 1. GitHub Actions Workflow Audit

### Current State: Consolidated Architecture ✅

You have successfully consolidated 13 legacy workflows into **4 canonical workflows**:

| Canonical Workflow | Legacy Workflows Replaced | Status | Schedule |
|---|---|---|---|
| `daily-data-refresh.yml` | `backfill-ohlc.yml`, `batch-backfill-cron.yml`, `daily-historical-sync.yml` | ✅ Active | 6 AM UTC daily |
| `intraday-ingestion.yml` | `alpaca-intraday-cron.yml`, `intraday-update.yml`, `intraday-update-v2.yml` | ✅ Active | Every 15 min (market hours) |
| `intraday-forecast.yml` | Legacy forecast generation | ✅ Active | Triggered by ingestion |
| `ml-orchestration.yml` | `ml-forecast.yml`, `ml-evaluation.yml`, `data-quality-monitor.yml`, `drift-monitoring.yml`, `options-nightly.yml` | ✅ Active | 4 AM UTC weekdays |

**Good**: Proper workflow_run triggers, concurrency management, matrix strategies for timeframes.

### ⚠️ Issues Identified

#### 1. **Legacy Workflows Still Active (Non-Consolidated)**

31 workflows exist, but only ~8 are truly canonical. The rest are:

| Workflow | Status | Issue |
|---|---|---|
| `alpaca-intraday-cron-fixed.yml` | Disabled | Duplicate of `intraday-ingestion.yml` |
| `backfill-intraday-worker.yml` | Dispatch only | Unclear relationship to `intraday-ingestion.yml` |
| `daily-options-scrape.yml` | Active (market hours) | Separate from ML orchestration, runs independently |
| `job-worker.yml` | Dispatch only | Processes forecast/ranking jobs |
| `orchestrator-cron.yml` | Dispatch only | Supabase orchestrator (manual trigger) |
| `symbol-backfill.yml` | Dispatch only | Purpose unclear |
| `nightly-coverage-check.yml` | Active | Separate CI job |
| `frontend-integration-checks.yml` | Active | Separate CI job |
| `api-contract-tests.yml` | Active | Separate CI job |
| `test-ml.yml` | Active (PR/push) | Separate CI job |

**Problem**: Ambiguity about which workflows can safely be deleted. Several could be consolidated further.

#### 2. **Data Source Conflict: Alpaca vs Polygon/Massive**

From your dashboards and backend scripts:
- **Daily data**: Alpaca API (in `daily-data-refresh.yml`)
- **Intraday data**: Alpaca API (in `intraday-ingestion.yml`)
- **Options data**: Finnhub (in `daily-options-scrape.yml`)
- **Massive API**: Referenced in README but unclear if active

**Question**: Is Massive API still used for data ingestion, or fully replaced by Alpaca?

---

## 2. Data Pipeline Architecture Analysis

### Current Flow

```
┌─────────────────────────────────────────────────────────┐
│                 DATA INGESTION LAYER                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Market Hours (Every 15 min)                            │
│  ┌──────────────────────────────────────────┐          │
│  │ intraday-ingestion.yml                   │          │
│  │ - Fetches M15, H1 bars                   │          │
│  │ - Source: Alpaca API                     │          │
│  │ - Updates: ohlc_bars_v2                  │          │
│  └──────────────────────────────────────────┘          │
│         │                                              │
│         └──▶ intraday-forecast.yml ◀─ Triggers        │
│               - Generates real-time forecasts         │
│               - Updates: indicator_values             │
│                                                         │
│  Daily (6 AM UTC)                                      │
│  ┌──────────────────────────────────────────┐          │
│  │ daily-data-refresh.yml                   │          │
│  │ - Incremental/Full backfill              │          │
│  │ - Fetches M15, H1, H4, D1, W1            │          │
│  │ - Source: Alpaca API                     │          │
│  │ - Updates: ohlc_bars_v2                  │          │
│  └──────────────────────────────────────────┘          │
│         │                                              │
│         └──▶ ml-orchestration.yml ◀─ Triggers        │
│               ├── ml-forecast.yml                     │
│               ├── options-processing.yml             │
│               ├── model-health.yml                   │
│               └── smoke-tests.yml                    │
│                                                         │
│  Daily (Market hours, separate)                        │
│  ┌──────────────────────────────────────────┐          │
│  │ daily-options-scrape.yml                 │          │
│  │ - Options chains & IV                    │          │
│  │ - Source: Finnhub API                    │          │
│  │ - Updates: options_chain_snapshots       │          │
│  └──────────────────────────────────────────┘          │
│                                                         │
└─────────────────────────────────────────────────────────┘
        │                    │                    │
        ▼                    ▼                    ▼
   ┌─────────────┐    ┌─────────────┐    ┌──────────────┐
   │ ohlc_bars_v2│    │  ml_forecasts   │ options_data  │
   │             │    │                 │              │
   └─────────────┘    └─────────────────┘ └──────────────┘
        │                    │                    │
        ▼                    ▼                    ▼
   ┌───────────────────────────────────────────────────────┐
   │           SWIFT APP (ML Predictions Dashboard)        │
   │  ┌─────────────────────────────────────────────────┐ │
   │  │ Statistical Validation Tab                      │ │
   │  │ - Precision: 98.8%                              │ │
   │  │ - Win Rate: 75%+                                │ │
   │  │ - Sharpe Ratio: 1.5+                            │ │
   │  └─────────────────────────────────────────────────┘ │
   │  ┌─────────────────────────────────────────────────┐ │
   │  │ Live AAPL Forecast                              │ │
   │  │ - Price: $246.72                                │ │
   │  │ - Prediction: 40% BEARISH                       │ │
   │  │ - Target: $229.94                               │ │
   │  │ - M15/H1/H4/D1/W1 bars (conflicting?)          │ │
   │  └─────────────────────────────────────────────────┘ │
   └───────────────────────────────────────────────────────┘
```

### ⚠️ Critical Gaps

#### Gap 1: **Intraday Forecast Validation Disconnected**
- `intraday-forecast.yml` generates M15/H1 predictions
- But these predictions are **NOT validated** against historical performance
- Dashboard shows 98.8% precision, but this is from backtesting (not intraday)
- **Missing**: Walk-forward validation for intraday timeframes

#### Gap 2: **Multi-Timeframe Prediction Mismatch**
From your dashboard (AAPL screenshot):
```
M15: BEARISH -48% ($261.16)
H1:  BEARISH -40% ($253.78)
4H:  BEARISH -40% ($262.12)
D1:  BEARISH -40% ($229.94)
W1:  (not shown)
```

**Question**: Are these using the same ensemble model or different models?
- If same: Why do they diverge? (Likely due to different training windows)
- If different: Which prediction should override others?
- **Missing**: Hierarchical reconciliation logic for conflicting predictions

#### Gap 3: **Options Data Not Integrated into Forecasts**
- `daily-options-scrape.yml` runs independently
- Options data (IV, Greeks, chain) not fed into ML forecasts
- Forecasts and options ranks computed separately
- **Missing**: Unified pipeline that combines equity forecasts + options analytics

#### Gap 4: **Statistical Validation Doesn't Cover Live Data**
- Dashboard tab: "Statistical Validation" shows historical backtesting
- But live forecast (40% BEARISH on AAPL) hasn't been validated against recent live data
- **Missing**: Real-time model drift detection

---

## 3. Backend Script Accumulation Analysis

### Script Count by Category

```
Total Scripts: 35+ (excluding tests)

Data Ingestion/Backfill:
├── backfill_missing_data.sh
├── comprehensive_backfill.sh
├── smart_backfill_all.sh (in ml/src/scripts)
├── symbol-backfill workflow
└── (4+ more in backend/scripts/)

Database Operations:
├── 8x SQL scripts (check_aapl_data.sql, verify_latest_available.sql, etc.)
├── 6x shell wrappers (check-database-directly.sh, etc.)
└── 3x TypeScript utilities (test_chart_query.ts, etc.)

Deployment:
├── deploy_watchlist_reload.sh
├── deploy-internal-functions.sh
├── deploy_multi_timeframe.sh
├── verify_deployment.sh
└── apply_migration.sh

Testing/Validation:
├── test_symbol_sync.sh
├── test_v2_setup.sh
├── test-phase2-batch.sh
└── validate_data_quality.sh

Troubleshooting/Cleanup:
├── quick-fix.sh
├── reset-and-continue.sh
├── cleanup-and-restart.sh
└── MANY one-off debug scripts
```

### 🚨 Problems

1. **No Single Source of Truth**
   - `check_aapl_data.sql` vs `diagnose_chart_data_issue.sql` - unclear which to use
   - `deploy_multi_timeframe.sh` vs `deploy-phase2-batch.sh` - unclear which is current
   - Multiple versions of backfill scripts with unclear differences

2. **Script Drift**
   - Each script has its own logic for connecting to Supabase, Alpaca, etc.
   - No shared utility library = duplicate code across 35+ scripts
   - Environment variable handling inconsistent

3. **Deployment Uncertainty**
   - `MULTI_TIMEFRAME_DEPLOYMENT.md` says "complete"
   - But `DEPLOYMENT_STATUS.md` says "blocking issue: empty symbols table"
   - Which document is current?

---

## 4. Swift App Integration Issues

### Symbol Tracking Architecture

**Current State**: Partially deployed, blocked by empty `symbols` table

```
Swift App (SymbolSyncService)
    ├── Watchlist View
    ├── Chart View
    └── Symbol Search
         │
         ▼
    POST /sync-user-symbols (Edge Function)
         │
         ▼
    Database Trigger:
    1. Look up symbol in symbols table ◀── FAILS: Table is empty
    2. Insert user_symbol_tracking
    3. Create job_definitions (m15, h1, h4)
    4. Trigger orchestrator
         │
         ▼
    ohlc_bars_v2 (updated)
```

**Blocking Issue**: The `symbols` table is empty
- Swift app makes successful HTTP 200 calls
- But 0 jobs created because no symbol metadata exists
- Users can add symbols to watchlist, but no backfill triggers

**Options**:
1. **Populate symbols table** manually with common tickers
2. **Auto-create on demand** in Edge Function (lazy loading)
3. **Fetch from external API** (Alpha Vantage symbol list)

---

## 5. Dashboard/Model Validation Issues

### Problem: Three Different "Truth Sources"

| Component | Shows | Uses | Training Window | Issue |
|---|---|---|---|---|
| **Statistical Validation Tab** | Precision 98.8%, Win Rate 75%+ | Backtest data | 3-6 months | Historical accuracy |
| **Live Forecast (AAPL)** | BEARISH 40%, Target $229 | Live market data | Real-time | Current market condition |
| **Multi-TF Consensus** | M15/H1/H4 conflicting % | Separate models? | Unclear | Which model to trust? |

**Key Question**: When these conflict (Backtesting says 98%, live says 40%), how do you decide?

**Missing**: 
- Reconciliation rules
- Confidence scaling
- Real-time validation against live performance

### Problem: Tab Redundancy

| Tab | Purpose | Redundancy Risk |
|---|---|---|
| Overview | High-level status | Shows? |
| Model Performance | Walk-forward validation | vs Statistical Validation? |
| **Statistical Validation** | Backtest metrics | vs Model Performance? |
| Feature Importance | SHAP values? | vs Model Performance? |
| Forecast Accuracy | Prediction accuracy | vs Statistical Validation? |

**Likely**: Statistical Validation and Model Performance use different test sets or methods

---

## 6. Consolidation Recommendations

### Phase 1: Immediate Fixes (1-2 days)

#### 1.1: Fix Symbol Tracking Blocker
```bash
# Populate symbols table
cd backend
psql $DATABASE_URL < scripts/seed-symbols.sql

# Or use Edge Function with auto-create logic
# Edit: supabase/functions/sync-user-symbols/index.ts
# Add upsert for symbols table if not exists
```

#### 1.2: Clarify Validation Windows
```python
# Create unified validation framework
# ml/src/validation/unified_framework.py

class UnifiedValidator:
    def __init__(self):
        self.backtesting_window = "3m"      # Historical
        self.walkforward_window = "2w"      # Recent
        self.live_window = "realtime"       # Current
    
    def get_model_confidence(self, model, symbol):
        """Returns confidence score accounting for all validation methods"""
        backtesting_score = self.get_backtesting_score(model, symbol)
        walkforward_score = self.get_walkforward_score(model, symbol)
        live_drift = self.detect_live_drift(model, symbol)
        
        # Reconcile with clear rules
        return self._reconcile_scores(backtesting_score, 
                                      walkforward_score, 
                                      live_drift)
```

#### 1.3: Consolidate Backend Scripts
```bash
# Create utility library
backend/
├── lib/
│   ├── db.ts          # Shared Supabase logic
│   ├── alpaca.ts      # Shared Alpaca API
│   ├── deployment.ts  # Shared deploy helpers
│   └── validation.ts  # Shared validation
├── scripts/
│   ├── legacy/        # Archive old scripts
│   ├── backfill.sh    # Single authoritative backfill
│   └── deploy.sh      # Single authoritative deploy
```

### Phase 2: Dashboard Redesign (3-5 days)

#### 2.1: Unify Prediction Models

**Before** (Conflicting):
```
Statistical Validation: 98.8% precision (backtesting)
Live Forecast: 40% BEARISH (real-time)
Multi-TF Consensus: M15 -48%, H1 -40%, D1 -40% (diverging)
```

**After** (Reconciled):
```
┌─────────────────────────────────────────────────────────┐
│         UNIFIED ENSEMBLE PREDICTION                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ Ensemble Vote:                                          │
│  • Backtesting Model (XGBoost): BEARISH 95% (3mo data) │
│  • Walk-Forward Validation (RF): NEUTRAL 60% (2w data) │
│  • Live Intraday (LSTM): BEARISH 40% (current)        │
│                                                         │
│ Reconciled Prediction:                                  │
│  • Consensus: BEARISH (2 of 3 models agree)           │
│  • Confidence: 65% (average of recent 2)              │
│  • Drift Detected: YES (backtesting diverged)         │
│                                                         │
│ Recommended Action: HOLD (conflicting signals)         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

#### 2.2: Consolidate Dashboard Tabs

**Before** (Redundant):
- Overview
- Model Performance
- Statistical Validation
- Feature Importance
- Forecast Accuracy

**After** (Clear):
```
Dashboard (Restructured)
├── 📊 Prediction Summary
│   ├── Ensemble consensus (BEARISH/NEUTRAL/BULLISH)
│   ├── Confidence score with sources
│   ├── Model agreement matrix
│   └── Live drift alert
│
├── 📈 Model Health
│   ├── Walk-forward performance (2w rolling)
│   ├── Backtesting baseline (3mo)
│   ├── Feature importance (top 10)
│   └── Data quality check
│
├── 🎯 Real-Time Signals
│   ├── Multi-timeframe predictions (M15/H1/H4/D1/W1)
│   ├── Reconciliation logic (why they diverge)
│   ├── Support & Resistance
│   └── Recent price action
│
└── 🔧 System Status
    ├── Data freshness
    ├── Model retraining schedule
    ├── Options data integration status
    └── Active alerts
```

### Phase 3: ML Pipeline Unification (1-2 weeks)

#### 3.1: Integrate Options into Forecasts

```python
# ml/src/options_integrated_forecaster.py

class OptionsIntegratedForecaster:
    """Combines equity predictions + options analytics"""
    
    def generate_forecast(self, symbol):
        # 1. Get equity forecast (existing)
        equity_forecast = self.equity_forecaster.predict(symbol)
        
        # 2. Get current options chain data
        options_chain = self.get_current_options_chain(symbol)
        
        # 3. Compute implied volatility skew
        iv_skew = self.compute_iv_skew(options_chain)
        
        # 4. Reconcile with equity forecast
        # If IV suggests higher vol than model predicts, adjust confidence
        reconciled_forecast = self.reconcile_equity_options(
            equity_forecast, 
            iv_skew
        )
        
        # 5. Rank best options for the forecast
        options_trades = self.rank_options_for_forecast(
            options_chain, 
            reconciled_forecast
        )
        
        return {
            'equity_forecast': equity_forecast,
            'iv_analysis': iv_skew,
            'reconciled': reconciled_forecast,
            'recommended_options': options_trades
        }
```

#### 3.2: Standardize Model Outputs

```python
# ml/src/models/unified_output.py

@dataclass
class UnifiedPrediction:
    """Single standard output for all models"""
    
    symbol: str
    timestamp: datetime
    prediction: Literal["BULLISH", "NEUTRAL", "BEARISH"]
    confidence: float  # 0-1
    target_price: float
    
    # Validation metadata
    model_name: str
    training_window: str  # "3m", "2w", "realtime"
    validation_method: str  # "backtesting", "walkforward", "live"
    performance_vs_target: float  # Actual vs target accuracy
    
    # Reconciliation info
    consensus_score: float  # How many models agree
    drift_detected: bool
    data_freshness_hours: int
```

### Phase 4: Workflow Consolidation (1 week)

#### 4.1: Consolidate Legacy Workflows

```yaml
# Keep only these canonical workflows:
.github/workflows/
├── daily-data-refresh.yml       # All OHLC ingestion
├── intraday-ingestion.yml       # Real-time M15/H1
├── intraday-forecast.yml        # Intraday predictions
├── ml-orchestration.yml         # Full ML suite
├── deploy-supabase.yml          # Edge Functions
├── deploy-ml-dashboard.yml      # Dashboard function
├── daily-options-integrate.yml  # NEW: Combines options + forecasts
└── tests-ci.yml                 # Unified CI

# Archive everything else
.github/workflows/legacy/
├── alpaca-intraday-cron-fixed.yml
├── backfill-ohlc.yml
├── batch-backfill-cron.yml
└── ... (24 more)
```

#### 4.2: Create Central Workflow Orchestrator

```yaml
# .github/workflows/orchestrator.yml
# Single source of truth for all automation

name: Orchestrator - Unified Automation

# ... routes to canonical workflows based on trigger
```

---

## 7. Specific Questions to Resolve

1. **Data Provider**: Is Massive API still used, or fully replaced by Alpaca?
2. **Options Integration**: When you see BEARISH forecast, does it automatically suggest put spreads? Or separate workflow?
3. **Multi-TF Reconciliation**: What's the current rule when M15 predicts BULLISH but D1 predicts BEARISH?
4. **Validation Hierarchy**: If backtesting says 98% accuracy but live says 40%, which wins in trading decisions?
5. **Symbol Metadata**: Should `symbols` table be auto-populated, manually maintained, or fetched from API?
6. **Dashboard Trust**: How do users know which model/tab to trust when they see contradictions?
7. **Options Scraping**: Why does `daily-options-scrape.yml` run separately? Should it be part of `ml-orchestration.yml`?
8. **Performance**: Are you tracking actual trading performance vs model predictions anywhere?

---

## 8. Recommended Action Plan

### Week 1: Foundation
- [ ] Fix symbols table (unblock Swift app)
- [ ] Create unified validation framework
- [ ] Consolidate backend scripts into utility library
- [ ] Document current model/tab reconciliation rules

### Week 2: Integration
- [ ] Integrate options data into ML pipeline
- [ ] Create unified prediction output format
- [ ] Implement multi-timeframe reconciliation logic
- [ ] Add real-time drift detection

### Week 3: Dashboard
- [ ] Redesign dashboard tabs (unify/reduce)
- [ ] Display confidence with sources
- [ ] Show model agreement matrix
- [ ] Add "why conflicting?" explanations

### Week 4: Cleanup
- [ ] Archive legacy workflows
- [ ] Consolidate duplicate scripts
- [ ] Verify all workflows run correctly
- [ ] Update documentation

---

## Files to Create/Modify

```
Priority 1 (Critical):
├── ml/src/validation/unified_framework.py        (NEW)
├── ml/src/models/unified_output.py               (NEW)
├── backend/lib/shared_utilities.ts               (NEW)
├── backend/scripts/seed-symbols.sql              (UPDATE)
└── supabase/functions/sync-user-symbols/         (UPDATE)

Priority 2 (Important):
├── ml/src/options_integrated_forecaster.py       (NEW)
├── .github/workflows/daily-options-integrate.yml (NEW)
├── ml/VALIDATION_FRAMEWORK.md                    (NEW)
└── backend/SCRIPTS_CONSOLIDATION.md              (NEW)

Priority 3 (Cleanup):
├── .github/workflows/legacy/                     (NEW DIRECTORY)
├── .github/workflows/README.md                   (UPDATE)
└── backend/scripts/ARCHIVE_MAP.md                (NEW)
```

---

## Conclusion

Your system is **architecturally sound** with consolidated workflows and good separation of concerns. However:

1. **Data pipeline gaps** allow for conflicting predictions
2. **Dashboard doesn't reconcile** multiple models' outputs
3. **Backend scripts** have accumulated without consolidation
4. **Swift app symbol tracking** is blocked by empty table
5. **Options data** not integrated with equity forecasts

**Priority**: Fix symbols table (1 day), then unify validation framework (3 days), then redesign dashboard (1 week). These three changes will eliminate most confusion and conflicts.