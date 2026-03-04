/**
 * Statistical validation for backtests.
 *
 * Provides:
 *  - Bootstrap confidence intervals (95% CI on Sharpe, max drawdown, win rate)
 *  - Two-tailed t-test p-value on mean trade return vs. zero
 *  - IS/OOS 70/30 split metrics
 *  - Monthly returns heatmap data
 *  - Rolling Sharpe + win rate (63-bar window)
 *  - Drawdown series
 */

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ConfidenceInterval {
  lower: number;
  upper: number;
  confidence: number; // e.g. 0.95
}

export interface ValidationResult {
  confidence_intervals: {
    sharpe_ratio: ConfidenceInterval;
    max_drawdown_pct: ConfidenceInterval;
    win_rate: ConfidenceInterval;
  };
  p_value: number;
  bootstrap_iterations: number;
  sample_size: number;
  in_sample: SplitMetrics | null;
  out_of_sample: SplitMetrics | null;
}

export interface SplitMetrics {
  sharpe_ratio: number;
  total_return_pct: number;
  win_rate: number;
  total_trades: number;
  max_drawdown_pct: number;
}

export interface MonthlyReturn {
  year: number;
  month: number; // 1–12
  return_pct: number;
  is_partial: boolean; // true if this month's data may be incomplete
}

export interface RollingMetric {
  date: string;
  sharpe_63: number | null;
  win_rate_63: number | null;
}

export interface DrawdownPoint {
  date: string;
  drawdown_pct: number; // always <= 0
}

// ─── Bootstrap CI ─────────────────────────────────────────────────────────────

/** Pseudo-random LCG seeded for reproducibility (no crypto needed here). */
function lcgRand(seed: { v: number }): number {
  seed.v = (seed.v * 1664525 + 1013904223) & 0xffffffff;
  return (seed.v >>> 0) / 0x100000000;
}

/** Draw a bootstrap sample (with replacement) from an array. */
function bootstrapSample<T>(arr: T[], rng: { v: number }): T[] {
  const n = arr.length;
  const sample: T[] = new Array(n);
  for (let i = 0; i < n; i++) {
    sample[i] = arr[Math.floor(lcgRand(rng) * n)];
  }
  return sample;
}

/** Compute max drawdown (as fraction, e.g. 0.15 = 15%) from a pnl array. */
function computeMaxDrawdownFromPnl(
  pnls: number[],
  initialCapital: number,
): number {
  let equity = initialCapital;
  let peak = equity;
  let maxDD = 0;
  for (const pnl of pnls) {
    equity += pnl;
    if (equity > peak) peak = equity;
    const dd = peak > 0 ? (peak - equity) / peak : 0;
    if (dd > maxDD) maxDD = dd;
  }
  return maxDD;
}

/** Compute Sharpe from an array of trade returns (not annualized — for bootstrap comparison). */
function computeSharpeFromReturns(returns: number[]): number {
  if (returns.length < 2) return 0;
  const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
  const variance = returns.reduce((a, r) => a + (r - mean) ** 2, 0) /
    (returns.length - 1);
  const std = Math.sqrt(variance);
  return std > 0 ? mean / std : 0;
}

/** 95% bootstrap confidence intervals on Sharpe, max drawdown, and win rate. */
export function bootstrapCI(
  trades: Array<{ pnl: number; pnl_pct: number }>,
  initialCapital: number,
  iterations = 1000,
): ValidationResult["confidence_intervals"] {
  const pnls = trades.map((t) => t.pnl);
  const returns = trades.map((t) => t.pnl_pct / 100); // fractional

  const sharpes: number[] = [];
  const drawdowns: number[] = [];
  const winRates: number[] = [];

  const rng = { v: 42 };

  for (let iter = 0; iter < iterations; iter++) {
    const sampledPnls = bootstrapSample(pnls, rng);
    const sampledReturns = bootstrapSample(returns, rng);
    const sampledWins = bootstrapSample(
      trades.map((t) => (t.pnl > 0 ? 1 : 0)),
      rng,
    );

    sharpes.push(computeSharpeFromReturns(sampledReturns));
    drawdowns.push(
      computeMaxDrawdownFromPnl(sampledPnls, initialCapital) * 100,
    );
    winRates.push(
      (sampledWins.reduce((a, b) => a + b, 0) / sampledWins.length) * 100,
    );
  }

  function percentile(arr: number[], p: number): number {
    const sorted = [...arr].sort((a, b) => a - b);
    const idx = (p / 100) * (sorted.length - 1);
    const lo = Math.floor(idx);
    const hi = Math.ceil(idx);
    return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
  }

  return {
    sharpe_ratio: {
      lower: percentile(sharpes, 2.5),
      upper: percentile(sharpes, 97.5),
      confidence: 0.95,
    },
    max_drawdown_pct: {
      lower: percentile(drawdowns, 2.5),
      upper: percentile(drawdowns, 97.5),
      confidence: 0.95,
    },
    win_rate: {
      lower: Math.max(0, percentile(winRates, 2.5)),
      upper: Math.min(100, percentile(winRates, 97.5)),
      confidence: 0.95,
    },
  };
}

