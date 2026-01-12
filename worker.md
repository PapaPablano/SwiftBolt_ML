# Worker Summary

## GitHub Actions Workflows

### Alpaca Intraday Update (Market Hours) (`.github/workflows/alpaca-intraday-cron.yml`)
Function: Scheduled and manual job that gates on US market hours before refreshing intraday data and forecasts every 15 minutes on weekdays.@.github/workflows/alpaca-intraday-cron.yml#6-113

Scripts:
- `python src/scripts/alpaca_backfill_ohlc_v2.py --timeframe <tf>` for requested timeframes.@.github/workflows/alpaca-intraday-cron.yml#234-277
- `python -m src.intraday_forecast_job` for 15m/1h forecast generations.@.github/workflows/alpaca-intraday-cron.yml#292-312

Data input:
- Supabase, database, and Alpaca credentials injected from secrets.@.github/workflows/alpaca-intraday-cron.yml#129-152
- Optional workflow inputs (`symbols`, `timeframes`, `force_refresh`).@.github/workflows/alpaca-intraday-cron.yml#15-29
- **Source & Ingress:** GitHub Actions secrets → step writes `.env` consumed by `ml` scripts; dispatch inputs flow via `GITHUB_EVENT` payload.

Data output:
- Updates summarized via GitHub Step Summary including total bars and failed timeframes.@.github/workflows/alpaca-intraday-cron.yml#270-331
- Forecast artefacts for requested symbols/timeframes written via forecasting job.
- **Destination & Egress:** Supabase `ohlc_bars_v2` (via backfill script) and `forecasts` records updated; run results exposed in GitHub Step Summary.

Details: Skips execution outside market windows unless manually dispatched, captures Supabase snapshots when data is stale, and can trigger downstream cache refresh hooks.@.github/workflows/alpaca-intraday-cron.yml#154-323

### Backfill Worker Cron (`.github/workflows/backfill-cron.yml`)
Function: Cron job that wakes the backfill worker during market hours to process pending chunks.@.github/workflows/backfill-cron.yml#4-44

Scripts:
- `curl` POST to Supabase edge function `trigger-backfill` to enqueue worker runs.@.github/workflows/backfill-cron.yml#40-44

Data input:
- Supabase anon key used for authenticated trigger.@.github/workflows/backfill-cron.yml#38-43
- **Source & Ingress:** GitHub Actions secret `SUPABASE_ANON_KEY` injected into curl request headers hitting Supabase edge function.

Data output:
- Supabase backfill worker receives trigger and logs completion time in GitHub summary.@.github/workflows/backfill-cron.yml#40-50
- **Destination & Egress:** HTTPS POST to Supabase `trigger-backfill` function which calls internal `run-backfill-worker`; job results surfaced in GitHub workflow logs.

Details: Guarded by UTC market window checks and supports manual overrides through workflow dispatch.@.github/workflows/backfill-cron.yml#13-33

### Backfill Intraday Worker (`.github/workflows/backfill-intraday-worker.yml`)
Function: Manual workflow to run parallel intraday backfill workers (legacy/disabled schedule).@.github/workflows/backfill-intraday-worker.yml#1-27

Scripts:
- `curl` POST to Supabase `backfill-intraday-worker` for each matrix worker.@.github/workflows/backfill-intraday-worker.yml#36-48

Data input:
- Supabase URL and service role key from secrets.@.github/workflows/backfill-intraday-worker.yml#31-40
- Optional `parallel_workers` input controlling matrix fan-out.@.github/workflows/backfill-intraday-worker.yml#8-26
- **Source & Ingress:** Secrets and dispatch inputs provided by GitHub Actions environment -> exported env vars consumed by curl payload per worker.

Data output:
- Worker responses surfaced per matrix iteration and summarized with timestamps.@.github/workflows/backfill-intraday-worker.yml#45-55
- **Destination & Egress:** Each curl call posts to Supabase `backfill-intraday-worker` edge function; status echoed back into GitHub logs and step summaries.

Details: Allows manual scaling of backfill throughput with up to three concurrent invocations, retaining logs per worker.

### Automated OHLC Backfill (`.github/workflows/backfill-ohlc.yml`)
Function: Manual Alpaca OHLC backfill for selected symbols and timeframes.@.github/workflows/backfill-ohlc.yml#3-83

Scripts:
- `python src/scripts/alpaca_backfill_ohlc_v2.py` for single or multi-timeframe pulls.@.github/workflows/backfill-ohlc.yml#65-83

Data input:
- Supabase service key and Alpaca credentials from secrets.@.github/workflows/backfill-ohlc.yml#43-55
- Inputs: `symbols`, `timeframe`, `all_timeframes`.
- **Source & Ingress:** Secrets pulled from GitHub Actions store, written into `ml/.env`; workflow_dispatch inputs forwarded via environment flags to Python script.

Data output:
- Step summary echoes dataset scope and status.@.github/workflows/backfill-ohlc.yml#85-99
- **Destination & Egress:** Python backfill script writes directly to Supabase `ohlc_bars_v2`; run metadata recorded in GitHub summary output.

Details: Builds `.env` inside `ml/` for scripts and optionally loops over all supported timeframes to ensure coverage.@.github/workflows/backfill-ohlc.yml#42-83

### Phase 2 Batch Backfill Cron (`.github/workflows/batch-backfill-cron.yml`)
Function: Nightly orchestrator to seed batch backfill jobs with optional timeframe selection.@.github/workflows/batch-backfill-cron.yml#1-60

Scripts:
- `curl` POST to `batch-backfill-orchestrator` Supabase function.@.github/workflows/batch-backfill-cron.yml#38-43
- `curl` POST to Supabase RPC `get_batch_job_stats` for reporting.@.github/workflows/batch-backfill-cron.yml#54-60

