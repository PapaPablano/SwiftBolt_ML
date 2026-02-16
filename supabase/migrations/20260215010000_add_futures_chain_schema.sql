-- ============================================================================
-- SwiftBolt ML - Futures Chain Schema
-- Migration: 20260215010000_add_futures_chain_schema.sql
-- ============================================================================
-- Adds comprehensive futures reference data layer for full contract discovery
-- Supports: ES, NQ, RTY, YM, EMD (indices) + GC, SI, HG (metals) MVP roots
-- ============================================================================

-- ============================================================================
-- ENUM TYPES
-- ============================================================================

CREATE TYPE futures_sector AS ENUM ('indices', 'metals', 'energy', 'rates', 'agriculture', 'softs');
CREATE TYPE roll_method AS ENUM ('volume', 'open_interest', 'calendar');
CREATE TYPE adjustment_method AS ENUM ('none', 'additive', 'multiplicative');

-- ============================================================================
-- FUTURES ROOTS TABLE
-- ============================================================================
-- Master list of futures roots with specifications

CREATE TABLE futures_roots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL UNIQUE, -- e.g., 'GC', 'ES', 'NQ'
    name TEXT NOT NULL, -- e.g., 'Gold', 'E-mini S&P 500'
    exchange TEXT NOT NULL, -- e.g., 'COMEX', 'CME'
    sector futures_sector NOT NULL,
    tick_size NUMERIC(20, 6) NOT NULL,
    point_value NUMERIC(20, 6) NOT NULL, -- Dollar value per point/tick
    currency TEXT NOT NULL DEFAULT 'USD',
    session_template TEXT, -- e.g., 'CME_US_Index', 'COMEX_Metals'
    trading_start_time TIME, -- e.g., '18:00:00' for ES overnight
    trading_end_time TIME, -- e.g., '17:00:00' next day
    timezone TEXT DEFAULT 'America/New_York',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_futures_roots_symbol ON futures_roots(symbol);
CREATE INDEX idx_futures_roots_sector ON futures_roots(sector);
CREATE INDEX idx_futures_roots_exchange ON futures_roots(exchange);

COMMENT ON TABLE futures_roots IS 'Futures root symbols with contract specifications';
COMMENT ON COLUMN futures_roots.symbol IS 'Root symbol (e.g., GC, ES)';
COMMENT ON COLUMN futures_roots.point_value IS 'Dollar value per full point move';

-- ============================================================================
-- FUTURES CONTRACTS TABLE
-- ============================================================================
-- Individual dated contracts for each root

CREATE TABLE futures_contracts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    root_id UUID NOT NULL REFERENCES futures_roots(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL UNIQUE, -- Full contract symbol, e.g., 'GCZ25', 'ESH26'
    contract_code TEXT NOT NULL, -- Month code + year, e.g., 'Z25', 'H26'
    expiry_month INTEGER NOT NULL CHECK (expiry_month >= 1 AND expiry_month <= 12),
    expiry_year INTEGER NOT NULL,
    last_trade_date DATE,
    first_notice_date DATE, -- For physically delivered contracts
    settlement_date DATE, -- For cash-settled contracts
    contract_size TEXT, -- e.g., '100 troy oz' for GC
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_spot BOOLEAN NOT NULL DEFAULT FALSE, -- Is this the current front month?
    volume_30d NUMERIC(20, 2), -- 30-day average volume
    open_interest NUMERIC(20, 2), -- Latest open interest
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Prevent duplicate contracts per root/month/year
    UNIQUE(root_id, expiry_month, expiry_year)
);

CREATE INDEX idx_futures_contracts_root ON futures_contracts(root_id);
CREATE INDEX idx_futures_contracts_symbol ON futures_contracts(symbol);
CREATE INDEX idx_futures_contracts_active ON futures_contracts(root_id, is_active);
CREATE INDEX idx_futures_contracts_expiry ON futures_contracts(expiry_year, expiry_month);

COMMENT ON TABLE futures_contracts IS 'Individual dated futures contracts with expiry information';
COMMENT ON COLUMN futures_contracts.symbol IS 'Full contract symbol (e.g., GCZ25, ESH26)';

-- ============================================================================
-- FUTURES ROLL CONFIGURATION TABLE
-- ============================================================================
-- Per-root configuration for continuous contract generation

