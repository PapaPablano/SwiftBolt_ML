# Feature Mapping: Calculation → Storage → Usage

Generated: 2026-01-26

This doc maps ML feature calculations to their storage locations and where they are used in the pipeline.

---

## 1) Primary Tables

### OHLC Source (ground truth)
- Table: `public.ohlc_bars_v2`
- Fields (core): `ts, open, high, low, close, volume, timeframe, provider, is_forecast`
- Rule: ML feature generation uses **only** `is_forecast = false` bars.

### Feature Cache (computed indicators)
- Table: `public.indicator_values`
- Primary key: `(symbol_id, timeframe, ts)`
- Columns used by ML (current):
  - Momentum/trend: `rsi_14, macd, macd_signal, macd_hist, adx, williams_r, cci`
  - Volatility: `atr_14, bb_upper, bb_lower`
  - Trend: `supertrend_value, supertrend_trend, supertrend_factor`
  - SuperTrend AI: `supertrend_performance_index, supertrend_signal_strength, signal_confidence, supertrend_confidence_norm, supertrend_distance_norm, perf_ama`
  - Volume/flow: `mfi, obv`
  - Stochastic: `stoch_k, stoch_d`
  - OHLC copy: `open, high, low, close, volume`

---

## 2) Calculation Sources (Code)

All calculations are applied in `ml/src/features/technical_indicators.py` via:
- `add_technical_features(df)`
  - Delegates to `ml/src/features/technical_indicators_corrected.py` for core indicators.

Key code locations:
- `ml/src/features/technical_indicators.py`
- `ml/src/features/technical_indicators_corrected.py`
- `ml/src/features/feature_cache.py`
- `ml/src/data/supabase_db.py` (upsert + fetch)

---

## 3) Feature-by-Feature Mapping

### RSI (14)
- **Calculated in:** `TechnicalIndicatorsCorrect.calculate_rsi`
- **Stored as:** `indicator_values.rsi_14`
- **Used by:** ML features in `add_technical_features`, forecasting models, ranking
- **Note:** legacy column `rsi` is not populated.

### MACD
- **Calculated in:** `TechnicalIndicatorsCorrect.calculate_macd`
- **Stored as:** `indicator_values.macd, macd_signal, macd_hist`
- **Used by:** ML models and ranking

### ATR (14)
- **Calculated in:** `TechnicalIndicatorsCorrect.calculate_atr`
- **Stored as:** `indicator_values.atr_14`
- **Used by:** volatility, SuperTrend, and features

### Bollinger Bands
- **Calculated in:** `TechnicalIndicatorsCorrect.calculate_bollinger_bands`
- **Stored as:** `indicator_values.bb_upper, bb_lower`
- **Used by:** volatility regime + features

### ADX (14)
- **Calculated in:** `TechnicalIndicatorsCorrect.calculate_adx_correct`
- **Stored as:** `indicator_values.adx`
- **Used by:** trend strength in ML

### KDJ / Stochastic
- **Calculated in:** `TechnicalIndicatorsCorrect.calculate_kdj_correct`
- **Stored as:**
  - `indicator_values.stoch_k, stoch_d`
  - `kdj_k, kdj_d, kdj_j` are produced internally but not persisted

### SuperTrend
- **Calculated in:** `TechnicalIndicatorsCorrect.calculate_supertrend`
- **Parameters:** ATR period=7, multiplier=2.0
- **Stored as:**
  - `indicator_values.supertrend_value` (active band / stop level)
  - `indicator_values.supertrend_trend` (1 bullish, 0 bearish)
  - `indicator_values.supertrend_factor` (ATR multiplier / adaptive factor)
- **Used by:** ML forecasting, trend confirmation, optional signal layers

### SuperTrend AI (enhanced)
- **Calculated in:** `SuperTrendAI.calculate` (called from `add_technical_features`)
- **Stored as:**\n  `supertrend_performance_index, supertrend_signal_strength, signal_confidence,\n  supertrend_confidence_norm, supertrend_distance_norm, perf_ama`
- **Used by:** ML feature cache + ensemble weighting

### MFI
- **Calculated in:** `TechnicalIndicatorsCorrect.calculate_mfi`
- **Stored as:** `indicator_values.mfi`

### OBV
- **Calculated in:** `TechnicalIndicatorsCorrect.calculate_obv`
- **Stored as:** `indicator_values.obv`

### Williams %R
- **Calculated in:** `TechnicalIndicatorsCorrect.calculate_williams_r`
- **Stored as:** `indicator_values.williams_r`

### CCI
- **Calculated in:** `TechnicalIndicatorsCorrect.calculate_cci`
- **Stored as:** `indicator_values.cci`

---

## 4) Where Features Are Stored

Features are stored in `public.indicator_values` via:
- `ml/src/features/feature_cache.py`
  - Calls `db.upsert_indicator_values(symbol_id, timeframe, features)`
- `ml/src/data/supabase_db.py::upsert_indicator_values`

Intraday snapshots also write into `indicator_values`:
- `ml/src/intraday_forecast_job.py`
  - Writes latest ~20 bars per run for intraday timeframes

---

## 5) Where Features Are Used

### ML forecast pipelines
- `ml/src/unified_forecast_job.py`
  - Uses `fetch_or_build_features` (from cache or rebuild)
  - Feature cache hits use `indicator_values` if fresh

### Feature caching logic
- `ml/src/features/feature_cache.py`
  - Priority: Redis cache → `indicator_values` → recompute from OHLC
  - Freshness window: approx 30 minutes

### Models / ranking
- `ml/src/models/enhanced_forecaster.py`
- `ml/src/models/enhanced_options_ranker.py`
- `ml/src/strategies/multi_indicator_signals.py`

### API surface (not ML training, but uses the same stored features)
- `backend/supabase/functions/chart/index.ts`
- `backend/supabase/functions/chart-read/index.ts`
- `backend/supabase/functions/chart-data-v2/index.ts`

---

## 6) Data Flow Summary

1. **OHLC ingestion** → `ohlc_bars_v2` (non-forecast only)
2. **Feature generation** → `add_technical_features` over OHLC
3. **Cache write** → `indicator_values`
4. **ML usage** → `fetch_or_build_features` (cache or rebuild)

---

## 7) Operational Notes

- `indicator_values` can be overwritten by intraday snapshot runs.
- If a column is missing in the snapshot payload, it can become NULL for latest bars.
- Use backfill/recompute to restore missing feature columns.

---

## 8) Quick Verification Queries

Use these to verify ML-relevant features are populated:

```sql
-- Latest indicator rows for AAPL (D1)
SELECT ts, rsi_14, macd, macd_signal, macd_hist, adx, atr_14,
       bb_upper, bb_lower, supertrend_value, supertrend_trend,
       mfi, stoch_k, stoch_d, williams_r, cci, obv
FROM indicator_values
WHERE symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
  AND timeframe = 'd1'
ORDER BY ts DESC
LIMIT 5;
```

---

## 9) Known Gaps / TODOs

- `rsi` (legacy column) is not populated; use `rsi_14`.
- SuperTrend AI columns require the 2026-01-26 migration to exist in the DB.