Data input:
- Supabase service role and anon keys from secrets.@.github/workflows/batch-backfill-cron.yml#24-59
- Inputs: `symbols_count`, `timeframes` used to build request payload.@.github/workflows/batch-backfill-cron.yml#28-37
- **Source & Ingress:** GitHub Actions secrets loaded into environment variables; workflow inputs parsed into JSON body sent over HTTPS to Supabase edge function.

Data output:
- Orchestrator response and job stats printed to logs for monitoring.@.github/workflows/batch-backfill-cron.yml#38-60
- **Destination & Egress:** Curl requests hit Supabase `batch-backfill-orchestrator` function and REST RPC `get_batch_job_stats`; responses streamed to GitHub logs.

Details: Runs once nightly after market close and continues even if orchestrator endpoint is temporarily unavailable (continue-on-error).@.github/workflows/batch-backfill-cron.yml#5-61

### Daily Data Refresh (`.github/workflows/daily-data-refresh.yml`)
Function: Daily 06:00 UTC refresh with optional full backfill and validation artifact upload.@.github/workflows/daily-data-refresh.yml#4-107

Scripts:
- `python src/scripts/alpaca_backfill_ohlc_v2.py` across all timeframes for incremental updates.@.github/workflows/daily-data-refresh.yml#63-70
- `./src/scripts/smart_backfill_all.sh` for forced full backfills.@.github/workflows/daily-data-refresh.yml#72-78
- `python src/scripts/backfill_with_gap_detection.py --all` for validation and enforcement.@.github/workflows/daily-data-refresh.yml#80-101

Data input:
- Supabase, database, and Alpaca secrets stored in generated `.env`.@.github/workflows/daily-data-refresh.yml#35-50
- Manual flag `force_full_backfill` to switch execution path.@.github/workflows/daily-data-refresh.yml#7-13
- **Source & Ingress:** GitHub Actions pulls secrets into environment then writes `ml/.env`; dispatch input toggles `force_full_backfill` flag consumed by Bash/Python scripts.

Data output:
- Validation report artifact uploaded to GitHub and logged in summary.@.github/workflows/daily-data-refresh.yml#80-107
- Gap detection logs inform follow-up actions.
- **Destination & Egress:** Alpaca API responses ingested into Supabase `ohlc_bars_v2`; validation artifacts stored as GitHub Action artifacts and summaries.

Details: Handles both lightweight incremental refresh and heavy validation runs while continuing despite validation failures to surface issues without halting automation.@.github/workflows/daily-data-refresh.yml#52-107

### Daily Historical Sync (Yahoo Finance) (`.github/workflows/daily-historical-sync.yml`)
Function: Manual/legacy workflow to sync verified Yahoo Finance data and purge stale intraday rows.@.github/workflows/daily-historical-sync.yml#1-88

Scripts:
- `python src/scripts/backfill_ohlc_yfinance.py` per symbol or watchlist.@.github/workflows/daily-historical-sync.yml#59-70
- `curl` DELETE against Supabase REST API to remove Tradier intraday data.@.github/workflows/daily-historical-sync.yml#72-84

Data input:
- Supabase URL and service key via secrets.@.github/workflows/daily-historical-sync.yml#51-83
- Inputs: `symbols`, `days_back` (default 1).@.github/workflows/daily-historical-sync.yml#13-22
- **Source & Ingress:** GitHub Actions secrets and dispatch inputs feed Python script parameters; Yahoo Finance data fetched via script-level HTTP requests.

Data output:
- Yahoo-derived OHLC rows inserted through scripts; stale intraday rows deleted via REST call.@.github/workflows/daily-historical-sync.yml#64-84
- **Destination & Egress:** Data posted to Supabase REST endpoints updating `ohlc_bars_v2`; DELETE request removes Tradier rows; run details emitted in workflow logs.

Details: Schedule disabled after Alpaca migration but kept for manual recovery scenarios; still enforces market-hour gate and cleanup logic.@.github/workflows/daily-historical-sync.yml#6-86

### Options Scrape (`.github/workflows/daily-options-scrape.yml`)
Function: High-frequency cron to fetch options snapshots during and after market hours.@.github/workflows/daily-options-scrape.yml#4-99

Scripts:
- `curl` POST to Supabase `options-scrape` function with dynamic payload.@.github/workflows/daily-options-scrape.yml#60-84

Data input:
- Supabase service role key for authorization.@.github/workflows/daily-options-scrape.yml#47-64
- Market-hour detection from system clock; optional manual dispatch.
- **Source & Ingress:** Secrets injected into curl headers; cron schedule/time-of-day derived from GitHub runner clock; manual inputs via dispatch payload.

Data output:
- Returns scraped totals and records symbol-level responses in summary env variables.@.github/workflows/daily-options-scrape.yml#78-95
- **Destination & Egress:** Supabase `options-scrape` edge function writes to options tables; response metrics appended to GitHub Step Summary and env vars.

Details: Adapts payload based on time of day (increasing expirations after close) and aborts on weekends.@.github/workflows/daily-options-scrape.yml#26-85

### Data Quality Monitor (`.github/workflows/data-quality-monitor.yml`)
Function: Periodic validation and alerting workflow that opens GitHub issues on repeated failures.@.github/workflows/data-quality-monitor.yml#6-176

Scripts:
- `scripts/validate_data_quality.sh` generates coverage report.@.github/workflows/data-quality-monitor.yml#62-74
- GitHub Script step ensures labels and opens issues when validation fails.@.github/workflows/data-quality-monitor.yml#91-169

Data input:
- Database and Supabase credentials via `.env` creation.@.github/workflows/data-quality-monitor.yml#35-46
- Symbols list input defaulting to major watchlist.@.github/workflows/data-quality-monitor.yml#12-16
- **Source & Ingress:** Secrets mapped into `.env` for shell script; symbol list from workflow inputs defaults; PostgreSQL client pulls coverage metrics via `psql` using `DATABASE_URL`.

