create extension if not exists "hypopg" with schema "extensions";

create extension if not exists "index_advisor" with schema "extensions";

create extension if not exists "pg_trgm" with schema "public";

create type "public"."data_status" as enum ('verified', 'live', 'provisional');

drop trigger if exists "watchlist_auto_backfill_trigger" on "public"."watchlist_items";

drop policy "Authenticated users can read indicator_values" on "public"."indicator_values";

drop policy "Public read indicator_values" on "public"."indicator_values";

drop policy "Service role manages indicator_values" on "public"."indicator_values";

drop policy "retention_policies_authenticated_read" on "public"."retention_policies";

drop policy "retention_policies_service_role_all" on "public"."retention_policies";

drop policy "scanner_alerts_select_own" on "public"."scanner_alerts";

drop policy "scanner_alerts_update_own" on "public"."scanner_alerts";

drop policy "watchlists_delete_own" on "public"."watchlists";

drop policy "watchlists_insert_own" on "public"."watchlists";

drop policy "watchlists_select_own" on "public"."watchlists";

drop policy "watchlists_update_own" on "public"."watchlists";

revoke delete on table "public"."news_items" from "anon";

revoke insert on table "public"."news_items" from "anon";

revoke update on table "public"."news_items" from "anon";

revoke delete on table "public"."news_items" from "authenticated";

revoke insert on table "public"."news_items" from "authenticated";

revoke update on table "public"."news_items" from "authenticated";

revoke delete on table "public"."ohlc_bars_v2" from "anon";

revoke insert on table "public"."ohlc_bars_v2" from "anon";

revoke update on table "public"."ohlc_bars_v2" from "anon";

revoke delete on table "public"."ohlc_bars_v2" from "authenticated";

revoke insert on table "public"."ohlc_bars_v2" from "authenticated";

revoke update on table "public"."ohlc_bars_v2" from "authenticated";

revoke delete on table "public"."quotes" from "anon";

revoke insert on table "public"."quotes" from "anon";

revoke update on table "public"."quotes" from "anon";

revoke delete on table "public"."quotes" from "authenticated";

revoke insert on table "public"."quotes" from "authenticated";

revoke update on table "public"."quotes" from "authenticated";

revoke delete on table "public"."retention_policies" from "anon";

revoke insert on table "public"."retention_policies" from "anon";

revoke references on table "public"."retention_policies" from "anon";

revoke select on table "public"."retention_policies" from "anon";

revoke trigger on table "public"."retention_policies" from "anon";

revoke truncate on table "public"."retention_policies" from "anon";

revoke update on table "public"."retention_policies" from "anon";

revoke delete on table "public"."retention_policies" from "authenticated";

revoke insert on table "public"."retention_policies" from "authenticated";

revoke references on table "public"."retention_policies" from "authenticated";

revoke select on table "public"."retention_policies" from "authenticated";

revoke trigger on table "public"."retention_policies" from "authenticated";

revoke truncate on table "public"."retention_policies" from "authenticated";

revoke update on table "public"."retention_policies" from "authenticated";

revoke delete on table "public"."retention_policies" from "service_role";

revoke insert on table "public"."retention_policies" from "service_role";

revoke references on table "public"."retention_policies" from "service_role";

revoke select on table "public"."retention_policies" from "service_role";

revoke trigger on table "public"."retention_policies" from "service_role";

revoke truncate on table "public"."retention_policies" from "service_role";

revoke update on table "public"."retention_policies" from "service_role";

revoke delete on table "public"."symbols" from "anon";

revoke insert on table "public"."symbols" from "anon";

revoke update on table "public"."symbols" from "anon";

revoke delete on table "public"."symbols" from "authenticated";

revoke insert on table "public"."symbols" from "authenticated";

revoke update on table "public"."symbols" from "authenticated";

alter table "public"."indicator_values" drop constraint "indicator_values_unique";

alter table "public"."job_definitions" drop constraint "job_definitions_symbol_timeframe_job_type_key";

alter table "public"."ohlc_bars_v2" drop constraint "ohlc_bars_v2_data_status_check";

alter table "public"."ohlc_bars_v2" drop constraint "ohlc_bars_v2_provider_check";

alter table "public"."ohlc_bars_v2" drop constraint "ohlc_bars_v2_symbol_id_timeframe_ts_provider_is_forecast_key";

alter table "public"."retention_policies" drop constraint "retention_policies_table_name_key";

alter table "public"."indicator_values" drop constraint "indicator_values_timeframe_check";

alter table "public"."supertrend_signals" drop constraint "supertrend_signals_outcome_check";

drop function if exists "public"."claim_backfill_chunk"(p_limit integer);

drop function if exists "public"."cleanup_old_indicator_values"(p_retention_days integer);

drop function if exists "public"."generate_partition_ddl"(p_table_name text, p_start_date date, p_end_date date);

drop function if exists "public"."get_chart_data_v2"(p_symbol_id uuid, p_timeframe character varying, p_start_date timestamp without time zone, p_end_date timestamp without time zone);

drop function if exists "public"."get_latest_indicators"(p_symbol_id uuid, p_timeframe text, p_limit integer);

drop function if exists "public"."reset_stale_jobs"(p_stale_minutes integer);

drop function if exists "public"."run_retention_cleanup"();

drop function if exists "public"."seed_backfill_for_symbol"(p_symbol_id uuid, p_timeframes text[]);

drop function if exists "public"."trigger_backfill_on_watchlist_add"();

drop view if exists "public"."v_job_queue_health";

drop view if exists "public"."v_table_stats";

drop function if exists "public"."worker_claim_job"(p_job_type text);

drop function if exists "public"."worker_complete_job"(p_job_id uuid, p_success boolean, p_error text);

drop function if exists "public"."worker_complete_ranking_job"(p_job_id uuid);

drop function if exists "public"."worker_fail_ranking_job"(p_job_id uuid, p_error_msg text);

drop function if exists "public"."worker_get_ranking_job"();

drop view if exists "public"."corporate_actions_summary";

drop function if exists "public"."get_chart_data_v2_dynamic"(p_symbol_id uuid, p_timeframe character varying, p_max_bars integer, p_include_forecast boolean);

drop view if exists "public"."market_intelligence_dashboard";

drop view if exists "public"."ohlc_bars_unified";

drop view if exists "public"."provider_coverage_summary";

drop view if exists "public"."strike_price_stats";

drop view if exists "public"."v_alpaca_health";

alter table "public"."retention_policies" drop constraint "retention_policies_pkey";

drop index if exists "public"."idx_forecast_jobs_stale_check";

drop index if exists "public"."idx_forecast_jobs_status_priority";

drop index if exists "public"."idx_indicator_values_ts";

drop index if exists "public"."idx_indicator_values_ts_recent";

drop index if exists "public"."idx_intraday_eval_option_b_evaluated";

drop index if exists "public"."idx_job_queue_stale_check";

drop index if exists "public"."idx_job_queue_type_status_priority";

drop index if exists "public"."idx_ml_forecasts_evaluation";

drop index if exists "public"."idx_ml_forecasts_symbol_id";

drop index if exists "public"."idx_ohlc_bars_v2_forecast_lookup";

drop index if exists "public"."idx_ohlc_bars_v2_m15_lookup";

drop index if exists "public"."idx_ohlc_bars_v2_natural_key";

drop index if exists "public"."idx_ohlc_bars_v2_provider";

drop index if exists "public"."idx_ohlc_bars_v2_timeframe_lookup";

drop index if exists "public"."idx_ohlc_chart_query";

drop index if exists "public"."idx_ohlc_forecast";

drop index if exists "public"."idx_ohlc_intraday";

drop index if exists "public"."idx_ohlc_unique_forecast";

drop index if exists "public"."idx_ohlc_unique_historical";

drop index if exists "public"."idx_ohlc_v2_alpaca_historical";

drop index if exists "public"."idx_ohlc_v2_alpaca_intraday";

drop index if exists "public"."idx_ohlc_v2_intraday_query";

drop index if exists "public"."idx_ohlc_verified";

drop index if exists "public"."idx_options_price_history_expiry_analysis";

drop index if exists "public"."idx_options_price_history_partition_key";

drop index if exists "public"."idx_ranking_jobs_stale_check";

drop index if exists "public"."idx_ranking_jobs_symbol_status";

drop index if exists "public"."indicator_values_unique";

drop index if exists "public"."job_definitions_symbol_timeframe_job_type_key";

drop index if exists "public"."ohlc_bars_v2_symbol_id_timeframe_ts_provider_is_forecast_key";

drop index if exists "public"."retention_policies_pkey";

drop index if exists "public"."retention_policies_table_name_key";

drop index if exists "public"."idx_ohlc_provider_range";

drop index if exists "public"."idx_ohlc_v2_chart_query";

drop index if exists "public"."idx_ohlc_v2_provider";

drop table "public"."retention_policies";

alter table "public"."options_underlying_history" alter column "source_provider" drop default;

alter table "public"."symbols" alter column "primary_source" drop default;

alter type "public"."data_provider" rename to "data_provider__old_version_to_be_dropped";

create type "public"."data_provider" as enum ('finnhub', 'massive', 'yfinance', 'tradier', 'alpaca', 'polygon', 'ml_forecast');


  create table "public"."project_members" (
    "user_id" uuid not null,
    "project_id" text not null,
    "inserted_at" timestamp with time zone not null default now()
      );



  create table "public"."provider_checkpoints" (
    "provider" text not null,
    "symbol" text not null,
    "timeframe" text not null,
    "last_ts" timestamp with time zone,
    "bars_written" integer default 0,
    "updated_at" timestamp with time zone default now(),
    "symbol_id" uuid
      );



  create table "public"."rate_buckets" (
    "provider" text not null,
    "capacity" integer not null,
    "refill_per_min" integer not null,
    "tokens" numeric not null,
    "updated_at" timestamp with time zone not null default now()
      );



  create table "public"."symbol_backfill_queue" (
    "id" uuid not null default gen_random_uuid(),
    "symbol_id" uuid not null,
    "ticker" text not null,
    "status" text not null default 'pending'::text,
    "timeframes" text[] default ARRAY['d1'::text, 'h1'::text, 'w1'::text],
    "created_at" timestamp with time zone not null default now(),
    "started_at" timestamp with time zone,
    "completed_at" timestamp with time zone,
    "error_message" text,
    "bars_inserted" integer default 0
      );


alter table "public"."symbol_backfill_queue" enable row level security;

alter table "public"."ohlc_bars" alter column provider type "public"."data_provider" using provider::text::"public"."data_provider";

alter table "public"."options_underlying_history" alter column source_provider type "public"."data_provider" using source_provider::text::"public"."data_provider";

