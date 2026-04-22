---
date: 2026-04-22
topic: forecast-pipeline-integrity
---

# Forecast Pipeline Integrity — Full-Stack Fixes

## Problem Frame

A full-stack audit of the ML forecasting → Edge Function serving → SwiftUI chart rendering pipeline found 5 P1 and 11 P2 issues. The most critical are temporal integrity violations in the ML pipeline: XGBoost's early-stopping eval set uses random shuffle (leaking future data), and the PurgedWalkForwardCV includes post-test-fold data in training folds. These fundamental issues undermine forecast quality. Downstream, the Edge Functions have a type contract mismatch (Unix seconds vs ms) and an unbounded query, while the Swift client has stale-state bugs on symbol switch and incorrect cache staleness defaults.

## Requirements

**ML Pipeline — Temporal Integrity (P1)**
- R1. XGBoost early-stopping eval set must use temporal split, not random shuffle (`ml/src/models/xgboost_forecaster.py:162`)
- R2. PurgedWalkForwardCV must restrict training to indices strictly before test fold — remove the concatenation of post-test indices (`ml/src/evaluation/purged_walk_forward_cv.py:79`)

**ML Pipeline — Data Leakage Prevention (P2)**
- R3. LSTM MinMaxScaler must be fit only on training data, not the full series (`ml/src/models/lstm_forecaster.py:215`)
- R4. STRICT_LOOKAHEAD_CHECK must guard ARIMA-GARCH and LSTM paths, not just `compute_simplified_features` (`ml/src/unified_forecast_job.py:96`)
- R5. Ensemble GB eval_set scaling must be consistent with training data (`ml/src/models/ensemble_forecaster.py:347`)
- R6. `horizon_days` loop variable must not be overwritten inside synthesis block (`ml/src/unified_forecast_job.py:705`)

**Edge Functions — Contract & Query Correctness (P1+P2)**
- R7. ForecastPoint.ts type contract must match actual data: either deliver Unix ms or update the type declaration to say Unix seconds (`supabase/functions/chart/index.ts:1337` + `_shared/chart-types.ts`)
- R8. Cascade forecast rows must be scoped per horizon — `is_consensus` must not bleed across horizons (`supabase/functions/get-multi-horizon-forecasts/index.ts:343`)
- R9. `ml_forecasts` query must have explicit `.limit()` to prevent PostgREST truncation (`supabase/functions/chart/index.ts:1047`)

**Swift Client — Stale State & Rendering (P1+P2)**
- R10. `selectedForecastHorizon` must reset on symbol switch, not rely on deferred `loadChart` (`client-macos/SwiftBoltML/ViewModels/ChartViewModel.swift:15`)
- R11. `aggregateIntradayToday` must return nil (not zero-priced OHLCBar) when no intraday bars match (`client-macos/SwiftBoltML/ViewModels/ChartViewModel.swift:1298`)
- R12. `chartDataV2` must clear immediately on symbol switch, not after 100ms debounce (`client-macos/SwiftBoltML/ViewModels/ChartViewModel.swift:15`)
- R13. `rebuildSelectedForecastBars` must not create hybrids from different fetch cycles (`client-macos/SwiftBoltML/ViewModels/ChartViewModel.swift:494`)
- R14. `isDataStale` must default to `false` (not `true`) when `dataQuality` is nil (`client-macos/SwiftBoltML/Models/ChartDataV2Response.swift:272`)
- R15. ForecastHorizonsView must re-default horizon when horizon list changes after symbol switch (`client-macos/SwiftBoltML/Views/ForecastHorizonsView.swift:99`)
- R16. `loadMultiTimeframeForecasts` must cancel in-flight tasks on symbol change (`client-macos/SwiftBoltML/ViewModels/ChartViewModel.swift:1143`)

## Success Criteria

- All ML model training uses strictly temporal data ordering — no future data in training or early-stopping sets
- Walk-forward CV folds contain only past data in training indices
- STRICT_LOOKAHEAD_CHECK guards all model paths, not just one
- ForecastPoint.ts type matches actual delivered units across all consumers
- Symbol switching in the Swift app shows no stale forecast data from the previous symbol
- No zero-priced candles appear from timezone edge cases

## Scope Boundaries

- **In scope:** All 16 P1+P2 issues from the audit across ML, Edge Functions, and Swift
- **Out of scope:** P3 issues (zero-bar fresh status, range band collapse), new model architectures, forecast accuracy improvements beyond fixing data leakage, intraday horizon_days mapping issue (needs separate investigation)
- **Non-goal:** Retraining models — fix the code first, retrain in a separate step

## Key Decisions

- **Fix code, don't retrain yet:** Fix all temporal integrity issues first, then retrain models in a dedicated run. Retraining on leaked data would contaminate the new results.
- **Three independent tracks:** ML fixes (R1-R6), Edge Function fixes (R7-R9), and Swift fixes (R10-R16) can be developed in parallel on separate branches.
- **ForecastPoint.ts resolution:** Update the type declaration to say Unix seconds (since the round-trip conversion is correct internally) and audit Swift/React consumers that may parse as ms.

## Dependencies / Assumptions

- ML fixes require access to the Python environment (`ml/.venv`)
- Edge Function fixes can be deployed independently
- Swift fixes require Xcode build verification
- Model retraining should happen AFTER all R1-R6 fixes are merged

## Outstanding Questions

### Deferred to Planning
- [Affects R5][Technical] Verify whether GradientBoostingForecaster.train() does its own internal scaling — determines if the ensemble eval_set mismatch is real or a false positive
- [Affects R7][Technical] Audit all Swift and React consumers of `ForecastPoint.ts` to determine which interpretation (seconds vs ms) each uses
- [Affects R4][Needs research] Determine what specific checks the ARIMA-GARCH and LSTM lookahead guards should perform

## Next Steps

-> `/ce:plan` for structured implementation planning across all 3 tracks
