// support-resistance: Get support and resistance levels for a symbol
// GET /support-resistance?symbol=AAPL
//
// Returns S/R levels using 3 modern indicators:
// - Pivot Levels (multi-timeframe: 5, 25, 50, 100 bars)
// - Polynomial Regression (dynamic trending S/R with slopes)
// - Logistic Regression (ML-based with probabilities)

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

// ============================================================================
// Types
// ============================================================================

interface OHLCBar {
  ts: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

type PivotStatus = "support" | "resistance" | "active" | "inactive";

interface PivotLevelPeriod {
  high: number | null;
  low: number | null;
  highStatus: PivotStatus;
  lowStatus: PivotStatus;
}

interface PivotLevelsResult {
  period5: PivotLevelPeriod | null;
  period25: PivotLevelPeriod | null;
  period50: PivotLevelPeriod | null;
  period100: PivotLevelPeriod | null;
}

interface PolynomialResult {
  support: number | null;
  resistance: number | null;
  supportSlope: number;
  resistanceSlope: number;
  forecastSupport: number[];
  forecastResistance: number[];
}

interface LogisticLevel {
  level: number;
  probability: number;
  timesRespected: number;
  isSupport: boolean;
}

interface LogisticResult {
  supportLevels: LogisticLevel[];
  resistanceLevels: LogisticLevel[];
  signals: string[];
}

interface SupportResistanceResponse {
  symbol: string;
  currentPrice: number;
  lastUpdated: string;
  // Summary
  nearestSupport: number | null;
  nearestResistance: number | null;
  supportDistancePct: number | null;
  resistanceDistancePct: number | null;
  allSupports: number[];
  allResistances: number[];
  bias: string;
  // Indicator results
  pivotLevels: PivotLevelsResult;
  polynomial: PolynomialResult;
  logistic: LogisticResult;
  // Signals
  signals: string[];
}

// ============================================================================
// Pivot Levels Detector (Multi-timeframe)
// ============================================================================

function detectPivots(
  bars: OHLCBar[],
  period: number
): { highs: number[]; lows: number[]; highIdx: number[]; lowIdx: number[] } {
  const highs: number[] = [];
  const lows: number[] = [];
  const highIdx: number[] = [];
  const lowIdx: number[] = [];

  for (let i = period; i < bars.length - period; i++) {
    const bar = bars[i];

    // Check pivot high
    let isHigh = true;
    for (let j = i - period; j <= i + period; j++) {
      if (j !== i && bars[j].high > bar.high) {
        isHigh = false;
        break;
      }
    }
    if (isHigh) {
      highs.push(bar.high);
      highIdx.push(i);
    }

    // Check pivot low
    let isLow = true;
    for (let j = i - period; j <= i + period; j++) {
      if (j !== i && bars[j].low < bar.low) {
        isLow = false;
        break;
      }
    }
    if (isLow) {
      lows.push(bar.low);
      lowIdx.push(i);
    }
  }

  return { highs, lows, highIdx, lowIdx };
}

function calculateATR(bars: OHLCBar[], period: number): number {
  if (bars.length <= period) return 0;

  const trueRanges: number[] = [];
  for (let i = 1; i < bars.length; i++) {
    const tr = Math.max(
      bars[i].high - bars[i].low,
      Math.abs(bars[i].high - bars[i - 1].close),
      Math.abs(bars[i].low - bars[i - 1].close)
    );
    trueRanges.push(tr);
  }

  // Wilder's smoothing
  let atr = trueRanges.slice(0, period).reduce((a, b) => a + b, 0) / period;
  for (let i = period; i < trueRanges.length; i++) {
    atr = (atr * (period - 1) + trueRanges[i]) / period;
  }

  return atr;
}

function calculatePivotLevels(bars: OHLCBar[]): PivotLevelsResult {
  const result: PivotLevelsResult = {
    period5: null,
    period25: null,
    period50: null,
    period100: null,
  };

  if (bars.length < 20) return result;

  const lastBar = bars[bars.length - 1];
  const atr = calculateATR(bars, Math.min(200, bars.length - 1)) * 1.5;

  const periods = [5, 25, 50, 100] as const;
  const periodKeys: Record<number, keyof PivotLevelsResult> = {
    5: "period5",
    25: "period25",
    50: "period50",
    100: "period100",
  };

  for (const period of periods) {
    if (bars.length <= period * 2) continue;

    const pivots = detectPivots(bars, period);

    const recentHigh = pivots.highs.length > 0 ? pivots.highs[pivots.highs.length - 1] : 0;
    const recentLow = pivots.lows.length > 0 ? pivots.lows[pivots.lows.length - 1] : 0;

    // Determine status based on price position relative to level + ATR
    let highStatus: PivotStatus = "inactive";
    let lowStatus: PivotStatus = "inactive";

    if (recentHigh > 0) {
      if (lastBar.low > recentHigh + atr) {
        highStatus = "support";
      } else if (lastBar.high < recentHigh - atr) {
        highStatus = "resistance";
      } else {
        highStatus = "active";
      }
    }

    if (recentLow > 0) {
      if (lastBar.low > recentLow + atr) {
        lowStatus = "support";
      } else if (lastBar.high < recentLow - atr) {
        lowStatus = "resistance";
      } else {
        lowStatus = "active";
      }
    }

    result[periodKeys[period]] = {
      high: recentHigh > 0 ? Math.round(recentHigh * 100) / 100 : null,
      low: recentLow > 0 ? Math.round(recentLow * 100) / 100 : null,
      highStatus,
      lowStatus,
    };
  }

  return result;
}

// ============================================================================
// Polynomial Regression Indicator
// ============================================================================

function polyFit(x: number[], y: number[], degree: number): number[] | null {
  if (x.length < degree + 1) return null;

  // Normalize x to [0, 1]
  const xMin = Math.min(...x);
  const xMax = Math.max(...x);
  const xRange = xMax - xMin || 1;
  const xNorm = x.map((v) => (v - xMin) / xRange);

  // Build Vandermonde matrix
  const n = x.length;
  const m = degree + 1;
  const A: number[][] = [];
  for (let i = 0; i < n; i++) {
    const row: number[] = [];
    for (let j = 0; j < m; j++) {
      row.push(Math.pow(xNorm[i], j));
    }
    A.push(row);
  }

  // Solve A^T * A * coeffs = A^T * y using normal equations
  // This is simplified - for production, use a proper linear algebra library
  const ATA: number[][] = [];
  const ATb: number[] = [];

  for (let i = 0; i < m; i++) {
    ATA.push([]);
    for (let j = 0; j < m; j++) {
      let sum = 0;
      for (let k = 0; k < n; k++) {
        sum += A[k][i] * A[k][j];
      }
      ATA[i].push(sum);
    }
    let sumB = 0;
    for (let k = 0; k < n; k++) {
      sumB += A[k][i] * y[k];
    }
    ATb.push(sumB);
  }

  // Gaussian elimination (simplified)
  const coeffs = gaussianElimination(ATA, ATb);
  return coeffs;
}

function gaussianElimination(A: number[][], b: number[]): number[] | null {
  const n = A.length;
  const augmented = A.map((row, i) => [...row, b[i]]);

  for (let i = 0; i < n; i++) {
    // Find pivot
    let maxRow = i;
    for (let k = i + 1; k < n; k++) {
      if (Math.abs(augmented[k][i]) > Math.abs(augmented[maxRow][i])) {
        maxRow = k;
      }
    }
    [augmented[i], augmented[maxRow]] = [augmented[maxRow], augmented[i]];

    if (Math.abs(augmented[i][i]) < 1e-10) return null;

    // Eliminate column
    for (let k = i + 1; k < n; k++) {
      const factor = augmented[k][i] / augmented[i][i];
      for (let j = i; j <= n; j++) {
        augmented[k][j] -= factor * augmented[i][j];
      }
    }
  }

  // Back substitution
  const x = new Array(n).fill(0);
  for (let i = n - 1; i >= 0; i--) {
    x[i] = augmented[i][n];
    for (let j = i + 1; j < n; j++) {
      x[i] -= augmented[i][j] * x[j];
    }
    x[i] /= augmented[i][i];
  }

  return x;
}

function calculatePolynomialSR(bars: OHLCBar[], lookback = 150): PolynomialResult {
  const result: PolynomialResult = {
    support: null,
    resistance: null,
    supportSlope: 0,
    resistanceSlope: 0,
    forecastSupport: [],
    forecastResistance: [],
  };

  if (bars.length < 20) return result;

  const n = bars.length;
  const pivotSize = 5;

  // Detect pivots
  const resPivots: { idx: number; price: number }[] = [];
  const supPivots: { idx: number; price: number }[] = [];

  for (let i = pivotSize; i < n - pivotSize; i++) {
    // Check resistance (high pivot)
    let isHigh = true;
    for (let j = i - pivotSize; j <= i + pivotSize; j++) {
      if (j !== i && bars[j].high > bars[i].high) {
        isHigh = false;
        break;
      }
    }
    if (isHigh) {
      resPivots.push({ idx: i, price: bars[i].high });
    }

    // Check support (low pivot)
    let isLow = true;
    for (let j = i - pivotSize; j <= i + pivotSize; j++) {
      if (j !== i && bars[j].low < bars[i].low) {
        isLow = false;
        break;
      }
    }
    if (isLow) {
      supPivots.push({ idx: i, price: bars[i].low });
    }
  }

  // Filter by lookback
  const minIdx = Math.max(0, n - lookback);
  const filteredRes = resPivots.filter((p) => p.idx >= minIdx);
  const filteredSup = supPivots.filter((p) => p.idx >= minIdx);

  // Fit linear regression to resistance pivots
  if (filteredRes.length >= 2) {
    const xRes = filteredRes.map((p) => n - 1 - p.idx);
    const yRes = filteredRes.map((p) => p.price);
    const coeffs = polyFit(xRes, yRes, 1);
    if (coeffs) {
      // Predict at x=0 (current bar)
      result.resistance = Math.round(coeffs[0] * 100) / 100;
      result.resistanceSlope = Math.round(coeffs[1] * 10000) / 10000;

      // Forecast
      const xMin = Math.min(...xRes);
      const xMax = Math.max(...xRes);
      for (let i = 1; i <= 10; i++) {
        const xNorm = (-i - xMin) / (xMax - xMin || 1);
        const forecast = coeffs[0] + coeffs[1] * xNorm;
        result.forecastResistance.push(Math.round(forecast * 100) / 100);
      }
    }
  }

  // Fit linear regression to support pivots
  if (filteredSup.length >= 2) {
    const xSup = filteredSup.map((p) => n - 1 - p.idx);
    const ySup = filteredSup.map((p) => p.price);
    const coeffs = polyFit(xSup, ySup, 1);
    if (coeffs) {
      result.support = Math.round(coeffs[0] * 100) / 100;
      result.supportSlope = Math.round(coeffs[1] * 10000) / 10000;

      // Forecast
      const xMin = Math.min(...xSup);
      const xMax = Math.max(...xSup);
      for (let i = 1; i <= 10; i++) {
        const xNorm = (-i - xMin) / (xMax - xMin || 1);
        const forecast = coeffs[0] + coeffs[1] * xNorm;
        result.forecastSupport.push(Math.round(forecast * 100) / 100);
      }
    }
  }

  return result;
}

// ============================================================================
// Logistic Regression Indicator (Simplified)
// ============================================================================

function calculateRSI(bars: OHLCBar[], period = 14): number[] {
  const rsi: number[] = new Array(bars.length).fill(50);
  if (bars.length <= period) return rsi;

  const gains: number[] = [0];
  const losses: number[] = [0];

  for (let i = 1; i < bars.length; i++) {
    const change = bars[i].close - bars[i - 1].close;
    gains.push(Math.max(change, 0));
    losses.push(Math.max(-change, 0));
  }

  let avgGain = gains.slice(0, period + 1).reduce((a, b) => a + b, 0) / period;
  let avgLoss = losses.slice(0, period + 1).reduce((a, b) => a + b, 0) / period;

  for (let i = period; i < bars.length; i++) {
    avgGain = (avgGain * (period - 1) + gains[i]) / period;
    avgLoss = (avgLoss * (period - 1) + losses[i]) / period;
    const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    rsi[i] = 100 - 100 / (1 + rs);
  }

  return rsi;
}

function calculateLogisticSR(bars: OHLCBar[]): LogisticResult {
  const result: LogisticResult = {
    supportLevels: [],
    resistanceLevels: [],
    signals: [],
  };

  if (bars.length < 30) return result;

  const pivotLength = 14;
  const probThreshold = 0.7;
  const n = bars.length;

  // Pre-calculate RSI
  const rsiValues = calculateRSI(bars, pivotLength);

  // Calculate ATR
  const atr = calculateATR(bars, pivotLength);

  // Track levels
  interface LevelTrack {
    isSupport: boolean;
    level: number;
    startIdx: number;
    timesRespected: number;
    rsi: number;
    bodySize: number;
    endIdx: number | null;
  }

  const allLevels: LevelTrack[] = [];

  // Process bars sequentially
  for (let currentIdx = pivotLength * 2; currentIdx < n; currentIdx++) {
    const currentBar = bars[currentIdx];

    // Update existing levels
    for (const level of allLevels) {
      if (level.endIdx !== null) continue;
      if (currentIdx <= level.startIdx + pivotLength) continue;

      if (level.isSupport) {
        if (currentBar.low < level.level) {
          if (currentBar.close > level.level) {
            level.timesRespected++;
          } else {
            level.endIdx = currentIdx;
          }
        }
      } else {
        if (currentBar.high > level.level) {
          if (currentBar.close < level.level) {
            level.timesRespected++;
          } else {
            level.endIdx = currentIdx;
          }
        }
      }
    }

    // Detect pivots
    const pivotIdx = currentIdx - pivotLength;
    if (pivotIdx >= pivotLength) {
      const bar = bars[pivotIdx];

      // Check pivot high (resistance)
      let isHigh = true;
      for (let offset = 1; offset <= pivotLength; offset++) {
        if (
          bars[pivotIdx - offset].high > bar.high ||
          bars[pivotIdx + offset].high > bar.high
        ) {
          isHigh = false;
          break;
        }
      }

      if (isHigh) {
        const rsi = rsiValues[pivotIdx];
        const bodySize = Math.abs(bar.close - bar.open);
        allLevels.push({
          isSupport: false,
          level: bar.high,
          startIdx: pivotIdx,
          timesRespected: 0,
          rsi: rsi > 50 ? 1 : -1,
          bodySize: atr > 0 && bodySize > atr ? 1 : -1,
          endIdx: null,
        });
      }

      // Check pivot low (support)
      let isLow = true;
      for (let offset = 1; offset <= pivotLength; offset++) {
        if (
          bars[pivotIdx - offset].low < bar.low ||
          bars[pivotIdx + offset].low < bar.low
        ) {
          isLow = false;
          break;
        }
      }

      if (isLow) {
        const rsi = rsiValues[pivotIdx];
        const bodySize = Math.abs(bar.close - bar.open);
        allLevels.push({
          isSupport: true,
          level: bar.low,
          startIdx: pivotIdx,
          timesRespected: 0,
          rsi: rsi > 50 ? 1 : -1,
          bodySize: atr > 0 && bodySize > atr ? 1 : -1,
          endIdx: null,
        });
      }
    }
  }

  // Calculate probabilities using simple heuristic
  // (Simplified from full logistic regression)
  const lastClose = bars[n - 1].close;

  for (const level of allLevels) {
    if (level.endIdx !== null) continue;

    // Simple probability based on respects and distance
    const dist = Math.abs(level.level - lastClose) / lastClose;
    if (dist > 0.07) continue; // Skip far levels

    // Base probability on respects (0.5 + 0.1 per respect, max 0.9)
    const prob = Math.min(0.9, 0.5 + level.timesRespected * 0.1);

    if (prob >= probThreshold) {
      const logLevel: LogisticLevel = {
        level: Math.round(level.level * 100) / 100,
        probability: Math.round(prob * 100) / 100,
        timesRespected: level.timesRespected,
        isSupport: level.isSupport,
      };

      if (level.isSupport && level.level < lastClose) {
        result.supportLevels.push(logLevel);
      } else if (!level.isSupport && level.level > lastClose) {
        result.resistanceLevels.push(logLevel);
      }
    }
  }

  // Sort by probability
  result.supportLevels.sort((a, b) => b.probability - a.probability);
  result.resistanceLevels.sort((a, b) => b.probability - a.probability);

  // Detect signals on last bar
  const lastBar = bars[n - 1];
  for (const level of allLevels) {
    if (level.endIdx !== null) continue;

    if (level.isSupport) {
      if (lastBar.low < level.level) {
        if (lastBar.close > level.level) {
          result.signals.push("support_retest");
        } else {
          result.signals.push("support_break");
        }
      }
    } else {
      if (lastBar.high > level.level) {
        if (lastBar.close < level.level) {
          result.signals.push("resistance_retest");
        } else {
          result.signals.push("resistance_break");
        }
      }
    }
  }

  return result;
}

// ============================================================================
// Main Handler
// ============================================================================

serve(async (req: Request): Promise<Response> => {
  if (req.method === "OPTIONS") {
    return handleCorsOptions();
  }

  if (req.method !== "GET") {
    return errorResponse("Method not allowed", 405);
  }

  try {
    const url = new URL(req.url);
    const symbol = url.searchParams.get("symbol");
    const lookback = parseInt(url.searchParams.get("lookback") || "252");

    if (!symbol) {
      return errorResponse("Missing required parameter: symbol", 400);
    }

    const supabase = getSupabaseClient();

    // Get symbol ID
    const { data: symbolData, error: symbolError } = await supabase
      .from("symbols")
      .select("id, ticker")
      .eq("ticker", symbol.toUpperCase())
      .single();

    if (symbolError || !symbolData) {
      return errorResponse(`Symbol not found: ${symbol}`, 404);
    }

    // Fetch OHLC data
    const { data: rawOhlcData, error: ohlcError } = await supabase
      .from("ohlc_bars")
      .select("ts, open, high, low, close, volume")
      .eq("symbol_id", symbolData.id)
      .eq("timeframe", "d1")
      .order("ts", { ascending: false })
      .limit(lookback);

    const ohlcData = rawOhlcData ? [...rawOhlcData].reverse() : null;

    if (ohlcError) {
      console.error("[support-resistance] OHLC query error:", ohlcError);
      return errorResponse(`Database error: ${ohlcError.message}`, 500);
    }

    if (!ohlcData || ohlcData.length < 20) {
      return errorResponse(`Insufficient data for ${symbol}`, 400);
    }

    const lastBar = ohlcData[ohlcData.length - 1];
    const currentPrice = lastBar.close;

    // Calculate all indicators
    const pivotLevels = calculatePivotLevels(ohlcData as OHLCBar[]);
    const polynomial = calculatePolynomialSR(ohlcData as OHLCBar[]);
    const logistic = calculateLogisticSR(ohlcData as OHLCBar[]);

    // Collect all supports and resistances
    const allSupports: number[] = [];
    const allResistances: number[] = [];

    // From pivot levels
    const pivotPeriods = [pivotLevels.period5, pivotLevels.period25, pivotLevels.period50, pivotLevels.period100];
    for (const pl of pivotPeriods) {
      if (!pl) continue;
      if (pl.low && pl.low > 0 && pl.low < currentPrice) {
        allSupports.push(pl.low);
      }
      if (pl.high && pl.high > 0 && pl.high > currentPrice) {
        allResistances.push(pl.high);
      }
    }

    // From polynomial
    if (polynomial.support && polynomial.support < currentPrice) {
      allSupports.push(polynomial.support);
    }
    if (polynomial.resistance && polynomial.resistance > currentPrice) {
      allResistances.push(polynomial.resistance);
    }

    // From logistic
    for (const l of logistic.supportLevels) {
      allSupports.push(l.level);
    }
    for (const l of logistic.resistanceLevels) {
      allResistances.push(l.level);
    }

    // Deduplicate and sort
    const uniqueSupports = [...new Set(allSupports)].sort((a, b) => b - a);
    const uniqueResistances = [...new Set(allResistances)].sort((a, b) => a - b);

    const nearestSupport = uniqueSupports[0] || null;
    const nearestResistance = uniqueResistances[0] || null;

    const supportDistancePct = nearestSupport
      ? Math.round(((currentPrice - nearestSupport) / currentPrice) * 10000) / 100
      : null;
    const resistanceDistancePct = nearestResistance
      ? Math.round(((nearestResistance - currentPrice) / currentPrice) * 10000) / 100
      : null;

    // Calculate bias
    let bias = "Neutral";
    if (supportDistancePct !== null && resistanceDistancePct !== null) {
      if (supportDistancePct < resistanceDistancePct) {
        bias = "Bullish";
      } else if (resistanceDistancePct < supportDistancePct) {
        bias = "Bearish";
      }
    }

    // Collect all signals
    const signals = [...logistic.signals];

    const response: SupportResistanceResponse = {
      symbol: symbolData.ticker,
      currentPrice: Math.round(currentPrice * 100) / 100,
      lastUpdated: lastBar.ts,
      nearestSupport,
      nearestResistance,
      supportDistancePct,
      resistanceDistancePct,
      allSupports: uniqueSupports.slice(0, 5),
      allResistances: uniqueResistances.slice(0, 5),
      bias,
      pivotLevels,
      polynomial,
      logistic,
      signals,
    };

    console.log(
      `[support-resistance] ${symbol}: price=${currentPrice}, ` +
        `support=${nearestSupport}, resistance=${nearestResistance}, ` +
        `bias=${bias}, signals=${signals.length}`
    );

    return jsonResponse(response);
  } catch (err) {
    console.error("[support-resistance] Unexpected error:", err);
    return errorResponse(
      `Internal server error: ${err instanceof Error ? err.message : String(err)}`,
      500
    );
  }
});
