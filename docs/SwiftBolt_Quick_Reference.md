""# SwiftBolt_ML Quick Reference

**Updated**: January 21, 2026  
**Status**: Ready to execute  
**Timeline**: 3 weeks total effort

---

## 🎯 Key Issues At a Glance

| Issue | Severity | Impact | Fix Time | Status |
|-------|----------|--------|----------|--------|
| Symbols table empty | 🚫 BLOCKING | Swift app returns 0 jobs | 1 hour | READY |
| Dashboard shows 4 conflicting signals | ⚠️ HIGH | User confusion, poor trades | 3 days | READY |
| 35+ backend scripts (no clarity) | 💼 MEDIUM | High maintenance, duplication | 2 days | READY |
| 31 workflows (23 legacy) | 💼 MEDIUM | Cluttered CI/CD, potential duplicates | 1 day | READY |
| Options disconnected from forecasts | 🔴 IMPORTANT | Missing signal synthesis | 2 weeks | NEXT PHASE |

---

## 📊 Quick Wins (This Week)

### Monday (1 hour)

**Fix Swift App Symbol Tracking**

```bash
cd ~/SwiftBolt_ML
psql $DATABASE_URL < backend/scripts/seed-symbols.sql
./backend/scripts/test_symbol_sync.sh
# Result: Swift app unblocked, can add symbols
```

✅ Effort: 1 hour  
✅ Value: Unblocks entire Swift app feature

---

### Tuesday-Wednesday (2-3 days)

**Create Unified Validator**

```bash
cd ml
touch src/validation/unified_framework.py
# Copy code from SwiftBolt_Implementation.md
python -m pytest tests/test_unified_validator.py -v
```

✅ Effort: 2-3 days  
✅ Value: Dashboard shows single confidence score, not 4 conflicting ones

---

### Thursday-Friday (2 days)

**Consolidate Scripts & Workflows**

```bash
# Archive 30+ legacy scripts
mkdir -p backend/scripts/legacy
mv backend/scripts/*.sh backend/scripts/legacy/
cp backend/scripts/canonical/backfill.sh

# Archive 23 legacy workflows
mkdir -p .github/workflows/legacy
mv .github/workflows/backfill*.yml .github/workflows/legacy/
mv .github/workflows/intraday-update*.yml .github/workflows/legacy/
mv .github/workflows/ml-forecast.yml .github/workflows/legacy/
```

✅ Effort: 2 days  
✅ Value: Reduced maintenance burden, clear canonical versions

---

## 🔄 Current vs Recommended Data Architecture

### Current (Fragmented)

```
Market Data
  │
  ├─→ Intraday Job (every 15 min) → M15, H1
  │
  ├─→ Daily Job (6 AM UTC) → M15/H1/H4/D1/W1
  │
  └─→ Options Scrape (separate) → Finnhub data

Forecast Pipeline (separate)
  │
  ├─→ ARIMA-GARCH
  ├─→ XGBoost
  └─→ Transformer

Validation (3 sources, not reconciled)
  │
  ├─→ Backtesting: 98.8% (historical)
  ├─→ Walk-forward: 78% (quarterly)
  └─→ Live: 40% (today - DEGRADED)

Problem: Options not aware of forecasts
         Forecasts not aware of options
         User sees conflicting signals
```

### Recommended (Integrated)

