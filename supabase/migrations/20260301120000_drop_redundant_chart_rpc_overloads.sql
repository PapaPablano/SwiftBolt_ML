-- Drop redundant get_chart_data_v2 overloads, keeping only the varchar overload
-- that properly aggregates h1/h4 from m15 base bars.
--
-- Problem: Three overloads exist with different p_timeframe types (text, varchar,
-- timeframe enum). PostgREST resolves string params to the "text" overload, which
-- queries h1/h4 rows directly from ohlc_bars_v2 instead of aggregating from m15.
-- This causes h1/h4 charts to show stale data when only m15 bars have been refreshed.
--
-- Fix: Drop the "text" and "timeframe" overloads. The remaining "varchar" overload:
-- - Aggregates h1/h4 from m15 bars (always fresh when intraday-live-refresh runs)
-- - Has proper provider priority (alpaca > polygon > yfinance > tradier)
-- - Returns forecast bars for d1/w1 timeframes
-- - Returns all needed columns (is_forecast, data_status, confidence_score, etc.)

-- Drop the "text" overload (simple, no m15 aggregation)
DROP FUNCTION IF EXISTS public.get_chart_data_v2(uuid, text, timestamptz, timestamptz);

-- Drop the "timeframe" enum overload (simplest, no provider filtering)
DROP FUNCTION IF EXISTS public.get_chart_data_v2(uuid, timeframe, timestamptz, timestamptz);

-- Verify: only the varchar overload should remain
-- SELECT pg_get_function_arguments(oid) FROM pg_proc WHERE proname = 'get_chart_data_v2';
