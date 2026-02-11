# Forecasting Architecture: SwiftUI → Supabase → Python ML

**Single source of truth for MVP build order, API contracts, and job structure.**

---

## Clarifying Answers (Before Finalizing)

### 1) What are you forecasting?

| Target | Scope | Notes |
|--------|-------|-------|
| **Full price path** | Primary | Multi-step forecast: array of `{ ts, value, lower?, upper? }` per horizon. `value` = predicted close. |
| **Overall label** | Per horizon | `bullish` / `neutral` / `bearish` from ensemble consensus. |
| **Confidence** | Per horizon | 0–1 score; used for UI badge and gating. |
| **Direction label** | Optional | Binary up/down from `ml_binary_forecasts` (experimental). |
| **Volatility** | Later | Not in MVP; `forecast_volatility` exists in `training_stats` for future use. |

**In short:** Next close (and sequence of closes) + directional label + confidence. Not raw returns or volatility in MVP.

---

### 2) What horizons matter, and do you need confidence bands?

| Horizon | Timeframe | Use Case | Confidence Bands |
|---------|-----------|----------|------------------|
| **15m** | m15 | L1 gate, intraday scalping | ✅ `lower`/`upper` in points |
| **1h** | h1 | Intraday swing | ✅ |
| **4h** | h4 | Regime/TabPFN (experimental) | ✅ |
| **1D** | d1 | Primary daily chart | ✅ |
| **1W** | w1 | Swing / weekly | ✅ (via d1 aggregation) |

**MVP priorities:** 15m, 1h, 1D. 4h/8h/1W are secondary. Confidence bands: yes — `ForecastPoint` has `lower`/`upper`; SwiftUI renders as shaded band.

---

### 3) Data sources and MVP scope?

| Source | Role | MVP |
|--------|------|-----|
| **Alpaca** | Primary OHLC, corporate actions, market calendar | ✅ |
| **Finnhub** | News, supplemental quotes | ✅ |
| **Polygon (Massive)** | Supplemental historical, options | Optional fallback |
| **Tradier** | Options chains, expiries | ✅ (options ranker) |

**MVP scope:** US stocks only. Client talks only to Edge Functions; keys stay server-side.

---

## Minimal Postgres Schema (MVP)

Tables needed for OHLC caching + multi-horizon forecasts + canary metrics:

```
symbols              (id, ticker, asset_type, primary_source, status?, ...)
ohlc_bars_v2         (symbol_id, timeframe, ts, open, high, low, close, volume, provider, is_forecast)
                     UNIQUE(symbol_id, timeframe, ts, provider, is_forecast)
ml_forecasts         (symbol_id, timeframe, horizon, points JSONB, overall_label, confidence, run_at, model_type)
ml_forecasts_intraday(symbol_id, timeframe, horizon, points JSONB, run_at, ...)
quotes               (symbol_id, ts, last, bid, ask, ...) — optional for MVP
ensemble_validation_metrics  (symbol, horizon, validation_date, val_rmse, test_rmse, divergence, is_overfitting)
```

**Optional `forecast_metrics` (canary + rollback):**

```sql
CREATE TABLE IF NOT EXISTS public.forecast_metrics (
  id BIGSERIAL PRIMARY KEY,
  symbol TEXT NOT NULL,
  horizon TEXT NOT NULL,
  predicted_at TIMESTAMPTZ NOT NULL,
  realized_at TIMESTAMPTZ,
  predicted_value DECIMAL(12,4),
  realized_value DECIMAL(12,4),
  error_pct DECIMAL(8,4),  -- |realized - predicted| / predicted
  is_canary BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_forecast_metrics_canary ON forecast_metrics(is_canary, predicted_at) WHERE is_canary;
```

---

## GET /chart JSON Contract (Exact)

**Endpoint:** `GET /chart?symbol=AAPL&timeframe=d1&start=&end=`  
**or** `GET /chart-data-v2?symbol=AAPL&timeframe=d1&days=60&includeForecast=true`

### Response (chart-data-v2 — canonical for layered rendering)

```json
{
  "symbol": "AAPL",
  "symbol_id": "uuid",
  "timeframe": "d1",
  "layers": {
    "historical": { "count": 2000, "provider": "alpaca", "data": [...], "oldestBar": "...", "newestBar": "..." },
    "intraday": { "count": 26, "provider": "alpaca", "data": [...], "oldestBar": "...", "newestBar": "..." },
    "forecast": { "count": 10, "provider": "ml", "data": [...], "oldestBar": "...", "newestBar": "..." }
  },
  "metadata": { "total_bars": 2036, "start_date": "...", "end_date": "..." },
  "mlSummary": {
    "overallLabel": "bullish",
    "confidence": 0.72,
    "horizons": [
      {
        "horizon": "1D",
        "points": [
          { "ts": 1707264000, "value": 187.52, "lower": 185.1, "upper": 190.0 }
        ],
        "targets": { "tp1": 188.5, "tp2": 189.2, "stopLoss": 186.0 }
      }
    ]
  }
}
```

