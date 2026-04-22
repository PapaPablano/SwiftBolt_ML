# Data Freshness Architecture

How OHLCV data and ML forecasts flow from providers to clients.

## Ingestion Paths

### m1 + m15 Bars (Real-Time via pg_cron)
- **Mechanism:** `pg_cron` triggers `ingest-live` Edge Function every 1 minute during market hours (Mon-Fri 13:00-20:59 UTC)
- **Source:** Alpaca API
- **Pass 1 (m1):** Last 5-minute window of 1-minute bars → `ohlc_bars_v2` with `data_status: 'live'`
- **Pass 2 (m15):** Last 20-minute window of 15-minute bars → `ohlc_bars_v2` with `data_status: 'live'`
- **Pass 3 (Kalman):** Adjusts cached intraday forecast target prices based on price movement (see Forecast Pipeline below)
- **Max staleness:** ~2 minutes (1-minute cron + processing)
- **Symbol universe:** Watchlist-driven via `watchlist_items` table

### m15/h1/d1 Bars (Backup via GitHub Actions)
- **Mechanism:** `schedule-intraday-ingestion.yml` runs Python scripts every 5 minutes during market hours
- **Source:** Alpaca API via Python ML pipeline
- **Note:** GitHub Actions cron is **unreliable** for sub-10-minute intervals on low-activity repos. pg_cron is the primary path; GH Actions is a backup.

### Daily/Weekly Bars (End-of-Day)
- **Mechanism:** Same GitHub Actions workflow, after-hours runs
- **Destination:** `ohlc_bars_v2` with `data_status: 'verified'` after market close

## Forecast Pipeline

### Training (Weekly)
- **Mechanism:** `schedule-intraday-forecast.yml` runs Monday 4 AM UTC (or on-demand via `workflow_dispatch`)
- **Models:** LSTM + ARIMA-GARCH ensemble (2-model production)
- **Output:** Forecast points persisted to `ml_forecasts` / `ml_forecasts_intraday`
- **Symbol universe:** Watchlist-driven via `resolve_symbol_list()` in `ml/src/scripts/universe_utils.py`

### Live Adjustment (Every Minute)
- **Mechanism:** Third pass in `ingest-live` Edge Function (pg_cron)
- **Method:** Kalman filter adjustment with gain=0.15
- **Horizons:** 15m, 1h, 4h (short-term only; daily+ horizons update only on training)
- **Formula:** `adjusted_target = target_price + 0.15 * (actual_close - forecast_base_price)`
- **Effect:** Forecasts stay fresh between weekly training runs

### Evaluation (Daily)
- **Mechanism:** `ml/src/evaluation_job_daily.py` (scheduled or manual)
- **Output:** Walk-forward accuracy metrics, signal quality scores
- **Signal quality:** 0-100 score (50% accuracy + 30% confidence tightness + 20% regime alignment) written to `ml_forecasts.signal_quality`

## Staleness Detection (Chart Endpoint)

The `chart` Edge Function computes staleness for every response:

1. Finds the most recent actual bar's timestamp (`lastActualBarTs`)
2. Computes age: `ageMinutes = (now - lastActualBarTs) / 60_000`
3. Looks up the SLA from `FRESHNESS_SLA_MINUTES`
4. Sets `isStale = ageMinutes > slaMinutes`

### SLA Thresholds

| Timeframe | SLA (minutes) | Rationale |
|-----------|--------------|-----------|
| m15 | 15 | 3x the pg_cron interval (conservative) |
| m30 | 60 | 1 hour tolerance |
| h1 | 120 | 2 hours |
| h4 | 480 | 8 hours |
| d1 | 1440 | 24 hours |
| w1 | 10080 | 1 week |

### Data Status Values

| Value | Meaning |
|-------|---------|
| `fresh` | Data within SLA |
| `stale` | Data beyond SLA, backfill triggered |
| `no_data` | Zero bars exist for this symbol/timeframe |
| `updating` | Active backfill in progress |

## Chart Response Fields

### Freshness Object
| Field | Type | Description |
|-------|------|-------------|
| `ageMinutes` | number/null | Minutes since most recent bar |
| `slaMinutes` | number | SLA threshold for this timeframe |
| `isWithinSla` | boolean | `ageMinutes <= slaMinutes` |
| `lastUpdated` | string/null | ISO 8601 timestamp of most recent bar |
| `isStale` | boolean | `ageMinutes > slaMinutes` |
| `ageSeconds` | number/null | Seconds since most recent bar |
| `slaSeconds` | number | SLA threshold in seconds |

### Signal Quality (per forecast horizon in mlSummary)
| Field | Type | Description |
|-------|------|-------------|
| `signalQuality` | number/null | 0-100 composite score |
| `calibrationLabel` | string/null | "well-calibrated" / "moderate" / "uncalibrated" |
| `accuracyPct` | number/null | Walk-forward accuracy percentage |

## Infrastructure

### pg_cron Jobs (Reliable Path)
| Job | Schedule | Target |
|-----|----------|--------|
| `ingest-live` | `* 13-20 * * 1-5` | m1 + m15 bars + Kalman adjustment |
| `intraday-live-refresh` | `*/15 13-20 * * 1-5` | Additional intraday refresh |
| `backfill-worker` | `* * * * *` | Process backfill queue |

### GitHub Actions (Backup/Training)
| Workflow | Schedule | Purpose |
|----------|----------|---------|
| `schedule-intraday-ingestion` | `*/5 market hours` | Backup m15/h1 ingestion |
| `schedule-intraday-forecast` | `Weekly Mon 4AM UTC` | Full ensemble training |
| `schedule-ml-orchestration` | `Daily 4AM UTC` | Daily forecasting + evaluation |

### Key Diagnostic Queries

Check if pg_cron jobs are actually succeeding at the Edge Function level (not just the HTTP call level):
```sql
-- pg_cron "succeeded" only means net.http_post returned — check actual HTTP status in Edge Function logs
SELECT j.jobname, jrd.status, jrd.start_time
FROM cron.job_run_details jrd
JOIN cron.job j ON j.jobid = jrd.jobid
WHERE jrd.start_time > now() - interval '5 minutes'
ORDER BY jrd.start_time DESC;
```

Check vault secret alignment:
```sql
SELECT name FROM vault.decrypted_secrets ORDER BY name;
-- Cross-reference with: SELECT jobname, command FROM cron.job WHERE command LIKE '%vault%';
```
