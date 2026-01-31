-- Migration: Add model_type column to ml_forecasts
-- Date: 2026-01-31
-- Description: Adds model_type column to track which ML model generated each forecast
--              (e.g., 'xgboost', 'tabpfn', 'transformer', 'baseline')

-- Add model_type column
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ml_forecasts' AND column_name = 'model_type'
    ) THEN
        ALTER TABLE ml_forecasts
        ADD COLUMN model_type TEXT DEFAULT 'xgboost'
        CHECK (model_type IN ('xgboost', 'tabpfn', 'transformer', 'baseline', 'arima', 'prophet', 'ensemble'));

        RAISE NOTICE 'Added model_type column to ml_forecasts';
    END IF;
END $$;

-- Update existing records to have model_type='xgboost' (since that's what's been used)
UPDATE ml_forecasts
SET model_type = 'xgboost'
WHERE model_type IS NULL;

-- Create index for filtering by model_type
CREATE INDEX IF NOT EXISTS idx_ml_forecasts_model_type
ON ml_forecasts(model_type, created_at DESC);

-- Create compound index for symbol + model_type queries
CREATE INDEX IF NOT EXISTS idx_ml_forecasts_symbol_model_type
ON ml_forecasts(symbol_id, model_type, horizon, created_at DESC);

-- Add comment for documentation
COMMENT ON COLUMN ml_forecasts.model_type IS
    'ML model that generated this forecast: xgboost, tabpfn, transformer, baseline, etc.';

-- Create view for model comparison
CREATE OR REPLACE VIEW forecast_model_comparison AS
SELECT
    s.ticker as symbol,
    f.horizon,
    f.model_type,
    f.overall_label as direction,
    f.confidence,
    f.forecast_return,
    f.quality_score,
    f.model_agreement,
    f.n_models,
    f.synthesis_data->>'train_time_sec' as train_time_sec,
    f.synthesis_data->>'inference_time_sec' as inference_time_sec,
    f.created_at
FROM ml_forecasts f
JOIN symbols s ON f.symbol_id = s.id
WHERE f.created_at > NOW() - INTERVAL '24 hours'
ORDER BY s.ticker, f.horizon, f.model_type, f.created_at DESC;

COMMENT ON VIEW forecast_model_comparison IS
    'Compare forecasts from different models for the same symbol/horizon';

-- Function to get model agreement across different model types
CREATE OR REPLACE FUNCTION get_model_agreement_stats(
    p_symbol_id UUID,
    p_horizon TEXT DEFAULT '1D',
    p_lookback_hours INTEGER DEFAULT 24
)
RETURNS TABLE (
    model_type TEXT,
    forecast_count BIGINT,
    avg_confidence NUMERIC,
    bullish_pct NUMERIC,
    bearish_pct NUMERIC,
    neutral_pct NUMERIC,
    avg_forecast_return NUMERIC,
    avg_quality_score NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        f.model_type,
        COUNT(*)::BIGINT AS forecast_count,
        AVG(f.confidence)::NUMERIC AS avg_confidence,
        (SUM(CASE WHEN LOWER(f.overall_label) = 'bullish' THEN 1 ELSE 0 END)::NUMERIC / COUNT(*) * 100)::NUMERIC AS bullish_pct,
        (SUM(CASE WHEN LOWER(f.overall_label) = 'bearish' THEN 1 ELSE 0 END)::NUMERIC / COUNT(*) * 100)::NUMERIC AS bearish_pct,
        (SUM(CASE WHEN LOWER(f.overall_label) = 'neutral' THEN 1 ELSE 0 END)::NUMERIC / COUNT(*) * 100)::NUMERIC AS neutral_pct,
        AVG(f.forecast_return)::NUMERIC AS avg_forecast_return,
        AVG(f.quality_score)::NUMERIC AS avg_quality_score
    FROM ml_forecasts f
    WHERE f.symbol_id = p_symbol_id
        AND f.horizon = p_horizon
        AND f.created_at >= NOW() - (p_lookback_hours || ' hours')::INTERVAL
    GROUP BY f.model_type
    ORDER BY f.model_type;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_model_agreement_stats IS
    'Get statistics on how different model types agree for a symbol/horizon';
