# Supabase Database Blueprint

This reference compiles the major Supabase tables, views, and helper functions that power SwiftBolt ML. Each section captures the intent of the data pool, the most important columns (with types), notable constraints or triggers, access policies, and representative sample rows so future work can follow established patterns.

---

## Core Market Data Domain

### `symbols`
- **Purpose:** Master catalog of tradable instruments across asset classes.@backend/supabase/migrations/001_core_schema.sql#25-37
- **Key Columns:**
  | Column | Type | Notes |
  | --- | --- | --- |
  | `id` | `UUID` | Primary key via `gen_random_uuid()` |
  | `ticker` | `TEXT` | Unique exchange ticker (e.g., `AAPL`) |
  | `asset_type` | `asset_type` enum | `stock`, `future`, `option`, `crypto` |
  | `primary_source` | `data_provider` enum | Defaults to `finnhub` |
  | `description` | `TEXT` | Optional label |
  | `created_at` / `updated_at` | `TIMESTAMPTZ` | Auto-managed timestamp pair |
- **Indexes:** Symbol and asset-type search acceleration via `idx_symbols_ticker`, `idx_symbols_asset_type`.@backend/supabase/migrations/001_core_schema.sql#35-36
- **Security:** RLS enabled; authenticated users have read access, service role can perform all operations.@backend/supabase/migrations/001_core_schema.sql#184-303
- **Sample Row:**
  ```json
  {
    "id": "7a3f2be2-1e5d-4bcb-9c35-7dcb91f1c201",
    "ticker": "NVDA",
    "asset_type": "stock",
    "primary_source": "finnhub",
    "created_at": "2025-12-01T15:45:10Z",
    "updated_at": "2025-12-05T09:21:44Z"
  }
  ```

### `ohlc_bars`
- **Purpose:** Legacy daily/weekly OHLCV repository retained for backward compatibility projects.@backend/supabase/migrations/001_core_schema.sql#41-58
- **Highlights:**
  - Enforces uniqueness on `(symbol_id, timeframe, ts)`.
  - Stores provider origin (`finnhub`/`massive`) and raw OHLCV decimals.
- **Usage Tip:** New implementations should prefer `ohlc_bars_v2`, but this table remains useful for historical validation.

### `quotes`
- **Purpose:** Latest quote snapshot per symbol, providing intraday reference data.@backend/supabase/migrations/001_core_schema.sql#63-75
- **Notable Fields:** `last`, `bid`, `ask`, day high/low, `prev_close`; `updated_at` auto-refreshes via trigger.@backend/supabase/migrations/001_core_schema.sql#364-367

### `news_items`
- **Purpose:** Cached news articles linked to individual symbols or the broader market.@backend/supabase/migrations/001_core_schema.sql#166-178
- **Columns:** `title`, `source`, `url`, `summary`, `published_at`, `fetched_at`.
- **Access:** Authenticated users can read all records, reflecting public news availability.@backend/supabase/migrations/001_core_schema.sql#225-228

---

## Layered Price Data

### `ohlc_bars_v2`
- **Purpose:** Unified OHLCV store that segregates historical (Polygon), intraday (Tradier), and forecast layers.@backend/supabase/migrations/20260105000000_ohlc_bars_v2.sql#5-207
- **Key Columns:**
  | Column | Type | Description |
  | --- | --- | --- |
  | `symbol_id` | `UUID` | FK → `symbols` |
  | `timeframe` | `VARCHAR(10)` | Flexible granularity (`m15`, `h1`, `d1`, etc.) |
  | `ts` | `TIMESTAMP` | Bar boundary |
  | `open/high/low/close` | `DECIMAL(10,4)` | Price points |
  | `volume` | `BIGINT` | Trade volume |
  | `provider` | `VARCHAR(20)` | `polygon`, `tradier`, `ml_forecast` |
  | `is_intraday` | `BOOLEAN` | True for real-time data |
  | `is_forecast` | `BOOLEAN` | True for ML projections |
  | `data_status` | `VARCHAR(20)` | `verified`, `live`, `provisional` |
  | `confidence_score/upper_band/lower_band` | Forecast metadata |
