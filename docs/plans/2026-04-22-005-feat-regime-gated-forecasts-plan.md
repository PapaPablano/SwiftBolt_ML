---
title: "feat: Regime-gated 5-10 day forecasts with confidence suppression"
type: feat
status: active
date: 2026-04-22
origin: docs/brainstorms/2026-04-22-5-10-day-forecast-improvement-brainstorm.md
---

# feat: Regime-Gated 5-10 Day Forecasts

## Overview

Add regime-conditioned ensemble weighting and confidence-based suppression to 5D/10D forecasts. Only publish forecasts when the signal quality score meets threshold and the market regime supports the prediction type. Suppress low-confidence output with "insufficient confidence" instead of misleading point estimates.

## Requirements Trace

- A1. Condition ensemble weights on market regime
- A2. Suppress forecasts when signal quality score < 40
- A3. Require model directional agreement + regime alignment
- A4. Use existing signal quality score as gating metric
- A5. Show "insufficient confidence" in chart UI for suppressed forecasts

## Implementation Units

- [ ] **Unit 1: Add regime conditioning to unified_forecast_job**

**Goal:** Weight ensemble models based on detected market regime for 5D/10D horizons.

**Files:**
- Modify: `ml/src/unified_forecast_job.py`
- Reference: `ml/src/features/market_regime.py`

**Approach:**
- Before running the ensemble for 5D/10D, detect the current regime via existing `market_regime.py` features
- In trending regimes, increase LSTM weight (momentum-sensitive). In choppy regimes, increase ARIMA-GARCH weight (mean-reversion).
- Apply weights via the existing `IntradayDailyFeedback` weight precedence system

**Test scenarios:**
- Happy path: Trending regime → LSTM weight increases from default
- Happy path: Choppy regime → ARIMA-GARCH weight increases
- Edge case: Regime detection fails → use default weights (no change from current behavior)

**Verification:** Forecast runs with regime-adjusted weights logged

---

- [ ] **Unit 2: Add confidence gate to suppress low-quality forecasts**

**Goal:** Skip publishing 5D/10D forecasts when signal quality score is below threshold.

**Files:**
- Modify: `ml/src/unified_forecast_job.py`
- Modify: `ml/src/evaluation/signal_quality.py`

**Approach:**
- After computing the forecast and signal quality score, check: if `signal_quality < 40`, mark the forecast as `suppressed: true` in `ml_forecasts`
- Add a `suppressed BOOLEAN DEFAULT FALSE` column to `ml_forecasts` (migration)
- Suppressed forecasts are still stored (for evaluation) but the chart endpoint skips them

**Test scenarios:**
- Happy path: Score ≥ 40 → forecast published normally
- Happy path: Score < 40 → forecast stored with `suppressed: true`
- Edge case: Score is NULL (not yet computed) → don't suppress (backward compatible)

**Verification:** Low-confidence forecasts marked as suppressed in DB

---

- [ ] **Unit 3: Chart endpoint respects suppression + UI shows "insufficient confidence"**

**Goal:** Chart endpoint skips suppressed forecasts; Swift UI shows informational message.

**Files:**
- Modify: `supabase/functions/chart/index.ts`
- Modify: `client-macos/SwiftBoltML/Views/ForecastHorizonsView.swift`
- Create: `supabase/migrations/YYYYMMDDHHMMSS_add_forecast_suppressed.sql`

**Approach:**
- Migration: add `suppressed BOOLEAN DEFAULT FALSE` to `ml_forecasts`
- Chart endpoint: filter `suppressed = false` in the ml_forecasts query (or exclude suppressed from mlSummary)
- Swift: when a horizon has no forecast data (suppressed), show a subtle "Insufficient confidence" label instead of blank space

**Test scenarios:**
- Happy path: Non-suppressed forecast shows normally in chart
- Happy path: Suppressed forecast → "Insufficient confidence" label in UI
- Edge case: All horizons suppressed → chart shows bars without any forecast overlay

**Verification:** Suppressed forecasts don't appear as price predictions in chart; label visible

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Regime detection too aggressive → suppresses too many forecasts | Start with low threshold (score < 40). Tune after 1 week of data. |
| Signal quality not yet computed for 5D/10D | Score computation runs in evaluation job. First training run after this ships will populate scores. |

## Sources & References

- **Origin:** [docs/brainstorms/2026-04-22-5-10-day-forecast-improvement-brainstorm.md](docs/brainstorms/2026-04-22-5-10-day-forecast-improvement-brainstorm.md)
- Signal quality: `ml/src/evaluation/signal_quality.py` (just built this session)
- Regime features: `ml/src/features/market_regime.py`
- Ensemble weights: `ml/src/intraday_daily_feedback.py`