### ForecastPoint (SwiftUI contract)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ts` | int \| string | ✅ | Unix seconds or ISO8601 |
| `value` | number | ✅ | Predicted close |
| `lower` | number | No | Band lower (default = value) |
| `upper` | number | No | Band upper (default = value) |

SwiftUI `ForecastPoint` already supports `ts` as Int or ISO8601 string; `lower`/`upper` default to `value` if missing.

---

## Scheduled Jobs (Ingest vs Train vs Infer)

| Job | Trigger | Purpose | Writes To |
|-----|---------|---------|-----------|
| **Intraday ingestion** | Cron `*/15 13-22 * * 1-5` (UTC) | Fetch m15/h1 from Alpaca, upsert `ohlc_bars_v2` | `ohlc_bars_v2` |
| **Run backfill worker** | Cron or queue | Process `backfill_chunks` for gaps | `ohlc_bars_v2` |
| **Intraday inference** | Cron `5,20,35,50 13-22 * * 1-5` | Fast inference 15m/1h; no retrain | `ml_forecasts_intraday`, `ohlc_bars_v2` (forecast rows) |
| **Daily inference** | Cron `0 4 * * 1-5` (post-close) | Full daily forecasts 1D/5D/10D/20D | `ml_forecasts` |
| **Retrain** | Weekly or on drift | Walk-forward validation, weight calibration | Model artifacts, `ensemble_validation_metrics` |
| **Canary** | Daily 6PM CST | AAPL/MSFT/SPY predicted vs realized | `forecast_metrics` |

**Design rules:**
- Inference is fast (read cached bars, predict, write).
- Retraining is controlled (weekly or explicit trigger).
- Rollback: switch `model_type` or feature version via env; canary flags bad runs.

---

## Edge Function Patterns

- **Auth:** Validate JWT; reject unauthenticated for paid endpoints.
- **Rate limiting:** Use Supabase docs pattern (atomic counter / token bucket) at function entry.
- **Cache-first:** Read from Postgres; refresh only if `last_bar_ts` is stale or missing.

---

## Walk-Forward Validation (XGBoost / Time Series)

- Use time-aware splits: train on past, validate on holdout, test on future.
- Store per-window metrics in `ensemble_validation_metrics`.
- Never use random k-fold for time series.

---

## Scaffolding Checklist (No Big Refactors)

### Must
- [x] MVP schema exists (`ohlc_bars_v2`, `ml_forecasts`, `ml_forecasts_intraday`, `symbols`)
- [x] `GET /chart` and `GET /chart-data-v2` Edge Functions return bars + forecast overlay
- [x] Scheduled ingestion: `intraday-ingestion.yml` (m15/h1)
- [x] Scheduled inference: `intraday-forecast.yml` (15m/1h), `ml-orchestration.yml` (daily)

### Should
- [ ] `forecast_metrics` table for canary
- [ ] Walk-forward evaluation module (exists in `ml/src/evaluation/walk_forward.py`)
- [ ] Canary runner for AAPL/MSFT/SPY at 6PM CST (script exists: `generate_canary_metrics.py`)

### Nice
- [ ] `model_registry` table (version, created_at, is_active)
- [ ] Feature-set versioning column in forecasts
- [ ] Simple rollback switch (env `ACTIVE_MODEL_VERSION`)

---

## Canary Schedule (6PM CST)

Add to `.github/workflows/` or Supabase cron:

```yaml
# canary-daily.yml
on:
  schedule:
    - cron: "0 0 * * 1-5"  # Midnight UTC ≈ 6PM CST (winter); 7PM CDT (summer)
```

Script: `ml/scripts/generate_canary_metrics.py` — compare predicted vs realized for AAPL, MSFT, SPY. Store in `forecast_metrics` with `is_canary=true`. Flag when `error_pct > 0.15`.

---

## Model Registry / Rollback (Nice-to-Have)

```sql
-- model_registry: versioning + active switch
CREATE TABLE IF NOT EXISTS public.model_registry (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  version TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  is_active BOOLEAN DEFAULT FALSE,
  metadata JSONB
);
-- Only one row should have is_active=true per model_type
```

Env: `ACTIVE_MODEL_VERSION=v1.2` — inference jobs read this and write `model_type` accordingly.

---

## File Reference

| Purpose | Path |
|---------|------|
| Chart Edge Function | `supabase/functions/chart/index.ts` |
| Chart Data V2 | `supabase/functions/chart-data-v2/index.ts` |
| Intraday ingestion | `.github/workflows/intraday-ingestion.yml` |
| Intraday forecast | `.github/workflows/intraday-forecast.yml` |
| Daily ML | `.github/workflows/ml-orchestration.yml` |
| Unified forecast job | `ml/src/unified_forecast_job.py` |
| Intraday forecast job | `ml/src/intraday_forecast_job.py` |
| Canary script | `ml/scripts/generate_canary_metrics.py` |
| Swift chart models | `client-macos/SwiftBoltML/Models/ChartResponse.swift`, `ChartDataV2Response.swift` |