CREATE TABLE futures_roll_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    root_id UUID NOT NULL REFERENCES futures_roots(id) ON DELETE CASCADE,
    roll_method roll_method NOT NULL DEFAULT 'volume',
    adjustment_method adjustment_method NOT NULL DEFAULT 'none',
    volume_threshold_days INTEGER DEFAULT 3, -- Days before expiry to check volume
    oi_threshold_ratio NUMERIC(5, 4) DEFAULT 0.5, -- OI ratio to trigger roll
    roll_offset_days INTEGER DEFAULT 0, -- Days before expiry to roll (0 = on trigger)
    auto_roll_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(root_id)
);

CREATE INDEX idx_futures_roll_config_root ON futures_roll_config(root_id);
CREATE INDEX idx_futures_roll_config_auto ON futures_roll_config(auto_roll_enabled);

COMMENT ON TABLE futures_roll_config IS 'Configuration for automatic continuous contract rolling';

-- ============================================================================
-- FUTURES ROLL EVENTS TABLE
-- ============================================================================
-- Historical record of roll events for reproducibility

CREATE TABLE futures_roll_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    root_id UUID NOT NULL REFERENCES futures_roots(id) ON DELETE CASCADE,
    from_contract_id UUID NOT NULL REFERENCES futures_contracts(id),
    to_contract_id UUID NOT NULL REFERENCES futures_contracts(id),
    roll_date DATE NOT NULL,
    trigger_method roll_method NOT NULL,
    volume_ratio NUMERIC(10, 6), -- Volume ratio at roll time
    oi_ratio NUMERIC(10, 6), -- Open interest ratio at roll time
    price_gap NUMERIC(20, 6), -- Price difference between contracts at roll
    adjustment_factor NUMERIC(20, 6), -- For multiplicative adjustment
    adjustment_offset NUMERIC(20, 6), -- For additive adjustment
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_futures_roll_events_root ON futures_roll_events(root_id);
CREATE INDEX idx_futures_roll_events_date ON futures_roll_events(roll_date DESC);
CREATE INDEX idx_futures_roll_events_from ON futures_roll_events(from_contract_id);
CREATE INDEX idx_futures_roll_events_to ON futures_roll_events(to_contract_id);

COMMENT ON TABLE futures_roll_events IS 'Historical record of continuous contract roll events';

-- ============================================================================
-- FUTURES CONTINUOUS MAP TABLE
-- ============================================================================
-- Maps continuous aliases (GC1!, GC2!) to actual dated contracts over time

CREATE TABLE futures_continuous_map (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    root_id UUID NOT NULL REFERENCES futures_roots(id) ON DELETE CASCADE,
    depth INTEGER NOT NULL CHECK (depth >= 1 AND depth <= 12), -- 1 = front month, 2 = second month, etc.
    continuous_alias TEXT NOT NULL, -- e.g., 'GC1!', 'GC2!'
    contract_id UUID NOT NULL REFERENCES futures_contracts(id),
    valid_from DATE NOT NULL,
    valid_until DATE, -- NULL means currently active
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(root_id, depth, valid_from)
);

CREATE INDEX idx_futures_continuous_map_root ON futures_continuous_map(root_id);
CREATE INDEX idx_futures_continuous_map_active ON futures_continuous_map(root_id, depth, is_active);
CREATE INDEX idx_futures_continuous_map_alias ON futures_continuous_map(continuous_alias);
CREATE INDEX idx_futures_continuous_map_valid ON futures_continuous_map(valid_from, valid_until);

COMMENT ON TABLE futures_continuous_map IS 'Mapping of continuous contract aliases to dated contracts';
COMMENT ON COLUMN futures_continuous_map.depth IS '1=front month, 2=second month, etc.';

-- ============================================================================
-- OHLC BARS V2 EXTENSION FOR FUTURES
-- ============================================================================
-- Add futures-specific columns to existing ohlc_bars_v2 table if it exists
-- Otherwise, ensure the symbols table can reference futures

-- First, check if we need to update the symbols table to link to futures_roots
ALTER TABLE symbols 
ADD COLUMN IF NOT EXISTS futures_root_id UUID REFERENCES futures_roots(id),
ADD COLUMN IF NOT EXISTS is_continuous BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_symbols_futures_root ON symbols(futures_root_id);
CREATE INDEX IF NOT EXISTS idx_symbols_is_continuous ON symbols(is_continuous);

COMMENT ON COLUMN symbols.futures_root_id IS 'Links a symbol to its futures root (for dated contracts)';
COMMENT ON COLUMN symbols.is_continuous IS 'True if this is a continuous contract alias (e.g., GC1!)';

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to generate contract symbol from root, month, year
CREATE OR REPLACE FUNCTION generate_contract_symbol(
    p_root TEXT,
    p_month INTEGER,
    p_year INTEGER
) RETURNS TEXT AS $$
DECLARE
    v_month_code CHAR(1);
    v_year_suffix TEXT;
