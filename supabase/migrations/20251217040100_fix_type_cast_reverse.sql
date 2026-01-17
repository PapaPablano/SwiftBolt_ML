-- Fix type casting in get_strike_price_comparison function
-- Cast the option_side column to TEXT instead of casting parameter to enum

CREATE OR REPLACE FUNCTION get_strike_price_comparison(
    p_symbol_id UUID,
    p_strike NUMERIC,
    p_side TEXT,
    p_lookback_days INTEGER DEFAULT 30
)
RETURNS TABLE (
    expiry DATE,
    current_mark NUMERIC,
    avg_mark NUMERIC,
    pct_diff_from_avg NUMERIC,
    sample_count BIGINT,
    min_mark NUMERIC,
    max_mark NUMERIC,
    current_iv NUMERIC,
    avg_iv NUMERIC
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    WITH historical_stats AS (
        SELECT
            oph.expiry,
            AVG(oph.mark) as avg_mark,
            COUNT(*) as sample_count,
            MIN(oph.mark) as min_mark,
            MAX(oph.mark) as max_mark,
            AVG(oph.implied_vol) as avg_iv
        FROM options_price_history oph
        WHERE oph.underlying_symbol_id = p_symbol_id
        AND oph.strike = p_strike
        AND oph.side::text = p_side
        AND oph.snapshot_at >= NOW() - (p_lookback_days || ' days')::INTERVAL
        AND oph.mark IS NOT NULL
        GROUP BY oph.expiry
    ),
    current_prices AS (
        SELECT
            orr.expiry,
            orr.mark as current_mark,
            orr.implied_vol as current_iv
        FROM options_ranks orr
        WHERE orr.underlying_symbol_id = p_symbol_id
        AND orr.strike = p_strike
        AND orr.side::text = p_side
    )
    SELECT
        COALESCE(cp.expiry, hs.expiry) as expiry,
        cp.current_mark,
        hs.avg_mark,
        CASE
            WHEN hs.avg_mark > 0 THEN
                ((cp.current_mark - hs.avg_mark) / hs.avg_mark * 100)
            ELSE NULL
        END as pct_diff_from_avg,
        hs.sample_count,
        hs.min_mark,
        hs.max_mark,
        cp.current_iv,
        hs.avg_iv
    FROM current_prices cp
    FULL OUTER JOIN historical_stats hs ON cp.expiry = hs.expiry
    ORDER BY expiry;
END;
$$;
