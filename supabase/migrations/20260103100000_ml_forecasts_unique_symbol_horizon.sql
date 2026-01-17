-- Migration: Add unique index for ml_forecasts(symbol_id, horizon)
-- Date: 2026-01-03
-- Description: Ensures upsert on_conflict="symbol_id,horizon" works correctly

CREATE UNIQUE INDEX IF NOT EXISTS ux_ml_forecasts_symbol_horizon
ON public.ml_forecasts(symbol_id, horizon);