alter table "public"."symbols" alter column primary_source type "public"."data_provider" using primary_source::text::"public"."data_provider";

alter table "public"."options_underlying_history" alter column "source_provider" set default null;

alter table "public"."symbols" alter column "primary_source" set default 'finnhub'::public.data_provider;

drop type "public"."data_provider__old_version_to_be_dropped";

alter table "public"."backfill_jobs" add column "symbol_id" uuid;

alter table "public"."corporate_actions" enable row level security;

alter table "public"."coverage_status" add column "symbol_id" uuid;

alter table "public"."coverage_status" enable row level security;

alter table "public"."forecast_evaluations" enable row level security;

alter table "public"."forecast_jobs" add column "symbol_id" uuid;

alter table "public"."ga_optimization_runs" add column "symbol_id" uuid;

alter table "public"."ga_strategy_params" add column "symbol_id" uuid;

alter table "public"."indicator_values" drop column "computed_at";

alter table "public"."indicator_values" drop column "rsi_14";

alter table "public"."indicator_values" add column "created_at" timestamp with time zone default now();

alter table "public"."indicator_values" add column "rsi" numeric(10,4);

alter table "public"."indicator_values" alter column "adx" set data type numeric(10,4) using "adx"::numeric(10,4);

alter table "public"."indicator_values" alter column "atr_14" set data type numeric(18,6) using "atr_14"::numeric(18,6);

alter table "public"."indicator_values" alter column "bb_lower" set data type numeric(18,6) using "bb_lower"::numeric(18,6);

alter table "public"."indicator_values" alter column "bb_upper" set data type numeric(18,6) using "bb_upper"::numeric(18,6);

alter table "public"."indicator_values" alter column "close" set data type numeric(18,6) using "close"::numeric(18,6);

alter table "public"."indicator_values" alter column "high" set data type numeric(18,6) using "high"::numeric(18,6);

do $$
begin
  if (select data_type
      from information_schema.columns
      where table_schema = 'public'
        and table_name = 'indicator_values'
        and column_name = 'id') <> 'uuid' then
    execute 'alter table "public"."indicator_values" alter column "id" drop default';
    execute 'alter table "public"."indicator_values" alter column "id" set data type bigint using "id"::bigint';
    execute 'alter table "public"."indicator_values" alter column "id" add generated always as identity';
  end if;
end $$;

alter table "public"."indicator_values" alter column "low" set data type numeric(18,6) using "low"::numeric(18,6);

alter table "public"."indicator_values" alter column "macd" set data type numeric(10,4) using "macd"::numeric(10,4);

alter table "public"."indicator_values" alter column "macd_hist" set data type numeric(10,4) using "macd_hist"::numeric(10,4);

alter table "public"."indicator_values" alter column "macd_signal" set data type numeric(10,4) using "macd_signal"::numeric(10,4);

alter table "public"."indicator_values" alter column "nearest_resistance" set data type numeric(18,6) using "nearest_resistance"::numeric(18,6);

alter table "public"."indicator_values" alter column "nearest_support" set data type numeric(18,6) using "nearest_support"::numeric(18,6);

alter table "public"."indicator_values" alter column "open" set data type numeric(18,6) using "open"::numeric(18,6);

alter table "public"."indicator_values" alter column "resistance_distance_pct" set data type numeric(6,3) using "resistance_distance_pct"::numeric(6,3);

alter table "public"."indicator_values" alter column "supertrend_factor" set data type numeric(10,4) using "supertrend_factor"::numeric(10,4);

alter table "public"."indicator_values" alter column "supertrend_trend" set data type smallint using "supertrend_trend"::smallint;

alter table "public"."indicator_values" alter column "supertrend_value" set data type numeric(18,6) using "supertrend_value"::numeric(18,6);

alter table "public"."indicator_values" alter column "support_distance_pct" set data type numeric(6,3) using "support_distance_pct"::numeric(6,3);

alter table "public"."indicator_values" alter column "timeframe" set data type text using "timeframe"::text;

alter table "public"."indicator_values" alter column "volume" set data type numeric(18,6) using "volume"::numeric(18,6);

alter table "public"."job_definitions" add column "batch_version" integer not null default 1;

alter table "public"."job_definitions" add column "symbol_id" uuid;

alter table "public"."job_queue" add column "symbol_id" uuid;

alter table "public"."job_queue" enable row level security;

alter table "public"."job_runs" add column "actual_cost" numeric default 0;

alter table "public"."job_runs" add column "expected_cost" numeric default 1;

alter table "public"."market_calendar" enable row level security;

alter table "public"."model_performance_history" enable row level security;

alter table "public"."model_weights" enable row level security;

alter table "public"."ohlc_bars_v2" add column "raw_ts_text" text;

alter table "public"."ohlc_bars_v2" alter column "data_status" set data type public.data_status using "data_status"::public.data_status;

alter table "public"."ohlc_bars_v2" alter column "fetched_at" set data type timestamp with time zone using "fetched_at"::timestamp with time zone;

alter table "public"."ohlc_bars_v2" alter column "provider" set data type public.data_provider using "provider"::public.data_provider;

alter table "public"."ohlc_bars_v2" alter column "timeframe" set data type public.timeframe using "timeframe"::public.timeframe;

alter table "public"."ohlc_bars_v2" alter column "ts" set data type timestamp with time zone using "ts"::timestamp with time zone;

alter table "public"."ohlc_bars_v2" alter column "updated_at" set data type timestamp with time zone using "updated_at"::timestamp with time zone;

alter table "public"."ohlc_bars_v2" enable row level security;

alter table "public"."options_price_history" drop column "snapshot_date";

alter table "public"."options_scrape_jobs" add column "symbol_id" uuid;

alter table "public"."options_snapshots" enable row level security;

alter table "public"."options_underlying_history" alter column "source_provider" set default 'alpaca'::public.data_provider;

alter table "public"."ranking_jobs" add column "symbol_id" uuid;

alter table "public"."ranking_jobs" enable row level security;

alter table "public"."supertrend_signals" add column "symbol_id" uuid;

alter table "public"."symbols" enable row level security;

CREATE INDEX corporate_actions_symbol_id_idx ON public.corporate_actions USING btree (symbol_id);

CREATE INDEX forecast_evaluations_forecast_id_idx ON public.forecast_evaluations USING btree (forecast_id);

CREATE INDEX forecast_evaluations_symbol_id_idx ON public.forecast_evaluations USING btree (symbol_id);

CREATE INDEX idx_backfill_chunks_symbol_id ON public.backfill_chunks USING btree (symbol_id);

CREATE INDEX idx_backfill_jobs_symbol_id ON public.backfill_jobs USING btree (symbol_id);

CREATE INDEX idx_coverage_status_symbol_id ON public.coverage_status USING btree (symbol_id);

CREATE INDEX idx_forecast_jobs_symbol_id ON public.forecast_jobs USING btree (symbol_id);

CREATE INDEX idx_ga_optimization_runs_symbol_id ON public.ga_optimization_runs USING btree (symbol_id);

CREATE INDEX idx_ga_strategy_params_symbol_id ON public.ga_strategy_params USING btree (symbol_id);

CREATE INDEX idx_job_definitions_batch_version ON public.job_definitions USING btree (batch_version) WHERE (batch_version > 1);

CREATE INDEX idx_job_definitions_symbol_id ON public.job_definitions USING btree (symbol_id);

CREATE INDEX idx_job_queue_symbol_id ON public.job_queue USING btree (symbol_id);

CREATE INDEX idx_job_runs_provider_cost ON public.job_runs USING btree (provider, expected_cost) WHERE (status = 'success'::text);

CREATE INDEX idx_job_runs_status ON public.job_runs USING btree (status);

CREATE INDEX idx_job_runs_status_updated_at ON public.job_runs USING btree (status, updated_at DESC);

CREATE INDEX idx_ohlc_v2_forecast_provider ON public.ohlc_bars_v2 USING btree (symbol_id, timeframe, ts DESC) WHERE ((is_forecast = true) AND (provider = 'ml_forecast'::public.data_provider));

CREATE INDEX idx_ohlc_v2_symbol_tf_ts ON public.ohlc_bars_v2 USING btree (symbol_id, timeframe, ts);

CREATE INDEX idx_ohlc_v2_ts ON public.ohlc_bars_v2 USING btree (ts);

CREATE INDEX idx_ohlc_v2_verified ON public.ohlc_bars_v2 USING btree (symbol_id, timeframe, ts, data_status) WHERE (data_status = 'verified'::public.data_status);

CREATE INDEX idx_options_scrape_jobs_symbol_id ON public.options_scrape_jobs USING btree (symbol_id);

CREATE INDEX idx_project_members_user_project ON public.project_members USING btree (user_id, project_id);

CREATE INDEX idx_provider_checkpoints_symbol_id ON public.provider_checkpoints USING btree (symbol_id);

CREATE INDEX idx_provider_checkpoints_updated ON public.provider_checkpoints USING btree (provider, updated_at DESC);

CREATE INDEX idx_ranking_jobs_symbol_id ON public.ranking_jobs USING btree (symbol_id);

CREATE INDEX idx_supertrend_signals_symbol_id ON public.supertrend_signals USING btree (symbol_id);

CREATE INDEX idx_symbol_backfill_queue_status ON public.symbol_backfill_queue USING btree (status, created_at);

CREATE INDEX idx_symbols_description_trgm ON public.symbols USING gin (description public.gin_trgm_ops);

CREATE INDEX idx_symbols_ticker_trgm ON public.symbols USING gin (ticker public.gin_trgm_ops);

CREATE INDEX idx_watchlist_items_list ON public.watchlist_items USING btree (watchlist_id);

CREATE UNIQUE INDEX indicator_values_symbol_id_timeframe_ts_key ON public.indicator_values USING btree (symbol_id, timeframe, ts);

CREATE UNIQUE INDEX job_definitions_symbol_tf_jobtype_version_key ON public.job_definitions USING btree (symbol, timeframe, job_type, batch_version);

CREATE INDEX job_runs_job_def_id_idx ON public.job_runs USING btree (job_def_id);

CREATE INDEX ml_forecast_evals_intraday_forecast_id_idx ON public.ml_forecast_evaluations_intraday USING btree (forecast_id);

CREATE INDEX options_backfill_jobs_symbol_id_idx ON public.options_backfill_jobs USING btree (symbol_id);

CREATE INDEX options_ranks_contract_symbol_idx ON public.options_ranks USING btree (contract_symbol);

CREATE UNIQUE INDEX project_members_pkey ON public.project_members USING btree (user_id, project_id);

CREATE UNIQUE INDEX provider_checkpoints_pkey ON public.provider_checkpoints USING btree (provider, symbol, timeframe);

