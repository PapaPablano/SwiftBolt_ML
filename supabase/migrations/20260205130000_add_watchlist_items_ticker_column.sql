-- Fix: record "new" has no field "ticker" when inserting into watchlist_items.
-- Realtime or downstream code expects NEW.ticker. Add ticker and sync from symbols.

ALTER TABLE public.watchlist_items
  ADD COLUMN IF NOT EXISTS ticker text;

-- Backfill existing rows
UPDATE public.watchlist_items wi
SET ticker = s.ticker
FROM public.symbols s
WHERE wi.symbol_id = s.id AND wi.ticker IS NULL;

-- Trigger: keep ticker in sync from symbols on INSERT/UPDATE
CREATE OR REPLACE FUNCTION public.sync_watchlist_item_ticker()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  SELECT s.ticker INTO NEW.ticker
  FROM symbols s
  WHERE s.id = NEW.symbol_id;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS sync_watchlist_item_ticker_trigger ON public.watchlist_items;
CREATE TRIGGER sync_watchlist_item_ticker_trigger
  BEFORE INSERT OR UPDATE OF symbol_id ON public.watchlist_items
  FOR EACH ROW
  EXECUTE FUNCTION public.sync_watchlist_item_ticker();

-- Run trigger once for any rows still null (e.g. symbol_id not in symbols yet)
UPDATE public.watchlist_items wi
SET ticker = s.ticker
FROM public.symbols s
WHERE wi.symbol_id = s.id AND wi.ticker IS NULL;

COMMENT ON COLUMN public.watchlist_items.ticker IS 'Denormalized from symbols.ticker for Realtime/triggers; kept in sync by sync_watchlist_item_ticker_trigger.';
