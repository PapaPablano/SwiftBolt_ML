---
date: 2026-04-22
topic: forecast-accuracy-risks
---

# Forecast Accuracy Risks — Intraday Horizon, DateTime, and Fallback Issues

## Problem Frame

Three forecast accuracy risks were identified during the full-stack pipeline audit but deferred from the initial fix plan. All three affect the correctness of intraday forecasts — the system may be training on wrong labels, synthesizing wrong timestamps, or serving wrong horizon data.

## Requirements

**Intraday Horizon Label Mismatch**
- R1. The `horizon_days` value for both 15m and 1h horizons in `HORIZON_CONFIG` (`ml/src/intraday_forecast_job.py:70,81`) is `0.0417`. When consumed by `BaselineForecaster.prepare_training_data`, it calls `max(1, int(np.ceil(horizon_days)))` which produces `1` — meaning the training label is a 1-day-ahead return, not a 15-minute or 1-hour return. Either `horizon_days` must use a sub-day unit that the training pipeline understands, or `prepare_training_data` must handle fractional days correctly for intraday horizons.
- R2. Verify whether `horizon_days` is used ONLY for `_build_forecast_points` timestamp calculation (where 0.0417 is correct as a fraction of a day) or also for label construction in the training loop (where it's wrong). The fix depends on which paths consume it.

**ARIMA-GARCH DateTime Synthesis**
- R3. `_ensure_datetime_index` (`ml/src/models/arima_garch_forecaster.py:98-106`) synthesizes a `date_range` ending at `pd.Timestamp.now()` with `freq="B"` (business days) when the input series has no DatetimeIndex. This creates artificial timestamps that don't match actual bar timestamps. If any downstream code joins on timestamps or uses them for temporal alignment, the synthetic dates will produce incorrect results.
- R4. Determine whether ARIMA-GARCH is used in the intraday path (where freq="B" is wrong for minute/hour bars) or only in the daily path (where business-day frequency is reasonable).

**h4 Timeframe Silent Fallback**
- R5. The chart endpoint (`supabase/functions/chart/index.ts:670`) maps `h4` to `h1` for intraday forecast lookup: `const intradayHorizonTf = timeframe === "h4" ? "h1" : timeframe`. If no `h1` intraday forecast exists, the entire intraday branch is skipped and the chart falls back to daily forecasts — with no indication to the user. The horizon label at line 1102 then shows "1h" even though the data came from a daily source.
- R6. Either produce h4-specific intraday forecasts, or make the fallback explicit in the response (e.g., `forecastSource: "daily_fallback"`) so the client can display appropriate context.

## Success Criteria

- Intraday forecast training labels match the actual prediction horizon (15m label for 15m, 1h label for 1h — not 1-day)
- ARIMA-GARCH datetime synthesis uses appropriate frequency for the timeframe being processed
- h4 chart requests either get h4-specific forecasts or clearly indicate the forecast is a daily fallback

## Scope Boundaries

- **In scope:** The 3 accuracy risks above, investigation to determine actual severity, targeted fixes
- **Out of scope:** New model architectures, retraining (separate step), other deferred P3 items
- **Non-goal:** Changing the ARIMA-GARCH model itself — only fixing the datetime handling

## Key Decisions

- **Investigate before fixing:** R2 and R4 require reading more code to determine actual severity. The issues may be less severe than they appear if `horizon_days` is only used for timestamp calculation (not label construction) and ARIMA-GARCH is only used in the daily path.
- **Fix what's confirmed, defer what's not:** If investigation shows R1 is only a timestamp issue (correct behavior), close it. If it's a real label mismatch, fix it.

## Outstanding Questions

### Resolve During Planning
- [Affects R1-R2][Needs research] Trace all consumers of `horizon_days` in `intraday_forecast_job.py` — is it used in `BaselineForecaster.prepare_training_data` for intraday horizons, or only for forecast point timestamp construction?
- [Affects R3-R4][Needs research] Is `ArimaGarchForecaster` invoked from `intraday_forecast_job.py` for 15m/1h horizons, or only from `unified_forecast_job.py` for daily horizons?
- [Affects R5-R6][Technical] Does the ML pipeline actually produce h4-specific intraday forecasts, or is h4 only served through daily forecasts by design?

## Next Steps

-> `/ce:plan` to investigate and fix confirmed issues
