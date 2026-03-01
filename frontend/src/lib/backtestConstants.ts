import type { ConditionTypeConfig, Operator, StrategyConfig } from '../types/strategyBacktest';

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Returns true when id is a real UUID (persisted to Supabase), false for local temp ids. */
export function isStrategyIdUuid(id: string): boolean {
  return UUID_REGEX.test(id);
}

/** Intraday-aware time for lightweight-charts: Unix (number) when date has time, else business day string. */
export function toChartTime(raw: string | number): string | number {
  if (typeof raw === 'number') return raw;
  const s = String(raw ?? '').trim();
  if (!s) return '';
  const hasTime = /^\d{4}-\d{2}-\d{2}[T\s]\d/.test(s);
  if (hasTime) return Math.floor(new Date(s).getTime() / 1000);
  const day = s.match(/^(\d{4}-\d{2}-\d{2})/)?.[1];
  return day ?? s;
}

/** Dedupe equity curve by time (keep last per time) so lightweight-charts never sees prev time === time. */
export function dedupeEquityCurve(
  points: { time: string | number; value: number }[]
): { time: string | number; value: number }[] {
  if (!points.length) return [];
  const sorted = [...points].sort((a, b) => {
    const ta = a.time;
    const tb = b.time;
    return ta < tb ? -1 : ta > tb ? 1 : 0;
  });
  const out: { time: string | number; value: number }[] = [];
  let prev: string | number | undefined;
  for (const p of sorted) {
    if (p.time !== prev) {
      out.push({ time: p.time, value: p.value });
      prev = p.time;
    } else {
      out[out.length - 1] = { time: p.time, value: p.value };
    }
  }
  return out;
}

/** Map UI horizon (15m, 1h, 4h, 1D) to API timeframe (m15, h1, h4, d1). */
export function horizonToTimeframe(horizon: string): string {
  const map: Record<string, string> = { '15m': 'm15', '1h': 'h1', '4h': 'h4', '1D': 'd1' };
  return map[horizon] || 'd1';
}

export const createDefaultConfig = (): StrategyConfig => ({
  entryConditions: [{ type: 'rsi', params: { period: 14 }, operator: '<', value: 30 }],
  exitConditions: [{ type: 'rsi', params: { period: 14 }, operator: '>', value: 70 }],
  positionSizing: { type: 'percent_of_equity', value: 2 },
  riskManagement: { stopLoss: { type: 'percent', value: 2 }, takeProfit: { type: 'percent', value: 5 } },
});

