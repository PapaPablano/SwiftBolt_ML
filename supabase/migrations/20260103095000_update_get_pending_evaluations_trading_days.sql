-- Migration: Update get_pending_evaluations to use trading-day bars
-- Date: 2026-01-03
-- Description: Determines evaluation_due based on availability of the Nth future daily bar

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
        SELECT b.ts AS eval_ts
        FROM ohlc_bars b
        WHERE b.symbol_id = f.symbol_id
          AND b.timeframe = 'd1'
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
