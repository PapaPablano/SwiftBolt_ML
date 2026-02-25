# Code Analysis Progress — SwiftBolt_ML

**Last Updated:** 2026-02-23  
**Status:** Phase 3 (Analysis) Complete — Ready for Review & Cleanup Approval

---

## Continuing in a New Chat
Start with:
> "Continue code analysis - please read `code-analysis-progress.md` to understand where we left off, then proceed with the next phase."

---

## Project Context

- **Type:** Python ML trading system + Supabase backend + React/TS frontend + macOS Swift client
- **Primary focus:** `ml/src` (248 Python files), `backend/supabase/functions` (44 Edge Functions), `frontend/src` (14 files)
- **Analysis scope:** All of the above — unused imports, dead code, orphaned/duplicate files
- **Aggressiveness:** Moderate
- **Safety:** Never modify without explicit user approval

---

## Completed Phases

- ✅ Phase 1 — Discovery (project structure mapped)
- ✅ Phase 2 — Scanning (ruff, file pattern analysis, import cross-referencing)
- ✅ Phase 3 — Analysis (findings categorized and prioritized)

---

## FINDINGS SUMMARY

### Total Issues Found
| Category | Count | Risk Level |
|----------|-------|------------|
| Unused Python imports (F401) | 93 | Low — safe to remove |
| Unused Python variables (F841) | 22 | Low — safe to remove |
| Syntax errors in Python files | 7 | Medium — needs investigation |
| Duplicate/versioned Python files | 16 | Medium — confirm which is canonical |
| Truly orphaned Python files (no importers) | 5 | High — likely dead |
| Orphaned frontend components | 0 | N/A — all used via ChartWithIndicators |
| Duplicate backend shared files | 2 | Low — old versions superseded |
| Likely dev-only edge functions | 5 | Low — can be archived |

---

## DETAILED FINDINGS

---

### 1. PYTHON — Syntax Errors (Fix First!)

These files have parse errors that block ruff from fully analyzing them:

| File | Issue |
|------|-------|
| `ml/src/api/validation_api.py` | 3x "Expected an identifier" syntax errors |
| `ml/src/hardcoded_env.py` | 4x syntax errors — likely malformed/temp file |

**Action:** Open these files and investigate. `hardcoded_env.py` is likely junk (no importers found except auth files that themselves reference it).

---

### 2. PYTHON — Orphaned Files (No Importers Found)

These files are not imported by anything else in `ml/src`. They may be CLI scripts or truly dead:

| File | Notes |
|------|-------|
| `ml/src/ga_training_job.py` | GA strategy training — check if run via CLI/scheduler |
| `ml/src/strategy_builder_auth_bypass.py` | Name says "bypass" — likely dev hack, unused |
| `ml/src/ranking_evaluation_job.py` | No importers found |
| `ml/src/options_snapshot_job.py` | No importers found |
| `ml/src/hardcoded_env.py` | Has syntax errors + no real importers = strong delete candidate |

**Action needed:** Check if any of these are invoked via `python -m` or shell scripts. If not, they're dead code.

---

### 3. PYTHON — Duplicate/Versioned Files

#### 3a. `_legacy/` folder (9 files) — SAFE TO ARCHIVE

```
ml/src/_legacy/evaluation_job.py
ml/src/_legacy/forecast_job.py
ml/src/_legacy/forecast_job_worker.py
ml/src/_legacy/hourly_ranking_scheduler.py
ml/src/_legacy/intraday_evaluation_job.py
ml/src/_legacy/job_worker.py
ml/src/_legacy/multi_horizon_forecast.py
ml/src/_legacy/multi_horizon_forecast_job.py
ml/src/_legacy/ranking_job_worker.py
```
The folder has a `README.md` acknowledging they're legacy. Safe to delete (they're already in git history).

#### 3b. Feature file duplicates — NEEDS CONFIRMATION

| Old/Unused File | Canonical (Active) File | Evidence |
|-----------------|------------------------|---------|
| `ml/src/features/sr_polynomial_fixed.py` | `ml/src/features/sr_polynomial.py` | `sr_polynomial_fixed` has **zero importers**; `sr_polynomial` is imported by 3 files |
| `ml/src/features/technical_indicators_tradingview.py` | `ml/src/features/technical_indicators_corrected.py` | `tradingview` version has **zero importers** |

**Note:** `technical_indicators_corrected.py` IS actively used (imported by `technical_indicators.py`, `temporal_indicators.py`, `indicator_recompute.py`). The `technical_indicators.py` wrapper references `_corrected` — these two should eventually be merged but are both active.

#### 3c. Cross-directory duplicates — INVESTIGATE

| File A | File B | Status |
|--------|--------|--------|
| `ml/src/forecast_validator.py` | `ml/src/monitoring/forecast_validator.py` | Need to check which is imported |
| `ml/src/monitoring/greeks_validator.py` | `ml/src/validation/greeks_validator.py` | Need to check which is imported |
| `ml/src/evaluation/walk_forward.py` | `ml/src/optimization/walk_forward.py` | Different modules but same name — likely different code |
| `ml/src/models/weight_optimizer.py` | `ml/src/training/weight_optimizer.py` | Different modules but same name |