// ─── t-test p-value ───────────────────────────────────────────────────────────

/** Two-tailed t-test p-value: H0 = mean trade return is zero. */
export function tTestPValue(trades: Array<{ pnl_pct: number }>): number {
  if (trades.length < 2) return 1;

  const returns = trades.map((t) => t.pnl_pct / 100);
  const n = returns.length;
  const mean = returns.reduce((a, b) => a + b, 0) / n;
  const variance = returns.reduce((a, r) => a + (r - mean) ** 2, 0) / (n - 1);
  const se = Math.sqrt(variance / n);

  if (se === 0) return mean === 0 ? 1 : 0;

  const tStat = mean / se;
  const df = n - 1;

  // Approximate p-value using incomplete beta function via regularized beta
  return 2 * (1 - tCdf(Math.abs(tStat), df));
}

/**
 * CDF of the t-distribution using a rational approximation.
 * Accurate to ~4 decimal places for df >= 1.
 */
function tCdf(t: number, df: number): number {
  // Use normal approximation for large df
  if (df >= 100) {
    return normalCdf(t);
  }
  // Regularized incomplete beta: I(df/(df+t^2), df/2, 1/2)
  const x = df / (df + t * t);
  const ib = incompleteBeta(x, df / 2, 0.5);
  return 1 - 0.5 * ib;
}

/** Standard normal CDF via the error function. */
function normalCdf(z: number): number {
  return 0.5 * (1 + erf(z / Math.SQRT2));
}

/** Approximation of the error function (Abramowitz and Stegun 7.1.26). */
function erf(x: number): number {
  const sign = x >= 0 ? 1 : -1;
  x = Math.abs(x);
  const t = 1 / (1 + 0.3275911 * x);
  const poly = t *
    (0.254829592 +
      t *
        (-0.284496736 +
          t * (1.421413741 + t * (-1.453152027 + t * 1.061405429))));
  return sign * (1 - poly * Math.exp(-x * x));
}

/**
 * Regularized incomplete beta function I(x, a, b) via continued fraction.
 * Used by tCdf for small df.
 */
function incompleteBeta(x: number, a: number, b: number): number {
  if (x <= 0) return 0;
  if (x >= 1) return 1;

  const lbeta = lgamma(a) + lgamma(b) - lgamma(a + b);
  const front = Math.exp(Math.log(x) * a + Math.log(1 - x) * b - lbeta) / a;

  // Lentz continued fraction
  let f = 1;
  let c = 1;
  let d = 1 - (a + b) * x / (a + 1);
  if (Math.abs(d) < 1e-30) d = 1e-30;
  d = 1 / d;
  f = d;

  for (let m = 1; m <= 100; m++) {
    // Even step
    let numerator = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m));
    d = 1 + numerator * d;
    if (Math.abs(d) < 1e-30) d = 1e-30;
    c = 1 + numerator / c;
    if (Math.abs(c) < 1e-30) c = 1e-30;
    d = 1 / d;
    f *= d * c;

    // Odd step
    numerator = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1));
    d = 1 + numerator * d;
    if (Math.abs(d) < 1e-30) d = 1e-30;
    c = 1 + numerator / c;
    if (Math.abs(c) < 1e-30) c = 1e-30;
    d = 1 / d;
    const delta = d * c;
    f *= delta;

    if (Math.abs(delta - 1) < 1e-8) break;
  }

  return front * f;
}

/** Log-gamma function (Stirling's approximation for lgamma). */
function lgamma(x: number): number {
  const c = [
    76.18009172947146,
    -86.50532032941677,
    24.01409824083091,
    -1.231739572450155,
    0.001208650973866179,
    -5.395239384953e-6,
  ];
  let y = x;
  let tmp = x + 5.5;
  tmp = (x + 0.5) * Math.log(tmp) - tmp;
  let ser = 1.000000000190015;
  for (const coef of c) {
    ser += coef / ++y;
  }
  return tmp + Math.log(2.5066282746310005 * ser / x);
}

