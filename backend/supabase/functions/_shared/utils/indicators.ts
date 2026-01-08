// Lightweight indicator layer (compute on-read, not stored)
// Provides EMA, RSI, ATR for technical analysis

import type { Bar } from "../providers/types.ts";

export interface BarWithIndicators extends Bar {
  ema_20?: number;
  rsi_14?: number;
  atr_14?: number;
  supertrend_upper?: number;
  supertrend_lower?: number;
  supertrend_trend?: 1 | -1;
}

/**
 * Exponential Moving Average
 */
function ema(values: number[], period: number): (number | undefined)[] {
  const k = 2 / (period + 1);
  const result: (number | undefined)[] = [];
  let emaValue = 0;
  
  for (let i = 0; i < values.length; i++) {
    if (i === 0) {
      emaValue = values[i];
    } else {
      emaValue = values[i] * k + emaValue * (1 - k);
    }
    result.push(i >= period - 1 ? emaValue : undefined);
  }
  
  return result;
}

/**
 * Relative Strength Index
 */
function rsi(values: number[], period: number): (number | undefined)[] {
  const result: (number | undefined)[] = [undefined];
  let avgGain = 0;
  let avgLoss = 0;
  
  for (let i = 1; i < values.length; i++) {
    const change = values[i] - values[i - 1];
    const gain = change > 0 ? change : 0;
    const loss = change < 0 ? -change : 0;
    
    if (i <= period) {
      avgGain += gain;
      avgLoss += loss;
      if (i === period) {
        avgGain /= period;
        avgLoss /= period;
        const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
        result.push(100 - 100 / (1 + rs));
      } else {
        result.push(undefined);
      }
    } else {
      avgGain = (avgGain * (period - 1) + gain) / period;
      avgLoss = (avgLoss * (period - 1) + loss) / period;
      const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
      result.push(100 - 100 / (1 + rs));
    }
  }
  
  return result;
}

/**
 * Average True Range
 */
function atr(high: number[], low: number[], close: number[], period: number): (number | undefined)[] {
  const tr: number[] = [];
  
  for (let i = 0; i < close.length; i++) {
    if (i === 0) {
      tr.push(high[i] - low[i]);
    } else {
      tr.push(Math.max(
        high[i] - low[i],
        Math.abs(high[i] - close[i - 1]),
        Math.abs(low[i] - close[i - 1])
      ));
    }
  }
  
  const result: (number | undefined)[] = [];
  let atrValue = 0;
  
  for (let i = 0; i < tr.length; i++) {
    if (i < period - 1) {
      result.push(undefined);
    } else if (i === period - 1) {
      atrValue = tr.slice(0, period).reduce((a, b) => a + b, 0) / period;
      result.push(atrValue);
    } else {
      atrValue = (atrValue * (period - 1) + tr[i]) / period;
      result.push(atrValue);
    }
  }
  
  return result;
}

/**
 * SuperTrend indicator (optional, can be enabled later)
 */
function supertrend(
  high: number[],
  low: number[],
  close: number[],
  atrValues: (number | undefined)[],
  period: number = 10,
  multiplier: number = 3
): {
  upper: (number | undefined)[];
  lower: (number | undefined)[];
  trend: (1 | -1 | undefined)[];
} {
  const upper: (number | undefined)[] = [];
  const lower: (number | undefined)[] = [];
  const trend: (1 | -1 | undefined)[] = [];
  
  for (let i = 0; i < close.length; i++) {
    if (atrValues[i] === undefined) {
      upper.push(undefined);
      lower.push(undefined);
      trend.push(undefined);
      continue;
    }
    
    const hl2 = (high[i] + low[i]) / 2;
    const basicUpper = hl2 + multiplier * atrValues[i]!;
    const basicLower = hl2 - multiplier * atrValues[i]!;
    
    if (i === 0 || upper[i - 1] === undefined) {
      upper.push(basicUpper);
      lower.push(basicLower);
      trend.push(1);
    } else {
      const prevUpper = upper[i - 1]!;
      const prevLower = lower[i - 1]!;
      const prevTrend = trend[i - 1]!;
      
      const newUpper = (basicUpper < prevUpper || close[i - 1] > prevUpper) ? basicUpper : prevUpper;
      const newLower = (basicLower > prevLower || close[i - 1] < prevLower) ? basicLower : prevLower;
      
      let newTrend: 1 | -1;
      if (prevTrend === 1) {
        newTrend = close[i] <= newUpper ? 1 : -1;
      } else {
        newTrend = close[i] >= newLower ? -1 : 1;
      }
      
      upper.push(newUpper);
      lower.push(newLower);
      trend.push(newTrend);
    }
  }
  
  return { upper, lower, trend };
}

/**
 * Attach indicators to bars (computed on-read, not stored)
 * Returns bars with indicator columns added
 */
export function attachIndicators(bars: Bar[], includeSupertrend = false): BarWithIndicators[] {
  if (bars.length === 0) return [];
  
  const closes = bars.map(b => b.close);
  const highs = bars.map(b => b.high);
  const lows = bars.map(b => b.low);
  
  const ema20 = ema(closes, 20);
  const rsi14 = rsi(closes, 14);
  const atr14 = atr(highs, lows, closes, 14);
  
  let st: ReturnType<typeof supertrend> | undefined;
  if (includeSupertrend) {
    st = supertrend(highs, lows, closes, atr14, 10, 3);
  }
  
  return bars.map((bar, i) => ({
    ...bar,
    ema_20: ema20[i],
    rsi_14: rsi14[i],
    atr_14: atr14[i],
    ...(st && {
      supertrend_upper: st.upper[i],
      supertrend_lower: st.lower[i],
      supertrend_trend: st.trend[i],
    }),
  }));
}
