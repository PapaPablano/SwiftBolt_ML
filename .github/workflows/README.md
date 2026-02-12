# GitHub Actions Workflows

This document describes the consolidated GitHub Actions workflow architecture for SwiftBolt ML.

## Architecture Overview

```
Daily Data Refresh (data ingestion only)
Intraday Ingestion (data ingestion only)

ML Orchestration (schedule/manual)
Intraday Forecast (schedule/manual)
```

## Primary Workflows

### 1. Daily Data Refresh (`daily-data-refresh.yml`)

**The canonical workflow for all OHLC data ingestion.**

| Property | Value |
|----------|-------|
| Schedule | `0 6 * * *` (6:00 AM UTC daily) |
| Trigger | `schedule` + `workflow_dispatch` |

#### Inputs

| Input | Description | Default |
|-------|-------------|---------|
| `full_backfill` | Run complete backfill with gap detection | `false` |
| `symbol` | Single symbol to process | All watchlist |
| `timeframe` | Single timeframe to process | All (m15, h1, h4, d1, w1) |

#### Usage

```bash
# Incremental refresh (default)
gh workflow run daily-data-refresh.yml

# Full backfill for specific symbol
gh workflow run daily-data-refresh.yml -f full_backfill=true -f symbol=AAPL

# Single timeframe refresh
gh workflow run daily-data-refresh.yml -f timeframe=d1
```

---

### 2. Intraday Ingestion (`intraday-ingestion.yml`)

**Fetches fresh intraday OHLC data during market hours. Runs before forecast so data is fresh.**

| Property | Value |
|----------|-------|
| Schedule | `*/15 13-22 * * 1-5` (UTC): every 15 min at :00, :15, :30, :45 |
| UTC window | 13:00–22:59 UTC ≈ 8:00–17:59 ET |
| Concurrency | `intraday-ingestion-*`; forecast runs at :05,:20,:35,:50 to avoid overlap |

#### Inputs

| Input | Description | Default |
|-------|-------------|---------|
| `symbols` | Comma-separated symbols | All watchlist |
| `timeframes` | Comma-separated timeframes | `m15,h1` |
| `force_refresh` | Force refresh even if data exists | `false` |

---

### 3. Intraday Forecast (`intraday-forecast.yml`)

**Generates intraday forecasts on schedule or manual trigger. Writes to `ml_forecasts_intraday`.**

| Property | Value |
|----------|-------|
| Schedule | `5,20,35,50 13-22 * * 1-5` (UTC): 5 min after each quarter-hour, Mon–Fri |
| UTC window | 13:00–22:59 UTC ≈ 8:00–17:59 ET (market + extended) |
| Concurrency | `intraday-forecast-*`; does not overlap ingestion (ingestion at :00,:15,:30,:45) |
| CLI (from `ml/`) | `python -m src.intraday_forecast_job --horizon 15m` (or 1h, 4h, 8h, 1D / all) |
| Horizons | 15m (4-step = 1h ahead), 1h, 4h, 8h, 1D; manual can pass `--symbol SPY` for canary-only |

---

### 4. ML Orchestration (`ml-orchestration.yml`)

**Consolidated ML pipeline for nightly processing.**

| Property | Value |
|----------|-------|
| Schedule | `0 4 * * 1-5` (4:00 AM UTC weekdays) |
| Trigger | `schedule` + `workflow_dispatch` |

#### Jobs

| Job | Description |
|-----|-------------|
| `ml-forecast` | Ensemble predictions (RF + XGBoost) |
| `options-processing` | Options backfill and snapshots |
| `model-health` | Evaluation, drift detection, data quality |
| `smoke-tests` | Basic validation checks |

#### Inputs

| Input | Description | Default |
|-------|-------------|---------|
| `job_filter` | Specific job to run | All jobs |
| `symbol` | Single symbol to process | All watchlist |

---

## Supporting Workflows

### Deployment

| Workflow | Description |
|----------|-------------|
| `deploy-supabase.yml` | Deploy Edge Functions and migrations |
| `deploy-ml-dashboard.yml` | Deploy ML dashboard function |

### CI/Testing

| Workflow | Description |
|----------|-------------|
| `test-ml.yml` | ML tests and linting (push/PR trigger) |
| `api-contract-tests.yml` | API schema validation |
| `frontend-integration-checks.yml` | E2E integration checks |

### Queue Processing

| Workflow | Description |
|----------|-------------|
| `job-worker.yml` | Process pending forecast/ranking jobs |
| `orchestrator-cron.yml` | Supabase orchestrator (manual only) |

---

## Legacy Workflows (Archived)

Legacy workflows have been moved to `./legacy/` directory. See `legacy/README.md` for details.

**Consolidated Summary (22 → 8 workflows):**

| Archived From | Consolidated Into |
|---------------|-------------------|
| `backfill-*.yml`, `daily-historical-sync.yml` | `daily-data-refresh.yml` |
| `alpaca-intraday-*.yml`, `intraday-update*.yml` | `intraday-ingestion.yml` |
| `ml-forecast.yml`, `ml-evaluation.yml`, `*-monitoring.yml`, `options-nightly.yml` | `ml-orchestration.yml` |
| `job-worker.yml`, `orchestrator-*.yml`, `symbol-*.yml` | Various or deprecated |