```
Daily ML Orchestration (6 AM UTC)
  │
  ├─→ Stage 1: Data Prep (6:05)
  │   ├─ Load M15/H1/H4/D1/W1
  │   ├─ Load options data
  │   └─ Feature engineering
  │
  ├─→ Stage 2: Forecast (6:15)
  │   ├─ ARIMA-GARCH
  │   ├─ XGBoost
  │   └─ Ensemble
  │
  ├─→ Stage 3: Options Integration (6:25)
  │   ├─ Load equity forecast
  │   ├─ Filter options by Greeks/IV
  │   └─ Rank by risk/reward
  │
  ├─→ Stage 4: Unified Validation (6:35)
  │   ├─ Backtesting score (40% weight)
  │   ├─ Walk-forward score (35% weight)
  │   ├─ Live score (25% weight)
  │   └─ Unified confidence = 76.8%
  │
  └─→ Stage 5: Health Check (6:45)
      ├─ Data freshness
      ├─ Model performance vs targets
      └─ Slack alerts

Single Dashboard (one source of truth)
  │
  ├─→ Prediction: "Bullish 76.8% confidence"
  ├─→ Why: "Drift detected (-50% from historical)"
  ├─→ Multi-TF: "D1 bullish, M15 bearish (weighted consensus bullish)"
  └─→ Options: "Best calls: 40 delta, 65th percentile IV"

Benefit: Options integrated ✓  
          Forecasts aware of options ✓  
          User gets coherent signal ✓
```

---

## 📋 Workflow Consolidation Status

### Keep (8 Canonical Workflows)

```
✅ daily-data-refresh.yml          - OHLC ingestion (keep)
✅ intraday-ingestion.yml          - Real-time M15/H1 (keep)
✅ intraday-forecast.yml           - Intraday predictions (keep)
✅ ml-orchestration.yml            - Full ML suite (keep)
✅ deploy-supabase.yml             - Edge functions (keep)
✅ deploy-ml-dashboard.yml         - Dashboard deployment (keep)
✅ test-ml.yml                     - Unit tests (keep)
✅ api-contract-tests.yml          - Integration tests (keep)
```

### Archive (23 Workflows to Consolidate)

```
⚠️  Backfill Duplicates (4)
    backfill-ohlc.yml → daily-data-refresh
    batch-backfill-cron.yml → daily-data-refresh
    daily-historical-sync.yml → daily-data-refresh
    symbol-backfill.yml → daily-data-refresh

⚠️  Intraday Duplicates (5)
    alpaca-intraday-cron.yml → intraday-ingestion
    alpaca-intraday-cron-fixed.yml → intraday-ingestion
    intraday-update.yml → intraday-ingestion
    intraday-update-v2.yml → intraday-ingestion
    backfill-intraday-worker.yml → intraday-ingestion

⚠️  ML Pipeline Duplicates (5)
    ml-forecast.yml → ml-orchestration
    ml-evaluation.yml → ml-orchestration
    data-quality-monitor.yml → ml-orchestration
    drift-monitoring.yml → ml-orchestration
    options-nightly.yml → ml-orchestration

❓ Unclear/Dead (9)
    daily-options-scrape.yml → Verify + consolidate into ml-orchestration
    job-worker.yml → Verify + consolidate
    orchestrator-cron.yml → Supabase-specific, keep or consolidate
    symbol-weight-training.yml → Move to ml-orchestration
    sync-user-symbols.yml → No recent runs (likely dead)
    scheduled-refresh.yml → No recent runs (likely dead)
    performance-tracking.yml → 60 days no runs (dead)
    nightly-coverage-check.yml → Keep (separate concern)
    frontend-integration-checks.yml → Keep (separate concern)
```

---

## 📚 Backend Script Status

### Canonical Scripts (Authoritative)

```
✅ scripts/canonical/backfill.sh     - Backfill OHLC data
✅ scripts/canonical/deploy.sh       - Deploy all services
✅ scripts/canonical/validate.sh     - Validate data quality
✅ scripts/canonical/seed.sh         - Seed initial data
```

### To Archive (30+ Scripts)

```
⚠️  Backfill scripts (3-4 versions)
⚠️  Diagnostic scripts (6: check_*.sql, diagnose_*.sql)
⚠️  Deployment variants (4: deploy_prod.sh, etc.)
⚠️  Validation variants (5: validate_*.sh)
⚠️  One-off debug scripts (10+)
```

**Action**: Archive to `scripts/legacy/` with README

### Shared Library (New)

