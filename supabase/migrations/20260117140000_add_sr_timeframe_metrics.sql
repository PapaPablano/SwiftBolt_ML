-- Migration: add columns for multi-timeframe S/R metrics
BEGIN;

ALTER TABLE sr_levels
    ADD COLUMN IF NOT EXISTS support_methods_agreeing INTEGER,
    ADD COLUMN IF NOT EXISTS resistance_methods_agreeing INTEGER,
    ADD COLUMN IF NOT EXISTS pivot_confidence NUMERIC(6, 2),
    ADD COLUMN IF NOT EXISTS logistic_support_slope NUMERIC(14, 8),
    ADD COLUMN IF NOT EXISTS logistic_resistance_slope NUMERIC(14, 8);

COMMENT ON COLUMN sr_levels.support_methods_agreeing IS 'Number of indicator families confirming the stored support level';
COMMENT ON COLUMN sr_levels.resistance_methods_agreeing IS 'Number of indicator families confirming the stored resistance level';
COMMENT ON COLUMN sr_levels.pivot_confidence IS 'Aggregate agreement score for nearest pivot cluster across methods';
COMMENT ON COLUMN sr_levels.logistic_support_slope IS 'Slope of logistic regression-derived support levels (trend)';
COMMENT ON COLUMN sr_levels.logistic_resistance_slope IS 'Slope of logistic regression-derived resistance levels (trend)';

COMMIT;
