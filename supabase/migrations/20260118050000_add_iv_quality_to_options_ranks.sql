-- Migration: Add IV curve quality fields to options_ranks

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'options_ranks'
          AND column_name = 'iv_curve_ok'
    ) THEN
        ALTER TABLE options_ranks
        ADD COLUMN iv_curve_ok BOOLEAN DEFAULT TRUE;

        COMMENT ON COLUMN options_ranks.iv_curve_ok IS
            'True when the IV curve is smooth across strikes (no large jumps).';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'options_ranks'
          AND column_name = 'iv_data_quality_score'
    ) THEN
        ALTER TABLE options_ranks
        ADD COLUMN iv_data_quality_score DOUBLE PRECISION DEFAULT 1.0;

        COMMENT ON COLUMN options_ranks.iv_data_quality_score IS
            'Composite IV data quality score (freshness, coverage, curve smoothness).';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_options_ranks_iv_quality
    ON options_ranks(iv_curve_ok, iv_data_quality_score)
    WHERE iv_curve_ok IS FALSE OR iv_data_quality_score < 0.8;
