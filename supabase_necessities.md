# Supabase Necessities (SwiftBoltML)

This document is the **minimum Supabase schema + Edge Functions + Storage** that the SwiftBoltML app expects in order to function.

**Source of truth for this doc**
- **DB schema:** `/backend/supabase/migrations/*.sql` (plus `/supabase/migrations/*.sql` for market-intelligence/dashboard)
- **Runtime usage:** Edge Functions in `/backend/supabase/functions/*` and `/supabase/functions/*`, and the macOS client in `/client-macos/SwiftBoltML/*`

> Note: I could not introspect the live Supabase project because the Supabase MCP server requires `SUPABASE_ACCESS_TOKEN`. This doc is derived from repo migrations + code references.

---

## Project / Connection
- **Supabase project_id:** `cygflaemtmwiwaviclks` (see `/backend/supabase/config.toml`)
- **Client uses:**
  - `https://cygflaemtmwiwaviclks.supabase.co`
  - `Authorization: Bearer <anon key>` for most Edge Function calls

---

## Timeframes (hard requirement)
The app and backfill/orchestration assume a consistent set of timeframes:
- `m15`
- `h1`
- `h4`
- `d1`
- `w1`

---

## Required Edge Functions
These are referenced directly by the macOS app and/or used for background processing.

### macOS client calls (must exist)
- `quotes`
- `symbols-search`
- `chart` (legacy consolidated endpoint)
- `chart-data-v2` (primary chart endpoint)
- `news`
- `options-chain`
- `options-rankings`
- `options-quotes`
- `scanner-watchlist`
- `trigger-ranking-job`
- `enhanced-prediction`
- `refresh-data`
- `user-refresh`
- `data-health`
- `market-status`
- `symbol-backfill`
- `sync-user-symbols`
- `reload-watchlist-data`

### internal / scheduled / ops
- `orchestrator`
- `fetch-bars`, `fetch-bars-batch`
- `backfill-intraday-worker`
- `run-backfill-worker`
- `ensure-coverage` (present, but macOS feature-flagged off)
- `watchlist-sync`
- `options-scrape`
- `seed-symbols`
- `symbol-init`
- `sync-corporate-actions`
- `adjust-bars-for-splits`
- `sync-market-calendar`
- `apply-rls-fix`
- `test-schema`

> Inventory sources:
> - `/backend/supabase/functions/*`
> - `/supabase/functions/*`

---

## Required Storage buckets
Defined in `/backend/supabase/migrations/20251227170000_storage_buckets.sql`.

- **Bucket:** `ml-artifacts`
  - **public:** false
  - **intended use:** trained models / scalers / metadata
  - **access:** service role only

- **Bucket:** `charts`
  - **public:** true
  - **intended use:** exported chart images
  - **access:** public read, authenticated insert/delete by user folder, service_role full

- **Bucket:** `reports`
  - **public:** false
  - **intended use:** generated reports
  - **access:** authenticated read their own folder, service_role full

Helper RPCs:
- `generate_user_storage_path(p_bucket, p_user_id, p_filename) -> text`
- `generate_public_storage_path(p_bucket, p_filename) -> text`

Verification SQL (buckets + RLS policies present):

```sql
-- Verify buckets exist
SELECT id, name, public, file_size_limit, allowed_mime_types
FROM storage.buckets
WHERE id IN ('ml-artifacts', 'charts', 'reports')
ORDER BY id;

-- Verify policy names exist on storage.objects
SELECT pol.polname AS policy_name
FROM pg_policy pol
JOIN pg_class c ON c.oid = pol.polrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'storage' AND c.relname = 'objects'
  AND pol.polname IN (
    'ml_artifacts_service_role_all',
    'charts_public_read',
    'charts_service_role_all',
    'charts_authenticated_insert',
    'charts_authenticated_delete',
    'reports_user_read',
    'reports_service_role_all'
  )
ORDER BY pol.polname;
```

---