CREATE UNIQUE INDEX rate_buckets_pkey ON public.rate_buckets USING btree (provider);

CREATE UNIQUE INDEX symbol_backfill_queue_pkey ON public.symbol_backfill_queue USING btree (id);

CREATE UNIQUE INDEX symbol_backfill_queue_symbol_id_status_key ON public.symbol_backfill_queue USING btree (symbol_id, status);

CREATE UNIQUE INDEX uq_ohlc_bars_v2_symbol_timeframe_ts_provider_forecast ON public.ohlc_bars_v2 USING btree (symbol_id, timeframe, ts, provider, is_forecast);

CREATE UNIQUE INDEX uq_ohlc_v2_bar_layer ON public.ohlc_bars_v2 USING btree (symbol_id, timeframe, ts, provider, is_forecast);

CREATE UNIQUE INDEX ux_ohlc_bars_v2_layer ON public.ohlc_bars_v2 USING btree (symbol_id, timeframe, ts, provider, is_forecast);

CREATE INDEX idx_ohlc_provider_range ON public.ohlc_bars_v2 USING btree (symbol_id, timeframe, provider, ts) WHERE (is_forecast = false);

CREATE INDEX idx_ohlc_v2_chart_query ON public.ohlc_bars_v2 USING btree (symbol_id, timeframe, ts DESC);

CREATE INDEX idx_ohlc_v2_provider ON public.ohlc_bars_v2 USING btree (provider, ts DESC);

alter table "public"."project_members" add constraint "project_members_pkey" PRIMARY KEY using index "project_members_pkey";

alter table "public"."provider_checkpoints" add constraint "provider_checkpoints_pkey" PRIMARY KEY using index "provider_checkpoints_pkey";

alter table "public"."rate_buckets" add constraint "rate_buckets_pkey" PRIMARY KEY using index "rate_buckets_pkey";

alter table "public"."symbol_backfill_queue" add constraint "symbol_backfill_queue_pkey" PRIMARY KEY using index "symbol_backfill_queue_pkey";

alter table "public"."backfill_chunks" add constraint "backfill_chunks_symbol_id_fkey" FOREIGN KEY (symbol_id) REFERENCES public.symbols(id) ON DELETE CASCADE not valid;

alter table "public"."backfill_chunks" validate constraint "backfill_chunks_symbol_id_fkey";

alter table "public"."backfill_jobs" add constraint "backfill_jobs_symbol_id_fkey" FOREIGN KEY (symbol_id) REFERENCES public.symbols(id) ON DELETE CASCADE not valid;

alter table "public"."backfill_jobs" validate constraint "backfill_jobs_symbol_id_fkey";

alter table "public"."coverage_status" add constraint "coverage_status_symbol_id_fkey" FOREIGN KEY (symbol_id) REFERENCES public.symbols(id) ON DELETE CASCADE not valid;

alter table "public"."coverage_status" validate constraint "coverage_status_symbol_id_fkey";

alter table "public"."forecast_jobs" add constraint "forecast_jobs_symbol_id_fkey" FOREIGN KEY (symbol_id) REFERENCES public.symbols(id) ON DELETE CASCADE not valid;

alter table "public"."forecast_jobs" validate constraint "forecast_jobs_symbol_id_fkey";

alter table "public"."ga_optimization_runs" add constraint "ga_optimization_runs_symbol_id_fkey" FOREIGN KEY (symbol_id) REFERENCES public.symbols(id) ON DELETE CASCADE not valid;

alter table "public"."ga_optimization_runs" validate constraint "ga_optimization_runs_symbol_id_fkey";

alter table "public"."ga_strategy_params" add constraint "ga_strategy_params_symbol_id_fkey" FOREIGN KEY (symbol_id) REFERENCES public.symbols(id) ON DELETE CASCADE not valid;

alter table "public"."ga_strategy_params" validate constraint "ga_strategy_params_symbol_id_fkey";

alter table "public"."indicator_values" add constraint "indicator_values_symbol_id_timeframe_ts_key" UNIQUE using index "indicator_values_symbol_id_timeframe_ts_key";

alter table "public"."job_definitions" add constraint "job_definitions_symbol_id_fkey" FOREIGN KEY (symbol_id) REFERENCES public.symbols(id) ON DELETE CASCADE not valid;

alter table "public"."job_definitions" validate constraint "job_definitions_symbol_id_fkey";

alter table "public"."job_definitions" add constraint "job_definitions_symbol_tf_jobtype_version_key" UNIQUE using index "job_definitions_symbol_tf_jobtype_version_key";

alter table "public"."job_queue" add constraint "job_queue_symbol_id_fkey" FOREIGN KEY (symbol_id) REFERENCES public.symbols(id) ON DELETE CASCADE not valid;

alter table "public"."job_queue" validate constraint "job_queue_symbol_id_fkey";

alter table "public"."options_scrape_jobs" add constraint "options_scrape_jobs_symbol_id_fkey" FOREIGN KEY (symbol_id) REFERENCES public.symbols(id) ON DELETE CASCADE not valid;

alter table "public"."options_scrape_jobs" validate constraint "options_scrape_jobs_symbol_id_fkey";

alter table "public"."project_members" add constraint "project_members_user_id_fkey" FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE not valid;

alter table "public"."project_members" validate constraint "project_members_user_id_fkey";

alter table "public"."provider_checkpoints" add constraint "provider_checkpoints_symbol_id_fkey" FOREIGN KEY (symbol_id) REFERENCES public.symbols(id) ON DELETE CASCADE not valid;

alter table "public"."provider_checkpoints" validate constraint "provider_checkpoints_symbol_id_fkey";

alter table "public"."ranking_jobs" add constraint "ranking_jobs_symbol_id_fkey" FOREIGN KEY (symbol_id) REFERENCES public.symbols(id) ON DELETE CASCADE not valid;

alter table "public"."ranking_jobs" validate constraint "ranking_jobs_symbol_id_fkey";

alter table "public"."supertrend_signals" add constraint "supertrend_signals_symbol_id_fkey" FOREIGN KEY (symbol_id) REFERENCES public.symbols(id) ON DELETE CASCADE not valid;

alter table "public"."supertrend_signals" validate constraint "supertrend_signals_symbol_id_fkey";

alter table "public"."symbol_backfill_queue" add constraint "symbol_backfill_queue_status_check" CHECK ((status = ANY (ARRAY['pending'::text, 'processing'::text, 'completed'::text, 'failed'::text]))) not valid;

alter table "public"."symbol_backfill_queue" validate constraint "symbol_backfill_queue_status_check";

alter table "public"."symbol_backfill_queue" add constraint "symbol_backfill_queue_symbol_id_fkey" FOREIGN KEY (symbol_id) REFERENCES public.symbols(id) ON DELETE CASCADE not valid;

alter table "public"."symbol_backfill_queue" validate constraint "symbol_backfill_queue_symbol_id_fkey";

alter table "public"."symbol_backfill_queue" add constraint "symbol_backfill_queue_symbol_id_status_key" UNIQUE using index "symbol_backfill_queue_symbol_id_status_key";

alter table "public"."indicator_values" add constraint "indicator_values_timeframe_check" CHECK ((timeframe = ANY (ARRAY['m15'::text, 'h1'::text, 'h4'::text, 'd1'::text, 'w1'::text]))) not valid;

alter table "public"."indicator_values" validate constraint "indicator_values_timeframe_check";

alter table "public"."supertrend_signals" add constraint "supertrend_signals_outcome_check" CHECK (((outcome)::text = ANY ((ARRAY['WIN'::character varying, 'LOSS'::character varying, 'OPEN'::character varying])::text[]))) not valid;

alter table "public"."supertrend_signals" validate constraint "supertrend_signals_outcome_check";

set check_function_bodies = off;

CREATE OR REPLACE FUNCTION public.claim_next_backfill_job()
 RETURNS TABLE(job_id uuid, symbol_id uuid, ticker text, timeframes text[])
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
DECLARE
    v_job RECORD;
BEGIN
    -- Claim the oldest pending job
    UPDATE public.symbol_backfill_queue
    SET status = 'processing', started_at = now()
    WHERE id = (
        SELECT id FROM public.symbol_backfill_queue
        WHERE status = 'pending'
        ORDER BY created_at ASC
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    )
    RETURNING * INTO v_job;
    
    IF v_job IS NULL THEN
        RETURN;
    END IF;
    
    RETURN QUERY SELECT v_job.id, v_job.symbol_id, v_job.ticker, v_job.timeframes;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.cleanup_stale_intraday()
 RETURNS integer
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
DECLARE
  deleted_count INTEGER;