Data output:
- Report artifact uploaded and summarized; optional GitHub issue created with remediation steps.@.github/workflows/data-quality-monitor.yml#84-169
- **Destination & Egress:** Validation script outputs to `/tmp/report.txt` → uploaded as GitHub artifact; GitHub issue created via `actions/github-script` when failures persist.

Details: Installs Postgres client for direct checks, surfaces warnings for stale data, and skips redundant issue creation thanks to label presence check.@.github/workflows/data-quality-monitor.yml#48-169

### Deploy ml-dashboard (`.github/workflows/deploy-ml-dashboard.yml`)
Function: Auto-deploy Supabase `ml-dashboard` edge function when relevant files change.@.github/workflows/deploy-ml-dashboard.yml#4-35

Scripts:
- `supabase functions deploy ml-dashboard` via Supabase CLI.@.github/workflows/deploy-ml-dashboard.yml#29-35

Data input:
- Supabase access token and project reference secrets.@.github/workflows/deploy-ml-dashboard.yml#31-34
- **Source & Ingress:** GitHub Actions secrets feed Supabase CLI `supabase functions deploy` command executed within `backend/` directory.

Data output:
- Updated edge function deployed to Supabase project.
- **Destination & Egress:** Supabase CLI pushes function bundle to project referenced by `SUPABASE_PROJECT_REF`; deployment logs captured in GitHub job output.

Details: Uses Supabase CLI setup action and enforces concurrency per branch to avoid overlapping deploys.@.github/workflows/deploy-ml-dashboard.yml#15-35

### Deploy Supabase Functions (`.github/workflows/deploy-supabase.yml`)
Function: Deploys all Supabase edge functions and database migrations on pushes to main.@.github/workflows/deploy-supabase.yml#3-72

Scripts:
- `supabase functions deploy` for all functions.@.github/workflows/deploy-supabase.yml#32-34
- `supabase db push` for migrations after successful function deploy.@.github/workflows/deploy-supabase.yml#68-70

Data input:
- Supabase access token, project ref, Alpaca credentials for secret propagation.@.github/workflows/deploy-supabase.yml#27-44
- **Source & Ingress:** Secrets imported into environment for Supabase CLI commands and `supabase secrets set` invocation; workflow triggers on repo push.

Data output:
- Updated edge functions and applied migrations in target project.
- **Destination & Egress:** `supabase functions deploy` uploads edge functions; `supabase db push` applies migrations to hosted database; CLI output logged to GitHub Actions.

Details: CLI linked to project via `supabase link` in both jobs and sets runtime secrets post-deploy.@.github/workflows/deploy-supabase.yml#26-44

### Model Drift Monitoring (`.github/workflows/drift-monitoring.yml`)
Function: Daily drift and staleness check across forecasts and supporting data.@.github/workflows/drift-monitoring.yml#4-76

Scripts:
- Inline Python invoking `DriftDetector` and `check_all_staleness`.@.github/workflows/drift-monitoring.yml#35-61
- `python src/monitoring/forecast_staleness.py --all` for detailed checks.@.github/workflows/drift-monitoring.yml#63-70

Data input:
- Supabase URL and key for data access.@.github/workflows/drift-monitoring.yml#38-66
- Optional manual `window_days` input to tune analysis window.@.github/workflows/drift-monitoring.yml#8-13
- **Source & Ingress:** Secrets and inputs flow into environment; Python modules connect to Supabase via `SUPABASE_KEY` to query drift data.

Data output:
- Logs warnings for stale data and surfaces drift results in workflow log.@.github/workflows/drift-monitoring.yml#35-75
- **Destination & Egress:** Findings emitted to GitHub logs and warnings; no external data writes except optional Supabase queries for metrics.

Details: Marks issues as GitHub workflow errors when drift detected and encourages escalation through manual notifications.@.github/workflows/drift-monitoring.yml#35-76

### Intraday Forecast (Calibration) (`.github/workflows/intraday-forecast.yml`)
Function: Market-hour–gated intraday forecast job with manual symbol overrides.@.github/workflows/intraday-forecast.yml#3-114

Scripts:
- `python -m src.intraday_forecast_job` with requested symbol/horizon combinations.@.github/workflows/intraday-forecast.yml#85-100

Data input:
- Supabase service key for data/feature pulls.@.github/workflows/intraday-forecast.yml#87-89
- Manual `symbol` input for scoped forecasts.@.github/workflows/intraday-forecast.yml#6-10
- **Source & Ingress:** Secrets populate `.env` for ML scripts; symbol dispatch input forwarded as CLI argument to forecast job.

Data output:
- Step summary records status and market state; forecast records stored via invoked module.@.github/workflows/intraday-forecast.yml#102-113
- **Destination & Egress:** Forecast script writes results into Supabase forecasts tables; GitHub summary communicates market state.

Details: Stops automatically outside extended market hours unless manually run, ensuring compute budget aligns with trading windows.@.github/workflows/intraday-forecast.yml#24-61

### Intraday Data Update (`.github/workflows/intraday-update.yml`)
Function: Manual data refresh that calls Supabase intraday update function during market hours.@.github/workflows/intraday-update.yml#3-98

Scripts:
- `curl` POST to `functions/v1/intraday-update` with optional symbol list.@.github/workflows/intraday-update.yml#63-73

Data input:
- Supabase service role key for auth.@.github/workflows/intraday-update.yml#63-66
- Workflow input `symbols` to scope update.@.github/workflows/intraday-update.yml#5-9
- **Source & Ingress:** Secrets inserted into curl headers hitting Supabase edge function; optional `symbols` input encoded into request JSON.

Data output:
- Response provides symbols updated and market state, recorded in environment for summary.@.github/workflows/intraday-update.yml#69-95
- **Destination & Egress:** Supabase `intraday-update` function updates downstream tables/caches; response consumed by workflow and summarized.

