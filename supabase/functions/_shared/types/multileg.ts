// Multi-Leg Options Strategy Types
// These types define the data structures for multi-leg options tracking

// ============================================================================
// ENUM TYPES
// ============================================================================

export type StrategyType =
  | "bull_call_spread"
  | "bear_call_spread"
  | "bull_put_spread"
  | "bear_put_spread"
  | "long_straddle"
  | "short_straddle"
  | "long_strangle"
  | "short_strangle"
  | "iron_condor"
  | "iron_butterfly"
  | "call_ratio_backspread"
  | "put_ratio_backspread"
  | "calendar_spread"
  | "diagonal_spread"
  | "butterfly_spread"
  | "custom";

export type StrategyStatus = "open" | "closed" | "expired" | "rolled";

export type PositionType = "long" | "short";

export type OptionType = "call" | "put";

export type LegRole =
  | "primary_leg"
  | "hedge_leg"
  | "upside_leg"
  | "downside_leg"
  | "income_leg"
  | "protection_leg"
  | "speculation_leg";

export type AlertType =
  | "expiration_soon"
  | "strike_breached"
  | "forecast_flip"
  | "assignment_risk"
  | "profit_target_hit"
  | "stop_loss_hit"
  | "vega_squeeze"
  | "theta_decay_benefit"
  | "volatility_spike"
  | "gamma_risk"
  | "leg_closed"
  | "strategy_auto_adjusted"
  | "custom";

export type AlertSeverity = "info" | "warning" | "critical";

export type JournalAction =
  | "created"
  | "leg_added"
  | "leg_closed"
  | "price_updated"
  | "greeks_updated"
  | "alert_generated"
  | "alert_acknowledged"
  | "strategy_closed"
  | "strategy_rolled"
  | "note_added";

export type MarketCondition =
  | "bullish"
  | "bearish"
  | "neutral"
  | "volatile"
  | "range_bound";

export type ForecastAlignment = "bullish" | "neutral" | "bearish";

// ============================================================================
// CORE INTERFACES
// ============================================================================

export interface MultiLegStrategy {
  id: string;
  userId: string;
  name: string;
  strategyType: StrategyType;
  underlyingSymbolId: string;
  underlyingTicker: string;

  createdAt: string; // ISO timestamp
  openedAt?: string;
  closedAt?: string;
  status: StrategyStatus;

  // Entry cost structure
  totalDebit?: number;
  totalCredit?: number;
  netPremium?: number;
  numContracts: number;

  // Risk profile
  maxRisk?: number;
  maxReward?: number;
  maxRiskPct?: number;

  // Breakevens
  breakevenPoints?: number[];
  profitZones?: ProfitZone[];

  // P&L tracking
  currentValue?: number;
  totalPL?: number;
  totalPLPct?: number;
  realizedPL?: number;

  // ML/Forecast integration
  forecastId?: string;
  forecastAlignment?: ForecastAlignment;
  forecastConfidence?: number;
  alignmentCheckAt?: string;

  // Greeks (portfolio level)
  combinedDelta?: number;
  combinedGamma?: number;
  combinedTheta?: number;
  combinedVega?: number;
  combinedRho?: number;
  greeksUpdatedAt?: string;

  // Days to expiration
  minDTE?: number;
  maxDTE?: number;

  // Metadata
  tags?: Record<string, string>;
  notes?: string;

  lastAlertAt?: string;
  version: number;
  updatedAt: string;

  // Nested data (when joined)
  legs?: OptionsLeg[];
  alerts?: MultiLegAlert[];
}

export interface ProfitZone {
  min: number;
  max: number;
}

export interface OptionsLeg {
  id: string;
  strategyId: string;

  legNumber: number;
  legRole?: LegRole;
  positionType: PositionType;
  optionType: OptionType;

  strike: number;
  expiry: string; // ISO date
  dteAtEntry?: number;
  currentDTE?: number;

  entryTimestamp: string;
  entryPrice: number;
  contracts: number;
  totalEntryCost?: number;

  currentPrice?: number;
  currentValue?: number;
  unrealizedPL?: number;
  unrealizedPLPct?: number;

  isClosed: boolean;
  exitPrice?: number;
  exitTimestamp?: string;
  realizedPL?: number;

