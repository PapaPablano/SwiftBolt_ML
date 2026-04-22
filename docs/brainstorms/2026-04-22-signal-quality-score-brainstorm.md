---
date: 2026-04-22
topic: signal-quality-score
---

# Unified Signal Quality Score + Calibration Display

## Problem Frame

The ML pipeline produces forecasts with ensemble weights, walk-forward validation metrics, and regime features — but none of this reaches the user. The chart shows directional arrows without communicating how trustworthy the signal is. Users can't distinguish a well-calibrated 1D forecast (58% accuracy, trending regime, tight confidence band) from a noisy one (51% accuracy, choppy regime, wide band). This leads to overconfidence in weak signals and underconfidence in strong ones.

## Requirements

**Backend Score Computation**
- R1. Compute a per-symbol, per-horizon signal quality score (0-100) combining: (a) walk-forward accuracy from `forecast_validation_metrics`, (b) ensemble confidence interval width from `ml_forecasts`, and (c) regime alignment from computed regime features
- R2. Store the score in `ml_forecasts` / `ml_forecasts_intraday` (additive column) so the chart endpoint can read it without a separate query
- R3. Recompute the score on each training run and each evaluation cycle — NOT on every Kalman adjustment tick (too expensive)

**Chart API Surface**
- R4. Add signal quality fields to the chart response `mlSummary` object: `signalQuality` (0-100 integer), `calibrationLabel` (string: "well-calibrated" / "moderate" / "uncalibrated"), and `accuracyPct` (walk-forward accuracy percentage for this horizon)
- R5. These fields are additive and optional — existing clients that don't read them are unaffected

**Swift Client Display**
- R6. Show a compact calibration badge next to each forecast horizon in the chart view: colored dot (green/yellow/red) + label (e.g., "1D: 58% accuracy, well-calibrated")
- R7. The badge is informational only — does NOT gate trading decisions, block paper trades, or influence position sizing
- R8. Badge shows in the ForecastHorizonsView component alongside existing horizon data

**Score Formula**
- R9. The score formula is: `quality = (accuracy_weight * normalized_accuracy) + (confidence_weight * normalized_confidence_tightness) + (regime_weight * regime_alignment_score)`. Default weights: 50% accuracy, 30% confidence tightness, 20% regime alignment. Tunable via config, not hardcoded.
- R10. Calibration labels: 70-100 → "well-calibrated" (green), 40-69 → "moderate" (yellow), 0-39 → "uncalibrated" (red)

## Success Criteria

- Every forecast horizon in the chart response includes `signalQuality`, `calibrationLabel`, and `accuracyPct`
- The Swift chart view shows a colored calibration badge next to each forecast
- The score uses real walk-forward metrics — not synthetic or placeholder data
- Users can glance at the badge and immediately know whether to trust the signal

## Scope Boundaries

- **In scope:** Score computation, chart API enrichment, Swift badge display
- **Out of scope:** Score-driven position sizing, paper trade gating, React dashboard display (follow-up), score history/trending
- **Non-goal:** Replacing the existing forecast display — the badge augments, doesn't replace

## Key Decisions

- **Informational only:** The score is a display primitive. No automated behavior changes based on the score. This keeps scope tight and avoids premature coupling.
- **Compute on training/evaluation, not on Kalman ticks:** The score inputs (accuracy, regime) don't change minute-by-minute. Recompute when evaluation runs, not on every price adjustment.
- **Additive API change:** New optional fields in `mlSummary` per CLAUDE.md convention — non-breaking for existing clients.
- **Three-component weighted score:** Simple enough to explain, rich enough to be meaningful. Weights are configurable for future tuning.

## Dependencies / Assumptions

- `forecast_validation_metrics` table contains per-symbol, per-horizon accuracy data (verified: exists in migrations)
- `ml_forecasts` / `ml_forecasts_intraday` tables can accept a new `signal_quality` column (Supabase migration)
- Regime features are computed during training and accessible at evaluation time
- The chart endpoint already returns `mlSummary` with forecast data

## Outstanding Questions

### Deferred to Planning
- [Affects R1][Needs research] What's the current walk-forward accuracy distribution across symbols? If most are 50-55%, the score range may be narrow and labels need adjustment.
- [Affects R9][Technical] How to normalize confidence interval width into 0-1 range — use historical distribution or fixed bounds?
- [Affects R1][Technical] Are regime features available at chart-read time, or only at training time? This affects whether the score can be recomputed dynamically or must be pre-computed.

## Next Steps

-> `/ce:plan` for structured implementation planning
