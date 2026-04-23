---
title: "feat: Quantile regression for 5-10 day probability ranges"
type: feat
status: active
date: 2026-04-22
origin: docs/brainstorms/2026-04-22-5-10-day-forecast-improvement-brainstorm.md
---

# feat: Quantile Regression for 5-10 Day Probability Ranges

## Overview

Replace point estimates for 5D/10D forecasts with calibrated probability ranges using XGBoost quantile regression. Produces 5 percentile bands (10th/25th/50th/75th/90th) displayed as shaded areas on the chart. Users see "AAPL 5D: $265-$275 (50% band)" instead of a single target price.

## Requirements Trace

- B1. Train separate XGBoost models for 10th/25th/50th/75th/90th percentiles at 5D and 10D
- B2. Use pinball loss for each quantile target
- B3. Output price ranges in the chart response
- B4. Conviction = range width relative to price (narrow = high, wide = low)
- B5. Walk-forward validation using calibration curves
- B6. Monotonicity constraint to prevent quantile crossing
- B7. Display ranges as shaded bands on chart

## Scope Boundaries

- **In scope:** 5D and 10D horizons only. XGBoost quantile models, chart API enrichment, Swift/JS chart visualization
- **Out of scope:** Intraday quantiles, 1D horizon, options-implied approach, replacing the LSTM/ARIMA ensemble (quantile layer is additive)

### Deferred to Separate Tasks

- Phase B calibration tuning (after 2+ weeks of data)
- Quantile regression for intraday horizons (different dynamics)

## Key Technical Decisions

- **XGBoost with pinball loss:** Native quantile support via `objective: "reg:quantileerror"` with `quantile_alpha` parameter. One model per quantile (5 models per horizon = 10 total for 5D+10D).
- **Additive to existing ensemble:** Quantile predictions run alongside the existing LSTM+ARIMA-GARCH point estimate, not replacing it. The 50th percentile quantile serves as a cross-check.
- **Post-hoc sorting for monotonicity:** After prediction, sort quantiles to ensure q10 ≤ q25 ≤ q50 ≤ q75 ≤ q90. Simpler than constrained training and works well in practice.
- **Chart visualization:** Shaded bands in the WebView chart (chart.js) using area series. Inner band (25th-75th) darker, outer band (10th-90th) lighter.

## Implementation Units

- [ ] **Unit 1: Train quantile XGBoost models**

**Goal:** Add quantile regression training to the weekly forecast job for 5D and 10D.

**Files:**
- Create: `ml/src/models/quantile_forecaster.py`
- Modify: `ml/src/unified_forecast_job.py`
- Test: `ml/tests/test_quantile_forecaster.py`

**Approach:**
- New `QuantileForecaster` class wrapping XGBoost with pinball loss
- Trains 5 models per horizon (q10, q25, q50, q75, q90) using the same features as the existing ensemble
- Returns a dict: `{horizon: {q10: price, q25: price, q50: price, q75: price, q90: price}}`
- Post-hoc sort to enforce monotonicity
- Integrated into `unified_forecast_job.py` after the existing ensemble forecast

**Test scenarios:**
- Happy path: 5 quantile predictions produced, monotonically ordered
- Happy path: q50 is close to the point estimate from LSTM+ARIMA ensemble
- Edge case: Input features have NaN → graceful fallback to point estimate only
- Edge case: Very small training set (<50 samples) → skip quantile training

**Verification:** `pytest ml/tests/test_quantile_forecaster.py` passes

---

- [ ] **Unit 2: Persist quantile predictions to database**

**Goal:** Store quantile predictions alongside existing forecasts.

**Files:**
- Create: `supabase/migrations/YYYYMMDDHHMMSS_add_quantile_columns.sql`
- Modify: `ml/src/unified_forecast_job.py`

**Approach:**
- Add columns to `ml_forecasts`: `q10 NUMERIC(12,4)`, `q25 NUMERIC(12,4)`, `q50 NUMERIC(12,4)`, `q75 NUMERIC(12,4)`, `q90 NUMERIC(12,4)`
- After quantile prediction, write to the same forecast row via UPDATE
- Null quantile columns = quantile model not yet trained (backward compatible)

**Test scenarios:**
- Happy path: Forecast row has all 5 quantile columns populated
- Edge case: Quantile training skipped → columns stay NULL