```typescript
backend/lib/shared.ts
  ├─ Database connection utilities
  ├─ Retry with exponential backoff
  ├─ Logging (consistent format)
  ├─ Batch operations
  └─ Error handling

// Usage in scripts:
import { retryWithBackoff, log, batchInsert } from '../lib/shared';
```

---

## 📈 Dashboard Reconciliation Formula

### Current Dashboard Problem

```
User sees:
┌──────────────────────────┐
│ Statistical Tab: 98.8% ✅ │
│ Live Forecast: 40% ↓     │
│ M15: -48%↓  H1: -40%↓    │
│                          │
│ ❓ Which one do I trade on?│
└──────────────────────────┘
```

### Solution: Unified Confidence Score

```
Formula:
Unified = (40% × Backtesting) + (35% × Walk-Forward) + (25% × Live)
        = (40% × 0.988) + (35% × 0.78) + (25% × 0.40)
        = 0.395 + 0.273 + 0.100
        = 0.768 = 76.8%

Dashboard shows:
┌──────────────────────────────┐
│ Confidence: 76.8% ⚠️          │
│                              │
│ Why it's not higher:         │
│ • Live accuracy down 50%    │
│ • Drift detected            │
│ • Monitor for retraining   │
│                              │
│ Components:                 │
│ • Historical: 98.8% ✅      │
│ • Quarterly: 78% ⚠️        │
│ • Recent: 40% ✗             │
└──────────────────────────────┘
```

### Multi-Timeframe Reconciliation

```
When predictions conflict:
M15: BEARISH (-48%)
H1:  BEARISH (-40%)
D1:  BULLISH (+60%)  ← Conflict!
W1:  BULLISH (+70%)

Hierarchy weighting:
W1: 50% weight × BULLISH
D1: 40% weight × BULLISH  
H4: 30% weight × ... (if present)
H1: 20% weight × BEARISH
M15: 10% weight × BEARISH

Consensus: Weighted average = Consensus Direction
           + Confidence penalty for conflict

Dashboard shows:
"Consensus: BULLISH (but watch M15 for pullback)"
```

---

## ✅ Success Criteria Checklist

### By End of Week 1

**Monday (Done)**
- [ ] Symbols table has 8 core symbols
- [ ] test_symbol_sync.sh returns "jobs_created: 3"
- [ ] Swift app can add symbols without errors

**Tuesday-Wednesday (Done)**
- [ ] unified_framework.py created and tested
- [ ] All unit tests passing (test_unified_validator.py)
- [ ] Integration into ml_orchestration.yml working
- [ ] Sample predictions stored with unified score

**Thursday-Friday (Done)**
- [ ] 4 canonical scripts in scripts/canonical/
- [ ] 30+ old scripts archived to scripts/legacy/
- [ ] 8 canonical workflows remaining in .github/workflows/
- [ ] 23 legacy workflows in .github/workflows/legacy/
- [ ] README files documenting consolidation

### By End of Week 2

- [ ] Dashboard shows unified confidence score
- [ ] Drift alerts visible on dashboard
- [ ] Multi-TF reconciliation displayed
- [ ] User testing completed
- [ ] Deployed to production

### By End of Week 3

- [ ] Options integrated into forecasts
- [ ] Auto-create symbols on demand
- [ ] Real-time performance tracking
- [ ] Model retraining on drift detection

---

## 📊 Effort Estimate

| Task | Duration | Effort | Value | Priority |
|------|----------|--------|-------|----------|
| Fix symbols table | 1h | 👨 | 👨👨👨 | NOW |
| Unified validator | 3d | 👨👨 | 👨👨👨 | THIS WEEK |
| Consolidate scripts | 2d | 👨👨 | 👨👨 | THIS WEEK |
| Consolidate workflows | 1d | 👨 | 👨👨 | THIS WEEK |
| Dashboard redesign | 1w | 👨👨👨 | 👨👨👨 | NEXT WEEK |
| Options integration | 2w | 👨👨👨 | 👨👨👨 | MONTH 2 |
| **TOTAL** | **3 weeks** | | |

