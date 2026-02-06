-- Add is_active column to symbols for soft filtering
ALTER TABLE public.symbols ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;
COMMENT ON COLUMN public.symbols.is_active IS 'When false, symbol is excluded from backfill and regime analysis';
