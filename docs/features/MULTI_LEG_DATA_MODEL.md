# Multi-Leg Options Data Model - Detailed Specification

## Overview

This document provides the complete Postgres schema, TypeScript/Swift types, and validation rules for multi-leg options position tracking in SwiftBolt ML.

## Database Schema

### Complete SQL Setup

```sql
-- ============================================================================
-- MULTI-LEG OPTIONS STRATEGY CORE TABLES
-- ============================================================================

-- 1. OPTIONS_STRATEGIES (Master record for each multi-leg position)
-- ============================================================================

CREATE TABLE options_strategies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  
  -- Basic identifiers
  name TEXT NOT NULL,                          -- "Bull Call Spread - AAPL Jan 2026"
  strategy_type VARCHAR(50) NOT NULL,          -- Enum: bull_call_spread, bear_call_spread, etc.
  
  -- Underlying reference
  underlying_symbol_id UUID NOT NULL REFERENCES symbols(id),
  underlying_ticker TEXT NOT NULL,             -- Cached for performance
  
  -- Lifecycle
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  opened_at TIMESTAMPTZ,                       -- When position was actually opened (for averaging)
  closed_at TIMESTAMPTZ,                       -- When fully exited
  status VARCHAR(20) NOT NULL DEFAULT 'open',  -- open, closed, expired, rolled
  
  -- Entry cost structure
  total_debit NUMERIC,                         -- Sum of all long leg costs
  total_credit NUMERIC,                        -- Sum of all short leg credits
  net_premium NUMERIC,                         -- total_credit - total_debit (negative = debit)
  num_contracts INT DEFAULT 1,                 -- Number of contracts per leg
  
  -- Risk profile
  max_risk NUMERIC,                            -- Maximum theoretical loss
  max_reward NUMERIC,                          -- Maximum theoretical profit
  max_risk_pct NUMERIC,                        -- max_risk / account_equity %
  
  -- Breakevens (array for multi-zone strategies)
  breakeven_points NUMERIC[],                  -- [be1, be2, ...] for complex strategies
  profit_zones JSONB,                          -- [{"min": 95, "max": 105}, ...]
  
  -- P&L tracking
  current_value NUMERIC,                       -- Sum of current leg values
  total_pl NUMERIC,                            -- Current unrealized P&L
  total_pl_pct NUMERIC,                        -- (current_value - net_premium) / ABS(net_premium)
  realized_pl NUMERIC,                         -- Realized from closed legs
  
  -- ML/Forecast integration
  forecast_id UUID REFERENCES ml_forecasts(id),
  forecast_alignment VARCHAR(20),              -- bullish, neutral, bearish, null
  forecast_confidence NUMERIC,                 -- 0-1 confidence score at entry
  alignment_check_at TIMESTAMPTZ,              -- Last time we checked alignment
  
  -- Greeks (portfolio level)
  combined_delta NUMERIC,                      -- Sum of all leg deltas
  combined_gamma NUMERIC,
  combined_theta NUMERIC,
  combined_vega NUMERIC,
  combined_rho NUMERIC,
  greeks_updated_at TIMESTAMPTZ,
  
  -- Days to expiration (minimum across legs)
  min_dte INT,
  max_dte INT,
  
  -- Metadata
  tags JSONB,                                  -- {"sentiment": "bullish", "timeframe": "1w", "created_from": "ranker"}
  notes TEXT,
  
  -- Tracking
  last_alert_at TIMESTAMPTZ,
  version INT DEFAULT 1,                       -- For optimistic locking
  
  CONSTRAINT positive_max_risk CHECK (max_risk >= 0),
  CONSTRAINT valid_status CHECK (status IN ('open', 'closed', 'expired', 'rolled')),
  CONSTRAINT valid_strategy_type CHECK (
    strategy_type IN (
      'bull_call_spread', 'bear_call_spread', 'bull_put_spread', 'bear_put_spread',
      'long_straddle', 'short_straddle', 'long_strangle', 'short_strangle',
      'iron_condor', 'iron_butterfly', 'call_ratio_backspread', 'put_ratio_backspread',
      'calendar_spread', 'diagonal_spread', 'butterfly_spread', 'custom'
    )
  )
);

CREATE INDEX ix_options_strategies_user_status 
  ON options_strategies(user_id, status);
CREATE INDEX ix_options_strategies_user_created 
  ON options_strategies(user_id, created_at DESC);
CREATE INDEX ix_options_strategies_symbol 
  ON options_strategies(underlying_symbol_id);
CREATE INDEX ix_options_strategies_forecast 
  ON options_strategies(forecast_id);

ALTER TABLE options_strategies ENABLE ROW LEVEL SECURITY;
CREATE POLICY options_strategies_user_policy 
  ON options_strategies FOR ALL USING (auth.uid() = user_id);


-- 2. OPTIONS_LEGS (Individual contract in strategy)
-- ============================================================================

CREATE TABLE options_legs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  strategy_id UUID NOT NULL REFERENCES options_strategies(id) ON DELETE CASCADE,
  
  -- Leg structure
  leg_number INT NOT NULL,                     -- 1, 2, 3, 4 (order in strategy)
  leg_role VARCHAR(30),                        -- primary_leg, hedge_leg, upside_leg, downside_leg, etc.
  position_type VARCHAR(10) NOT NULL,          -- long or short
  option_type VARCHAR(4) NOT NULL,             -- call or put
  
  -- Contract terms
  strike NUMERIC NOT NULL,
  expiry DATE NOT NULL,
  dte_at_entry INT,                            -- Days to expiry when opened
  current_dte INT,                             -- Updated daily
  
  -- Entry (multiple entries supported via options_leg_entries)
  entry_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  entry_price NUMERIC NOT NULL,                -- Premium per contract
  contracts INT NOT NULL DEFAULT 1,            -- Number of 100-share contracts
  total_entry_cost NUMERIC,                    -- entry_price * contracts * 100
  
  -- Current state
  current_price NUMERIC,                       -- Latest market price
  current_value NUMERIC,                       -- current_price * contracts * 100
  unrealized_pl NUMERIC,                       -- current_value - total_entry_cost (+ for long, - for short)
  unrealized_pl_pct NUMERIC,                   -- (current_value - total_entry_cost) / ABS(total_entry_cost)
  
  -- Exit (when leg is closed)
  is_closed BOOLEAN DEFAULT FALSE,
  exit_price NUMERIC,                          -- Price at which leg was closed
  exit_timestamp TIMESTAMPTZ,                  -- When leg was closed
  realized_pl NUMERIC,                         -- Actual P&L from closed leg
  
  -- Greeks at entry (snapshot)
  entry_delta NUMERIC,
  entry_gamma NUMERIC,
  entry_theta NUMERIC,
  entry_vega NUMERIC,
  entry_rho NUMERIC,
  
  -- Greeks current (updated with price feeds)
  current_delta NUMERIC,
  current_gamma NUMERIC,
  current_theta NUMERIC,
  current_vega NUMERIC,
  current_rho NUMERIC,
  greeks_updated_at TIMESTAMPTZ,
  
  -- Volatility snapshot
  entry_implied_vol NUMERIC,
  current_implied_vol NUMERIC,
  vega_exposure NUMERIC,                       -- Impact per 1% IV change
  
  -- Assignment & Exercise
  is_assigned BOOLEAN DEFAULT FALSE,
  assignment_timestamp TIMESTAMPTZ,
  assignment_price NUMERIC,
  
  is_exercised BOOLEAN DEFAULT FALSE,
  exercise_timestamp TIMESTAMPTZ,
  exercise_price NUMERIC,
  
  -- Risk flags
  is_itm BOOLEAN,                              -- In-the-money at current price
  is_deep_itm BOOLEAN,                         -- More than 2 strikes ITM
  is_breaching_strike BOOLEAN,                 -- Near strike within 0.5%
  is_near_expiration BOOLEAN,                  -- < 3 days to expiry
  
  notes TEXT,
  
  UNIQUE(strategy_id, leg_number),
  CONSTRAINT valid_position_type CHECK (position_type IN ('long', 'short')),
  CONSTRAINT valid_option_type CHECK (option_type IN ('call', 'put')),
  CONSTRAINT positive_strike CHECK (strike > 0),
  CONSTRAINT positive_contracts CHECK (contracts > 0),
  CONSTRAINT positive_entry_price CHECK (entry_price > 0)
);

CREATE INDEX ix_options_legs_strategy 
  ON options_legs(strategy_id);
CREATE INDEX ix_options_legs_expiry 
  ON options_legs(expiry);
CREATE INDEX ix_options_legs_itm 
  ON options_legs(strategy_id, is_itm);

ALTER TABLE options_legs ENABLE ROW LEVEL SECURITY;
CREATE POLICY options_legs_user_policy 
  ON options_legs FOR ALL
  USING (strategy_id IN (
    SELECT id FROM options_strategies WHERE user_id = auth.uid()
  ));


-- 3. OPTIONS_LEG_ENTRIES (Average cost tracking for multi-entry legs)
-- ============================================================================

CREATE TABLE options_leg_entries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  leg_id UUID NOT NULL REFERENCES options_legs(id) ON DELETE CASCADE,
  
  entry_price NUMERIC NOT NULL,                -- Premium per contract
  contracts INT NOT NULL,                      -- Contracts added at this price
  entry_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  
  notes TEXT,
  
  CONSTRAINT positive_contracts CHECK (contracts > 0),
  CONSTRAINT positive_price CHECK (entry_price > 0)
);

CREATE INDEX ix_options_leg_entries_leg 
  ON options_leg_entries(leg_id);


-- 4. OPTIONS_MULTI_LEG_ALERTS (Strategy-level alerts)
-- ============================================================================

CREATE TABLE options_multi_leg_alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  strategy_id UUID NOT NULL REFERENCES options_strategies(id) ON DELETE CASCADE,
  leg_id UUID REFERENCES options_legs(id) ON DELETE SET NULL,  -- NULL if strategy-level
  
  alert_type VARCHAR(50) NOT NULL,
  -- Types: expiration_soon, strike_breached, forecast_flip, assignment_risk,
  --        profit_target_hit, stop_loss_hit, vega_squeeze, theta_decay_benefit,
  --        volatility_spike, leg_closed, strategy_auto_adjusted
  
  severity VARCHAR(20) NOT NULL DEFAULT 'info',  -- info, warning, critical
  
  -- Message and details
  title TEXT NOT NULL,                         -- "Assignment risk: $105C ITM in 2 days"
  reason TEXT,                                 -- Detailed explanation
  details JSONB,                               -- {"leg_number": 2, "strike": 105, "current_price": 106.50}
  
  -- Action suggestion
  suggested_action TEXT,                       -- "Consider closing leg 1", "Roll to next expiry"
  
  -- Lifecycle
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  acknowledged_at TIMESTAMPTZ,
  resolved_at TIMESTAMPTZ,
  resolution_action TEXT,                      -- "closed", "rolled", "ignored", "profit_taken"
  
  action_required BOOLEAN DEFAULT TRUE,
  
  CONSTRAINT valid_alert_type CHECK (
    alert_type IN (
      'expiration_soon', 'strike_breached', 'forecast_flip', 'assignment_risk',
      'profit_target_hit', 'stop_loss_hit', 'vega_squeeze', 'theta_decay_benefit',
      'volatility_spike', 'leg_closed', 'strategy_auto_adjusted', 'custom'
    )
  ),
  CONSTRAINT valid_severity CHECK (severity IN ('info', 'warning', 'critical'))
);

CREATE INDEX ix_options_multi_leg_alerts_strategy 
  ON options_multi_leg_alerts(strategy_id, created_at DESC);
CREATE INDEX ix_options_multi_leg_alerts_action_required 
  ON options_multi_leg_alerts(strategy_id, action_required);

ALTER TABLE options_multi_leg_alerts ENABLE ROW LEVEL SECURITY;
CREATE POLICY options_multi_leg_alerts_user_policy 
  ON options_multi_leg_alerts FOR ALL
  USING (strategy_id IN (
    SELECT id FROM options_strategies WHERE user_id = auth.uid()
  ));


-- 5. OPTIONS_STRATEGY_TEMPLATES (Pre-built strategy configs)
-- ============================================================================

CREATE TABLE options_strategy_templates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(100) NOT NULL UNIQUE,           -- "Bull Call Spread 1:1"
  strategy_type VARCHAR(50) NOT NULL,
  
  -- Template configuration
  leg_config JSONB NOT NULL,                   -- Array of leg blueprints
  -- [
  --   {"leg": 1, "type": "long", "option_type": "call", "strike_offset": -5, "dte": 45},
  --   {"leg": 2, "type": "short", "option_type": "call", "strike_offset": 0, "dte": 45}
  -- ]
  
  -- Expected outcomes
  typical_max_risk NUMERIC,                    -- For $100 stock, 2 contracts
  typical_max_reward NUMERIC,
  typical_cost_pct NUMERIC,                    -- Cost as % of max width
  
  -- Metadata
  description TEXT,
  best_for TEXT,                               -- "Bullish outlook, limited risk"
  market_condition VARCHAR(30),                -- bullish, bearish, neutral, volatile, range_bound
  
  created_by UUID REFERENCES auth.users(id),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  is_system_template BOOLEAN DEFAULT FALSE,   -- TRUE for pre-built templates
  is_public BOOLEAN DEFAULT FALSE,             -- Shared templates
  
  CONSTRAINT valid_market_condition CHECK (
    market_condition IN ('bullish', 'bearish', 'neutral', 'volatile', 'range_bound')
  )
);

CREATE INDEX ix_strategy_templates_type 
  ON options_strategy_templates(strategy_type);
CREATE INDEX ix_strategy_templates_public 
  ON options_strategy_templates(is_public);


-- 6. OPTIONS_STRATEGY_METRICS (Daily P&L snapshots for analytics)
-- ============================================================================

CREATE TABLE options_strategy_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  strategy_id UUID NOT NULL REFERENCES options_strategies(id) ON DELETE CASCADE,
  
  recorded_at DATE NOT NULL,                   -- Date of snapshot
  recorded_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  
  -- Snapshot data
  underlying_price NUMERIC,
  total_value NUMERIC,
  total_pl NUMERIC,
  total_pl_pct NUMERIC,
  
  -- Greeks at snapshot
  delta_snapshot NUMERIC,
  gamma_snapshot NUMERIC,
  theta_snapshot NUMERIC,
  vega_snapshot NUMERIC,
  
  -- DTE info
  min_dte INT,
  
  -- Alerts count
  alert_count INT DEFAULT 0,
  critical_alert_count INT DEFAULT 0,
  
  UNIQUE(strategy_id, recorded_at)
);

CREATE INDEX ix_strategy_metrics_date 
  ON options_strategy_metrics(strategy_id, recorded_at DESC);


-- 7. MULTI_LEG_JOURNAL (Audit log for strategy changes)
-- ============================================================================

CREATE TABLE multi_leg_journal (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  strategy_id UUID NOT NULL REFERENCES options_strategies(id) ON DELETE CASCADE,
  
  action VARCHAR(50) NOT NULL,                 -- created, leg_added, leg_closed, price_updated, alert_generated, strategy_closed
  
  actor_user_id UUID REFERENCES auth.users(id),  -- User action or system
  actor_service VARCHAR(50),                   -- "price_updater", "alert_evaluator", "ui_action"
  
  leg_id UUID REFERENCES options_legs(id),     -- NULL if strategy-level action
  
  changes JSONB,                               -- {"field": "current_price", "before": 2.50, "after": 2.75}
  notes TEXT,
  
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_multi_leg_journal_strategy 
  ON multi_leg_journal(strategy_id, created_at DESC);
CREATE INDEX ix_multi_leg_journal_action 
  ON multi_leg_journal(action);
```

