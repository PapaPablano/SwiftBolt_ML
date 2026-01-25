# Legacy Workflows

**Archived**: 2026-01-21  
**Updated**: 2026-01-25 (moved test-ml.yml to legacy)

This directory contains legacy GitHub Actions workflows that have been superseded by the consolidated canonical workflows.

## Why Archived

These workflows were created during development and have been consolidated to reduce:
- Maintenance overhead (31 workflows → 8)
- Potential race conditions from overlapping triggers
- Unclear ownership and responsibility
- CI/CD complexity
- Duplicate CI runs (test-ml.yml duplicated functionality already in ci.yml)

## Canonical Workflows (Active)

The following workflows are **active** in the parent directory:

| Workflow | Purpose | Schedule/Trigger |
|----------|---------|----------|
| `ci.yml` | Comprehensive CI with change detection (includes ML tests, linting) | On push/PR to main branches |
| `daily-data-refresh.yml` | Daily OHLC data ingestion | 6 AM UTC (Mon-Fri) |
| `intraday-ingestion.yml` | Intraday price updates | Every 15 min (market hours) |
| `intraday-forecast.yml` | Intraday ML predictions | Every hour (market hours) |
| `ml-orchestration.yml` | Nightly ML suite (forecasts, options, health) | 4 AM UTC (Mon-Fri) |
| `deploy-supabase.yml` | Edge function deployment | On push to main |
| `deploy-ml-dashboard.yml` | Dashboard deployment | On push to main |
| `api-contract-tests.yml` | API contract validation | On PR/push |

## Archived Workflows

### Consolidated into `ci.yml`
- `test-ml.yml` - ML tests and linting (now handled by ci.yml with path-based change detection)

### Consolidated into `ml-orchestration.yml`
- `ml-forecast.yml` - Nightly forecasts
- `ml-evaluation.yml` - Feedback loop evaluation
- `data-quality-monitor.yml` - Data quality checks
- `drift-monitoring.yml` - Model drift detection
- `options-nightly.yml` - Options processing

### Consolidated into `daily-data-refresh.yml`
- `daily-historical-sync.yml` - Historical data sync
- `backfill-cron.yml` - Scheduled backfills
- `batch-backfill-cron.yml` - Batch backfill jobs

### Consolidated into `intraday-ingestion.yml`
- `alpaca-intraday-cron.yml` - Alpaca intraday data
- `alpaca-intraday-cron-fixed.yml` - Fixed version
- `intraday-update.yml` - Intraday updates
- `intraday-update-v2.yml` - V2 updates
- `nightly-coverage-check.yml` - Coverage validation

### Replaced by Other Workflows
- `backfill-ohlc.yml` → Manual backfill via `backfill.sh`
- `backfill-intraday-worker.yml` → `intraday-ingestion.yml`
- `symbol-backfill.yml` → `daily-data-refresh.yml`
- `symbol-weight-training.yml` → `ml-orchestration.yml`

### Development/Testing (No Longer Needed)
- `daily-options-scrape.yml` - Options scraping (manual now)
- `frontend-integration-checks.yml` - Frontend tests (separate repo)
- `job-worker.yml` - Job queue worker
- `orchestrator-cron.yml` - Orchestrator cron
- `orchestrator-health.yml` - Health checks

## Data Flow (Current Architecture)

```
┌─────────────────────────────────────────────────────────────┐
│                    MARKET HOURS (9:30-16:00 ET)             │
├─────────────────────────────────────────────────────────────┤
│  intraday-ingestion.yml     Every 15 min                    │
│  └── Fetches live prices from Alpaca                        │
│                                                             │
│  intraday-forecast.yml      Every hour                      │
│  └── Generates intraday predictions                         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    POST-MARKET (After 4 PM ET)              │
├─────────────────────────────────────────────────────────────┤
│  daily-data-refresh.yml     6 AM UTC                        │
│  └── Refreshes daily OHLC bars                              │
│                                                             │
│  ml-orchestration.yml       4 AM UTC (after data refresh)   │
│  ├── ml-forecast (ensemble predictions)                     │
│  ├── options-processing (backfill + snapshots)              │
│  ├── model-health (evaluation + drift + quality)            │
│  │   └── unified-validation (new)                           │
│  └── smoke-tests (verification)                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    ON DEMAND                                │
├─────────────────────────────────────────────────────────────┤
│  ci.yml                      On push/PR to main branches    │
│  ├── detect-changes (uses dorny/paths-filter)               │
│  ├── test-ml (only if ml/** changed)                        │
│  ├── lint-ml (only if ml/** changed)                        │
│  ├── test-edge-functions (only if functions/** changed)     │
│  └── validate-migrations (only if migrations/** changed)    │
│                                                             │
│  deploy-supabase.yml        On push to main                 │
│  deploy-ml-dashboard.yml    On push to main                 │
│  api-contract-tests.yml     On PR/push                      │
└─────────────────────────────────────────────────────────────┘
```

## Restoration

If you need to restore a legacy workflow:

```bash
# View workflow content
cat legacy/workflow-name.yml

# Restore (not recommended - update canonical instead)
cp legacy/workflow-name.yml ../
```

**Warning**: Restoring legacy workflows may cause:
- Duplicate job execution
- Race conditions with canonical workflows
- Conflicting data writes

Consider updating the canonical workflows instead.

## Migration Notes

### For `ml-orchestration.yml`
All ML-related cron jobs have been consolidated. The workflow now includes:
- Unified validation stage (drift detection + multi-TF reconciliation)
- Proper job dependencies (ml-forecast → model-health → smoke-tests)
- Consolidated summary reporting

### For `intraday-ingestion.yml`
Intraday data fetching is now centralized with:
- Alpaca as primary provider
- Automatic fallback logic
- Rate limiting and retry handling

### For `daily-data-refresh.yml`
Daily data operations are consolidated with:
- Symbol universe resolution
- Multi-timeframe support
- Coverage tracking