BEGIN
  DELETE FROM ohlc_bars_v2
  WHERE provider = 'tradier'
    AND is_intraday = true
    AND DATE(ts) < CURRENT_DATE;

  GET DIAGNOSTICS deleted_count = ROW_COUNT;
  RETURN deleted_count;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.complete_backfill_job(p_job_id uuid, p_success boolean, p_bars_inserted integer DEFAULT 0, p_error_message text DEFAULT NULL::text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
BEGIN
    UPDATE public.symbol_backfill_queue
    SET 
        status = CASE WHEN p_success THEN 'completed' ELSE 'failed' END,
        completed_at = now(),
        bars_inserted = p_bars_inserted,
        error_message = p_error_message
    WHERE id = p_job_id;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.exec_sql(p_sql text)
 RETURNS text
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
declare
  res text;
begin
  execute p_sql;
  res := 'ok';
  return res;
end;
$function$
;

CREATE OR REPLACE FUNCTION public.get_chart_data_v2(p_symbol_id uuid, p_timeframe public.timeframe, p_from timestamp with time zone, p_to timestamp with time zone)
 RETURNS TABLE(ts timestamp with time zone, open numeric, high numeric, low numeric, close numeric, volume bigint, provider public.data_provider, is_intraday boolean, is_forecast boolean, data_status public.data_status, confidence_score numeric, upper_band numeric, lower_band numeric)
 LANGUAGE sql
 STABLE
AS $function$
  WITH actual AS (
    SELECT *
    FROM ohlc_bars_v2
    WHERE symbol_id = p_symbol_id
      AND timeframe = p_timeframe
      AND ts >= p_from AND ts <= p_to
      AND is_forecast = false
  ),
  last_actual AS (
    SELECT max(ts) AS last_ts FROM actual
  ),
  forecasts AS (
    SELECT *
    FROM ohlc_bars_v2
    WHERE symbol_id = p_symbol_id
      AND timeframe = p_timeframe
      AND is_forecast = true
      AND provider = 'ml_forecast'
      AND ts > COALESCE((SELECT last_ts FROM last_actual), p_from)
      AND ts <= p_to
  )
  SELECT ts, open, high, low, close, volume, provider, is_intraday, is_forecast, data_status, confidence_score, upper_band, lower_band
  FROM actual
  UNION ALL
  SELECT ts, open, high, low, close, volume, provider, is_intraday, is_forecast, data_status, confidence_score, upper_band, lower_band
  FROM forecasts
  ORDER BY ts;
$function$
;

CREATE OR REPLACE FUNCTION public.get_chart_data_v2(p_symbol_id uuid, p_timeframe text, p_start_date timestamp with time zone, p_end_date timestamp with time zone)
 RETURNS TABLE(ts timestamp with time zone, open numeric, high numeric, low numeric, close numeric, volume bigint, provider text, is_intraday boolean)
 LANGUAGE plpgsql
 STABLE
AS $function$
BEGIN
  RETURN QUERY
  WITH base AS (
    SELECT *
    FROM public.ohlc_bars_v2 o
    WHERE o.symbol_id = p_symbol_id
      AND o.timeframe = p_timeframe
      AND o.ts >= p_start_date
      AND o.ts <= p_end_date
      AND o.is_forecast = false
  ),
  hist AS (
    SELECT DISTINCT ON (date_trunc('minute', o.ts), o.provider)
      o.ts, o.open, o.high, o.low, o.close, o.volume, (o.provider)::text AS provider, false AS is_intraday, o.id
    FROM base o
    WHERE o.ts < date_trunc('day', now())
    ORDER BY date_trunc('minute', o.ts), o.provider, o.id DESC
  ),
  intra_raw AS (
    SELECT 
      o.ts, o.open, o.high, o.low, o.close, o.volume,
      CASE WHEN o.provider = 'alpaca' THEN 1 ELSE 2 END AS provider_rank,
      (o.provider)::text AS provider, o.id
    FROM base o
    WHERE o.ts >= date_trunc('day', now())
  ),
  intra AS (
    SELECT DISTINCT ON (date_trunc('minute', intra_raw.ts))
      intra_raw.ts, intra_raw.open, intra_raw.high, intra_raw.low, intra_raw.close, intra_raw.volume, intra_raw.provider, true AS is_intraday
    FROM intra_raw
    ORDER BY date_trunc('minute', intra_raw.ts), provider_rank, intra_raw.id DESC
  )
  SELECT hist.ts, hist.open, hist.high, hist.low, hist.close, hist.volume, hist.provider, hist.is_intraday FROM hist
  UNION ALL
  SELECT intra.ts, intra.open, intra.high, intra.low, intra.close, intra.volume, intra.provider, intra.is_intraday FROM intra
  ORDER BY 1;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.get_latest_historical_date(p_symbol_id uuid, p_timeframe character varying)
 RETURNS date
 LANGUAGE plpgsql
AS $function$
DECLARE
  latest_date DATE;
BEGIN
  SELECT DATE(MAX(ts))
  INTO latest_date
  FROM ohlc_bars_v2
  WHERE symbol_id = p_symbol_id
    AND timeframe = p_timeframe
    AND provider = 'polygon'
    AND is_forecast = false;

  RETURN latest_date;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.get_symbol_ohlc_averages(p_symbol_id uuid, p_timeframe text, p_lookback_days integer DEFAULT 30)
 RETURNS TABLE(avg_open numeric, avg_high numeric, avg_low numeric, avg_close numeric, bars_count integer)
 LANGUAGE sql
 STABLE
AS $function$
  select
    avg(open)::numeric,
    avg(high)::numeric,
    avg(low)::numeric,
    avg(close)::numeric,
    count(*)::int
  from public.ohlc_bars_v2
  where symbol_id = p_symbol_id
    and timeframe = p_timeframe::public.timeframe
    and ts >= now() - (p_lookback_days || ' days')::interval
    and is_forecast = false
$function$
;

CREATE OR REPLACE FUNCTION public.get_symbol_ohlc_averages(p_symbol_ids uuid[])
 RETURNS TABLE(symbol_id uuid, avg_daily_volume_all double precision, avg_daily_volume_10d double precision, avg_close_all double precision, avg_close_10d double precision)
 LANGUAGE sql
 STABLE
AS $function$
  with d1 as (
    select
      symbol_id,
      ts,
      close,
      volume,
      row_number() over (partition by symbol_id order by ts desc) as rn
    from public.ohlc_bars
    where timeframe = 'd1'
      and symbol_id = any(p_symbol_ids)
  )
  select
    symbol_id,
    avg(volume)::double precision as avg_daily_volume_all,
    avg(volume) filter (where rn <= 10)::double precision as avg_daily_volume_10d,
    avg(close)::double precision as avg_close_all,
    avg(close) filter (where rn <= 10)::double precision as avg_close_10d
  from d1
  group by symbol_id;
$function$
;

CREATE OR REPLACE FUNCTION public.get_symbols_needing_sync(p_limit integer DEFAULT 100)
 RETURNS TABLE(symbol_id uuid, ticker character varying, latest_date date, days_behind integer)
 LANGUAGE plpgsql
AS $function$
BEGIN
  RETURN QUERY
  SELECT
    s.id as symbol_id,
    s.ticker,
    get_latest_historical_date(s.id, 'd1') as latest_date,
    (CURRENT_DATE - get_latest_historical_date(s.id, 'd1'))::INTEGER as days_behind
  FROM symbols s
  WHERE s.is_active = true
    AND is_historical_stale(s.id, 'd1')
  ORDER BY days_behind DESC NULLS FIRST
  LIMIT p_limit;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.get_token_status(p_provider text)
 RETURNS TABLE(provider text, available_tokens numeric, capacity integer, refill_rate integer, seconds_until_full numeric)
 LANGUAGE plpgsql
AS $function$
declare
  v_capacity int;
  v_refill_per_min int;
  v_tokens numeric;
  v_updated_at timestamptz;
  v_current_tokens numeric;
begin
  select 
    rb.capacity,
    rb.refill_per_min,
    rb.tokens,
    rb.updated_at
  into 
    v_capacity,
    v_refill_per_min,
    v_tokens,
    v_updated_at
  from rate_buckets rb
  where rb.provider = p_provider;

  if not found then
    return;
  end if;

  -- Calculate current tokens with refill
  v_current_tokens := least(
    v_capacity::numeric,
    v_tokens + (extract(epoch from (now() - v_updated_at)) / 60.0) * v_refill_per_min
  );

  return query select 
    p_provider,
    v_current_tokens,
    v_capacity,
    v_refill_per_min,
    case 
      when v_current_tokens >= v_capacity then 0
      else ((v_capacity - v_current_tokens) / v_refill_per_min) * 60
    end as seconds_until_full;
end$function$
;

CREATE OR REPLACE FUNCTION public.is_historical_stale(p_symbol_id uuid, p_timeframe character varying)
 RETURNS boolean
 LANGUAGE plpgsql
AS $function$
DECLARE
  latest_date DATE;
  yesterday DATE;
BEGIN
  latest_date := get_latest_historical_date(p_symbol_id, p_timeframe);
  yesterday := CURRENT_DATE - INTERVAL '1 day';

  -- Skip weekends
  IF EXTRACT(DOW FROM yesterday) IN (0, 6) THEN
    -- Find the previous Friday
    IF EXTRACT(DOW FROM yesterday) = 0 THEN
      yesterday := yesterday - INTERVAL '2 days';
    ELSE
      yesterday := yesterday - INTERVAL '1 day';
    END IF;
  END IF;

  RETURN latest_date IS NULL OR latest_date < yesterday;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.is_market_open(p_at timestamp with time zone DEFAULT now(), p_tz text DEFAULT 'America/New_York'::text)
 RETURNS boolean
 LANGUAGE sql
 STABLE
AS $function$
  with local as (
    select (p_at at time zone p_tz) as local_ts
  ),
  d as (
    select date(local_ts) as d, local_ts from local
  )
  select mc.is_open
         and (
           mc.market_open is null or mc.market_close is null
           or (local.local_ts::time between mc.market_open and mc.market_close)
         )
  from d
  join public.market_calendar mc on mc.date = d.d
  join local on true
$function$
;

CREATE OR REPLACE FUNCTION public.is_rfc3339_or_date_only(ts_text text)
 RETURNS boolean
 LANGUAGE plpgsql
 IMMUTABLE
AS $function$
BEGIN
  IF ts_text IS NULL THEN
    RETURN false;
  END IF;
  -- YYYY-MM-DD
  IF ts_text ~ '^\d{4}-\d{2}-\d{2}$' THEN
    RETURN true;
  END IF;
  -- RFC-3339 (basic check). Allows timezone Z or +/-HH:MM, optional fractional seconds
  IF ts_text ~ '^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(Z|[+-]\d{2}:?\d{2})$' THEN
    RETURN true;
  END IF;
  RETURN false;
END;
$function$
;

create or replace view "public"."my_artifacts" as  SELECT id,
    bucket_id,
    name,
    metadata,
    created_at,
    updated_at
   FROM storage.objects o
  WHERE ((bucket_id = 'ml-artifacts'::text) AND (split_part(name, '/'::text, 1) IN ( SELECT pm.project_id
           FROM public.project_members pm
          WHERE (pm.user_id = ( SELECT auth.uid() AS uid)))));


CREATE OR REPLACE FUNCTION public.ohlc_bars_v2_alpaca_ts_trigger()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
BEGIN
  -- Only apply when provider is alpaca and raw_ts_text provided
  IF NEW.provider::text = 'alpaca' AND NEW.raw_ts_text IS NOT NULL THEN
    IF NOT public.is_rfc3339_or_date_only(NEW.raw_ts_text) THEN
      RAISE EXCEPTION 'Invalid Alpaca time format (expected RFC-3339 or YYYY-MM-DD): %', NEW.raw_ts_text
        USING ERRCODE = '22007';
    END IF;
    NEW.ts := public.parse_alpaca_ts(NEW.raw_ts_text);
  END IF;
  RETURN NEW;
END;
$function$
;

create or replace view "public"."option_rankings" as  SELECT id,
    underlying_symbol_id,
    expiry,
    strike,
    side,
    ml_score,
    implied_vol,
    delta,
    gamma,
    open_interest,
    volume,
    run_at,
    created_at,
    contract_symbol,
    theta,
    vega,
    rho,
    bid,
    ask,
    mark,
    last_price,
    momentum_score,
    value_score,
    greeks_score,
    composite_rank,
    iv_rank,
    spread_pct,
    vol_oi_ratio,
    signal_discount,
    signal_runner,
    signal_greeks,
    signal_buy,
    signals,
    liquidity_confidence,
    ranking_mode,
    relative_value_score,
    entry_difficulty_score,
    ranking_stability_score
   FROM public.options_ranks;


CREATE OR REPLACE FUNCTION public.parse_alpaca_ts(ts_text text)
 RETURNS timestamp with time zone
 LANGUAGE plpgsql
 STABLE
AS $function$
DECLARE
  ts_out timestamptz;
BEGIN
  IF ts_text IS NULL THEN
    RAISE EXCEPTION 'ts_text is NULL';
  END IF;
  IF ts_text ~ '^\d{4}-\d{2}-\d{2}$' THEN
    ts_out := (ts_text || 'T00:00:00Z')::timestamptz;
    RETURN ts_out;
  ELSIF ts_text ~ '^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(Z|[+-]\d{2}:?\d{2})$' THEN
    ts_out := ts_text::timestamptz;
    RETURN ts_out;
  ELSE
    RAISE EXCEPTION 'Invalid timestamp format: %', ts_text USING ERRCODE = '22007';
  END IF;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.queue_symbol_backfill()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
DECLARE
    v_ticker TEXT;
    v_existing_bars INTEGER;
BEGIN
    -- Get the ticker for this symbol
    SELECT ticker INTO v_ticker FROM public.symbols WHERE id = NEW.symbol_id;
    
    IF v_ticker IS NULL THEN
        RETURN NEW;
    END IF;
    
    -- Check if we already have sufficient d1 data for this symbol
    SELECT COUNT(*) INTO v_existing_bars
    FROM public.ohlc_bars
    WHERE symbol_id = NEW.symbol_id AND timeframe = 'd1';
    
    -- Only queue backfill if we have less than 100 d1 bars
    IF v_existing_bars < 100 THEN
        -- Insert into backfill queue (ignore if already pending)
        INSERT INTO public.symbol_backfill_queue (symbol_id, ticker, status, timeframes)
        VALUES (NEW.symbol_id, v_ticker, 'pending', ARRAY['d1', 'h1', 'w1'])
        ON CONFLICT (symbol_id, status) DO NOTHING;
        
        RAISE NOTICE 'Queued backfill for % (% existing d1 bars)', v_ticker, v_existing_bars;
    ELSE
        RAISE NOTICE 'Skipping backfill for % (% existing d1 bars)', v_ticker, v_existing_bars;
    END IF;
    
    RETURN NEW;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.run_orchestrator_tick()
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
declare
  svc_secret jsonb;
  svc_key text;
  base_url text := 'https://cygflaemtmwiwaviclks.supabase.co';
  req_id bigint;
begin
  -- Read service role key from Vault
  -- Supabase automatically stores this as 'service_role' secret
  select decrypted_secret into svc_key
  from vault.decrypted_secrets
  where name = 'service_role';

  -- If secret not found, raise error
  if svc_key is null then
    raise exception 'Service role key not found in Vault. Please add it via: select vault.create_secret(''service_role'', ''your-key-here'');';
  end if;

  -- Fire-and-forget HTTP call to Edge Function "orchestrator"
  select net.http_post(
    url := base_url || '/functions/v1/orchestrator?action=tick',
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || svc_key,
      'Content-Type', 'application/json'
    ),
    body := '{}'::jsonb,
    timeout_milliseconds := 30000  -- 30 second timeout
  ) into req_id;

  -- Note: We don't wait for completion (fire-and-forget)
  -- The orchestrator runs async in the background
  raise notice 'Orchestrator tick triggered with request_id: %', req_id;