## TypeScript Types

```typescript
// src/types/multileg.ts

export type StrategyType = 
  | 'bull_call_spread'
  | 'bear_call_spread'
  | 'bull_put_spread'
  | 'bear_put_spread'
  | 'long_straddle'
  | 'short_straddle'
  | 'long_strangle'
  | 'short_strangle'
  | 'iron_condor'
  | 'iron_butterfly'
  | 'call_ratio_backspread'
  | 'put_ratio_backspread'
  | 'calendar_spread'
  | 'diagonal_spread'
  | 'butterfly_spread'
  | 'custom';

export type StrategyStatus = 'open' | 'closed' | 'expired' | 'rolled';
export type PositionType = 'long' | 'short';
export type OptionType = 'call' | 'put';
export type LegRole = 
  | 'primary_leg'
  | 'hedge_leg'
  | 'upside_leg'
  | 'downside_leg'
  | 'income_leg'
  | 'protection_leg'
  | 'speculation_leg';

export interface MultiLegStrategy {
  id: string;
  userId: string;
  name: string;
  strategyType: StrategyType;
  underlyingSymbolId: string;
  underlyingTicker: string;
  
  createdAt: Date;
  openedAt?: Date;
  closedAt?: Date;
  status: StrategyStatus;
  
  totalDebit: number;          // Cost of long legs
  totalCredit: number;         // Income from short legs
  netPremium: number;          // total_credit - total_debit
  numContracts: number;
  
  maxRisk: number;
  maxReward: number;
  maxRiskPct: number;
  
  breakevenPoints: number[];
  profitZones: { min: number; max: number }[];
  
  currentValue: number;
  totalPL: number;
  totalPLPct: number;
  realizedPL: number;
  
  forecastId?: string;
  forecastAlignment?: 'bullish' | 'neutral' | 'bearish';
  forecastConfidence?: number;
  alignmentCheckAt?: Date;
  
  combinedDelta: number;
  combinedGamma: number;
  combinedTheta: number;
  combinedVega: number;
  combinedRho: number;
  greeksUpdatedAt?: Date;
  
  minDTE: number;
  maxDTE: number;
  
  tags?: Record<string, any>;
  notes?: string;
  
  lastAlertAt?: Date;
  version: number;
  
  legs: OptionsLeg[];          // Eager-loaded legs
}

export interface OptionsLeg {
  id: string;
  strategyId: string;
  
  legNumber: number;           // 1, 2, 3, 4
  legRole?: LegRole;
  positionType: PositionType;  // long or short
  optionType: OptionType;      // call or put
  
  strike: number;
  expiry: Date;
  dteAtEntry: number;
  currentDTE: number;
  
  entryTimestamp: Date;
  entryPrice: number;          // Per contract
  contracts: number;
  totalEntryCost: number;      // entry_price * contracts * 100
  
  currentPrice?: number;
  currentValue?: number;
  unrealizedPL?: number;
  unrealizedPLPct?: number;
  
  isClosed: boolean;
  exitPrice?: number;
  exitTimestamp?: Date;
  realizedPL?: number;
  
  // Greeks
  entryDelta?: number;
  entryGamma?: number;
  entryTheta?: number;
  entryVega?: number;
  entryRho?: number;
  
  currentDelta?: number;
  currentGamma?: number;
  currentTheta?: number;
  currentVega?: number;
  currentRho?: number;
  greeksUpdatedAt?: Date;
  
  entryImpliedVol?: number;
  currentImpliedVol?: number;
  vegaExposure?: number;
  
  // Assignment/Exercise
  isAssigned: boolean;
  assignmentTimestamp?: Date;
  assignmentPrice?: number;
  
  isExercised: boolean;
  exerciseTimestamp?: Date;
  exercisePrice?: number;
  
  // Risk flags
  isITM?: boolean;
  isDeepITM?: boolean;
  isBreachingStrike?: boolean;
  isNearExpiration?: boolean;
  
  notes?: string;
  
  entries?: OptionsLegEntry[];  // Multiple entries for averaging
}

export interface OptionsLegEntry {
  id: string;
  legId: string;
  
  entryPrice: number;
  contracts: number;
  entryTimestamp: Date;
  
  notes?: string;
}

export interface MultiLegAlert {
  id: string;
  strategyId: string;
  legId?: string;               // NULL if strategy-level alert
  
  alertType: AlertType;
  severity: 'info' | 'warning' | 'critical';
  
  title: string;
  reason?: string;
  details?: Record<string, any>;
  suggestedAction?: string;
  
  createdAt: Date;
  acknowledgedAt?: Date;
  resolvedAt?: Date;
  resolutionAction?: string;
  
  actionRequired: boolean;
}

export type AlertType = 
  | 'expiration_soon'
  | 'strike_breached'
  | 'forecast_flip'
  | 'assignment_risk'
  | 'profit_target_hit'
  | 'stop_loss_hit'
  | 'vega_squeeze'
  | 'theta_decay_benefit'
  | 'volatility_spike'
  | 'leg_closed'
  | 'strategy_auto_adjusted'
  | 'custom';

export interface StrategyTemplate {
  id: string;
  name: string;
  strategyType: StrategyType;
  
  legConfig: TemplateLegConfig[];
  
  typicalMaxRisk: number;
  typicalMaxReward: number;
  typicalCostPct: number;
  
  description: string;
  bestFor: string;
  marketCondition: 'bullish' | 'bearish' | 'neutral' | 'volatile' | 'range_bound';
  
  createdBy: string;
  createdAt: Date;
  updatedAt: Date;
  
  isSystemTemplate: boolean;
  isPublic: boolean;
}

export interface TemplateLegConfig {
  leg: number;
  type: 'long' | 'short';
  optionType: 'call' | 'put';
  strikeOffset: number;        // Relative to spot (e.g., -5 = 5 points below)
  dte: number;                 // Days to expiration
  role?: LegRole;
}

export interface StrategyMetrics {
  id: string;
  strategyId: string;
  recordedAt: Date;
  recordedTimestamp: Date;
  
  underlyingPrice: number;
  totalValue: number;
  totalPL: number;
  totalPLPct: number;
  
  deltaSnapshot: number;
  gammaSnapshot: number;
  thetaSnapshot: number;
  vegaSnapshot: number;
  
  minDTE: number;
  alertCount: number;
  criticalAlertCount: number;
}
```

