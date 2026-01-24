-- ============================================================================
-- SwiftBolt ML - Multi-Leg Options Foundation
-- Migration: 20260120100000_multi_leg_foundation.sql
--
-- Creates tables for multi-leg options strategy tracking:
-- 1. options_strategies - Master strategy record
-- 2. options_legs - Individual contracts (2-4 per strategy)
-- 3. options_leg_entries - Cost averaging support
-- 4. options_multi_leg_alerts - Strategy-level alerts
-- 5. options_strategy_templates - Pre-built strategy configs
-- 6. options_strategy_metrics - Daily P&L snapshots
-- 7. multi_leg_journal - Audit trail
-- 8. user_alert_preferences - Per-user alert thresholds
-- ============================================================================

-- ============================================================================
-- ENUM TYPES
-- ============================================================================

-- Strategy type enum
CREATE TYPE strategy_type AS ENUM (
  'bull_call_spread',
  'bear_call_spread',
  'bull_put_spread',
  'bear_put_spread',
  'long_straddle',
  'short_straddle',
  'long_strangle',
  'short_strangle',
  'iron_condor',
  'iron_butterfly',
  'call_ratio_backspread',
  'put_ratio_backspread',
  'calendar_spread',
  'diagonal_spread',
  'butterfly_spread',
  'custom'
);

-- Strategy status enum
CREATE TYPE strategy_status AS ENUM ('open', 'closed', 'expired', 'rolled');

-- Position type enum
CREATE TYPE position_type AS ENUM ('long', 'short');

-- Leg role enum
CREATE TYPE leg_role AS ENUM (
  'primary_leg',
  'hedge_leg',
  'upside_leg',
  'downside_leg',
  'income_leg',
  'protection_leg',
  'speculation_leg'
);

-- Alert type enum
CREATE TYPE multi_leg_alert_type AS ENUM (
  'expiration_soon',
  'strike_breached',
  'forecast_flip',
  'assignment_risk',
  'profit_target_hit',
  'stop_loss_hit',
  'vega_squeeze',
  'theta_decay_benefit',
  'volatility_spike',
  'gamma_risk',
  'leg_closed',
  'strategy_auto_adjusted',
  'custom'
);

-- Alert severity enum
CREATE TYPE alert_severity AS ENUM ('info', 'warning', 'critical');

-- Journal action enum
CREATE TYPE journal_action AS ENUM (
  'created',
  'leg_added',
  'leg_closed',
  'price_updated',
  'greeks_updated',
  'alert_generated',
  'alert_acknowledged',
  'strategy_closed',
  'strategy_rolled',
  'note_added'
);

-- Market condition enum
CREATE TYPE market_condition AS ENUM ('bullish', 'bearish', 'neutral', 'volatile', 'range_bound');

-- ============================================================================
-- 1. OPTIONS_STRATEGIES (Master record for each multi-leg position)
-- ============================================================================

CREATE TABLE options_strategies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,

  -- Basic identifiers
  name TEXT NOT NULL,
  strategy_type strategy_type NOT NULL,

  -- Underlying reference
  underlying_symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
  underlying_ticker TEXT NOT NULL,

  -- Lifecycle
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  opened_at TIMESTAMPTZ,
  closed_at TIMESTAMPTZ,
  status strategy_status NOT NULL DEFAULT 'open',

  -- Entry cost structure
  total_debit NUMERIC(20, 2),
  total_credit NUMERIC(20, 2),
  net_premium NUMERIC(20, 2),
  num_contracts INT DEFAULT 1,

  -- Risk profile
  max_risk NUMERIC(20, 2),
  max_reward NUMERIC(20, 2),
  max_risk_pct NUMERIC(10, 4),

  -- Breakevens
  breakeven_points NUMERIC[],
  profit_zones JSONB,

  -- P&L tracking
  current_value NUMERIC(20, 2),
  total_pl NUMERIC(20, 2),
  total_pl_pct NUMERIC(10, 4),
  realized_pl NUMERIC(20, 2),

  -- ML/Forecast integration
  forecast_id UUID REFERENCES ml_forecasts(id) ON DELETE SET NULL,
  forecast_alignment trend_label,
  forecast_confidence NUMERIC(5, 4),
  alignment_check_at TIMESTAMPTZ,

  -- Greeks (portfolio level)
  combined_delta NUMERIC(15, 6),
  combined_gamma NUMERIC(15, 6),
  combined_theta NUMERIC(15, 6),
  combined_vega NUMERIC(15, 6),
  combined_rho NUMERIC(15, 6),
  greeks_updated_at TIMESTAMPTZ,

  -- Days to expiration
  min_dte INT,
  max_dte INT,

  -- Metadata
  tags JSONB,
  notes TEXT,

  -- Tracking
  last_alert_at TIMESTAMPTZ,
  version INT DEFAULT 1,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT positive_max_risk CHECK (max_risk IS NULL OR max_risk >= 0),
  CONSTRAINT positive_num_contracts CHECK (num_contracts > 0)
);

