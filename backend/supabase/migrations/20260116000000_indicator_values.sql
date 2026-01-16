-- Migration: Indicator Values Table for Chart Visualization
-- Created: 2026-01-16
-- Purpose: Persisted technical indicators for charting and ML forecasting reuse

-- ============================================================================
-- indicator_values: Per-candle indicator storage for chart visualization
-- ============================================================================

CREATE TABLE IF NOT EXISTS indicator_values (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    timeframe VARCHAR(10) NOT NULL CHECK (timeframe IN ('m15', 'h1', 'h4', 'd1', 'w1')),
    ts TIMESTAMPTZ NOT NULL,

    -- OHLC snapshot (for context/validation)
    open NUMERIC(20, 6),
    high NUMERIC(20, 6),
    low NUMERIC(20, 6),
    close NUMERIC(20, 6),
    volume BIGINT,

    -- RSI
    rsi_14 NUMERIC(8, 4),

    -- MACD
    macd NUMERIC(16, 6),
    macd_signal NUMERIC(16, 6),
    macd_hist NUMERIC(16, 6),

    -- SuperTrend
    supertrend_value NUMERIC(20, 6),
    supertrend_trend INTEGER,
    supertrend_factor NUMERIC(6, 3),

    -- Support/Resistance
    nearest_support NUMERIC(20, 6),
    nearest_resistance NUMERIC(20, 6),
    support_distance_pct NUMERIC(8, 4),
    resistance_distance_pct NUMERIC(8, 4),

    -- Additional indicators
    adx NUMERIC(8, 4),
    atr_14 NUMERIC(20, 6),
    bb_upper NUMERIC(20, 6),
    bb_lower NUMERIC(20, 6),

    -- Metadata
    metadata JSONB DEFAULT '{}',
    computed_at TIMESTAMPTZ DEFAULT NOW(),

    -- Unique constraint for upsert
    CONSTRAINT indicator_values_unique UNIQUE (symbol_id, timeframe, ts)
);

-- ============================================================================
-- Indexes for efficient querying
-- ============================================================================

-- Primary lookup: symbol + timeframe + time ordered
CREATE INDEX IF NOT EXISTS idx_indicator_values_symbol_tf_ts
ON indicator_values(symbol_id, timeframe, ts DESC);

-- Time-based queries across all symbols
CREATE INDEX IF NOT EXISTS idx_indicator_values_ts
ON indicator_values(ts DESC);

-- Partial index for recent data (most common query pattern)
CREATE INDEX IF NOT EXISTS idx_indicator_values_recent
ON indicator_values(symbol_id, timeframe, ts DESC)
WHERE ts > NOW() - INTERVAL '90 days';

-- ============================================================================
-- Row Level Security
-- ============================================================================

ALTER TABLE indicator_values ENABLE ROW LEVEL SECURITY;

-- Service role can manage all indicator data
CREATE POLICY "Service role manages indicator_values"
ON indicator_values FOR ALL
USING (auth.role() = 'service_role');

-- Authenticated users can read indicator data
CREATE POLICY "Authenticated users can read indicator_values"
ON indicator_values FOR SELECT
USING (auth.role() = 'authenticated');

-- Public read access (for chart visualization)
CREATE POLICY "Public read indicator_values"
ON indicator_values FOR SELECT
USING (true);

-- ============================================================================
-- Helper Functions
-- ============================================================================

-- Get latest indicators for a symbol
CREATE OR REPLACE FUNCTION get_latest_indicators(
    p_symbol_id UUID,
    p_timeframe TEXT DEFAULT 'd1',
    p_limit INTEGER DEFAULT 100
)
RETURNS TABLE (
    ts TIMESTAMPTZ,
    close NUMERIC,
    rsi_14 NUMERIC,
    macd NUMERIC,
    macd_hist NUMERIC,
    supertrend_value NUMERIC,
    supertrend_trend INTEGER,
    nearest_support NUMERIC,
    nearest_resistance NUMERIC,
    adx NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        iv.ts,
        iv.close,
        iv.rsi_14,
        iv.macd,
        iv.macd_hist,
        iv.supertrend_value,
        iv.supertrend_trend,
        iv.nearest_support,
        iv.nearest_resistance,
        iv.adx
    FROM indicator_values iv
    WHERE iv.symbol_id = p_symbol_id
      AND iv.timeframe = p_timeframe
    ORDER BY iv.ts DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Cleanup function: Remove old indicator data (keep 90 days by default)
CREATE OR REPLACE FUNCTION cleanup_old_indicator_values(
    p_retention_days INTEGER DEFAULT 90
)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM indicator_values
    WHERE computed_at < NOW() - (p_retention_days || ' days')::INTERVAL;

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE indicator_values IS
'Persisted technical indicators for chart visualization. Updated by forecast jobs.';

COMMENT ON COLUMN indicator_values.timeframe IS
'Bar timeframe: m15 (15-min), h1 (1-hour), h4 (4-hour), d1 (daily), w1 (weekly)';

COMMENT ON COLUMN indicator_values.supertrend_trend IS
'1 = bullish (price above SuperTrend), 0 = bearish (price below)';

COMMENT ON COLUMN indicator_values.metadata IS
'Extensible JSONB field for additional indicator data or debugging info';

COMMENT ON COLUMN indicator_values.computed_at IS
'Timestamp when this indicator snapshot was computed and saved';

COMMENT ON FUNCTION get_latest_indicators IS
'Retrieve the most recent indicator values for a symbol and timeframe';

COMMENT ON FUNCTION cleanup_old_indicator_values IS
'Remove indicator values older than retention period to manage table growth';
