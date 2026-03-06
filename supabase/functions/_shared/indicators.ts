// supabase/functions/_shared/indicators.ts
// Standalone indicator math used by the /chart Edge Function for partial-candle
// indicator recomputation. Functions are pure and stateless.
//
// Adapted from strategy-backtest-worker/indicators.ts (same algorithm,
// direct-value API instead of the BarData/family pattern).

// ─── Types ────────────────────────────────────────────────────────────────────

export interface BarInput {
  closes: number[];
  highs: number[];
  lows: number[];
  volumes: number[];
  opens: number[];
}

// ─── SMA ─────────────────────────────────────────────────────────────────────

export function computeSMA(data: number[], period: number): (number | null)[] {
  const result: (number | null)[] = [];
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push(null);
      continue;
    }
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += data[j];
    result.push(sum / period);
  }
  return result;
}

// ─── EMA ─────────────────────────────────────────────────────────────────────

export function computeEMA(data: number[], period: number): (number | null)[] {
  const result: (number | null)[] = [];
  const k = 2 / (period + 1);
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push(null);
      continue;
    }
    if (i === period - 1) {
      let sum = 0;
      for (let j = 0; j < period; j++) sum += data[j];
      result.push(sum / period);
      continue;
    }
    const prev = result[i - 1] ?? data[i];
    result.push((data[i] - prev) * k + prev);
  }
  return result;
}

/** Returns the last non-null EMA value, or null if fewer than `period` bars. */
export function lastEMA(data: number[], period: number): number | null {
  const arr = computeEMA(data, period);
  for (let i = arr.length - 1; i >= 0; i--) {
    if (arr[i] !== null) return arr[i]!;
  }
  return null;
}

// ─── RSI ─────────────────────────────────────────────────────────────────────

/**
 * Wilder-smoothed RSI(14). Returns the latest RSI value, or null if fewer
 * than `period + 1` bars are available.
 */
export function computeRSI(
  closes: number[],
  period = 14,
): number | null {
  const n = closes.length;
  if (n < period + 1) return null;

  let prevAvgGain = 0;
  let prevAvgLoss = 0;
  let latestRsi: number | null = null;

  for (let i = 1; i < n; i++) {
    const diff = closes[i] - closes[i - 1];
    const gain = diff > 0 ? diff : 0;
    const loss = diff < 0 ? -diff : 0;

    if (i <= period) {
      prevAvgGain += gain;
      prevAvgLoss += loss;
      if (i === period) {
        prevAvgGain /= period;
        prevAvgLoss /= period;
        const rs = prevAvgLoss === 0 ? 100 : prevAvgGain / prevAvgLoss;
        latestRsi = 100 - 100 / (1 + rs);
      }
    } else {
      prevAvgGain = (prevAvgGain * (period - 1) + gain) / period;
      prevAvgLoss = (prevAvgLoss * (period - 1) + loss) / period;
      const rs = prevAvgLoss === 0 ? 100 : prevAvgGain / prevAvgLoss;
      latestRsi = 100 - 100 / (1 + rs);
    }
  }

  return latestRsi;
}

// ─── MACD ────────────────────────────────────────────────────────────────────

export interface MACDResult {
  macd: number | null;
  signal: number | null;
  histogram: number | null;
}

/**
 * MACD(12, 26, 9). Returns the latest MACD line, signal line, and histogram,
 * or nulls if there is insufficient data.
 */
export function computeMACD(
  closes: number[],
  fast = 12,
  slow = 26,
  signal = 9,
): MACDResult {
  const emaFast = computeEMA(closes, fast);
  const emaSlow = computeEMA(closes, slow);
  const n = closes.length;

  const macdLine: (number | null)[] = [];
  for (let i = 0; i < n; i++) {
    macdLine.push(
      emaFast[i] !== null && emaSlow[i] !== null
        ? emaFast[i]! - emaSlow[i]!
        : null,
    );
  }

  // Compute signal EMA over the macd line values
  let sigCount = 0;
  let sigSum = 0;
  let sigEma: number | null = null;
  let latestSignal: number | null = null;
  let latestHistogram: number | null = null;
  let latestMacd: number | null = null;

  for (let i = 0; i < n; i++) {
    if (macdLine[i] === null) continue;
    sigCount++;
    sigSum += macdLine[i]!;
    if (sigCount < signal) continue;
    if (sigCount === signal) {
      sigEma = sigSum / signal;
    } else {
      sigEma = (macdLine[i]! - sigEma!) * (2 / (signal + 1)) + sigEma!;
    }
    latestMacd = macdLine[i];
    latestSignal = sigEma;
    latestHistogram = macdLine[i]! - sigEma!;
  }

  return { macd: latestMacd, signal: latestSignal, histogram: latestHistogram };
}

// ─── ATR ─────────────────────────────────────────────────────────────────────

/**
 * Wilder-smoothed ATR(14). Returns the latest ATR value, or null if
 * insufficient bars.
 */
export function computeATR(
  highs: number[],
  lows: number[],
  closes: number[],
  period = 14,
): number | null {
  const n = closes.length;
  if (n < period) return null;

  // True ranges
  const tr: number[] = [];
  for (let i = 0; i < n; i++) {
    if (i === 0) {
      tr.push(highs[0] - lows[0]);
    } else {
      tr.push(
        Math.max(
          highs[i] - lows[i],
          Math.abs(highs[i] - closes[i - 1]),
          Math.abs(lows[i] - closes[i - 1]),
        ),
      );
    }
  }

  let atr: number | null = null;
  for (let i = 0; i < n; i++) {
    if (i < period - 1) continue;
    if (i === period - 1) {
      let sum = 0;
      for (let j = 0; j < period; j++) sum += tr[j];
      atr = sum / period;
    } else {
      atr = (atr! * (period - 1) + tr[i]) / period;
    }
  }

  return atr;
}

// ─── Bollinger Bands ─────────────────────────────────────────────────────────

export interface BollingerResult {
  upper: number | null;
  middle: number | null;
  lower: number | null;
}

/**
 * Bollinger Bands(20, 2). Returns upper/middle/lower for the latest bar.
 */
export function computeBollinger(
  closes: number[],
  period = 20,
  stdDevMult = 2,
): BollingerResult {
  const n = closes.length;
  if (n < period) return { upper: null, middle: null, lower: null };

  const slice = closes.slice(n - period);
  const mean = slice.reduce((a, b) => a + b, 0) / period;
  const variance = slice.reduce((a, b) => a + (b - mean) ** 2, 0) / period;
  const stdDev = Math.sqrt(variance);

  return {
    upper: mean + stdDevMult * stdDev,
    middle: mean,
    lower: mean - stdDevMult * stdDev,
  };
}

// ─── Convenience: recompute all chart indicators from bar arrays ──────────────

export interface PartialIndicators {
  rsi: number | null;
  macdHistogram: number | null;
  ema9: number | null;
  ema21: number | null;
  atr: number | null;
  bollingerUpper: number | null;
  bollingerLower: number | null;
}

/**
 * Recompute the price-derived chart indicators from the provided bar input.
 * Used by the /chart function when appending a synthetic partial candle.
 */
export function recomputePartialIndicators(bars: BarInput): PartialIndicators {
  const { closes, highs, lows } = bars;
  const macd = computeMACD(closes);
  const bb = computeBollinger(closes);

  return {
    rsi: computeRSI(closes),
    macdHistogram: macd.histogram,
    ema9: lastEMA(closes, 9),
    ema21: lastEMA(closes, 21),
    atr: computeATR(highs, lows, closes),
    bollingerUpper: bb.upper,
    bollingerLower: bb.lower,
  };
}