CREATE INDEX ix_options_strategies_user_status ON options_strategies(user_id, status);
CREATE INDEX ix_options_strategies_user_created ON options_strategies(user_id, created_at DESC);
CREATE INDEX ix_options_strategies_symbol ON options_strategies(underlying_symbol_id);
CREATE INDEX ix_options_strategies_forecast ON options_strategies(forecast_id);
CREATE INDEX ix_options_strategies_status_dte ON options_strategies(status, min_dte);

COMMENT ON TABLE options_strategies IS 'Master record for multi-leg options strategies';
COMMENT ON COLUMN options_strategies.net_premium IS 'total_credit - total_debit (negative = debit strategy)';
COMMENT ON COLUMN options_strategies.breakeven_points IS 'Array of price points where strategy breaks even';

-- ============================================================================
-- 2. OPTIONS_LEGS (Individual contract in strategy)
-- ============================================================================

CREATE TABLE options_legs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  strategy_id UUID NOT NULL REFERENCES options_strategies(id) ON DELETE CASCADE,

  -- Leg structure
  leg_number INT NOT NULL,
  leg_role leg_role,
  position_type position_type NOT NULL,
  option_type option_side NOT NULL,

  -- Contract terms
  strike NUMERIC(20, 2) NOT NULL,
  expiry DATE NOT NULL,
  dte_at_entry INT,
  current_dte INT,

  -- Entry
  entry_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  entry_price NUMERIC(15, 4) NOT NULL,
  contracts INT NOT NULL DEFAULT 1,
  total_entry_cost NUMERIC(20, 2),

  -- Current state
  current_price NUMERIC(15, 4),
  current_value NUMERIC(20, 2),
  unrealized_pl NUMERIC(20, 2),
  unrealized_pl_pct NUMERIC(10, 4),

  -- Exit
  is_closed BOOLEAN DEFAULT FALSE,
  exit_price NUMERIC(15, 4),
  exit_timestamp TIMESTAMPTZ,
  realized_pl NUMERIC(20, 2),

  -- Greeks at entry
  entry_delta NUMERIC(10, 6),
  entry_gamma NUMERIC(10, 6),
  entry_theta NUMERIC(10, 6),
  entry_vega NUMERIC(10, 6),
  entry_rho NUMERIC(10, 6),

  -- Greeks current
  current_delta NUMERIC(10, 6),
  current_gamma NUMERIC(10, 6),
  current_theta NUMERIC(10, 6),
  current_vega NUMERIC(10, 6),
  current_rho NUMERIC(10, 6),
  greeks_updated_at TIMESTAMPTZ,

  -- Volatility
  entry_implied_vol NUMERIC(10, 6),
  current_implied_vol NUMERIC(10, 6),
  vega_exposure NUMERIC(15, 4),

  -- Assignment & Exercise
  is_assigned BOOLEAN DEFAULT FALSE,
  assignment_timestamp TIMESTAMPTZ,
  assignment_price NUMERIC(20, 2),

  is_exercised BOOLEAN DEFAULT FALSE,
  exercise_timestamp TIMESTAMPTZ,
  exercise_price NUMERIC(20, 2),

  -- Risk flags
  is_itm BOOLEAN,
  is_deep_itm BOOLEAN,
  is_breaching_strike BOOLEAN,
  is_near_expiration BOOLEAN,

  notes TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(strategy_id, leg_number),
  CONSTRAINT positive_strike CHECK (strike > 0),
  CONSTRAINT positive_contracts CHECK (contracts > 0),
  CONSTRAINT positive_entry_price CHECK (entry_price > 0)
);

