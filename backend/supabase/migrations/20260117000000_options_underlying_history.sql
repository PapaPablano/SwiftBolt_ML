-- Migration: Options Underlying History
-- Tracks 7-day price history and derived metrics for options' underlying assets
-- Enables momentum ranking with underlying price context

-- Create enum if not exists for data provider
DO $$ BEGIN
    CREATE TYPE data_provider AS ENUM ('alpaca', 'polygon', 'yfinance', 'tradier');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create options_underlying_history table
CREATE TABLE IF NOT EXISTS options_underlying_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign key to symbols table
    underlying_symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,

    -- Timeframe for this data point
    timeframe timeframe NOT NULL,

    -- Timestamp of the data point
    ts TIMESTAMPTZ NOT NULL,

    -- OHLCV data
    open NUMERIC(12, 4),
    high NUMERIC(12, 4),
    low NUMERIC(12, 4),
    close NUMERIC(12, 4),
    volume NUMERIC(20, 0),

    -- 7-day derived metrics
    ret_7d NUMERIC(8, 4),      -- 7-day return percentage
    vol_7d NUMERIC(8, 4),      -- 7-day annualized volatility
    drawdown_7d NUMERIC(8, 4), -- Max drawdown over 7 days
    gap_count INTEGER DEFAULT 0, -- Number of significant gaps

    -- Data source tracking
    source_provider data_provider DEFAULT 'alpaca',

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Composite unique constraint for idempotent upserts
CREATE UNIQUE INDEX IF NOT EXISTS idx_options_underlying_history_unique
    ON options_underlying_history(underlying_symbol_id, timeframe, ts);

-- Index for efficient queries by symbol and timeframe
CREATE INDEX IF NOT EXISTS idx_options_underlying_history_symbol_tf_ts
    ON options_underlying_history(underlying_symbol_id, timeframe, ts DESC);

-- Index for queries by symbol only
CREATE INDEX IF NOT EXISTS idx_options_underlying_history_symbol_ts
    ON options_underlying_history(underlying_symbol_id, ts DESC);

-- Enable RLS
ALTER TABLE options_underlying_history ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Anyone can read (public data)
CREATE POLICY "Options underlying history is publicly readable"
    ON options_underlying_history
    FOR SELECT
    USING (true);

-- RLS Policy: Only service role can insert/update (automated jobs)
CREATE POLICY "Only service role can modify options underlying history"
    ON options_underlying_history
    FOR ALL
    USING (auth.role() = 'service_role');

-- ============================================================================
-- Helper Functions
-- ============================================================================

