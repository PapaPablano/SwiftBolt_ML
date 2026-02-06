-- Fix: queue_symbol_backfill was inserting NEW.id (watchlist_items.id) into
-- data_jobs.symbol_id, causing FK violation. data_jobs.symbol_id must reference
-- symbols(id), i.e. NEW.symbol_id.

CREATE OR REPLACE FUNCTION public.queue_symbol_backfill()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $function$
BEGIN
  INSERT INTO public.data_jobs (job_type, symbol_id, ticker)
  VALUES ('backfill_h4', NEW.symbol_id, NEW.ticker);
  RETURN NEW;
END;
$function$;

COMMENT ON FUNCTION public.queue_symbol_backfill() IS 'Queues backfill job for new watchlist symbol; uses symbol_id (not watchlist row id).';
