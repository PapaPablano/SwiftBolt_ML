-- 20260117203000_coverage_health_and_seed_trigger.sql
-- Extend coverage monitoring views/RPCs and reintroduce job definition seeding trigger

begin;

-- -----------------------------------------------------------------------------
-- Coverage view focused on watchlist symbols across all required timeframes
-- -----------------------------------------------------------------------------
drop view if exists public.coverage_watchlist_status;

create or replace view public.coverage_watchlist_status as
with watchlist_symbols as (
  select distinct wi.symbol_id, s.ticker
  from public.watchlist_items wi
  join public.symbols s on s.id = wi.symbol_id
),
watchlist_timeframes as (
  select ws.symbol_id,
         ws.ticker,
         unnest(array['m15','h1','h4','d1','w1']) as timeframe
  from watchlist_symbols ws
)
select
  wtf.ticker as symbol,
  wtf.symbol_id,
  wtf.timeframe,
  cs.from_ts,
  cs.to_ts,
  cs.last_success_at,
  cs.last_rows_written,
  cs.last_provider,
  case
    when cs.last_success_at is null then null
    else extract(epoch from (now() - cs.last_success_at)) / 3600.0
  end as hours_since_success,
  provider_stats.alpaca_bars_last_24h,
  provider_stats.total_bars_last_24h,
  provider_stats.last_fetched_at
from watchlist_timeframes wtf
left join public.coverage_status cs
  on cs.timeframe::text = wtf.timeframe
  and (cs.symbol_id = wtf.symbol_id or cs.symbol = wtf.ticker)
left join lateral (
  select
    sum(case when o.provider = 'alpaca' then 1 else 0 end)
      filter (where o.ts >= (now() - interval '1 day')) as alpaca_bars_last_24h,
    count(*) filter (where o.ts >= (now() - interval '1 day')) as total_bars_last_24h,
    max(o.fetched_at) as last_fetched_at
  from public.ohlc_bars_v2 o
  where o.symbol_id = wtf.symbol_id
    and o.timeframe::text = wtf.timeframe
    and o.is_forecast = false
) provider_stats on true;

comment on view public.coverage_watchlist_status is
'Computed view that expands watchlist symbols across required timeframes and joins coverage_status/provider coverage telemetry.';

-- -----------------------------------------------------------------------------
-- RPC returning symbols/timeframes that violate coverage SLAs
-- -----------------------------------------------------------------------------
create or replace function public.get_watchlist_coverage_gaps(
  p_max_age_hours numeric default 6,
  p_min_bars_24h integer default 5
)
returns table (
  symbol text,
  timeframe text,
  hours_since_success numeric,
  alpaca_bars_last_24h bigint,
  total_bars_last_24h bigint,
  last_provider text,
  last_success_at timestamptz,
  last_fetched_at timestamptz
)
language sql
stable
as $$
  select
    symbol,
    timeframe,
    hours_since_success,
    coalesce(alpaca_bars_last_24h, 0)::bigint as alpaca_bars_last_24h,
    coalesce(total_bars_last_24h, 0)::bigint as total_bars_last_24h,
    last_provider,
    last_success_at,
    last_fetched_at
  from public.coverage_watchlist_status
  where hours_since_success is null
     or hours_since_success > p_max_age_hours
     or coalesce(alpaca_bars_last_24h, 0) < p_min_bars_24h
  order by symbol, timeframe;
$$;

comment on function public.get_watchlist_coverage_gaps(numeric, integer) is
'Returns watchlist symbol/timeframe pairs that exceed freshness thresholds or lack Alpaca coverage.';

-- -----------------------------------------------------------------------------
-- Reintroduce seed_job_definition_for_symbol + watchlist trigger
-- -----------------------------------------------------------------------------
drop trigger if exists watchlist_auto_job_definition_trigger on public.watchlist_items;
drop function if exists public.trigger_job_definition_on_watchlist_add();
drop function if exists public.seed_job_definition_for_symbol(uuid, text[]);

do $$
begin
  if not exists (
    select 1 from pg_proc where proname = 'seed_job_definition_for_symbol'
      and pronamespace = 'public'::regnamespace
  ) then
    -- no-op placeholder, real function recreated below
    null;
  end if;
end $$;

create or replace function public.seed_job_definition_for_symbol(
  p_symbol_id uuid,
  p_timeframes text[] default array['m15','h1','h4','d1','w1']
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_ticker text;
  v_timeframe text;
  v_job_type text;
  v_job_def_id uuid;
  v_results jsonb := '[]'::jsonb;
  v_job_result jsonb;
  v_normalized_timeframes text[];
begin
  select ticker into v_ticker from public.symbols where id = p_symbol_id;
  if v_ticker is null then
    raise exception 'Symbol with ID % not found', p_symbol_id;
  end if;

  if p_timeframes is null or array_length(p_timeframes, 1) is null then
    v_normalized_timeframes := array['m15','h1','h4','d1','w1'];
  else
    v_normalized_timeframes := p_timeframes;
  end if;

  foreach v_timeframe in array v_normalized_timeframes loop
    v_timeframe := lower(v_timeframe);
    v_timeframe := case v_timeframe
      when '15m' then 'm15'
      when '1h' then 'h1'
      when '4h' then 'h4'
      else v_timeframe
    end;

    exit when v_timeframe is null;
    if v_timeframe not in ('m15','h1','h4','d1','w1') then
      continue;
    end if;

    v_job_type := case when v_timeframe in ('m15','h1','h4') then 'fetch_intraday' else 'fetch_historical' end;

    begin
      insert into public.job_definitions (symbol, timeframe, job_type, window_days, priority, enabled, updated_at)
      values (v_ticker, v_timeframe, v_job_type, case when v_job_type = 'fetch_intraday' then 30 else 730 end, 150, true, now())
      on conflict (symbol, timeframe, job_type)
      do update set
        window_days = greatest(public.job_definitions.window_days, excluded.window_days),
        priority = greatest(public.job_definitions.priority, excluded.priority),
        enabled = true,
        updated_at = now()
      returning id into v_job_def_id;

      v_job_result := jsonb_build_object(
        'ticker', v_ticker,
        'timeframe', v_timeframe,
        'job_type', v_job_type,
        'job_def_id', v_job_def_id,
        'status', 'created'
      );
    exception when others then
      v_job_result := jsonb_build_object(
        'ticker', v_ticker,
        'timeframe', v_timeframe,
        'job_type', v_job_type,
        'status', 'error',
        'error', sqlerrm
      );
    end;

    v_results := v_results || v_job_result;
  end loop;

  return jsonb_build_object(
    'symbol_id', p_symbol_id,
    'ticker', v_ticker,
    'jobs', v_results
  );
end;
$$;

comment on function public.seed_job_definition_for_symbol(uuid, text[]) is
'Ensures job_definitions rows exist for the supplied symbol across requested timeframes.';

create or replace function public.trigger_job_definition_on_watchlist_add()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_result jsonb;
begin
  begin
    v_result := public.seed_job_definition_for_symbol(NEW.symbol_id, array['m15','h1','h4','d1','w1']);
    raise notice 'Auto job definition created: %', v_result;
  exception when others then
    raise warning 'Failed to create job definition for symbol_id %: %', NEW.symbol_id, sqlerrm;
  end;
  return NEW;
end;
$$;

create trigger watchlist_auto_job_definition_trigger
  after insert on public.watchlist_items
  for each row
  execute function public.trigger_job_definition_on_watchlist_add();

comment on trigger watchlist_auto_job_definition_trigger on public.watchlist_items is
'Automatically seeds job definitions for new watchlist symbols across required timeframes.';

commit;