## Swift Types

```swift
// SwiftBolt_ML/Shared/Models/MultiLegModels.swift

import Foundation

enum StrategyType: String, Codable, CaseIterable {
    case bullCallSpread = "bull_call_spread"
    case bearCallSpread = "bear_call_spread"
    case bullPutSpread = "bull_put_spread"
    case bearPutSpread = "bear_put_spread"
    case longStraddle = "long_straddle"
    case shortStraddle = "short_straddle"
    case longStrangle = "long_strangle"
    case shortStrangle = "short_strangle"
    case ironCondor = "iron_condor"
    case ironButterfly = "iron_butterfly"
    case callRatioBackspread = "call_ratio_backspread"
    case putRatioBackspread = "put_ratio_backspread"
    case calendarSpread = "calendar_spread"
    case diagonalSpread = "diagonal_spread"
    case butterflySpread = "butterfly_spread"
    case custom = "custom"
    
    var displayName: String {
        switch self {
        case .bullCallSpread: return "Bull Call Spread"
        case .bearCallSpread: return "Bear Call Spread"
        case .bullPutSpread: return "Bull Put Spread"
        case .bearPutSpread: return "Bear Put Spread"
        case .longStraddle: return "Long Straddle"
        case .shortStraddle: return "Short Straddle"
        case .longStrangle: return "Long Strangle"
        case .shortStrangle: return "Short Strangle"
        case .ironCondor: return "Iron Condor"
        case .ironButterfly: return "Iron Butterfly"
        case .callRatioBackspread: return "Call Ratio Backspread"
        case .putRatioBackspread: return "Put Ratio Backspread"
        case .calendarSpread: return "Calendar Spread"
        case .diagonalSpread: return "Diagonal Spread"
        case .butterflySpread: return "Butterfly Spread"
        case .custom: return "Custom Strategy"
        }
    }
    
    var legCount: Int {
        switch self {
        case .bullCallSpread, .bearCallSpread, .bullPutSpread, .bearPutSpread,
             .longStraddle, .shortStraddle, .longStrangle, .shortStrangle,
             .calendarSpread, .diagonalSpread:
            return 2
        case .ironCondor, .ironButterfly, .butterflySpread:
            return 4
        case .callRatioBackspread, .putRatioBackspread:
            return 3
        case .custom:
            return 0  // Variable
        }
    }
}

enum StrategyStatus: String, Codable {
    case open, closed, expired, rolled
}

enum PositionType: String, Codable {
    case long, short
}

enum OptionType: String, Codable {
    case call, put
}

enum LegRole: String, Codable {
    case primaryLeg = "primary_leg"
    case hedgeLeg = "hedge_leg"
    case upsideLeg = "upside_leg"
    case downsideLeg = "downside_leg"
    case incomeLeg = "income_leg"
    case protectionLeg = "protection_leg"
    case speculationLeg = "speculation_leg"
}

struct MultiLegStrategy: Identifiable, Codable {
    let id: UUID
    let userId: UUID
    let name: String
    let strategyType: StrategyType
    let underlyingSymbolId: UUID
    let underlyingTicker: String
    
    let createdAt: Date
    var openedAt: Date?
    var closedAt: Date?
    var status: StrategyStatus
    
    var totalDebit: Decimal
    var totalCredit: Decimal
    var netPremium: Decimal
    var numContracts: Int
    
    var maxRisk: Decimal
    var maxReward: Decimal
    var maxRiskPct: Decimal
    
    var breakevenPoints: [Decimal]
    var profitZones: [ProfitZone]
    
    var currentValue: Decimal
    var totalPL: Decimal
    var totalPLPct: Decimal
    var realizedPL: Decimal
    
    var forecastId: UUID?
    var forecastAlignment: ForecastAlignment?
    var forecastConfidence: Decimal?
    var alignmentCheckAt: Date?
    
    var combinedDelta: Decimal
    var combinedGamma: Decimal
    var combinedTheta: Decimal
    var combinedVega: Decimal
    var combinedRho: Decimal
    var greeksUpdatedAt: Date?
    
    var minDTE: Int
    var maxDTE: Int
    
    var tags: [String: String]?
    var notes: String?
    var lastAlertAt: Date?
    var version: Int
    
    var legs: [OptionsLeg]
    
    // Computed properties
    var isNearExpiration: Bool { minDTE <= 3 }
    var netDebitStrategy: Bool { netPremium < 0 }
    var maxProfit: Decimal { maxReward >= 0 ? maxReward : 0 }
}

struct ProfitZone: Codable {
    let min: Decimal
    let max: Decimal
}

enum ForecastAlignment: String, Codable {
    case bullish, neutral, bearish
}

struct OptionsLeg: Identifiable, Codable {
    let id: UUID
    let strategyId: UUID
    
    let legNumber: Int
    var legRole: LegRole?
    let positionType: PositionType
    let optionType: OptionType
    
    let strike: Decimal
    let expiry: Date
    var dteAtEntry: Int
    var currentDTE: Int
    
    let entryTimestamp: Date
    var entryPrice: Decimal
    var contracts: Int
    var totalEntryCost: Decimal
    
    var currentPrice: Decimal?
    var currentValue: Decimal?
    var unrealizedPL: Decimal?
    var unrealizedPLPct: Decimal?
    
    var isClosed: Bool
    var exitPrice: Decimal?
    var exitTimestamp: Date?
    var realizedPL: Decimal?
    
    // Greeks
    var entryDelta: Decimal?
    var entryGamma: Decimal?
    var entryTheta: Decimal?
    var entryVega: Decimal?
    var entryRho: Decimal?
    
    var currentDelta: Decimal?
    var currentGamma: Decimal?
    var currentTheta: Decimal?
    var currentVega: Decimal?
    var currentRho: Decimal?
    var greeksUpdatedAt: Date?
    
    var entryImpliedVol: Decimal?
    var currentImpliedVol: Decimal?
    var vegaExposure: Decimal?
    
    var isAssigned: Bool
    var assignmentTimestamp: Date?
    var assignmentPrice: Decimal?
    
    var isExercised: Bool
    var exerciseTimestamp: Date?
    var exercisePrice: Decimal?
    
    var isITM: Bool?
    var isDeepITM: Bool?
    var isBreachingStrike: Bool?
    var isNearExpiration: Bool?
    
    var notes: String?
    
    var entries: [OptionsLegEntry]?
    
    // Computed
    var displayStrike: String { strike.formatted(.number.precision(.fractionLength(2))) }
    var displayCurrentPrice: String { currentPrice?.formatted(.number.precision(.fractionLength(2))) ?? "--" }
}

struct OptionsLegEntry: Identifiable, Codable {
    let id: UUID
    let legId: UUID
    
    let entryPrice: Decimal
    let contracts: Int
    let entryTimestamp: Date
    let notes: String?
}
```

