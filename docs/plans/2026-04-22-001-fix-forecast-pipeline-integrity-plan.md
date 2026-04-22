---
title: "fix: Forecast pipeline temporal integrity and data flow fixes"
type: fix
status: completed
date: 2026-04-22
origin: docs/brainstorms/2026-04-22-forecast-pipeline-integrity-brainstorm.md
---

# fix: Forecast Pipeline Temporal Integrity and Data Flow Fixes

## Overview

Fix 16 issues across the ML forecast pipeline (temporal integrity violations), Edge Function serving layer (type contract + query bugs), and Swift chart rendering (stale state on symbol switch). The ML fixes are the highest impact — XGBoost and walk-forward CV currently leak future data into training.

## Problem Frame

Full-stack audit found fundamental temporal integrity violations: XGBoost uses random shuffle for early-stopping eval (future data leaks into training), PurgedWalkForwardCV includes post-test data in training folds, and LSTM scaler is fit on the full series. Downstream, ForecastPoint timestamps use seconds but the type says ms, and the Swift client shows stale forecasts during symbol switching. (see origin: `docs/brainstorms/2026-04-22-forecast-pipeline-integrity-brainstorm.md`)

## Requirements Trace

**ML (R1-R6):** R1. XGBoost temporal split, R2. Walk-forward CV fix, R3. LSTM scaler split, R4. Lookahead guard coverage, R5. Ensemble scaling consistency, R6. horizon_days variable safety

**Edge Functions (R7-R9):** R7. ForecastPoint.ts unit fix, R8. Cascade horizon scoping, R9. ml_forecasts query limit

**Swift (R10-R16):** R10. Horizon reset on symbol switch, R11. aggregateIntradayToday nil return, R12. chartDataV2 immediate clear, R13. No hybrid fetch-cycle mixing, R14. isDataStale default false, R15. Horizon picker re-default, R16. Cancel in-flight multiTimeframe tasks

## Scope Boundaries

- **In scope:** All 16 P1+P2 issues from audit
- **Out of scope:** P3 issues, model retraining (separate step after code fixes), new model architectures
- **Non-goal:** Improving forecast accuracy beyond fixing data leakage

### Deferred to Separate Tasks

- Model retraining after R1-R6 fixes merge
- Intraday horizon_days mapping investigation (1h → 0.0417 → ceil to 1 day)

## Phased Delivery

### Phase A: ML Pipeline (R1-R6) — one branch, one PR
### Phase B: Edge Functions (R7-R9) — one branch, one PR  
### Phase C: Swift Client (R10-R16) — one branch, one PR

All 3 phases are independent and can execute in parallel.

## Implementation Units

### Phase A: ML Pipeline

- [x] **Unit 1: Fix XGBoost temporal split (R1)**

**Goal:** Replace random shuffle train_test_split with temporal split for early-stopping eval set.

**Files:**
- Modify: `ml/src/models/xgboost_forecaster.py`
- Test: `ml/tests/test_xgboost_forecaster.py`

**Approach:** Replace `train_test_split(X_scaled, y, test_size=0.2)` with temporal split: `split_idx = int(len(X_scaled) * 0.8)`, `X_tr = X_scaled[:split_idx]`, `X_es = X_scaled[split_idx:]`.

**Execution note:** Write a test first that asserts eval set indices are all >= max(train set indices).

**Test scenarios:**
- Happy path: After split, all eval set timestamps are after all training set timestamps
- Edge case: Dataset with < 5 samples — split still produces valid non-empty train and eval sets
- Integration: Model trains without error and produces predictions after temporal split

**Verification:** `pytest ml/tests/test_xgboost_forecaster.py` passes with temporal ordering assertion

---

- [x] **Unit 2: Fix PurgedWalkForwardCV (R2)**

**Goal:** Remove future data from training folds.

**Files:**
- Modify: `ml/src/evaluation/purged_walk_forward_cv.py`
- Test: `ml/tests/test_purged_walk_forward_cv.py`

**Approach:** Line 79: remove the second concatenation that adds `np.arange(embargo_end, n_samples)`. Training indices must be `np.arange(0, test_start)` only.

**Execution note:** Write a test first that asserts max(train_indices) < min(test_indices) for every fold.

**Test scenarios:**
- Happy path: For each fold, all training indices < all test indices
- Happy path: Embargo gap between train end and test start is respected
- Edge case: First fold — training set may be very small
- Edge case: Last fold — test set extends to end of dataset

**Verification:** All folds pass temporal ordering assertion

---

- [x] **Unit 3: Fix LSTM scaler + lookahead guards + ensemble + horizon_days (R3-R6)**

**Goal:** Fix remaining 4 ML P2 issues in a single unit since they're independent one-line fixes.

**Files:**
- Modify: `ml/src/models/lstm_forecaster.py` (R3 — scaler fit on train only)
- Modify: `ml/src/unified_forecast_job.py` (R4 — extend lookahead guard, R6 — rename variable)
- Modify: `ml/src/models/ensemble_forecaster.py` (R5 — verify/fix eval_set scaling)