---

## 🚀 Getting Started Tomorrow

### 8:00 AM Monday

```bash
# 1-hour fix
cd ~/SwiftBolt_ML

# Seed symbols
psql $DATABASE_URL < backend/scripts/seed-symbols.sql

# Verify
psql $DATABASE_URL -c "SELECT COUNT(*) FROM symbols;"
# Expected: 8

# Test end-to-end
./backend/scripts/test_symbol_sync.sh
# Expected: jobs_created: 3

# Redeploy Swift app
echo "🚀 Swift app now ready to use"
```

### 9:00 AM Tuesday

```bash
# Start unified validator
cd ml
touch src/validation/unified_framework.py
# Copy code from SwiftBolt_Implementation.md

# Run tests
python -m pytest tests/test_unified_validator.py -v
```

---

## 🗂️ Key Files to Know

### New Files to Create

- `ml/src/validation/unified_framework.py` - Validator logic
- `ml/tests/test_unified_validator.py` - Validator tests
- `ml/src/models/unified_output.py` - Store predictions
- `backend/lib/shared.ts` - Shared utilities
- `backend/scripts/canonical/backfill.sh` - Canonical backfill
- `backend/scripts/canonical/deploy.sh` - Canonical deploy
- `backend/scripts/canonical/validate.sh` - Canonical validate
- `backend/scripts/canonical/seed.sh` - Canonical seed

### Existing Files to Update

- `.github/workflows/ml-orchestration.yml` - Add validation stage
- `.github/workflows/daily-data-refresh.yml` - Use shared lib
- `backend/scripts/seed-symbols.sql` - Populate with core symbols
- `backend/scripts/test_symbol_sync.sh` - Test harness

### Files to Archive

- `backend/scripts/*.sh` (old versions) → `backend/scripts/legacy/`
- `.github/workflows/backfill*.yml` → `.github/workflows/legacy/`
- `.github/workflows/intraday-update*.yml` → `.github/workflows/legacy/`
- `.github/workflows/ml-forecast.yml` → `.github/workflows/legacy/`

---

## 🤔 Questions to Answer

**Before you start, decide:**

1. **Validation Weights**: Should backtesting be 40% (current)? Or increase live to 40%?
2. **Drift Threshold**: Is 25% divergence the right threshold? Or 15%?
3. **Retraining Frequency**: On schedule (30 days)? On drift detection? Manual only?
4. **Timeframe Hierarchy**: D1 > H4 > H1 > M15? Or by recent performance?
5. **Options Integration**: Should IV skew adjust model confidence?
6. **Auto-Create Symbols**: From Finnhub on demand? Or manual only?

Document decisions in: `ml/docs/VALIDATION_FRAMEWORK.md`

---

## 📖 Reference Documents

1. **This document** - Quick overview (start here)
2. `SwiftBolt_System_Audit.md` - Deep technical analysis
3. `SwiftBolt_Implementation.md` - Step-by-step code examples
4. `ml/docs/VALIDATION_FRAMEWORK.md` - Validation rules (create this)
5. `backend/scripts/legacy/README.md` - Archive guide (create this)
6. `.github/workflows/legacy/README.md` - Workflow guide (create this)

---

## ⭐ The Insight

Your system is **architecturally excellent**. The issue isn't the design—it's **accumulation and fragmentation**.

You have:
- ✅ Great data ingestion (Alpaca, Finnhub)
- ✅ Great ML models (ensemble approach)
- ✅ Great app integration (Swift + Supabase)

But you're showing users **4 conflicting signals** instead of 1 coherent signal.

**The fix**: Add an explicit reconciliation layer that combines backtesting, walk-forward, and live scores with clear rules and context.

This is high-value work because it directly improves:
- 📈 Trading signal quality
- 🤝 User trust in model
- ⚙️ System maintainability

**Ready?** Start with the symbols table tomorrow morning. 1 hour. Changes everything.
""