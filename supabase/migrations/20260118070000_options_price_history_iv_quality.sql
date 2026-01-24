-- Migration: Add IV quality fields to options_price_history and snapshots

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'options_price_history'
          AND column_name = 'iv_curve_ok'
    ) THEN
        ALTER TABLE options_price_history
        ADD COLUMN iv_curve_ok BOOLEAN DEFAULT TRUE;

        COMMENT ON COLUMN options_price_history.iv_curve_ok IS
            'True when the IV curve is smooth across strikes (no large jumps).';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'options_price_history'
          AND column_name = 'iv_data_quality_score'
    ) THEN
        ALTER TABLE options_price_history
        ADD COLUMN iv_data_quality_score DOUBLE PRECISION DEFAULT 1.0;

        COMMENT ON COLUMN options_price_history.iv_data_quality_score IS
            'Composite IV data quality score (freshness, coverage, curve smoothness).';
    END IF;
END $$;

CREATE OR REPLACE FUNCTION capture_options_snapshot(p_symbol_id UUID)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_rows_inserted INTEGER;
BEGIN
    -- Insert current options_ranks data into history
    -- Clamp values to fit within column precision limits
    INSERT INTO options_price_history (
        underlying_symbol_id,
        contract_symbol,
        expiry,
        strike,
        side,
        bid,
        ask,
        mark,
        last_price,
        delta,
        gamma,
        theta,
        vega,
        rho,
        implied_vol,
        volume,
        open_interest,
        ml_score,
        iv_curve_ok,
        iv_data_quality_score,
        snapshot_at
    )
    SELECT
        underlying_symbol_id,
        contract_symbol,
        expiry,
        strike,
        side,
        bid,
        ask,
        mark,
        last_price,
        -- Clamp delta to NUMERIC(6,4) range: -99.9999 to 99.9999
        CASE WHEN delta IS NULL THEN NULL
             WHEN delta > 99.9999 THEN 99.9999
             WHEN delta < -99.9999 THEN -99.9999
             ELSE delta END,
        -- Clamp gamma to NUMERIC(8,6) range: -99.999999 to 99.999999
        CASE WHEN gamma IS NULL THEN NULL
             WHEN gamma > 99.999999 THEN 99.999999
             WHEN gamma < -99.999999 THEN -99.999999
             ELSE gamma END,
        -- Clamp theta to NUMERIC(8,6) range: -99.999999 to 99.999999
        CASE WHEN theta IS NULL THEN NULL
             WHEN theta > 99.999999 THEN 99.999999
             WHEN theta < -99.999999 THEN -99.999999
             ELSE theta END,
        -- Clamp vega to NUMERIC(8,6) range: -99.999999 to 99.999999
        CASE WHEN vega IS NULL THEN NULL
             WHEN vega > 99.999999 THEN 99.999999
             WHEN vega < -99.999999 THEN -99.999999
             ELSE vega END,
        -- Clamp rho to NUMERIC(8,6) range: -99.999999 to 99.999999
        CASE WHEN rho IS NULL THEN NULL
             WHEN rho > 99.999999 THEN 99.999999
             WHEN rho < -99.999999 THEN -99.999999
             ELSE rho END,
        -- Clamp implied_vol to NUMERIC(6,4) range: 0 to 99.9999
        CASE WHEN implied_vol IS NULL THEN NULL
             WHEN implied_vol > 99.9999 THEN 99.9999
             WHEN implied_vol < 0 THEN 0
             ELSE implied_vol END,
        volume,
        open_interest,
        -- Clamp ml_score to NUMERIC(5,4) range: 0 to 9.9999
        CASE WHEN ml_score IS NULL THEN NULL
             WHEN ml_score > 9.9999 THEN 9.9999
             WHEN ml_score < 0 THEN 0
             ELSE ml_score END,
        iv_curve_ok,
        iv_data_quality_score,
        run_at
    FROM options_ranks
    WHERE underlying_symbol_id = p_symbol_id
    AND run_at IS NOT NULL;

    GET DIAGNOSTICS v_rows_inserted = ROW_COUNT;

    RETURN v_rows_inserted;
END;
$$;

COMMENT ON FUNCTION capture_options_snapshot IS
    'Captures current options_ranks data into price history for a given symbol, with IV quality fields.';
