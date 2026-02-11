# Intraday Writer + Chart Endpoints — Deploy and Monitor

**Scope:** Production L1 writer (canonical points), GET /chart, GET /chart-data-v2, canary monitoring, and release validation.

---

## 1. Deploy together (same release window)

- **Avoid a transient mismatch** where storage becomes canonical but one endpoint still assumes a minimal point shape (or vice versa). Deploy the **writer** and **both Edge endpoints** (/chart and /chart-data-v2) in the **same release window**.
- **Rollback hygiene:** If you roll back, roll back writer and endpoints together so contract and storage stay aligned.

---

## 2. Roundtrip test as deploy gate

- **Release validation:** Run the integration test `ml/tests/test_chart_roundtrip_intraday.py` against **staging** (or prod) as part of release validation. It inserts a canonical diagnostic row, calls `/chart` and `/chart-data-v2`, asserts:
  - **chart:** `ts` remains ISO string; extended keys (ohlc, indicators) preserved.
  - **chart-data-v2:** `ts` is integer (unix seconds); extended keys preserved; `4h_trading` → `h4`.
  Then it deletes the row. Run with `SUPABASE_URL` and key set for the target env (e.g. staging):
  ```bash
  cd ml && pytest tests/test_chart_roundtrip_intraday.py -v
  ```
- **Human-friendly checklist:** Keep the standalone gate script `ml/scripts/run_verification_gate_known_row.py` for manual runs: `--insert --call` does insert → call both endpoints → cleanup in one command. It warns about using service role keys for inserts under RLS.

---

## 3. Insert / cleanup and RLS (keep during rollout)

- **Insert (gate script):** Use `SUPABASE_SERVICE_ROLE_KEY` only in CI/admin contexts. Anon-key inserts should fail under RLS in prod so prod doesn’t accumulate test rows.
- **Cleanup:** Keep **diagnostic row cleanup** enabled during rollout. The gate script deletes the inserted row after `--call` (or when `--cleanup` is passed). That way you can safely re-run the gate multiple times without polluting `ml_forecasts_intraday`.

---

## 4. Canary monitoring (6PM CST)

Add checks for **canary symbols** (e.g. AAPL, MSFT, SPY) at 6PM CST:

| Check | Description | Alert if |
|-------|-------------|----------|
| **Latest intraday forecast age** | Max age of most recent `ml_forecasts_intraday` row per symbol | Age > threshold (e.g. 2h for 15m horizon) |
| **Points length** | `points` array length for latest forecast | Empty or missing `points` |
| **Canonical keys** | Presence of `timeframe` and `step` on points | Any point missing `timeframe` or `step` |
| **Divergence** | Realized bars vs forecast bands | Divergence > 15% (per your monitoring conventions) |

Implement via existing monitoring (e.g. `ml/src/monitoring/`, cron, or Supabase Edge scheduled function). Alert when any canary fails a check.

---

## 5. Residual feedback loop (where residuals live + read path)

- **Evaluator dual-write (required so loop doesn’t go dark):** In **`ml/src/evaluation_job_intraday.py`**, `save_evaluation()` writes to **forecast_evaluations** (calibration/analytics) and then calls **`db.save_intraday_evaluation(...)`** to write the same row into **ml_forecast_evaluations_intraday**. So `get_recent_intraday_residuals()` hits the ML table first; fallback to forecast_evaluations only if the ML table is empty.
- **Where residuals live:** Intraday evaluations are written to **ml_forecast_evaluations_intraday** (and forecast_evaluations). The evaluator dual-writes so that `get_recent_intraday_residuals()` sees rows.
- **Read path:** `db.get_recent_intraday_residuals(symbol_id, horizon, limit=20)` in `supabase_db.py` queries `ml_forecast_evaluations_intraday` by symbol_id and horizon, ordered by `evaluated_at` desc. Returns `price_error`, `price_error_pct`, `direction_correct`, `evaluated_at`.
- **Wired into inference:** The intraday job calls `get_recent_intraday_residuals()` before `synthesizer.generate_forecast(...)` and passes `recent_residuals=recent_residuals`. The synthesizer dampens confidence using mean absolute `price_error_pct` when residuals are non-empty (first iteration; no retrain).
- **Optional next:** Expand evaluation beyond `target_price`: also evaluate `points[].value` (and band hit-rate using `lower`/`upper`) so residuals correspond to the stored path, not just the scalar target. That would require step-level or path-level eval rows (e.g. a dedicated intraday eval table with step_index) if you want per-step residuals later.

---

## 6. Option B wiring (confirm before deploy)

Verify these call sites are present in the branch you deploy:

- **Indicator attach:** `ml/src/intraday_forecast_job.py` — after `build_intraday_path_points(...)`, call `attach_indicators_to_forecast_points(path_df, path_points)` before `canonicalize_intraday_points(path_points, tf)` and DB write.
- **Recent residuals:** `ml/src/intraday_forecast_job.py` — before `synthesizer.generate_forecast(...)`, call `recent_residuals = db.get_recent_intraday_residuals(symbol_id, horizon, limit=20)` and pass `recent_residuals=recent_residuals` into `generate_forecast`.
- **Residual damping:** `ml/src/forecast_synthesizer.py` — `_generate_base_forecast(..., recent_residuals=...)` dampens confidence using mean absolute `price_error_pct` when `recent_residuals` is non-empty.
- **DB helper:** `ml/src/data/supabase_db.py` — `get_recent_intraday_residuals(symbol_id, horizon, limit=20)`.

---

## 7. Related docs

- [INTRADAY_POINTS_STORAGE_CONTRACT.md](INTRADAY_POINTS_STORAGE_CONTRACT.md) — step semantics, `ts` format.
- [FORECAST_PIPELINE_MASTER_PLAN.md](FORECAST_PIPELINE_MASTER_PLAN.md) — L1 pipeline and chart contract.
- Verification gate: `ml/scripts/run_verification_gate_known_row.py`.
