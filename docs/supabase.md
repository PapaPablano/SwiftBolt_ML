# Supabase Schema — Reference & Data Flow

This document describes the SwiftBolt ML Supabase schema: table purposes, relationships, and how data flows through the system. The schema is for context only; table order and constraints in raw DDL may not be valid for direct execution.

---

## Table of Contents

1. [Overview & Core Entity](#1-overview--core-entity)
2. [Backfill & Data Ingestion](#2-backfill--data-ingestion)
3. [OHLC & Price Data](#3-ohlc--price-data)
4. [Jobs & Orchestration](#4-jobs--orchestration)
5. [Features & ML Pipeline](#5-features--ml-pipeline)
6. [Forecasts (Daily & Intraday)](#6-forecasts-daily--intraday)
7. [ML Quality & Calibration](#7-ml-quality--calibration)
8. [Indicators & Support/Resistance](#8-indicators--supportresistance)
9. [Options](#9-options)
10. [GA / Backtest](#10-ga--backtest)
11. [Corporate, News, Sentiment](#11-corporate-news-sentiment)
12. [User, Watchlist, Alerts](#12-user-watchlist-alerts)
13. [Validation & Ranking](#13-validation--ranking)
14. [Entity Relationship Summary](#14-entity-relationship-summary)

---

## 1. Overview & Core Entity

### Central entity: `symbols`

Almost all market and ML data is keyed by **symbol**. `symbols` is the single source of truth for tickers and asset metadata.

| Column         | Type   | Notes                                      |
|----------------|--------|--------------------------------------------|
| id             | uuid   | PK, default `gen_random_uuid()`            |
| ticker         | text   | UNIQUE (e.g. AAPL, SPY)                    |
| asset_type     | enum   | USER-DEFINED                               |
| description    | text   | Optional                                   |
| primary_source | enum   | Default `finnhub` (data_provider)           |
| name           | varchar| Optional display name                      |
| is_active      | boolean| Default true                               |
| created_at, updated_at | timestamptz |                        |

**Flow:** Symbols are created first. Backfill jobs, bars, forecasts, options, indicators, and most other tables reference `symbols.id` via `symbol_id` (or `underlying_symbol_id` where applicable).

---

### Supporting reference tables

- **market_calendar** — Trading calendar: `date` (PK), `is_open`, `session_open`/`session_close`, `market_open`/`market_close`. Used to know when markets are open for scheduling and validation.
- **project_members** — Links `auth.users(id)` to `project_id`; used for project-scoped access.

---

## 2. Backfill & Data Ingestion

Purpose: Fill historical and intraday OHLC data in chunks, track progress, and record which datasets exist.

### Flow (high level)

```
backfill_config (key/value)
       ↓
backfill_jobs (one per symbol/timeframe range)
       ↓
backfill_chunks (per-day or per-slice units)
       ↓
Writes → ohlc_bars_v2 / intraday_bars / bar_datasets
       ↓
coverage_status, provider_checkpoints (per symbol/timeframe)
```

### Tables

| Table                  | Purpose |
|------------------------|--------|
| **backfill_config**    | Key-value config for backfill (e.g. batch size, limits). PK: `key`. |
| **backfill_jobs**      | One job per symbol + timeframe + time range. Tracks `status`, `progress`, `from_ts`/`to_ts`. FK: `symbol_id` → symbols. |
| **backfill_chunks**    | Sub-units of a job (e.g. per day). `job_id` → backfill_jobs, `symbol_id` → symbols. Tracks `status`, `try_count`, `last_error`. |
| **ingestion_runs**     | Top-level run record: `provider`, `started_at`/`finished_at`, `status`, optional `git_sha`/`notes`. Referenced by bar_datasets. |
| **bar_datasets**       | Describes a coherent bar set: symbol, timeframe, provider, `start_ts`/`end_ts`/`as_of_ts`, `bar_count`, `checksum`, `status` (live/verified/frozen). FK: symbol_id, ingestion_run_id. |
| **coverage_status**    | Per (symbol, timeframe): `from_ts`/`to_ts`, `last_success_at`, `last_rows_written`, `last_provider`. PK: (symbol, timeframe). |
| **provider_checkpoints** | Per (provider, symbol, timeframe): `last_ts`, `bars_written`. Used to resume fetches. |
| **provider_migration_audit** | Log of migrations from one provider to another (symbol/timeframe, bar counts, date range). |
| **symbol_backfill_queue** | Queue of symbols to backfill: `symbol_id`, `ticker`, `status`, `timeframes` (array), `bars_inserted`, timestamps. |
| **intraday_backfill_status** | Per symbol: `last_backfill_at`, `backfill_days`, `bar_count`, `status`, `error_message`. PK: symbol_id. |

---

## 3. OHLC & Price Data

Purpose: Store bar and quote data used for charts, features, and ML.

### Flow

```
External APIs (e.g. Alpaca)
       ↓
job_runs / backfill_chunks
       ↓
ohlc_bars_v2 (main bar store)  OR  intraday_bars (1m/5m/15m)
       ↓
Optional: corporate_actions → ohlc_bars_v2.adjusted_for
quotes (latest NBBO / last for each symbol)
```

### Tables

| Table                 | Purpose |
|-----------------------|--------|
| **ohlc_bars**         | Legacy bar store: symbol_id, timeframe (enum), ts, OHLCV, provider. |
| **ohlc_bars_v2**      | Main bar table: symbol_id, timeframe, ts (with range CHECK), OHLCV, provider, `is_intraday`/`is_forecast`, `data_status`, `confidence_score`, bands, `adjusted_for` → corporate_actions. |
| **ohlc_bars_h4_alpaca** | Alpaca 4h bars: symbol_id, ts (no tz), OHLCV, provider. |
| **intraday_bars**     | 1m/5m/15m bars: symbol_id, timeframe (1m/5m/15m), ts, OHLCV, vwap, trade_count. |
| **quotes**            | One row per symbol: symbol_id (PK), ts, last, bid, ask, day_high/day_low, prev_close, updated_at. |
| **corporate_actions** | Splits, dividends, etc.: symbol_id/symbol, action_type (stock_split, reverse_split, dividend, merger, spin_off), ex_date, record_date, payment_date, old_rate/new_rate, ratio, cash_amount, bars_adjusted, adjusted_at, metadata. Used by ohlc_bars_v2 for adjustment lineage. |

---

## 4. Jobs & Orchestration

Purpose: Define and run scheduled and ad-hoc work (fetch, forecast, etc.) and track health.

### Flow

```
job_definitions (what to run: symbol/timeframe, window_days, priority)
       ↓
job_queue (pending work items) or job_runs (execution log)
       ↓
data_jobs / forecast_jobs (domain-specific job tables)
       ↓
orchestrator_heartbeat (health), rate_buckets (provider rate limits)
```

### Tables

| Table                   | Purpose |
|-------------------------|--------|
| **job_definitions**     | Defines recurring jobs: job_type (fetch_intraday, fetch_historical, run_forecast), symbol/timeframe, window_days, priority, enabled. Optional symbol_id, symbols_array, batch_number/total_batches, batch_version. |
| **job_queue**          | Generic queue: job_type, symbol, status (pending/processing/completed/failed), priority, payload (jsonb), attempts/max_attempts, error_message, timestamps. FK: symbol_id. |
| **job_runs**            | Execution log for job_def: job_def_id, symbol, timeframe, job_type, slice_from/slice_to, status (queued/running/success/failed/cancelled), progress_percent, rows_written, provider, attempt, error_*, triggered_by, expected_cost/actual_cost. |
| **data_jobs**           | Data-specific jobs: job_type, symbol_id, ticker, status (pending/running/completed/failed), started_at/completed_at, error_message, metadata. |
| **forecast_jobs**       | Forecast-specific: symbol, status, priority, retry_count/max_retries, error_message, timestamps. FK: symbol_id. |
| **orchestrator_heartbeat** | Per name: last_seen, status (healthy/warning/error), message, updated_at. PK: name. |
| **rate_buckets**        | Per provider: capacity, refill_per_min, tokens, updated_at. PK: provider. |

---

## 5. Features & ML Pipeline

Purpose: Build feature sets from bar datasets and run forecast/training pipelines.

### Flow

```
bar_datasets
       ↓
feature_sets (definition_version, status: building/ready/failed, feature_keys)
       ↓
feature_rows (ts, OHLCV, features jsonb)
       ↓
forecast_runs (model_key, model_version, horizon, status)
       ↓
forecast_points (ts, yhat, lower, upper, confidence, kind: point/path)
training_runs (lookback_days, n_*_samples, ensemble_validation_accuracy, weights, models_artifact_path)
```

### Tables

| Table                | Purpose |
|----------------------|--------|
| **feature_sets**     | One per dataset + definition: dataset_id → bar_datasets, definition_version, status (building/ready/failed), feature_keys (array). |
| **feature_rows**     | One row per (feature_set_id, ts): open/high/low/close/volume, features (jsonb). FK: feature_set_id → feature_sets. |
| **forecast_runs**    | One run per dataset (and optional feature_set): dataset_id, feature_set_id, model_key, model_version, horizon, status (running/success/failed), metrics (jsonb), finished_at. |
| **forecast_points**  | Time series output of a run: forecast_run_id, ts, yhat, lower/upper, confidence, kind (point/path). |

**Training:**

| Table             | Purpose |
|-------------------|--------|
| **training_runs** | Per symbol/timeframe/run_date: lookback_days, n_training_samples, n_validation_samples, ensemble_validation_accuracy, model_performances (jsonb), weights (jsonb), models_artifact_path. FK: symbol_id. |

**Validation (ensemble):**

| Table                        | Purpose |
|-----------------------------|--------|
| **ensemble_validation_metrics** | Per symbol/horizon/validation_date/window: train/val/test RMSE, divergence, is_overfitting, model_count, models_used, sample counts, directional_accuracy, MAE, hyperparameters, etc. symbol_id stored as text. |

---

## 6. Forecasts (Daily & Intraday)

Purpose: Store ML forecast outputs (daily and intraday), evaluations, and monitoring.

### Flow (daily)

```
ml_forecasts (per symbol/horizon/timeframe: overall_label, confidence, points, supertrend_*, sr_levels, model_agreement, ensemble_type, model_type, etc.)
       ↓
forecast_evaluations (after realization: realized_price, realized_return, direction_correct, price_error, rf/gb predictions, model_agreement)
ml_forecast_changes (audit log: field_name, old_value, new_value, change_reason)
forecast_monitoring_alerts (alerts by symbol/horizon, severity, details)
```

### Flow (intraday)

```
ml_forecasts_intraday (overall_label, confidence, target_price, supertrend/ensemble components, expires_at)
       ↓
ml_forecast_paths_intraday (steps, interval_sec, points jsonb, expires_at)
ml_forecast_evaluations_intraday (realized_*, direction_correct, option_b_* outcome fields)
```

### Tables (daily)

| Table                      | Purpose |
|----------------------------|--------|
| **ml_forecasts**           | Main daily forecast: symbol_id, horizon (1D/5D/10D/20D), timeframe, overall_label (enum), confidence, run_at, points (jsonb). SuperTrend: supertrend_factor, supertrend_performance, supertrend_signal, trend_label, trend_confidence, stop_level, target_price. S/R: sr_levels, sr_density, support/resistance hold probabilities and strength scores. Ensemble: ensemble_type, n_models, model_predictions/model_confidences, ensemble_method/ensemble_weights, confidence_source. Quality: quality_score, quality_issues, backtest_metrics. Optional: synthesis_data, forecast_return/volatility, ci_lower/ci_upper, is_base_horizon, is_consensus, handoff_confidence, consensus_weight, adaptive_supertrend_*. model_type: xgboost, tabpfn, transformer, baseline, arima, prophet, ensemble, binary. |
| **forecast_evaluations**   | After outcome: forecast_id → ml_forecasts, symbol, horizon, predicted_* vs realized_*, direction_correct, price_error(_pct), rf_prediction/gb_prediction, rf_correct/gb_correct, model_agreement, synth_* components, rf_weight/gb_weight. |
| **ml_forecast_changes**    | Audit: forecast_id, field_name, old_value/new_value (jsonb), change_reason, changed_at. |
| **forecast_validation_metrics** | Per symbol/horizon/scope: lookback_days, quality_grade, metrics (jsonb), computed_at. |
| **forecast_monitoring_alerts** | symbol_id, horizon, alert_type, severity, details (jsonb). |

### Tables (intraday)

| Table                             | Purpose |
|-----------------------------------|--------|
| **ml_forecasts_intraday**         | Short-horizon: symbol_id, symbol, horizon, timeframe, overall_label, confidence, target_price, current_price, supertrend_component, sr_component, ensemble_component, layers_agreeing, expires_at, points, evaluated_at, forecast_return. |
| **ml_forecast_paths_intraday**    | Path forecast: symbol_id, symbol, timeframe, horizon, steps, interval_sec, overall_label, confidence, model_type, points (jsonb), created_at, expires_at. |
| **ml_forecast_evaluations_intraday** | Evaluation: forecast_id → ml_forecasts_intraday, symbol_id, symbol, horizon, predicted_* vs realized_*, direction_correct, supertrend_direction_correct, sr_containment, ensemble_direction_correct, option_b_outcome (FULL_HIT/DIRECTIONAL_HIT/etc.), option_b_* metrics. |

**Other:**

| Table                | Purpose |
|----------------------|--------|
| **live_predictions**| symbol_id, timeframe (enum), signal (enum), accuracy_score, metadata, prediction_time. |

---

## 7. ML Quality & Calibration

| Table                     | Purpose |
|---------------------------|--------|
| **ml_confidence_calibration** | Per horizon: bucket_low/bucket_high, predicted_confidence, actual_accuracy, adjustment_factor, n_samples, is_calibrated. |
| **ml_data_quality_log**   | Per symbol/check_date: issues (jsonb), rows_flagged, rows_removed, quality_score. FK: symbol_id. |
| **model_performance_history** | Per evaluation_date/horizon: total_forecasts, correct_forecasts, accuracy, rf/gb/ensemble accuracy, weights, recommended weights, avg/max price error pct, bullish/bearish/neutral accuracy. |
| **model_weights**         | Global per horizon: horizon (UNIQUE), rf_weight, gb_weight, last_updated, update_reason, rf_accuracy_30d, gb_accuracy_30d. |
| **symbol_model_weights**  | Per symbol/horizon: rf_weight, gb_weight, synth_weights (jsonb), diagnostics (jsonb), calibration_source, intraday_sample_count, intraday_accuracy. |
| **model_validation_stats**| symbol_id, validation_type (enum), accuracy (0–1), sample_size, window_start/end, metrics (jsonb). |
| **ml_model_versions**     | symbol_id, model_type, horizon, version_hash, parameters, training_stats, performance_metrics. |

---

## 8. Indicators & Support/Resistance

Purpose: Cached technical indicators and S/R levels for charts and signals.

### Flow

```
ohlc_bars_v2 / intraday_bars
       ↓
indicator_values (RSI, MACD, ADX, ATR, BB, SuperTrend, support/resistance distances, stoch, Williams %R, CCI, MFI, OBV, supertrend_* metrics)
sr_levels (pivot, fib, nearest_support/resistance, zigzag_swings, kmeans_centers, polynomial S/R, strength scores)
sr_level_history (level_type, level_price, level_source, strength_score, touch_count, is_broken)
       ↓
supertrend_signals (BUY/SELL, entry_price, stop_level, target_price, confidence, outcome, exit_*, pnl_*)
technical_indicators_cache (cache_key PK, symbol, timeframe, data jsonb)
```

### Tables

| Table                        | Purpose |
|-----------------------------|--------|
| **indicator_values**        | Per symbol/timeframe/ts: OHLCV, rsi, macd/macd_signal/macd_hist, adx, atr_14, bb_upper/bb_lower, supertrend_*, nearest_support/resistance, support/resistance_distance_pct, plus rsi_14, stoch_k/d, williams_r, cci, mfi, obv, supertrend_performance_index, supertrend_signal_strength, signal_confidence, supertrend_*_norm, perf_ama, supertrend_metrics, supertrend_confidence, supertrend_trend_duration. Timeframes: m1–w1, M. |
| **sr_levels**               | Per symbol/timeframe/computed_date: current_price, pivot_pp/r1–r3/s1–s3, fib_* levels, nearest_support/resistance, support/resistance_distance_pct, zigzag_swings, kmeans_centers, all_supports/all_resistances, lookback_bars, support/resistance strength and hold probabilities, polynomial_support/resistance, slopes. |
| **sr_level_history**        | History of S/R levels: symbol_id, level_type, level_price, level_source, strength_score, first_detected_at, last_touched_at, touch_count, is_broken, broken_at. |
| **supertrend_signals**      | Signals: symbol, signal_date, signal_type (BUY/SELL), entry_price, stop_level, target_price, confidence (0–10), atr_at_signal, factor_used, performance_index, risk/reward amounts, outcome (WIN/LOSS/OPEN), exit_price/exit_date, pnl_percent/pnl_amount. FK: symbol_id. |
| **technical_indicators_cache** | Cache: cache_key (PK), symbol, timeframe, data (jsonb), cached_at. |

---

## 9. Options

Purpose: Chain snapshots, ranks, strategies (multi-leg), legs, journal, alerts, and backfill/scrape jobs.

### Flow

```
symbols (underlying)
       ↓
options_chain_snapshots / options_snapshots / options_price_history (chain data)
options_ranks (ML and heuristic scores for contracts)
iv_history (ATM IV, skew, etc. per symbol/date)
       ↓
options_strategies (user_id, strategy_type, underlying_symbol_id, status, premium, risk/reward, forecast_id, greeks)
       ↓
options_legs (strike, expiry, entry_*, current_*, greeks, is_closed, assignment/exercise)
options_leg_entries (leg_id, entry_price, contracts, entry_timestamp)
       ↓
multi_leg_journal (strategy_id, action, actor_*, leg_id, changes, notes)
options_multi_leg_alerts (strategy_id, leg_id, alert_type, severity, title, reason, suggested_action, acknowledged/resolved)
options_strategy_metrics (strategy_id, recorded_at, underlying_price, total_value, delta/gamma/theta/vega snapshots, alert counts)
```

### Tables (chain & IV)

| Table                      | Purpose |
|----------------------------|--------|
| **options_chain_snapshots** | Per underlying/expiry/strike/side: bid, ask, mark, last_price, volume, open_interest, IV, delta, gamma, theta, vega, rho, snapshot_date, fetched_at, ml_score. |
| **options_snapshots**      | Similar: underlying_symbol_id, contract_symbol, option_type (call/put), strike, expiration, bid/ask/last, underlying_price, volume, OI, greeks, iv, snapshot_time. |
| **options_price_history**  | Historical option prices and greeks; contract_symbol, expiry, strike, side, iv_curve_ok, iv_data_quality_score. |
| **iv_history**             | Per symbol/ts (date): atm_iv, iv_min/max/median, put_iv_atm/call_iv_atm, iv_skew, vwiv. |
| **options_ranks**          | Ranking run: underlying_symbol_id, expiry, strike, side, ml_score, greeks, volume, OI, run_at, plus momentum/value/greeks/composite scores, signals (e.g. signal_discount, signal_runner), liquidity_confidence, ranking_mode, entry_rank/exit_rank, catalyst_score, iv_percentile, etc. |

### Tables (strategies & legs)

| Table                       | Purpose |
|-----------------------------|--------|
| **options_strategies**      | user_id, name, strategy_type (enum), underlying_symbol_id, underlying_ticker, opened_at/closed_at, status (enum), total_debit/credit, net_premium, num_contracts, max_risk/reward, breakeven_points, profit_zones, current_value, total_pl/realized_pl, forecast_id → ml_forecasts, forecast_alignment/confidence, combined greeks, min/max_dte, tags, notes, last_alert_at, version. |
| **options_legs**            | strategy_id, leg_number, leg_role, position_type, option_type, strike, expiry, dte_at_entry/current_dte, entry_* / current_* (price, value, greeks), unrealized_pl, is_closed, exit_*, realized_pl, assignment/exercise fields, is_itm, is_breaching_strike, is_near_expiration, notes. |
| **options_leg_entries**     | leg_id, entry_price, contracts, entry_timestamp, notes. |
| **options_strategy_templates** | name (UNIQUE), strategy_type, leg_config (jsonb), typical_max_risk/reward, cost_pct, description, best_for, market_condition, is_system_template, is_public. |
| **options_strategy_metrics**| strategy_id, recorded_at (date + timestamp), underlying_price, total_value, total_pl, delta/gamma/theta/vega snapshots, min_dte, alert_count, critical_alert_count. |
| **multi_leg_journal**       | strategy_id → options_strategies, action (enum), actor_user_id, actor_service, leg_id → options_legs, changes (jsonb), notes. |
| **options_multi_leg_alerts**| strategy_id, leg_id, alert_type, severity (enum), title, reason, details, suggested_action, acknowledged_at, resolved_at, resolution_action, action_required. |
| **options_underlying_history** | underlying_symbol_id, timeframe, ts, OHLCV, ret_7d, vol_7d, drawdown_7d, gap_count, source_provider. |

### Tables (jobs)

| Table                   | Purpose |
|-------------------------|--------|
| **options_backfill_jobs** | symbol_id, ticker, status (pending/processing/completed/failed), error_message, timestamps. |
| **options_scrape_jobs**   | symbol, status, options_count, error_message, timestamps. FK: symbol_id. |

---

## 10. GA / Backtest

Purpose: Genetic-algorithm optimization runs and their backtest trades.

### Flow

```
ga_optimization_runs (symbol, generations, population_size, training_days, best_* metrics, top_strategies jsonb, status)
       ↓
ga_strategy_params (symbol, genes jsonb, fitness jsonb, is_active, training_*, validation_win_rate/profit_factor)
ga_backtest_trades (run_id, strategy_rank, symbol, contract_symbol, entry/exit dates and prices, greeks at entry, pnl_pct, duration_minutes, exit_reason, entry_signal)
```

| Table                  | Purpose |
|------------------------|--------|
| **ga_optimization_runs** | id, symbol, started_at/completed_at, generations, population_size, training_days, best_fitness_score, best_win_rate, best_profit_factor, best_sharpe, top_strategies (jsonb), status, error_message. FK: symbol_id. |
| **ga_strategy_params** | symbol, genes (jsonb), fitness (jsonb), is_active, training_days/samples, validation_win_rate/profit_factor, generations_run, population_size. FK: symbol_id. |
| **ga_backtest_trades**  | run_id → ga_optimization_runs, strategy_rank, symbol, contract_symbol, entry/exit dates and prices, delta/gamma/vega/theta at entry, pnl_pct, duration_minutes, exit_reason, entry_signal. |

---

## 11. Corporate, News, Sentiment

| Table               | Purpose |
|---------------------|--------|
| **corporate_actions** | See §3; links to ohlc_bars_v2.adjusted_for. |
| **news_items**       | symbol_id, title, source, url, summary, published_at, fetched_at, sentiment_score. |
| **sentiment_scores** | symbol_id, as_of_date, sentiment_score. |

---

## 12. User, Watchlist, Alerts

### Flow

```
auth.users (Supabase Auth)
       ↓
watchlists (user_id, name)
       ↓
watchlist_items (watchlist_id, symbol_id)
user_alert_preferences (user_id UNIQUE, toggles and thresholds for expiration, strike, assignment, profit target, stop loss, forecast, theta, gamma, vega, max_alerts_per_hour, etc.)
scanner_alerts (symbol_id, user_id, condition_label, severity, dismissed, condition_type, details, is_read, expires_at)
```

| Table                     | Purpose |
|---------------------------|--------|
| **watchlists**            | user_id, name. PK: id. |
| **watchlist_items**       | watchlist_id, symbol_id. PK: (watchlist_id, symbol_id). |
| **user_alert_preferences**| One row per user_id: enable_* flags (expiration, strike, assignment, profit target, stop loss, forecast, theta, gamma, vega), thresholds (e.g. expiration_alert_dte, strike_breach_threshold, profit_target_pct, stop_loss_pct, min_forecast_confidence, min_daily_theta, gamma_alert_threshold), max_alerts_per_hour, alert_batch_window_minutes. |
| **scanner_alerts**        | symbol_id, user_id (optional), triggered_at, condition_label, severity, dismissed, condition_type, details (jsonb), is_read, expires_at. |

---

## 13. Validation & Ranking

Purpose: Store validation outcomes and ranking job/evaluation metadata.

### Flow

```
validation_results (symbol, direction, unified_confidence, backtesting/walkforward/live scores, drift_*, consensus_direction, recommendation, retraining_trigger)
validation_audits (symbol_id, user_id, confidence_score, weights_config, client_state, logged_at)
ranking_jobs (symbol, status, requested_by, priority)
       ↓
ranking_evaluations (symbol_id, is_healthy, n_days/n_contracts, mean_ic, stability, hit_rate, leakage_suspected, calibration_*, trend/vol regime, n_alerts, horizon, ranking_mode)
```

| Table                  | Purpose |
|------------------------|--------|
| **validation_results** | symbol_id, symbol, direction (BULLISH/BEARISH/NEUTRAL), unified_confidence, backtesting_score, walkforward_score, live_score, drift_detected, drift_magnitude, drift_severity, drift_explanation, timeframe_conflict, consensus_direction, conflict_explanation, recommendation, retraining_trigger, retraining_reason. |
| **validation_audits**  | symbol_id, user_id, confidence_score (0–1), weights_config, client_state (jsonb), logged_at. |
| **ranking_jobs**       | symbol, status (enum job_status), started_at/completed_at, error_message, retry_count, max_retries, requested_by, priority. FK: symbol_id. |
| **ranking_evaluations**| symbol_id, evaluated_at, is_healthy, n_days, n_contracts, mean_ic, std_ic, min/max_ic, ic_trend, stability, hit_rate, hit_rate_ci_*, leakage_suspected, leakage_score, permuted_ic_mean, calibration_error, calibration_is_monotonic, trend_regime, vol_regime, regime_adx/atr_pct, n_alerts, alert_types, has_critical_alert, horizon, ranking_mode. |

---

## 14. Entity Relationship Summary

### Symbols as hub

- **symbol_id** (or underlying_symbol_id) is used by: backfill_jobs, backfill_chunks, bar_datasets, coverage_status, data_jobs, forecast_jobs, forecast_evaluations, forecast_monitoring_alerts, ga_*, indicator_values, intraday_bars, intraday_backfill_status, iv_history, job_queue, ml_forecasts, ml_forecasts_intraday, ml_forecast_paths_intraday, ml_* logs/weights/validation, news_items, ohlc_bars*, options_*, provider_checkpoints, quotes, ranking_*, scanner_alerts, sentiment_scores, sr_levels, sr_level_history, supertrend_signals, symbol_backfill_queue, symbol_model_weights, training_runs, validation_audits, validation_results, watchlist_items (via symbol_id).

### Key foreign keys

| Child table / column   | References        |
|------------------------|-------------------|
| backfill_chunks.job_id | backfill_jobs(id) |
| backfill_*.symbol_id    | symbols(id)       |
| bar_datasets.symbol_id, ingestion_run_id | symbols(id), ingestion_runs(id) |
| feature_sets.dataset_id | bar_datasets(dataset_id) |
| feature_rows.feature_set_id | feature_sets(feature_set_id) |
| forecast_runs.dataset_id, feature_set_id | bar_datasets(dataset_id), feature_sets(feature_set_id) |
| forecast_points.forecast_run_id | forecast_runs(forecast_run_id) |
| forecast_evaluations.forecast_id | ml_forecasts(id) |
| ml_forecast_evaluations_intraday.forecast_id | ml_forecasts_intraday(id) |
| ohlc_bars_v2.adjusted_for | corporate_actions(id) |
| options_strategies.forecast_id | ml_forecasts(id) |
| options_legs.strategy_id | options_strategies(id) |
| multi_leg_journal.strategy_id, leg_id | options_strategies(id), options_legs(id) |
| ga_backtest_trades.run_id | ga_optimization_runs(id) |
| job_runs.job_def_id | job_definitions(id) |
| watchlist_items.watchlist_id, symbol_id | watchlists(id), symbols(id) |
| project_members.user_id | auth.users(id) |

### Data flow (end-to-end)

1. **Ingestion:** job_definitions / backfill_jobs → backfill_chunks / job_runs → ohlc_bars_v2, intraday_bars, bar_datasets → coverage_status, provider_checkpoints.
2. **Features:** bar_datasets → feature_sets → feature_rows.
3. **Forecasting:** feature_sets / bar_datasets → forecast_runs → forecast_points; and separately ml_forecasts (daily), ml_forecasts_intraday + ml_forecast_paths_intraday (intraday).
4. **Evaluation:** ml_forecasts → forecast_evaluations; ml_forecasts_intraday → ml_forecast_evaluations_intraday.
5. **Options:** symbols → options_chain_snapshots / options_ranks / iv_history → options_strategies → options_legs → options_leg_entries, multi_leg_journal, options_multi_leg_alerts.
6. **Indicators & S/R:** symbol + timeframe → indicator_values, sr_levels, sr_level_history, supertrend_signals, technical_indicators_cache.

This file is the single reference for the Supabase schema and its flows; for executable migrations, use the project’s migration files under `supabase/migrations/`.
