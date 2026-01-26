-- Add forecast_return if missing
ALTER TABLE public.ml_forecasts
  ADD COLUMN IF NOT EXISTS forecast_return DOUBLE PRECISION;

-- Normalize legacy horizons written by older jobs (recent only)
UPDATE public.ml_forecasts
SET horizon = CASE
  WHEN horizon IN ('1W', '5M') THEN '5D'
  WHEN horizon IN ('2W', '6M') THEN '10D'
  WHEN horizon IN ('1M') THEN '20D'
  WHEN horizon IN ('3M', '4M') THEN '20D'
  ELSE horizon
END
WHERE horizon IN ('1W', '2W', '5M', '6M', '1M', '3M', '4M')
  AND created_at >= NOW() - INTERVAL '7 days';

-- Remove older legacy horizons to keep the table clean
DELETE FROM public.ml_forecasts
WHERE horizon IN ('1W', '2W', '5M', '6M', '1M', '3M', '4M')
  AND created_at < NOW() - INTERVAL '7 days';