**Verification:** `ml_forecasts` rows for 5D/10D have non-null quantile values after training

---

- [ ] **Unit 3: Add quantile data to chart response**

**Goal:** Include quantile bands in the chart endpoint's mlSummary.

**Files:**
- Modify: `supabase/functions/chart/index.ts`
- Modify: `supabase/functions/_shared/chart-types.ts`

**Approach:**
- Add to `HorizonForecast` type: `quantiles?: { q10: number, q25: number, q50: number, q75: number, q90: number }`
- Read quantile columns from the ml_forecasts row and include when non-null
- Add `conviction` computed field: `1 - (q75 - q25) / q50` — higher when range is narrow

**Test scenarios:**
- Happy path: Chart response includes quantiles object in horizon data
- Edge case: Quantiles NULL → field absent (backward compatible)

**Verification:** `GET /chart` response includes quantile bands for 5D/10D horizons

---

- [ ] **Unit 4: Render quantile bands on chart**

**Goal:** Display probability ranges as shaded bands on the TradingView chart.

**Files:**
- Modify: `client-macos/SwiftBoltML/Resources/WebChart/chart.js`
- Modify: `client-macos/SwiftBoltML/Views/WebChartView.swift`

**Approach:**
- In chart.js, when forecast data includes quantiles, render two area series:
  - Inner band (q25-q75): semi-transparent fill (50% band)
  - Outer band (q10-q90): lighter transparent fill (80% band)
  - Median line (q50) as a dashed line
- Colors from existing forecast palette, reduced opacity
- WebChartView passes quantile data through the JS bridge alongside existing forecast points

**Test scenarios:**
- Happy path: Shaded bands visible on chart for 5D forecast
- Happy path: Inner band is visually distinct from outer band
- Edge case: No quantile data → no bands shown (existing point forecast still works)
- Edge case: Very narrow band (high conviction) → thin visible line

**Verification:** Chart shows graduated shaded bands for 5D/10D forecast horizons

---

- [ ] **Unit 5: Add calibration evaluation**

**Goal:** Evaluate quantile calibration as part of the daily evaluation job.

**Files:**
- Modify: `ml/src/evaluation_job_daily.py`
- Create: `ml/src/evaluation/calibration.py`

**Approach:**
- New `compute_calibration_metrics(actuals, quantile_predictions)` function
- For each quantile: what % of actual prices fell below the predicted quantile?
- Perfect calibration: 10% below q10, 25% below q25, etc.
- Output calibration error per quantile and overall calibration score
- Store in `forecast_validation_metrics` or a new `quantile_calibration_metrics` table

**Test scenarios:**
- Happy path: Perfect synthetic data → calibration error ≈ 0
- Happy path: Biased predictions → calibration error reflects the bias
- Edge case: Too few samples for reliable calibration (<20) → skip, log warning

**Verification:** Calibration metrics computed and stored after evaluation run

## System-Wide Impact

- **Interaction graph:** Quantile training runs inside `unified_forecast_job.py` after the existing ensemble. Chart endpoint reads quantile columns from `ml_forecasts`. Chart.js renders bands. All additive — existing flow unchanged.
- **Unchanged invariants:** Existing point estimates, signal quality scores, regime gating — all preserved. Quantile bands are a new additive layer.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Quantile crossing despite post-hoc sort | Sort enforces monotonicity. If predictions are severely crossed, the sort produces a very narrow band — which is a correct "low conviction" signal. |
| 10 new XGBoost models add training time | Each quantile model trains on the same features — can be parallelized. Total overhead ~2x (5 models per horizon vs 1). |
| Calibration takes weeks of data to evaluate | Ship with uncalibrated quantiles first. Add calibration tracking. Tune after 2+ weeks. |

## Sources & References

- **Origin:** [docs/brainstorms/2026-04-22-5-10-day-forecast-improvement-brainstorm.md](docs/brainstorms/2026-04-22-5-10-day-forecast-improvement-brainstorm.md) — Phase B
- XGBoost quantile: `objective: "reg:quantileerror"`, `quantile_alpha` parameter
- Existing XGBoost: `ml/src/models/xgboost_forecaster.py`
- Chart.js area series: TradingView Lightweight Charts `addAreaSeries()`
