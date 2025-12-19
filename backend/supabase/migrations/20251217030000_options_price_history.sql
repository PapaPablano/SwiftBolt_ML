-- Migration: Options Price History Tracking
-- Tracks historical prices, Greeks, and IV for options contracts over time
-- Enables strike price analysis and average price calculations

-- Create options_price_history table
CREATE TABLE IF NOT EXISTS options_price_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    underlying_symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    contract_symbol TEXT NOT NULL,
    expiry DATE NOT NULL,
    strike NUMERIC(10, 2) NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('call', 'put')),

    -- Pricing data
    bid NUMERIC(10, 2),
    ask NUMERIC(10, 2),
    mark NUMERIC(10, 2),
    last_price NUMERIC(10, 2),

    -- Greeks
    delta NUMERIC(6, 4),
    gamma NUMERIC(8, 6),
    theta NUMERIC(8, 6),
    vega NUMERIC(8, 6),
    rho NUMERIC(8, 6),
    implied_vol NUMERIC(6, 4),

    -- Volume/OI
    volume INTEGER,
    open_interest INTEGER,

    -- ML score from ranking (if available)
    ml_score NUMERIC(5, 4),

    -- Snapshot timestamp
    snapshot_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX idx_options_price_history_underlying ON options_price_history(underlying_symbol_id);
CREATE INDEX idx_options_price_history_contract ON options_price_history(contract_symbol);
CREATE INDEX idx_options_price_history_strike_expiry ON options_price_history(underlying_symbol_id, strike, expiry, side);
CREATE INDEX idx_options_price_history_snapshot ON options_price_history(snapshot_at DESC);

-- Composite index for strike price analysis queries
CREATE INDEX idx_options_price_history_analysis ON options_price_history(
    underlying_symbol_id,
    strike,
    side,
    snapshot_at DESC
);

-- Enable RLS
ALTER TABLE options_price_history ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Anyone can read (public data)
CREATE POLICY "Options price history is publicly readable"
    ON options_price_history
    FOR SELECT
    USING (true);

-- RLS Policy: Only service role can insert/update (automated jobs)
CREATE POLICY "Only service role can modify options price history"
    ON options_price_history
    FOR ALL
    USING (auth.role() = 'service_role');

-- Create view for strike price statistics
CREATE OR REPLACE VIEW strike_price_stats AS
SELECT
    underlying_symbol_id,
    strike,
    side,
    expiry,
    COUNT(*) as sample_count,
    AVG(mark) as avg_mark,
    STDDEV(mark) as stddev_mark,
    MIN(mark) as min_mark,
    MAX(mark) as max_mark,
    AVG(implied_vol) as avg_iv,
    MAX(snapshot_at) as last_snapshot,
    MIN(snapshot_at) as first_snapshot
FROM options_price_history
WHERE mark IS NOT NULL
GROUP BY underlying_symbol_id, strike, side, expiry;

-- Grant access to view
GRANT SELECT ON strike_price_stats TO anon, authenticated;

-- Function to capture options snapshot from current rankings
CREATE OR REPLACE FUNCTION capture_options_snapshot(p_symbol_id UUID)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_rows_inserted INTEGER;
BEGIN
    -- Insert current options_ranks data into history
    INSERT INTO options_price_history (
        underlying_symbol_id,
        contract_symbol,
        expiry,
        strike,
        side,
        bid,
        ask,
        mark,
        last_price,
        delta,
        gamma,
        theta,
        vega,
        rho,
        implied_vol,
        volume,
        open_interest,
        ml_score,
        snapshot_at
    )
    SELECT
        underlying_symbol_id,
        contract_symbol,
        expiry,
        strike,
        side,
        bid,
        ask,
        mark,
        last_price,
        delta,
        gamma,
        theta,
        vega,
        rho,
        implied_vol,
        volume,
        open_interest,
        ml_score,
        run_at
    FROM options_ranks
    WHERE underlying_symbol_id = p_symbol_id
    AND run_at IS NOT NULL;

    GET DIAGNOSTICS v_rows_inserted = ROW_COUNT;

    RETURN v_rows_inserted;
END;
$$;

-- Function to get strike price comparison across expirations
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
        AND oph.side = p_side::option_side
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
        AND orr.side = p_side::option_side
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

-- Cleanup function for old price history (keep 90 days)
CREATE OR REPLACE FUNCTION cleanup_old_price_history()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_rows_deleted INTEGER;
BEGIN
    DELETE FROM options_price_history
    WHERE snapshot_at < NOW() - INTERVAL '90 days';

    GET DIAGNOSTICS v_rows_deleted = ROW_COUNT;

    RETURN v_rows_deleted;
END;
$$;

COMMENT ON TABLE options_price_history IS 'Historical snapshots of options pricing and Greeks for trend analysis';
COMMENT ON FUNCTION capture_options_snapshot IS 'Captures current options_ranks data into price history for a given symbol';
COMMENT ON FUNCTION get_strike_price_comparison IS 'Returns strike price comparison across expirations with historical averages';
COMMENT ON FUNCTION cleanup_old_price_history IS 'Removes price history older than 90 days';