**Approach:**
- R3: Split scaler.fit_transform into fit on train, transform on val
- R4: Add `_maybe_run_strict_guard` calls for ARIMA-GARCH and LSTM paths
- R5: Verify GradientBoostingForecaster.train() scaling — fix if mismatched
- R6: Rename `horizon_days` at line 705 to `h_days_synthesis`

**Test scenarios:**
- R3: LSTM scaler min/max computed from train slice only — val slice has values outside [0,1] when train range is narrower
- R6: Outer loop `horizon_days` value unchanged after synthesis block executes

**Verification:** `pytest ml/tests/ -m "not integration"` passes

### Phase B: Edge Functions

---

- [x] **Unit 4: Fix ForecastPoint.ts type contract (R7)**

**Goal:** Align the type declaration with actual delivered data (Unix seconds).

**Files:**
- Modify: `supabase/functions/_shared/chart-types.ts`

**Approach:** Update the `ForecastPoint.ts` comment from `// Unix ms timestamp` to `// Unix seconds timestamp`. The internal round-trip (toUnixSeconds then *1000) is correct — only the documentation is wrong.

**Test expectation:** none — comment/type documentation fix.

**Verification:** Grep confirms no `chart-types.ts` reference says "ms" for ForecastPoint.ts

---

- [x] **Unit 5: Fix cascade horizon scoping + ml_forecasts limit (R8, R9)**

**Goal:** Fix cascade row bleed and unbounded query.

**Files:**
- Modify: `supabase/functions/get-multi-horizon-forecasts/index.ts` (R8)
- Modify: `supabase/functions/chart/index.ts` (R9)

**Approach:**
- R8: Add horizon tag to cascade rows during collection, filter by `c.horizon === row.horizon` instead of `c.is_consensus`
- R9: Add `.limit(10)` to the ml_forecasts query (generous buffer for 3 horizons)

**Test scenarios:**
- R8: Cascade rows for horizon "1D" do not include rows tagged for "1W"
- R9: Query returns at most 10 rows regardless of historical forecast count

**Verification:** Deploy and verify via smoke test

### Phase C: Swift Client

---

- [x] **Unit 6: Fix symbol-switch stale state (R10, R12, R14)**

**Goal:** Clear all forecast state immediately on symbol switch.

**Files:**
- Modify: `client-macos/SwiftBoltML/ViewModels/ChartViewModel.swift`
- Modify: `client-macos/SwiftBoltML/Models/ChartDataV2Response.swift` (R14)

**Approach:**
- R10: In `selectedSymbol` didSet, add `selectedForecastHorizon = nil` and `_cachedSelectedForecastBars = nil`
- R12: In `selectedSymbol` didSet, add `chartDataV2 = nil` and `chartData = nil` before the debounced loadTask
- R14: Change `dataQuality?.isStale ?? true` to `dataQuality?.isStale ?? false`

**Test scenarios:**
- R10: After symbol switch, selectedForecastHorizon is nil
- R12: After symbol switch, chartDataV2 is nil before loadTask fires
- R14: When dataQuality is nil, isDataStale returns false

**Verification:** Build succeeds. Symbol switch shows no stale forecast from previous symbol.

---

- [x] **Unit 7: Fix aggregateIntradayToday + rebuildSelectedForecastBars + horizon picker + task cancellation (R11, R13, R15, R16)**

**Goal:** Fix remaining Swift P1+P2 issues.

**Files:**
- Modify: `client-macos/SwiftBoltML/ViewModels/ChartViewModel.swift` (R11, R13, R16)
- Modify: `client-macos/SwiftBoltML/Views/ForecastHorizonsView.swift` (R15)

**Approach:**
- R11: Change `aggregateIntradayToday` return type to `OHLCBar?`, return nil when sorted bars is empty
- R13: In `rebuildSelectedForecastBars`, use single authoritative source for both layers and mlSummary
- R15: Add `.onChange(of: horizons)` to re-default selectedHorizon when list changes
- R16: Store multiTimeframe task handle, cancel in selectedSymbol didSet, validate symbol after await

**Test scenarios:**
- R11: aggregateIntradayToday returns nil when no today-bars exist
- R15: After symbol switch with different horizon set, picker shows valid horizon

**Verification:** Build succeeds. No zero-priced candles. Horizon picker always shows valid selection.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| ML fixes change model behavior (forecasts differ after fix) | Expected — current forecasts are based on leaked data. Retrain after merge. |
| R11 return type change (OHLCBar → OHLCBar?) propagates to callers | Check all callers of aggregateIntradayToday and add nil handling |
| R7 type comment change doesn't reach Swift consumers who hardcoded ms interpretation | Grep Swift client for ForecastPoint timestamp parsing during R7 implementation |

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-22-forecast-pipeline-integrity-brainstorm.md](docs/brainstorms/2026-04-22-forecast-pipeline-integrity-brainstorm.md)
- Full audit findings from this session (2026-04-22)
- ML pipeline: `ml/src/models/`, `ml/src/evaluation/`, `ml/src/unified_forecast_job.py`
- Edge Functions: `supabase/functions/chart/index.ts`, `supabase/functions/get-multi-horizon-forecasts/index.ts`
- Swift client: `client-macos/SwiftBoltML/ViewModels/ChartViewModel.swift`, `Views/ForecastHorizonsView.swift`
