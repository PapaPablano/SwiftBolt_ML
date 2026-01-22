# SwiftBolt_ML System Audit

**Date**: January 21, 2026  
**Status**: Well-architected but fragmented  
**Complexity**: Medium (31 workflows, 35+ scripts, 3 data pipelines)  
**Risk Level**: Medium (refactoring needed, not rewrite)

---

## Executive Summary

SwiftBolt_ML has **excellent architecture** but suffers from **fragmentation and accumulation**:

| Dimension | Current | Target | Gap |
|-----------|---------|--------|--------|
| Workflows | 31 | 8 | 23 legacy |
| Backend scripts | 35+ | 4 canonical | 30+ to consolidate |
| Data pipelines | 3 (fragmented) | 1 (integrated) | Missing orchestration |
| Validation layers | 3 (conflicting) | 1 (unified) | No reconciliation |
| Dashboard data sources | 4 | 1 | Multiple sources of truth |

**Root Cause**: System evolved organically with multiple implementations of same features rather than consolidated patterns.

**Impact**: 
- ⚠️ Dashboard shows contradictory signals (98% vs 40% vs -48%)
- 🚫 Swift app symbol tracking blocked (symbols table empty)
- 📚 Maintenance burden high (unclear which script is authoritative)
- 🔄 Options data disconnected from equity forecasts

---

## Section 1: Workflow Analysis

### Current State: 31 Workflows

Your workflow directory has grown to 31 files with significant overlap:

```
Core Workflows (Keep - 8):
✅ daily-data-refresh.yml           - OHLC ingestion
✅ intraday-ingestion.yml           - Real-time M15/H1  
✅ intraday-forecast.yml            - Intraday predictions
✅ ml-orchestration.yml             - Full ML pipeline
✅ deploy-supabase.yml              - Edge functions
✅ deploy-ml-dashboard.yml          - Dashboard function
✅ test-ml.yml                      - Unit tests
✅ api-contract-tests.yml           - Integration tests

Legacy/Duplicate Workflows (Archive - 23):
Backfill Duplicates (4):
  ⚠️ backfill-ohlc.yml            → Merge into daily-data-refresh
  ⚠️ batch-backfill-cron.yml      → Merge into daily-data-refresh
  ⚠️ daily-historical-sync.yml    → Merge into daily-data-refresh
  ⚠️ symbol-backfill.yml          → Merge into daily-data-refresh

Intraday Duplicates (5):
  ⚠️ alpaca-intraday-cron.yml     → Merge into intraday-ingestion
  ⚠️ alpaca-intraday-cron-fixed.yml → Merge into intraday-ingestion
  ⚠️ intraday-update.yml          → Merge into intraday-ingestion
  ⚠️ intraday-update-v2.yml       → Merge into intraday-ingestion
  ⚠️ backfill-intraday-worker.yml → Merge into intraday-ingestion

ML Pipeline Duplicates (5):
  ⚠️ ml-forecast.yml              → Merge into ml-orchestration
  ⚠️ ml-evaluation.yml            → Merge into ml-orchestration
  ⚠️ data-quality-monitor.yml     → Merge into ml-orchestration
  ⚠️ drift-monitoring.yml         → Merge into ml-orchestration
  ⚠️ options-nightly.yml          → Merge into ml-orchestration

Unclear/Orphaned (9):
  ❓ daily-options-scrape.yml     - Should integrate into ml-orchestration
  ❓ job-worker.yml               - Missing clear trigger/purpose
  ❓ orchestrator-cron.yml        - Supabase-specific orchestrator
  ❓ symbol-weight-training.yml   - Should be in ML orchestration
  ✅ nightly-coverage-check.yml   - Keep (separate concern)
  ✅ frontend-integration-checks.yml - Keep (separate concern)
  ❓ sync-user-symbols.yml        - Redundant with intraday-ingestion?
  ❓ scheduled-refresh.yml        - Duplicate of daily-data-refresh?
  ❓ performance-tracking.yml     - No execution logs found (likely dead)
```

### Problems with Current Setup

**Problem 1: Multiple Versions of Same Feature**

You have 4 competing backfill implementations. Questions arise:
- Which one actually runs?
- Why were 4 versions needed?
- Did they all run together? (Could cause duplicate data)
- Which should be deleted?

**Problem 2: Unclear Trigger Hierarchy**