CREATE INDEX ix_options_legs_strategy ON options_legs(strategy_id);
CREATE INDEX ix_options_legs_expiry ON options_legs(expiry);
CREATE INDEX ix_options_legs_itm ON options_legs(strategy_id, is_itm);
CREATE INDEX ix_options_legs_closed ON options_legs(strategy_id, is_closed);

COMMENT ON TABLE options_legs IS 'Individual option contracts within a multi-leg strategy';
COMMENT ON COLUMN options_legs.leg_number IS 'Position in strategy (1, 2, 3, 4)';
COMMENT ON COLUMN options_legs.position_type IS 'long = bought, short = sold';

-- ============================================================================
-- 3. OPTIONS_LEG_ENTRIES (Average cost tracking for multi-entry legs)
-- ============================================================================

CREATE TABLE options_leg_entries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  leg_id UUID NOT NULL REFERENCES options_legs(id) ON DELETE CASCADE,

  entry_price NUMERIC(15, 4) NOT NULL,
  contracts INT NOT NULL,
  entry_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  notes TEXT,

  CONSTRAINT positive_leg_entry_contracts CHECK (contracts > 0),
  CONSTRAINT positive_leg_entry_price CHECK (entry_price > 0)
);

CREATE INDEX ix_options_leg_entries_leg ON options_leg_entries(leg_id);

COMMENT ON TABLE options_leg_entries IS 'Multiple entries for cost averaging support';

-- ============================================================================
-- 4. OPTIONS_MULTI_LEG_ALERTS (Strategy-level alerts)
-- ============================================================================

CREATE TABLE options_multi_leg_alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  strategy_id UUID NOT NULL REFERENCES options_strategies(id) ON DELETE CASCADE,
  leg_id UUID REFERENCES options_legs(id) ON DELETE SET NULL,

  alert_type multi_leg_alert_type NOT NULL,
  severity alert_severity NOT NULL DEFAULT 'info',

  -- Message and details
  title TEXT NOT NULL,
  reason TEXT,
  details JSONB,

  -- Action suggestion
  suggested_action TEXT,

  -- Lifecycle
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  acknowledged_at TIMESTAMPTZ,
  resolved_at TIMESTAMPTZ,
  resolution_action TEXT,

  action_required BOOLEAN DEFAULT TRUE
);

CREATE INDEX ix_options_multi_leg_alerts_strategy ON options_multi_leg_alerts(strategy_id, created_at DESC);
CREATE INDEX ix_options_multi_leg_alerts_action_required ON options_multi_leg_alerts(strategy_id, action_required);
CREATE INDEX ix_options_multi_leg_alerts_unresolved ON options_multi_leg_alerts(strategy_id, resolved_at)
  WHERE resolved_at IS NULL;

COMMENT ON TABLE options_multi_leg_alerts IS 'Alerts triggered for multi-leg strategies';
COMMENT ON COLUMN options_multi_leg_alerts.leg_id IS 'NULL if strategy-level alert';

-- ============================================================================
-- 5. OPTIONS_STRATEGY_TEMPLATES (Pre-built strategy configs)
-- ============================================================================

CREATE TABLE options_strategy_templates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(100) NOT NULL UNIQUE,
  strategy_type strategy_type NOT NULL,

  -- Template configuration
  leg_config JSONB NOT NULL,

  -- Expected outcomes
  typical_max_risk NUMERIC(20, 2),
  typical_max_reward NUMERIC(20, 2),
  typical_cost_pct NUMERIC(10, 4),

  -- Metadata
  description TEXT,
  best_for TEXT,
  market_condition market_condition,

  created_by UUID,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),

  is_system_template BOOLEAN DEFAULT FALSE,
  is_public BOOLEAN DEFAULT FALSE
);

CREATE INDEX ix_strategy_templates_type ON options_strategy_templates(strategy_type);
CREATE INDEX ix_strategy_templates_public ON options_strategy_templates(is_public);

COMMENT ON TABLE options_strategy_templates IS 'Pre-built strategy configurations for quick creation';
COMMENT ON COLUMN options_strategy_templates.leg_config IS 'Array of leg blueprints with strike_offset and dte';

-- ============================================================================
-- 6. OPTIONS_STRATEGY_METRICS (Daily P&L snapshots for analytics)
-- ============================================================================