end;
$function$
;

CREATE OR REPLACE FUNCTION public.seed_job_definition_for_symbol(p_symbol_id uuid, p_timeframes text[] DEFAULT ARRAY['h1'::text])
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
DECLARE
  v_ticker TEXT;
  v_timeframe TEXT;
  v_job_def_id UUID;
  v_results JSONB := '[]'::JSONB;
  v_job_result JSONB;
  v_job_type TEXT;
BEGIN
  SELECT ticker INTO v_ticker FROM symbols WHERE id = p_symbol_id;
  IF v_ticker IS NULL THEN
    RAISE EXCEPTION 'Symbol with ID % not found', p_symbol_id;
  END IF;

  FOREACH v_timeframe IN ARRAY p_timeframes LOOP
    BEGIN
      v_job_type := CASE 
        WHEN v_timeframe IN ('15m', '1h', '4h', 'h1', 'h4', 'm15') THEN 'fetch_intraday'
        ELSE 'fetch_historical'
      END;

      v_timeframe := CASE v_timeframe
        WHEN '1h' THEN 'h1'
        WHEN '4h' THEN 'h4'
        WHEN '15m' THEN 'm15'
        ELSE v_timeframe
      END;

      BEGIN
        INSERT INTO job_definitions (symbol, timeframe, job_type, window_days, priority, enabled)
        VALUES (v_ticker, v_timeframe, v_job_type, 730, 150, true)
        RETURNING id INTO v_job_def_id;
      EXCEPTION WHEN unique_violation THEN
        UPDATE job_definitions SET
          window_days = GREATEST(window_days, 730),
          priority = GREATEST(priority, 150),
          enabled = true,
          updated_at = NOW()
        WHERE symbol = v_ticker 
          AND timeframe = v_timeframe 
          AND job_type = v_job_type
        RETURNING id INTO v_job_def_id;
      END;

      v_job_result := jsonb_build_object(
        'ticker', v_ticker,
        'timeframe', v_timeframe,
        'job_def_id', v_job_def_id,
        'status', 'created'
      );
      v_results := v_results || v_job_result;
    EXCEPTION WHEN OTHERS THEN
      v_job_result := jsonb_build_object(
        'ticker', v_ticker,
        'timeframe', v_timeframe,
        'status', 'error',
        'error', SQLERRM
      );
      v_results := v_results || v_job_result;
    END;
  END LOOP;

  RETURN jsonb_build_object('symbol_id', p_symbol_id, 'ticker', v_ticker, 'jobs', v_results);
END;
$function$
;

CREATE OR REPLACE FUNCTION public.sync_symbol_id_from_ticker()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  -- If symbol TEXT column is updated, sync symbol_id
  IF NEW.symbol IS NOT NULL AND (OLD.symbol IS NULL OR NEW.symbol != OLD.symbol) THEN
    SELECT id INTO NEW.symbol_id
    FROM symbols
    WHERE ticker = NEW.symbol;
    
    -- If symbol not found, raise warning but allow insert/update
    IF NEW.symbol_id IS NULL THEN
      RAISE WARNING 'Symbol % not found in symbols table', NEW.symbol;
    END IF;
  END IF;
  
  RETURN NEW;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.take_token(p_provider text, p_cost numeric DEFAULT 1)
 RETURNS boolean
 LANGUAGE plpgsql
AS $function$
declare
  v_capacity int;
  v_refill_per_min int;
  v_tokens numeric;
  v_updated_at timestamptz;
  v_new_tokens numeric;
begin
  -- Lock row for update and refill tokens
  select 
    capacity,
    refill_per_min,
    tokens,
    updated_at
  into 
    v_capacity,
    v_refill_per_min,
    v_tokens,
    v_updated_at
  from rate_buckets
  where provider = p_provider
  for update;

  if not found then
    raise exception 'Provider % not found in rate_buckets', p_provider;
  end if;

  -- Calculate refilled tokens based on time elapsed
  v_new_tokens := least(
    v_capacity::numeric,
    v_tokens + (extract(epoch from (now() - v_updated_at)) / 60.0) * v_refill_per_min
  );

  -- Check if we have enough tokens
  if v_new_tokens >= p_cost then
    -- Deduct tokens and update timestamp
    update rate_buckets
    set 
      tokens = v_new_tokens - p_cost,
      updated_at = now()
    where provider = p_provider;
    
    return true;
  else
    -- Not enough tokens, just update the refilled amount
    update rate_buckets
    set 
      tokens = v_new_tokens,
      updated_at = now()
    where provider = p_provider;
    
    return false;
  end if;
end$function$
;

CREATE OR REPLACE FUNCTION public.trigger_job_definition_on_watchlist_add()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
  v_result JSONB;
BEGIN
  BEGIN
    v_result := seed_job_definition_for_symbol(NEW.symbol_id, ARRAY['h1']);
    RAISE NOTICE 'Auto job definition created: %', v_result;
  EXCEPTION WHEN OTHERS THEN
    RAISE WARNING 'Failed to create job definition for symbol_id %: %', NEW.symbol_id, SQLERRM;
  END;
  RETURN NEW;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.claim_queued_job()
 RETURNS TABLE(job_run_id uuid, symbol text, timeframe text, job_type text, slice_from timestamp with time zone, slice_to timestamp with time zone)
 LANGUAGE plpgsql
AS $function$
declare
  v_job_run record;
begin
  select
    jr.id as job_run_id,
    jr.symbol,
    jr.timeframe,
    jr.job_type,
    jr.slice_from,
    jr.slice_to
  into v_job_run
  from public.job_runs jr
  left join public.job_definitions jd
    on jd.id = jr.job_def_id
  where jr.status = 'queued'
  order by
    case jr.timeframe
      when 'm15' then 1
      when 'h1' then 2
      when 'h4' then 3
      when 'd1' then 4
      when 'w1' then 5
      else 6
    end asc,
    coalesce(jr.slice_to, jr.created_at) desc,
    coalesce(jd.priority, 0) desc,
    jr.created_at desc
  limit 1
  for update of jr skip locked;

  if v_job_run.job_run_id is null then
    return;
  end if;

  update public.job_runs
  set
    status = 'running',
    started_at = now(),
    updated_at = now()
  where id = v_job_run.job_run_id;

  return query
  select
    v_job_run.job_run_id,
    v_job_run.symbol,
    v_job_run.timeframe,
    v_job_run.job_type,
    v_job_run.slice_from,
    v_job_run.slice_to;
end;
$function$
;

create or replace view "public"."corporate_actions_summary" as  SELECT s.ticker,
    ca.action_type,
    ca.ex_date,
    count(b.id) AS bars_affected
   FROM ((public.corporate_actions ca
     JOIN public.symbols s ON ((s.id = ca.symbol_id)))
     LEFT JOIN public.ohlc_bars_v2 b ON ((b.adjusted_for = ca.id)))
  GROUP BY s.ticker, ca.action_type, ca.ex_date;


CREATE OR REPLACE FUNCTION public.detect_ohlc_gaps(p_symbol text, p_timeframe text, p_max_gap_hours integer DEFAULT 24)
 RETURNS TABLE(gap_start timestamp with time zone, gap_end timestamp with time zone, gap_hours numeric)
 LANGUAGE plpgsql
