-- GA Strategy Parameters Storage
-- Stores optimized trading parameters from genetic algorithm runs

-- Table for GA-optimized strategy parameters
CREATE TABLE IF NOT EXISTS ga_strategy_params (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,

    -- Strategy genes (JSON blob for flexibility)
    genes JSONB NOT NULL,

    -- Fitness metrics from backtesting
    fitness JSONB,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,

    -- Training info
    training_days INTEGER DEFAULT 30,
    training_samples INTEGER,
    validation_win_rate DECIMAL(5,4),
    validation_profit_factor DECIMAL(6,3),

    -- GA run metadata
    generations_run INTEGER,
    population_size INTEGER,

    CONSTRAINT unique_active_per_symbol UNIQUE (symbol, is_active)
        DEFERRABLE INITIALLY DEFERRED
);

-- Index for quick lookups
CREATE INDEX idx_ga_params_symbol ON ga_strategy_params(symbol);
CREATE INDEX idx_ga_params_active ON ga_strategy_params(is_active) WHERE is_active = TRUE;

-- Track GA optimization history
CREATE TABLE IF NOT EXISTS ga_optimization_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,

    -- Configuration
    generations INTEGER NOT NULL,
    population_size INTEGER NOT NULL,
    training_days INTEGER NOT NULL,

    -- Results
    best_fitness_score DECIMAL(6,4),
    best_win_rate DECIMAL(5,4),
    best_profit_factor DECIMAL(6,3),
    best_sharpe DECIMAL(6,3),

    -- Top 5 strategies stored as JSON array
    top_strategies JSONB,

    -- Status
    status TEXT DEFAULT 'running',
    error_message TEXT
);

CREATE INDEX idx_ga_runs_symbol ON ga_optimization_runs(symbol);
CREATE INDEX idx_ga_runs_status ON ga_optimization_runs(status);

-- Trade history for GA backtesting validation
CREATE TABLE IF NOT EXISTS ga_backtest_trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES ga_optimization_runs(id) ON DELETE CASCADE,
    strategy_rank INTEGER, -- 1-5 for top strategies

    -- Trade details
    symbol TEXT NOT NULL,
    contract_symbol TEXT NOT NULL,
    entry_date TIMESTAMPTZ,
    exit_date TIMESTAMPTZ,
    entry_price DECIMAL(10,4),
    exit_price DECIMAL(10,4),

    -- Greeks at entry
    delta_entry DECIMAL(6,4),
    gamma_entry DECIMAL(8,6),
    vega_entry DECIMAL(8,4),
    theta_entry DECIMAL(8,4),

    -- Performance
    pnl_pct DECIMAL(8,4),
    duration_minutes INTEGER,
    exit_reason TEXT,
    entry_signal TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_backtest_trades_run ON ga_backtest_trades(run_id);
CREATE INDEX idx_backtest_trades_symbol ON ga_backtest_trades(symbol);

-- Function to get active GA parameters for a symbol
CREATE OR REPLACE FUNCTION get_ga_parameters(p_symbol TEXT)
RETURNS TABLE (
    id UUID,
    genes JSONB,
    fitness JSONB,
    created_at TIMESTAMPTZ,
    win_rate DECIMAL,
    profit_factor DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        g.id,
        g.genes,
        g.fitness,
        g.created_at,
        g.validation_win_rate,
        g.validation_profit_factor
    FROM ga_strategy_params g
    WHERE g.symbol = p_symbol
      AND g.is_active = TRUE
    ORDER BY g.created_at DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Function to deactivate old parameters and insert new
CREATE OR REPLACE FUNCTION upsert_ga_parameters(
    p_symbol TEXT,
    p_genes JSONB,
    p_fitness JSONB,
    p_training_days INTEGER DEFAULT 30,
    p_training_samples INTEGER DEFAULT NULL,
    p_generations INTEGER DEFAULT NULL,
    p_population INTEGER DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    new_id UUID;
BEGIN
    -- Deactivate existing active parameters
    UPDATE ga_strategy_params
    SET is_active = FALSE, updated_at = NOW()
    WHERE symbol = p_symbol AND is_active = TRUE;

    -- Insert new parameters
    INSERT INTO ga_strategy_params (
        symbol, genes, fitness, training_days, training_samples,
        validation_win_rate, validation_profit_factor,
        generations_run, population_size, is_active
    ) VALUES (
        p_symbol, p_genes, p_fitness, p_training_days, p_training_samples,
        (p_fitness->>'win_rate')::DECIMAL,
        (p_fitness->>'profit_factor')::DECIMAL,
        p_generations, p_population, TRUE
    )
    RETURNING id INTO new_id;

    RETURN new_id;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT SELECT ON ga_strategy_params TO anon, authenticated;
GRANT SELECT ON ga_optimization_runs TO anon, authenticated;
GRANT SELECT ON ga_backtest_trades TO anon, authenticated;

-- Service role gets full access
GRANT ALL ON ga_strategy_params TO service_role;
GRANT ALL ON ga_optimization_runs TO service_role;
GRANT ALL ON ga_backtest_trades TO service_role;

-- Function to count ranking data for GA training
CREATE OR REPLACE FUNCTION count_ranking_data(p_symbol TEXT)
RETURNS TABLE (
    days INTEGER,
    samples BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(DISTINCT DATE(run_at))::INTEGER as days,
        COUNT(*)::BIGINT as samples
    FROM options_ranks o
    JOIN symbols s ON s.id = o.underlying_symbol_id
    WHERE s.ticker = p_symbol
      AND run_at > NOW() - INTERVAL '60 days';
END;
$$ LANGUAGE plpgsql;

-- Comments
COMMENT ON TABLE ga_strategy_params IS 'Stores GA-optimized trading strategy parameters per symbol';
COMMENT ON TABLE ga_optimization_runs IS 'History of GA optimization runs with results';
COMMENT ON TABLE ga_backtest_trades IS 'Sample trades from GA backtesting for analysis';
COMMENT ON FUNCTION get_ga_parameters IS 'Get active GA parameters for a symbol';
COMMENT ON FUNCTION upsert_ga_parameters IS 'Insert new GA parameters, deactivating old ones';
COMMENT ON FUNCTION count_ranking_data IS 'Count ranking data days and samples for GA training';