// ─── IS / OOS split ───────────────────────────────────────────────────────────

/** Compute metrics for a subset of trades and equity curve points. */
export function computeSplitMetrics(
  trades: Array<{ pnl: number; pnl_pct: number }>,
  equityCurve: Array<{ value: number }>,
  initialCapital: number,
  annFactor: number,
): SplitMetrics {
  if (trades.length === 0) {
    return {
      sharpe_ratio: 0,
      total_return_pct: 0,
      win_rate: 0,
      total_trades: 0,
      max_drawdown_pct: 0,
    };
  }

  const wins = trades.filter((t) => t.pnl > 0).length;
  const winRate = (wins / trades.length) * 100;

  const totalPnl = trades.reduce((s, t) => s + t.pnl, 0);
  const totalReturnPct = (totalPnl / initialCapital) * 100;

  let maxDD = 0;
  let peak = initialCapital;
  let equity = initialCapital;
  for (const eq of equityCurve) {
    equity = eq.value;
    if (equity > peak) peak = equity;
    const dd = peak > 0 ? (peak - equity) / peak : 0;
    if (dd > maxDD) maxDD = dd;
  }

  // Sharpe on equity returns
  const returns: number[] = [];
  for (let i = 1; i < equityCurve.length; i++) {
    const prev = equityCurve[i - 1].value;
    if (prev > 0) returns.push((equityCurve[i].value - prev) / prev);
  }
  let sharpe = 0;
  if (returns.length > 1) {
    const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
    const variance = returns.reduce((a, r) => a + (r - mean) ** 2, 0) /
      (returns.length - 1);
    const std = Math.sqrt(variance);
    if (std > 0) sharpe = (mean / std) * Math.sqrt(annFactor);
  }

  return {
    sharpe_ratio: sharpe,
    total_return_pct: totalReturnPct,
    win_rate: winRate,
    total_trades: trades.length,
    max_drawdown_pct: maxDD * 100,
  };
}

// ─── Monthly returns ──────────────────────────────────────────────────────────

/**
 * Aggregate equity curve into monthly returns.
 * Returns one entry per calendar month covered by the backtest.
 */
export function computeMonthlyReturns(
  equityCurve: Array<{ date: string; value: number }>,
): MonthlyReturn[] {
  if (equityCurve.length < 2) return [];

  const monthlyMap = new Map<
    string,
    { start: number; end: number; key: string }
  >();

  for (const point of equityCurve) {
    const date = new Date(point.date);
    const year = date.getUTCFullYear();
    const month = date.getUTCMonth() + 1;
    const key = `${year}-${String(month).padStart(2, "0")}`;

    if (!monthlyMap.has(key)) {
      monthlyMap.set(key, { start: point.value, end: point.value, key });
    } else {
      monthlyMap.get(key)!.end = point.value;
    }
  }

  const firstDate = new Date(equityCurve[0].date);
  const lastDate = new Date(equityCurve[equityCurve.length - 1].date);

  return Array.from(monthlyMap.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, { start, end }]) => {
      const [yearStr, monthStr] = key.split("-");
      const year = parseInt(yearStr);
      const month = parseInt(monthStr);

      // Mark partial: first or last month where data doesn't span the whole month
      const pointDate = new Date(year, month - 1, 1);
      const isFirstMonth = year === firstDate.getUTCFullYear() &&
        month === firstDate.getUTCMonth() + 1;
      const isLastMonth = year === lastDate.getUTCFullYear() &&
        month === lastDate.getUTCMonth() + 1;
      void pointDate;

      return {
        year,
        month,
        return_pct: start > 0 ? ((end - start) / start) * 100 : 0,
        is_partial: isFirstMonth || isLastMonth,
      };
    });
}

// ─── Rolling metrics ──────────────────────────────────────────────────────────

/**
 * Compute rolling Sharpe (63-bar window) and rolling win rate from equity curve + trades.
 */