  // Greeks at entry
  entryDelta?: number;
  entryGamma?: number;
  entryTheta?: number;
  entryVega?: number;
  entryRho?: number;

  // Greeks current
  currentDelta?: number;
  currentGamma?: number;
  currentTheta?: number;
  currentVega?: number;
  currentRho?: number;
  greeksUpdatedAt?: string;

  // Volatility
  entryImpliedVol?: number;
  currentImpliedVol?: number;
  vegaExposure?: number;

  // Assignment & Exercise
  isAssigned: boolean;
  assignmentTimestamp?: string;
  assignmentPrice?: number;

  isExercised: boolean;
  exerciseTimestamp?: string;
  exercisePrice?: number;

  // Risk flags
  isITM?: boolean;
  isDeepITM?: boolean;
  isBreachingStrike?: boolean;
  isNearExpiration?: boolean;

  notes?: string;
  updatedAt: string;

  // Nested data
  entries?: OptionsLegEntry[];
}

export interface OptionsLegEntry {
  id: string;
  legId: string;
  entryPrice: number;
  contracts: number;
  entryTimestamp: string;
  notes?: string;
}

export interface MultiLegAlert {
  id: string;
  strategyId: string;
  legId?: string;

  alertType: AlertType;
  severity: AlertSeverity;

  title: string;
  reason?: string;
  details?: Record<string, unknown>;
  suggestedAction?: string;

  createdAt: string;
  acknowledgedAt?: string;
  resolvedAt?: string;
  resolutionAction?: string;

  actionRequired: boolean;
}

export interface StrategyTemplate {
  id: string;
  name: string;
  strategyType: StrategyType;

  legConfig: TemplateLegConfig[];

  typicalMaxRisk?: number;
  typicalMaxReward?: number;
  typicalCostPct?: number;

  description?: string;
  bestFor?: string;
  marketCondition?: MarketCondition;

  createdBy?: string;
  createdAt: string;
  updatedAt: string;

  isSystemTemplate: boolean;
  isPublic: boolean;
}

export interface TemplateLegConfig {
  leg: number;
  type: PositionType;
  optionType: OptionType;
  strikeOffset: number;
  dte: number;
  role?: LegRole;
}

export interface StrategyMetrics {
  id: string;
  strategyId: string;
  recordedAt: string;
  recordedTimestamp: string;

  underlyingPrice?: number;
  totalValue?: number;
  totalPL?: number;
  totalPLPct?: number;

  deltaSnapshot?: number;
  gammaSnapshot?: number;
  thetaSnapshot?: number;
  vegaSnapshot?: number;

  minDTE?: number;
  alertCount: number;
  criticalAlertCount: number;
}

export interface JournalEntry {
  id: string;
  strategyId: string;
  action: JournalAction;
  actorUserId?: string;
  actorService?: string;
  legId?: string;
  changes?: Record<string, unknown>;
  notes?: string;
  createdAt: string;
}

export interface UserAlertPreferences {
  id: string;
  userId: string;

  enableExpirationAlerts: boolean;
  expirationAlertDTE: number;

  enableStrikeAlerts: boolean;
  strikeBreachThreshold: number;

  enableAssignmentAlerts: boolean;

  enableProfitTargetAlerts: boolean;
  profitTargetPct: number;

  enableStopLossAlerts: boolean;
  stopLossPct: number;

  enableForecastAlerts: boolean;
  minForecastConfidence: number;

  enableThetaAlerts: boolean;
  minDailyTheta: number;

  enableGammaAlerts: boolean;
  gammaAlertThreshold: number;

  enableVegaAlerts: boolean;

  maxAlertsPerHour: number;
  alertBatchWindowMinutes: number;

  createdAt: string;
  updatedAt: string;
}

// ============================================================================
// API REQUEST/RESPONSE TYPES
// ============================================================================

export interface CreateStrategyRequest {
  name: string;
  strategyType: StrategyType;
  underlyingSymbolId: string;
  underlyingTicker: string;
  legs: CreateLegInput[];
  forecastId?: string;
  forecastAlignment?: ForecastAlignment;
  notes?: string;
  tags?: Record<string, string>;
}

