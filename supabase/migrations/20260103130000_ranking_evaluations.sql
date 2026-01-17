-- Ranking Evaluations table for options ranking validation
-- Equivalent to forecast_evaluations for the ranking system
-- Stores daily IC metrics, stability, hit rate, and alerts

CREATE TABLE IF NOT EXISTS ranking_evaluations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol_id UUID REFERENCES symbols(id),
    
    -- Health status
    is_healthy BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Sample sizes
    n_days INTEGER NOT NULL DEFAULT 0,
    n_contracts INTEGER NOT NULL DEFAULT 0,
    
    -- IC metrics (Information Coefficient)
    mean_ic DOUBLE PRECISION,
    std_ic DOUBLE PRECISION,
    min_ic DOUBLE PRECISION,
    max_ic DOUBLE PRECISION,
    ic_trend DOUBLE PRECISION,
    
    -- Stability metrics
    stability DOUBLE PRECISION,
    
    -- Hit rate metrics
    hit_rate DOUBLE PRECISION,
    hit_rate_n INTEGER,
    hit_rate_ci_lower DOUBLE PRECISION,
    hit_rate_ci_upper DOUBLE PRECISION,
    
    -- Leakage detection
    leakage_suspected BOOLEAN DEFAULT FALSE,
    leakage_score DOUBLE PRECISION,
    permuted_ic_mean DOUBLE PRECISION,
    
    -- Calibration metrics
    calibration_error DOUBLE PRECISION,
    calibration_is_monotonic BOOLEAN,
    
    -- Regime info
    trend_regime TEXT,
    vol_regime TEXT,
    regime_adx DOUBLE PRECISION,
    regime_atr_pct DOUBLE PRECISION,
    
    -- Alerts
    n_alerts INTEGER DEFAULT 0,
    alert_types TEXT[],
    has_critical_alert BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    horizon TEXT DEFAULT '1D',
    ranking_mode TEXT DEFAULT 'entry',
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for time-series queries
CREATE INDEX IF NOT EXISTS idx_ranking_evaluations_evaluated_at 
    ON ranking_evaluations(evaluated_at DESC);

-- Index for symbol lookups
CREATE INDEX IF NOT EXISTS idx_ranking_evaluations_symbol 
    ON ranking_evaluations(symbol_id, evaluated_at DESC);

-- Index for health status monitoring
CREATE INDEX IF NOT EXISTS idx_ranking_evaluations_health 
    ON ranking_evaluations(is_healthy, evaluated_at DESC);

-- RLS policies
ALTER TABLE ranking_evaluations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role can manage ranking_evaluations"
    ON ranking_evaluations
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Authenticated users can read ranking_evaluations"
    ON ranking_evaluations
    FOR SELECT
    TO authenticated
    USING (true);

-- Function to get latest ranking health for a symbol
CREATE OR REPLACE FUNCTION get_ranking_health(p_symbol_id UUID DEFAULT NULL)
RETURNS TABLE (
    symbol_id UUID,
    is_healthy BOOLEAN,
    mean_ic DOUBLE PRECISION,
    stability DOUBLE PRECISION,
    hit_rate DOUBLE PRECISION,
    leakage_suspected BOOLEAN,
    n_alerts INTEGER,
    evaluated_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT ON (re.symbol_id)
        re.symbol_id,
        re.is_healthy,
        re.mean_ic,
        re.stability,
        re.hit_rate,
        re.leakage_suspected,
        re.n_alerts,
        re.evaluated_at
    FROM ranking_evaluations re
    WHERE (p_symbol_id IS NULL OR re.symbol_id = p_symbol_id)
    ORDER BY re.symbol_id, re.evaluated_at DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to check for IC collapse (alert trigger)
CREATE OR REPLACE FUNCTION check_ranking_ic_collapse()
RETURNS TABLE (
    symbol_id UUID,
    mean_ic DOUBLE PRECISION,
    ic_trend DOUBLE PRECISION,
    days_declining INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH recent_evals AS (
        SELECT 
            re.symbol_id,
            re.mean_ic,
            re.ic_trend,
            re.evaluated_at,
            ROW_NUMBER() OVER (
                PARTITION BY re.symbol_id 
                ORDER BY re.evaluated_at DESC
            ) as rn
        FROM ranking_evaluations re
        WHERE re.evaluated_at > NOW() - INTERVAL '7 days'
    ),
    declining AS (
        SELECT 
            r.symbol_id,
            COUNT(*) FILTER (WHERE r.ic_trend < 0) as days_declining
        FROM recent_evals r
        WHERE r.rn <= 5
        GROUP BY r.symbol_id
    )
    SELECT 
        r.symbol_id,
        r.mean_ic,
        r.ic_trend,
        COALESCE(d.days_declining, 0)::INTEGER as days_declining
    FROM recent_evals r
    JOIN declining d ON r.symbol_id = d.symbol_id
    WHERE r.rn = 1
      AND (r.mean_ic < 0.02 OR d.days_declining >= 3);
END;
$$ LANGUAGE plpgsql;

COMMENT ON TABLE ranking_evaluations IS 
    'Stores daily validation metrics for options ranking system - equivalent to forecast_evaluations';