Details: Skips execution when outside 9:30–16:00 ET unless manually triggered, summarizing outcomes in GitHub step summary.@.github/workflows/intraday-update.yml#15-96

### Intraday Update V2 (Tradier) (`.github/workflows/intraday-update-v2.yml`)
Function: Legacy Tradier-based intraday update kept for manual fallback.@.github/workflows/intraday-update-v2.yml#3-125

Scripts:
- Temporary Deno script `run_intraday.ts` invoking `_shared/intraday-service-v2.ts` helpers.@.github/workflows/intraday-update-v2.yml#85-118

Data input:
- Supabase and Tradier credentials from secrets.@.github/workflows/intraday-update-v2.yml#70-118
- Manual `symbols` input to limit processing.@.github/workflows/intraday-update-v2.yml#12-15
- **Source & Ingress:** GitHub secrets exported to env for Deno script; optional dispatch input parsed into `INPUT_SYMBOLS` env for runtime.

Data output:
- Logs successful/failed symbols and exits when market closed.@.github/workflows/intraday-update-v2.yml#84-124
- **Destination & Egress:** Deno script posts updated bars to Supabase via `_shared` services; GitHub job logs capture per-symbol outcomes.

Details: Market clock is queried via Tradier to ensure only open sessions run, with DST-guarded lock window checks.@.github/workflows/intraday-update-v2.yml#35-68

### ML Job Worker (`.github/workflows/job-worker.yml`)
Function: Market-aware worker that processes forecast and ranking job queues when backlog detected.@.github/workflows/job-worker.yml#4-122

Scripts:
- `python -m src.job_worker --job-type forecast` for forecast queue.@.github/workflows/job-worker.yml#104-109
- `python src/ranking_job_worker.py` for ranking queue.@.github/workflows/job-worker.yml#118-121

Data input:
- Supabase URL/key and `MIN_BARS_FOR_TRAINING` envs.@.github/workflows/job-worker.yml#101-117
- Optional `job_type` input to target a specific queue.@.github/workflows/job-worker.yml#10-20
- **Source & Ingress:** Secrets and inputs provided via GitHub env; preflight Supabase REST query uses `SUPABASE_KEY` for queue counts.

Data output:
- Job execution results routed through script logs; summary indicates completion per run.@.github/workflows/job-worker.yml#78-123
- **Destination & Egress:** Python workers mutate Supabase `job_queue`/`ranking_jobs` tables; status reporting surfaces in GitHub logs and summary.

Details: Performs preflight Supabase query to skip expensive setup when queues are empty, conserving resources.@.github/workflows/job-worker.yml#60-76

### ML Forecast Evaluation (Feedback Loop) (`.github/workflows/ml-evaluation.yml`)
Function: Daily evaluation job comparing forecasts to realized outcomes and optionally updating model weights.@.github/workflows/ml-evaluation.yml#3-138

Scripts:
- `python -m src.evaluation_job` (scheduled) or horizon-specific execution.@.github/workflows/ml-evaluation.yml#51-74
- `curl` POST to Supabase RPC `trigger_weight_update` for weight adjustments.@.github/workflows/ml-evaluation.yml#86-91
- `curl` Supabase `ml-dashboard` function for accuracy summaries.@.github/workflows/ml-evaluation.yml#99-101

Data input:
- Supabase URL/key for data and RPC access.@.github/workflows/ml-evaluation.yml#47-100
- Inputs: `horizon`, `update_weights` to customize manual runs.@.github/workflows/ml-evaluation.yml#10-21
- **Source & Ingress:** Secrets consumed by Python evaluation script and curl RPC calls; workflow inputs forwarded as CLI args/env variables.

Data output:
- Forecast evaluations stored via script, RPC updates weights, summaries captured in step summary.@.github/workflows/ml-evaluation.yml#80-138
- **Destination & Egress:** Evaluation job writes to Supabase tables; RPC updates `model_weights`; accuracy fetch output logged in GitHub summary.

Details: Adjusts behavior between scheduled and manual invocations while maintaining a feedback loop into Supabase-stored metrics.@.github/workflows/ml-evaluation.yml#45-138

### ML Forecast (Ensemble) (`.github/workflows/ml-forecast.yml`)
Function: Weeknight ensemble forecast job with manual overrides for symbol and ensemble usage.@.github/workflows/ml-forecast.yml#3-103

Scripts:
- `python -m src.forecast_job` for scheduled or manual runs.@.github/workflows/ml-forecast.yml#52-74

Data input:
- Supabase URL/key, ensemble flag, and minimum bars threshold env values.@.github/workflows/ml-forecast.yml#47-74
- Manual inputs `symbol`, `use_ensemble` to target runs.@.github/workflows/ml-forecast.yml#12-20
- **Source & Ingress:** Secrets and env flags configured in GitHub run; dispatch inputs propagate to CLI params of `src.forecast_job`.

Data output:
- Forecast records written through script; step summary reports trigger context and features used.@.github/workflows/ml-forecast.yml#77-102
- **Destination & Egress:** Forecast script saves predictions to Supabase `forecasts`; GitHub summary communicates run metadata.

Details: Scheduled after options pipelines to ensure upstream data freshness before computing ensemble forecasts.@.github/workflows/ml-forecast.yml#4-86

### Nightly Options Backfill (`.github/workflows/options-nightly.yml`)
Function: Manual/scheduled options backfill and snapshot capture workflow.@.github/workflows/options-nightly.yml#3-89

Scripts:
- `python src/scripts/backfill_options.py` for historical chains.@.github/workflows/options-nightly.yml#41-60
- `python src/options_snapshot_job.py` to store price snapshots.@.github/workflows/options-nightly.yml#63-68