export function computeRollingMetrics(
  equityCurve: Array<{ date: string; value: number }>,
  trades: Array<{ entry_date: string; exit_date: string; pnl: number }>,
  annFactor: number,
  windowSize = 63,
): RollingMetric[] {
  const metrics: RollingMetric[] = [];

  if (equityCurve.length < windowSize + 1) {
    return equityCurve.map((e) => ({
      date: e.date,
      sharpe_63: null,
      win_rate_63: null,
    }));
  }

  for (let i = 0; i < equityCurve.length; i++) {
    if (i < windowSize) {
      metrics.push({
        date: equityCurve[i].date,
        sharpe_63: null,
        win_rate_63: null,
      });
      continue;
    }

    const window = equityCurve.slice(i - windowSize, i + 1);
    const returns: number[] = [];
    for (let j = 1; j < window.length; j++) {
      const prev = window[j - 1].value;
      if (prev > 0) returns.push((window[j].value - prev) / prev);
    }

    let sharpe63: number | null = null;
    if (returns.length > 1) {
      const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
      const variance = returns.reduce((a, r) => a + (r - mean) ** 2, 0) /
        (returns.length - 1);
      const std = Math.sqrt(variance);
      sharpe63 = std > 0 ? (mean / std) * Math.sqrt(annFactor) : 0;
    }

    // Rolling win rate: trades whose exit_date falls within the window
    const windowStart = equityCurve[i - windowSize].date;
    const windowEnd = equityCurve[i].date;
    const windowTrades = trades.filter(
      (t) => t.exit_date >= windowStart && t.exit_date <= windowEnd,
    );
    const winRate63 = windowTrades.length > 0
      ? (windowTrades.filter((t) => t.pnl > 0).length / windowTrades.length) *
        100
      : null;

    metrics.push({
      date: equityCurve[i].date,
      sharpe_63: sharpe63,
      win_rate_63: winRate63,
    });
  }

  return metrics;
}

// ─── Drawdown series ──────────────────────────────────────────────────────────

/**
 * Compute percentage drawdown series from equity curve.
 * Values are always <= 0 (0 at new highs, negative during drawdowns).
 */
export function computeDrawdownSeries(
  equityCurve: Array<{ date: string; value: number }>,
): DrawdownPoint[] {
  let peak = 0;
  const series: DrawdownPoint[] = [];

  for (const point of equityCurve) {
    if (point.value > peak) peak = point.value;
    const dd = peak > 0 ? ((point.value - peak) / peak) * 100 : 0;
    series.push({ date: point.date, drawdown_pct: dd });
  }

  return series;
}

// ─── Full validation runner ───────────────────────────────────────────────────

export interface FullValidationOutput {
  validation: ValidationResult | null;
  monthly_returns: MonthlyReturn[];
  rolling_metrics: RollingMetric[];
  drawdown_series: DrawdownPoint[];
}

/**
 * Run all statistical validations on a completed backtest.
 * Returns null for validation if fewer than 10 trades (insufficient sample).
 */
export function runValidation(
  trades: Array<{
    pnl: number;
    pnl_pct: number;
    entry_date: string;
    exit_date: string;
  }>,
  equityCurve: Array<{ date: string; value: number }>,
  initialCapital: number,
  annFactor: number,
  bootstrapIterations = 1000,
): FullValidationOutput {
  // Always compute time-series data
  const monthly_returns = computeMonthlyReturns(equityCurve);
  const rolling_metrics = computeRollingMetrics(equityCurve, trades, annFactor);
  const drawdown_series = computeDrawdownSeries(equityCurve);

  // Skip statistical validation if insufficient trades
  if (trades.length < 10) {
    return {
      validation: null,
      monthly_returns,
      rolling_metrics,
      drawdown_series,
    };
  }

  // Bootstrap CI and p-value
  const confidence_intervals = bootstrapCI(
    trades,
    initialCapital,
    bootstrapIterations,
  );
  const p_value = tTestPValue(trades);

  // IS/OOS 70/30 split by bar index (not by trade count — ensures temporal correctness)
  const splitIdx = Math.floor(equityCurve.length * 0.7);
  const isCutoff = equityCurve[splitIdx]?.date ?? "";

  const isTrades = trades.filter((t) => t.exit_date <= isCutoff);
  const oosTrades = trades.filter((t) => t.exit_date > isCutoff);
  const isEquity = equityCurve.slice(0, splitIdx + 1);
  const oosEquity = equityCurve.slice(splitIdx);

  const in_sample = computeSplitMetrics(
    isTrades,
    isEquity,
    initialCapital,
    annFactor,
  );
  const out_of_sample = computeSplitMetrics(
    oosTrades,
    oosEquity,
    oosEquity[0]?.value ?? initialCapital,
    annFactor,
  );

  const validation: ValidationResult = {
    confidence_intervals,
    p_value,
    bootstrap_iterations: bootstrapIterations,
    sample_size: trades.length,
    in_sample,
    out_of_sample,
  };

  return { validation, monthly_returns, rolling_metrics, drawdown_series };
}