export interface CreateLegInput {
  legNumber: number;
  legRole?: LegRole;
  positionType: PositionType;
  optionType: OptionType;
  strike: number;
  expiry: string;
  entryPrice: number;
  contracts: number;
  // Optional Greeks at entry
  delta?: number;
  gamma?: number;
  theta?: number;
  vega?: number;
  rho?: number;
  impliedVol?: number;
}

export interface UpdateStrategyRequest {
  name?: string;
  notes?: string;
  tags?: Record<string, string>;
  forecastId?: string;
  forecastAlignment?: ForecastAlignment;
}

export interface CloseLegRequest {
  legId: string;
  exitPrice: number;
  notes?: string;
}

export interface CloseStrategyRequest {
  strategyId: string;
  exitPrices: { legId: string; exitPrice: number }[];
  notes?: string;
}

export interface ListStrategiesRequest {
  status?: StrategyStatus;
  underlyingSymbolId?: string;
  strategyType?: StrategyType;
  limit?: number;
  offset?: number;
}

export interface ListStrategiesResponse {
  strategies: MultiLegStrategy[];
  total: number;
  hasMore: boolean;
}

export interface StrategyDetailResponse {
  strategy: MultiLegStrategy;
  legs: OptionsLeg[];
  alerts: MultiLegAlert[];
  metrics?: StrategyMetrics[];
}

// ============================================================================
// P&L CALCULATION TYPES
// ============================================================================

export interface PLSnapshot {
  underlyingPrice: number;
  timestamp: string;

  totalEntryCost: number;
  totalCurrentValue: number;
  totalUnrealizedPL: number;
  totalUnrealizedPLPct: number;

  legSnapshots: LegPLSnapshot[];

  // Aggregated Greeks
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
}

export interface LegPLSnapshot {
  legId: string;
  legNumber: number;

  entryPrice: number;
  currentPrice: number;

  entryCost: number;
  currentValue: number;

  unrealizedPL: number;
  unrealizedPLSigned: number;
  unrealizedPLPct: number;

  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;

  isITM: boolean;
  isDeepITM: boolean;
  isBreachingStrike: boolean;
}

export interface MaxRiskReward {
  maxRisk: number;
  maxReward: number;
  breakevenPoints: number[];
  profitZones?: ProfitZone[];
}

export interface CalculatePLRequest {
  strategyId: string;
  underlyingPrice: number;
  legPrices: { legId: string; price: number; delta?: number; gamma?: number; theta?: number; vega?: number; rho?: number }[];
}

// ============================================================================
// DATABASE ROW TYPES (snake_case for direct DB mapping)
// ============================================================================

export interface StrategyRow {
  id: string;
  user_id: string;
  name: string;
  strategy_type: StrategyType;
  underlying_symbol_id: string;
  underlying_ticker: string;
  created_at: string;
  opened_at: string | null;
  closed_at: string | null;
  status: StrategyStatus;
  total_debit: number | null;
  total_credit: number | null;
  net_premium: number | null;
  num_contracts: number;
  max_risk: number | null;
  max_reward: number | null;
  max_risk_pct: number | null;
  breakeven_points: number[] | null;
  profit_zones: ProfitZone[] | null;
  current_value: number | null;
  total_pl: number | null;
  total_pl_pct: number | null;
  realized_pl: number | null;
  forecast_id: string | null;
  forecast_alignment: ForecastAlignment | null;
  forecast_confidence: number | null;
  alignment_check_at: string | null;
  combined_delta: number | null;
  combined_gamma: number | null;
  combined_theta: number | null;
  combined_vega: number | null;
  combined_rho: number | null;
  greeks_updated_at: string | null;
  min_dte: number | null;
  max_dte: number | null;
  tags: Record<string, string> | null;
  notes: string | null;
  last_alert_at: string | null;
  version: number;
  updated_at: string;
}

