/**
 * Parameterized indicator library for the strategy backtest worker.
 *
 * Each indicator "family" function accepts configurable periods from condition
 * params. A lazy cache (buildIndicatorCache) ensures each (family, params)
 * combination is computed at most once per backtest run.
 */

// ─── Types ────────────────────────────────────────────────────────────────────

export interface BarData {
  closes: number[];
  highs: number[];
  lows: number[];
  volumes: number[];
  opens: number[];
}

/** Arrays of indicator values indexed by bar. null = not yet warm. */
export type IndicatorValues = Record<string, (number | null)[]>;

/** Cache key → computed indicator arrays */
export type IndicatorCache = Map<string, IndicatorValues>;

type IndicatorFn = (
  bars: BarData,
  params: Record<string, unknown>,
) => IndicatorValues;

// ─── Internal helpers ────────────────────────────────────────────────────────

/** Coerce a param to number, falling back to defaultVal. */
function p(
  params: Record<string, unknown>,
  key: string,
  defaultVal: number,
): number {
  const v = params[key];
  const n = Number(v);
  return !isNaN(n) && v !== null && v !== undefined ? n : defaultVal;
}

/**
 * Normalize param keys from frontend camelCase to the snake_case/short names
 * expected by indicator family functions. Handles both Swift and frontend formats.
 */
const PARAM_ALIASES: Record<string, string> = {
  // MACD — frontend sends fastPeriod/slowPeriod/signalPeriod
  fastPeriod: "fast",
  slowPeriod: "slow",
  signalPeriod: "signal",
  // Stochastic — frontend sends kPeriod/dPeriod
  kPeriod: "period",
  dPeriod: "smooth",
  // Bollinger — frontend sends stdDev
  stdDev: "std_dev",
  // SuperTrend — frontend sends factor
  factor: "multiplier",
  // Generic — price_breakout, volume_spike use "lookback"
  lookback: "period",
};

function normalizeParams(
  raw: Record<string, unknown>,
): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(raw)) {
    result[PARAM_ALIASES[k] ?? k] = v;
  }
  return result;
}