Data input:
- Supabase URL/key from secrets.@.github/workflows/options-nightly.yml#37-68
- Optional `symbol` input for manual filtering.@.github/workflows/options-nightly.yml#6-10
- **Source & Ingress:** Secrets exported for Python scripts; manual input mapped to CLI args; underlying scripts fetch options data from configured providers (Polygon/Alpaca) via API calls.

Data output:
- Updates `options_chain_snapshots` and `options_ranks` tables via invoked scripts.@.github/workflows/options-nightly.yml#63-85
- **Destination & Egress:** Supabase tables updated through script-level Supabase clients; job summary records counts in GitHub Step Summary.

Details: Designed for post-market execution with extended timeout to accommodate slower option data ingestion.@.github/workflows/options-nightly.yml#15-88

### Orchestrator Cron (`.github/workflows/orchestrator-cron.yml`)
Function: Manual trigger for orchestration edge function (schedule disabled pending Alpaca migration verification).@.github/workflows/orchestrator-cron.yml#1-25

Scripts:
- `curl` POST to Supabase `orchestrator?action=tick`.@.github/workflows/orchestrator-cron.yml#18-21

Data input:
- Supabase service role key for authorization.@.github/workflows/orchestrator-cron.yml#18-21
- **Source & Ingress:** GitHub secret inserted into curl header; manual dispatch triggers run.

Data output:
- Logs orchestration tick results and timestamp.@.github/workflows/orchestrator-cron.yml#18-26
- **Destination & Egress:** Supabase `orchestrator` function executed server-side; response echoed in GitHub logs.

Details: Keeps orchestrator accessible without automated polling to avoid conflicts with new data providers.@.github/workflows/orchestrator-cron.yml#4-26

### Symbol Backfill Worker (`.github/workflows/symbol-backfill.yml`)
Function: Manual symbol backfill queue processor with market-hour guard.@.github/workflows/symbol-backfill.yml#3-107

Scripts:
- `python src/scripts/process_backfill_queue.py` for queued jobs.@.github/workflows/symbol-backfill.yml#79-81
- `python src/scripts/deep_backfill_ohlc.py --all-timeframes` for single-symbol manual runs.@.github/workflows/symbol-backfill.yml#83-95

Data input:
- Supabase URL/key and Polygon (Massive) API key.@.github/workflows/symbol-backfill.yml#75-95
- Inputs: `symbol`, `force` to control execution path.@.github/workflows/symbol-backfill.yml#9-19
- **Source & Ingress:** Secrets and inputs passed from GitHub env into Python scripts; Polygon data pulled via Massive API using provided key.

Data output:
- Logs results and options for queue vs. targeted backfills in summary.@.github/workflows/symbol-backfill.yml#97-109
- **Destination & Egress:** Scripts write to Supabase `symbol_backfill_queue`, `ohlc_bars_v2`; GitHub summary highlights run mode.

Details: Supports forced runs to overwrite existing data and bypasses schedule when manual override provided.@.github/workflows/symbol-backfill.yml#31-106

### Symbol Weight Training (`.github/workflows/symbol-weight-training.yml`)
Function: Twice-daily weight training job synchronized to 08:45 America/Chicago.@.github/workflows/symbol-weight-training.yml#1-57

Scripts:
- `python src/symbol_weight_training_job.py` inside `ml/`.@.github/workflows/symbol-weight-training.yml#41-48

Data input:
- Supabase URL/key and `ENABLE_SYMBOL_WEIGHTS` flag.@.github/workflows/symbol-weight-training.yml#43-46
- **Source & Ingress:** GitHub secrets populate environment for training script; cron-triggered run ensures consistent schedule.

Data output:
- Updated symbol weights persisted through training script; workflow summary reports status.@.github/workflows/symbol-weight-training.yml#41-57
- **Destination & Egress:** Training job updates Supabase tables storing symbol weights; results surfaced via GitHub summary.

Details: Double-cron plus runtime time-check ensures execution only occurs at intended local time despite DST shifts.@.github/workflows/symbol-weight-training.yml#5-27

### API Contract Tests (`.github/workflows/api-contract-tests.yml`)
Function: Validates response schemas of key endpoints to prevent breaking the SwiftUI app. Runs on PRs and pushes to main/develop when Supabase functions or Swift client code changes.@.github/workflows/api-contract-tests.yml#1-325

Scripts:
- Creates JSON schemas for `chart`, `user-refresh`, and `data-health` endpoints using ajv-cli.@.github/workflows/api-contract-tests.yml#49-150
- Validates endpoint TypeScript types match defined schemas and checks Swift model compatibility.@.github/workflows/api-contract-tests.yml#152-280

Data input:
- No external data dependencies; uses local file system checks.
- **Source & Ingress:** Workflow triggers on code changes; schema definitions generated inline; TypeScript/Swift files read from repository.

Data output:
- GitHub Step Summary with validation results and compatibility checks.@.github/workflows/api-contract-tests.yml#152-320
- **Destination & Egress:** Validation report published to GitHub Actions summary; no external data writes.

Details: Ensures API contract stability between backend Edge Functions and SwiftUI client, preventing breaking changes through automated schema validation.@.github/workflows/api-contract-tests.yml#31-325

### Frontend Integration Checks (`.github/workflows/frontend-integration-checks.yml`)
Function: Validates live data flow from backend to frontend during market hours and ensures ML rankings integration. Runs on code changes to client or backend.@.github/workflows/frontend-integration-checks.yml#1-594

Scripts:
- Checks live data flow patterns and ViewModel→endpoint mappings in Swift code.@.github/workflows/frontend-integration-checks.yml#43-150
- Validates ML rankings integration and data freshness UI components.@.github/workflows/frontend-integration-checks.yml#200-350
- Performs end-to-end data flow validation during simulated market hours.@.github/workflows/frontend-integration-checks.yml#400-550