## Validation Rules

### Strategy-Level Validation

```python
# backend/services/strategy_validator.py

def validate_strategy_creation( dict) -> List[str]:
    """Validate multi-leg strategy before creation."""
    errors = []
    
    # Check leg count
    expected_leg_count = STRATEGY_LEG_COUNTS.get(data['strategy_type'])
    if expected_leg_count and len(data['legs']) != expected_leg_count:
        errors.append(f"Strategy {data['strategy_type']} requires {expected_leg_count} legs, got {len(data['legs'])}")
    
    # Check strike ordering (spreads)
    if data['strategy_type'] in ['bull_call_spread', 'bear_put_spread']:
        if data['legs'][0]['strike'] >= data['legs'][1]['strike']:
            errors.append("Bull spread: long leg strike must be < short leg strike")
    
    # Check all legs have same underlying
    underlying_ids = set(leg['underlying_symbol_id'] for leg in data['legs'])
    if len(underlying_ids) > 1:
        errors.append("All legs must have the same underlying symbol")
    
    # Check expiration (calendar spreads allowed different expirations)
    if data['strategy_type'] not in ['calendar_spread', 'diagonal_spread']:
        expiries = set(leg['expiry'] for leg in data['legs'])
        if len(expiries) > 1:
            errors.append(f"Strategy {data['strategy_type']} requires same expiry for all legs")
    
    # Validate max_risk and max_reward calculations
    try:
        calculated_risk = calculate_max_risk(data['legs'], data['strategy_type'])
        if calculated_risk != data['max_risk']:
            errors.append(f"Max risk mismatch: expected {calculated_risk}, got {data['max_risk']}")
    except Exception as e:
        errors.append(f"Could not calculate max risk: {str(e)}")
    
    return errors
```

## Next Steps

1. **Execute schema creation** in Supabase
2. **Generate migrations** for typespec/supabase compatibility
3. **Create CRUD services** (create, read, update strategies)
4. **Implement P&L calculations** (see separate docs)
5. **Build alert evaluator** (see alert system docs)

---

## References

- [Multi-Leg Options Overview](./MULTI_LEG_OPTIONS_OVERVIEW.md)
- [Alert System Design](./MULTI_LEG_ALERT_SYSTEM.md)
- [P&L Calculation Engine](./MULTI_LEG_PL_CALCULATOR.md)