- **Constraints & Triggers:** Unique per `(symbol_id, timeframe, ts, provider, is_forecast)` plus validation trigger `validate_ohlc_v2_write()` enforcing date boundaries (historical < today, intraday = today, forecasts > today).@backend/supabase/migrations/20260105000000_ohlc_bars_v2.sql#34-115
- **Helper Function:** `get_chart_data_v2` returns consistent chart-ready series filtered by provider rules.@backend/supabase/migrations/20260105000000_ohlc_bars_v2.sql#117-173
- **Sample Rows:**
  ```
  ┌──────────┬─────┬────────────────────┬────────┬────────┬────────┬────────┬─────────┬─────────────┬─────────────┬──────────────┐
  │ provider │ tf  │ ts                 │ open   │ high   │ low    │ close  │ volume  │ is_intraday │ is_forecast │ data_status  │
  ├──────────┼─────┼────────────────────┼────────┼────────┼────────┼────────┼─────────┼─────────────┼─────────────┼──────────────┤
  │ polygon  │ d1  │ 2025-12-30 00:00Z  │ 700.12 │ 712.25 │ 698.01 │ 710.44 │ 24551000│ false       │ false       │ verified     │
  │ tradier  │ m15 │ 2026-01-10 15:15Z  │ 712.10 │ 713.88 │ 711.32 │ 713.45 │   152430│ true        │ false       │ live         │
  │ ml_forecast │ d1 │ 2026-01-15 00:00Z│ 718.00 │ 728.50 │ 715.10 │ 725.40 │      null│ false       │ true        │ provisional  │
  ```

### `intraday_bars`
- **Purpose:** High-frequency (1m/5m/15m) OHLCV table optimized for real-time analytics and aggregation.@backend/supabase/migrations/20251227140000_intraday_bars.sql#5-150
- **Highlights:**
  - Unique constraint on `(symbol_id, timeframe, ts)` for safe upserts.
  - Helper functions `get_latest_intraday_bar` and `aggregate_intraday_to_daily` supply derived metrics, while `cleanup_old_intraday_bars` prunes data older than 30 days.@backend/supabase/migrations/20251227140000_intraday_bars.sql#45-122
  - View `intraday_daily_summary` summarizes current-day performance per symbol for dashboards.@backend/supabase/migrations/20251227140000_intraday_bars.sql#124-138
- **Sample Record:**
  ```json
  {
    "symbol_id": "5fd8...",
    "timeframe": "5m",
    "ts": "2026-01-10T15:35:00Z",
    "open": 238.15,
    "high": 238.90,
    "low": 237.80,
    "close": 238.44,
    "volume": 185432,
    "vwap": 238.12
  }
  ```

### `intraday_backfill_status`
- **Purpose:** Tracks intraday backfill progress per symbol to avoid duplicate processing.@backend/supabase/migrations/20260106120100_intraday_backfill_tracking.sql#4-120
- **Fields:** `last_backfill_at`, `backfill_days`, `bar_count`, `status`, `error_message`.
- **Automation:** Functions `needs_intraday_backfill`, `mark_backfill_started`, `mark_backfill_completed`, and `mark_backfill_failed` orchestrate lifecycle updates for scheduler or worker logic.@backend/supabase/migrations/20260106120100_intraday_backfill_tracking.sql#21-113

---

## Forecasting & Analytics Domain

### `ml_forecasts`
- **Purpose:** Stores model predictions along with summary label, confidence score, and path projections for chart overlays.@backend/supabase/migrations/001_core_schema.sql#80-94
- **Key Attributes:**
  - `overall_label` enum (`bullish`, `neutral`, `bearish`).
  - `confidence` bounded between 0 and 1.
  - `points` JSON array recording time/value bounds for future projections.
- **Sample `points` Element:**
  ```json
  {
    "ts": "2026-01-12T00:00:00Z",
    "value": 1.042,
    "lower": 0.98,
    "upper": 1.09
  }
  ```

