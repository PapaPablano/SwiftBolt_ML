-- Options Snapshots Table
-- Stores historical options chain data for ML training and backtesting
-- Data sourced from Tradier API

-- Create options_snapshots table
CREATE TABLE IF NOT EXISTS options_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    underlying_symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    contract_symbol TEXT NOT NULL,
    option_type TEXT NOT NULL CHECK (option_type IN ('call', 'put')),
    strike NUMERIC(12, 2) NOT NULL,
    expiration DATE NOT NULL,

    -- Pricing
    bid NUMERIC(10, 4),
    ask NUMERIC(10, 4),
    last NUMERIC(10, 4),
    underlying_price NUMERIC(10, 4),

    -- Volume & Interest
    volume INTEGER DEFAULT 0,
    open_interest INTEGER DEFAULT 0,

    -- Greeks
    delta NUMERIC(8, 6),
    gamma NUMERIC(8, 6),
    theta NUMERIC(8, 6),
    vega NUMERIC(8, 6),
    rho NUMERIC(8, 6),
    iv NUMERIC(8, 6),  -- Implied Volatility

    -- Metadata
    snapshot_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Unique constraint for upserts
    CONSTRAINT options_snapshots_unique UNIQUE (contract_symbol, snapshot_time)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_options_snapshots_symbol
    ON options_snapshots(underlying_symbol_id);

CREATE INDEX IF NOT EXISTS idx_options_snapshots_time
    ON options_snapshots(snapshot_time DESC);

CREATE INDEX IF NOT EXISTS idx_options_snapshots_expiration
    ON options_snapshots(expiration);

CREATE INDEX IF NOT EXISTS idx_options_snapshots_contract
    ON options_snapshots(contract_symbol);

-- Composite index for filtering by symbol and time
CREATE INDEX IF NOT EXISTS idx_options_snapshots_symbol_time
    ON options_snapshots(underlying_symbol_id, snapshot_time DESC);

-- Index for strike price queries (ATM/OTM/ITM filtering)
CREATE INDEX IF NOT EXISTS idx_options_snapshots_strike
    ON options_snapshots(underlying_symbol_id, strike);

-- Add comment
COMMENT ON TABLE options_snapshots IS 'Historical options chain data for ML training. Populated by Tradier scraper.';

-- View for latest options by symbol
CREATE OR REPLACE VIEW latest_options AS
SELECT DISTINCT ON (os.contract_symbol)
    os.*,
    s.ticker as underlying_ticker
FROM options_snapshots os
JOIN symbols s ON s.id = os.underlying_symbol_id
ORDER BY os.contract_symbol, os.snapshot_time DESC;

-- Function to get options chain at a specific point in time
CREATE OR REPLACE FUNCTION get_options_chain_at(
    p_symbol TEXT,
    p_time TIMESTAMPTZ DEFAULT NOW()
)
RETURNS TABLE (
    contract_symbol TEXT,
    option_type TEXT,
    strike NUMERIC,
    expiration DATE,
    bid NUMERIC,
    ask NUMERIC,
    last NUMERIC,
    underlying_price NUMERIC,
    volume INTEGER,
    open_interest INTEGER,
    delta NUMERIC,
    gamma NUMERIC,
    theta NUMERIC,
    vega NUMERIC,
    iv NUMERIC,
    snapshot_time TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT ON (os.contract_symbol)
        os.contract_symbol,
        os.option_type,
        os.strike,
        os.expiration,
        os.bid,
        os.ask,
        os.last,
        os.underlying_price,
        os.volume,
        os.open_interest,
        os.delta,
        os.gamma,
        os.theta,
        os.vega,
        os.iv,
        os.snapshot_time
    FROM options_snapshots os
    JOIN symbols s ON s.id = os.underlying_symbol_id
    WHERE s.ticker = p_symbol
      AND os.snapshot_time <= p_time
    ORDER BY os.contract_symbol, os.snapshot_time DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to get options history for a specific contract
CREATE OR REPLACE FUNCTION get_option_history(
    p_contract_symbol TEXT,
    p_days INTEGER DEFAULT 30
)
RETURNS TABLE (
    snapshot_time TIMESTAMPTZ,
    bid NUMERIC,
    ask NUMERIC,
    last NUMERIC,
    underlying_price NUMERIC,
    volume INTEGER,
    open_interest INTEGER,
    delta NUMERIC,
    iv NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        os.snapshot_time,
        os.bid,
        os.ask,
        os.last,
        os.underlying_price,
        os.volume,
        os.open_interest,
        os.delta,
        os.iv
    FROM options_snapshots os
    WHERE os.contract_symbol = p_contract_symbol
      AND os.snapshot_time >= NOW() - (p_days || ' days')::INTERVAL
    ORDER BY os.snapshot_time DESC;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT SELECT ON options_snapshots TO anon, authenticated;
GRANT SELECT ON latest_options TO anon, authenticated;
GRANT ALL ON options_snapshots TO service_role;
