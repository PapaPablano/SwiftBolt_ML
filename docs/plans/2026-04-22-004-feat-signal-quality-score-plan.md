---
title: "feat: Signal quality score + calibration badge"
type: feat
status: active
date: 2026-04-22
origin: docs/brainstorms/2026-04-22-signal-quality-score-brainstorm.md
---

# feat: Signal Quality Score + Calibration Badge

## Overview

Add a per-symbol, per-horizon signal quality score (0-100) to forecasts and surface it as a calibration badge in the SwiftUI chart. The score combines walk-forward accuracy, confidence interval tightness, and regime alignment. Displayed as an informational badge — no automated trading behavior changes.

## Requirements Trace

- R1. Compute signal quality score (0-100) from accuracy + confidence width + regime alignment
- R4. Add `signalQuality`, `calibrationLabel`, `accuracyPct` to chart response `mlSummary`
- R6. Show calibration badge in ForecastHorizonsView (green/yellow/red dot + label)
- R9. Score formula: 50% accuracy + 30% confidence tightness + 20% regime alignment
- R10. Labels: 70+ green "well-calibrated", 40-69 yellow "moderate", 0-39 red "uncalibrated"

## Scope Boundaries

- **In scope:** Score computation in evaluation job, chart API enrichment, Swift badge
- **Out of scope:** Position sizing, trade gating, React dashboard, score history

## Implementation Units

- [ ] **Unit 1: Add signal_quality column and compute score in evaluation job**

**Goal:** Compute and persist the signal quality score during ML evaluation.

**Requirements:** R1, R9

**Files:**
- Create: `supabase/migrations/YYYYMMDDHHMMSS_add_signal_quality.sql`
- Modify: `ml/src/evaluation_job_daily.py` or `ml/src/services/validation_service.py`

**Approach:**
- Add `signal_quality INTEGER`, `calibration_label VARCHAR(20)`, `accuracy_pct NUMERIC(5,2)` columns to `ml_forecasts` and `ml_forecasts_intraday`
- After computing walk-forward accuracy in the evaluation job, compute the score:
  - `accuracy_component = min(100, max(0, (accuracy - 0.45) / 0.2 * 100))` — normalizes 45%-65% accuracy range to 0-100
  - `confidence_component` — inverse of confidence interval width, normalized to 0-100
  - `regime_component` — 100 if regime matches forecast direction, 50 if neutral, 0 if opposing
  - `quality = 0.5 * accuracy_component + 0.3 * confidence_component + 0.2 * regime_component`
- Write score to the forecast row via UPDATE after evaluation completes

**Test scenarios:**
- Happy path: 60% accuracy + tight confidence + aligned regime → score ~80, "well-calibrated"
- Happy path: 50% accuracy + wide confidence + choppy regime → score ~30, "uncalibrated"
- Edge case: No validation metrics yet for symbol → score NULL, label NULL
- Edge case: Accuracy exactly at label boundaries (40, 70) → correct label assignment

**Verification:** `ml_forecasts` rows have non-null `signal_quality` after evaluation run

---

- [ ] **Unit 2: Add signal quality to chart response**

**Goal:** Include the score in the chart endpoint's mlSummary.

**Requirements:** R4, R5

**Files:**
- Modify: `supabase/functions/chart/index.ts`
- Modify: `supabase/functions/_shared/chart-types.ts`

**Approach:**
- Add `signalQuality`, `calibrationLabel`, `accuracyPct` to the `HorizonForecast` type in chart-types.ts
- In chart/index.ts where mlSummary horizons are built, read `signal_quality`, `calibration_label`, `accuracy_pct` from the forecast row and include in the response
- Fields are optional — absent when score hasn't been computed yet

**Test scenarios:**
- Happy path: Chart response includes signalQuality in each horizon's data
- Edge case: Forecast exists but no score computed yet → fields absent (not null)

**Verification:** `GET /chart?symbol=AAPL&timeframe=d1` response includes `signalQuality` in mlSummary horizons

---

- [ ] **Unit 3: Add calibration badge to SwiftUI ForecastHorizonsView**

**Goal:** Display colored calibration badge next to each forecast horizon.

**Requirements:** R6, R7, R8, R10

**Files:**
- Modify: `client-macos/SwiftBoltML/Views/ForecastHorizonsView.swift`
- Modify: `client-macos/SwiftBoltML/Models/ChartDataV2Response.swift`

**Approach:**
- Add `signalQuality: Int?`, `calibrationLabel: String?`, `accuracyPct: Double?` to the Swift forecast horizon model
- In ForecastHorizonsView, next to each horizon label, show a small colored circle (green/yellow/red based on calibrationLabel) + text like "58% · well-calibrated"
- Use DesignTokens.Colors.success/warning/error for the dot colors
- When signalQuality is nil, don't show the badge (graceful degradation)

**Test scenarios:**
- Happy path: Badge shows green dot + "58% · well-calibrated" for score 75
- Happy path: Badge shows red dot + "51% · uncalibrated" for score 30
- Edge case: signalQuality nil → no badge shown, no crash
- Edge case: All horizons have scores → badges visible for each

**Verification:** Build succeeds. Forecast horizons show colored calibration badges.

## System-Wide Impact

- **Interaction graph:** Evaluation job writes score → chart reads it → Swift displays it. No new APIs or data flows beyond additive columns.
- **Unchanged invariants:** Chart response shape is additive only. Existing clients unaffected.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Accuracy distribution too narrow (all 50-55%) → labels all "uncalibrated" | Adjust normalization bounds based on actual distribution during implementation |
| Regime features not available at evaluation time | Fall back to 0 for regime component, making it accuracy + confidence only |

## Sources & References

- **Origin:** [docs/brainstorms/2026-04-22-signal-quality-score-brainstorm.md](docs/brainstorms/2026-04-22-signal-quality-score-brainstorm.md)
- Validation tables: `forecast_validation_metrics`, `ensemble_validation_metrics`
- Chart types: `supabase/functions/_shared/chart-types.ts`
- Forecast view: `client-macos/SwiftBoltML/Views/ForecastHorizonsView.swift`