-- Function to get underlying history for a symbol
CREATE OR REPLACE FUNCTION get_underlying_history(
    p_symbol_id UUID,
    p_timeframe TEXT,
    p_lookback_days INTEGER DEFAULT 7
)
RETURNS TABLE (
    ts TIMESTAMPTZ,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    volume NUMERIC,
    ret_7d NUMERIC,
    vol_7d NUMERIC,
    drawdown_7d NUMERIC,
    gap_count INTEGER
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        ouh.ts,
        ouh.open,
        ouh.high,
        ouh.low,
        ouh.close,
        ouh.volume,
        ouh.ret_7d,
        ouh.vol_7d,
        ouh.drawdown_7d,
        ouh.gap_count
    FROM options_underlying_history ouh
    WHERE ouh.underlying_symbol_id = p_symbol_id
      AND ouh.timeframe = p_timeframe::timeframe
      AND ouh.ts >= NOW() - (p_lookback_days || ' days')::INTERVAL
    ORDER BY ouh.ts DESC;
END;
$$;

-- Function to get latest 7-day metrics for an underlying
CREATE OR REPLACE FUNCTION get_latest_underlying_metrics(
    p_symbol_id UUID,
    p_timeframe TEXT DEFAULT 'd1'
)
RETURNS TABLE (
    ret_7d NUMERIC,
    vol_7d NUMERIC,
    drawdown_7d NUMERIC,
    gap_count INTEGER,
    last_ts TIMESTAMPTZ,
    bars_count INTEGER
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        ouh.ret_7d,
        ouh.vol_7d,
        ouh.drawdown_7d,
        ouh.gap_count,
        MAX(ouh.ts) AS last_ts,
        COUNT(*)::INTEGER AS bars_count
    FROM options_underlying_history ouh
    WHERE ouh.underlying_symbol_id = p_symbol_id
      AND ouh.timeframe = p_timeframe::timeframe
      AND ouh.ts >= NOW() - INTERVAL '7 days'
    GROUP BY ouh.ret_7d, ouh.vol_7d, ouh.drawdown_7d, ouh.gap_count
    ORDER BY last_ts DESC
    LIMIT 1;
END;
$$;

-- Function to get enriched options features with underlying metrics
CREATE OR REPLACE FUNCTION get_options_enriched_features(
    p_option_id UUID
)
RETURNS TABLE (
    contract_symbol TEXT,
    underlying_symbol_id UUID,
    strike NUMERIC,
    side TEXT,
    expiry DATE,
    -- Options rank fields
    ml_score NUMERIC,
    composite_rank NUMERIC,
    momentum_score NUMERIC,
    value_score NUMERIC,
    greeks_score NUMERIC,
    iv_rank NUMERIC,
    -- Underlying 7-day metrics
    underlying_ret_7d NUMERIC,
    underlying_vol_7d NUMERIC,
    underlying_drawdown_7d NUMERIC,
    underlying_gap_count INTEGER,
    -- Price history fields
    mark NUMERIC,
    implied_vol NUMERIC,
    delta NUMERIC,
    gamma NUMERIC,
    theta NUMERIC,
    vega NUMERIC
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_underlying_symbol_id UUID;
BEGIN
    -- Get underlying symbol ID from option
    SELECT orr.underlying_symbol_id INTO v_underlying_symbol_id
    FROM options_ranks orr
    WHERE orr.id = p_option_id;

    IF v_underlying_symbol_id IS NULL THEN
        RETURN;
    END IF;

    RETURN QUERY
    SELECT
        orr.contract_symbol,
        orr.underlying_symbol_id,
        orr.strike,
        orr.side::TEXT,
        orr.expiry,
        -- Options rank fields
        orr.ml_score,
        orr.composite_rank,
        orr.momentum_score,
        orr.value_score,
        orr.greeks_score,
        orr.iv_rank,
        -- Underlying 7-day metrics (latest)
        COALESCE(
            (SELECT ouh.ret_7d FROM options_underlying_history ouh
             WHERE ouh.underlying_symbol_id = v_underlying_symbol_id
               AND ouh.timeframe = 'd1'
             ORDER BY ouh.ts DESC LIMIT 1),
            0
        ) AS underlying_ret_7d,
        COALESCE(
            (SELECT ouh.vol_7d FROM options_underlying_history ouh
             WHERE ouh.underlying_symbol_id = v_underlying_symbol_id
               AND ouh.timeframe = 'd1'
             ORDER BY ouh.ts DESC LIMIT 1),
            0
        ) AS underlying_vol_7d,
        COALESCE(
            (SELECT ouh.drawdown_7d FROM options_underlying_history ouh
             WHERE ouh.underlying_symbol_id = v_underlying_symbol_id
               AND ouh.timeframe = 'd1'
             ORDER BY ouh.ts DESC LIMIT 1),
            0
        ) AS underlying_drawdown_7d,
        COALESCE(
            (SELECT ouh.gap_count FROM options_underlying_history ouh
             WHERE ouh.underlying_symbol_id = v_underlying_symbol_id
               AND ouh.timeframe = 'd1'
             ORDER BY ouh.ts DESC LIMIT 1),
            0
        ) AS underlying_gap_count,
        -- Price history fields
        orr.mark,
        orr.implied_vol,
        orr.delta,
        orr.gamma,
        orr.theta,
        orr.vega
    FROM options_ranks orr
    WHERE orr.id = p_option_id;
END;
$$;

-- ============================================================================
-- Cleanup Function
-- ============================================================================

-- Cleanup function for old underlying history (keep configurable days)
CREATE OR REPLACE FUNCTION cleanup_old_underlying_history(
    p_keep_days INTEGER DEFAULT 180
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_rows_deleted INTEGER;
BEGIN
    DELETE FROM options_underlying_history
    WHERE ts < NOW() - (p_keep_days || ' days')::INTERVAL;

    GET DIAGNOSTICS v_rows_deleted = ROW_COUNT;

    RETURN v_rows_deleted;
END;
$$;

-- ============================================================================
-- Health Monitoring
-- ============================================================================

-- Create health status view for underlying history
CREATE OR REPLACE VIEW options_underlying_health AS
SELECT
    s.ticker AS symbol,
    s.id AS symbol_id,
    ouh.timeframe,
    MAX(ouh.ts) AS last_refreshed_at,
    COUNT(*) AS row_count,
    7 - COUNT(DISTINCT DATE(ouh.ts)) AS missing_days,
    CASE
        WHEN MAX(ouh.ts) < NOW() - INTERVAL '24 hours' THEN 'stale'
        WHEN COUNT(*) < 5 THEN 'incomplete'
        ELSE 'healthy'
    END AS status
FROM symbols s
LEFT JOIN options_underlying_history ouh ON s.id = ouh.underlying_symbol_id
WHERE ouh.ts >= NOW() - INTERVAL '7 days'
GROUP BY s.ticker, s.id, ouh.timeframe;

-- Grant access to views
GRANT SELECT ON options_underlying_health TO anon, authenticated;

-- Comments
COMMENT ON TABLE options_underlying_history IS 'Stores 7-day price history and derived metrics for options underlying assets';
COMMENT ON FUNCTION get_underlying_history IS 'Returns underlying price history for a given symbol and timeframe';
COMMENT ON FUNCTION get_latest_underlying_metrics IS 'Returns the latest 7-day metrics for an underlying';
COMMENT ON FUNCTION get_options_enriched_features IS 'Returns options with enriched underlying metrics';
COMMENT ON FUNCTION cleanup_old_underlying_history IS 'Removes underlying history older than specified days';