/** Library aligned with TechnicalIndicatorsView (Swift) + ML technical_indicators API keys. */
export const conditionTypes: ConditionTypeConfig[] = [
  // —— Momentum ——
  { id: 'rsi', name: 'RSI', params: [{ name: 'period', min: 5, max: 30, default: 14 }], presets: [{ label: 'Oversold', operator: '<', value: 30 }, { label: 'Overbought', operator: '>', value: 70 }, { label: 'Bullish', operator: '>', value: 60 }, { label: 'Bearish', operator: '<', value: 40 }] },
  { id: 'macd', name: 'MACD', params: [{ name: 'fastPeriod', min: 5, max: 20, default: 12 }, { name: 'slowPeriod', min: 15, max: 40, default: 26 }, { name: 'signalPeriod', min: 5, max: 15, default: 9 }], presets: [{ label: 'Bullish', operator: '>', value: 0 }, { label: 'Bearish', operator: '<', value: 0 }] },
  { id: 'macd_signal', name: 'MACD Signal', params: [{ name: 'fastPeriod', min: 5, max: 20, default: 12 }, { name: 'slowPeriod', min: 15, max: 40, default: 26 }, { name: 'signalPeriod', min: 5, max: 15, default: 9 }], presets: [{ label: 'Bullish', operator: '>', value: 0 }, { label: 'Bearish', operator: '<', value: 0 }] },
  { id: 'macd_hist', name: 'MACD Histogram', params: [{ name: 'fastPeriod', min: 5, max: 20, default: 12 }, { name: 'slowPeriod', min: 15, max: 40, default: 26 }, { name: 'signalPeriod', min: 5, max: 15, default: 9 }], presets: [{ label: 'Bullish', operator: '>', value: 0 }, { label: 'Bearish', operator: '<', value: 0 }] },
  { id: 'stochastic', name: 'Stochastic %K', params: [{ name: 'kPeriod', min: 5, max: 21, default: 14 }, { name: 'dPeriod', min: 2, max: 5, default: 3 }], presets: [{ label: 'Oversold', operator: '<', value: 20 }, { label: 'Overbought', operator: '>', value: 80 }, { label: 'Bullish', operator: '>', value: 60 }, { label: 'Bearish', operator: '<', value: 40 }] },
  { id: 'kdj_k', name: 'KDJ K', params: [{ name: 'period', min: 5, max: 21, default: 9 }, { name: 'kSmooth', min: 2, max: 9, default: 5 }, { name: 'dSmooth', min: 2, max: 9, default: 5 }], presets: [{ label: 'Oversold', operator: '<', value: 20 }, { label: 'Overbought', operator: '>', value: 80 }] },
  { id: 'kdj_d', name: 'KDJ D', params: [{ name: 'period', min: 5, max: 21, default: 9 }, { name: 'kSmooth', min: 2, max: 9, default: 5 }, { name: 'dSmooth', min: 2, max: 9, default: 5 }], presets: [{ label: 'Oversold', operator: '<', value: 20 }, { label: 'Overbought', operator: '>', value: 80 }] },
  { id: 'kdj_j', name: 'KDJ J', params: [{ name: 'period', min: 5, max: 21, default: 9 }, { name: 'kSmooth', min: 2, max: 9, default: 5 }, { name: 'dSmooth', min: 2, max: 9, default: 5 }], presets: [{ label: 'Oversold', operator: '<', value: 0 }, { label: 'Overbought', operator: '>', value: 100 }, { label: 'Bullish', operator: '>', value: 20 }, { label: 'Bearish', operator: '<', value: 80 }] },
  { id: 'mfi', name: 'MFI', params: [{ name: 'period', min: 5, max: 30, default: 14 }], presets: [{ label: 'Oversold', operator: '<', value: 20 }, { label: 'Overbought', operator: '>', value: 80 }, { label: 'Bullish', operator: '<', value: 30 }, { label: 'Bearish', operator: '>', value: 70 }] },
  { id: 'williams_r', name: 'Williams %R', params: [{ name: 'period', min: 5, max: 28, default: 14 }], presets: [{ label: 'Oversold', operator: '<', value: -80 }, { label: 'Overbought', operator: '>', value: -20 }, { label: 'Bullish', operator: '<', value: -50 }, { label: 'Bearish', operator: '>', value: -50 }] },
  { id: 'cci', name: 'CCI', params: [{ name: 'period', min: 10, max: 40, default: 20 }], presets: [{ label: 'Strong Bullish', operator: '<', value: -200 }, { label: 'Bullish', operator: '<', value: -100 }, { label: 'Bearish', operator: '>', value: 100 }, { label: 'Strong Bearish', operator: '>', value: 200 }] },
  { id: 'returns_1d', name: 'Returns 1D', params: [], presets: [{ label: 'Bullish', operator: '>', value: 0.01 }, { label: 'Strong Bullish', operator: '>', value: 0.03 }, { label: 'Bearish', operator: '<', value: -0.01 }, { label: 'Strong Bearish', operator: '<', value: -0.03 }] },
  { id: 'returns_5d', name: 'Returns 5D', params: [], presets: [{ label: 'Bullish', operator: '>', value: 0.02 }, { label: 'Strong Bullish', operator: '>', value: 0.05 }, { label: 'Bearish', operator: '<', value: -0.02 }, { label: 'Strong Bearish', operator: '<', value: -0.05 }] },
  { id: 'returns_20d', name: 'Returns 20D', params: [], presets: [{ label: 'Bullish', operator: '>', value: 0.05 }, { label: 'Strong Bullish', operator: '>', value: 0.10 }, { label: 'Bearish', operator: '<', value: -0.05 }, { label: 'Strong Bearish', operator: '<', value: -0.10 }] },
  // —— Trend ——
  { id: 'sma', name: 'SMA', params: [{ name: 'period', min: 5, max: 200, default: 20 }] },
  { id: 'ema', name: 'EMA', params: [{ name: 'period', min: 5, max: 50, default: 12 }] },
  { id: 'sma_cross', name: 'SMA Crossover', params: [{ name: 'fastPeriod', min: 5, max: 30, default: 10 }, { name: 'slowPeriod', min: 20, max: 100, default: 50 }] },
  { id: 'ema_cross', name: 'EMA Crossover', params: [{ name: 'fastPeriod', min: 5, max: 30, default: 12 }, { name: 'slowPeriod', min: 20, max: 100, default: 26 }] },
  { id: 'adx', name: 'ADX', params: [{ name: 'period', min: 7, max: 28, default: 14 }], presets: [{ label: 'Weak trend', operator: '<', value: 20 }, { label: 'Trend', operator: '>', value: 25 }, { label: 'Strong trend', operator: '>', value: 40 }] },
  { id: 'plus_di', name: '+DI', params: [{ name: 'period', min: 7, max: 28, default: 14 }] },
  { id: 'minus_di', name: '-DI', params: [{ name: 'period', min: 7, max: 28, default: 14 }] },
  { id: 'price_above_sma', name: 'Price Above SMA', params: [{ name: 'period', min: 5, max: 50, default: 20 }] },
  { id: 'price_above_ema', name: 'Price Above EMA', params: [{ name: 'period', min: 5, max: 50, default: 12 }] },
  { id: 'price_vs_sma20', name: 'Price vs SMA20', params: [], presets: [{ label: 'Strong Bullish', operator: '>', value: 0.05 }, { label: 'Bullish', operator: '>', value: 0.02 }, { label: 'Bearish', operator: '<', value: -0.02 }, { label: 'Strong Bearish', operator: '<', value: -0.05 }] },
  { id: 'price_vs_sma50', name: 'Price vs SMA50', params: [], presets: [{ label: 'Strong Bullish', operator: '>', value: 0.05 }, { label: 'Bullish', operator: '>', value: 0.02 }, { label: 'Bearish', operator: '<', value: -0.02 }, { label: 'Strong Bearish', operator: '<', value: -0.05 }] },
  // —— Volatility ——
  { id: 'bb', name: 'Bollinger Bands', params: [{ name: 'period', min: 10, max: 30, default: 20 }, { name: 'stdDev', min: 1, max: 3, step: 0.1, default: 2 }] },
  { id: 'bb_upper', name: 'BB Upper', params: [{ name: 'period', min: 10, max: 30, default: 20 }, { name: 'stdDev', min: 1, max: 3, step: 0.1, default: 2 }] },
  { id: 'bb_lower', name: 'BB Lower', params: [{ name: 'period', min: 10, max: 30, default: 20 }, { name: 'stdDev', min: 1, max: 3, step: 0.1, default: 2 }] },
  { id: 'atr', name: 'ATR', params: [{ name: 'period', min: 7, max: 28, default: 14 }] },
  { id: 'volatility_20d', name: 'Volatility 20D', params: [] },
  { id: 'supertrend_factor', name: 'SuperTrend Factor', params: [{ name: 'factor', min: 1, max: 5, step: 0.5, default: 2 }] },
  { id: 'supertrend_trend', name: 'SuperTrend Trend', params: [], presets: [{ label: 'Bullish', operator: '==', value: 1 }, { label: 'Bearish', operator: '==', value: 0 }] },
  { id: 'supertrend_signal', name: 'SuperTrend Signal', params: [], presets: [{ label: 'Buy', operator: '==', value: 1 }, { label: 'Sell', operator: '==', value: -1 }] },
  // —— Price ——
  { id: 'close', name: 'Close / Price', params: [] },
  { id: 'high', name: 'High', params: [] },
  { id: 'low', name: 'Low', params: [] },
  { id: 'open', name: 'Open', params: [] },
  { id: 'price_breakout', name: 'Price Breakout', params: [{ name: 'lookback', min: 5, max: 50, default: 20 }] },
  // —— Volume ——
  { id: 'volume', name: 'Volume', params: [{ name: 'multiplier', min: 0.5, max: 5, step: 0.5, default: 1 }] },
  { id: 'volume_ratio', name: 'Volume Ratio', params: [], presets: [{ label: 'High', operator: '>', value: 1.5 }, { label: 'Very high', operator: '>', value: 2 }, { label: 'Low', operator: '<', value: 0.5 }] },
  { id: 'obv', name: 'OBV', params: [] },
  { id: 'volume_spike', name: 'Volume Spike', params: [{ name: 'multiplier', min: 1, max: 5, step: 0.5, default: 2 }] },
  // —— Other ——
  { id: 'ml_signal', name: 'ML Signal', params: [{ name: 'confidence', min: 0.5, max: 1, step: 0.05, default: 0.7 }] },
];

export const operators: { id: Operator; label: string }[] = [
  { id: '>', label: '>' },
  { id: '<', label: '<' },
  { id: '>=', label: '>=' },
  { id: '<=', label: '<=' },
  { id: '==', label: '==' },
  { id: 'cross_up', label: 'Crosses Above' },
  { id: 'cross_down', label: 'Crosses Below' },
];

export const datePresets = [
  { id: 'lastMonth', label: '1M', days: 30 },
  { id: 'last3Months', label: '3M', days: 90 },
  { id: 'last6Months', label: '6M', days: 180 },
  { id: 'lastYear', label: '1Y', days: 365 },
  { id: 'covidCrash', label: 'COVID', startDate: '2020-02-19', endDate: '2020-03-23' },
  { id: 'gfc', label: 'GFC', startDate: '2007-12-01', endDate: '2009-06-01' },
];
