-- PostgreSQL Best Practices: Batch RPC for N+1 fix + multi-leg alerts index
-- Migration: 20260212010000_get_latest_bars_batch_and_indexes.sql
-- Reference: docs/audits/SQL_PERFORMANCE_AUDIT.md, .cursor/rules/supabase-postgres-best-practices.mdc
--
-- 1. get_latest_bars_batch: Single query replaces N+1 loop in data-health edge function
-- 2. idx_multi_leg_alerts_unresolved: Optimizes strategy_id + resolved_at IS NULL pattern

-- RPC: Get latest bar ts per (symbol_id, timeframe) in one query
CREATE OR REPLACE FUNCTION get_latest_bars_batch(
  p_symbol_ids UUID[],
  p_timeframes TEXT[]
)
RETURNS TABLE (
  symbol_id UUID,
  timeframe TEXT,
  latest_ts TIMESTAMPTZ
)
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  WITH ranked_bars AS (
    SELECT
      ohlc_bars_v2.symbol_id,
      ohlc_bars_v2.timeframe,
      ohlc_bars_v2.ts,
      ROW_NUMBER() OVER (
        PARTITION BY ohlc_bars_v2.symbol_id, ohlc_bars_v2.timeframe
        ORDER BY ohlc_bars_v2.ts DESC
      ) AS rn
    FROM ohlc_bars_v2
    WHERE
      ohlc_bars_v2.symbol_id = ANY(p_symbol_ids)
      AND ohlc_bars_v2.timeframe::text = ANY(p_timeframes)
      AND ohlc_bars_v2.is_forecast = false
  )
  SELECT rb.symbol_id, rb.timeframe::text, rb.ts AS latest_ts
  FROM ranked_bars rb
  WHERE rb.rn = 1;
$$;

GRANT EXECUTE ON FUNCTION get_latest_bars_batch(UUID[], TEXT[]) TO authenticated;
GRANT EXECUTE ON FUNCTION get_latest_bars_batch(UUID[], TEXT[]) TO service_role;
GRANT EXECUTE ON FUNCTION get_latest_bars_batch(UUID[], TEXT[]) TO anon;

COMMENT ON FUNCTION get_latest_bars_batch IS 'Batch lookup of latest OHLC bar per symbol/timeframe; replaces N+1 in data-health';

-- Composite index for multi-leg-list: strategy_id + resolved_at IS NULL
CREATE INDEX IF NOT EXISTS idx_multi_leg_alerts_unresolved
ON options_multi_leg_alerts(strategy_id, severity)
WHERE resolved_at IS NULL;

COMMENT ON INDEX idx_multi_leg_alerts_unresolved IS 'Optimizes multi-leg-list query for active alerts per strategy';
