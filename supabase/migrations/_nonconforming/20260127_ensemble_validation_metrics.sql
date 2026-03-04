-- Migration: Add ensemble_validation_metrics table for divergence tracking
-- Purpose: Store divergence metrics from walk-forward validation for overfitting detection
-- Created: 2026-01-27

-- Create ensemble_validation_metrics table
CREATE TABLE IF NOT EXISTS public.ensemble_validation_metrics (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,

    -- Reference to symbol and forecast configuration
    symbol_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    horizon TEXT NOT NULL,  -- "1D", "4h", "8h", etc.

    -- Validation window information
    validation_date TIMESTAMP WITH TIME ZONE NOT NULL,
    window_id INT NOT NULL,

    -- Performance metrics
    train_rmse DECIMAL(12, 6),
    val_rmse DECIMAL(12, 6) NOT NULL,
    test_rmse DECIMAL(12, 6) NOT NULL,

    -- Divergence metrics (overfitting detection)
    divergence DECIMAL(8, 6) NOT NULL,  -- abs(val_rmse - test_rmse) / val_rmse
    divergence_threshold DECIMAL(8, 6) NOT NULL DEFAULT 0.20,
    is_overfitting BOOLEAN NOT NULL DEFAULT FALSE,

    -- Ensemble configuration
    model_count INT NOT NULL,
    models_used TEXT[] NOT NULL,  -- Array of model names: ["LSTM", "ARIMA_GARCH", "GB"]

    -- Sample counts
    n_train_samples INT,
    n_val_samples INT,
    n_test_samples INT,
    data_span_days INT,

    -- Hyperparameters used
    hyperparameters JSONB,

    -- Accuracy metrics
    directional_accuracy DECIMAL(5, 4),  -- Percentage of correct direction predictions
    mean_absolute_error DECIMAL(12, 6),

    -- Metadata
    trained_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_divergence CHECK (divergence >= 0),
    CONSTRAINT valid_rmse CHECK (train_rmse > 0 AND val_rmse > 0 AND test_rmse > 0),
    CONSTRAINT valid_model_count CHECK (model_count BETWEEN 1 AND 6)
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_ensemble_validation_symbol
    ON public.ensemble_validation_metrics(symbol, horizon);

CREATE INDEX IF NOT EXISTS idx_ensemble_validation_date
    ON public.ensemble_validation_metrics(validation_date);

CREATE INDEX IF NOT EXISTS idx_ensemble_validation_overfitting
    ON public.ensemble_validation_metrics(is_overfitting, horizon, validation_date);

CREATE INDEX IF NOT EXISTS idx_ensemble_validation_symbol_horizon_date
    ON public.ensemble_validation_metrics(symbol, horizon, validation_date DESC);

-- Create a composite index for finding recent overfitting events
CREATE INDEX IF NOT EXISTS idx_ensemble_overfitting_recent
    ON public.ensemble_validation_metrics(is_overfitting, created_at DESC)
    WHERE is_overfitting = TRUE;

-- Enable Row Level Security
ALTER TABLE public.ensemble_validation_metrics ENABLE ROW LEVEL SECURITY;

-- Create RLS policy to allow authenticated access
CREATE POLICY "authenticated_read_ensemble_metrics" ON public.ensemble_validation_metrics
    FOR SELECT TO authenticated
    USING (TRUE);

CREATE POLICY "authenticated_insert_ensemble_metrics" ON public.ensemble_validation_metrics
    FOR INSERT TO authenticated
    WITH CHECK (TRUE);

CREATE POLICY "authenticated_update_ensemble_metrics" ON public.ensemble_validation_metrics
    FOR UPDATE TO authenticated
    USING (TRUE)
    WITH CHECK (TRUE);

-- Create a view for overfitting summary (symbols currently overfitting)
CREATE OR REPLACE VIEW public.vw_overfitting_symbols AS
SELECT
    symbol,
    horizon,
    COUNT(*) as overfitting_count,
    MAX(validation_date) as latest_overfitting,
    AVG(divergence) as avg_divergence,
    MAX(divergence) as max_divergence
FROM public.ensemble_validation_metrics
WHERE is_overfitting = TRUE
    AND validation_date > CURRENT_TIMESTAMP - INTERVAL '7 days'
GROUP BY symbol, horizon
ORDER BY avg_divergence DESC, latest_overfitting DESC;

-- Create a view for divergence trends (val vs test RMSE over time)
CREATE OR REPLACE VIEW public.vw_divergence_trends AS
SELECT
    symbol,
    horizon,
    validation_date,
    val_rmse,
    test_rmse,
    divergence,
    is_overfitting,
    model_count,
    ROW_NUMBER() OVER (PARTITION BY symbol, horizon ORDER BY validation_date) as window_sequence
FROM public.ensemble_validation_metrics
ORDER BY symbol, horizon, validation_date DESC;

-- Create a function to get statistics on ensemble performance
CREATE OR REPLACE FUNCTION public.get_ensemble_stats(
    p_symbol TEXT DEFAULT NULL,
    p_horizon TEXT DEFAULT NULL,
    p_days INT DEFAULT 30
)
RETURNS TABLE (
    symbol TEXT,
    horizon TEXT,
    total_windows BIGINT,
    avg_val_rmse DECIMAL,
    avg_test_rmse DECIMAL,
    avg_divergence DECIMAL,
    max_divergence DECIMAL,
    overfitting_ratio DECIMAL,
    model_count_modes INT[]
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        evm.symbol,
        evm.horizon,
        COUNT(*),
        ROUND(AVG(evm.val_rmse)::NUMERIC, 6),
        ROUND(AVG(evm.test_rmse)::NUMERIC, 6),
        ROUND(AVG(evm.divergence)::NUMERIC, 6),
        ROUND(MAX(evm.divergence)::NUMERIC, 6),
        ROUND((SUM(CASE WHEN evm.is_overfitting THEN 1 ELSE 0 END)::NUMERIC / COUNT(*)), 4),
        ARRAY_AGG(DISTINCT evm.model_count)
    FROM public.ensemble_validation_metrics evm
    WHERE (p_symbol IS NULL OR evm.symbol = p_symbol)
        AND (p_horizon IS NULL OR evm.horizon = p_horizon)
        AND evm.validation_date > CURRENT_TIMESTAMP - INTERVAL '1 day' * p_days
    GROUP BY evm.symbol, evm.horizon;
END;
$$ LANGUAGE plpgsql STABLE;

-- Grant permissions
GRANT SELECT ON public.ensemble_validation_metrics TO authenticated;
GRANT INSERT ON public.ensemble_validation_metrics TO authenticated;
GRANT UPDATE ON public.ensemble_validation_metrics TO authenticated;
GRANT SELECT ON public.vw_overfitting_symbols TO authenticated;
GRANT SELECT ON public.vw_divergence_trends TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_ensemble_stats TO authenticated;
