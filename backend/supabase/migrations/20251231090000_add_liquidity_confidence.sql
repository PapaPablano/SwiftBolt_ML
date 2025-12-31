-- Migration: Add liquidity_confidence column to options_ranks
-- This column stores the liquidity confidence multiplier (0.1 to 1.0)
-- used to dampen momentum scores for low-volume/low-price options

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'options_ranks' 
                   AND column_name = 'liquidity_confidence') THEN
        ALTER TABLE options_ranks 
        ADD COLUMN liquidity_confidence DOUBLE PRECISION DEFAULT 1.0;
        
        COMMENT ON COLUMN options_ranks.liquidity_confidence IS 
            'Liquidity confidence multiplier (0.1-1.0). Low values indicate '
            'noisy momentum signals due to low volume/OI/price.';
    END IF;
END $$;

-- Create index for filtering by liquidity
CREATE INDEX IF NOT EXISTS idx_options_ranks_liquidity 
    ON options_ranks(liquidity_confidence) 
    WHERE liquidity_confidence < 0.5;
