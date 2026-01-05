-- Migration: Add OHLC data quality checks and monitoring
-- Detects anomalous high/low values that don't match close prices

-- Function to detect OHLC anomalies
CREATE OR REPLACE FUNCTION detect_ohlc_anomalies(
    p_symbol_id UUID DEFAULT NULL,
    p_timeframe TEXT DEFAULT 'd1',
    p_lookback_days INT DEFAULT 90,
    p_high_threshold NUMERIC DEFAULT 1.15,  -- High > close * 1.15 (15% above)
    p_low_threshold NUMERIC DEFAULT 0.85    -- Low < close * 0.85 (15% below)
)
RETURNS TABLE (
    symbol_id UUID,
    ticker TEXT,
    ts TIMESTAMPTZ,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    high_deviation_pct NUMERIC,
    low_deviation_pct NUMERIC,
    issue_type TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        o.symbol_id,
        s.ticker,
        o.ts,
        o.open,
        o.high,
        o.low,
        o.close,
        ROUND((o.high / o.close - 1) * 100, 2) as high_deviation_pct,
        ROUND((1 - o.low / o.close) * 100, 2) as low_deviation_pct,
        CASE 
            WHEN o.high > o.close * p_high_threshold THEN 'HIGH_ANOMALY'
            WHEN o.low < o.close * p_low_threshold THEN 'LOW_ANOMALY'
            WHEN o.high < o.close THEN 'HIGH_BELOW_CLOSE'
            WHEN o.low > o.close THEN 'LOW_ABOVE_CLOSE'
            ELSE 'UNKNOWN'
        END as issue_type
    FROM ohlc_bars o
    JOIN symbols s ON o.symbol_id = s.id
    WHERE o.timeframe::TEXT = p_timeframe
        AND (p_symbol_id IS NULL OR o.symbol_id = p_symbol_id)
        AND o.ts >= NOW() - (p_lookback_days || ' days')::INTERVAL
        AND (
            o.high > o.close * p_high_threshold 
            OR o.low < o.close * p_low_threshold
            OR o.high < o.close
            OR o.low > o.close
        )
    ORDER BY o.ts DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to auto-correct obvious OHLC anomalies
-- This is conservative and only fixes clear data errors
CREATE OR REPLACE FUNCTION auto_correct_ohlc_anomalies(
    p_symbol_id UUID DEFAULT NULL,
    p_timeframe TEXT DEFAULT 'd1',
    p_dry_run BOOLEAN DEFAULT TRUE
)
RETURNS TABLE (
    symbol_id UUID,
    ticker TEXT,
    ts TIMESTAMPTZ,
    old_high NUMERIC,
    new_high NUMERIC,
    old_low NUMERIC,
    new_low NUMERIC,
    action TEXT
) AS $$
DECLARE
    v_record RECORD;
    v_new_high NUMERIC;
    v_new_low NUMERIC;
BEGIN
    FOR v_record IN 
        SELECT * FROM detect_ohlc_anomalies(p_symbol_id, p_timeframe, 90, 1.15, 0.85)
    LOOP
        v_new_high := v_record.high;
        v_new_low := v_record.low;
        
        -- Fix high anomalies: cap at close * 1.03 (reasonable intraday range)
        IF v_record.issue_type = 'HIGH_ANOMALY' THEN
            v_new_high := v_record.close * 1.03;
        END IF;
        
        -- Fix low anomalies: floor at close * 0.97
        IF v_record.issue_type = 'LOW_ANOMALY' THEN
            v_new_low := v_record.close * 0.97;
        END IF;
        
        -- Fix high below close: set high = close
        IF v_record.issue_type = 'HIGH_BELOW_CLOSE' THEN
            v_new_high := v_record.close;
        END IF;
        
        -- Fix low above close: set low = close
        IF v_record.issue_type = 'LOW_ABOVE_CLOSE' THEN
            v_new_low := v_record.close;
        END IF;
        
        -- Apply correction if not dry run
        IF NOT p_dry_run AND (v_new_high != v_record.high OR v_new_low != v_record.low) THEN
            UPDATE ohlc_bars
            SET 
                high = v_new_high,
                low = v_new_low,
                updated_at = NOW()
            WHERE ohlc_bars.symbol_id = v_record.symbol_id
                AND ohlc_bars.timeframe = p_timeframe
                AND ohlc_bars.ts = v_record.ts;
        END IF;
        
        -- Return the change record
        RETURN QUERY SELECT 
            v_record.symbol_id,
            v_record.ticker,
            v_record.ts,
            v_record.high as old_high,
            v_new_high as new_high,
            v_record.low as old_low,
            v_new_low as new_low,
            CASE 
                WHEN p_dry_run THEN 'DRY_RUN'
                ELSE 'CORRECTED'
            END as action;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Add trigger to validate OHLC data on insert/update
CREATE OR REPLACE FUNCTION validate_ohlc_data()
RETURNS TRIGGER AS $$
BEGIN
    -- Ensure high >= close and low <= close
    IF NEW.high < NEW.close THEN
        NEW.high := NEW.close;
    END IF;
    
    IF NEW.low > NEW.close THEN
        NEW.low := NEW.close;
    END IF;
    
    -- Ensure high >= open and low <= open
    IF NEW.high < NEW.open THEN
        NEW.high := GREATEST(NEW.open, NEW.close);
    END IF;
    
    IF NEW.low > NEW.open THEN
        NEW.low := LEAST(NEW.open, NEW.close);
    END IF;
    
    -- Flag extreme anomalies (>50% deviation) for review
    IF NEW.high > NEW.close * 1.5 OR NEW.low < NEW.close * 0.5 THEN
        RAISE WARNING 'Extreme OHLC anomaly detected for symbol_id=% ts=% high=% low=% close=%',
            NEW.symbol_id, NEW.ts, NEW.high, NEW.low, NEW.close;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to ohlc_bars table
DROP TRIGGER IF EXISTS trigger_validate_ohlc_data ON ohlc_bars;
CREATE TRIGGER trigger_validate_ohlc_data
    BEFORE INSERT OR UPDATE ON ohlc_bars
    FOR EACH ROW
    EXECUTE FUNCTION validate_ohlc_data();

-- Comments
COMMENT ON FUNCTION detect_ohlc_anomalies IS 'Detects anomalous OHLC values that deviate significantly from close prices';
COMMENT ON FUNCTION auto_correct_ohlc_anomalies IS 'Auto-corrects obvious OHLC data errors (use dry_run=true to preview)';
COMMENT ON FUNCTION validate_ohlc_data IS 'Trigger function to validate OHLC data on insert/update';
