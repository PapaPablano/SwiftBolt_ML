-- Migration: Fix get_pending_evaluations to use ohlc_bars_v2
-- Date: 2026-01-21
-- Description: The function was querying the old ohlc_bars table which is no longer updated.
--              This migration updates it to use ohlc_bars_v2 which contains fresh Alpaca data.

DROP FUNCTION IF EXISTS get_pending_evaluations(TEXT);

CREATE OR REPLACE FUNCTION get_pending_evaluations(p_horizon TEXT DEFAULT '1D')
RETURNS TABLE (
    forecast_id UUID,
    symbol_id UUID,
    symbol TEXT,
    horizon TEXT,
    overall_label trend_label,
    confidence NUMERIC,
    points JSONB,
    created_at TIMESTAMPTZ,
    evaluation_due TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        f.id as forecast_id,
        f.symbol_id,
        s.ticker as symbol,
        f.horizon,
        f.overall_label,
        f.confidence,
        f.points,
        f.created_at,
        due.eval_ts as evaluation_due
    FROM ml_forecasts f
    JOIN symbols s ON f.symbol_id = s.id
    CROSS JOIN LATERAL (
        SELECT
            CASE
                WHEN f.horizon = '1D' THEN 1
                WHEN f.horizon = '1W' THEN 5
                WHEN f.horizon = '1M' THEN 20
                ELSE 1
            END AS steps
    ) p
    LEFT JOIN LATERAL (
        -- Use ohlc_bars_v2 (the active table with fresh data) instead of ohlc_bars
        SELECT b.ts AS eval_ts
        FROM ohlc_bars_v2 b
        WHERE b.symbol_id = f.symbol_id
          AND b.timeframe = 'd1'
          AND b.is_forecast = false
          AND b.ts > f.created_at
        ORDER BY b.ts ASC
        OFFSET (p.steps - 1)
        LIMIT 1
    ) due ON TRUE
    WHERE f.horizon = p_horizon
      AND due.eval_ts IS NOT NULL
      AND due.eval_ts <= NOW()
      AND NOT EXISTS (
        SELECT 1
        FROM forecast_evaluations e
        WHERE e.forecast_id = f.id
      )
    ORDER BY f.created_at ASC
    LIMIT 100;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_pending_evaluations(TEXT) IS 'Returns forecasts that are due for evaluation based on available OHLC data in ohlc_bars_v2';
