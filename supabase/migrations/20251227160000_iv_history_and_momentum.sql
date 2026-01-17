-- Migration: IV History and Momentum Framework
-- Stores IV statistics for proper IV Rank calculation
-- Adds momentum tracking columns to options rankings

-- ============================================================================
-- IV History Table - Daily IV snapshots for 52-week rank calculation
-- ============================================================================

CREATE TABLE IF NOT EXISTS iv_history (
    id BIGSERIAL PRIMARY KEY,
    symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    ts DATE NOT NULL,
    -- ATM IV (most representative)
    atm_iv DOUBLE PRECISION NOT NULL,
    -- IV spread across chain
    iv_min DOUBLE PRECISION,
    iv_max DOUBLE PRECISION,
    iv_median DOUBLE PRECISION,
    -- Put/Call IV skew
    put_iv_atm DOUBLE PRECISION,
    call_iv_atm DOUBLE PRECISION,
    iv_skew DOUBLE PRECISION,  -- put_iv - call_iv
    -- Volume-weighted IV
    vwiv DOUBLE PRECISION,  -- Volume-weighted implied volatility
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(symbol_id, ts)
);

-- Indexes for efficient IV rank calculation
CREATE INDEX IF NOT EXISTS idx_iv_history_symbol_ts
    ON iv_history(symbol_id, ts DESC);

CREATE INDEX IF NOT EXISTS idx_iv_history_ts
    ON iv_history(ts DESC);

-- RLS
ALTER TABLE iv_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY "IV history readable by authenticated"
    ON iv_history FOR SELECT TO authenticated USING (true);

CREATE POLICY "Service role manages IV history"
    ON iv_history FOR ALL TO service_role USING (true);

-- ============================================================================
-- IV Statistics View - 52-week high/low/rank per symbol
-- ============================================================================

CREATE OR REPLACE VIEW iv_statistics AS
WITH iv_52week AS (
    SELECT
        symbol_id,
        MIN(atm_iv) as iv_52_low,
        MAX(atm_iv) as iv_52_high,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY atm_iv) as iv_52_median,
        COUNT(*) as days_of_data
    FROM iv_history
    WHERE ts >= CURRENT_DATE - INTERVAL '52 weeks'
    GROUP BY symbol_id
),
latest_iv AS (
    SELECT DISTINCT ON (symbol_id)
        symbol_id,
        atm_iv as iv_current,
        ts as last_update
    FROM iv_history
    ORDER BY symbol_id, ts DESC
)
SELECT
    s.id as symbol_id,
    s.ticker as symbol,
    l.iv_current,
    w.iv_52_low,
    w.iv_52_high,
    w.iv_52_median,
    w.days_of_data,
    -- IV Rank: (current - low) / (high - low) * 100
    CASE
        WHEN w.iv_52_high = w.iv_52_low THEN 50.0
        ELSE ((l.iv_current - w.iv_52_low) / (w.iv_52_high - w.iv_52_low)) * 100
    END as iv_rank,
    l.last_update
FROM symbols s
LEFT JOIN latest_iv l ON l.symbol_id = s.id
LEFT JOIN iv_52week w ON w.symbol_id = s.id;

GRANT SELECT ON iv_statistics TO authenticated;

-- ============================================================================
-- Function: Calculate IV Rank for a symbol
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_iv_rank(p_symbol_id UUID)
RETURNS TABLE (
    iv_current DOUBLE PRECISION,
    iv_52_low DOUBLE PRECISION,
    iv_52_high DOUBLE PRECISION,
    iv_rank DOUBLE PRECISION
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        iv_current,
        iv_52_low,
        iv_52_high,
        iv_rank
    FROM iv_statistics
    WHERE symbol_id = p_symbol_id;
$$;

-- ============================================================================
-- Function: Calculate IV Percentile (% of days below current)
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_iv_percentile(
    p_symbol_id UUID,
    p_current_iv DOUBLE PRECISION DEFAULT NULL
)
RETURNS DOUBLE PRECISION
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_current_iv DOUBLE PRECISION;
    v_below_count INTEGER;
    v_total_count INTEGER;
BEGIN
    -- Get current IV if not provided
    IF p_current_iv IS NULL THEN
        SELECT atm_iv INTO v_current_iv
        FROM iv_history
        WHERE symbol_id = p_symbol_id
        ORDER BY ts DESC
        LIMIT 1;
    ELSE
        v_current_iv := p_current_iv;
    END IF;

    IF v_current_iv IS NULL THEN
        RETURN 50.0;  -- Default when no data
    END IF;

    -- Count days with IV below current
    SELECT
        COUNT(*) FILTER (WHERE atm_iv < v_current_iv),
        COUNT(*)
    INTO v_below_count, v_total_count
    FROM iv_history
    WHERE symbol_id = p_symbol_id
      AND ts >= CURRENT_DATE - INTERVAL '52 weeks';

    IF v_total_count = 0 THEN
        RETURN 50.0;
    END IF;

    RETURN (v_below_count::DOUBLE PRECISION / v_total_count) * 100;
END;
$$;

-- ============================================================================
-- Enhanced Options Ranks Table - Add momentum framework columns
-- ============================================================================

-- Add new columns to options_ranks if they don't exist
DO $$
BEGIN
    -- Momentum framework columns
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'options_ranks' AND column_name = 'momentum_score') THEN
        ALTER TABLE options_ranks ADD COLUMN momentum_score DOUBLE PRECISION;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'options_ranks' AND column_name = 'value_score') THEN
        ALTER TABLE options_ranks ADD COLUMN value_score DOUBLE PRECISION;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'options_ranks' AND column_name = 'greeks_score') THEN
        ALTER TABLE options_ranks ADD COLUMN greeks_score DOUBLE PRECISION;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'options_ranks' AND column_name = 'composite_rank') THEN
        ALTER TABLE options_ranks ADD COLUMN composite_rank DOUBLE PRECISION;
    END IF;

    -- IV Rank column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'options_ranks' AND column_name = 'iv_rank') THEN
        ALTER TABLE options_ranks ADD COLUMN iv_rank DOUBLE PRECISION;
    END IF;

    -- Spread percentage
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'options_ranks' AND column_name = 'spread_pct') THEN
        ALTER TABLE options_ranks ADD COLUMN spread_pct DOUBLE PRECISION;
    END IF;

    -- Volume/OI ratio
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'options_ranks' AND column_name = 'vol_oi_ratio') THEN
        ALTER TABLE options_ranks ADD COLUMN vol_oi_ratio DOUBLE PRECISION;
    END IF;

    -- Signal flags
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'options_ranks' AND column_name = 'signal_discount') THEN
        ALTER TABLE options_ranks ADD COLUMN signal_discount BOOLEAN DEFAULT FALSE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'options_ranks' AND column_name = 'signal_runner') THEN
        ALTER TABLE options_ranks ADD COLUMN signal_runner BOOLEAN DEFAULT FALSE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'options_ranks' AND column_name = 'signal_greeks') THEN
        ALTER TABLE options_ranks ADD COLUMN signal_greeks BOOLEAN DEFAULT FALSE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'options_ranks' AND column_name = 'signal_buy') THEN
        ALTER TABLE options_ranks ADD COLUMN signal_buy BOOLEAN DEFAULT FALSE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'options_ranks' AND column_name = 'signals') THEN
        ALTER TABLE options_ranks ADD COLUMN signals TEXT;
    END IF;
