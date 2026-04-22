---
date: 2026-04-22
topic: 5-10-day-forecast-improvement
---

# Improve 5-10 Day Price Level Forecasting

## Problem Frame

The current 5D and 10D forecasts (LSTM + ARIMA-GARCH ensemble via `ml/src/unified_forecast_job.py`) have poor directional accuracy — barely above a coin flip. They produce point estimates without confidence bands, don't adapt to market regime, and output for every symbol regardless of model confidence. Users need: 55%+ directional accuracy, useful price ranges (not point estimates), and fewer but higher-conviction calls.

## Requirements

**Phase A: Regime Gating + Confidence Suppression (Quick Win)**
- A1. Condition ensemble weights on market regime (trending/choppy/mean-reverting) using existing regime features from `ml/src/features/`
- A2. Add a confidence gate that suppresses 5D/10D forecast output when ensemble internal agreement is below threshold (models disagree on direction)
- A3. Only publish forecasts when: (a) models agree on direction AND (b) the regime supports the forecast type (e.g., don't publish momentum-based calls in choppy regimes)
- A4. Use the signal quality score (just built this session) as the gating metric — forecasts with score < 40 are suppressed
- A5. Suppressed forecasts show "insufficient confidence" in the chart UI instead of a misleading point estimate

**Phase B: Quantile Regression (Full Upgrade)**
- B1. Replace point estimates with quantile predictions: train separate models for the 10th, 25th, 50th, 75th, 90th percentiles of the 5D and 10D price distribution
- B2. XGBoost supports quantile regression natively — use pinball loss for each quantile
- B3. Output price ranges: "AAPL 5D: $265-$275 (50% band), $258-$282 (80% band)"
- B4. Conviction = range width relative to current price. Narrow range = high conviction. Wide = uncertain.
- B5. Walk-forward validation using calibration curves (% of actuals falling within each band) instead of pure accuracy
- B6. Add monotonicity constraint to prevent quantile crossing (10th > 90th)
- B7. Display ranges as shaded bands on the chart (graduated transparency from 50% to 80% band)

## Success Criteria

- Phase A: Fewer but better forecasts — average published accuracy improves from ~50% to 55%+ by filtering out low-confidence calls
- Phase B: Calibrated probability ranges — 50% of actual prices fall within the 50% band, 80% within the 80% band
- Both: Users can distinguish "the model is confident here" from "this is a guess" at a glance

## Scope Boundaries

- **In scope:** 5D and 10D horizons only. Regime gating, confidence suppression, quantile regression, chart visualization.
- **Out of scope:** Intraday horizons (15m/1h/4h), 1D horizon (different dynamics), new model architectures beyond XGBoost quantile, options-implied distribution approach.
- **Non-goal:** Achieving 60%+ accuracy — that's aspirational but unrealistic for medium-term equity forecasting without fundamental data.

## Key Decisions

- **Phase A first:** Regime gating ships with existing infrastructure (signal quality score, regime features). Immediate value.
- **Phase B second:** Quantile regression is the principled solution but needs retraining and new evaluation metrics. Ships after Phase A validates.
- **XGBoost for quantile regression:** Native pinball loss support, already in the codebase, well-tested for tabular data. LSTM doesn't naturally produce quantiles.
- **Suppress, don't lie:** When confidence is low, show "insufficient confidence" rather than a misleading point estimate. Silence is better than noise.

## Dependencies / Assumptions

- Regime features from `ml/src/features/` are accurate enough to condition on (verified as false-alarm-free in the forecast accuracy investigation earlier this session)
- Signal quality score (PR #42, just merged) provides the gating metric for Phase A
- XGBoost quantile regression is available in the installed sklearn/xgboost version
- The chart endpoint's `mlSummary` can carry range data (additive fields, non-breaking)

## Outstanding Questions

### Deferred to Planning
- [Affects A2][Technical] What confidence threshold optimizes the accuracy/coverage tradeoff? Needs backtesting on historical forecasts.
- [Affects B1][Technical] How many training samples per quantile are needed for stable estimates at 5D/10D?
- [Affects B6][Technical] Best approach for monotonicity constraint — sorted output post-hoc, or constrained training?
- [Affects B7][Technical] How should the Swift chart render quantile bands — shaded area overlay on the existing TradingView chart, or separate forecast panel?

## Next Steps

-> `/ce:plan` Phase A first, then Phase B as a follow-up plan
