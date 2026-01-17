-- Option B Forecast Accuracy Framework
-- Adds columns to track the 4-tier outcome classification:
-- FULL_HIT: Direction correct AND price within band ± tolerance
-- DIRECTIONAL_HIT: Direction correct AND price within 2x tolerance
-- DIRECTIONAL_ONLY: Direction correct but price beyond 2x tolerance
-- MISS: Direction incorrect
--
-- Tolerance by horizon:
-- 1-3 days: ±1% of mid-price
-- 4-10 days: ±2% of mid-price

-- Add Option B columns to intraday evaluations table
ALTER TABLE ml_forecast_evaluations_intraday
ADD COLUMN IF NOT EXISTS option_b_outcome TEXT,
ADD COLUMN IF NOT EXISTS option_b_direction_correct BOOLEAN,
ADD COLUMN IF NOT EXISTS option_b_within_tolerance BOOLEAN,
ADD COLUMN IF NOT EXISTS option_b_mape NUMERIC,
ADD COLUMN IF NOT EXISTS option_b_bias NUMERIC;

-- Add check constraint for valid outcomes
ALTER TABLE ml_forecast_evaluations_intraday
DROP CONSTRAINT IF EXISTS valid_option_b_outcome;

ALTER TABLE ml_forecast_evaluations_intraday
ADD CONSTRAINT valid_option_b_outcome 
CHECK (option_b_outcome IS NULL OR option_b_outcome IN ('FULL_HIT', 'DIRECTIONAL_HIT', 'DIRECTIONAL_ONLY', 'MISS'));

-- Create index for Option B outcome queries
CREATE INDEX IF NOT EXISTS idx_intraday_eval_option_b_outcome 
ON ml_forecast_evaluations_intraday(option_b_outcome);

CREATE INDEX IF NOT EXISTS idx_intraday_eval_option_b_evaluated 
ON ml_forecast_evaluations_intraday(evaluated_at, option_b_outcome);

-- Add Option B columns to daily forecast evaluations table (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'ml_forecast_evaluations') THEN
        ALTER TABLE ml_forecast_evaluations
        ADD COLUMN IF NOT EXISTS option_b_outcome TEXT,
        ADD COLUMN IF NOT EXISTS option_b_direction_correct BOOLEAN,
        ADD COLUMN IF NOT EXISTS option_b_within_tolerance BOOLEAN,
        ADD COLUMN IF NOT EXISTS option_b_mape NUMERIC,
        ADD COLUMN IF NOT EXISTS option_b_bias NUMERIC;
        
        ALTER TABLE ml_forecast_evaluations
        DROP CONSTRAINT IF EXISTS valid_option_b_outcome_daily;
        
        ALTER TABLE ml_forecast_evaluations
        ADD CONSTRAINT valid_option_b_outcome_daily 
        CHECK (option_b_outcome IS NULL OR option_b_outcome IN ('FULL_HIT', 'DIRECTIONAL_HIT', 'DIRECTIONAL_ONLY', 'MISS'));
        
        CREATE INDEX IF NOT EXISTS idx_daily_eval_option_b_outcome 
        ON ml_forecast_evaluations(option_b_outcome);
    END IF;
END $$;

-- Function to get Option B accuracy stats for intraday forecasts
CREATE OR REPLACE FUNCTION get_intraday_option_b_stats(
    p_symbol_id UUID DEFAULT NULL,
    p_horizon TEXT DEFAULT NULL,
    p_lookback_hours INT DEFAULT 72
)
RETURNS TABLE (
    symbol TEXT,
    horizon TEXT,
    total_forecasts BIGINT,
    full_hit_rate NUMERIC,
    directional_hit_rate NUMERIC,
    directional_only_rate NUMERIC,
    miss_rate NUMERIC,
    directional_accuracy NUMERIC,
    avg_mape NUMERIC,
    avg_bias NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.symbol,
        e.horizon,
        COUNT(*)::BIGINT as total_forecasts,
        ROUND(
            COUNT(*) FILTER (WHERE e.option_b_outcome = 'FULL_HIT')::NUMERIC / 
            NULLIF(COUNT(*), 0), 3
        ) as full_hit_rate,
        ROUND(
            COUNT(*) FILTER (WHERE e.option_b_outcome = 'DIRECTIONAL_HIT')::NUMERIC / 
            NULLIF(COUNT(*), 0), 3
        ) as directional_hit_rate,
        ROUND(
            COUNT(*) FILTER (WHERE e.option_b_outcome = 'DIRECTIONAL_ONLY')::NUMERIC / 
            NULLIF(COUNT(*), 0), 3
        ) as directional_only_rate,
        ROUND(
            COUNT(*) FILTER (WHERE e.option_b_outcome = 'MISS')::NUMERIC / 
            NULLIF(COUNT(*), 0), 3
        ) as miss_rate,
        ROUND(
            COUNT(*) FILTER (WHERE e.option_b_direction_correct = true)::NUMERIC / 
            NULLIF(COUNT(*), 0), 3
        ) as directional_accuracy,
        ROUND(AVG(e.option_b_mape)::NUMERIC, 4) as avg_mape,
        ROUND(AVG(e.option_b_bias)::NUMERIC, 4) as avg_bias
    FROM ml_forecast_evaluations_intraday e
    WHERE e.created_at >= NOW() - (p_lookback_hours || ' hours')::INTERVAL
      AND e.option_b_outcome IS NOT NULL
      AND (p_symbol_id IS NULL OR e.symbol_id = p_symbol_id)
      AND (p_horizon IS NULL OR e.horizon = p_horizon)
    GROUP BY e.symbol, e.horizon
    ORDER BY e.symbol, e.horizon;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to check Option B health status
CREATE OR REPLACE FUNCTION get_option_b_health_status(
    p_directional_accuracy NUMERIC,
    p_full_hit_rate NUMERIC
)
RETURNS TEXT AS $$
BEGIN
    IF p_directional_accuracy >= 0.54 AND p_full_hit_rate >= 0.42 THEN
        RETURN 'OPTIMAL';
    ELSIF p_directional_accuracy >= 0.52 AND p_full_hit_rate >= 0.35 THEN
        RETURN 'ACCEPTABLE';
    ELSIF p_directional_accuracy >= 0.50 THEN
        RETURN 'MARGINAL';
    ELSE
        RETURN 'DEGRADED';
    END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION get_intraday_option_b_stats IS 
'Get Option B framework accuracy stats for intraday forecasts. 
Returns full_hit_rate (primary metric), directional accuracy, MAPE, and bias.';

COMMENT ON FUNCTION get_option_b_health_status IS 
'Determine health status based on Option B metrics.
OPTIMAL: dir_acc >= 54%, full_hit >= 42%
ACCEPTABLE: dir_acc >= 52%, full_hit >= 35%
MARGINAL: dir_acc >= 50%
DEGRADED: dir_acc < 50%';