export interface LegRow {
  id: string;
  strategy_id: string;
  leg_number: number;
  leg_role: LegRole | null;
  position_type: PositionType;
  option_type: OptionType;
  strike: number;
  expiry: string;
  dte_at_entry: number | null;
  current_dte: number | null;
  entry_timestamp: string;
  entry_price: number;
  contracts: number;
  total_entry_cost: number | null;
  current_price: number | null;
  current_value: number | null;
  unrealized_pl: number | null;
  unrealized_pl_pct: number | null;
  is_closed: boolean;
  exit_price: number | null;
  exit_timestamp: string | null;
  realized_pl: number | null;
  entry_delta: number | null;
  entry_gamma: number | null;
  entry_theta: number | null;
  entry_vega: number | null;
  entry_rho: number | null;
  current_delta: number | null;
  current_gamma: number | null;
  current_theta: number | null;
  current_vega: number | null;
  current_rho: number | null;
  greeks_updated_at: string | null;
  entry_implied_vol: number | null;
  current_implied_vol: number | null;
  vega_exposure: number | null;
  is_assigned: boolean;
  assignment_timestamp: string | null;
  assignment_price: number | null;
  is_exercised: boolean;
  exercise_timestamp: string | null;
  exercise_price: number | null;
  is_itm: boolean | null;
  is_deep_itm: boolean | null;
  is_breaching_strike: boolean | null;
  is_near_expiration: boolean | null;
  notes: string | null;
  updated_at: string;
}

