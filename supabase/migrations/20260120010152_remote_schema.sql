drop trigger if exists "update_orchestrator_heartbeat_updated_at" on "public"."orchestrator_heartbeat";

revoke delete on table "public"."orchestrator_heartbeat" from "anon";

revoke insert on table "public"."orchestrator_heartbeat" from "anon";

revoke references on table "public"."orchestrator_heartbeat" from "anon";

revoke select on table "public"."orchestrator_heartbeat" from "anon";

revoke trigger on table "public"."orchestrator_heartbeat" from "anon";

revoke truncate on table "public"."orchestrator_heartbeat" from "anon";

revoke update on table "public"."orchestrator_heartbeat" from "anon";

revoke delete on table "public"."orchestrator_heartbeat" from "authenticated";

revoke insert on table "public"."orchestrator_heartbeat" from "authenticated";

revoke references on table "public"."orchestrator_heartbeat" from "authenticated";

revoke select on table "public"."orchestrator_heartbeat" from "authenticated";

revoke trigger on table "public"."orchestrator_heartbeat" from "authenticated";

revoke truncate on table "public"."orchestrator_heartbeat" from "authenticated";

revoke update on table "public"."orchestrator_heartbeat" from "authenticated";

revoke delete on table "public"."orchestrator_heartbeat" from "service_role";

revoke insert on table "public"."orchestrator_heartbeat" from "service_role";

revoke references on table "public"."orchestrator_heartbeat" from "service_role";

revoke select on table "public"."orchestrator_heartbeat" from "service_role";

revoke trigger on table "public"."orchestrator_heartbeat" from "service_role";

revoke truncate on table "public"."orchestrator_heartbeat" from "service_role";

revoke update on table "public"."orchestrator_heartbeat" from "service_role";

alter table "public"."orchestrator_heartbeat" drop constraint "orchestrator_heartbeat_status_check";

alter table "public"."supertrend_signals" drop constraint "supertrend_signals_outcome_check";

drop view if exists "public"."coverage_watchlist_status";

drop function if exists "public"."get_watchlist_coverage_gaps"(p_max_age_hours numeric, p_min_bars_24h integer);

drop view if exists "public"."latest_forecast_summary";

drop view if exists "public"."v_latest_sr_levels";

alter table "public"."orchestrator_heartbeat" drop constraint "orchestrator_heartbeat_pkey";

drop index if exists "public"."orchestrator_heartbeat_last_seen_idx";

drop index if exists "public"."orchestrator_heartbeat_pkey";

drop table "public"."orchestrator_heartbeat";

alter table "public"."indicator_values" add column "rsi_14" double precision;

alter table "public"."indicator_values" alter column "id" drop default;

alter table "public"."indicator_values" alter column "id" add generated always as identity;

alter table "public"."indicator_values" alter column "id" set data type bigint using "id"::bigint;

alter table "public"."ml_forecasts" add column "updated_at" timestamp with time zone default now();

alter table "public"."sr_levels" drop column "logistic_resistance_slope";

alter table "public"."sr_levels" drop column "logistic_support_slope";

alter table "public"."sr_levels" drop column "pivot_confidence";

alter table "public"."sr_levels" drop column "resistance_methods_agreeing";

alter table "public"."sr_levels" drop column "support_methods_agreeing";

CREATE INDEX idx_indicator_values_rsi_14 ON public.indicator_values USING btree (rsi_14) WHERE (rsi_14 IS NOT NULL);

alter table "public"."supertrend_signals" add constraint "supertrend_signals_outcome_check" CHECK (((outcome)::text = ANY ((ARRAY['WIN'::character varying, 'LOSS'::character varying, 'OPEN'::character varying])::text[]))) not valid;

alter table "public"."supertrend_signals" validate constraint "supertrend_signals_outcome_check";

set check_function_bodies = off;

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
      AND o.timeframe = p_timeframe::timeframe
      AND o.provider = 'alpaca'
      AND o.is_forecast = false
    ORDER BY o.ts
  )
  SELECT
    b.ts as gap_start,
    b.next_ts as gap_end,
    b.gap_hrs as gap_hours
  FROM bars_with_next b
  WHERE b.gap_hrs > p_max_gap_hours
  ORDER BY b.gap_hrs DESC;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.get_ohlc_coverage_stats(p_symbol text, p_timeframe text)
 RETURNS TABLE(bar_count bigint, oldest_bar timestamp with time zone, newest_bar timestamp with time zone, time_span_days integer)
 LANGUAGE plpgsql
AS $function$
BEGIN
  RETURN QUERY
  SELECT
    COUNT(*)::BIGINT as bar_count,
    MIN(o.ts)::TIMESTAMP WITH TIME ZONE as oldest_bar,
    MAX(o.ts)::TIMESTAMP WITH TIME ZONE as newest_bar,
    EXTRACT(DAY FROM (MAX(o.ts) - MIN(o.ts)))::INTEGER as time_span_days
  FROM ohlc_bars_v2 o
  WHERE o.symbol_id = (SELECT id FROM symbols WHERE ticker = p_symbol)
    AND o.timeframe = p_timeframe::timeframe
    AND o.provider = 'alpaca'
    AND o.is_forecast = false;
END;
$function$
;

create or replace view "public"."latest_forecast_summary" as  SELECT f.symbol_id,
    s.ticker,
    f.horizon,
    f.overall_label,
    f.confidence,
    f.run_at,
    f.points
   FROM (public.ml_forecasts f
     JOIN public.symbols s ON ((s.id = f.symbol_id)))
  WHERE (f.run_at = ( SELECT max(f2.run_at) AS max
           FROM public.ml_forecasts f2
          WHERE (f2.symbol_id = f.symbol_id)));


create or replace view "public"."market_intelligence_dashboard" as  SELECT 'Market Status'::text AS metric,
        CASE
            WHEN public.is_market_open() THEN 'OPEN'::text
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

create or replace view "public"."v_latest_sr_levels" as  SELECT DISTINCT ON (sr.symbol_id, sr.timeframe) sr.id,
    sr.symbol_id,
    sr.computed_at,
    sr.timeframe,
    sr.current_price,
    sr.pivot_pp,
    sr.pivot_r1,
    sr.pivot_r2,
    sr.pivot_r3,
    sr.pivot_s1,
    sr.pivot_s2,
    sr.pivot_s3,
    sr.fib_trend,
    sr.fib_range_high,
    sr.fib_range_low,
    sr.fib_0,
    sr.fib_236,
    sr.fib_382,
    sr.fib_500,
    sr.fib_618,
    sr.fib_786,
    sr.fib_100,
    sr.nearest_support,
    sr.nearest_resistance,
    sr.support_distance_pct,
    sr.resistance_distance_pct,
    sr.sr_ratio,
    sr.zigzag_swings,
    sr.kmeans_centers,
    sr.all_supports,
    sr.all_resistances,
    sr.period_high,
    sr.period_low,
    sr.lookback_bars,
    sr.computed_date,
    sr.created_at,
    s.ticker
   FROM (public.sr_levels sr
     JOIN public.symbols s ON ((sr.symbol_id = s.id)))
  ORDER BY sr.symbol_id, sr.timeframe, sr.computed_at DESC;