### `ranking_evaluations`
- **Purpose:** Daily health metrics for the options ranking pipeline, covering IC behaviour, hit rates, leakage detection, and regime context.@backend/supabase/migrations/20260103130000_ranking_evaluations.sql#5-158
- **Key Columns:** Sample sizes (`n_days`, `n_contracts`), IC stats (`mean_ic`, `ic_trend`), calibration metrics, alert flags.
- **Functions:**
  - `get_ranking_health(symbol_id)` surfaces the latest evaluation per symbol for dashboards.@backend/supabase/migrations/20260103130000_ranking_evaluations.sql#88-114
  - `check_ranking_ic_collapse()` identifies degrading IC trends for alerting.@backend/supabase/migrations/20260103130000_ranking_evaluations.sql#117-157

### `options_ranks`
- **Purpose:** Ranked options contracts produced by ML pipeline including Greeks, open interest, and ML scores.@backend/supabase/migrations/001_core_schema.sql#99-119
- **Constraints:** Unique per `(underlying_symbol_id, expiry, strike, side)` to track the latest scored contract.
- **Sample Row:**
  ```json
  {
    "underlying_symbol_id": "9bf3...",
    "expiry": "2026-01-17",
    "strike": 750.0,
    "side": "call",
    "ml_score": 0.78,
    "implied_vol": 0.45,
    "delta": 0.32,
    "run_at": "2026-01-10T04:05:00Z"
  }
  ```

### `ranking_jobs`
- **Purpose:** Lightweight job queue that feeds ranking workers with pending tasks and retry metadata.@backend/supabase/migrations/20251217020000_ranking_job_queue.sql#13-113
- **Columns:** `status`, `retry_count`, `priority`, timestamps, optional `requested_by`.
- **Processing Functions:** `get_next_ranking_job`, `complete_ranking_job`, `fail_ranking_job`, and `cleanup_old_ranking_jobs` manage leasing and lifecycle updates.@backend/supabase/migrations/20251217020000_ranking_job_queue.sql#35-112

---

## Options Data Domain

### `options_snapshots`
- **Purpose:** Historical options chain captures with Greeks, IV, and volume metrics, populated by scraping providers like Tradier.@backend/supabase/migrations/20251227110000_options_snapshots.sql#6-160
- **Key Fields:** `contract_symbol`, `option_type`, `strike`, `expiration`, `bid/ask/last`, `underlying_price`, `volume`, `open_interest`, full set of Greeks.
- **Views & Functions:**
  - `latest_options` view returns the freshest snapshot per contract for quick lookup.@backend/supabase/migrations/20251227110000_options_snapshots.sql#65-71
  - `get_options_chain_at(symbol, time)` and `get_option_history(contract, days)` support temporal analysis workflows.@backend/supabase/migrations/20251227110000_options_snapshots.sql#74-156

### `options_price_history`
- **Purpose:** Denser time-series history for selected contracts including mark price, Greeks, IV, and optional ML score references.@backend/supabase/migrations/20251217030000_options_price_history.sql#6-243
- **Indexes:** Multiple composites optimize strike/expiry queries and recency filters.@backend/supabase/migrations/20251217030000_options_price_history.sql#41-52
- **Utilities:**
  - `capture_options_snapshot(symbol_id)` snapshots current `options_ranks` output into the history table.@backend/supabase/migrations/20251217030000_options_price_history.sql#92-149
  - `get_strike_price_comparison` compares current vs historical averages across expirations.@backend/supabase/migrations/20251217030000_options_price_history.sql#152-218
  - `cleanup_old_price_history` prunes data older than 90 days.@backend/supabase/migrations/20251217030000_options_price_history.sql#221-236

---

## Orchestration & Coverage Domain

