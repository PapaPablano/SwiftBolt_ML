-- Normalize intraday horizon casing for existing rows
UPDATE public.ml_forecasts_intraday
SET horizon = CASE
    WHEN LOWER(horizon) = '1d' THEN '1D'
    WHEN LOWER(horizon) = '15m' THEN '15m'
    WHEN LOWER(horizon) = '1h' THEN '1h'
    WHEN LOWER(horizon) = '4h' THEN '4h'
    WHEN LOWER(horizon) = '8h' THEN '8h'
    ELSE horizon
END
WHERE horizon IS NOT NULL;