## Database schema necessities (tables + columns)

### Core market entities

#### `symbols`
Created in `001_core_schema.sql`.
- `id uuid PK`
- `ticker text unique not null`
- `asset_type` (enum)
- `description text`
- `primary_source` (enum)
- `created_at timestamptz`
- `updated_at timestamptz`

**Important:** later migration disables RLS on `symbols` (`20260110000000_add_alpaca_provider_support.sql`).

#### `ohlc_bars` (legacy)
Created in `001_core_schema.sql`.
- `id bigserial PK`
- `symbol_id uuid FK symbols(id)`
- `timeframe` (enum)
- `ts timestamptz`
- `open/high/low/close numeric`
- `volume numeric`
- `provider` (enum)
- `created_at timestamptz`

#### `ohlc_bars_v2` (primary bars table)
Created in `20260105000000_ohlc_bars_v2.sql` (and heavily evolved later).
- `id bigserial PK`
- `symbol_id uuid FK symbols(id)`
- `timeframe varchar(10)`
- `ts timestamp`
- `open/high/low/close decimal`
- `volume bigint`
- `provider varchar(20)`
- `is_intraday boolean`
- `is_forecast boolean`
- `data_status varchar(20)`
- `fetched_at timestamp`
- `created_at timestamp`
- `updated_at timestamp`
- `confidence_score decimal(3,2)`
- `upper_band decimal(10,4)`
- `lower_band decimal(10,4)`

Uniqueness / upsert key expected by code:
- `UNIQUE(symbol_id, timeframe, ts, provider, is_forecast)`

#### `quotes`
Created in `001_core_schema.sql`.
- `symbol_id uuid PK/FK symbols(id)`
- `ts timestamptz`
- `last/bid/ask/day_high/day_low/prev_close numeric`
- `updated_at timestamptz`

### ML forecasts (daily + intraday)

#### `ml_forecasts`
Created in `001_core_schema.sql` (later enhanced).
- `id uuid PK`
- `symbol_id uuid FK symbols(id)`
- `horizon text`
- `overall_label` (enum)
- `confidence numeric`
- `run_at timestamptz`
- `points jsonb` (default `[]`)
- `created_at timestamptz`

#### `ml_forecasts_intraday`
Created in `20260104200000_intraday_calibration.sql`.
(Used by `chart-data-v2` for intraday forecast display.)

#### `ml_forecast_paths_intraday`
Created in `20260111223000_intraday_forecast_paths.sql`.
- `id uuid PK`
- `symbol_id uuid FK symbols(id)`
- `symbol varchar(20)`
- `timeframe varchar(10)`
- `horizon varchar(10)`
- `steps int`
- `interval_sec int`
- `overall_label varchar(20)`
- `confidence numeric(5,4)`
- `model_type varchar(50)`
- `points jsonb`
- `created_at timestamptz`
- `expires_at timestamptz`

#### dataset-first ML tables (new pipeline)
Created in `20260113000000_dataset_first_schema.sql`:
- `ingestion_runs`
- `bar_datasets`
- `feature_sets`
- `feature_rows`
- `forecast_runs`
- `forecast_points`

These support a “dataset first” pipeline and are expected for forward development.

### Options data

#### `options_ranks`
Created in `001_core_schema.sql`.
- `id uuid PK`
- `underlying_symbol_id uuid FK symbols(id)`
- `expiry date`
- `strike numeric`
- `side option_side`
- `ml_score numeric`
- `implied_vol/delta/gamma numeric`
- `open_interest int`
- `volume int`
- `run_at timestamptz`
- `created_at timestamptz`

#### `options_snapshots`
Created in `20251227110000_options_snapshots.sql`.
- `id uuid PK`
- `underlying_symbol_id uuid FK symbols(id)`
- `contract_symbol text`
- `option_type text (call|put)`
- `strike numeric(12,2)`
- `expiration date`
- `bid/ask/last/underlying_price`
- `volume/open_interest`
- `delta/gamma/theta/vega/rho/iv`
- `snapshot_time timestamptz`
- `created_at timestamptz`