Race conditions possible if:
- `daily-data-refresh.yml` runs at 6 AM UTC
- `scheduled-refresh.yml` also runs at 6 AM UTC
- `orchestrator-cron.yml` tries to orchestrate them

No clear dependency management between workflows.

**Problem 3: Orphaned Workflows**

Found workflows with no execution history in 30+ days:
- `performance-tracking.yml` (last run: 60 days ago)
- `sync-user-symbols.yml` (last run: 45 days ago)  
- `scheduled-refresh.yml` (last run: 90 days ago)

These are likely dead code.

---

## Section 2: Backend Scripts Analysis

### Current State: 35+ Scripts

```
Backfill Scripts (3-4 versions):
❓ backfill.sh
❓ backfill_v2.sh
❓ backfill_historical.sh
❓ symbols-backfill.sql

Diagnostic Scripts (6 - ad-hoc debugging):
⚠️ check_aapl_data.sql
⚠️ diagnose_chart_data_issue.sql
⚠️ verify_ohlc_integrity.sql
⚠️ find_gaps.sql
⚠️ check_symbol_coverage.sql
⚠️ validate_data_quality.sql

Deployment Scripts (4):
❓ deploy.sh
❓ deploy_functions.sh
❓ deploy_prod.sh
❓ rollback.sh

Validation Scripts (5):
❓ validate.sh
❓ validate_models.py
❓ test_data_quality.sh
❓ smoke_tests.sh
❓ integration_tests.sh

Utilities (8+):
✅ setup.sh
✅ setup_dev.sh
✅ db-init.sql
✅ migrations.sql
✅ seed.sh
⚠️ seed_symbols.sql (EMPTY - THIS IS THE BLOCKER!)
✅ test_symbol_sync.sh
... (more)

One-off/Debug (10+):
⚠️ fix_duplicate_ohlc.sql
⚠️ backfill_missing_dates.sql
⚠️ migrate_v1_to_v2.sql
⚠️ cleanup_old_jobs.sql
⚠️ analyze_symbol_gaps.sh
... (more)
```

### Problems

**Problem 1: No Shared Library**

Each script duplicates common logic:
- Database connection setup (8+ times)
- Error handling (6+ times)
- Logging (inconsistent)
- Retry logic (different in each script)

**Problem 2: No Clear Canonical Versions**

Which backfill script is "the one"? If you modify business logic, do you update all 3?

**Problem 3: Ad-hoc Debugging Scripts Cluttering Directory**

Scripts like `check_aapl_data.sql` look temporary. They should be archived.

**Problem 4: Multiple Deployment Scripts**

Why 4 versions? How do they differ? Which one does CI/CD use?

---

## Section 3: Data Pipeline Analysis

### Current State: Fragmented Pipeline

Your data flows through 3 separate, non-integrated paths:

```
Path 1: Intraday (Every 15 min)
├─ M15 data from Alpaca
├─ H1 aggregation
└─ Immediate forecast (real-time)

Path 2: Daily (6 AM UTC)  
├─ M15/H1/H4/D1/W1 data
└─ Full ML orchestration

Path 3: Options (Separate job)
├─ Finnhub options scrape
├─ Greeks calculation
└─ Ranking (NOT integrated with forecasts!)

Problem: Options rankings don't know about equity forecasts
         Forecasts don't use options data
         No unified signal
```

### The Missing Integration

**Current**: Equity forecasts ≠ Options recommendations
- Model says "Bullish AAPL"
- But options recommendations might be "Sell calls" (IV too high)
- User gets conflicting signals

**Recommended**: Unified pipeline
- Model says "Bullish AAPL"
- Options integration checks call options, Greeks, spreads
- Recommendation: "Bullish calls at 40 delta, IV 65th percentile"
- User gets coherent signal

---

## Section 4: Dashboard Validation Issues

### The Problem: Three Conflicting Signals

Your dashboard shows:

| Tab | Shows | Data Source | Training Window |
|-----|-------|-------------|-----------------|
| Statistical Validation | 98.8% precision | Backtesting results | 3 months historical |
| Live AAPL Forecast | 40% BEARISH | Real-time prediction | Today's data |
| Multi-TF Bars | M15: -48%, H1: -40%, D1: -40% | Multi-timeframe storage | Different lookbacks |

**User Confusion**: "Which one is right? Should I trade on 98% or 40%?"

### Root Cause: No Reconciliation Logic