### `job_definitions`, `job_runs`, `coverage_status`
- **Purpose:** Unified orchestrator metadata (SPEC-8) used to manage market data workflows, slice tracking, and coverage analytics.@backend/supabase/migrations/20260107000000_spec8_unified_orchestrator.sql#5-211
- **`job_definitions`:** Templates describing symbol/timeframe jobs with priority, default window, and enablement flags.
- **`job_runs`:** Execution audit log capturing status (`queued`, `running`, `success`, `failed`, `cancelled`), attempt count, provider, slices, and errors. Includes trigger-generated `idx_hash` to deduplicate slices.@backend/supabase/migrations/20260107000000_spec8_unified_orchestrator.sql#21-113
- **`coverage_status`:** Aggregates last-success metadata and window coverage (`from_ts`, `to_ts`, `last_provider`) per symbol/timeframe pair.@backend/supabase/migrations/20260107000000_spec8_unified_orchestrator.sql#50-63
- **Supporting Logic:**
  - Trigger `trigger_update_coverage_status` refreshes coverage upon successful run completion.@backend/supabase/migrations/20260107000000_spec8_unified_orchestrator.sql#115-139
  - Function `get_coverage_gaps(symbol, timeframe, window_days)` highlights missing slices for remediation.@backend/supabase/migrations/20260107000000_spec8_unified_orchestrator.sql#141-179
- **Realtime:** `job_runs` are added to Supabase Realtime publication to power live dashboards and notifications.@backend/supabase/migrations/20260107000000_spec8_unified_orchestrator.sql#66-94

---

## Market Intelligence Domain

### `market_calendar`
- **Purpose:** Local cache of trading day metadata (holiday flags, session windows) for quick availability checks.@supabase/migrations/20260110_140000_market_intelligence.sql#5-17
- **Columns:** `date` (PK), `is_open`, `session_open/close`, `market_open/close`, `created_at`, `updated_at`.
- **Functions:**
  - `is_market_open(date)` determines live open/close status relative to stored times.@supabase/migrations/20260110_140000_market_intelligence.sql#51-70
  - `next_trading_day(from_date)` returns the next open session for scheduling.@supabase/migrations/20260110_140000_market_intelligence.sql#72-81
  - `market_calendar_coverage` view rolls data up by month with open/closed counts for monitoring.@supabase/migrations/20260110_141000_market_intelligence_dashboard.sql#69-80

### `corporate_actions`
- **Purpose:** Registry of splits, dividends, mergers, and adjustment status, keyed by symbol and ex-date.@supabase/migrations/20260110_140000_market_intelligence.sql#19-118
- **Key Fields:** `action_type`, `ex_date`, `ratio`, `cash_amount`, `bars_adjusted`, `adjusted_at`, `metadata` JSON.
- **Indexes:** optimize symbol lookups, ex-date ranges, and outstanding adjustments (`bars_adjusted = false`).@supabase/migrations/20260110_140000_market_intelligence.sql#46-48
- **Helper Functions:**
  - `get_pending_adjustments` returns outstanding splits alongside counts of affected bars.@supabase/migrations/20260110_140000_market_intelligence.sql#83-104
  - `has_pending_splits(symbol)` boolean helper for UI/tooling flows.@supabase/migrations/20260110_140000_market_intelligence.sql#107-117
- **Views & Health Checks:**
  - `market_intelligence_dashboard` compiles high-level KPIs (market status, pending splits, calendar cache depth, unadjusted bars).@supabase/migrations/20260110_141000_market_intelligence_dashboard.sql#5-48
  - `corporate_actions_summary` details adjusted vs unadjusted bar counts per action.@supabase/migrations/20260110_141000_market_intelligence_dashboard.sql#51-67
  - `get_market_intelligence_health()` produces JSONB health summaries for monitoring surfaces.@supabase/migrations/20260110_141000_market_intelligence_dashboard.sql#82-159
- **Sample Action:**
  ```json
  {
    "symbol": "AAPL",
    "action_type": "stock_split",
    "ex_date": "2026-02-01",
    "ratio": 4,
    "bars_adjusted": false,
    "metadata": { "old_rate": 1, "new_rate": 4 }
  }
  ```