AS $function$
BEGIN
  RETURN QUERY
  WITH bars_with_next AS (
    SELECT
      o.ts,
      LEAD(o.ts) OVER (ORDER BY o.ts) as next_ts,
      EXTRACT(EPOCH FROM (LEAD(o.ts) OVER (ORDER BY o.ts) - o.ts)) / 3600 as gap_hrs
    FROM ohlc_bars_v2 o
    WHERE o.symbol_id = (SELECT id FROM symbols WHERE ticker = p_symbol)
      AND o.timeframe = p_timeframe
      AND o.provider = 'alpaca'
      AND o.is_forecast = false
    ORDER BY o.ts
  )
  SELECT
    b.ts::TIMESTAMP WITH TIME ZONE as gap_start,
    b.next_ts::TIMESTAMP WITH TIME ZONE as gap_end,
    b.gap_hrs::DECIMAL as gap_hours
  FROM bars_with_next b
  WHERE b.gap_hrs > p_max_gap_hours
  ORDER BY b.gap_hrs DESC;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.get_chart_data_v2_dynamic(p_symbol_id uuid, p_timeframe character varying, p_max_bars integer DEFAULT 1000, p_include_forecast boolean DEFAULT true)
 RETURNS TABLE(ts text, open numeric, high numeric, low numeric, close numeric, volume bigint, provider text, is_intraday boolean, is_forecast boolean, data_status text, confidence_score numeric, upper_band numeric, lower_band numeric)
 LANGUAGE plpgsql
