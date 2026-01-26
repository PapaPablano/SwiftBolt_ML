-- Enforce supported forecast horizons only
-- Allowed horizons: 1D, 5D, 10D, 20D

-- Remove any existing rows with unsupported horizons
DELETE FROM public.ml_forecasts
WHERE horizon NOT IN ('1D', '5D', '10D', '20D');

-- Add a constraint to prevent future invalid horizons
ALTER TABLE public.ml_forecasts
  DROP CONSTRAINT IF EXISTS ml_forecasts_horizon_check;

ALTER TABLE public.ml_forecasts
  ADD CONSTRAINT ml_forecasts_horizon_check
  CHECK (horizon IN ('1D', '5D', '10D', '20D'));