---

## Watchlist & User-Facing Domain

### `watchlists` & `watchlist_items`
- **Purpose:** User-configurable symbol groups for interface personalization.@backend/supabase/migrations/001_core_schema.sql#123-143
- **Structure:**
  - `watchlists` captures `user_id`, `name`, timestamps.
  - `watchlist_items` is a many-to-many join storing `added_at` per symbol.
- **Security:** Strict RLS ensures users only manage their own watchlists; service role bypasses restrictions for backend automations.@backend/supabase/migrations/001_core_schema.sql#235-282

### `scanner_alerts`
- **Purpose:** Tracks triggered market conditions (with optional severity) per user or globally.@backend/supabase/migrations/001_core_schema.sql#148-161
- **Policies:** Authenticated users read/dismiss their alerts; service role writes new alerts or updates state transitions.@backend/supabase/migrations/001_core_schema.sql#284-338

---

## Access & Governance Summary

- **Row-Level Security:** Enabled for most user-facing tables to protect per-user data while allowing authenticated read access to public market data.@backend/supabase/migrations/001_core_schema.sql#181-338
- **Realtime:** `job_runs` is subscribed via Supabase Realtime to broadcast orchestrator state for UI and alerting layers.@backend/supabase/migrations/20260107000000_spec8_unified_orchestrator.sql#66-94
- **Sequences:** Tables such as `ohlc_bars_v2` grant sequence usage to authenticated and service roles to support insert operations from Edge Functions.@backend/supabase/migrations/20260105000000_ohlc_bars_v2.sql#195-199

---

## Quick Reference: Common Functions & Usage Patterns

| Function | Purpose | Reference |
| --- | --- | --- |
| `get_chart_data_v2(symbol_id, timeframe, start, end)` | Returns provider-aware OHLC bars for chart rendering | @backend/supabase/migrations/20260105000000_ohlc_bars_v2.sql#117-173 |
| `aggregate_intraday_to_daily(symbol_id, date)` | Rolls aggregated 5m bars into daily summary | @backend/supabase/migrations/20251227140000_intraday_bars.sql#69-104 |
| `needs_intraday_backfill(symbol_id)` | Signals whether a symbol requires new intraday backfill | @backend/supabase/migrations/20260106120100_intraday_backfill_tracking.sql#21-60 |
| `get_ranking_health(symbol_id)` | Retrieves latest ranking evaluation health snapshot | @backend/supabase/migrations/20260103130000_ranking_evaluations.sql#88-114 |
| `get_options_chain_at(symbol, time)` | Returns best snapshot for each contract at/before a timestamp | @backend/supabase/migrations/20251227110000_options_snapshots.sql#74-119 |
| `capture_options_snapshot(symbol_id)` | Copies current ranked contracts into historical pricing table | @backend/supabase/migrations/20251217030000_options_price_history.sql#92-149 |
| `get_coverage_gaps(symbol, timeframe, window_days)` | Surfaces missing data ranges for orchestrator remediation | @backend/supabase/migrations/20260107000000_spec8_unified_orchestrator.sql#141-179 |
| `get_market_intelligence_health()` | Produces JSONB health components (calendar coverage, adjustments, data quality) | @supabase/migrations/20260110_141000_market_intelligence_dashboard.sql#82-159 |

---

## Usage Guidance & Next Steps

1. **Schema-first Validation:** When introducing new data flows, align column types and provider flags with existing tables (e.g., match `provider` enumerations in `ohlc_bars_v2`).
2. **Respect Layer Separation:** Historical, intraday, and forecast improvements should honor validation rules to avoid cross-layer contamination.
3. **RLS Awareness:** Client-facing features should authenticate via Supabase auth and rely on policies; service role credentials are reserved for backend pipelines.
4. **Monitoring Hooks:** Leverage orchestrator tables and market intelligence views for dashboards and health checks before triggering heavy jobs.
5. **Documentation Maintenance:** Update `databasesummary.md` after new migrations land to keep this blueprint authoritative.
