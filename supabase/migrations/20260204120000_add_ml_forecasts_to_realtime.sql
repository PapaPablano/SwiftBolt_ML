-- Enable Realtime CDC for ml_forecasts so postgres_changes fire for binary (and other) forecast upserts.
DO $$
BEGIN
  ALTER PUBLICATION supabase_realtime ADD TABLE public.ml_forecasts;
EXCEPTION
  WHEN duplicate_object THEN
    -- already added
    NULL;
END $$;
