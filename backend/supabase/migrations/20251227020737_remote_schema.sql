create schema if not exists "pgmq";

create extension if not exists "pgmq" with schema "pgmq";

drop policy "Authenticated users can read ml_features" on "public"."ml_features";

drop policy "Service role manages ml_features" on "public"."ml_features";

drop policy "options_ranks_select_anon" on "public"."options_ranks";

drop policy "retention_policies_authenticated_read" on "public"."retention_policies";

drop policy "retention_policies_service_role_all" on "public"."retention_policies";

drop policy "symbols_select_anon" on "public"."symbols";

revoke delete on table "public"."ml_features" from "anon";

revoke insert on table "public"."ml_features" from "anon";

revoke references on table "public"."ml_features" from "anon";

revoke select on table "public"."ml_features" from "anon";

revoke trigger on table "public"."ml_features" from "anon";

revoke truncate on table "public"."ml_features" from "anon";

revoke update on table "public"."ml_features" from "anon";

revoke delete on table "public"."ml_features" from "authenticated";

revoke insert on table "public"."ml_features" from "authenticated";

revoke references on table "public"."ml_features" from "authenticated";

revoke select on table "public"."ml_features" from "authenticated";

revoke trigger on table "public"."ml_features" from "authenticated";

revoke truncate on table "public"."ml_features" from "authenticated";

revoke update on table "public"."ml_features" from "authenticated";

revoke delete on table "public"."ml_features" from "service_role";

revoke insert on table "public"."ml_features" from "service_role";

revoke references on table "public"."ml_features" from "service_role";

revoke select on table "public"."ml_features" from "service_role";

revoke trigger on table "public"."ml_features" from "service_role";

revoke truncate on table "public"."ml_features" from "service_role";

revoke update on table "public"."ml_features" from "service_role";

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

alter table "public"."ml_features" drop constraint "ml_features_symbol_id_fkey";

alter table "public"."ml_features" drop constraint "ml_features_unique";

alter table "public"."retention_policies" drop constraint "retention_policies_table_name_key";

alter table "public"."supertrend_signals" drop constraint "supertrend_signals_outcome_check";

drop function if exists "public"."check_features_freshness"(p_symbol text, p_timeframe text);

drop function if exists "public"."generate_partition_ddl"(p_table_name text, p_start_date date, p_end_date date);

drop function if exists "public"."get_latest_ml_features"(p_symbol text, p_timeframe text, p_limit integer);

drop function if exists "public"."reset_stale_jobs"(p_stale_minutes integer);

drop function if exists "public"."run_retention_cleanup"();

drop view if exists "public"."v_job_queue_health";

drop view if exists "public"."v_table_stats";

drop function if exists "public"."worker_claim_job"(p_job_type text);

drop function if exists "public"."worker_complete_job"(p_job_id uuid, p_success boolean, p_error text);

drop function if exists "public"."worker_complete_ranking_job"(p_job_id uuid);

drop function if exists "public"."worker_fail_ranking_job"(p_job_id uuid, p_error_msg text);

drop function if exists "public"."worker_get_ranking_job"();

drop view if exists "public"."strike_price_stats";

alter table "public"."ml_features" drop constraint "ml_features_pkey";

alter table "public"."retention_policies" drop constraint "retention_policies_pkey";

drop index if exists "public"."idx_forecast_jobs_stale_check";

drop index if exists "public"."idx_forecast_jobs_status_priority";

drop index if exists "public"."idx_job_queue_stale_check";

drop index if exists "public"."idx_job_queue_type_status_priority";

drop index if exists "public"."idx_ml_features_computed";

drop index if exists "public"."idx_ml_features_symbol_tf";

drop index if exists "public"."idx_ml_features_ts";

drop index if exists "public"."idx_ml_forecasts_evaluation";

drop index if exists "public"."idx_options_price_history_expiry_analysis";

drop index if exists "public"."idx_options_price_history_partition_key";

drop index if exists "public"."idx_ranking_jobs_stale_check";

drop index if exists "public"."idx_ranking_jobs_symbol_status";

drop index if exists "public"."ml_features_pkey";

drop index if exists "public"."ml_features_unique";

drop index if exists "public"."retention_policies_pkey";

drop index if exists "public"."retention_policies_table_name_key";

drop table "public"."ml_features";

drop table "public"."retention_policies";

alter table "public"."ml_forecasts" drop column "composite_signal";

alter table "public"."ml_forecasts" drop column "indicator_scores";

alter table "public"."ml_forecasts" alter column "supertrend_factor" set data type double precision using "supertrend_factor"::double precision;

alter table "public"."ml_forecasts" alter column "training_stats" set default '{}'::jsonb;

alter table "public"."ml_forecasts" alter column "training_stats" set not null;

alter table "public"."options_chain_snapshots" add column "ml_score" numeric(5,4);

alter table "public"."options_price_history" drop column "snapshot_date";

alter table "public"."options_ranks" drop column "supertrend_factor";

alter table "public"."options_ranks" drop column "supertrend_performance";

alter table "public"."options_ranks" drop column "trend_analysis";

alter table "public"."options_ranks" drop column "trend_confidence";

alter table "public"."options_ranks" drop column "trend_label";

CREATE INDEX idx_options_snapshots_ml_score ON public.options_chain_snapshots USING btree (ml_score DESC) WHERE (ml_score IS NOT NULL);

