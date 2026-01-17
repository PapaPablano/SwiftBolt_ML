-- ============================================================================
-- SwiftBolt ML - Support & Resistance Levels Schema
-- Migration: 20251224060000_support_resistance_levels.sql
-- ============================================================================

-- -----------------------------------------------------------------------------
-- sr_levels: Support and Resistance levels computed for each symbol
-- Stores pivot points, Fibonacci levels, and computed S/R zones
-- -----------------------------------------------------------------------------
CREATE TABLE sr_levels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    timeframe TEXT NOT NULL DEFAULT '1d', -- '1h', '1d', '1w'
    
    -- Current price at computation time
    current_price NUMERIC(20, 6) NOT NULL,
    
    -- Pivot Points (Classical)
    pivot_pp NUMERIC(20, 6),
    pivot_r1 NUMERIC(20, 6),
    pivot_r2 NUMERIC(20, 6),
    pivot_r3 NUMERIC(20, 6),
    pivot_s1 NUMERIC(20, 6),
    pivot_s2 NUMERIC(20, 6),
    pivot_s3 NUMERIC(20, 6),
    
    -- Fibonacci Retracement
    fib_trend TEXT, -- 'uptrend' or 'downtrend'
    fib_range_high NUMERIC(20, 6),
    fib_range_low NUMERIC(20, 6),
    fib_0 NUMERIC(20, 6),      -- 0% level
    fib_236 NUMERIC(20, 6),    -- 23.6% level
    fib_382 NUMERIC(20, 6),    -- 38.2% level
    fib_500 NUMERIC(20, 6),    -- 50% level
    fib_618 NUMERIC(20, 6),    -- 61.8% level
    fib_786 NUMERIC(20, 6),    -- 78.6% level
    fib_100 NUMERIC(20, 6),    -- 100% level
    
    -- Computed nearest levels
    nearest_support NUMERIC(20, 6),
    nearest_resistance NUMERIC(20, 6),
    support_distance_pct NUMERIC(8, 4),
    resistance_distance_pct NUMERIC(8, 4),
    sr_ratio NUMERIC(8, 4), -- resistance_dist / support_dist
    
    -- ZigZag swing data (stored as JSONB for flexibility)
    zigzag_swings JSONB DEFAULT '[]'::jsonb,
    -- Schema: [{"type": "high"|"low", "price": number, "ts": "ISO8601", "index": number}]
    
    -- K-Means cluster centers
    kmeans_centers JSONB DEFAULT '[]'::jsonb,
    -- Schema: [number, number, ...]
    
    -- All computed support/resistance levels
    all_supports JSONB DEFAULT '[]'::jsonb,
    all_resistances JSONB DEFAULT '[]'::jsonb,
    
    -- Price data used for computation
    period_high NUMERIC(20, 6),
    period_low NUMERIC(20, 6),
    lookback_bars INTEGER DEFAULT 100,
    
    -- Computed date for unique constraint (set by trigger)
    computed_date DATE NOT NULL DEFAULT CURRENT_DATE,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX idx_sr_levels_symbol ON sr_levels(symbol_id);
CREATE INDEX idx_sr_levels_symbol_timeframe ON sr_levels(symbol_id, timeframe);
CREATE INDEX idx_sr_levels_computed_at ON sr_levels(computed_at DESC);

-- Unique constraint: one S/R record per symbol/timeframe/day
CREATE UNIQUE INDEX idx_sr_levels_unique ON sr_levels(
    symbol_id, 
    timeframe, 
    computed_date
);

-- Trigger to set computed_date from computed_at
CREATE OR REPLACE FUNCTION set_sr_computed_date()
RETURNS TRIGGER AS $$
BEGIN
    NEW.computed_date := NEW.computed_at::date;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_sr_levels_set_date
    BEFORE INSERT OR UPDATE ON sr_levels
    FOR EACH ROW
    EXECUTE FUNCTION set_sr_computed_date();

-- -----------------------------------------------------------------------------
-- sr_level_history: Historical tracking of S/R level changes
-- Useful for tracking how levels evolve over time
-- -----------------------------------------------------------------------------
CREATE TABLE sr_level_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    level_type TEXT NOT NULL, -- 'support', 'resistance', 'pivot'
    level_price NUMERIC(20, 6) NOT NULL,
    level_source TEXT NOT NULL, -- 'pivot_s1', 'fib_618', 'zigzag', 'kmeans'
    strength_score NUMERIC(5, 2), -- 0-100 strength rating
    first_detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_touched_at TIMESTAMPTZ,
    touch_count INTEGER DEFAULT 1,
    is_broken BOOLEAN DEFAULT FALSE,
    broken_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sr_history_symbol ON sr_level_history(symbol_id);
CREATE INDEX idx_sr_history_type ON sr_level_history(level_type);
CREATE INDEX idx_sr_history_price ON sr_level_history(level_price);

