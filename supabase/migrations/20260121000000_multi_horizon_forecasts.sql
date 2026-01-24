-- Multi-Horizon Forecasting Schema
-- Supports cascading forecasts across multiple time horizons per timeframe

ALTER TABLE ml_forecasts
ADD COLUMN IF NOT EXISTS timeframe TEXT,
ADD COLUMN IF NOT EXISTS is_base_horizon BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS is_consensus BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS handoff_confidence NUMERIC(5,2),
ADD COLUMN IF NOT EXISTS consensus_weight NUMERIC(5,2);

-- Create index for timeframe queries
CREATE INDEX IF NOT EXISTS idx_ml_forecasts_timeframe 
ON ml_forecasts(symbol_id, timeframe, horizon);

-- Create index for consensus forecasts
CREATE INDEX IF NOT EXISTS idx_ml_forecasts_consensus 
ON ml_forecasts(symbol_id, is_consensus, horizon) 
WHERE is_consensus = true;

-- Create view for multi-horizon forecast summary
CREATE OR REPLACE VIEW multi_horizon_forecast_summary AS
SELECT 
    s.ticker as symbol,
    mf.timeframe,
    mf.horizon,
    mf.overall_label as direction,
    mf.confidence,
    mf.target_price,
    mf.ci_upper AS upper_band,
    mf.ci_lower AS lower_band,
    mf.is_base_horizon,
    mf.is_consensus,
    mf.handoff_confidence,
    mf.consensus_weight,
    mf.synthesis_data,
    mf.created_at
FROM ml_forecasts mf
JOIN symbols s ON s.id = mf.symbol_id
WHERE mf.created_at >= NOW() - INTERVAL '24 hours'
ORDER BY s.ticker, mf.timeframe, mf.horizon;

-- Function to get all horizons for a symbol and timeframe
CREATE OR REPLACE FUNCTION get_multi_horizon_forecasts(
    p_symbol TEXT,
    p_timeframe TEXT DEFAULT NULL
)
RETURNS TABLE (
    timeframe TEXT,
    horizon TEXT,
    direction TEXT,
    confidence NUMERIC,
    target_price NUMERIC,
    upper_band NUMERIC,
    lower_band NUMERIC,
    is_base_horizon BOOLEAN,
    handoff_confidence NUMERIC,
    consensus_weight NUMERIC,
    key_drivers JSONB,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        mf.timeframe,
        mf.horizon,
        mf.overall_label as direction,
        mf.confidence,
        mf.target_price,
        mf.ci_upper AS upper_band,
        mf.ci_lower AS lower_band,
        mf.is_base_horizon,
        mf.handoff_confidence,
        mf.consensus_weight,
        mf.synthesis_data->'key_drivers' as key_drivers,
        mf.created_at
    FROM ml_forecasts mf
    JOIN symbols s ON s.id = mf.symbol_id
    WHERE s.ticker = p_symbol
        AND (p_timeframe IS NULL OR mf.timeframe = p_timeframe)
        AND mf.is_consensus = false
        AND mf.created_at >= NOW() - INTERVAL '24 hours'
    ORDER BY 
        CASE mf.timeframe
            WHEN 'm15' THEN 1
            WHEN 'h1' THEN 2
            WHEN 'h4' THEN 3
            WHEN 'd1' THEN 4
            WHEN 'w1' THEN 5
            ELSE 6
        END,
        mf.created_at DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to get consensus forecasts for a symbol
CREATE OR REPLACE FUNCTION get_consensus_forecasts(
    p_symbol TEXT
)
RETURNS TABLE (
    horizon TEXT,
    direction TEXT,
    confidence NUMERIC,
    target_price NUMERIC,
    upper_band NUMERIC,
    lower_band NUMERIC,
    contributing_timeframes JSONB,
    agreement_score NUMERIC,
    handoff_quality NUMERIC,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        mf.horizon,
        mf.overall_label as direction,
        mf.confidence,
        mf.target_price,
        mf.ci_upper AS upper_band,
        mf.ci_lower AS lower_band,
        mf.model_agreement->'contributing_timeframes' as contributing_timeframes,
        (mf.model_agreement->>'agreement_score')::NUMERIC as agreement_score,
        (mf.model_agreement->>'handoff_quality')::NUMERIC as handoff_quality,
        mf.created_at
    FROM ml_forecasts mf
    JOIN symbols s ON s.id = mf.symbol_id
    WHERE s.ticker = p_symbol
        AND mf.is_consensus = true
        AND mf.created_at >= NOW() - INTERVAL '24 hours'
    ORDER BY 
        CASE 
            WHEN mf.horizon LIKE '%h' THEN 1
            WHEN mf.horizon LIKE '%d' THEN 2
            WHEN mf.horizon LIKE '%w' THEN 3
            WHEN mf.horizon LIKE '%M' THEN 4
            WHEN mf.horizon LIKE '%Y' THEN 5
            ELSE 6
        END,
        mf.created_at DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to get forecast cascade (all timeframes + consensus for a horizon)
CREATE OR REPLACE FUNCTION get_forecast_cascade(
    p_symbol TEXT,
    p_horizon TEXT
)
RETURNS TABLE (
    source TEXT,  -- timeframe or 'consensus'
    direction TEXT,
    confidence NUMERIC,
    target_price NUMERIC,
    upper_band NUMERIC,
    lower_band NUMERIC,
    handoff_confidence NUMERIC,
    is_consensus BOOLEAN,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COALESCE(mf.timeframe, 'consensus') as source,
        mf.overall_label as direction,
        mf.confidence,
        mf.target_price,
        mf.upper_band,
        mf.lower_band,
        mf.handoff_confidence,
        mf.is_consensus,
        mf.created_at
    FROM ml_forecasts mf
    JOIN symbols s ON s.id = mf.symbol_id
    WHERE s.ticker = p_symbol
        AND mf.horizon = p_horizon
        AND mf.created_at >= NOW() - INTERVAL '24 hours'
    ORDER BY 
        mf.is_consensus DESC,  -- Consensus first
        CASE mf.timeframe
            WHEN 'm15' THEN 1
            WHEN 'h1' THEN 2
            WHEN 'h4' THEN 3
            WHEN 'd1' THEN 4
            WHEN 'w1' THEN 5
            ELSE 6
        END;
END;
$$ LANGUAGE plpgsql;

-- Comment on new columns
COMMENT ON COLUMN ml_forecasts.timeframe IS 'Source timeframe for the forecast (m15, h1, h4, d1, w1, or consensus)';
COMMENT ON COLUMN ml_forecasts.is_base_horizon IS 'True if this is the primary horizon for this timeframe';
COMMENT ON COLUMN ml_forecasts.is_consensus IS 'True if this is a consensus forecast from multiple timeframes';
COMMENT ON COLUMN ml_forecasts.handoff_confidence IS 'Confidence in handing off to next timeframe (0-1)';
COMMENT ON COLUMN ml_forecasts.consensus_weight IS 'Weight of this forecast in consensus calculation (0-1)';