Data input:
- Swift client code and Supabase function definitions from repository.
- Optional manual dispatch for on-demand validation.
- **Source & Ingress:** Repository files provide integration patterns; workflow analyzes code structure and endpoint connections.

Data output:
- Comprehensive integration report with live data flow validation results.@.github/workflows/frontend-integration-checks.yml#36-590
- **Destination & Egress:** GitHub Step Summary with integration status; identifies missing connections or deprecated patterns.

Details: Ensures SwiftUI app can properly consume live backend data and that ML rankings flow correctly to the frontend interface.@.github/workflows/frontend-integration-checks.yml#27-594

### ML Tests & Linting (`.github/workflows/test-ml.yml`)
Function: CI pipeline running tests, linting, and security scans on ML code paths.@.github/workflows/test-ml.yml#3-120

Scripts:
- `pytest` with coverage reporting.@.github/workflows/test-ml.yml#39-43
- `black`, `isort`, `flake8`, `mypy` for quality checks.@.github/workflows/test-ml.yml#72-90
- `safety` and `bandit` for security audits.@.github/workflows/test-ml.yml#112-120

Data input:
- Python version matrix 3.10/3.11 via strategy.@.github/workflows/test-ml.yml#17-38
- Requirements and dev requirements installed from repo.
- **Source & Ingress:** Code checkout provides ML sources; requirements retrieved from repo files; GitHub matrix injects Python versions.

Data output:
- Coverage uploaded to Codecov; lint and security logs produced in job steps.@.github/workflows/test-ml.yml#44-120
- **Destination & Egress:** Coverage XML sent to Codecov via action; lint/test logs retained in GitHub job output; Bandit/Safety reports stored as artifacts when configured.

Details: Ensures ML module quality across pushes and PRs to master/develop branches with layered checks.@.github/workflows/test-ml.yml#3-121

## Supabase Edge Functions (`supabase/functions`)

### adjust-bars-for-splits (`supabase/functions/adjust-bars-for-splits/index.ts`)
Function: Processes corporate action split payloads to adjust historical bars and mark corporate actions complete.@supabase/functions/adjust-bars-for-splits/index.ts#11-147

Scripts:
- Uses Supabase client to query `corporate_actions`, `symbols`, and `ohlc_bars_v2` tables and upsert adjusted bars in chunks.@supabase/functions/adjust-bars-for-splits/index.ts#33-121

Data input:
- JSON body `{ splits: Split[] }` containing symbol, date, ratio metadata.@supabase/functions/adjust-bars-for-splits/index.ts#13-30
- **Source & Ingress:** Upstream caller (e.g., `sync-corporate-actions` function) sends JSON payload over Supabase Edge Function HTTP endpoint using service role credentials.

Data output:
- Upserts adjusted rows into `ohlc_bars_v2` and flags corresponding corporate actions as processed.@supabase/functions/adjust-bars-for-splits/index.ts#97-138
- **Destination & Egress:** Writes to Supabase Postgres tables (`ohlc_bars_v2`, `corporate_actions`); response returned to invoking client over HTTPS.

Details: Handles missing data gracefully, batching updates to avoid payload limits, and returns per-symbol adjustment summaries.@supabase/functions/adjust-bars-for-splits/index.ts#71-149

### apply-h1-fix (`supabase/functions/apply-h1-fix/index.ts`)
Function: One-time migration utility that recreates `get_chart_data_v2` to source h1 data from `ohlc_bars_v2` instead of intraday only.@supabase/functions/apply-h1-fix/index.ts#6-175

Scripts:
- Executes Supabase RPC `exec_sql` to drop and recreate the function with updated logic.@supabase/functions/apply-h1-fix/index.ts#26-175

Data input:
- No payload; relies on environment-supplied Supabase credentials.@supabase/functions/apply-h1-fix/index.ts#20-28
- **Source & Ingress:** Supabase Edge Function runtime loads `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` environment variables provided at deploy time.

Data output:
- Returns migration success metadata and updates database function definition.@supabase/functions/apply-h1-fix/index.ts#165-175
- **Destination & Egress:** Executes SQL via Supabase RPC (`exec_sql`) against hosted Postgres; JSON response sent back to HTTP caller.

Details: Enables cross-timeframe aggregation for h1 by combining historical `ohlc_bars_v2` and real-time intraday aggregations inside the new SQL function.@supabase/functions/apply-h1-fix/index.ts#68-159

### chart (`supabase/functions/chart/index.ts`)
Function: Consolidated chart data endpoint for frontend consumption. Single read path for app charts returning OHLC bars, forecasts, options ranks, and freshness indicators.@supabase/functions/chart/index.ts#1-344

Scripts:
- Calls `get_chart_data_v2` for provider-aware OHLC bars, fetches latest forecasts, and retrieves options ranks.@supabase/functions/chart/index.ts#100-280
- Includes market status, pending splits warnings, and comprehensive metadata for UI rendering.@supabase/functions/chart/index.ts#50-344

Data input:
- GET query parameters: `symbol`, `timeframe`, optional `start`/`end` dates.@supabase/functions/chart/index.ts#80-120
- **Source & Ingress:** Frontend app makes authenticated GET requests; function reads from multiple Supabase tables using service role credentials.

Data output:
- JSON response with bars, forecast data, options ranks, meta information, and freshness metrics.@supabase/functions/chart/index.ts#250-344
- **Destination & Egress:** Consolidated chart data returned to caller; no database writes except read operations against `ohlc_bars_v2`, `forecasts`, `options_ranks`.

Details: Eliminates need for multiple frontend API calls by providing all chart-related data in a single, provider-aware response with freshness indicators.@supabase/functions/chart/index.ts#1-344

### data-health (`supabase/functions/data-health/index.ts`)
Function: Unified health snapshot endpoint for data freshness monitoring across all symbols/timeframes. Combines coverage, job status, forecast staleness, and options data into health classifications.@supabase/functions/data-health/index.ts#1-336

