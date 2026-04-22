---
date: 2026-04-22
topic: open-ideation
focus: platform improvements after full-stack rationalization
---

# Ideation: SwiftBolt ML Platform Improvements

## Survivors (7)

### 1. Unified Signal Quality Score ⭐ SELECTED
Single per-symbol composite score (walk-forward accuracy + confidence width + regime alignment) surfaced everywhere. Every downstream decision consumes one number.
- **Confidence:** High | **Complexity:** Medium
- **Grounding:** `forecast_validation_metrics`, `ensemble_validation_metrics`, regime features in `ml/src/features/`

### 2. Regime-Aware Position Sizing
Wire regime features into executor position sizing. Trend → size up, chop → scale down.
- **Confidence:** High | **Complexity:** Low-Medium
- **Grounding:** Regime features computed in `ml/src/features/`, executor uses flat sizing

### 3. Strategy Auto-Suggestion from Trade History
Mine closed paper trades for winning patterns. Auto-suggest rules from signal co-occurrence.
- **Confidence:** Medium | **Complexity:** High
- **Grounding:** 38-indicator registry + trade history table exist

### 4. Watchlist Morning Briefing
Pre-fetch all watchlist symbols' overnight moves, forecasts, alerts into one view.
- **Confidence:** High | **Complexity:** Medium
- **Grounding:** All data sources exist, needs aggregation endpoint + Swift view

### 5. Strategy Condition Debug Trace
Per-bar evaluation trace showing why conditions did/didn't fire.
- **Confidence:** High | **Complexity:** Medium
- **Grounding:** `condition-evaluator.ts` evaluates but doesn't persist traces

### 6. Adaptive Ensemble Reweighting (Online)
Auto-update ensemble weights after each evaluation cycle. Make `IntradayDailyFeedback` write-back.
- **Confidence:** High | **Complexity:** Low
- **Grounding:** Feedback class exists, evaluation jobs compute accuracy

### 7. Forecast Confidence Calibration Display ⭐ SELECTED
Show calibration quality next to forecasts: "1D accuracy: 58%, well-calibrated."
- **Confidence:** High | **Complexity:** Low
- **Grounding:** `forecast_validation_metrics` table exists, chart API supports additive fields

## Rejected Ideas (20)

- Kill ML pipeline — contradicts accuracy priority
- Forecast-free signal layer — contradicts accuracy priority
- Web-only client — macOS app just redesigned
- Weekly ML = spreadsheet — provocative but not actionable without A/B
- Collapse 30 dirs to 3 — cleanup, not product improvement
- WebSocket ingest — infrastructure complexity
- Continuous learning — high-risk ML architecture change
- Self-validating deploys — low user-facing impact
- Remove Edge Functions surface — already done (PR #36)
- Migration git hook — trivial DX
- Client-side indicator cache — premature optimization
- Auto-generate API registry — already done (PR #34)
- Disabled feature tracker — just file an issue
- Options delta hedge signal — niche
- Duplicates: regime tagging (2x), correlation guard (2x), sentiment circuit breaker (2x)

## Session Log

- 2026-04-22: Generated 35 raw ideas across 4 frames (user pain, inversion, leverage, assumption-breaking). Filtered to 7 survivors. Selected #1 + #7 for brainstorming.
