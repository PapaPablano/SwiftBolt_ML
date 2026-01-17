-- Migration: Add ml_features table and enhance options_ranks for Phase 1 improvements
-- Created: 2024-12-19

-- ============================================================================
-- 1. ML Features Cache Table
-- ============================================================================
-- Caches computed technical indicators to avoid recomputation during options ranking
-- and forecast generation. All processing reads from cached ohlc_bars data.

CREATE TABLE IF NOT EXISTS ml_features (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id UUID REFERENCES symbols(id) ON DELETE CASCADE NOT NULL,
    timeframe TEXT NOT NULL DEFAULT 'd1',
    ts TIMESTAMPTZ NOT NULL,

    -- Momentum Indicators
    rsi_14 REAL,
    stoch_k REAL,
    stoch_d REAL,
    kdj_k REAL,
    kdj_d REAL,
    kdj_j REAL,
    kdj_j_minus_d REAL,  -- Divergence signal
    macd REAL,
    macd_signal REAL,
    macd_hist REAL,

    -- Trend Indicators
    adx REAL,
    plus_di REAL,
    minus_di REAL,
    supertrend REAL,
    supertrend_trend INTEGER,  -- 1 = bullish, 0 = bearish

    -- Volume Indicators
    obv REAL,
    obv_sma REAL,
    mfi REAL,
    vroc REAL,
    volume_ratio REAL,

    -- Volatility Indicators
    atr_14 REAL,
    bb_upper REAL,
    bb_middle REAL,
    bb_lower REAL,
    bb_width REAL,
    keltner_upper REAL,
    keltner_middle REAL,
    keltner_lower REAL,
    volatility_20d REAL,

    -- SuperTrend AI metadata
    supertrend_factor REAL,
    supertrend_performance_index REAL,

    -- Metadata
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Unique constraint for upsert
    CONSTRAINT ml_features_unique UNIQUE (symbol_id, timeframe, ts)
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_ml_features_symbol_tf ON ml_features(symbol_id, timeframe);
CREATE INDEX IF NOT EXISTS idx_ml_features_ts ON ml_features(ts DESC);
CREATE INDEX IF NOT EXISTS idx_ml_features_computed ON ml_features(computed_at DESC);

-- ============================================================================
-- 2. Enhance options_ranks table with trend analysis
-- ============================================================================

-- Add trend analysis columns if they don't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'options_ranks' AND column_name = 'trend_analysis') THEN
        ALTER TABLE options_ranks ADD COLUMN trend_analysis JSONB;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'options_ranks' AND column_name = 'supertrend_factor') THEN
        ALTER TABLE options_ranks ADD COLUMN supertrend_factor REAL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'options_ranks' AND column_name = 'supertrend_performance') THEN
        ALTER TABLE options_ranks ADD COLUMN supertrend_performance REAL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'options_ranks' AND column_name = 'trend_label') THEN
        ALTER TABLE options_ranks ADD COLUMN trend_label trend_label;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'options_ranks' AND column_name = 'trend_confidence') THEN
        ALTER TABLE options_ranks ADD COLUMN trend_confidence REAL;
    END IF;
END $$;

-- ============================================================================
-- 3. Add ml_forecasts enhancements
-- ============================================================================

DO $$
BEGIN
    -- Add supertrend columns to ml_forecasts if they don't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'ml_forecasts' AND column_name = 'supertrend_factor') THEN
        ALTER TABLE ml_forecasts ADD COLUMN supertrend_factor REAL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'ml_forecasts' AND column_name = 'supertrend_signal') THEN
        ALTER TABLE ml_forecasts ADD COLUMN supertrend_signal INTEGER;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'ml_forecasts' AND column_name = 'composite_signal') THEN
        ALTER TABLE ml_forecasts ADD COLUMN composite_signal REAL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'ml_forecasts' AND column_name = 'indicator_scores') THEN
        ALTER TABLE ml_forecasts ADD COLUMN indicator_scores JSONB;
    END IF;
END $$;

-- ============================================================================
-- 4. RLS Policies for ml_features
-- ============================================================================

ALTER TABLE ml_features ENABLE ROW LEVEL SECURITY;

-- Service role can do everything
CREATE POLICY "Service role manages ml_features"
ON ml_features FOR ALL
USING (auth.role() = 'service_role');

-- Authenticated users can read
CREATE POLICY "Authenticated users can read ml_features"
ON ml_features FOR SELECT
USING (auth.role() = 'authenticated');

-- ============================================================================
-- 5. Helper Functions
-- ============================================================================

-- Function to get latest features for a symbol
CREATE OR REPLACE FUNCTION get_latest_ml_features(
    p_symbol TEXT,
    p_timeframe TEXT DEFAULT 'd1',
    p_limit INTEGER DEFAULT 100
)
RETURNS TABLE (
    ts TIMESTAMPTZ,
    rsi_14 REAL,
    macd_hist REAL,
    adx REAL,
    supertrend_trend INTEGER,
    kdj_j REAL,
    mfi REAL,
    bb_width REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        mf.ts,
        mf.rsi_14,
        mf.macd_hist,
        mf.adx,
        mf.supertrend_trend,
        mf.kdj_j,
        mf.mfi,
        mf.bb_width
    FROM ml_features mf
    JOIN symbols s ON mf.symbol_id = s.id
    WHERE s.ticker = p_symbol
      AND mf.timeframe = p_timeframe
    ORDER BY mf.ts DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to check if features are stale (older than 1 day)
CREATE OR REPLACE FUNCTION check_features_freshness(
    p_symbol TEXT,
    p_timeframe TEXT DEFAULT 'd1'
)
RETURNS TABLE (
    is_stale BOOLEAN,
    latest_ts TIMESTAMPTZ,
    age_hours REAL
) AS $$
DECLARE
    v_latest TIMESTAMPTZ;
    v_age INTERVAL;
BEGIN
    SELECT MAX(mf.ts) INTO v_latest
    FROM ml_features mf
    JOIN symbols s ON mf.symbol_id = s.id
    WHERE s.ticker = p_symbol
      AND mf.timeframe = p_timeframe;

    IF v_latest IS NULL THEN
        RETURN QUERY SELECT TRUE::BOOLEAN, NULL::TIMESTAMPTZ, NULL::REAL;
    ELSE
        v_age := NOW() - v_latest;
        RETURN QUERY SELECT
            (v_age > INTERVAL '1 day')::BOOLEAN,
            v_latest,
            EXTRACT(EPOCH FROM v_age) / 3600.0;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- 6. Comments
-- ============================================================================

COMMENT ON TABLE ml_features IS 'Cached technical indicators computed from ohlc_bars. Used by options ranker and forecast jobs.';
COMMENT ON COLUMN ml_features.supertrend_trend IS '1 = bullish, 0 = bearish. From SuperTrend AI with K-means optimized factor.';
COMMENT ON COLUMN ml_features.kdj_j_minus_d IS 'KDJ divergence signal: J - D. Positive = bullish divergence.';
COMMENT ON COLUMN ml_features.supertrend_factor IS 'Optimal ATR multiplier found by K-means clustering.';
COMMENT ON COLUMN ml_features.supertrend_performance_index IS 'Performance index (0-1) of the SuperTrend configuration.';
