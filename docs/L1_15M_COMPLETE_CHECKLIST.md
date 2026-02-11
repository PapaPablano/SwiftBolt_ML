# L1 15m — Complete Checklist

**Scope:** Residual loop, “what gets evaluated,” point shape, and ensemble (XGBoost/RF/GB) wiring into inference and stored `ml_forecasts_intraday` row.

---

## 1. Residual read helper (done)

- **Implementation:** `db.get_recent_intraday_residuals(symbol_id, horizon, limit=20)` in **`ml/src/data/supabase_db.py`**.
- **Source:** Reads from **ml_forecast_evaluations_intraday** first; if empty, **fallback** to **forecast_evaluations** (with `evaluation_date` → `evaluated_at` mapping) so the loop works whether the evaluator writes to one or both tables.
- **Returns:** Last-K rows with `price_error`, `price_error_pct`, `direction_correct`, `evaluated_at` (ordered by time desc).

---

## 2. Residual loop wired into inference (done)

- **15m job:** In **`ml/src/intraday_forecast_job.py`**, before `synthesizer.generate_forecast(...)`:
  - `recent_residuals = db.get_recent_intraday_residuals(symbol_id, horizon, limit=20)`
  - `synthesizer.generate_forecast(..., recent_residuals=recent_residuals)`
- **Synthesizer:** In **`ml/src/forecast_synthesizer.py`**, `_generate_base_forecast(..., recent_residuals=...)` **dampens confidence** using mean absolute `price_error_pct`: `confidence *= max(0.7, 1.0 - min(0.3, mean_abs_pct))`. No retrain; deterministic adjustment.

---

## 3. What gets evaluated (current vs optional)

- **Current:** Evaluator scores **target_price** vs the next realized close; writes `price_error`, `price_error_pct`, `direction_correct` to forecast_evaluations and (via dual-write) to ml_forecast_evaluations_intraday.
- **Optional (for path-aligned residuals):** Also evaluate **points[].value** (and optionally band hit-rate using **lower**/ **upper**) so residuals correspond to the stored path, not just the scalar target. That would imply step-level or path-level eval rows (e.g. dedicated intraday eval table with `step_index`) if you want per-step residuals later.

---

## 4. Point shape (aligned)

- **Intraday contract:** **value** / **lower** / **upper** plus optional **nested** **ohlc** and **indicators** (and **timeframe**, **step**). **Not** top-level open/high/low/close. See [INTRADAY_POINTS_STORAGE_CONTRACT.md](INTRADAY_POINTS_STORAGE_CONTRACT.md).

---

## 5. Ensemble (XGBoost / production) wiring into L1 inference

- **Where it’s called:** **`ml/src/intraday_forecast_job.py`** (config-driven):
  - **Advanced (4h/8h/1D):** `ensemble = get_production_ensemble(horizon=..., symbol_id=...)` → `ensemble.train(features_df, labels_series, ohlc_df=...)` → `ensemble_pred = ensemble.predict(features_df.tail(1), ohlc_df=df.tail(1))`.
  - **Basic (15m/1h):** `EnsembleForecaster(horizon="1D", symbol_id=...)` → `train(X, y)` → `ensemble_pred = forecaster.predict(last_features)`.
- **What gets passed to the synthesizer:** `synthesizer.generate_forecast(..., ensemble_result=ensemble_pred, recent_residuals=recent_residuals)`. The **ensemble_result** dict has at least `label`, `confidence`, `agreement` (and optionally `n_models`).
- **How the synthesizer uses it:** In **`ml/src/forecast_synthesizer.py`**, **`_generate_base_forecast`** reads `ml_label = ensemble_result.get("label")`, `ml_confidence = ensemble_result.get("confidence")`, `ml_agreement = ensemble_result.get("agreement")`, maps label to `ml_bias`, and uses them in direction and **confidence** calculation. The result includes **ml_component** (and other components).
- **What gets persisted in ml_forecasts_intraday:** The job passes **ensemble_label** = `ensemble_pred.get("label", "neutral")` and **ensemble_component** = `synth_result.ml_component` (and supertrend/sr components) into **`db.insert_intraday_forecast(...)`** (insert-only; no upsert). So the ensemble’s **label** and its **contribution to the synthesized forecast** are both stored.

**Exact insertion point for XGBoost (or any new model):** If XGBoost is intended to be part of L1, it should be invoked inside **`get_production_ensemble(...)`** (or the basic **EnsembleForecaster**) so that **predict()** returns a dict with **label** and **confidence** (and optionally **agreement**). That output is already passed as **ensemble_result** into **generate_forecast**; no change to the points schema. To add a dedicated “XGBoost probability” field (e.g. P(bullish)) you could:
- Extend **ensemble_result** with e.g. **prob_bullish** and have the synthesizer use it to set **ensemble_component** or **adjusted_confidence**, and/or
- Persist it in the row (e.g. add a column or a **components** blob) if you want it stored for analytics.

---

## 6. Idempotent upsert (optional)

- **Insert-only (default):** `db.insert_intraday_forecast(...)` — no on_conflict; duplicates only if same `created_at` (e.g. same microsecond).
- **Idempotent path:** `db.upsert_intraday_forecast_idempotent(..., created_at_iso=..., ...)` — conflict target `(symbol_id, horizon, created_at)`; replace-on-conflict for `points`, `synthesis_data`, `confidence`, etc. Caller must pass deterministic `created_at_iso` for cron retries to hit the same row.

---

## 7. Dashboard query (xgb_prob / xgb_weight in synthesis_data)

`xgb_prob` and `xgb_weight` (when XGB blend runs) are stored in `synthesis_data->ensemble_result`. Example SQL to retrieve recent intraday forecasts with XGB explainability:

```sql
SELECT id, symbol, horizon, created_at,
       synthesis_data->'ensemble_result'->>'xgb_prob' AS xgb_prob,
       synthesis_data->'ensemble_result'->'weights'->>'xgb' AS xgb_weight,
       overall_label, confidence
FROM ml_forecasts_intraday
WHERE synthesis_data IS NOT NULL
  AND synthesis_data->'ensemble_result' ? 'xgb_prob'
ORDER BY created_at DESC
LIMIT 50;
```

---

## 8. Related docs

- [INTRADAY_POINTS_STORAGE_CONTRACT.md](INTRADAY_POINTS_STORAGE_CONTRACT.md) — step semantics, point shape, ts.
- [INTRADAY_DEPLOY_AND_MONITOR.md](INTRADAY_DEPLOY_AND_MONITOR.md) — deploy, residual loop, Option B wiring, evaluator dual-write.
- [FORECAST_PIPELINE_MASTER_PLAN.md](FORECAST_PIPELINE_MASTER_PLAN.md) — L1 pipeline and chart contract.