alter table "public"."options_chain_snapshots" add constraint "options_chain_snapshots_ml_score_check" CHECK (((ml_score >= (0)::numeric) AND (ml_score <= (1)::numeric))) not valid;

alter table "public"."options_chain_snapshots" validate constraint "options_chain_snapshots_ml_score_check";

alter table "public"."supertrend_signals" add constraint "supertrend_signals_outcome_check" CHECK (((outcome)::text = ANY ((ARRAY['WIN'::character varying, 'LOSS'::character varying, 'OPEN'::character varying])::text[]))) not valid;

alter table "public"."supertrend_signals" validate constraint "supertrend_signals_outcome_check";

set check_function_bodies = off;

create or replace view "public"."options_validation_data" as  WITH ranked_snapshots AS (
         SELECT ocs.id,
            ocs.underlying_symbol_id,
            s.ticker AS underlying_symbol,
            ocs.expiry,
            ocs.strike,
            ocs.side,
            ocs.mark,
            ocs.ml_score,
            ocs.snapshot_date,
            ocs.implied_vol,
            ocs.delta,
            lead(ocs.mark) OVER (PARTITION BY ocs.underlying_symbol_id, ocs.expiry, ocs.strike, ocs.side ORDER BY ocs.snapshot_date) AS next_mark,
            lead(ocs.snapshot_date) OVER (PARTITION BY ocs.underlying_symbol_id, ocs.expiry, ocs.strike, ocs.side ORDER BY ocs.snapshot_date) AS next_date
           FROM (public.options_chain_snapshots ocs
             JOIN public.symbols s ON ((ocs.underlying_symbol_id = s.id)))
          WHERE ((ocs.ml_score IS NOT NULL) AND (ocs.mark IS NOT NULL) AND (ocs.mark > (0)::numeric))
        )
 SELECT snapshot_date AS ranking_date,
    underlying_symbol,
    underlying_symbol_id,
    expiry,
    strike,
    side,
    mark AS entry_price,
    ml_score,
    next_mark AS exit_price,
    next_date,
        CASE
            WHEN ((next_mark IS NOT NULL) AND (mark > (0)::numeric)) THEN ((next_mark - mark) / mark)
            ELSE NULL::numeric
        END AS forward_return,
        CASE
            WHEN (next_date = (snapshot_date + 1)) THEN true
            ELSE false
        END AS is_consecutive_day
   FROM ranked_snapshots
  WHERE (next_mark IS NOT NULL);


CREATE OR REPLACE FUNCTION public.refresh_watchlist_data()
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
DECLARE
    symbol_record RECORD;
BEGIN
    -- Loop through all symbols in any watchlist
    FOR symbol_record IN 
        SELECT DISTINCT s.ticker, s.id as symbol_id
        FROM watchlist_items wi
        JOIN symbols s ON s.id = wi.symbol_id
    LOOP
        -- Queue a forecast job for each symbol (worker already handles this)
        INSERT INTO job_queue (job_type, symbol, status, priority, payload)
        VALUES (
            'forecast',
            symbol_record.ticker,
            'pending',
            2,  -- Medium-high priority
            jsonb_build_object(
                'symbol_id', symbol_record.symbol_id,
                'horizons', ARRAY['1D', '1W'],
                'triggered_by', 'pg_cron_hourly'
            )
        )
        ON CONFLICT DO NOTHING;  -- Avoid duplicate jobs
        
        RAISE NOTICE 'Queued forecast for %', symbol_record.ticker;
    END LOOP;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.refresh_watchlist_options()
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
DECLARE
    symbol_record RECORD;
BEGIN
    -- Loop through all symbols in any watchlist
    FOR symbol_record IN 
        SELECT DISTINCT s.ticker
        FROM watchlist_items wi
        JOIN symbols s ON s.id = wi.symbol_id
    LOOP
        -- Queue a ranking job in the ranking_jobs table (what ranking_job_worker expects)
        INSERT INTO ranking_jobs (symbol, status, priority, requested_by)
        VALUES (
            symbol_record.ticker,
            'pending',
            1,  -- High priority for scheduled jobs
            'pg_cron_hourly'
        )
        ON CONFLICT DO NOTHING;
        
        RAISE NOTICE 'Queued options ranking for %', symbol_record.ticker;
    END LOOP;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.claim_next_job(p_job_type text DEFAULT NULL::text)
 RETURNS TABLE(job_id uuid, job_type text, symbol text, payload jsonb)
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_job_id UUID;
BEGIN
    SELECT j.id INTO v_job_id
    FROM job_queue j
    WHERE j.status = 'pending'
      AND (p_job_type IS NULL OR j.job_type = p_job_type)
      AND j.attempts < j.max_attempts
    ORDER BY j.priority ASC, j.created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED;
    
    IF v_job_id IS NULL THEN
        RETURN;
    END IF;
    
    UPDATE job_queue
    SET status = 'processing',
        started_at = NOW(),
        attempts = attempts + 1
    WHERE id = v_job_id;
    
    RETURN QUERY
    SELECT j.id, j.job_type, j.symbol, j.payload
    FROM job_queue j
    WHERE j.id = v_job_id;
END;
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



  create policy "options_ranks_select_authenticated"
  on "public"."options_ranks"
  as permissive
  for select
  to authenticated
using (true);



  create policy "symbols_select_authenticated"
  on "public"."symbols"
  as permissive
  for select
  to authenticated
using (true);