---

## Required Secrets

Configure these in GitHub repository settings (Settings → Secrets and variables → Actions):

| Secret | Description |
|--------|-------------|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key |
| `SUPABASE_ANON_KEY` | Supabase anonymous key |
| `SUPABASE_ACCESS_TOKEN` | Supabase CLI access token |
| `SUPABASE_PROJECT_REF` | Supabase project reference |
| `DATABASE_URL` | Direct Postgres connection string |
| `ALPACA_API_KEY` | Alpaca API key |
| `ALPACA_API_SECRET` | Alpaca API secret |

---

## Composite Actions

### Setup ML Environment (`.github/actions/setup-ml-env`)

Shared setup for ML Python environment with caching.

```yaml
- name: Setup ML Environment
  uses: ./.github/actions/setup-ml-env
  with:
    supabase-url: ${{ secrets.SUPABASE_URL }}
    supabase-key: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
    database-url: ${{ secrets.DATABASE_URL }}
    alpaca-api-key: ${{ secrets.ALPACA_API_KEY }}
    alpaca-api-secret: ${{ secrets.ALPACA_API_SECRET }}
```

---

## Monitoring

### Supabase Tables Updated

| Table | Workflow |
|-------|----------|
| `ohlc_bars_v2` | Daily Data Refresh, Intraday Ingestion |
| `indicator_values` | Intraday Forecast |
| `ml_forecasts_intraday` | Intraday Forecast (15m/1h/4h/8h/1D points) |
| `ml_forecasts` | ML Orchestration |
| `forecast_evaluations` | ML Orchestration (model-health) |
| `model_weights` | ML Orchestration (model-health) |
| `options_chain_snapshots` | ML Orchestration (options-processing) |
| `options_ranks` | ML Orchestration (options-processing) |

### Data Flow

1. **Daily data**: `Daily Data Refresh` (ingestion only)
2. **Intraday data**: `Intraday Ingestion` (ingestion only)
3. **ML**: `ML Orchestration` + `Intraday Forecast` run on schedule/manual as separate pipelines

---

## Live market test (15m forecasts + hourly validation)

**Pre-open wiring check**

1. Run **Test Workflow Fixes** (`.github/workflows/test-workflow-fixes.yml`) with `test_type=integration` (or `all`) to confirm secrets, `setup-ml-env`, and DB connectivity.
2. Required secrets: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`, `ALPACA_API_KEY`, `ALPACA_API_SECRET`.

**Every 15 minutes (market hours)**

- **Intraday Ingestion** runs at :00, :15, :30, :45 UTC (13–22 UTC Mon–Fri).
- **Intraday Forecast** runs at :05, :20, :35, :50 UTC and calls (from `ml/`):
  - `python -m src.intraday_forecast_job --horizon 15m` (and 1h, 4h, 8h, 1D when horizon=all).
- 15m horizon uses 4-step multi-step (1 hour ahead) and writes to `ml_forecasts_intraday`. Manual run with a single symbol: `--symbol SPY`.

**Hourly validation (“is it updating?”)**

- **Hourly Canary (15m→1h)** (`.github/workflows/hourly-canary-15m.yml`):
  - **Predict** (scheduled at 14:35–19:35 UTC): runs intraday forecast for canaries (AAPL, MSFT, SPY) with `--horizon 15m`.
  - **Hourly summary** (scheduled at 15:40, 16:40, 17:40, 18:40, 19:40, 20:40 UTC): runs `hourly_canary_summary.py --forecast-source intraday` for the single :30 bar that just closed (09:30–14:30 CST). Confirms the latest `ml_forecasts_intraday` row (`created_at <= target`) vs realized closes; uploads artifact `hourly-canary-summary`.
  - **EOD summary** (scheduled at 21:10 UTC): same script with all targets `09:30,10:30,...,14:30` CST for the full day.
- Manual summary example (CST date, canaries):
  ```bash
  cd ml && python scripts/hourly_canary_summary.py \
    --symbols SPY,AAPL,MSFT --date-cst 2026-02-12 \
    --forecast-source intraday --out validation_results/hourly_canary_summary.csv
  ```
- The script reports whether it used `points_exact`, `points_nearest`, or `target_price` for a quick check that 15m points align with target timestamps.

---
## Troubleshooting

### Common Issues

**Workflow skipped (weekend/after-hours):**
- Intraday workflows only run during market hours
- Use `workflow_dispatch` for manual override

**Gap detection failures:**
- Run with `full_backfill=true` to repair data gaps
- Check Alpaca API rate limits

**ML Orchestration not triggering:**
- Verify the schedule is enabled in GitHub Actions
- Run manually via `workflow_dispatch`

### Logs and Artifacts

- Each workflow uploads validation reports as artifacts
- Check job summaries for detailed results
- Use `gh run view <run-id>` for CLI access
