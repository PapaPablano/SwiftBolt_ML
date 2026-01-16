---
description: Consolidated GitHub Actions workflow plan
---

# GitHub Actions Refresh Plan

Roadmap for collapsing the current set of workflows into a leaner pipeline that matches the new indicator persistence architecture.

## 1. Current Pain Points
- Redundant cron schedules (`backfill-ohlc`, `batch-backfill-cron`, `daily-historical-sync`) duplicate OHLC ingestion logic.
- Separate intraday ingestion and forecast workflows increase setup overhead and can drift out of sync.
- ML validation/monitoring jobs (`ml-evaluation`, `data-quality-monitor`, `drift-monitoring`, `test-ml`) all bootstrap the same environment independently.
- Utility workflows (`symbol-backfill`, `symbol-weight-training`) run ad-hoc scripts but could be parameterized instead of duplicated YAML.

## 2. Target Architecture Overview
```
Daily Data Refresh ──▶ Intraday Ingestion ──▶ ML Orchestration
        │                      │                       │
  (manual full backfill)  (workflow_run trigger)   (options + eval + monitoring)
```

### 2.1 Daily Data Refresh (Primary Ingestion)
- Keep `daily-data-refresh.yml` as the canonical workflow.
- Expand it to:
  - Run incremental refresh each morning (existing behaviour).
  - Offer `workflow_dispatch` inputs for:
    - `full_backfill` toggle (triggers the heavier scripts).
    - `symbol` / `timeframe` overrides for targeted reruns.
  - Invoke backfill scripts (`backfill-ohlc`, `daily-historical-sync`, `batch-backfill-cron`) as matrix jobs when `full_backfill` is true.
- Retire standalone cron YAMLs once their logic is reachable via this unified workflow.

### 2.2 Intraday Data + Forecast Bundle
Create two streamlined workflows:

1. **intraday-ingestion.yml**
   - Schedule every 5–15 minutes.
   - Matrix over timeframes (`m15`, `h1`).
   - Steps: fetch latest bars → quick validation → push metrics.
   - Replace `intraday-update-v2.yml`; remove `intraday-update.yml` after validation.

2. **intraday-forecast.yml** (renamed & simplified)
   - Trigger: `workflow_run` on intraday ingestion success (or a short cron offset).
   - Steps: run intraday forecast scripts, write indicator snapshots, notify dashboards.

### 2.3 ML Orchestration Workflow
One YAML to run the nightly ML suite:

- Trigger:
  - `workflow_run` from Daily Data Refresh (ensures fresh data).
  - Nightly cron for post-market processing.
- Job matrix includes:
  1. `ml-forecast`
  2. Options routines (`daily-options-scrape`, `options-nightly`)
  3. Model health (`ml-evaluation`, `data-quality-monitor`, `drift-monitoring`)
  4. Smoke tests (`test-ml`)
- Shared setup steps minimize repeated dependency installs.
- Decommission individual YAMLs after successful migration.

### 2.4 Orchestrator & Job Worker
- Keep `job-worker.yml` and `orchestrator-cron.yml` (they drive Supabase queue processing).
- Optionally fold orchestrator submission into Daily Data Refresh if queue usage drops.

### 2.5 Deployment & Miscellaneous
- Leave `frontend-integration-checks.yml` as a standalone CI gate (heavy E2E tests).
- Keep `deploy-supabase.yml` and `deploy-ml-dashboard.yml` manual-only (workflow_dispatch).
- Convert scripts from `symbol-backfill.yml`, `symbol-weight-training.yml`, `backfill-intraday-worker.yml`, `alpaca-intraday-cron.yml`, `api-contract-tests.yml` into reusable composite actions or CLI commands invoked from the consolidated workflows when needed.

## 3. Implementation Steps
1. **Author consolidated YAMLs**
   - Use composite actions for shared environment setup.
   - Reference existing Python scripts rather than duplicating logic.
2. **Migrate scripts**
   - Ensure backfill/ingestion scripts accept CLI flags (`symbol`, `timeframe`, `full_backfill`) so a single workflow covers multiple scenarios.
3. **Disable legacy workflows**
   - After new pipelines run cleanly for a week, remove the redundant YAML files.
4. **Update documentation**
   - Refresh `.github/workflows/README.md` to explain the new layout.
   - Document manual trigger inputs and sample usage.
5. **Monitor Supabase tables**
   - Confirm `indicator_values`, `ohlc_bars_v2`, and `ml_forecasts` remain fresh post migration.

## 4. Suggested Timeline
| Week | Milestone |
| ---- | --------- |
| 1 | Implement consolidated Daily Data Refresh workflow + retire old backfill cron jobs |
| 2 | Deploy intraday ingestion & forecast pair; validate indicator persistence |
| 3 | Roll out ML orchestration workflow; migrate monitoring jobs |
| 4 | Remove unused YAML files, update docs, and review Supabase metrics |

## 5. Risk Mitigation & Monitoring
- **Dry runs:** use `workflow_dispatch` on new YAMLs before enabling cron.
- **Alerts:** ensure status checks/Slack alerts fire on failure to avoid silent data drift.
- **Rollback:** keep legacy workflows on a `legacy-actions` branch for quick restore if needed.
- **Supabase dashboards:** track coverage and indicator freshness during migration.

This plan keeps the data/forecast pipeline aligned with the new indicator persistence while reducing GitHub Actions maintenance overhead.
