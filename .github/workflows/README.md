# GitHub Actions Workflows

This document describes the consolidated GitHub Actions workflow architecture for SwiftBolt ML.

## Architecture Overview

```
Daily Data Refresh ──▶ ML Orchestration
        │                    │
        │                    ├── ML Forecast
        │                    ├── Options Processing
        │                    ├── Model Health
        │                    └── Smoke Tests
        │
Intraday Ingestion ──▶ Intraday Forecast
```

## Primary Workflows

### 1. Daily Data Refresh (`daily-data-refresh.yml`)

**The canonical workflow for all OHLC data ingestion.**

| Property | Value |
|----------|-------|
| Schedule | `0 6 * * *` (6:00 AM UTC daily) |
| Trigger | `workflow_run` triggers ML Orchestration |

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

**Fetches fresh intraday OHLC data during market hours.**

| Property | Value |
|----------|-------|
| Schedule | `*/15 13-22 * * 1-5` (every 15 min, market hours) |
| Trigger | `workflow_run` triggers Intraday Forecast |

#### Inputs

| Input | Description | Default |
|-------|-------------|---------|
| `symbols` | Comma-separated symbols | All watchlist |
| `timeframes` | Comma-separated timeframes | `m15,h1` |
| `force_refresh` | Force refresh even if data exists | `false` |

---

### 3. Intraday Forecast (`intraday-forecast.yml`)

**Generates intraday forecasts after fresh data is ingested.**

| Property | Value |
|----------|-------|
| Schedule | Triggered by Intraday Ingestion |
| Backup | `5,20,35,50 13-22 * * 1-5` (5 min offset) |

---

### 4. ML Orchestration (`ml-orchestration.yml`)

**Consolidated ML pipeline for nightly processing.**

| Property | Value |
|----------|-------|
| Schedule | `0 4 * * 1-5` (4:00 AM UTC weekdays) |
| Trigger | `workflow_run` from Daily Data Refresh |

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

## Legacy Workflows (Cron Disabled)

These workflows have been consolidated but retain `workflow_dispatch` for manual runs:

| Workflow | Consolidated Into |
|----------|-------------------|
| `backfill-ohlc.yml` | `daily-data-refresh.yml` |
| `batch-backfill-cron.yml` | `daily-data-refresh.yml` |
| `daily-historical-sync.yml` | `daily-data-refresh.yml` |
| `alpaca-intraday-cron.yml` | `intraday-ingestion.yml` |
| `intraday-update.yml` | `intraday-ingestion.yml` |
| `intraday-update-v2.yml` | `intraday-ingestion.yml` |
| `ml-forecast.yml` | `ml-orchestration.yml` |
| `ml-evaluation.yml` | `ml-orchestration.yml` |
| `data-quality-monitor.yml` | `ml-orchestration.yml` |
| `drift-monitoring.yml` | `ml-orchestration.yml` |
| `options-nightly.yml` | `ml-orchestration.yml` |

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
| `ml_forecasts` | ML Orchestration |
| `forecast_evaluations` | ML Orchestration (model-health) |
| `model_weights` | ML Orchestration (model-health) |
| `options_chain_snapshots` | ML Orchestration (options-processing) |
| `options_ranks` | ML Orchestration (options-processing) |

### Data Flow

1. **Daily**: `Daily Data Refresh` → `ML Orchestration` → Fresh forecasts
2. **Intraday**: `Intraday Ingestion` → `Intraday Forecast` → Real-time signals
3. **On Demand**: Manual `workflow_dispatch` for targeted operations

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
- Verify Daily Data Refresh completed successfully
- Check `workflow_run` trigger configuration

### Logs and Artifacts

- Each workflow uploads validation reports as artifacts
- Check job summaries for detailed results
- Use `gh run view <run-id>` for CLI access