END;
$$;

-- ============================================================================
-- Function: Capture daily IV snapshot from options chain
-- ============================================================================

CREATE OR REPLACE FUNCTION capture_iv_snapshot(p_symbol_id UUID)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_atm_iv DOUBLE PRECISION;
    v_iv_min DOUBLE PRECISION;
    v_iv_max DOUBLE PRECISION;
    v_iv_median DOUBLE PRECISION;
    v_put_iv DOUBLE PRECISION;
    v_call_iv DOUBLE PRECISION;
BEGIN
    -- Get IV statistics from latest options chain
    SELECT
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY iv),
        MIN(iv),
        MAX(iv),
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY iv)
    INTO v_atm_iv, v_iv_min, v_iv_max, v_iv_median
    FROM options_snapshots
    WHERE underlying_symbol_id = p_symbol_id
      AND snapshot_time > NOW() - INTERVAL '1 day';

    -- Get put/call IV separately
    SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY iv)
    INTO v_put_iv
    FROM options_snapshots
    WHERE underlying_symbol_id = p_symbol_id
      AND option_type = 'put'
      AND snapshot_time > NOW() - INTERVAL '1 day';

    SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY iv)
    INTO v_call_iv
    FROM options_snapshots
    WHERE underlying_symbol_id = p_symbol_id
      AND option_type = 'call'
      AND snapshot_time > NOW() - INTERVAL '1 day';

    -- Insert or update daily IV record
    IF v_atm_iv IS NOT NULL THEN
        INSERT INTO iv_history (
            symbol_id, ts, atm_iv, iv_min, iv_max, iv_median,
            put_iv_atm, call_iv_atm, iv_skew
        )
        VALUES (
            p_symbol_id, CURRENT_DATE, v_atm_iv, v_iv_min, v_iv_max, v_iv_median,
            v_put_iv, v_call_iv, COALESCE(v_put_iv, 0) - COALESCE(v_call_iv, 0)
        )
        ON CONFLICT (symbol_id, ts)
        DO UPDATE SET
            atm_iv = EXCLUDED.atm_iv,
            iv_min = EXCLUDED.iv_min,
            iv_max = EXCLUDED.iv_max,
            iv_median = EXCLUDED.iv_median,
            put_iv_atm = EXCLUDED.put_iv_atm,
            call_iv_atm = EXCLUDED.call_iv_atm,
            iv_skew = EXCLUDED.iv_skew;
    END IF;
END;
$$;

-- ============================================================================
-- View: Top ranked options with signals
-- ============================================================================

CREATE OR REPLACE VIEW top_options_signals AS
SELECT
    s.ticker as symbol,
    r.contract_symbol,
    r.side,
    r.strike,
    r.expiry,
    r.composite_rank,
    r.momentum_score,
    r.value_score,
    r.greeks_score,
    r.iv_rank,
    r.delta,
    r.gamma,
    r.theta,
    r.vega,
    r.bid,
    r.ask,
    r.volume,
    r.open_interest,
    r.spread_pct,
    r.vol_oi_ratio,
    r.signal_discount,
    r.signal_runner,
    r.signal_greeks,
    r.signal_buy,
    r.signals,
    r.run_at
FROM options_ranks r
JOIN symbols s ON s.id = r.underlying_symbol_id
WHERE r.signal_buy = TRUE
  OR r.composite_rank > 65
ORDER BY r.composite_rank DESC;

GRANT SELECT ON top_options_signals TO authenticated;

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE iv_history IS 'Daily IV snapshots for 52-week IV rank calculation';
COMMENT ON VIEW iv_statistics IS '52-week IV statistics per symbol with IV rank';
COMMENT ON FUNCTION calculate_iv_rank IS 'Calculate IV rank for a symbol based on 52-week history';
COMMENT ON FUNCTION calculate_iv_percentile IS 'Calculate IV percentile (% of days below current IV)';
COMMENT ON FUNCTION capture_iv_snapshot IS 'Capture daily IV snapshot from options chain for a symbol';
COMMENT ON VIEW top_options_signals IS 'Top ranked options with buy signals';
