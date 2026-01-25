-- Fix indicator_values timeframe constraint to include h8
-- This allows 8-hour indicator snapshots to be saved

DO $$
BEGIN
    -- Drop the existing constraint if it exists
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'indicator_values_timeframe_check'
        AND table_name = 'indicator_values'
    ) THEN
        ALTER TABLE indicator_values 
        DROP CONSTRAINT indicator_values_timeframe_check;
    END IF;
    
    -- Add the updated constraint with h8 included
    ALTER TABLE indicator_values
    ADD CONSTRAINT indicator_values_timeframe_check 
    CHECK (timeframe IN ('m1', 'm5', 'm15', 'm30', 'h1', 'h4', 'h8', 'd1', 'w1', 'M'));
END $$;

COMMENT ON CONSTRAINT indicator_values_timeframe_check ON indicator_values IS
'Validates timeframe values including h8 (8-hour bars)';