BEGIN
    -- CME/CBOT/COMEX month codes
    v_month_code := CASE p_month
        WHEN 1 THEN 'F'
        WHEN 2 THEN 'G'
        WHEN 3 THEN 'H'
        WHEN 4 THEN 'J'
        WHEN 5 THEN 'K'
        WHEN 6 THEN 'M'
        WHEN 7 THEN 'N'
        WHEN 8 THEN 'Q'
        WHEN 9 THEN 'U'
        WHEN 10 THEN 'V'
        WHEN 11 THEN 'X'
        WHEN 12 THEN 'Z'
    END;
    
    -- Use last 2 digits of year
    v_year_suffix := RIGHT(p_year::TEXT, 2);
    
    RETURN p_root || v_month_code || v_year_suffix;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION generate_contract_symbol IS 'Generate CME/CBOT/COMEX contract symbol from root, month, year';

-- Function to get current continuous contract mapping
CREATE OR REPLACE FUNCTION get_continuous_contract(
    p_root TEXT,
    p_depth INTEGER DEFAULT 1,
    p_as_of DATE DEFAULT CURRENT_DATE
) RETURNS TABLE (
    continuous_alias TEXT,
    contract_symbol TEXT,
    contract_id UUID,
    expiry_month INTEGER,
    expiry_year INTEGER,
    last_trade_date DATE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        fcm.continuous_alias,
        fc.symbol AS contract_symbol,
        fc.id AS contract_id,
        fc.expiry_month,
        fc.expiry_year,
        fc.last_trade_date
    FROM futures_continuous_map fcm
    JOIN futures_roots fr ON fcm.root_id = fr.id
    JOIN futures_contracts fc ON fcm.contract_id = fc.id
    WHERE fr.symbol = p_root
      AND fcm.depth = p_depth
      AND fcm.is_active = TRUE
      AND fcm.valid_from <= p_as_of
      AND (fcm.valid_until IS NULL OR fcm.valid_until >= p_as_of);
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_continuous_contract IS 'Get the current dated contract for a continuous alias';

-- Function to resolve any symbol (dated or continuous) to actual contract
CREATE OR REPLACE FUNCTION resolve_futures_symbol(
    p_symbol TEXT,
    p_as_of DATE DEFAULT CURRENT_DATE
) RETURNS TABLE (
    resolved_symbol TEXT,
    is_continuous BOOLEAN,
    root_symbol TEXT,
    depth INTEGER,
    expiry_month INTEGER,
    expiry_year INTEGER,
    last_trade_date DATE
) AS $$
BEGIN
    -- First, check if it's a dated contract directly
    IF EXISTS (SELECT 1 FROM futures_contracts WHERE symbol = p_symbol) THEN
        RETURN QUERY
        SELECT 
            fc.symbol AS resolved_symbol,
            FALSE AS is_continuous,
            fr.symbol AS root_symbol,
            0 AS depth,
            fc.expiry_month,
            fc.expiry_year,
            fc.last_trade_date
        FROM futures_contracts fc
        JOIN futures_roots fr ON fc.root_id = fr.id
        WHERE fc.symbol = p_symbol;
        RETURN;
    END IF;
    
    -- Check if it's a continuous alias (e.g., GC1!)
    IF p_symbol ~ '^[A-Z]{1,4}[0-9]{1,2}!$' THEN
        RETURN QUERY
        SELECT 
            fc.symbol AS resolved_symbol,
            TRUE AS is_continuous,
            fr.symbol AS root_symbol,
            fcm.depth,
            fc.expiry_month,
            fc.expiry_year,
            fc.last_trade_date
        FROM futures_continuous_map fcm
        JOIN futures_roots fr ON fcm.root_id = fr.id
        JOIN futures_contracts fc ON fcm.contract_id = fc.id
        WHERE fcm.continuous_alias = p_symbol
          AND fcm.is_active = TRUE
          AND fcm.valid_from <= p_as_of
          AND (fcm.valid_until IS NULL OR fcm.valid_until >= p_as_of);
        RETURN;
    END IF;
    
    -- If no match, return empty
    RETURN;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION resolve_futures_symbol IS 'Resolve any futures symbol (dated or continuous) to actual contract details';

-- ============================================================================
-- SEED MVP FUTURES ROOTS
-- ============================================================================

INSERT INTO futures_roots (symbol, name, exchange, sector, tick_size, point_value, session_template) VALUES
-- US Index Futures
('ES', 'E-mini S&P 500', 'CME', 'indices', 0.25, 50.00, 'CME_US_Index'),
('NQ', 'E-mini NASDAQ-100', 'CME', 'indices', 0.25, 20.00, 'CME_US_Index'),
('RTY', 'E-mini Russell 2000', 'CME', 'indices', 0.10, 50.00, 'CME_US_Index'),
('YM', 'E-mini Dow ($5)', 'CBOT', 'indices', 1.00, 5.00, 'CBOT_Index'),
('EMD', 'E-mini S&P MidCap 400', 'CME', 'indices', 0.10, 100.00, 'CME_US_Index'),
-- Metals Futures
('GC', 'Gold', 'COMEX', 'metals', 0.10, 100.00, 'COMEX_Metals'),
('SI', 'Silver', 'COMEX', 'metals', 0.005, 5000.00, 'COMEX_Metals'),
('HG', 'Copper', 'COMEX', 'metals', 0.0005, 25000.00, 'COMEX_Metals')
ON CONFLICT (symbol) DO NOTHING;

-- ============================================================================
-- SEED DEFAULT ROLL CONFIGURATIONS
-- ============================================================================

INSERT INTO futures_roll_config (root_id, roll_method, adjustment_method, auto_roll_enabled)
SELECT id, 'volume', 'none', TRUE FROM futures_roots
ON CONFLICT (root_id) DO NOTHING;

-- ============================================================================
-- ROW LEVEL SECURITY POLICIES
-- ============================================================================

-- Enable RLS on new tables
ALTER TABLE futures_roots ENABLE ROW LEVEL SECURITY;
ALTER TABLE futures_contracts ENABLE ROW LEVEL SECURITY;
ALTER TABLE futures_roll_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE futures_roll_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE futures_continuous_map ENABLE ROW LEVEL SECURITY;

-- Allow read access to all authenticated and anonymous users
CREATE POLICY "Allow read access to futures_roots" ON futures_roots
    FOR SELECT USING (true);

CREATE POLICY "Allow read access to futures_contracts" ON futures_contracts
    FOR SELECT USING (true);

CREATE POLICY "Allow read access to futures_roll_config" ON futures_roll_config
    FOR SELECT USING (true);

CREATE POLICY "Allow read access to futures_roll_events" ON futures_roll_events
    FOR SELECT USING (true);

CREATE POLICY "Allow read access to futures_continuous_map" ON futures_continuous_map
    FOR SELECT USING (true);

-- ============================================================================
-- TRIGGERS FOR UPDATED_AT
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_futures_roots_updated_at
    BEFORE UPDATE ON futures_roots
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_futures_contracts_updated_at
    BEFORE UPDATE ON futures_contracts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_futures_roll_config_updated_at
    BEFORE UPDATE ON futures_roll_config
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_futures_continuous_map_updated_at
    BEFORE UPDATE ON futures_continuous_map
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- VIEWS FOR CONVENIENCE
-- ============================================================================

-- View: Active futures chain with continuous mapping
CREATE OR REPLACE VIEW v_futures_chain AS
SELECT 
    fr.symbol AS root_symbol,
    fr.name AS root_name,
    fr.sector,
    fr.exchange,
    fc.symbol AS contract_symbol,
    fc.contract_code,
    fc.expiry_month,
    fc.expiry_year,
    fc.last_trade_date,
    fc.first_notice_date,
    fc.is_active,
    fc.is_spot,
    fc.volume_30d,
    fc.open_interest,
    fcm.continuous_alias,
    fcm.depth,
    fcm.is_active AS is_continuous_active
FROM futures_roots fr
LEFT JOIN futures_contracts fc ON fr.id = fc.root_id
LEFT JOIN futures_continuous_map fcm ON fc.id = fcm.contract_id AND fcm.is_active = TRUE
WHERE fc.is_active = TRUE
ORDER BY fr.symbol, fc.expiry_year, fc.expiry_month;

COMMENT ON VIEW v_futures_chain IS 'Active futures contracts with continuous mapping info';

-- View: Current front month contracts for all roots
CREATE OR REPLACE VIEW v_futures_front_month AS
SELECT 
    fr.symbol AS root_symbol,
    fr.name AS root_name,
    fc.symbol AS front_contract,
    fc.expiry_month,
    fc.expiry_year,
    fc.last_trade_date,
    fc.volume_30d,
    fc.open_interest,
    DATE_PART('day', fc.last_trade_date - CURRENT_DATE) AS days_to_expiry
FROM futures_roots fr
JOIN futures_contracts fc ON fr.id = fc.root_id
WHERE fc.is_active = TRUE
  AND fc.is_spot = TRUE;

COMMENT ON VIEW v_futures_front_month IS 'Current front month (spot) contracts for all roots';