export interface AlertRow {
  id: string;
  strategy_id: string;
  leg_id: string | null;
  alert_type: AlertType;
  severity: AlertSeverity;
  title: string;
  reason: string | null;
  details: Record<string, unknown> | null;
  suggested_action: string | null;
  created_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
  resolution_action: string | null;
  action_required: boolean;
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Convert database row (snake_case) to API response (camelCase)
 */
export function strategyRowToModel(row: StrategyRow): MultiLegStrategy {
  return {
    id: row.id,
    userId: row.user_id,
    name: row.name,
    strategyType: row.strategy_type,
    underlyingSymbolId: row.underlying_symbol_id,
    underlyingTicker: row.underlying_ticker,
    createdAt: row.created_at,
    openedAt: row.opened_at ?? undefined,
    closedAt: row.closed_at ?? undefined,
    status: row.status,
    totalDebit: row.total_debit ?? undefined,
    totalCredit: row.total_credit ?? undefined,
    netPremium: row.net_premium ?? undefined,
    numContracts: row.num_contracts,
    maxRisk: row.max_risk ?? undefined,
    maxReward: row.max_reward ?? undefined,
    maxRiskPct: row.max_risk_pct ?? undefined,
    breakevenPoints: row.breakeven_points ?? undefined,
    profitZones: row.profit_zones ?? undefined,
    currentValue: row.current_value ?? undefined,
    totalPL: row.total_pl ?? undefined,
    totalPLPct: row.total_pl_pct ?? undefined,
    realizedPL: row.realized_pl ?? undefined,
    forecastId: row.forecast_id ?? undefined,
    forecastAlignment: row.forecast_alignment ?? undefined,
    forecastConfidence: row.forecast_confidence ?? undefined,
    alignmentCheckAt: row.alignment_check_at ?? undefined,
    combinedDelta: row.combined_delta ?? undefined,
    combinedGamma: row.combined_gamma ?? undefined,
    combinedTheta: row.combined_theta ?? undefined,
    combinedVega: row.combined_vega ?? undefined,
    combinedRho: row.combined_rho ?? undefined,
    greeksUpdatedAt: row.greeks_updated_at ?? undefined,
    minDTE: row.min_dte ?? undefined,
    maxDTE: row.max_dte ?? undefined,
    tags: row.tags ?? undefined,
    notes: row.notes ?? undefined,
    lastAlertAt: row.last_alert_at ?? undefined,
    version: row.version,
    updatedAt: row.updated_at,
  };
}

export function legRowToModel(row: LegRow): OptionsLeg {
  return {
    id: row.id,
    strategyId: row.strategy_id,
    legNumber: row.leg_number,
    legRole: row.leg_role ?? undefined,
    positionType: row.position_type,
    optionType: row.option_type,
    strike: row.strike,
    expiry: row.expiry,
    dteAtEntry: row.dte_at_entry ?? undefined,
    currentDTE: row.current_dte ?? undefined,
    entryTimestamp: row.entry_timestamp,
    entryPrice: row.entry_price,
    contracts: row.contracts,
    totalEntryCost: row.total_entry_cost ?? undefined,
    currentPrice: row.current_price ?? undefined,
    currentValue: row.current_value ?? undefined,
    unrealizedPL: row.unrealized_pl ?? undefined,
    unrealizedPLPct: row.unrealized_pl_pct ?? undefined,
    isClosed: row.is_closed,
    exitPrice: row.exit_price ?? undefined,
    exitTimestamp: row.exit_timestamp ?? undefined,
    realizedPL: row.realized_pl ?? undefined,
    entryDelta: row.entry_delta ?? undefined,
    entryGamma: row.entry_gamma ?? undefined,
    entryTheta: row.entry_theta ?? undefined,
    entryVega: row.entry_vega ?? undefined,
    entryRho: row.entry_rho ?? undefined,
    currentDelta: row.current_delta ?? undefined,
    currentGamma: row.current_gamma ?? undefined,
    currentTheta: row.current_theta ?? undefined,
    currentVega: row.current_vega ?? undefined,
    currentRho: row.current_rho ?? undefined,
    greeksUpdatedAt: row.greeks_updated_at ?? undefined,
    entryImpliedVol: row.entry_implied_vol ?? undefined,
    currentImpliedVol: row.current_implied_vol ?? undefined,
    vegaExposure: row.vega_exposure ?? undefined,
    isAssigned: row.is_assigned,
    assignmentTimestamp: row.assignment_timestamp ?? undefined,
    assignmentPrice: row.assignment_price ?? undefined,
    isExercised: row.is_exercised,
    exerciseTimestamp: row.exercise_timestamp ?? undefined,
    exercisePrice: row.exercise_price ?? undefined,
    isITM: row.is_itm ?? undefined,
    isDeepITM: row.is_deep_itm ?? undefined,
    isBreachingStrike: row.is_breaching_strike ?? undefined,
    isNearExpiration: row.is_near_expiration ?? undefined,
    notes: row.notes ?? undefined,
    updatedAt: row.updated_at,
  };
}

export function alertRowToModel(row: AlertRow): MultiLegAlert {
  return {
    id: row.id,
    strategyId: row.strategy_id,
    legId: row.leg_id ?? undefined,
    alertType: row.alert_type,
    severity: row.severity,
    title: row.title,
    reason: row.reason ?? undefined,
    details: row.details ?? undefined,
    suggestedAction: row.suggested_action ?? undefined,
    createdAt: row.created_at,
    acknowledgedAt: row.acknowledged_at ?? undefined,
    resolvedAt: row.resolved_at ?? undefined,
    resolutionAction: row.resolution_action ?? undefined,
    actionRequired: row.action_required,
  };
}

/**
 * Get the expected number of legs for a strategy type
 */
export function getExpectedLegCount(strategyType: StrategyType): number | null {
  switch (strategyType) {
    case "bull_call_spread":
    case "bear_call_spread":
    case "bull_put_spread":
    case "bear_put_spread":
    case "long_straddle":
    case "short_straddle":
    case "long_strangle":
    case "short_strangle":
    case "calendar_spread":
    case "diagonal_spread":
      return 2;
    case "call_ratio_backspread":
    case "put_ratio_backspread":
    case "butterfly_spread":
      return 3;
    case "iron_condor":
    case "iron_butterfly":
      return 4;
    case "custom":
      return null; // Variable
  }
}

/**
 * Get human-readable name for strategy type
 */
export function getStrategyDisplayName(strategyType: StrategyType): string {
  const names: Record<StrategyType, string> = {
    bull_call_spread: "Bull Call Spread",
    bear_call_spread: "Bear Call Spread",
    bull_put_spread: "Bull Put Spread",
    bear_put_spread: "Bear Put Spread",
    long_straddle: "Long Straddle",
    short_straddle: "Short Straddle",
    long_strangle: "Long Strangle",
    short_strangle: "Short Strangle",
    iron_condor: "Iron Condor",
    iron_butterfly: "Iron Butterfly",
    call_ratio_backspread: "Call Ratio Backspread",
    put_ratio_backspread: "Put Ratio Backspread",
    calendar_spread: "Calendar Spread",
    diagonal_spread: "Diagonal Spread",
    butterfly_spread: "Butterfly Spread",
    custom: "Custom Strategy",
  };
  return names[strategyType];
}