Scripts:
- Queries `coverage_status`, `job_runs`, `forecasts`, and `options_chain_snapshots` tables.@supabase/functions/data-health/index.ts#80-200
- Calculates freshness SLAs, determines health status (healthy/warning/critical), and aggregates summary metrics.@supabase/functions/data-health/index.ts#200-336

Data input:
- GET query parameters: optional `symbol` and `timeframe` filters (defaults to all).@supabase/functions/data-health/index.ts#60-80
- **Source & Ingress:** Monitoring dashboards or alerts make authenticated GET requests; function reads from multiple Supabase tables using service role credentials.

Data output:
- JSON with per-symbol/timeframe health statuses and overall summary statistics.@supabase/functions/data-health/index.ts#250-336
- **Destination & Egress:** Health data returned to caller; no database writes except read operations against monitoring tables.

Details: Provides comprehensive health monitoring with configurable SLAs, critical thresholds, and market-hour awareness for automated alerting.@supabase/functions/data-health/index.ts#1-336

### ensure-coverage (`supabase/functions/ensure-coverage/index.ts`)
Function: Checks bar coverage for a symbol/timeframe range and seeds backfill jobs when gaps exist.@supabase/functions/ensure-coverage/index.ts#1-133

Scripts:
- Calls Supabase RPC `get_coverage`, upserts into `backfill_jobs`, and seeds `backfill_chunks` entries.@supabase/functions/ensure-coverage/index.ts#39-127

Data input:
- JSON `{ symbol, timeframe, fromTs, toTs }` describing desired coverage window.@supabase/functions/ensure-coverage/index.ts#34-67
- **Source & Ingress:** External services or workflows invoke REST endpoint with service role credentials to request coverage verification.

Data output:
- Returns coverage metadata and job ID when backfill queued (202) or confirms existing coverage (200).@supabase/functions/ensure-coverage/index.ts#61-133
- **Destination & Egress:** Upserts into `backfill_jobs`/`backfill_chunks`; response JSON delivered to caller describing coverage/job status.

Details: Idempotently creates jobs thanks to `onConflict` keys and enumerates per-day chunks for downstream workers.@supabase/functions/ensure-coverage/index.ts#74-158

### market-status (`supabase/functions/market-status/index.ts`)
Function: Provides current market open/close status plus pending corporate actions for an optional symbol.@supabase/functions/market-status/index.ts#8-67

Scripts:
- Uses Alpaca-backed `MarketIntelligence` service to fetch status and corporate actions via Supabase client.@supabase/functions/market-status/index.ts#18-66

Data input:
- Optional query parameter `symbol` for corporate action lookup.@supabase/functions/market-status/index.ts#10-46
- **Source & Ingress:** HTTP GET requests from clients (e.g., app or dashboard) include query params; function reads environment-provided API keys for Alpaca.

Data output:
- JSON containing market status timestamps and pending corporate action summaries.@supabase/functions/market-status/index.ts#37-68
- **Destination & Egress:** Response returned to caller; no database writes except read operations against Supabase tables (`corporate_actions`).

Details: Applies in-memory caching via shared providers/rate limiter to stay within API quotas while responding quickly.@supabase/functions/market-status/index.ts#19-33

### options-quotes (`supabase/functions/options-quotes/index.ts`)
Function: Returns quotes for specified option contracts leveraging provider router cache.@supabase/functions/options-quotes/index.ts#25-128

Scripts:
- Retrieves options chain via `_shared` provider factory and maps requested contracts into quote payloads.@supabase/functions/options-quotes/index.ts#85-128

Data input:
- GET query params or POST body specifying `symbol`, `contracts[]`, optional `expiration` (max 120 contracts).@supabase/functions/options-quotes/index.ts#35-83
- **Source & Ingress:** REST clients send payloads through Supabase Edge Function; provider router retrieves upstream data from configured market data providers.

Data output:
- JSON response summarizing quote fields (bid/ask/mark/etc.) with timestamps.@supabase/functions/options-quotes/index.ts#118-128
- **Destination & Egress:** Edge function streams normalized quotes back to caller; does not persist to database unless caller saves results.

Details: Normalizes contract casing, enforces max contract count, and shares CORS handlers for cross-origin access.@supabase/functions/options-quotes/index.ts#26-127

### run-backfill-worker (`supabase/functions/run-backfill-worker/index.ts`)
Function: Claims pending backfill chunks, fetches data via adapter, and upserts results into `ohlc_bars_v2`.@supabase/functions/run-backfill-worker/index.ts#24-158

Scripts:
- Uses RPC `claim_backfill_chunks` and `update_job_progress`, plus helper `fetchIntradayForDay` and `upsertBars` batching.@supabase/functions/run-backfill-worker/index.ts#39-161

Data input:
- No request payload; relies on env-specified Supabase credentials.@supabase/functions/run-backfill-worker/index.ts#34-38
- **Source & Ingress:** Triggered via POST (usually from `trigger-backfill` workflow/function); environment variables supply Supabase access keys for RPC calls.

Data output:
- JSON run summary (processed, succeeded, failed) and updated chunk/job statuses in Supabase tables.@supabase/functions/run-backfill-worker/index.ts#71-161
- **Destination & Egress:** Writes processed bars to `ohlc_bars_v2` via helper; updates `backfill_chunks`/`backfill_jobs`; summary returned to HTTP caller.

Details: Applies bounded parallelism, retries with status escalation, and chunked upserts to respect Supabase payload limits.@supabase/functions/run-backfill-worker/index.ts#62-158

### symbol-backfill (`supabase/functions/symbol-backfill/index.ts`)
Function: Deep Polygon-based backfill for symbols across configurable timeframes with optional force logic.@supabase/functions/symbol-backfill/index.ts#1-320

