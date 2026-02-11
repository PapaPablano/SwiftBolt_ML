# Forecasting Implementation Mapping
## Document-to-Code Crosswalk (1D / 1W / 1M Focus)

**Last Updated:** January 2026

This file maps guidance from:
- `FORECASTING_QUICK_REFERENCE.md`
- `STOCK_FORECASTING_FRAMEWORK.md`
- `SWIFT_BOLT_IMPLEMENTATION.md`

to the **current SwiftBolt_ML codebase** and highlights what’s already implemented vs. what remains.

---

## 1) Price Target Framework (Anchor Zones + Multi‑Layer S/R + Directional Targets + Quality)

**Docs**
- Quick Reference: “Actionable price targets” + daily decision rules
- Framework: S/R, risk management, multi‑horizon logic

**Implemented**
- **Anchor zones** + **multi‑layer S/R** + **directional TP ladder** + **confluence/quality**
  - `ml/src/features/support_resistance_detector.py`
    - `calculate_anchor_zones()`
    - `calculate_moving_average_levels()`
    - `calculate_ichimoku_levels()`
    - `find_all_levels()` now aggregates: anchor zones, pivots, polynomial, logistic, MAs, Fibonacci, Ichimoku
  - `ml/src/forecast_weights.py`
    - `sr_weights` now matches the 6‑method weighting (anchor, pivots, polynomial, MAs, Fibonacci, Ichimoku)
  - `ml/src/forecast_synthesizer.py`
    - `_normalize_sr_response()` standardizes S/R input
    - `_build_price_targets()` generates TP1/TP2/TP3 + stop
    - `_score_target_confluence()` computes confluence/quality score
    - TP1 now becomes the primary target for forecasts

**Output / Storage**
- Target ladder + quality stored in `synthesis_data`:
  - `ml/src/unified_forecast_job.py` (writes `synthesis_data` to `ml_forecasts`)

---

## 2) Horizon Focus (1D / 1W / 1M only)

**Docs**
- Framework: “different models by horizon”
- Request: focus on 1D / 1W / 1M for now

**Implemented**
- `ml/src/unified_forecast_job.py`
  - filters horizons to `{1D, 1W, 1M}`
  - 1D uses `generate_1d_forecast`; 1W/1M use `generate_forecast(horizon_days=...)`
- `backend/supabase/functions/user-refresh/index.ts`
  - queues only `1D/1W/1M`
- `backend/supabase/functions/symbol-init/index.ts`
  - required horizons = `1D/1W/1M`
- `backend/supabase/functions/chart-data-v2/index.ts`
  - `DAILY_FORECAST_HORIZONS` limited to `1D/1W/1M`

---

## 3) Directional Quality / Confidence Rules

**Docs**
- Quick Reference: confidence thresholds, stale forecast checks
- Framework: ensemble agreement, validation standards

**Implemented**
- `ml/src/monitoring/forecast_quality.py`
  - `compute_quality_score()`
  - `check_quality_issues()` (low confidence, disagreement, staleness)
- `ml/scripts/run_forecast_quality.py`
  - CLI to fetch and report quality per symbol/horizon

**Gaps / Next Step**
- **Implemented** confidence gating + quality issues in forecast job:
  - `ml/src/unified_forecast_job.py` adds confidence threshold checks and persists `quality_score` + `quality_issues`.

---

## 4) S/R Methods & Market Structure

**Docs**
- Framework: multiple S/R methods + weighting + confluence

**Implemented**
- `ml/src/features/support_resistance_detector.py`
  - Pivot Levels
  - Polynomial SR
  - Logistic SR
  - Anchor Zones (new)
  - Moving Averages (new)
  - Fibonacci (new)
  - Ichimoku (new)

**Note**
- The legacy “methods” section now includes these for backward‑compat reads.

---

## 5) Forecast Synthesis Logic

**Docs**
- Framework: trend, SR constraints, ensemble agreement

**Implemented**
- `ml/src/forecast_synthesizer.py`
  - 3‑layer synthesis: SuperTrend + S/R constraints + ML ensemble
  - confidence boosts/penalties
  - directional target logic for TP ladder

---

## 6) Operational Flow (Triggering / Refresh)

**Docs**
- Quick Reference: “daily/weekly operational checks”

**Implemented**
- `backend/supabase/functions/user-refresh/index.ts`
  - queues forecast + S/R + options updates