AS $function$
BEGIN
  RETURN QUERY
  WITH recent_data AS (
    SELECT
      o.ts AS bar_ts,
      o.open,
      o.high,
      o.low,
      o.close,
      o.volume,
      o.provider::text AS provider_text,
      o.is_intraday,
      o.is_forecast,
      o.data_status::text AS data_status_text,
      o.confidence_score,
      o.upper_band,
      o.lower_band
    FROM ohlc_bars_v2 o
    WHERE o.symbol_id = p_symbol_id
      AND o.timeframe::text = p_timeframe
      AND o.is_forecast = false
      AND o.provider IN ('alpaca', 'polygon', 'tradier', 'yfinance')
    ORDER BY o.ts DESC
    LIMIT p_max_bars
  ),
  forecast_data AS (
    SELECT
      o.ts AS bar_ts,
      o.open,
      o.high,
      o.low,
      o.close,
      o.volume,
      o.provider::text AS provider_text,
      o.is_intraday,
      o.is_forecast,
      o.data_status::text AS data_status_text,
      o.confidence_score,
      o.upper_band,
      o.lower_band
    FROM ohlc_bars_v2 o
    WHERE p_include_forecast = true
      AND o.symbol_id = p_symbol_id
      AND o.timeframe::text = p_timeframe
      AND o.is_forecast = true
      AND o.provider = 'ml_forecast'
      AND (
        (p_timeframe IN ('m15', 'h1', 'h4') AND DATE(o.ts AT TIME ZONE 'America/New_York') >= CURRENT_DATE)
        OR (p_timeframe NOT IN ('m15', 'h1', 'h4') AND DATE(o.ts AT TIME ZONE 'America/New_York') > CURRENT_DATE)
      )
    ORDER BY o.ts ASC
    LIMIT 2000
  )
  SELECT
    to_char(combined.bar_ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
    combined.open,
    combined.high,
    combined.low,
    combined.close,
    combined.volume,
    combined.provider_text,
    combined.is_intraday,
    combined.is_forecast,
    combined.data_status_text,
    combined.confidence_score,
    combined.upper_band,
    combined.lower_band
  FROM (
    SELECT * FROM recent_data
    UNION ALL
    SELECT * FROM forecast_data
  ) combined
  ORDER BY combined.bar_ts ASC;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.get_coverage_gaps(p_symbol text, p_timeframe text, p_window_days integer DEFAULT 7)
 RETURNS TABLE(gap_from timestamp with time zone, gap_to timestamp with time zone, gap_hours numeric)
 LANGUAGE plpgsql
AS $function$
declare
  v_target_from timestamptz;
  v_target_to timestamptz;
  v_coverage_from timestamptz;
  v_coverage_to timestamptz;
  v_is_intraday boolean;
  v_today_close timestamptz;
begin
  v_is_intraday := p_timeframe in ('m15','h1','h4');

  if v_is_intraday then
    v_today_close := date_trunc('day', now()) + interval '21 hours';

    if now() < v_today_close then
      v_target_to := v_today_close - interval '1 day';
    else
      v_target_to := least(now(), v_today_close);
    end if;
  else
    v_target_to := now();
  end if;

  v_target_from := v_target_to - (p_window_days || ' days')::interval;

  select from_ts, to_ts into v_coverage_from, v_coverage_to
  from coverage_status
  where symbol = p_symbol and timeframe = p_timeframe;

  if v_coverage_from is null or v_coverage_to is null then
    return query
      select v_target_from, v_target_to, extract(epoch from (v_target_to - v_target_from)) / 3600.0;
    return;
  end if;

  if v_coverage_from > v_target_from then
    return query
      select v_target_from, v_coverage_from, extract(epoch from (v_coverage_from - v_target_from)) / 3600.0;
  end if;

  if v_coverage_to < v_target_to then
    return query
      select v_coverage_to, v_target_to, extract(epoch from (v_target_to - v_coverage_to)) / 3600.0;
  end if;

  return;
end;
$function$
;

CREATE OR REPLACE FUNCTION public.get_options_enriched_features(p_option_id uuid)
 RETURNS TABLE(contract_symbol text, underlying_symbol_id uuid, strike numeric, side text, expiry date, ml_score numeric, composite_rank numeric, momentum_score numeric, value_score numeric, greeks_score numeric, iv_rank numeric, underlying_ret_7d numeric, underlying_vol_7d numeric, underlying_drawdown_7d numeric, underlying_gap_count integer, mark numeric, implied_vol numeric, delta numeric, gamma numeric, theta numeric, vega numeric)
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
DECLARE
    v_underlying_symbol_id UUID;
BEGIN
    SELECT orr.underlying_symbol_id INTO v_underlying_symbol_id
    FROM options_ranks orr
    WHERE orr.id = p_option_id;

    IF v_underlying_symbol_id IS NULL THEN
        RETURN;
    END IF;

    RETURN QUERY
    SELECT
        orr.contract_symbol,
        orr.underlying_symbol_id,
        orr.strike,
        orr.side::TEXT,
        orr.expiry,
        orr.ml_score,
        orr.composite_rank,
        orr.momentum_score,
        orr.value_score,
        orr.greeks_score,
        orr.iv_rank,
        COALESCE((SELECT ouh.ret_7d FROM options_underlying_history ouh WHERE ouh.underlying_symbol_id = v_underlying_symbol_id AND ouh.timeframe = 'd1' ORDER BY ouh.ts DESC LIMIT 1), 0) AS underlying_ret_7d,
        COALESCE((SELECT ouh.vol_7d FROM options_underlying_history ouh WHERE ouh.underlying_symbol_id = v_underlying_symbol_id AND ouh.timeframe = 'd1' ORDER BY ouh.ts DESC LIMIT 1), 0) AS underlying_vol_7d,
        COALESCE((SELECT ouh.drawdown_7d FROM options_underlying_history ouh WHERE ouh.underlying_symbol_id = v_underlying_symbol_id AND ouh.timeframe = 'd1' ORDER BY ouh.ts DESC LIMIT 1), 0) AS underlying_drawdown_7d,
        COALESCE((SELECT ouh.gap_count FROM options_underlying_history ouh WHERE ouh.underlying_symbol_id = v_underlying_symbol_id AND ouh.timeframe = 'd1' ORDER BY ouh.ts DESC LIMIT 1), 0) AS underlying_gap_count,
        orr.mark,
        orr.implied_vol,
        orr.delta,
        orr.gamma,
        orr.theta,
        orr.vega
    FROM options_ranks orr
    WHERE orr.id = p_option_id;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.is_market_open(check_date date DEFAULT CURRENT_DATE)
 RETURNS boolean
 LANGUAGE plpgsql
 STABLE
AS $function$
DECLARE
  trading_day market_calendar%ROWTYPE;
BEGIN
  SELECT * INTO trading_day FROM market_calendar WHERE date = check_date;
  
  IF NOT FOUND THEN
    RETURN FALSE;  -- No calendar data, assume closed
  END IF;
  
  IF NOT trading_day.is_open THEN
    RETURN FALSE;  -- Market closed (holiday/weekend)
  END IF;
  
  RETURN LOCALTIME BETWEEN trading_day.market_open AND trading_day.market_close;
END;
$function$
;

create or replace view "public"."market_intelligence_dashboard" as  SELECT 'Market Status'::text AS metric,
        CASE
            WHEN public.is_market_open(now(), 'America/New_York') THEN 'OPEN'::text
            ELSE 'CLOSED'::text
        END AS value,
    (public.next_trading_day())::text AS next_event,
    'real-time'::text AS category
UNION ALL
 SELECT 'Pending Split Adjustments'::text AS metric,
    (count(*))::text AS value,
    (min(corporate_actions.ex_date))::text AS next_event,
    'corporate_actions'::text AS category
   FROM public.corporate_actions
  WHERE ((corporate_actions.bars_adjusted = false) AND (corporate_actions.action_type = ANY (ARRAY['stock_split'::text, 'reverse_split'::text])))
UNION ALL
 SELECT 'Calendar Cache Status'::text AS metric,
    ((count(*))::text || ' days'::text) AS value,
    (max(market_calendar.date))::text AS next_event,
    'calendar'::text AS category
   FROM public.market_calendar
  WHERE (market_calendar.date >= CURRENT_DATE)
UNION ALL
 SELECT 'Total Corporate Actions'::text AS metric,
    (count(*))::text AS value,
    (max(corporate_actions.ex_date))::text AS next_event,
    'corporate_actions'::text AS category
   FROM public.corporate_actions
UNION ALL
 SELECT 'Unadjusted Bars'::text AS metric,
    (count(*))::text AS value,
    NULL::text AS next_event,
    'data_quality'::text AS category
   FROM public.ohlc_bars_v2
  WHERE ((ohlc_bars_v2.adjusted_for IS NULL) AND (ohlc_bars_v2.symbol_id IN ( SELECT corporate_actions.symbol_id
           FROM public.corporate_actions
          WHERE ((corporate_actions.bars_adjusted = false) AND (corporate_actions.action_type = ANY (ARRAY['stock_split'::text, 'reverse_split'::text]))))));


create or replace view "public"."ohlc_bars_unified" as  SELECT id,
    symbol_id,
    timeframe,
    ts,
    open,
    high,
    low,
    close,
    volume,
    provider,
    is_intraday,
    is_forecast,
    data_status,
    fetched_at,
    created_at,
    updated_at,
    confidence_score,
    upper_band,
    lower_band,
    adjusted_for
   FROM public.ohlc_bars_v2;


create or replace view "public"."provider_coverage_summary" as  SELECT symbol_id,
    timeframe,
    provider,
    date((ts AT TIME ZONE 'UTC'::text)) AS day_utc,
    count(*) AS bars_count,
    max(fetched_at) AS last_fetched_at
   FROM public.ohlc_bars_v2
  GROUP BY symbol_id, timeframe, provider, (date((ts AT TIME ZONE 'UTC'::text)));


CREATE OR REPLACE FUNCTION public.reset_stale_running_jobs(p_max_age_minutes integer DEFAULT 60, p_max_attempts integer DEFAULT 5)
 RETURNS TABLE(reset_count integer)
 LANGUAGE plpgsql
AS $function$
declare
  v_reset int;
  v_failed int;
begin
  with stale as (
    select jr.id, jr.attempt
    from public.job_runs jr
    where jr.status = 'running'
      and coalesce(jr.started_at, jr.updated_at, jr.created_at) < now() - make_interval(mins => p_max_age_minutes)
    for update skip locked
  ),
  to_fail as (
    update public.job_runs jr
    set
      status = 'failed',
      error_message = 'Stale running job exceeded max attempts',
      error_code = 'STALE_RUNNING',
      finished_at = now(),
      updated_at = now()
    from stale s
    where jr.id = s.id
      and s.attempt >= p_max_attempts
    returning 1
  ),
  to_reset as (
    update public.job_runs jr
    set
      status = 'queued',
      attempt = jr.attempt + 1,
      error_message = null,
      error_code = null,
      started_at = null,
      updated_at = now()
    from stale s
    where jr.id = s.id
      and s.attempt < p_max_attempts
    returning 1
  )
  select
    coalesce((select count(*) from to_fail), 0),
    coalesce((select count(*) from to_reset), 0)
  into v_failed, v_reset;

  return query select (coalesce(v_reset, 0) + coalesce(v_failed, 0));
end;
$function$
;

create or replace view "public"."strike_price_stats" as  SELECT underlying_symbol_id,
    strike,
    side,
    expiry,
    count(*) AS sample_count,
    avg(mark) AS avg_mark,
    stddev(mark) AS stddev_mark,
    min(mark) AS min_mark,
    max(mark) AS max_mark,
    avg(implied_vol) AS avg_iv,
    max(snapshot_at) AS last_snapshot,
    min(snapshot_at) AS first_snapshot
   FROM public.options_price_history
  WHERE (mark IS NOT NULL)
  GROUP BY underlying_symbol_id, strike, side, expiry;


create or replace view "public"."v_alpaca_health" as  SELECT symbol_id,
    timeframe,
    max(fetched_at) AS last_fetched_at,
    count(*) FILTER (WHERE (ts >= (now() - '1 day'::interval))) AS bars_24h
   FROM public.ohlc_bars_v2
  WHERE (provider = 'alpaca'::public.data_provider)
  GROUP BY symbol_id, timeframe;


CREATE OR REPLACE FUNCTION public.validate_ohlc_v2_write()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
declare
  today date := (now() at time zone 'utc')::date;
  bar_date date := (coalesce(new.ts, old.ts))::date;
begin
  -- Basic invariants
  if new is not null and old is not null then
    -- upsert/update: keep symbol_id/timeframe/ts stable
    if new.symbol_id <> old.symbol_id or new.timeframe <> old.timeframe or new.ts <> old.ts then
      raise exception 'immutable keys changed: symbol_id/timeframe/ts';
    end if;
  end if;

  if new is not null then
    -- forbid both flags at once
    if coalesce(new.is_intraday, false) and coalesce(new.is_forecast, false) then
      raise exception 'is_intraday and is_forecast cannot both be true';
    end if;

    -- Historical layer: strictly before today
    if coalesce(new.is_intraday, false) = false and coalesce(new.is_forecast, false) = false then
      if bar_date >= today then
        raise exception 'historical bars must be strictly before today (ts=%)', new.ts;
      end if;
    end if;

    -- Intraday layer: date is today
    if coalesce(new.is_intraday, false) = true then
      if bar_date <> today then
        raise exception 'intraday bars must be on today (UTC) (ts=%)', new.ts;
      end if;
    end if;

    -- Forecast layer: strictly after now
    if coalesce(new.is_forecast, false) = true then
      if new.ts <= now() at time zone 'utc' then
        raise exception 'forecast bars must be strictly in the future (ts=%)', new.ts;
      end if;
    end if;
  end if;

  return coalesce(new, old);
end;
$function$
;

grant delete on table "public"."project_members" to "anon";

grant insert on table "public"."project_members" to "anon";

grant references on table "public"."project_members" to "anon";

grant select on table "public"."project_members" to "anon";

grant trigger on table "public"."project_members" to "anon";

grant truncate on table "public"."project_members" to "anon";

grant update on table "public"."project_members" to "anon";

grant delete on table "public"."project_members" to "authenticated";

grant insert on table "public"."project_members" to "authenticated";

grant references on table "public"."project_members" to "authenticated";

grant select on table "public"."project_members" to "authenticated";

grant trigger on table "public"."project_members" to "authenticated";

grant truncate on table "public"."project_members" to "authenticated";

grant update on table "public"."project_members" to "authenticated";

grant delete on table "public"."project_members" to "service_role";

grant insert on table "public"."project_members" to "service_role";

grant references on table "public"."project_members" to "service_role";

grant select on table "public"."project_members" to "service_role";

grant trigger on table "public"."project_members" to "service_role";

grant truncate on table "public"."project_members" to "service_role";

grant update on table "public"."project_members" to "service_role";

grant delete on table "public"."provider_checkpoints" to "anon";

grant insert on table "public"."provider_checkpoints" to "anon";

grant references on table "public"."provider_checkpoints" to "anon";

grant select on table "public"."provider_checkpoints" to "anon";

grant trigger on table "public"."provider_checkpoints" to "anon";

grant truncate on table "public"."provider_checkpoints" to "anon";

grant update on table "public"."provider_checkpoints" to "anon";

grant delete on table "public"."provider_checkpoints" to "authenticated";

grant insert on table "public"."provider_checkpoints" to "authenticated";

grant references on table "public"."provider_checkpoints" to "authenticated";

grant select on table "public"."provider_checkpoints" to "authenticated";

grant trigger on table "public"."provider_checkpoints" to "authenticated";

grant truncate on table "public"."provider_checkpoints" to "authenticated";

grant update on table "public"."provider_checkpoints" to "authenticated";

grant delete on table "public"."provider_checkpoints" to "service_role";

grant insert on table "public"."provider_checkpoints" to "service_role";

grant references on table "public"."provider_checkpoints" to "service_role";

grant select on table "public"."provider_checkpoints" to "service_role";

grant trigger on table "public"."provider_checkpoints" to "service_role";

grant truncate on table "public"."provider_checkpoints" to "service_role";

grant update on table "public"."provider_checkpoints" to "service_role";

grant delete on table "public"."rate_buckets" to "anon";

grant insert on table "public"."rate_buckets" to "anon";

grant references on table "public"."rate_buckets" to "anon";

grant select on table "public"."rate_buckets" to "anon";

grant trigger on table "public"."rate_buckets" to "anon";

grant truncate on table "public"."rate_buckets" to "anon";

grant update on table "public"."rate_buckets" to "anon";

grant delete on table "public"."rate_buckets" to "authenticated";

grant insert on table "public"."rate_buckets" to "authenticated";

grant references on table "public"."rate_buckets" to "authenticated";

grant select on table "public"."rate_buckets" to "authenticated";

grant trigger on table "public"."rate_buckets" to "authenticated";

grant truncate on table "public"."rate_buckets" to "authenticated";

grant update on table "public"."rate_buckets" to "authenticated";

grant delete on table "public"."rate_buckets" to "service_role";

grant insert on table "public"."rate_buckets" to "service_role";

grant references on table "public"."rate_buckets" to "service_role";

grant select on table "public"."rate_buckets" to "service_role";

grant trigger on table "public"."rate_buckets" to "service_role";

grant truncate on table "public"."rate_buckets" to "service_role";

grant update on table "public"."rate_buckets" to "service_role";

grant delete on table "public"."symbol_backfill_queue" to "anon";

grant insert on table "public"."symbol_backfill_queue" to "anon";

grant references on table "public"."symbol_backfill_queue" to "anon";

grant select on table "public"."symbol_backfill_queue" to "anon";

grant trigger on table "public"."symbol_backfill_queue" to "anon";

grant truncate on table "public"."symbol_backfill_queue" to "anon";

grant update on table "public"."symbol_backfill_queue" to "anon";

grant delete on table "public"."symbol_backfill_queue" to "authenticated";

grant insert on table "public"."symbol_backfill_queue" to "authenticated";

grant references on table "public"."symbol_backfill_queue" to "authenticated";

grant select on table "public"."symbol_backfill_queue" to "authenticated";

grant trigger on table "public"."symbol_backfill_queue" to "authenticated";

grant truncate on table "public"."symbol_backfill_queue" to "authenticated";

grant update on table "public"."symbol_backfill_queue" to "authenticated";

grant delete on table "public"."symbol_backfill_queue" to "service_role";

grant insert on table "public"."symbol_backfill_queue" to "service_role";

grant references on table "public"."symbol_backfill_queue" to "service_role";

grant select on table "public"."symbol_backfill_queue" to "service_role";

grant trigger on table "public"."symbol_backfill_queue" to "service_role";

grant truncate on table "public"."symbol_backfill_queue" to "service_role";

grant update on table "public"."symbol_backfill_queue" to "service_role";


  create policy "corporate_actions_select_all"
  on "public"."corporate_actions"
  as permissive
  for select
  to anon, authenticated
using (true);



  create policy "coverage_status_select_all"
  on "public"."coverage_status"
  as permissive
  for select
  to anon, authenticated
using (true);



  create policy "forecast_evaluations_select_all"
  on "public"."forecast_evaluations"
  as permissive
  for select
  to anon, authenticated
using (true);



  create policy "read indicators"
  on "public"."indicator_values"
  as permissive
  for select
  to public
using (true);



  create policy "service writes indicators"
  on "public"."indicator_values"
  as permissive
  for all
  to public
using ((auth.role() = 'service_role'::text));



  create policy "job_queue_service_all"
  on "public"."job_queue"
  as permissive
  for all
  to service_role
using (true)
with check (true);



  create policy "market_calendar_select_all"
  on "public"."market_calendar"
  as permissive
  for select
  to anon, authenticated
using (true);



  create policy "model_performance_history_select_all"
  on "public"."model_performance_history"
  as permissive
  for select
  to anon, authenticated
using (true);



  create policy "model_weights_select_all"
  on "public"."model_weights"
  as permissive
  for select
  to anon, authenticated
using (true);



  create policy "news_read"
  on "public"."news_items"
  as permissive
  for select
  to authenticated
using (true);



  create policy "ohlc_bars_v2_select_all"
  on "public"."ohlc_bars_v2"
  as permissive
  for select
  to anon, authenticated
using (true);



  create policy "ohlc_read"
  on "public"."ohlc_bars_v2"
  as permissive
  for select
  to authenticated
using (true);



  create policy "options_snapshots_select_all"
  on "public"."options_snapshots"
  as permissive
  for select
  to anon, authenticated
using (true);



  create policy "quotes_read"
  on "public"."quotes"
  as permissive
  for select
  to authenticated
using (true);



  create policy "ranking_jobs_service_all"
  on "public"."ranking_jobs"
  as permissive
  for all
  to service_role
using (true)
with check (true);



  create policy "Service role full access on symbol_backfill_queue"
  on "public"."symbol_backfill_queue"
  as permissive
  for all
  to service_role
using (true)
with check (true);



  create policy "symbols_read"
  on "public"."symbols"
  as permissive
  for select
  to authenticated
using (true);



  create policy "symbols_select_all"
  on "public"."symbols"
  as permissive
  for select
  to anon, authenticated
using (true);



  create policy "watchlist_items_delete"
  on "public"."watchlist_items"
  as permissive
  for delete
  to authenticated
using ((EXISTS ( SELECT 1
   FROM public.watchlists w
  WHERE ((w.id = watchlist_items.watchlist_id) AND (w.user_id = ( SELECT auth.uid() AS uid))))));



  create policy "watchlist_items_select"
  on "public"."watchlist_items"
  as permissive
  for select
  to authenticated
using ((EXISTS ( SELECT 1
   FROM public.watchlists w
  WHERE ((w.id = watchlist_items.watchlist_id) AND (w.user_id = ( SELECT auth.uid() AS uid))))));



  create policy "watchlist_items_update"
  on "public"."watchlist_items"
  as permissive
  for update
  to authenticated
using ((EXISTS ( SELECT 1
   FROM public.watchlists w
  WHERE ((w.id = watchlist_items.watchlist_id) AND (w.user_id = ( SELECT auth.uid() AS uid))))))
with check ((EXISTS ( SELECT 1
   FROM public.watchlists w
  WHERE ((w.id = watchlist_items.watchlist_id) AND (w.user_id = ( SELECT auth.uid() AS uid))))));



  create policy "watchlist_items_write"
  on "public"."watchlist_items"
  as permissive
  for insert
  to authenticated
with check ((EXISTS ( SELECT 1
   FROM public.watchlists w
  WHERE ((w.id = watchlist_items.watchlist_id) AND (w.user_id = ( SELECT auth.uid() AS uid))))));



  create policy "watchlists_delete"
  on "public"."watchlists"
  as permissive
  for delete
  to authenticated
using ((( SELECT auth.uid() AS uid) = user_id));



  create policy "watchlists_insert"
  on "public"."watchlists"
  as permissive
  for insert
  to authenticated
with check ((( SELECT auth.uid() AS uid) = user_id));



  create policy "watchlists_owner_read"
  on "public"."watchlists"
  as permissive
  for select
  to authenticated
using ((user_id = ( SELECT auth.uid() AS uid)));



  create policy "watchlists_select"
  on "public"."watchlists"
  as permissive
  for select
  to authenticated
using ((( SELECT auth.uid() AS uid) = user_id));



  create policy "watchlists_update"
  on "public"."watchlists"
  as permissive
  for update
  to authenticated
using ((( SELECT auth.uid() AS uid) = user_id))
with check ((( SELECT auth.uid() AS uid) = user_id));



  create policy "scanner_alerts_select_own"
  on "public"."scanner_alerts"
  as permissive
  for select
  to authenticated
using ((( SELECT auth.uid() AS uid) = user_id));



  create policy "scanner_alerts_update_own"
  on "public"."scanner_alerts"
  as permissive
  for update
  to authenticated
using ((( SELECT auth.uid() AS uid) = user_id))
with check ((( SELECT auth.uid() AS uid) = user_id));



  create policy "watchlists_delete_own"
  on "public"."watchlists"
  as permissive
  for delete
  to authenticated
using ((( SELECT auth.uid() AS uid) = user_id));



  create policy "watchlists_insert_own"
  on "public"."watchlists"
  as permissive
  for insert
  to authenticated
with check ((( SELECT auth.uid() AS uid) = user_id));



  create policy "watchlists_select_own"
  on "public"."watchlists"
  as permissive
  for select
  to authenticated
using ((( SELECT auth.uid() AS uid) = user_id));



  create policy "watchlists_update_own"
  on "public"."watchlists"
  as permissive
  for update
  to authenticated
using ((( SELECT auth.uid() AS uid) = user_id))
with check ((( SELECT auth.uid() AS uid) = user_id));


CREATE TRIGGER sync_backfill_chunks_symbol_id BEFORE INSERT OR UPDATE ON public.backfill_chunks FOR EACH ROW EXECUTE FUNCTION public.sync_symbol_id_from_ticker();

CREATE TRIGGER sync_backfill_jobs_symbol_id BEFORE INSERT OR UPDATE ON public.backfill_jobs FOR EACH ROW EXECUTE FUNCTION public.sync_symbol_id_from_ticker();

CREATE TRIGGER sync_coverage_status_symbol_id BEFORE INSERT OR UPDATE ON public.coverage_status FOR EACH ROW EXECUTE FUNCTION public.sync_symbol_id_from_ticker();

CREATE TRIGGER sync_forecast_jobs_symbol_id BEFORE INSERT OR UPDATE ON public.forecast_jobs FOR EACH ROW EXECUTE FUNCTION public.sync_symbol_id_from_ticker();

CREATE TRIGGER sync_ga_optimization_runs_symbol_id BEFORE INSERT OR UPDATE ON public.ga_optimization_runs FOR EACH ROW EXECUTE FUNCTION public.sync_symbol_id_from_ticker();

CREATE TRIGGER sync_ga_strategy_params_symbol_id BEFORE INSERT OR UPDATE ON public.ga_strategy_params FOR EACH ROW EXECUTE FUNCTION public.sync_symbol_id_from_ticker();

CREATE TRIGGER sync_job_definitions_symbol_id BEFORE INSERT OR UPDATE ON public.job_definitions FOR EACH ROW EXECUTE FUNCTION public.sync_symbol_id_from_ticker();

CREATE TRIGGER sync_job_queue_symbol_id BEFORE INSERT OR UPDATE ON public.job_queue FOR EACH ROW EXECUTE FUNCTION public.sync_symbol_id_from_ticker();

CREATE TRIGGER trg_ohlc_bars_v2_alpaca_ts_ins BEFORE INSERT ON public.ohlc_bars_v2 FOR EACH ROW EXECUTE FUNCTION public.ohlc_bars_v2_alpaca_ts_trigger();

CREATE TRIGGER trg_ohlc_bars_v2_alpaca_ts_upd BEFORE UPDATE ON public.ohlc_bars_v2 FOR EACH ROW EXECUTE FUNCTION public.ohlc_bars_v2_alpaca_ts_trigger();

CREATE TRIGGER trg_validate_ohlc_v2_write BEFORE INSERT OR UPDATE ON public.ohlc_bars_v2 FOR EACH ROW EXECUTE FUNCTION public.validate_ohlc_v2_write();

CREATE TRIGGER sync_options_scrape_jobs_symbol_id BEFORE INSERT OR UPDATE ON public.options_scrape_jobs FOR EACH ROW EXECUTE FUNCTION public.sync_symbol_id_from_ticker();

CREATE TRIGGER sync_provider_checkpoints_symbol_id BEFORE INSERT OR UPDATE ON public.provider_checkpoints FOR EACH ROW EXECUTE FUNCTION public.sync_symbol_id_from_ticker();

CREATE TRIGGER sync_ranking_jobs_symbol_id BEFORE INSERT OR UPDATE ON public.ranking_jobs FOR EACH ROW EXECUTE FUNCTION public.sync_symbol_id_from_ticker();

CREATE TRIGGER sync_supertrend_signals_symbol_id BEFORE INSERT OR UPDATE ON public.supertrend_signals FOR EACH ROW EXECUTE FUNCTION public.sync_symbol_id_from_ticker();

CREATE TRIGGER trigger_queue_symbol_backfill AFTER INSERT ON public.watchlist_items FOR EACH ROW EXECUTE FUNCTION public.queue_symbol_backfill();

CREATE TRIGGER watchlist_auto_job_definition_trigger AFTER INSERT ON public.watchlist_items FOR EACH ROW EXECUTE FUNCTION public.trigger_job_definition_on_watchlist_add();


  create policy "project members can read artifacts"
  on "storage"."objects"
  as permissive
  for select
  to authenticated
using (((bucket_id = 'ml-artifacts'::text) AND (split_part(name, '/'::text, 1) IN ( SELECT pm.project_id
   FROM public.project_members pm
  WHERE (pm.user_id = ( SELECT auth.uid() AS uid))))));



  create policy "project members can update artifacts"
  on "storage"."objects"
  as permissive
  for update
  to authenticated
using (((bucket_id = 'ml-artifacts'::text) AND (split_part(name, '/'::text, 1) IN ( SELECT pm.project_id
   FROM public.project_members pm
  WHERE (pm.user_id = ( SELECT auth.uid() AS uid))))))
with check (((bucket_id = 'ml-artifacts'::text) AND (split_part(name, '/'::text, 1) IN ( SELECT pm.project_id
   FROM public.project_members pm
  WHERE (pm.user_id = ( SELECT auth.uid() AS uid))))));



  create policy "project members can write artifacts"
  on "storage"."objects"
  as permissive
  for insert
  to authenticated
with check (((bucket_id = 'ml-artifacts'::text) AND (split_part(name, '/'::text, 1) IN ( SELECT pm.project_id
   FROM public.project_members pm
  WHERE (pm.user_id = ( SELECT auth.uid() AS uid))))));



  create policy "reports_authenticated_delete"
  on "storage"."objects"
  as permissive
  for delete
  to authenticated
using (((bucket_id = 'reports'::text) AND ((storage.foldername(name))[1] = (( SELECT auth.uid() AS uid))::text)));



  create policy "reports_authenticated_insert"
  on "storage"."objects"
  as permissive
  for insert
  to authenticated
with check (((bucket_id = 'reports'::text) AND ((storage.foldername(name))[1] = (( SELECT auth.uid() AS uid))::text)));