#### 3d. Auth file duplication

| File | Status |
|------|--------|
| `ml/src/strategy_builder_auth_bypass.py` | **No importers** — orphaned dev file |
| `ml/src/strategy_builder_auth_v2.py` | Imports `hardcoded_env` — active but references broken file |

#### 3e. Script duplicates

| Old | Canonical |
|-----|-----------|
| `ml/src/scripts/deep_backfill_ohlc.py` | `ml/src/scripts/deep_backfill_ohlc_v2.py` |
| `ml/src/scripts/alpaca_backfill_ohlc_v2.py` | Possibly supersedes older script |

---

### 4. PYTHON — Unused Imports (126 issues across 73 files)

**Top patterns to clean up (all low-risk, no behavior changes):**

#### typing imports (Python 3.10+ doesn't need these)
Many files import `from typing import List, Optional, Tuple, Dict, Any` unnecessarily:
```
ml/src/backtesting/backtest_engine.py        — List, Tuple
ml/src/backtesting/performance_metrics.py   — List
ml/src/backtesting/trade_logger.py          — datetime
ml/src/market_analysis/options_chain.py     — Dict, List, Optional
ml/src/risk/portfolio_manager.py            — List, Optional
ml/src/risk/risk_limits.py                  — List, Optional
ml/src/rebalancing/cost_optimizer.py        — List
ml/src/rebalancing/tax_aware_rebalancer.py  — List
ml/src/trading/broker_interface.py          — List
ml/src/strategies/strategy_builder.py       — Optional, Tuple
ml/src/strategy_builder_auth_v2.py          — Path, Any, Optional
... (many more)
```

#### Unused numpy/pandas imports
```
ml/src/attribution/brinson_attribution.py   — numpy
ml/src/data/relaxed_validator.py            — numpy
ml/src/market_analysis/greeks_aggregation.py — numpy
ml/src/market_analysis/liquidity_analyzer.py — numpy
ml/src/models/adaptive_targets.py           — numpy
ml/src/models/ensemble_loader.py            — numpy
ml/src/risk/scenario_builder.py             — numpy
ml/src/risk/stress_testing.py               — numpy, pandas
ml/src/strategies/adaptive_supertrend_adapter.py — numpy
ml/src/strategies/strategy_builder.py       — numpy
ml/src/training/model_training.py           — numpy
ml/src/visualization/pivot_levels_web.py    — numpy
ml/src/visualization/volatility_surfaces.py — pandas
```

#### Unused os/sys/json imports in scripts
```
ml/src/scripts/check_model_health.py        — os
ml/src/scripts/debug_ensemble_training.py   — os, pandas
ml/src/scripts/diagnose_intraday_forecast_issues.py — os, sys
ml/src/scripts/run_unified_validation_report.py — os
ml/src/scripts/smoke_tests.py               — os
ml/src/scripts/test_indicator_saving.py     — os, json, pandas
ml/src/scripts/validate_ohlc_before_training.py — os
ml/src/training/wandb_integration.py        — os
ml/src/stock-sentiment/app.py               — plotly, json, subprocess, os
```

#### Notably suspicious: `SIMPLIFIED_FEATURES` imported but unused in 4 model files
```
ml/src/models/baseline_forecaster.py
ml/src/models/binary_forecaster.py
ml/src/models/tabpfn_forecaster.py
ml/src/models/xgboost_forecaster.py  (also TemporalFeatureEngineer, compute_simplified_features)
```
These suggest a feature refactor was started but not completed — the imports were added but never wired in.

#### F811 — Redefined function (actual bug risk)
```
ml/src/features/support_resistance_detector.py
  — `find_all_levels` defined at line 747 is redefined later (overwriting the first definition)
```
This is a latent bug — the first definition is silently shadowed.

---

### 5. PYTHON — Unused Variables (F841, 22 issues)

Notable ones (not just loop throwaway vars):

| File | Variable | Notes |
|------|----------|-------|
| `ml/src/intraday_forecast_job.py` | `divergence_monitor` | Object created but never used |
| `ml/src/evaluation_job_intraday.py` | `calibration_record` | Record created but never persisted |
| `ml/src/forecast_synthesizer.py` | `combined` | Result computed but discarded |
| `ml/src/unified_forecast_job.py` | `data_quality_score` | Score computed but unused |
| `ml/src/optimization/walk_forward.py` | `oos_equity_series` | Out-of-sample data computed but discarded |
| `ml/src/risk/risk_limits.py` | `current_usage` | Usage computed but not checked |
| `ml/src/trading/paper_trading.py` | `transactions_df` | DataFrame built but unused |
| `ml/src/visualization/polynomial_sr_chart.py` | `fig`, `width2` | Figure created but not shown/returned |

Several of these look like **silent bugs** — data is computed but the result is discarded rather than returned or saved.

---

### 6. BACKEND — Duplicate Shared Files