CREATE TABLE options_strategy_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  strategy_id UUID NOT NULL REFERENCES options_strategies(id) ON DELETE CASCADE,

  recorded_at DATE NOT NULL,
  recorded_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Snapshot data
  underlying_price NUMERIC(20, 2),
  total_value NUMERIC(20, 2),
  total_pl NUMERIC(20, 2),
  total_pl_pct NUMERIC(10, 4),

  -- Greeks at snapshot
  delta_snapshot NUMERIC(15, 6),
  gamma_snapshot NUMERIC(15, 6),
  theta_snapshot NUMERIC(15, 6),
  vega_snapshot NUMERIC(15, 6),

  -- DTE info
  min_dte INT,

  -- Alerts count
  alert_count INT DEFAULT 0,
  critical_alert_count INT DEFAULT 0,

  UNIQUE(strategy_id, recorded_at)
);

CREATE INDEX ix_strategy_metrics_date ON options_strategy_metrics(strategy_id, recorded_at DESC);

COMMENT ON TABLE options_strategy_metrics IS 'Daily P&L snapshots for strategy analytics';

-- ============================================================================
-- 7. MULTI_LEG_JOURNAL (Audit log for strategy changes)
-- ============================================================================

CREATE TABLE multi_leg_journal (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  strategy_id UUID NOT NULL REFERENCES options_strategies(id) ON DELETE CASCADE,

  action journal_action NOT NULL,

  actor_user_id UUID,
  actor_service VARCHAR(50),

  leg_id UUID REFERENCES options_legs(id) ON DELETE SET NULL,

  changes JSONB,
  notes TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_multi_leg_journal_strategy ON multi_leg_journal(strategy_id, created_at DESC);
CREATE INDEX ix_multi_leg_journal_action ON multi_leg_journal(action);

COMMENT ON TABLE multi_leg_journal IS 'Audit trail for all strategy changes';
COMMENT ON COLUMN multi_leg_journal.actor_service IS 'Service name if system action (e.g., price_updater, alert_evaluator)';

-- ============================================================================
-- 8. USER_ALERT_PREFERENCES (Per-user alert thresholds)
-- ============================================================================

CREATE TABLE user_alert_preferences (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL UNIQUE,

  -- Expiration
  enable_expiration_alerts BOOLEAN DEFAULT TRUE,
  expiration_alert_dte INT DEFAULT 3,

  -- Strike breach
  enable_strike_alerts BOOLEAN DEFAULT TRUE,
  strike_breach_threshold NUMERIC(5, 4) DEFAULT 0.01,

  -- Assignment
  enable_assignment_alerts BOOLEAN DEFAULT TRUE,

  -- P&L targets
  enable_profit_target_alerts BOOLEAN DEFAULT TRUE,
  profit_target_pct NUMERIC(5, 4) DEFAULT 0.50,

  enable_stop_loss_alerts BOOLEAN DEFAULT TRUE,
  stop_loss_pct NUMERIC(5, 4) DEFAULT -0.30,

  -- Forecast
  enable_forecast_alerts BOOLEAN DEFAULT TRUE,
  min_forecast_confidence NUMERIC(5, 4) DEFAULT 0.70,

  -- Greeks
  enable_theta_alerts BOOLEAN DEFAULT TRUE,
  min_daily_theta NUMERIC(10, 2) DEFAULT 50,

  enable_gamma_alerts BOOLEAN DEFAULT TRUE,
  gamma_alert_threshold NUMERIC(5, 4) DEFAULT 0.15,

  enable_vega_alerts BOOLEAN DEFAULT TRUE,

  -- Frequency (to avoid alert spam)
  max_alerts_per_hour INT DEFAULT 10,
  alert_batch_window_minutes INT DEFAULT 15,

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE user_alert_preferences IS 'Per-user configuration for alert thresholds';

-- ============================================================================
-- ROW LEVEL SECURITY
-- ============================================================================

ALTER TABLE options_strategies ENABLE ROW LEVEL SECURITY;
ALTER TABLE options_legs ENABLE ROW LEVEL SECURITY;
ALTER TABLE options_leg_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE options_multi_leg_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE options_strategy_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE multi_leg_journal ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_alert_preferences ENABLE ROW LEVEL SECURITY;

-- Strategies: user owns their strategies
CREATE POLICY options_strategies_user_policy ON options_strategies
  FOR ALL USING (auth.uid() = user_id);

-- Service role has full access
CREATE POLICY options_strategies_service_policy ON options_strategies
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Legs: user owns legs via strategy
CREATE POLICY options_legs_user_policy ON options_legs
  FOR ALL USING (
    strategy_id IN (
      SELECT id FROM options_strategies WHERE user_id = auth.uid()
    )
  );

CREATE POLICY options_legs_service_policy ON options_legs
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Leg entries: user owns via leg -> strategy
CREATE POLICY options_leg_entries_user_policy ON options_leg_entries
  FOR ALL USING (
    leg_id IN (
      SELECT ol.id FROM options_legs ol
      JOIN options_strategies os ON ol.strategy_id = os.id
      WHERE os.user_id = auth.uid()
    )
  );

CREATE POLICY options_leg_entries_service_policy ON options_leg_entries
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Alerts: user owns alerts via strategy
CREATE POLICY options_multi_leg_alerts_user_policy ON options_multi_leg_alerts
  FOR ALL USING (
    strategy_id IN (
      SELECT id FROM options_strategies WHERE user_id = auth.uid()
    )
  );

CREATE POLICY options_multi_leg_alerts_service_policy ON options_multi_leg_alerts
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Metrics: user owns metrics via strategy
CREATE POLICY options_strategy_metrics_user_policy ON options_strategy_metrics
  FOR ALL USING (
    strategy_id IN (
      SELECT id FROM options_strategies WHERE user_id = auth.uid()
    )
  );

CREATE POLICY options_strategy_metrics_service_policy ON options_strategy_metrics
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Journal: user owns journal via strategy
CREATE POLICY multi_leg_journal_user_policy ON multi_leg_journal
  FOR ALL USING (
    strategy_id IN (
      SELECT id FROM options_strategies WHERE user_id = auth.uid()
    )
  );

CREATE POLICY multi_leg_journal_service_policy ON multi_leg_journal
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Alert preferences: user owns their preferences
CREATE POLICY user_alert_preferences_user_policy ON user_alert_preferences
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY user_alert_preferences_service_policy ON user_alert_preferences
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Templates: public templates readable by all, own templates editable
CREATE POLICY options_strategy_templates_read_policy ON options_strategy_templates
  FOR SELECT USING (is_public = TRUE OR is_system_template = TRUE OR created_by = auth.uid());

CREATE POLICY options_strategy_templates_write_policy ON options_strategy_templates
  FOR ALL USING (created_by = auth.uid() OR is_system_template = FALSE);

CREATE POLICY options_strategy_templates_service_policy ON options_strategy_templates
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to update strategy totals when legs change
CREATE OR REPLACE FUNCTION update_strategy_totals()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  UPDATE options_strategies
  SET
    total_debit = (
      SELECT COALESCE(SUM(total_entry_cost), 0)
      FROM options_legs
      WHERE strategy_id = COALESCE(NEW.strategy_id, OLD.strategy_id)
        AND position_type = 'long'
        AND is_closed = FALSE
    ),
    total_credit = (
      SELECT COALESCE(SUM(total_entry_cost), 0)
      FROM options_legs
      WHERE strategy_id = COALESCE(NEW.strategy_id, OLD.strategy_id)
        AND position_type = 'short'
        AND is_closed = FALSE
    ),
    current_value = (
      SELECT COALESCE(SUM(current_value), 0)
      FROM options_legs
      WHERE strategy_id = COALESCE(NEW.strategy_id, OLD.strategy_id)
        AND is_closed = FALSE
    ),
    min_dte = (
      SELECT MIN(current_dte)
      FROM options_legs
      WHERE strategy_id = COALESCE(NEW.strategy_id, OLD.strategy_id)
        AND is_closed = FALSE
    ),
    max_dte = (
      SELECT MAX(current_dte)
      FROM options_legs
      WHERE strategy_id = COALESCE(NEW.strategy_id, OLD.strategy_id)
        AND is_closed = FALSE
    ),
    updated_at = NOW()
  WHERE id = COALESCE(NEW.strategy_id, OLD.strategy_id);

  RETURN COALESCE(NEW, OLD);
END;
$$;

-- Trigger to update strategy totals
CREATE TRIGGER tr_update_strategy_totals
  AFTER INSERT OR UPDATE OR DELETE ON options_legs
  FOR EACH ROW
  EXECUTE FUNCTION update_strategy_totals();

-- Function to log journal entries
CREATE OR REPLACE FUNCTION log_strategy_change()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_action journal_action;
  v_changes JSONB;
BEGIN
  IF TG_OP = 'INSERT' THEN
    v_action := 'created';
    v_changes := to_jsonb(NEW);
  ELSIF TG_OP = 'UPDATE' THEN
    IF OLD.status != NEW.status AND NEW.status = 'closed' THEN
      v_action := 'strategy_closed';
    ELSIF OLD.status != NEW.status AND NEW.status = 'rolled' THEN
      v_action := 'strategy_rolled';
    ELSE
      v_action := 'price_updated';
    END IF;
    v_changes := jsonb_build_object(
      'before', to_jsonb(OLD),
      'after', to_jsonb(NEW)
    );
  END IF;

  INSERT INTO multi_leg_journal (strategy_id, action, actor_user_id, changes)
  VALUES (NEW.id, v_action, NEW.user_id, v_changes);

  RETURN NEW;
END;
$$;

-- Trigger for strategy journal logging
CREATE TRIGGER tr_log_strategy_change
  AFTER INSERT OR UPDATE ON options_strategies
  FOR EACH ROW
  EXECUTE FUNCTION log_strategy_change();

-- ============================================================================
-- SEED SYSTEM TEMPLATES
-- ============================================================================

INSERT INTO options_strategy_templates (
  name, strategy_type, leg_config, description, best_for, market_condition, is_system_template, is_public
) VALUES
(
  'Bull Call Spread (Standard)',
  'bull_call_spread',
  '[{"leg": 1, "type": "long", "option_type": "call", "strike_offset": 0, "dte": 45}, {"leg": 2, "type": "short", "option_type": "call", "strike_offset": 5, "dte": 45}]'::jsonb,
  'Buy ATM call, sell OTM call. Limited risk/reward bullish strategy.',
  'Moderately bullish outlook with defined risk',
  'bullish',
  TRUE,
  TRUE
),
(
  'Bear Put Spread (Standard)',
  'bear_put_spread',
  '[{"leg": 1, "type": "long", "option_type": "put", "strike_offset": 0, "dte": 45}, {"leg": 2, "type": "short", "option_type": "put", "strike_offset": -5, "dte": 45}]'::jsonb,
  'Buy ATM put, sell OTM put. Limited risk/reward bearish strategy.',
  'Moderately bearish outlook with defined risk',
  'bearish',
  TRUE,
  TRUE
),
(
  'Iron Condor (Wide)',
  'iron_condor',
  '[{"leg": 1, "type": "long", "option_type": "put", "strike_offset": -15, "dte": 45}, {"leg": 2, "type": "short", "option_type": "put", "strike_offset": -10, "dte": 45}, {"leg": 3, "type": "short", "option_type": "call", "strike_offset": 10, "dte": 45}, {"leg": 4, "type": "long", "option_type": "call", "strike_offset": 15, "dte": 45}]'::jsonb,
  'Sell OTM put spread and call spread. Profit from low volatility.',
  'Range-bound market, expecting low volatility',
  'range_bound',
  TRUE,
  TRUE
),
(
  'Long Straddle',
  'long_straddle',
  '[{"leg": 1, "type": "long", "option_type": "call", "strike_offset": 0, "dte": 30}, {"leg": 2, "type": "long", "option_type": "put", "strike_offset": 0, "dte": 30}]'::jsonb,
  'Buy ATM call and put. Profit from large price move in either direction.',
  'Expecting high volatility, unsure of direction',
  'volatile',
  TRUE,
  TRUE
),
(
  'Short Strangle',
  'short_strangle',
  '[{"leg": 1, "type": "short", "option_type": "call", "strike_offset": 10, "dte": 45}, {"leg": 2, "type": "short", "option_type": "put", "strike_offset": -10, "dte": 45}]'::jsonb,
  'Sell OTM call and put. Collect premium, profit if price stays in range.',
  'Neutral outlook, expecting low volatility',
  'neutral',
  TRUE,
  TRUE
);

-- ============================================================================
-- GRANTS
-- ============================================================================

-- Grant execute on functions to authenticated users
GRANT EXECUTE ON FUNCTION update_strategy_totals() TO authenticated;
GRANT EXECUTE ON FUNCTION log_strategy_change() TO authenticated;
