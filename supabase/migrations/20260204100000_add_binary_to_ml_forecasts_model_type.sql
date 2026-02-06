-- Migration: Add 'binary' to model_type CHECK on ml_forecasts
-- Date: 2026-02-04
-- Description: Allows binary up/down forecaster (BinaryForecaster) to write to ml_forecasts
--              with model_type = 'binary' for chart-data-v2 and SwiftUI overlay.

-- Drop existing CHECK on model_type (constraint name is table_column_check in PostgreSQL)
ALTER TABLE ml_forecasts
DROP CONSTRAINT IF EXISTS ml_forecasts_model_type_check;

-- Re-add CHECK including 'binary'
ALTER TABLE ml_forecasts
ADD CONSTRAINT ml_forecasts_model_type_check
CHECK (model_type IN ('xgboost', 'tabpfn', 'transformer', 'baseline', 'arima', 'prophet', 'ensemble', 'binary'));

COMMENT ON COLUMN ml_forecasts.model_type IS
    'ML model that generated this forecast: xgboost, tabpfn, transformer, baseline, binary, etc.';