export function computeSMAArray(
  data: number[],
  period: number,
): (number | null)[] {
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

export function computeEMAArray(
  data: number[],
  period: number,
): (number | null)[] {
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

function computeTrueRange(
  highs: number[],
  lows: number[],
  closes: number[],
): number[] {
  const tr: number[] = [];
  for (let i = 0; i < highs.length; i++) {
    if (i === 0) {
      tr.push(highs[0] - lows[0]);
      continue;
    }
    tr.push(
      Math.max(
        highs[i] - lows[i],
        Math.abs(highs[i] - closes[i - 1]),
        Math.abs(lows[i] - closes[i - 1]),
      ),
    );
  }
  return tr;
}

/** Wilder-smoothed ATR array. */
function computeWilderATR(
  highs: number[],
  lows: number[],
  closes: number[],
  period: number,
): (number | null)[] {
  const tr = computeTrueRange(highs, lows, closes);
  const n = closes.length;
  const result: (number | null)[] = [];
  for (let i = 0; i < n; i++) {
    if (i < period - 1) {
      result.push(null);
      continue;
    }
    if (i === period - 1) {
      let sum = 0;
      for (let j = 0; j < period; j++) sum += tr[j];
      result.push(sum / period);
    } else {
      result.push((result[i - 1]! * (period - 1) + tr[i]) / period);
    }
  }
  return result;
}

// ─── Indicator family functions ───────────────────────────────────────────────

function smaFamily(
  bars: BarData,
  params: Record<string, unknown>,
): IndicatorValues {
  const period = p(params, "period", 20);
  return { sma: computeSMAArray(bars.closes, period) };
}

function emaFamily(
  bars: BarData,
  params: Record<string, unknown>,
): IndicatorValues {
  const period = p(params, "period", 12);
  return { ema: computeEMAArray(bars.closes, period) };
}

function rsiFamily(
  bars: BarData,
  params: Record<string, unknown>,
): IndicatorValues {
  const period = p(params, "period", 14);
  const { closes } = bars;
  const n = closes.length;
  const result: number[] = [];
  let prevAvgGain = 0;
  let prevAvgLoss = 0;

  for (let i = 0; i < n; i++) {
    if (i < 1) {
      result.push(50);
      continue;
    }
    if (i <= period) {
      if (i < period) {
        result.push(50);
        continue;
      }
      // i === period: seed with SMA of first `period` changes
      let gains = 0, losses = 0;
      for (let j = 1; j <= period; j++) {
        const diff = closes[j] - closes[j - 1];
        if (diff > 0) gains += diff;
        else losses -= diff;
      }
      prevAvgGain = gains / period;
      prevAvgLoss = losses / period;
    } else {
      const diff = closes[i] - closes[i - 1];
      const gain = diff > 0 ? diff : 0;
      const loss = diff < 0 ? -diff : 0;
      prevAvgGain = (prevAvgGain * (period - 1) + gain) / period;
      prevAvgLoss = (prevAvgLoss * (period - 1) + loss) / period;
    }
    const rs = prevAvgLoss === 0 ? 100 : prevAvgGain / prevAvgLoss;
    result.push(100 - 100 / (1 + rs));
  }
  return { rsi: result };
}

function macdFamily(
  bars: BarData,
  params: Record<string, unknown>,
): IndicatorValues {
  const fast = p(params, "fast", 12);
  const slow = p(params, "slow", 26);
  const signal = p(params, "signal", 9);
  const { closes } = bars;
  const n = closes.length;
  const emaFast = computeEMAArray(closes, fast);
  const emaSlow = computeEMAArray(closes, slow);

  const macd: (number | null)[] = [];
  for (let i = 0; i < n; i++) {
    macd.push(
      emaFast[i] !== null && emaSlow[i] !== null
        ? emaFast[i]! - emaSlow[i]!
        : null,
    );
  }

  const macdSignal: (number | null)[] = [];
  const macdHist: (number | null)[] = [];
  let sigCount = 0, sigSum = 0, sigEma: number | null = null;
  for (let i = 0; i < n; i++) {
    if (macd[i] === null) {
      macdSignal.push(null);
      macdHist.push(null);
      continue;
    }
    sigCount++;
    sigSum += macd[i]!;
    if (sigCount < signal) {
      macdSignal.push(null);
      macdHist.push(null);
      continue;
    }
    if (sigCount === signal) {
      sigEma = sigSum / signal;
    } else {
      sigEma = (macd[i]! - sigEma!) * (2 / (signal + 1)) + sigEma!;
    }
    macdSignal.push(sigEma);
    macdHist.push(macd[i]! - sigEma!);
  }

  return { macd, macd_signal: macdSignal, macd_hist: macdHist };
}

function atrFamily(
  bars: BarData,
  params: Record<string, unknown>,
): IndicatorValues {
  const period = p(params, "period", 14);
  return { atr: computeWilderATR(bars.highs, bars.lows, bars.closes, period) };
}

function stochasticFamily(
  bars: BarData,
  params: Record<string, unknown>,
): IndicatorValues {
  const period = p(params, "period", 14);
  const smooth = p(params, "smooth", 3);
  const { closes, highs, lows } = bars;
  const n = closes.length;

  const rawK: (number | null)[] = [];
  for (let i = 0; i < n; i++) {
    if (i < period - 1) {
      rawK.push(null);
      continue;
    }
    const low = Math.min(...lows.slice(i - period + 1, i + 1));
    const high = Math.max(...highs.slice(i - period + 1, i + 1));
    const range = high - low;
    rawK.push(range > 0 ? (100 * (closes[i] - low)) / range : 50);
  }

  // Smooth %K and %D
  const kSmoothed = computeSMAArray(rawK.map((v) => v ?? 0), smooth).map(
    (v, i) => (rawK[i] === null ? null : v),
  );
  const dSmoothed = computeSMAArray(kSmoothed.map((v) => v ?? 0), smooth).map(
    (v, i) => (kSmoothed[i] === null ? null : v),
  );

  return {
    stochastic: kSmoothed,
    stochastic_k: kSmoothed,
    stochastic_d: dSmoothed,
  };
}

function adxFamily(
  bars: BarData,
  params: Record<string, unknown>,
): IndicatorValues {
  const period = p(params, "period", 14);
  const { highs, lows, closes } = bars;
  const n = closes.length;
  const tr = computeTrueRange(highs, lows, closes);

  const plusDM: number[] = [];
  const minusDM: number[] = [];
  for (let i = 0; i < n; i++) {
    if (i === 0) {
      plusDM.push(0);
      minusDM.push(0);
      continue;
    }
    const upMove = highs[i] - highs[i - 1];
    const downMove = lows[i - 1] - lows[i];
    plusDM.push(upMove > downMove && upMove > 0 ? upMove : 0);
    minusDM.push(downMove > upMove && downMove > 0 ? downMove : 0);
  }

  const adx: (number | null)[] = [];
  const plusDI: (number | null)[] = [];
  const minusDI: (number | null)[] = [];
  let smoothPlus = 0, smoothMinus = 0, smoothTR = 0, adxSmooth = 0;

  for (let i = 0; i < n; i++) {
    if (i < period) {
      smoothPlus += plusDM[i];
      smoothMinus += minusDM[i];
      smoothTR += tr[i];
      adx.push(null);
      plusDI.push(null);
      minusDI.push(null);
      continue;
    }
    if (i > period) {
      smoothPlus = smoothPlus - smoothPlus / period + plusDM[i];
      smoothMinus = smoothMinus - smoothMinus / period + minusDM[i];
      smoothTR = smoothTR - smoothTR / period + tr[i];
    }
    const pdi = smoothTR > 0 ? (smoothPlus / smoothTR) * 100 : 0;
    const mdi = smoothTR > 0 ? (smoothMinus / smoothTR) * 100 : 0;
    plusDI.push(pdi);
    minusDI.push(mdi);
    const diSum = pdi + mdi;
    const dx = diSum > 0 ? (Math.abs(pdi - mdi) / diSum) * 100 : 0;
    if (i < period * 2) {
      adx.push(null);
    } else if (i === period * 2) {
      adxSmooth = dx;
      adx.push(adxSmooth);
    } else {
      adxSmooth = (adxSmooth * (period - 1) + dx) / period;
      adx.push(adxSmooth);
    }
  }

  return { adx, plus_di: plusDI, minus_di: minusDI };
}

function bollingerFamily(
  bars: BarData,
  params: Record<string, unknown>,
): IndicatorValues {
  const period = p(params, "period", 20);
  const stdDevMult = p(params, "std_dev", 2);
  const { closes } = bars;
  const n = closes.length;
  const bbUpper: (number | null)[] = [];
  const bbLower: (number | null)[] = [];
  const bbMiddle: (number | null)[] = [];

  for (let i = 0; i < n; i++) {
    if (i < period - 1) {
      bbUpper.push(null);
      bbLower.push(null);
      bbMiddle.push(null);
      continue;
    }
    const slice = closes.slice(i - period + 1, i + 1);
    const mean = slice.reduce((a, b) => a + b, 0) / period;
    const variance = slice.reduce((a, v) => a + (v - mean) ** 2, 0) / period;
    const sd = Math.sqrt(variance);
    bbMiddle.push(mean);
    bbUpper.push(mean + stdDevMult * sd);
    bbLower.push(mean - stdDevMult * sd);
  }

  return {
    bb_upper: bbUpper,
    bb_lower: bbLower,
    bb_middle: bbMiddle,
    bb: bbMiddle,
  };
}

function cciFamily(
  bars: BarData,
  params: Record<string, unknown>,
): IndicatorValues {
  const period = p(params, "period", 20);
  const { closes, highs, lows } = bars;
  const n = closes.length;
  const result: (number | null)[] = [];

  for (let i = 0; i < n; i++) {
    if (i < period - 1) {
      result.push(null);
      continue;
    }
    const tps: number[] = [];
    for (let j = i - period + 1; j <= i; j++) {
      tps.push((highs[j] + lows[j] + closes[j]) / 3);
    }
    const tp = tps[tps.length - 1];
    const meanTP = tps.reduce((a, b) => a + b, 0) / period;
    const meanDev = tps.reduce((a, v) => a + Math.abs(v - meanTP), 0) / period;
    result.push(meanDev > 0 ? (tp - meanTP) / (0.015 * meanDev) : 0);
  }
  return { cci: result };
}

function obvFamily(
  bars: BarData,
  _params: Record<string, unknown>,
): IndicatorValues {
  const { closes, volumes } = bars;
  const result: number[] = [];
  for (let i = 0; i < closes.length; i++) {
    if (i === 0) {
      result.push(volumes[0]);
      continue;
    }
    if (closes[i] > closes[i - 1]) result.push(result[i - 1] + volumes[i]);
    else if (closes[i] < closes[i - 1]) {
      result.push(result[i - 1] - volumes[i]);
    } else result.push(result[i - 1]);
  }
  return { obv: result };
}

function volumeMaFamily(
  bars: BarData,
  params: Record<string, unknown>,
): IndicatorValues {
  const period = p(params, "period", 20);
  return { volume_ma: computeSMAArray(bars.volumes, period) };
}

function volumeRatioFamily(
  bars: BarData,
  params: Record<string, unknown>,
): IndicatorValues {
  const period = p(params, "period", 20);
  const ma = computeSMAArray(bars.volumes, period);
  return {
    volume_ratio: bars.volumes.map((v, i) =>
      ma[i] !== null && ma[i]! > 0 ? v / ma[i]! : null
    ),
  };
}

function supertrendFamily(
  bars: BarData,
  params: Record<string, unknown>,
): IndicatorValues {
  const period = p(params, "period", 7);
  const mult = p(params, "multiplier", 2.0);
  const { highs, lows, closes } = bars;
  const n = closes.length;

  if (n === 0) {
    return {
      supertrend_trend: [],
      supertrend_signal: [],
      supertrend_factor: [],
    };
  }

  const tr = computeTrueRange(highs, lows, closes);
  const alpha = 1 / period;
  const atr: number[] = [];
  for (let i = 0; i < n; i++) {
    atr.push(i === 0 ? tr[0] : alpha * tr[i] + (1 - alpha) * atr[i - 1]);
  }

  const hl2 = highs.map((h, i) => (h + lows[i]) / 2);
  const basicUpper = hl2.map((v, i) => v + mult * atr[i]);
  const basicLower = hl2.map((v, i) => v - mult * atr[i]);

  const finalUpper: number[] = [];
  const finalLower: number[] = [];
  const supertrend: number[] = [];
  const trend: number[] = [];
  const signal: number[] = [];

  finalUpper[0] = basicUpper[0];
  finalLower[0] = basicLower[0];
  supertrend[0] = basicLower[0];
  trend[0] = 1;
  signal[0] = 0;

  for (let i = 1; i < n; i++) {
    const fu =
      basicUpper[i] < basicUpper[i - 1] || closes[i - 1] > finalUpper[i - 1]
        ? basicUpper[i]
        : finalUpper[i - 1];
    const fl =
      basicLower[i] > basicLower[i - 1] || closes[i - 1] < finalLower[i - 1]
        ? basicLower[i]
        : finalLower[i - 1];
    finalUpper[i] = fu;
    finalLower[i] = fl;

    let st: number, inUptrend: number;
    if (closes[i] > fu) {
      st = fl;
      inUptrend = 1;
    } else if (closes[i] < fl) {
      st = fu;
      inUptrend = 0;
    } else if (trend[i - 1] === 1) {
      st = fl;
      inUptrend = 1;
    } else {
      st = fu;
      inUptrend = 0;
    }
    supertrend.push(st);
    trend.push(inUptrend);
    signal.push(st !== 0 ? ((closes[i] - st) / st) * 100 : 0);
  }

  return {
    supertrend_trend: trend,
    supertrend_signal: signal,
    supertrend_factor: new Array(n).fill(mult),
  };
}

function mfiFamily(
  bars: BarData,
  params: Record<string, unknown>,
): IndicatorValues {
  const period = p(params, "period", 14);
  const { closes, highs, lows, volumes } = bars;
  const n = closes.length;
  const result: (number | null)[] = [];

  for (let i = 0; i < n; i++) {
    if (i < period) {
      result.push(null);
      continue;
    }
    let posFlow = 0, negFlow = 0;
    for (let j = i - period + 1; j <= i; j++) {
      const tp = (highs[j] + lows[j] + closes[j]) / 3;
      const prevTp = j > 0
        ? (highs[j - 1] + lows[j - 1] + closes[j - 1]) / 3
        : tp;
      const mf = tp * volumes[j];
      if (tp > prevTp) posFlow += mf;
      else if (tp < prevTp) negFlow += mf;
    }
    const ratio = negFlow > 0 ? posFlow / negFlow : 100;
    result.push(100 - 100 / (1 + ratio));
  }
  return { mfi: result };
}

function williamsRFamily(
  bars: BarData,
  params: Record<string, unknown>,
): IndicatorValues {
  const period = p(params, "period", 14);
  const { closes, highs, lows } = bars;
  const n = closes.length;
  const result: (number | null)[] = [];

  for (let i = 0; i < n; i++) {
    if (i < period - 1) {
      result.push(null);
      continue;
    }
    const high = Math.max(...highs.slice(i - period + 1, i + 1));
    const low = Math.min(...lows.slice(i - period + 1, i + 1));
    const range = high - low;
    result.push(range > 0 ? ((high - closes[i]) / range) * -100 : 0);
  }
  return { williams_r: result };
}

function momentumFamily(
  bars: BarData,
  params: Record<string, unknown>,
): IndicatorValues {
  const period = p(params, "period", 10);
  const { closes } = bars;
  const result: (number | null)[] = [];
  for (let i = 0; i < closes.length; i++) {
    result.push(i < period ? null : closes[i] - closes[i - period]);
  }
  return { momentum: result };
}

function rocFamily(
  bars: BarData,
  params: Record<string, unknown>,
): IndicatorValues {
  const period = p(params, "period", 10);
  const { closes } = bars;
  const result: (number | null)[] = [];
  for (let i = 0; i < closes.length; i++) {
    if (i < period || closes[i - period] === 0) {
      result.push(null);
      continue;
    }
    result.push(((closes[i] - closes[i - period]) / closes[i - period]) * 100);
  }
  return { roc: result };
}

function priceFamily(
  bars: BarData,
  _params: Record<string, unknown>,
): IndicatorValues {
  return {
    close: bars.closes,
    price: bars.closes,
    open: bars.opens,
    high: bars.highs,
    low: bars.lows,
  };
}

function volumeFamily(
  bars: BarData,
  _params: Record<string, unknown>,
): IndicatorValues {
  return { volume: bars.volumes };
}

function priceAboveSmaFamily(
  bars: BarData,
  params: Record<string, unknown>,
): IndicatorValues {
  const period = p(params, "period", 20);
  const sma = computeSMAArray(bars.closes, period);
  return {
    price_above_sma: sma.map((v, i) =>
      v !== null ? (bars.closes[i] > v ? 1 : 0) : null
    ),
  };
}

function priceAboveEmaFamily(
  bars: BarData,
  params: Record<string, unknown>,
): IndicatorValues {
  const period = p(params, "period", 12);
  const ema = computeEMAArray(bars.closes, period);
  return {
    price_above_ema: ema.map((v, i) =>
      v !== null ? (bars.closes[i] > v ? 1 : 0) : null
    ),
  };
}

function priceVsSmaFamily(
  bars: BarData,
  params: Record<string, unknown>,
): IndicatorValues {
  const period = p(params, "period", 20);
  const sma = computeSMAArray(bars.closes, period);
  const pct = sma.map((v, i) =>
    v !== null && v > 0 ? (bars.closes[i] - v) / v : null
  );
  // Also pre-compute sma50 for the price_vs_sma50 alias
  const sma50 = computeSMAArray(bars.closes, 50);
  const pct50 = sma50.map((v, i) =>
    v !== null && v > 0 ? (bars.closes[i] - v) / v : null
  );
  return {
    price_vs_sma: pct,
    price_vs_sma20: pct,
    price_vs_sma50: pct50,
  };
}

function priceVsEmaFamily(
  bars: BarData,
  params: Record<string, unknown>,
): IndicatorValues {
  const period = p(params, "period", 12);
  const ema = computeEMAArray(bars.closes, period);
  return {
    price_vs_ema: ema.map((v, i) =>
      v !== null && v > 0 ? (bars.closes[i] - v) / v : null
    ),
  };
}

// ─── Registry mappings ────────────────────────────────────────────────────────

/** Maps a condition name to the family function that computes it. */
const CONDITION_TO_FAMILY: Record<string, string> = {
  rsi: "rsi",
  macd: "macd",
  macd_signal: "macd",
  macd_hist: "macd",
  sma: "sma",
  ema: "ema",
  stochastic: "stochastic",
  stochastic_k: "stochastic",
  stochastic_d: "stochastic",
  adx: "adx",
  plus_di: "adx",
  minus_di: "adx",
  atr: "atr",
  bb: "bollinger",
  bb_upper: "bollinger",
  bb_lower: "bollinger",
  bb_middle: "bollinger",
  cci: "cci",
  obv: "obv",
  volume_ma: "volume_ma",
  volume_ratio: "volume_ratio",
  supertrend_trend: "supertrend",
  supertrend_signal: "supertrend",
  supertrend_factor: "supertrend",
  mfi: "mfi",
  williams_r: "williams_r",
  momentum: "momentum",
  roc: "roc",
  close: "price",
  price: "price",
  open: "price",
  high: "price",
  low: "price",
  volume: "volume",
  price_above_sma: "price_above_sma",
  price_above_ema: "price_above_ema",
  price_vs_sma: "price_vs_sma",
  price_vs_sma20: "price_vs_sma",
  price_vs_sma50: "price_vs_sma",
  price_vs_ema: "price_vs_ema",
};

const FAMILY_FNS: Record<string, IndicatorFn> = {
  rsi: rsiFamily,
  macd: macdFamily,
  sma: smaFamily,
  ema: emaFamily,
  stochastic: stochasticFamily,
  adx: adxFamily,
  atr: atrFamily,
  bollinger: bollingerFamily,
  cci: cciFamily,
  obv: obvFamily,
  volume_ma: volumeMaFamily,
  volume_ratio: volumeRatioFamily,
  supertrend: supertrendFamily,
  mfi: mfiFamily,
  williams_r: williamsRFamily,
  momentum: momentumFamily,
  roc: rocFamily,
  price: priceFamily,
  volume: volumeFamily,
  price_above_sma: priceAboveSmaFamily,
  price_above_ema: priceAboveEmaFamily,
  price_vs_sma: priceVsSmaFamily,
  price_vs_ema: priceVsEmaFamily,
};

/** Default params for each family when the condition doesn't specify any. */
const FAMILY_DEFAULTS: Record<string, Record<string, unknown>> = {
  rsi: { period: 14 },
  macd: { fast: 12, slow: 26, signal: 9 },
  sma: { period: 20 },
  ema: { period: 12 },
  stochastic: { period: 14, smooth: 3 },
  adx: { period: 14 },
  atr: { period: 14 },
  bollinger: { period: 20, std_dev: 2 },
  cci: { period: 20 },
  volume_ma: { period: 20 },
  volume_ratio: { period: 20 },
  supertrend: { period: 7, multiplier: 2.0 },
  mfi: { period: 14 },
  williams_r: { period: 14 },
  momentum: { period: 10 },
  roc: { period: 10 },
  price_above_sma: { period: 20 },
  price_above_ema: { period: 12 },
  price_vs_sma: { period: 20 },
  price_vs_ema: { period: 12 },
};

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Lazily compute indicators for all conditions in a strategy.
 * Each unique (family, params) combination is computed at most once.
 */
export function buildIndicatorCache(
  conditions: Array<{ name: string; params?: Record<string, unknown> }>,
  bars: BarData,
): IndicatorCache {
  const cache: IndicatorCache = new Map();

  for (const cond of conditions) {
    const family = CONDITION_TO_FAMILY[cond.name];
    if (!family) continue;

    const defaults = FAMILY_DEFAULTS[family] ?? {};
    // Normalize aliases (fastPeriod → fast, etc.) then merge with defaults
    const aliased = normalizeParams(cond.params ?? {});
    const normalized: Record<string, unknown> = { ...defaults };
    for (const [k, v] of Object.entries(aliased)) {
      const n = Number(v);
      normalized[k] = !isNaN(n) && v !== null && v !== undefined ? n : v;
    }

    const cacheKey = `${family}:${JSON.stringify(normalized)}`;
    if (!cache.has(cacheKey)) {
      const fn = FAMILY_FNS[family];
      if (fn) {
        cache.set(cacheKey, fn(bars, normalized));
      }
    }
  }

  return cache;
}

/**
 * Look up the value of a specific indicator at barIndex.
 * Returns null if the indicator is unknown or not yet warm.
 */
export function getIndicatorValue(
  name: string,
  condParams: Record<string, unknown>,
  barIndex: number,
  cache: IndicatorCache,
): number | null {
  const family = CONDITION_TO_FAMILY[name];
  if (!family) return null;

  const defaults = FAMILY_DEFAULTS[family] ?? {};
  const aliased = normalizeParams(condParams ?? {});
  const normalized: Record<string, unknown> = { ...defaults };
  for (const [k, v] of Object.entries(aliased)) {
    const n = Number(v);
    normalized[k] = !isNaN(n) && v !== null && v !== undefined ? n : v;
  }

  const cacheKey = `${family}:${JSON.stringify(normalized)}`;
  const values = cache.get(cacheKey);
  if (!values) return null;

  const arr = values[name];
  if (!arr) return null;

  const v = arr[barIndex];
  return v !== undefined && v !== null ? v : null;
}

/** Returns true if the indicator name is in the registry. */
export function isKnownIndicator(name: string): boolean {
  return name in CONDITION_TO_FAMILY;
}

/**
 * Annualization factor for Sharpe ratio based on timeframe.
 * Assumes ~252 trading days / year; intraday bars scale accordingly.
 */
export function annualizationFactor(timeframe: string): number {
  const factors: Record<string, number> = {
    d1: 252,
    h4: Math.round(252 * 6.5 / 4), // ~410 4h bars/year
    h1: Math.round(252 * 6.5), // ~1638 1h bars/year
    m30: Math.round(252 * 13), // ~3276
    m15: Math.round(252 * 26), // ~6552
    m5: Math.round(252 * 78), // ~19656
  };
  return factors[timeframe] ?? 252;
}