Scripts:
- Calls Polygon Aggregates API, transforms data, and upserts into `ohlc_bars_v2` using Supabase client utilities.@supabase/functions/symbol-backfill/index.ts#47-205

Data input:
- JSON `{ symbol, timeframes?, force? }`, defaulting to day/hour/week coverage.@supabase/functions/symbol-backfill/index.ts#26-245
- **Source & Ingress:** Authorized clients (e.g., workflows) post JSON payload specifying symbol/timeframes; function reads Supabase and Polygon credentials from environment.

Data output:
- Response includes per-timeframe bar counts and total inserted bars; Supabase tables receive new historical data.@supabase/functions/symbol-backfill/index.ts#206-314
- **Destination & Egress:** Inserts/updates `symbols` and `ohlc_bars_v2`; JSON summary returned to caller detailing inserted bars and durations.

Details: Creates symbol records if absent, throttles API calls to respect rate limits, and supports skip logic when coverage sufficient.@supabase/functions/symbol-backfill/index.ts#251-303

### sync-corporate-actions (`supabase/functions/sync-corporate-actions/index.ts`)
Function: Syncs corporate actions from Alpaca, stores them, and triggers split adjustments when needed.@supabase/functions/sync-corporate-actions/index.ts#8-107

Scripts:
- Fetches watchlist symbols, retrieves Alpaca corporate actions, upserts into `corporate_actions`, and invokes `adjust-bars-for-splits` on demand.@supabase/functions/sync-corporate-actions/index.ts#33-105

Data input:
- No external payload; uses Supabase and Alpaca credentials via environment.@supabase/functions/sync-corporate-actions/index.ts#10-29
- **Source & Ingress:** Invoked via scheduled workflow or manual call; credentials provisioned through function environment enabling Alpaca API access and Supabase writes.

Data output:
- JSON result with counts; database tables updated accordingly and split adjustments triggered through Supabase Functions.invoke.@supabase/functions/sync-corporate-actions/index.ts#55-105
- **Destination & Egress:** Upserts to `corporate_actions`; initiates `adjust-bars-for-splits` function; returns summary JSON to caller.

Details: Employs shared rate limiter/cache to respect provider quotas and iterates through current symbol universe for coverage.@supabase/functions/sync-corporate-actions/index.ts#15-93

### sync-market-calendar (`supabase/functions/sync-market-calendar/index.ts`)
Function: Loads next 30 days of market hours from Alpaca and upserts into `market_calendar`.@supabase/functions/sync-market-calendar/index.ts#8-73

Scripts:
- Leverages `MarketIntelligence` to fetch calendar data and uses Supabase client for bulk upserts.@supabase/functions/sync-market-calendar/index.ts#31-58

Data input:
- No payload; uses Alpaca credentials and Supabase service key.@supabase/functions/sync-market-calendar/index.ts#10-28
- **Source & Ingress:** Function executes with environment credentials to fetch Alpaca calendar data; typically invoked via scheduler.

Data output:
- Upserts daily session info and returns range metadata in JSON.@supabase/functions/sync-market-calendar/index.ts#43-71
- **Destination & Egress:** Writes to `market_calendar` table; responds with JSON summary of synced range to HTTP caller.

Details: Normalizes calendar entries for the next month with updated timestamps for downstream scheduling awareness.@supabase/functions/sync-market-calendar/index.ts#33-70

### trigger-backfill (`supabase/functions/trigger-backfill/index.ts`)
Function: Lightweight trigger that calls the `run-backfill-worker` edge function using service role credentials.@supabase/functions/trigger-backfill/index.ts#12-47

Scripts:
- Performs authenticated fetch to worker endpoint and returns success flag plus worker response.@supabase/functions/trigger-backfill/index.ts#24-47

Data input:
- No body required; relies on Supabase URL and service key env vars.@supabase/functions/trigger-backfill/index.ts#19-29
- **Source & Ingress:** Caller (cron/workflow) sends POST without payload; edge function loads service key from environment to invoke worker.

Data output:
- JSON containing worker response payload and timestamp for auditing.@supabase/functions/trigger-backfill/index.ts#38-47
- **Destination & Egress:** Forward call to `run-backfill-worker`; returns aggregated response to caller.

Details: Enables external schedulers (e.g., GitHub Actions) to securely start the worker without exposing service keys client-side.@supabase/functions/trigger-backfill/index.ts#1-49

### user-refresh (`supabase/functions/user-refresh/index.ts`)
Function: Comprehensive user-triggered refresh sequencing backfill checks, OHLC pulls, ML queues, option ranking, and S/R calculations.@supabase/functions/user-refresh/index.ts#49-399

Scripts:
- Uses Supabase queries to inspect coverage, queue backfills, enqueue jobs, and update support/resistance metadata.@supabase/functions/user-refresh/index.ts#125-373
- Provider router fetches latest bars across multiple timeframes per symbol.@supabase/functions/user-refresh/index.ts#193-239

Data input:
- JSON `{ symbol }` from caller; environment supplies Supabase credentials.@supabase/functions/user-refresh/index.ts#23-76
- **Source & Ingress:** Client apps or workflows post symbol payload; function reads Supabase credentials and provider API keys from environment.

Data output:
- JSON response summarizing step outcomes and totals (bars updated, jobs queued, etc.).@supabase/functions/user-refresh/index.ts#333-420
- Supabase tables updated: `symbol_backfill_queue`, `ohlc_bars_v2`, `job_queue`, `ml_forecasts`, among others.@supabase/functions/user-refresh/index.ts#137-365
- **Destination & Egress:** Multiple Supabase tables updated via service-role client; final status JSON returned to caller detailing downstream effects.

Details: Implements step-wise status tracking, skipping redundant work when coverage sufficient, and records high-priority jobs for downstream workers.@supabase/functions/user-refresh/index.ts#125-399
