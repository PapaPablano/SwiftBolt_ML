-- Add evaluated_at column to ml_forecasts_intraday table
-- This column tracks when a forecast was evaluated (used by evaluation_job_intraday.py)

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ml_forecasts_intraday' 
        AND column_name = 'evaluated_at'
    ) THEN
        ALTER TABLE ml_forecasts_intraday
        ADD COLUMN evaluated_at TIMESTAMPTZ;
        
        -- Create index for efficient querying of evaluated forecasts
        CREATE INDEX IF NOT EXISTS idx_intraday_forecasts_evaluated_at
        ON ml_forecasts_intraday(evaluated_at);
        
        COMMENT ON COLUMN ml_forecasts_intraday.evaluated_at IS 
            'Timestamp when forecast was evaluated against realized price';
    END IF;
END $$;