-- -----------------------------------------------------------------------------
-- View: Latest S/R levels per symbol
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_latest_sr_levels AS
SELECT DISTINCT ON (symbol_id, timeframe)
    sr.*,
    s.ticker
FROM sr_levels sr
JOIN symbols s ON sr.symbol_id = s.id
ORDER BY symbol_id, timeframe, computed_at DESC;

-- -----------------------------------------------------------------------------
-- Function: Get S/R levels for a symbol
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_sr_levels(
    p_symbol_id UUID,
    p_timeframe TEXT DEFAULT '1d'
)
RETURNS TABLE (
    current_price NUMERIC,
    nearest_support NUMERIC,
    nearest_resistance NUMERIC,
    support_distance_pct NUMERIC,
    resistance_distance_pct NUMERIC,
    sr_ratio NUMERIC,
    pivot_pp NUMERIC,
    pivot_r1 NUMERIC,
    pivot_s1 NUMERIC,
    fib_trend TEXT,
    computed_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        sr.current_price,
        sr.nearest_support,
        sr.nearest_resistance,
        sr.support_distance_pct,
        sr.resistance_distance_pct,
        sr.sr_ratio,
        sr.pivot_pp,
        sr.pivot_r1,
        sr.pivot_s1,
        sr.fib_trend,
        sr.computed_at
    FROM sr_levels sr
    WHERE sr.symbol_id = p_symbol_id
      AND sr.timeframe = p_timeframe
    ORDER BY sr.computed_at DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- Function: Get symbols near support/resistance
-- Returns symbols where price is within threshold of S/R levels
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_symbols_near_sr(
    p_threshold_pct NUMERIC DEFAULT 2.0,
    p_level_type TEXT DEFAULT 'both' -- 'support', 'resistance', 'both'
)
RETURNS TABLE (
    symbol_id UUID,
    ticker TEXT,
    current_price NUMERIC,
    nearest_support NUMERIC,
    nearest_resistance NUMERIC,
    support_distance_pct NUMERIC,
    resistance_distance_pct NUMERIC,
    near_level_type TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        sr.symbol_id,
        s.ticker,
        sr.current_price,
        sr.nearest_support,
        sr.nearest_resistance,
        sr.support_distance_pct,
        sr.resistance_distance_pct,
        CASE 
            WHEN sr.support_distance_pct <= p_threshold_pct 
                 AND sr.resistance_distance_pct <= p_threshold_pct THEN 'both'
            WHEN sr.support_distance_pct <= p_threshold_pct THEN 'support'
            WHEN sr.resistance_distance_pct <= p_threshold_pct THEN 'resistance'
            ELSE 'none'
        END as near_level_type
    FROM v_latest_sr_levels sr
    JOIN symbols s ON sr.symbol_id = s.id
    WHERE sr.timeframe = '1d'
      AND (
          (p_level_type = 'support' AND sr.support_distance_pct <= p_threshold_pct)
          OR (p_level_type = 'resistance' AND sr.resistance_distance_pct <= p_threshold_pct)
          OR (p_level_type = 'both' AND (
              sr.support_distance_pct <= p_threshold_pct 
              OR sr.resistance_distance_pct <= p_threshold_pct
          ))
      )
    ORDER BY 
        LEAST(sr.support_distance_pct, sr.resistance_distance_pct) ASC;
END;
$$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- RLS Policies
-- -----------------------------------------------------------------------------
ALTER TABLE sr_levels ENABLE ROW LEVEL SECURITY;
ALTER TABLE sr_level_history ENABLE ROW LEVEL SECURITY;

-- Allow read access to all authenticated users
CREATE POLICY "Allow read access to sr_levels"
    ON sr_levels FOR SELECT
    USING (true);

CREATE POLICY "Allow read access to sr_level_history"
    ON sr_level_history FOR SELECT
    USING (true);

-- Allow service role to insert/update
CREATE POLICY "Allow service role to manage sr_levels"
    ON sr_levels FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Allow service role to manage sr_level_history"
    ON sr_level_history FOR ALL
    USING (auth.role() = 'service_role');

-- -----------------------------------------------------------------------------
-- Comments
-- -----------------------------------------------------------------------------
COMMENT ON TABLE sr_levels IS 'Support and resistance levels computed for each symbol using multiple detection methods';
COMMENT ON TABLE sr_level_history IS 'Historical tracking of individual S/R levels and their touches/breaks';
COMMENT ON COLUMN sr_levels.sr_ratio IS 'Ratio of resistance distance to support distance. >1 = bullish bias, <1 = bearish bias';
COMMENT ON COLUMN sr_levels.zigzag_swings IS 'ZigZag indicator swing points as JSON array';
COMMENT ON COLUMN sr_levels.kmeans_centers IS 'K-Means cluster centers representing price zones';