- `backend/supabase/functions/symbol-init/index.ts`
  - ensures data + queues ML forecast
- `backend/supabase/functions/chart-data-v2/index.ts`
  - returns forecast data for charting

**Gaps / Next Step**
- **Implemented** ops check CLI:
  - `ml/scripts/run_forecast_ops_check.py` runs quality checks for 1D/1W/1M (ready for cron/CI wiring).

---

## 7) Frontend / Chart Integration

**Docs**
- Implementation roadmap: chart overlays

**Implemented**
- Web chart overlay:
  - `client-macos/SwiftBoltML/Resources/WebChart/chart.js`
    - forecast line + dots (point markers)
  - `client-macos/SwiftBoltML/Views/WebChartView.swift`
    - target line drawn from `synthesis_data.tp1`
- Native chart overlay:
  - `client-macos/SwiftBoltML/Views/AdvancedChartView.swift`

**Gaps / Next Step**
- **Implemented** TP2/TP3/SL overlays:
  - `backend/supabase/functions/chart-data-v2/index.ts` includes `targets`
  - `client-macos/SwiftBoltML/Views/WebChartView.swift` draws TP1/TP2/TP3/SL
  - `client-macos/SwiftBoltML/Models/ChartResponse.swift` parses `targets`

---

## 8) Validation & Walk‑Forward (Research Framework)

**Docs**
- Framework: walk‑forward validation + regime checks

**Current State**
- **Implemented** CLI walk‑forward runner:
  - `ml/scripts/run_walk_forward.py` (uses `WalkForwardBacktester` + BaselineForecaster)

---

## 9) Production API Skeleton (FastAPI)

**Docs**
- Implementation guide includes a full FastAPI skeleton

**Current State**
- API stack is Supabase Edge Functions, not FastAPI.
- If you want FastAPI, it should live in `ml/api/` or `backend/api/`.

---

## 10) Where to Read the Output (Targets)

**Primary target (TP1)**
- Stored in: `ml_forecasts.synthesis_data.tp1`
- Chart uses TP1 as main target

**Fallback (raw point target)**
- `ml_forecasts.points` → `type: "target"`

---

## 11) L1 15m + Forecasting Lab

**Master plan:** [FORECAST_PIPELINE_MASTER_PLAN.md](FORECAST_PIPELINE_MASTER_PLAN.md) — single entry point for the L1 15m pipeline, lab, canonical points schema, and eval/residuals.

The L1 15m pipeline and forecasting lab share the same **canonical ForecastPoint** shape (see [master_blueprint.md](master_blueprint.md) — Canonical Forecast Point Schema) so lab outputs can be written to `ml_forecasts_intraday.points` and served via GET /chart without reshaping.

| Area | Doc / concept | Code / storage |
|------|----------------|----------------|
| **Lab** | Experiments, cascade (15m→1h→4h_trading→1D), canonical points emission | `ml/forecasting_lab/` — [cascade_runner.py](../ml/forecasting_lab/runner/cascade_runner.py), [schema/points.py](../ml/forecasting_lab/schema/points.py) (`ohlc_steps_to_points`), `result["points"]`; forecast_eval + residual features in results JSON |
| **Production L1** | Predict 15m OHLC → recompute indicators → write points | `ml/src/unified_forecast_job.py` or new L1 job; indicator recompute (e.g. [technical_indicators_corrected.py](../ml/src/features/technical_indicators_corrected.py) or new indicator_recompute); `ml_forecasts_intraday.points` |
| **Schema** | Canonical ForecastPoint (ts, value, optional ohlc, indicators, etc.) | [master_blueprint.md](master_blueprint.md) — Canonical Forecast Point Schema; migration comment on `ml_forecasts_intraday.points` |

---

## Quick “What’s Done vs. Not Done”

**Done**
- Anchor Zones
- Multi‑layer S/R with weighted consolidation
- Direction‑based TP ladder
- Confluence/quality scoring
- 1D/1W/1M‑only focus

**Not Done (Optional Next)**
- TP2/TP3/SL overlays in UIxq
- Automated daily/weekly ops checks (cron)
- Walk‑forward validation pipeline
- Regime‑switching model selection gates

---

## Suggested Next Task (if you want me to proceed)

1) Add TP2/TP3/SL overlays and quality badge on chart
2) Add min‑confidence gating for forecast writes
3) Create a cron job for daily quality checks
