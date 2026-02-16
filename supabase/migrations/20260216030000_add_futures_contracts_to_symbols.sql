-- ============================================================================
-- Add Futures Contracts to Symbols Table
-- Migration: 20260216030000_add_futures_contracts_to_symbols.sql
-- ============================================================================
-- This migration inserts dated futures contracts and continuous aliases
-- into the symbols table so they become searchable and chartable
-- ============================================================================

-- ============================================================================
-- Step 1: Add futures-specific columns to symbols table
-- ============================================================================

ALTER TABLE symbols 
ADD COLUMN IF NOT EXISTS futures_root_id UUID REFERENCES futures_roots(id),
ADD COLUMN IF NOT EXISTS is_continuous BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS expiry_month INTEGER,
ADD COLUMN IF NOT EXISTS expiry_year INTEGER,
ADD COLUMN IF NOT EXISTS last_trade_date DATE;

-- Create index for faster futures lookups
CREATE INDEX IF NOT EXISTS idx_symbols_futures_root ON symbols(futures_root_id);
CREATE INDEX IF NOT EXISTS idx_symbols_is_continuous ON symbols(is_continuous) WHERE is_continuous = TRUE;

-- ============================================================================
-- Step 2: Insert dated futures contracts as searchable symbols
-- ============================================================================

INSERT INTO symbols (
    ticker, 
    asset_type, 
    description, 
    primary_source, 
    futures_root_id, 
    is_continuous,
    expiry_month,
    expiry_year,
    last_trade_date
)
SELECT 
    fc.symbol as ticker,
    'future' as asset_type,
    fr.name || ' ' || fc.contract_code as description,
    'massive' as primary_source,
    fr.id as futures_root_id,
    FALSE as is_continuous,
    fc.expiry_month,
    fc.expiry_year,
    fc.last_trade_date
FROM futures_contracts fc
JOIN futures_roots fr ON fc.root_id = fr.id
WHERE fc.is_active = TRUE
ON CONFLICT (ticker) DO UPDATE SET
    asset_type = EXCLUDED.asset_type,
    description = EXCLUDED.description,
    futures_root_id = EXCLUDED.futures_root_id,
    is_continuous = EXCLUDED.is_continuous,
    expiry_month = EXCLUDED.expiry_month,
    expiry_year = EXCLUDED.expiry_year,
    last_trade_date = EXCLUDED.last_trade_date;

-- ============================================================================
-- Step 3: Insert continuous aliases as searchable symbols
-- ============================================================================

INSERT INTO symbols (
    ticker, 
    asset_type, 
    description, 
    primary_source, 
    futures_root_id, 
    is_continuous
)
SELECT 
    fcm.continuous_alias as ticker,
    'future' as asset_type,
    fr.name || ' (Continuous ' || fcm.depth || ')' as description,
    'massive' as primary_source,
    fr.id as futures_root_id,
    TRUE as is_continuous
FROM futures_continuous_map fcm
JOIN futures_roots fr ON fcm.root_id = fr.id
WHERE fcm.is_active = TRUE
ON CONFLICT (ticker) DO UPDATE SET
    asset_type = EXCLUDED.asset_type,
    description = EXCLUDED.description,
    futures_root_id = EXCLUDED.futures_root_id,
    is_continuous = EXCLUDED.is_continuous;

-- ============================================================================
-- Step 4: Update existing futures roots to mark them as roots
-- ============================================================================

UPDATE symbols 
SET 
    asset_type = 'future',
    futures_root_id = fr.id,
    is_continuous = FALSE
FROM futures_roots fr
WHERE symbols.ticker = fr.symbol
AND (symbols.asset_type != 'future' OR symbols.futures_root_id IS NULL);

-- ============================================================================
-- Step 5: Verify the inserts
-- ============================================================================

-- Count futures symbols by type
SELECT 
    'Roots' as type,
    COUNT(*) as count
FROM symbols s
JOIN futures_roots fr ON s.ticker = fr.symbol

UNION ALL

SELECT 
    'Dated Contracts' as type,
    COUNT(*) as count
FROM symbols
WHERE asset_type = 'future' 
AND is_continuous = FALSE 
AND futures_root_id IS NOT NULL
AND ticker NOT IN (SELECT symbol FROM futures_roots)

UNION ALL

SELECT 
    'Continuous Aliases' as type,
    COUNT(*) as count
FROM symbols
WHERE asset_type = 'future' 
AND is_continuous = TRUE;