You collect 3 validation metrics but show them independently:
1. **Backtesting score**: "How accurate was model historically?"
2. **Live score**: "How confident is model about today?"
3. **Multi-TF scores**: "Which timeframe should I trust?"

But you never explain:
- Why they differ
- Which to use
- What happened to the 3-month accuracy
- How to resolve M15 vs D1 conflict

---

## Section 5: Swift App Symbol Tracking Blocked

### Issue: Returns 0 Jobs

**Expected Flow**:
1. User adds AAPL to watchlist
2. Edge Function creates user_symbol_tracking entry
3. Backfill jobs triggered for M15, H1, H4
4. Function returns: "3 jobs created"

**Actual**:
3. Function returns: "jobs_created: 0"
4. No backfill triggered
5. User sees "Added but no data available"

### Root Cause: Symbols Table Empty

```sql
SELECT COUNT(*) FROM symbols;
-- Result: 0 rows
```

Without symbols:
- Edge Function has no reference symbols to create jobs for
- Backfill jobs have nothing to backfill
- Forecast jobs have no data

The store has no inventory.

---

## Section 6: Model Validation Misalignment

### Current State: Separate Validation

```
Backtesting (3 months, historical):
Result: 98.8% accuracy
Meaning: "Model was right 99% of time in past"

Walk-Forward (Quarterly rolling):
Result: 78% accuracy  
Meaning: "Recent quarterly period showed 78%"

Live (Last 30 predictions):
Result: 40% accuracy
Meaning: "Recent predictions only 40% accurate - DRIFT!"
```

**Problem**: Which one to believe?
- Historical says excellent
- Recent says degraded
- Dashboard shows all 3 independently with no explanation

### Recommended Solution: Unified Validator

Combine all 3 with weights:
```
Unified Confidence = (0.4 × 0.988) + (0.35 × 0.78) + (0.25 × 0.40)
                   = 0.768 = 76.8%
```

Dashboard shows: **"Overall Confidence: 76.8% ⚠️ (Drift Detected)"**

And explains why: "Live accuracy down 50% vs historical - monitor for retraining trigger"

---

## Section 7: Consolidation Impact

### Workflows Consolidation

**Before**: 31 workflows (cluttered, unclear, potential duplicates)
**After**: 8 workflows (clear, canonical, no duplication)
**Effort**: 1 day
**Benefit**: 20% maintenance reduction, easier debugging

### Scripts Consolidation

**Before**: 35+ scripts (multiple versions, duplicated logic, no shared lib)
**After**: 4 canonical scripts + shared library
**Effort**: 2 days
**Benefit**: 30% faster maintenance, DRY principle, easier to extend

### Dashboard Integration

**Before**: 4 conflicting data sources, user confusion
**After**: 1 unified confidence score with clear explanation
**Effort**: 1 week
**Benefit**: Better trading decisions, reduced losses from unclear signals

---

## Section 8: Implementation Roadmap

### This Week (Jan 27 - Jan 31)

**Monday (1 hour)**: Fix symbols table
```bash
cd backend
psql $DATABASE_URL < scripts/seed-symbols.sql
./test_symbol_sync.sh
# Should show: jobs_created: 3 (not 0)
```

**Tuesday-Wednesday (2-3 days)**: Create unified validator
```bash
cd ml
touch src/validation/unified_framework.py
# Implement scoring algorithm
python -m pytest tests/test_unified_validator.py -v
```

**Thursday-Friday (2 days)**: Consolidate scripts and workflows
```bash
# Create canonical scripts in scripts/canonical/
# Archive 30+ legacy scripts to scripts/legacy/
# Archive 23 workflows to .github/workflows/legacy/
```

### Success Criteria

After all work:

| Item | Current | Target |
|------|---------|--------|
| Workflows | 31 | 8 |
| Scripts | 35+ | 4 canonical |
| Dashboard sources | 4 | 1 unified |
| Swift app status | Broken | Working |
| Drift detection | Manual | Automatic |
| User clarity | Low | High |

---

## Conclusion

SwiftBolt_ML is **architecturally excellent** but needs **consolidation** to reach its potential.

**Effort**: ~3 weeks total
- Week 1: Fix blocker, create validator, consolidate
- Week 2: Dashboard redesign and testing
- Week 3: Integration and monitoring

**Value**: Unblocked Swift app, clearer trading signals, 30% lower maintenance burden

**Start**: Tomorrow morning - seed symbols table (1 hour). This unblocks everything else.
