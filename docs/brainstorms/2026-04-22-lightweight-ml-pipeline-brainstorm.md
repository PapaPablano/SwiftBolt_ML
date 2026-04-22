---
date: 2026-04-22
topic: lightweight-ml-pipeline
---

# Lightweight ML Pipeline — Hybrid Training + Real-Time Adjustment

## Problem Frame

The current ML forecast pipeline runs 5 models (LSTM, ARIMA-GARCH, XGBoost, TabPFN, ensemble) via GitHub Actions every 15 minutes for intraday and daily for daily horizons. This is slow (blocks GH Actions runners), expensive (compute + API costs), and complex to maintain. The intraday job is particularly wasteful — most of its compute produces nearly identical forecasts because market conditions don't change enough in 15-minute windows to justify a full model re-run.

## Requirements

**Training Pipeline (Reduced Frequency)**
- R1. Full ensemble training (LSTM + ARIMA-GARCH + active models) runs weekly or on-demand, not every 15 minutes
- R2. Training produces forecast points for all horizons (15m, 1h, 4h, 8h, 1D, 5D, 10D, 20D) and persists them to `ml_forecasts` / `ml_forecasts_intraday` tables
- R3. Training can be triggered manually via workflow_dispatch for immediate re-forecast after major market events

**Real-Time Forecast Adjustment (New)**
- R4. A lightweight adjustment layer updates cached forecast points as new price bars arrive, running inside `ingest-live` (pg_cron, every minute during market hours)
- R5. The adjustment uses Kalman filter or exponential smoothing to shift forecast target prices based on actual price movement since the forecast was generated
- R6. Adjusted forecasts are written back to the same tables the chart endpoint reads from, so clients see "live" updates without any new API
- R7. When the next full training run occurs, it replaces adjusted forecasts with fresh model predictions

**Cleanup**
- R8. Remove dead model code (Transformer, unused XGBoost paths) from the pipeline to reduce maintenance surface
- R9. Reduce GitHub Actions ML scheduled workflows from the current frequency to weekly training + daily evaluation only

## Success Criteria

- Full ensemble training runs once per week (or on-demand) and completes in under 30 minutes
- Intraday forecasts update every minute via the Kalman adjustment layer in `ingest-live`
- Forecast accuracy is maintained or improved (the adjustment layer corrects for price movement, reducing drift)
- GitHub Actions ML compute drops by 90%+ (from every-15-minute to weekly)
- The pipeline is simpler to reason about: "train weekly, adjust live, evaluate daily"

## Scope Boundaries

- **In scope:** Training frequency reduction, Kalman/EMA adjustment in ingest-live, dead model removal, GH Actions schedule simplification
- **Out of scope:** New model architectures, changing the chart endpoint response shape, adding new forecast horizons
- **Non-goal:** Real-time streaming to clients (the existing polling/freshness system is sufficient)

## Key Decisions

- **Hybrid over full rewrite:** Keep Python for training (proven, tested), add lightweight adjustment in the existing `ingest-live` Edge Function (already runs every minute, already has Alpaca price data).
- **Kalman filter for adjustment:** Already partially implemented in `intraday_forecast_job.py` (`kalman_weight` config). Move this logic to TypeScript in `ingest-live` for simpler execution.
- **Weekly training, not daily:** Market regime changes are slow enough that weekly retraining with daily evaluation catches degradation. On-demand retrain covers breaking events.

## Symbol Universe Decision

**Watchlist-driven (keep current pattern).** Symbols are sourced from `watchlist_items` table via `ml/src/scripts/universe_utils.py:resolve_symbol_list()`. Both training and live adjustment use the same universe. The `ingest-live` Edge Function already reads from `watchlist_items` for its symbol list — no change needed.

Resolution priority: `INPUT_SYMBOLS` env var → `watchlist_items` table → hardcoded fallback (`AAPL, MSFT, NVDA, TSLA, SPY, QQQ`).

## Dependencies / Assumptions

- `ingest-live` Edge Function (already running every minute via pg_cron) is the natural host for the adjustment layer
- The Kalman filter adjustment is simple enough to implement in TypeScript (no Python dependency needed for inference)
- `ml_forecasts` and `ml_forecasts_intraday` tables support UPSERT for the adjustment writes
- Symbol universe stays watchlist-driven — same source for training and live adjustment

## Outstanding Questions

### Deferred to Planning
- [Affects R4][Technical] How should the Kalman filter parameters (process noise, observation noise) be calibrated? Use defaults from the existing Python Kalman implementation or tune separately?
- [Affects R5][Technical] Should the adjustment apply to all horizons (15m through 20D) or only short-term (15m, 1h, 4h)?
- [Affects R9][Technical] Which GitHub Actions ML workflows can be removed vs. reduced in frequency? The `schedule-ml-orchestration.yml` (daily) and `schedule-intraday-forecast.yml` (every 15min) are the main targets.
- [Affects R8][Needs research] Which model code paths are truly dead vs. dormant-but-planned? Verify before removing.

## Next Steps

-> `/ce:plan` for structured implementation planning
