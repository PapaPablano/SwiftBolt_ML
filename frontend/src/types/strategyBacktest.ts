/** Shared types for strategy building and backtesting. */

/** Indicator types aligned with TechnicalIndicatorsView (Swift) + ML technical_indicators API keys. */
export type ConditionType =
  | 'rsi'
  | 'macd'
  | 'macd_signal'
  | 'macd_hist'
  | 'stochastic'
  | 'kdj_k'
  | 'kdj_d'
  | 'kdj_j'
  | 'mfi'
  | 'williams_r'
  | 'cci'
  | 'returns_1d'
  | 'returns_5d'
  | 'returns_20d'
  | 'sma'
  | 'ema'
  | 'sma_cross'
  | 'ema_cross'
  | 'adx'
  | 'plus_di'
  | 'minus_di'
  | 'price_above_sma'
  | 'price_above_ema'
  | 'price_vs_sma20'
  | 'price_vs_sma50'
  | 'bb'
  | 'bb_upper'
  | 'bb_lower'
  | 'atr'
  | 'volatility_20d'
  | 'supertrend_factor'
  | 'supertrend_trend'
  | 'supertrend_signal'
  | 'close'
  | 'high'
  | 'low'
  | 'open'
  | 'volume'
  | 'volume_ratio'
  | 'obv'
  | 'price_breakout'
  | 'volume_spike'
  | 'ml_signal';

export type Operator = '>' | '<' | '>=' | '<=' | '==' | 'cross_up' | 'cross_down';

export interface Condition {
  id: string;
  type: ConditionType;
  params: Record<string, number>;
  operator: Operator;
  value: number;
}

export interface EntryExitCondition {
  type: ConditionType;
  params: Record<string, number>;
  operator: Operator;
  value: number;
}

export interface PositionSizing {
  type: 'fixed' | 'percent_of_equity' | 'kelly';
  value: number;
}

export interface RiskManagement {
  stopLoss: { type: 'percent' | 'fixed'; value: number };
  takeProfit: { type: 'percent' | 'fixed'; value: number };
}

export interface StrategyConfig {
  entryConditions: EntryExitCondition[];
  exitConditions: EntryExitCondition[];
  positionSizing: PositionSizing;
  riskManagement: RiskManagement;
}

export interface Strategy {
  id: string;
  name: string;
  description: string;
  config: StrategyConfig;
  createdAt: string;
  updatedAt: string;
}

export interface Trade {
  id: string;
  entryTime: string;
  exitTime: string;
  entryPrice: number;
  exitPrice: number;
  quantity: number;
  pnl: number;
  pnlPercent: number;
  isWin: boolean;
}

export interface BacktestResult {
  id: string;
  strategyId: string;
  symbol: string;
  period: string;
  totalTrades: number;
  winningTrades: number;
  losingTrades: number;
  winRate: number;
  totalReturn: number;
  /** When present, use this for display so all panels match Total P&L (first entry → last exit notional). */
  tradeBasedReturnPct?: number;
  /** When present, max drawdown from trade log (worst single-trade return % as decimal, e.g. -0.052 for -5.2%). */
  tradeBasedMaxDrawdownPct?: number;
  buyAndHoldReturn: number;
  maxDrawdown: number;
  sharpeRatio: number;
  profitFactor: number;
  avgWin: number;
  avgLoss: number;
  trades: Trade[];
  /** time: business day "yyyy-mm-dd" (daily) or Unix seconds (intraday). Use dedupeEquityCurve before setData. */
  equityCurve: { time: string | number; value: number }[];
}

export interface ConditionParam {
  name: string;
  min: number;
  max: number;
  default: number;
  step?: number;
}

/** Preset operator+value from TechnicalIndicatorsModels (bullish/bearish interpretation). */
export interface ConditionPreset {
  label: string;
  operator: Operator;
  value: number;
}

export interface ConditionTypeConfig {
  id: ConditionType;
  name: string;
  params: ConditionParam[];
  presets?: ConditionPreset[];
}

export interface StrategyBacktestPanelProps {
  symbol: string;
  horizon: string;
  expanded?: boolean;
  /** Use chart date range for backtest so results match the visible chart. */
  startDate?: Date;
  endDate?: Date;
  /** Called when a backtest completes so parent can show the same result in the bottom section. */
  onBacktestComplete?: (result: BacktestResult | null) => void;
  /** When period preset is clicked, call with new start/end so parent can update chart date range. */
  onDateRangeChange?: (start: Date, end: Date) => void;
}
