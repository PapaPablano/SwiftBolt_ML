-- Migration: Add iv_rank_source column to options_ranks
-- Tracks the source of IV rank calculation for analysis/debugging:
-- - 'rpc': From database RPC with historical 52-week stats (preferred)
-- - 'chain_estimate': Estimated from current options chain min/max (less reliable)
-- - 'default': No IV data available, defaulted to 50
-- - 'rpc_no_range': RPC stats had zero range
-- - 'chain_no_range': Chain estimate had zero range

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'options_ranks'
                   AND column_name = 'iv_rank_source') THEN
        ALTER TABLE options_ranks
        ADD COLUMN iv_rank_source TEXT DEFAULT 'rpc';

        COMMENT ON COLUMN options_ranks.iv_rank_source IS
            'Source of IV rank calculation: rpc (historical stats), chain_estimate (current chain), default (no data)';
    END IF;
END $$;

-- Create index for filtering by IV source (useful for analyzing data quality)
CREATE INDEX IF NOT EXISTS idx_options_ranks_iv_source
    ON options_ranks(iv_rank_source)
    WHERE iv_rank_source != 'rpc';

-- Also ensure signals column can store JSON properly
-- Update any existing plain string signals to JSON arrays
DO $$
BEGIN
    -- Check if signals column exists and update format
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'options_ranks'
               AND column_name = 'signals') THEN
        -- Update non-JSON signals to JSON array format
        UPDATE options_ranks
        SET signals = '[]'::TEXT
        WHERE signals IS NULL OR signals = '';

        -- Update comma-separated strings to JSON arrays
        UPDATE options_ranks
        SET signals = (
            SELECT json_agg(trim(signal))::TEXT
            FROM unnest(string_to_array(signals, ',')) AS signal
            WHERE trim(signal) != ''
        )
        WHERE signals IS NOT NULL
        AND signals != ''
        AND signals NOT LIKE '[%';
    END IF;
END $$;