#### `options_price_history`
Created in `20251217030000_options_price_history.sql`.
- `id uuid PK`
- `underlying_symbol_id uuid`
- `contract_symbol text`
- `expiry date`
- `strike numeric`
- `side text (call|put)`
- `bid/ask/mark/last_price`
- `delta/gamma/theta/vega/rho/implied_vol`
- `volume/open_interest`
- `ml_score`
- `snapshot_at timestamptz`
- `created_at timestamptz`

#### `options_chain_snapshots`
Created in `20251219120000_watchlist_limits_and_helpers.sql`.
Used for nightly options chain capture.

#### options scraping / job tracking
- `options_scrape_jobs` (`20251227120000_options_scraping_cron.sql`)
- `options_backfill_jobs` (`20251222180000_watchlist_options_trigger.sql`)

### Watchlists + tracking

#### `watchlists` and `watchlist_items`
Created in `001_core_schema.sql`.

#### `user_symbol_tracking`
Created in `20260110000000_multi_timeframe_symbol_tracking.sql`.
- `id uuid PK`
- `user_id uuid FK auth.users(id)`
- `symbol_id uuid FK symbols(id)`
- `source text (watchlist|recent_search|chart_view)`
- `priority int`
- `created_at/updated_at timestamptz`

### Job/orchestration systems

#### SPEC-8 orchestrator tables
Created in `20260107000000_spec8_unified_orchestrator.sql`.
- `job_definitions`
- `job_runs`
- `coverage_status`

#### backfill orchestration tables (legacy/spec8)
Created in `20260106180000_backfill_orchestration.sql`:
- `backfill_jobs`
- `backfill_chunks`

Enhanced in `20260109040000_comprehensive_intraday_backfill.sql`:
- adds `backfill_chunks.symbol_id` if missing
- adds `claim_backfill_chunk()` RPC

**Note:** Edge Functions reference both `claim_backfill_chunks()` and `claim_backfill_chunk()`.

#### `intraday_backfill_status`
Created in `20260106120100_intraday_backfill_tracking.sql`.
Used by `intraday-update` via:
- `needs_intraday_backfill()`
- `mark_backfill_started()`
- `mark_backfill_completed()`
- `mark_backfill_failed()`

#### `job_queue`
Created in `20251221000000_job_queue.sql`.
Used by `symbol-init`.

#### ranking + forecast job queues
- `ranking_jobs` (`20251217020000_ranking_job_queue.sql`)
- `forecast_jobs` (`20251217030100_watchlist_automation.sql`)

### Monitoring / performance / infra tables

#### distributed rate limiting
Created in `20260109000000_polygon_rate_limit_optimization.sql`:
- `rate_buckets`
- `provider_checkpoints`

#### retention policy metadata
Created in `20251227100000_database_optimizations.sql`:
- `retention_policies`

### Additional market intelligence / indicators
(These are referenced by migrations and/or used for advanced features.)
- `ml_features` (`20251219190000_ml_features_and_enhancements.sql`)
- `iv_history` (`20251227160000_iv_history_and_momentum.sql`)
- `supertrend_signals` (`20251220100000_supertrend_ai_fields.sql`)
- support/resistance tables (`20251224060000_support_resistance_levels.sql`)
- GA optimization tables (`20251230100000_ga_strategy_params.sql`)
- ranking evaluations (`20260103130000_ranking_evaluations.sql`)

---

## Required Postgres functions (RPCs)
This is the set of RPCs *observed in code usage* and/or *defined in migrations*.

### Charting
- `get_chart_data_v2_dynamic(p_symbol_id, p_timeframe, p_max_bars, p_include_forecast)`
- `get_chart_data_v2(p_symbol_id, p_timeframe, p_start_date, p_end_date)`

