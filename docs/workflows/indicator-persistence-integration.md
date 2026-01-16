---
description: Indicator persistence integration plan
---

# Indicator Persistence Integration Plan

Comprehensive checklist for persisting chart indicator outputs from SwiftBoltML into Supabase so ML forecasting jobs can reuse the history.

## 1. Prerequisites
- Supabase project `swiftbolt_db` available and healthy.
- Access to run SQL migrations and deploy edge functions.
- ML stack configured with access to `ml/src` jobs and Supabase service key.
- macOS client build environment ready for SwiftBoltML app updates.

## 2. Database & Schema Work
1. **Create `indicator_values` table** (relational per-candle storage):
   ```sql
   create table public.indicator_values (
       id bigint generated always as identity primary key,
       symbol_id uuid references public.symbols(id) on delete cascade,
       timeframe text not null check (timeframe in ('m15','h1','h4','d1','w1')),
       ts timestamptz not null,
       open numeric(18,6),
       high numeric(18,6),
       low numeric(18,6),
       close numeric(18,6),
       volume numeric(18,6),
       rsi numeric(10,4),
       macd numeric(10,4),
       macd_signal numeric(10,4),
       macd_hist numeric(10,4),
       supertrend numeric(18,6),
       supertrend_trend int,
       supertrend_factor numeric(10,4),
       nearest_support numeric(18,6),
       nearest_resistance numeric(18,6),
       support_distance_pct numeric(6,3),
       resistance_distance_pct numeric(6,3),
       metadata jsonb default '{}'::jsonb,
       created_at timestamptz default now(),
       unique(symbol_id, timeframe, ts)
   );
   
   create index idx_indicator_values_symbol_tf_ts on public.indicator_values(symbol_id, timeframe, ts desc);
   ```
2. **Enable Row-Level Security** to mirror current chart access:
   ```sql
   alter table public.indicator_values enable row level security;
   create policy "read indicators" on public.indicator_values for select using (true);
   create policy "service writes indicators" on public.indicator_values for all using (auth.role() = 'service_role');
   ```
3. **Leverage existing S/R tables**: ensure `sr_levels` and `sr_level_history` migrations are applied (see @backend/supabase/migrations/20251224060000_support_resistance_levels.sql#1-255).
4. Optional: turn `indicator_values` into a Timescale hypertable if historic retention grows >10M rows.

## 3. Backend Job Updates (Python)
1. **Extend Supabase DB helper**:
   - Add `save_indicator_snapshot` & `save_sr_snapshot` helpers inside `SupabaseDB` @ml/src/data/supabase_db.py#302-383. Each helper should upsert into `indicator_values` (and optionally `sr_levels`).
2. **Modify forecast jobs**:
   - `forecast_job.py`: after calculating indicator bundles (e.g., `sr_levels`, SuperTrend, RSI), call the new helper for each timeframe processed @ml/src/forecast_job.py#744-1139.
   - `intraday_forecast_job.py`: mirror the same writes for intraday horizons @ml/src/intraday_forecast_job.py.
3. **Batch upserts**: reuse `client.table("indicator_values").upsert([...], on_conflict="symbol_id,timeframe,ts")` to minimize network round-trips.
4. **Logging**: emit structured logs when indicator persistence fails (include symbol, timeframe, ts).

## 4. Edge Functions & API Surface
1. **chart edge function** (`backend/supabase/functions/chart/index.ts`):
   - Optionally join latest indicator snapshot to enrich `ChartResponse` payload (e.g., fetch most recent `indicator_values` row for the requested timeframe).
   - Keep existing `mlSummary.srLevels` JSON path intact @backend/supabase/functions/chart/index.ts#202-243.
2. If multi-device clients need historical series, consider a dedicated REST endpoint (PostgREST view or edge function) exposing `indicator_values` windows by symbol/timeframe.

## 5. macOS Client Considerations
1. No persistence required client-side unless capturing user-customized overlays.
2. If needed later, re-use `SupabaseClient` in `ChartViewModel` to write per-user overlays (currently reads only @client-macos/SwiftBoltML/ViewModels/ChartViewModel.swift#37-167).

## 6. Testing & Validation
1. **Unit tests**: add coverage around the new SupabaseDB helpers ensuring payload structure and conflict handling.
2. **Integration script**: run a forecast job for a test symbol; verify rows in `indicator_values` + `ml_forecasts.sr_levels` via Supabase SQL:
   ```sql
   select count(*) from public.indicator_values where symbol_id = :symbol_id;
   select sr_levels from public.ml_forecasts where symbol_id = :symbol_id and sr_levels is not null;
   ```
3. **CI hook**: extend existing ML pipeline checks to fail when indicator persistence count is zero for the latest run.
4. **Manual QA**: query `select * from public.indicator_values order by created_at desc limit 20;` after running jobs to inspect values.

## 7. Rollout Checklist
- [ ] Apply database migration on Supabase `swiftbolt_db`.
- [ ] Deploy updated ML jobs with indicator persistence.
- [ ] Smoke-test forecast runs; confirm Supabase tables populated.
- [ ] Update `chart` function if exposing new data to clients.
- [ ] Document runbook in `docs/validation/SR_JS_vs_Swift.md` or related validation notes.
- [ ] Monitor Supabase table growth and add retention/partitioning rules as needed.

## 8. Follow-ups
- Add Supabase cron job to materialize daily indicator summaries for analytics dashboards.
- Evaluate storing additional indicators (pivot clusters, volume profile) as columns vs JSON once stabilized.
- Explore syncing `indicator_values` into warehouse if BI tooling requires it.
