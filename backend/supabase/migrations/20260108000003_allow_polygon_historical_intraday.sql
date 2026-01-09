-- Migration: Allow Polygon to write historical intraday data
-- Purpose: Enable 2-year backfill of m15/h1/h4 bars from Polygon
-- Date: 2026-01-08

-- Update validation trigger to allow Polygon historical intraday
CREATE OR REPLACE FUNCTION validate_ohlc_v2_write()
RETURNS TRIGGER AS $$
DECLARE
  today_date DATE := CURRENT_DATE;
  bar_date DATE := DATE(NEW.ts);
BEGIN
  -- Rule 1: Historical (Polygon) can write to dates BEFORE today
  -- UPDATED: Allow Polygon to write intraday data for HISTORICAL dates
  IF NEW.provider = 'polygon' THEN
    IF bar_date >= today_date THEN
      RAISE EXCEPTION 'Polygon historical data cannot write to today or future dates. Bar date: %, Today: %', bar_date, today_date;
    END IF;
    -- REMOVED: Old restriction that Polygon cannot be intraday
    -- Now allowed: Polygon can write historical intraday bars (m15/h1/h4) for dates before today
    IF NEW.is_forecast = true THEN
      RAISE EXCEPTION 'Polygon historical data cannot be marked as forecast';
    END IF;
  END IF;

  -- Rule 2: Intraday (Tradier) can only write to TODAY
  IF NEW.provider = 'tradier' THEN
    IF bar_date != today_date THEN
      RAISE EXCEPTION 'Tradier intraday data must be for today only. Bar date: %, Today: %', bar_date, today_date;
    END IF;
    IF NEW.is_intraday = false THEN
      RAISE EXCEPTION 'Tradier data must be marked as intraday';
    END IF;
    IF NEW.is_forecast = true THEN
      RAISE EXCEPTION 'Tradier intraday data cannot be marked as forecast';
    END IF;
  END IF;

  -- Rule 3: Forecasts (ML) can only write to FUTURE dates
  IF NEW.provider = 'ml_forecast' THEN
    IF bar_date <= today_date THEN
      RAISE EXCEPTION 'ML forecasts must be for future dates only. Bar date: %, Today: %', bar_date, today_date;
    END IF;
    IF NEW.is_forecast = false THEN
      RAISE EXCEPTION 'ML forecast data must be marked as forecast';
    END IF;
    IF NEW.is_intraday = true THEN
      RAISE EXCEPTION 'ML forecast data cannot be marked as intraday';
    END IF;
    -- Forecasts should have confidence bands
    IF NEW.upper_band IS NULL OR NEW.lower_band IS NULL THEN
      RAISE EXCEPTION 'ML forecasts must include upper_band and lower_band';
    END IF;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION validate_ohlc_v2_write IS
'Validates data layer separation rules:
- Polygon: Historical data (including intraday) for dates BEFORE today
- Tradier: Real-time intraday data for TODAY only
- ML: Forecasts for FUTURE dates only';
