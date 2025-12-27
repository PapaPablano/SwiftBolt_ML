-- Migration: Intraday Bars Storage
-- Stores minute/5min/15min OHLCV bars for intraday analysis
-- Separate from ohlc_bars to optimize for high-frequency data

-- Create intraday_bars table
CREATE TABLE IF NOT EXISTS intraday_bars (
    id BIGSERIAL PRIMARY KEY,
    symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    timeframe TEXT NOT NULL CHECK (timeframe IN ('1m', '5m', '15m')),
    ts TIMESTAMPTZ NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume BIGINT NOT NULL DEFAULT 0,
    vwap DOUBLE PRECISION,
    trade_count INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Unique constraint for upserts
    UNIQUE(symbol_id, timeframe, ts)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_intraday_bars_symbol_ts
    ON intraday_bars(symbol_id, ts DESC);

CREATE INDEX IF NOT EXISTS idx_intraday_bars_symbol_tf_ts
    ON intraday_bars(symbol_id, timeframe, ts DESC);

-- Partition-friendly index for date range queries
CREATE INDEX IF NOT EXISTS idx_intraday_bars_ts
    ON intraday_bars(ts DESC);

-- RLS
ALTER TABLE intraday_bars ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Intraday bars readable by authenticated"
    ON intraday_bars FOR SELECT TO authenticated USING (true);

CREATE POLICY "Service role manages intraday bars"
    ON intraday_bars FOR ALL TO service_role USING (true);

-- Function: Get latest intraday bar for a symbol
CREATE OR REPLACE FUNCTION get_latest_intraday_bar(
    p_symbol_id UUID,
    p_timeframe TEXT DEFAULT '5m'
)
RETURNS TABLE (
    ts TIMESTAMPTZ,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume BIGINT,
    vwap DOUBLE PRECISION
)
LANGUAGE sql
STABLE
AS $$
    SELECT ts, open, high, low, close, volume, vwap
    FROM intraday_bars
    WHERE symbol_id = p_symbol_id AND timeframe = p_timeframe
    ORDER BY ts DESC
    LIMIT 1;
$$;

-- Function: Aggregate intraday bars to daily
CREATE OR REPLACE FUNCTION aggregate_intraday_to_daily(
    p_symbol_id UUID,
    p_date DATE DEFAULT CURRENT_DATE
)
RETURNS TABLE (
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume BIGINT,
    vwap DOUBLE PRECISION,
    bar_count INTEGER
)
LANGUAGE sql
STABLE
AS $$
    WITH bars AS (
        SELECT *
        FROM intraday_bars
        WHERE symbol_id = p_symbol_id
          AND timeframe = '5m'
          AND ts::date = p_date
        ORDER BY ts
    ),
    first_bar AS (SELECT open FROM bars LIMIT 1),
    last_bar AS (SELECT close FROM bars ORDER BY ts DESC LIMIT 1)
    SELECT
        (SELECT open FROM first_bar) as open,
        MAX(high) as high,
        MIN(low) as low,
        (SELECT close FROM last_bar) as close,
        SUM(volume) as volume,
        SUM(close * volume) / NULLIF(SUM(volume), 0) as vwap,
        COUNT(*)::INTEGER as bar_count
    FROM bars;
$$;

-- Function: Clean up old intraday data (keep 30 days)
CREATE OR REPLACE FUNCTION cleanup_old_intraday_bars()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_rows_deleted INTEGER;
BEGIN
    DELETE FROM intraday_bars
    WHERE ts < NOW() - INTERVAL '30 days';

    GET DIAGNOSTICS v_rows_deleted = ROW_COUNT;

    RETURN v_rows_deleted;
END;
$$;

-- View: Current day's intraday summary per symbol
CREATE OR REPLACE VIEW intraday_daily_summary AS
SELECT
    s.id as symbol_id,
    s.ticker as symbol,
    COUNT(*) as bar_count,
    MIN(ib.ts) as first_bar,
    MAX(ib.ts) as last_bar,
    (array_agg(ib.open ORDER BY ib.ts ASC))[1] as day_open,
    MAX(ib.high) as day_high,
    MIN(ib.low) as day_low,
    (array_agg(ib.close ORDER BY ib.ts DESC))[1] as current_price,
    SUM(ib.volume) as total_volume,
    SUM(ib.close * ib.volume) / NULLIF(SUM(ib.volume), 0) as vwap
FROM intraday_bars ib
JOIN symbols s ON s.id = ib.symbol_id
WHERE ib.ts::date = CURRENT_DATE
  AND ib.timeframe = '5m'
GROUP BY s.id, s.ticker;

GRANT SELECT ON intraday_daily_summary TO authenticated;

-- Comments
COMMENT ON TABLE intraday_bars IS 'Stores intraday OHLCV bars (1m, 5m, 15m) for real-time analysis';
COMMENT ON FUNCTION aggregate_intraday_to_daily IS 'Aggregates intraday bars into daily OHLCV';
COMMENT ON FUNCTION cleanup_old_intraday_bars IS 'Removes intraday data older than 30 days';
