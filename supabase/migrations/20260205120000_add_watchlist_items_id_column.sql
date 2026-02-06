-- Fix: record "new" has no field "id" when inserting into watchlist_items.
-- Apply this and 20260205130000_add_watchlist_items_ticker_column.sql to the
-- Supabase project your app uses (Dashboard > SQL or: supabase link && supabase db push).
-- watchlist_items has composite PK (watchlist_id, symbol_id) and no id column;
-- some trigger or Realtime code expects NEW.id. Add id as a unique non-null column
-- so NEW.id exists, without changing the primary key.

ALTER TABLE public.watchlist_items
  ADD COLUMN IF NOT EXISTS id uuid NOT NULL DEFAULT gen_random_uuid();

-- Ensure uniqueness (one id per row)
CREATE UNIQUE INDEX IF NOT EXISTS idx_watchlist_items_id
  ON public.watchlist_items (id);

COMMENT ON COLUMN public.watchlist_items.id IS 'Surrogate id for triggers/Realtime; table primary key remains (watchlist_id, symbol_id).';
