# Forecasting Processes

This document captures the end-to-end forecasting pipeline, components, scripts, visualizations, and Supabase persistence used in SwiftBolt ML.

## High-level flow
1. **Job ingestion**: Forecast jobs are queued in `forecast_jobs` (Supabase) and claimed via the `get_next_forecast_job` RPC.
2. **Worker**: `ml/src/forecast_job_worker.py` polls the queue and runs `forecast_job.py` per symbol.
3. **Forecast generation**: `forecast_job.py` pulls OHLCV from Supabase, engineers technical features, runs ML forecasters (ensemble or baseline), blends SuperTrend AI, and writes results back to Supabase.
4. **Storage**: Forecasts are persisted in `ml_forecasts`; SuperTrend signals are stored in `supertrend_signals`.
5. **Surfacing**: The Supabase Edge Function `backend/supabase/functions/chart/index.ts` fetches chart data + ML forecasts for clients. macOS UI renders charts and overlays indicators/forecast points.
6. **Monitoring**: `ml/src/monitoring/forecast_staleness.py` checks freshness of `ml_forecasts`.

## Data and features
- **Source data**: OHLCV from Supabase tables `symbols` and `ohlc_bars` fetched via `SupabaseDatabase.fetch_ohlc_bars()` (`ml/src/data/supabase_db.py` @32-85).
- **Feature engineering**: `add_technical_features` builds returns, MAs, MACD, RSI, Bollinger Bands, ATR, regime features, etc. (`ml/src/features/technical_indicators.py` @13-75). Enhanced paths add multi-timeframe + SuperTrend/momentum/volume/volatility features (`ml/src/models/enhanced_forecaster.py` @148-180, @200-248).
- **SuperTrend AI**: `src/strategies/supertrend_ai.py` (not detailed here) enriches forecasts with trend metadata and optional signal upserts.

## ML components
- **BaselineForecaster**: RandomForest classification for direction labels; generates forecast points for visualization (`ml/src/models/baseline_forecaster.py`).
- **GradientBoostingForecaster**: XGBoost multiclass model used inside the ensemble (`ml/src/models/gradient_boosting_forecaster.py`).
- **EnsembleForecaster**: Blends RF (baseline) + GB predictions with weighted probabilities (`ml/src/models/ensemble_forecaster.py`).
- **EnhancedForecaster**: Full indicator suite, optional LightGBM + multi-timeframe features, SuperTrend integration, and multi-indicator signals (`ml/src/models/enhanced_forecaster.py`).
- **ForecastExplainer**: Human-readable explanations of predictions (feature contributions, signal breakdown, risk) (`ml/src/models/forecast_explainer.py`).

## Batch job scripts
- **Forecast generation**: `ml/src/forecast_job.py`
  - Fetches OHLCV, adds technical features, optionally runs SuperTrend AI, then trains and predicts per horizon using ensemble (RF + GB) or baseline fallback.
  - Persists forecasts via `SupabaseDatabase.upsert_forecast` and optionally SuperTrend signals.
- **Worker / queue consumer**: `ml/src/forecast_job_worker.py`
  - Polls `get_next_forecast_job` RPC, runs `forecast_job.py --symbol <ticker>` as a subprocess, marks completion via `complete_forecast_job` RPC or failure via `fail_forecast_job`.
  - Supports `--watch` to continuously process with a poll interval.
- **Monitoring**: `ml/src/monitoring/forecast_staleness.py`
  - Checks most recent `ml_forecasts.created_at` and flags stale/critical states; optional check of `options_ranks`.

## Supabase persistence & RPC
- **Tables**
  - `ml_forecasts` (`backend/supabase/migrations/003_ml_forecasts_table.sql`): `symbol_id`, `horizon`, `overall_label`, `confidence`, `points` (JSONB array of {ts, value, lower, upper}), `run_at`, `created_at`. Unique on `(symbol_id, horizon)`. `updated_at` later removed to fix trigger issues (`20251216044131_fix_ml_forecasts_trigger.sql`).
  - `supertrend_signals`: Upserted via `upsert_supertrend_signals` for generated SuperTrend entries (symbol, date, type, stops/targets, confidence).
  - `forecast_jobs`: Queue table consumed by worker (fields include `id`, `symbol`, `priority`, `status`, timestamps).
  - `ohlc_bars`, `symbols`: Source market data.
- **RPC / functions**
  - `get_next_forecast_job` (`20251217030200_fix_get_next_forecast_job.sql`): Locks highest-priority pending job and returns `(job_id, symbol)`.
  - `complete_forecast_job`, `fail_forecast_job`: Mark job status; invoked by worker.

## Database access layer
- `ml/src/data/supabase_db.py`
  - Initializes Supabase client from settings.
  - `fetch_ohlc_bars`: Reads OHLCV for a symbol/timeframe from `ohlc_bars`.
  - `get_symbol_id`: Resolves ticker to UUID from `symbols`.
  - `upsert_forecast`: Delete-then-insert into `ml_forecasts` (includes SuperTrend metadata if provided).
  - `upsert_supertrend_signals`: Upserts SuperTrend signals with `on_conflict` on `(symbol, signal_date, signal_type)`.

## Charting and visual surfacing
- **Edge Function**: `backend/supabase/functions/chart/index.ts`
  - GET `/chart?symbol={ticker}&timeframe={tf}`.
  - Loads symbol metadata, fetches `ml_forecasts` for horizons `["1D","1W"]`, returns `mlSummary` (overall label, confidence, per-horizon points) alongside OHLC bars (prefers DB cache up to 1000 bars).
  - Timeframe-aware cache TTL and last-trading-day freshness logic.
- **macOS client views**
  - `ChartViewModel` (`client-macos/SwiftBoltML/ViewModels/ChartViewModel.swift`): Fetches chart data, computes client-side indicators (SMA/EMA/RSI/MACD/Stoch/KDJ/ADX/SuperTrend/Bollinger/ATR) for overlays.
  - Views such as `PriceChartView`, `ChartView`, `AdvancedChartView`, and `ForecastExplainerView` render price + indicators; `ChartResponse` model includes optional `mlSummary` for overlaying forecast points/labels.

## Monitoring and freshness
- `check_forecast_staleness` (`ml/src/monitoring/forecast_staleness.py`): Flags stale/critical if latest `ml_forecasts.created_at` exceeds threshold (default 6h).
- CLI usage: `python -m src.monitoring.forecast_staleness --threshold <hours>` or `--all` to include `options_ranks`.

## How to run
- **One-off forecast for configured symbols**: `python ml/src/forecast_job.py`
- **Queue worker (single pass)**: `python ml/src/forecast_job_worker.py`
- **Queue worker (watch mode)**: `python ml/src/forecast_job_worker.py --watch --interval 10`
- **Staleness check**: `python ml/src/monitoring/forecast_staleness.py --threshold 6` (or `--all`)

## Outputs and visualization
- **Stored forecasts**: Each horizon produces directional label, confidence, and projected points suitable for plotting.
- **Client overlay**: Edge Function provides `mlSummary`; macOS client can overlay forecast bands/points with indicators.
- **SuperTrend signals**: Persisted separately for signal history and analysis.