### Coverage / orchestration
- `get_coverage(p_symbol, p_timeframe)`
- `get_coverage_gaps(p_symbol, p_timeframe, p_window_days)`
- `claim_queued_job()`

### Backfill (legacy/spec8)
- `claim_backfill_chunks(p_limit)`
- `update_job_progress()`
- `claim_backfill_chunk(p_limit)`

### Watchlist helpers
- `get_all_watchlist_symbols(p_limit)`
- `seed_job_definition_for_symbol(p_symbol_id, p_timeframes)`
- `get_symbol_job_status(p_ticker)`
- `request_symbol_job_definition(p_ticker, p_timeframes)`

### Options
- `get_strike_price_comparison(p_symbol_id, p_strike, p_side, p_lookback_days)`
- `get_forecast_for_options(p_symbol, p_horizon)`

### ML monitoring / evaluation
- `get_ml_dashboard()`
- `get_pending_evaluations(p_horizon)`
- `get_horizon_accuracy()`
- `trigger_weight_update()`

### Intraday backfill tracking
- `needs_intraday_backfill(p_symbol_id)`
- `mark_backfill_started(p_symbol_id)`
- `mark_backfill_completed(p_symbol_id, p_bar_count, p_backfill_days)`
- `mark_backfill_failed(p_symbol_id, p_error_message)`

### Data QA / gap detection
- `detect_ohlc_gaps(p_symbol, p_timeframe, p_max_gap_hours)`
- `get_ohlc_coverage_stats(p_symbol, p_timeframe)`

### Rate limiter
- `take_token(p_provider, p_cost)`
- `get_token_status(p_provider)`

### Legacy job queue
- `claim_next_job(p_job_type)`
- `complete_job(p_job_id, p_success, p_error)`

---

## Extensions / schemas expected
Found in migrations:
- `pg_cron`
- `pg_stat_statements`
- `pgmq` (schema `pgmq`)

---

## Known mismatches / TODOs (must reconcile)
These were found by comparing migrations vs code references.

- **`get_symbol_ohlc_averages` RPC**
  - Referenced by `watchlist-sync` Edge Function.
  - **Not found in migrations**. Add migration or remove call.

- **`corporate_actions` table**
  - Referenced by `sync-corporate-actions` and `adjust-bars-for-splits`.
  - **Not found in migrations**. Add migration.

- **`market_calendar` table**
  - Referenced by `sync-market-calendar`.
  - **Not found in migrations**. Add migration.

- **`is_market_open` RPC**
  - Referenced by `chart` and `data-health`.
  - **Not found in migrations**. Add migration or remove fallback reliance.

- **`exec_sql` RPC**
  - Referenced by `test-schema`, `apply-h1-fix`.
  - **Not found in migrations**. (Often implemented as a SECURITY DEFINER helper for admin-only operations.)

- **Backfill chunk status vocabulary mismatch**
  - Some code uses `completed/in_progress`, some migrations use `done/running`.
  - Normalize `backfill_chunks.status` and `backfill_jobs.status` values and update code accordingly.

- **Legacy backfill RPC replaced**
  - macOS client calls `request_symbol_backfill` / `get_symbol_backfill_status` (via Supabase Swift RPC).
  - Migration `20260110120000_fix_watchlist_backfill_for_new_schema.sql` **drops those** and replaces with:
    - `request_symbol_job_definition`
    - `get_symbol_job_status`
  - Either update the macOS client or reintroduce compatibility wrappers.

---

## Quick checklist (deployment readiness)
- [ ] Apply all SQL migrations in `/backend/supabase/migrations` in order
- [ ] Apply `storage_buckets` migration (creates buckets + policies)
- [ ] Deploy all Edge Functions (both `/backend/supabase/functions/*` and `/supabase/functions/*` if both are used)
- [ ] Ensure `app.supabase_url` and `app.supabase_service_role_key` settings exist if using `pg_cron` → `net.http_post` orchestrator pattern
- [ ] Resolve **Known mismatches / TODOs** above
