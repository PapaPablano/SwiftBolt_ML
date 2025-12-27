-- Migration: Fix get_pending_evaluations return type mismatch
-- Date: 2025-12-27
-- Description: Aligns overall_label return type with trend_label enum to satisfy RPC contract

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
        CASE
            WHEN f.horizon = '1D' THEN f.created_at + INTERVAL '1 day'
            WHEN f.horizon = '1W' THEN f.created_at + INTERVAL '5 days'
            WHEN f.horizon = '1M' THEN f.created_at + INTERVAL '20 days'
            ELSE f.created_at + INTERVAL '1 day'
        END as evaluation_due
    FROM ml_forecasts f
    JOIN symbols s ON f.symbol_id = s.id
    WHERE f.horizon = p_horizon
    AND f.created_at < NOW() - (
        CASE
            WHEN f.horizon = '1D' THEN INTERVAL '1 day'
            WHEN f.horizon = '1W' THEN INTERVAL '5 days'
            WHEN f.horizon = '1M' THEN INTERVAL '20 days'
            ELSE INTERVAL '1 day'
        END
    )
    AND NOT EXISTS (
        SELECT 1 FROM forecast_evaluations e
        WHERE e.forecast_id = f.id
    )
    ORDER BY f.created_at ASC
    LIMIT 100;
END;
$$ LANGUAGE plpgsql;