| Superseded (OLD) | Active (NEW) | Evidence |
|------------------|--------------|---------|
| `_shared/finnhub-client.ts` | `_shared/providers/finnhub-client.ts` | Old is a simple wrapper; new implements full `DataProviderAbstraction` interface with rate limiting |
| `_shared/massive-client.ts` | `_shared/providers/massive-client.ts` | Same pattern — old is superseded by providers/ version |

The root-level `_shared/finnhub-client.ts` is not imported by any function directly (confirmed via grep). Safe to delete.

---

### 7. BACKEND — Likely Dev-Only / One-Time Edge Functions

These are small utility functions that appear to be dev/ops tools rather than production endpoints:

| Function | Lines | Purpose |
|----------|-------|---------|
| `apply-rls-fix` | 39 | One-time RLS migration helper |
| `check-rls` | 43 | RLS verification — dev tool |
| `create-pr-helper` | 84 | GitHub PR automation — dev tool |
| `test-schema` | 58 | Schema testing — dev tool |
| `ga-strategy` | ? | GA strategy — has no callers in frontend or other functions |

**Note:** These should not be deleted without checking if they're invoked by GitHub Actions workflows.

---

### 8. FRONTEND — All Clear (mostly)

The frontend is small and well-structured. Key finding:

- `StrategyUI.tsx` and `DateRangeSelector.tsx` are **not imported anywhere** — confirmed orphaned components
- All other components (`TradingViewChart`, `IndicatorPanel`, `PivotLevelsPanel`) are used through `ChartWithIndicators.tsx`
- All hooks (`useIndicators`, `usePivotLevels`, `useWebSocket`) are used

**Orphaned components:**
```
frontend/src/components/StrategyUI.tsx       — not imported anywhere
frontend/src/components/DateRangeSelector.tsx — not imported anywhere
```

---

## PRIORITIZED CLEANUP PLAN

### Tier 1 — High Confidence, Safe to Delete (No Risk)
1. `ml/src/_legacy/` — entire folder (9 files, acknowledged as legacy)
2. `ml/src/features/sr_polynomial_fixed.py` — zero importers, superseded by `sr_polynomial.py`
3. `ml/src/features/technical_indicators_tradingview.py` — zero importers
4. `ml/src/strategy_builder_auth_bypass.py` — zero importers, name implies dev hack
5. `ml/src/hardcoded_env.py` — syntax errors + no real importers
6. `backend/supabase/functions/_shared/finnhub-client.ts` — superseded by providers/ version
7. `backend/supabase/functions/_shared/massive-client.ts` — superseded by providers/ version
8. `frontend/src/components/StrategyUI.tsx` — no importers
9. `frontend/src/components/DateRangeSelector.tsx` — no importers

### Tier 2 — Unused Imports (Safe, No Behavior Change)
Run: `ruff check ml/src --select F401,F841 --fix` (auto-fix mode)
- 93 unused import removals across 73 files
- Recommend doing this in one shot since ruff's auto-fix is reliable

### Tier 3 — Investigate Before Acting
1. `ml/src/ga_training_job.py` — check if called by scheduler/shell scripts
2. `ml/src/ranking_evaluation_job.py` — same
3. `ml/src/options_snapshot_job.py` — same
4. Cross-directory duplicates (`forecast_validator`, `greeks_validator`, `walk_forward`, `weight_optimizer`) — determine which copy is canonical
5. Dev-only edge functions (`apply-rls-fix`, etc.) — check GitHub Actions before deleting

### Tier 4 — Potential Silent Bugs (Investigate)
1. `support_resistance_detector.py` — F811 redefined `find_all_levels` function
2. `divergence_monitor` created but never used in `intraday_forecast_job.py`
3. `combined` variable discarded in `forecast_synthesizer.py`
4. `oos_equity_series` discarded in `optimization/walk_forward.py`
5. `data_quality_score` computed but unused in `unified_forecast_job.py`

---

## Next Steps for New Chat

1. Get user approval on Tier 1 deletions
2. Run `ruff --fix` for Tier 2 imports
3. Investigate Tier 3 files (check scheduler, GitHub Actions)
4. Review Tier 4 potential bugs file by file

### Commands for Next Chat

```bash
# Check if orphaned job files are called by any scheduler or shell script
grep -r "ga_training_job\|ranking_evaluation_job\|options_snapshot_job" /Users/ericpeterson/SwiftBolt_ML --include="*.py" --include="*.sh" --include="*.yml" --include="*.yaml" | grep -v __pycache__

# Check GitHub Actions for references to dev edge functions  
grep -r "apply-rls-fix\|check-rls\|create-pr-helper\|test-schema\|ga-strategy" /Users/ericpeterson/SwiftBolt_ML/.github --include="*.yml"

# Ruff auto-fix for unused imports (after approval)
cd /Users/ericpeterson/SwiftBolt_ML && ruff check ml/src --select F401,F841 --fix --exclude ml/src/_legacy

# Investigate cross-directory duplicates
grep -rn "from src.monitoring.forecast_validator\|from src.forecast_validator" ml/src --include="*.py" | grep -v __pycache__
grep -rn "from src.monitoring.greeks_validator\|from src.validation.greeks_validator" ml/src --include="*.py" | grep -v __pycache__
```
