// support-resistance: Get support and resistance levels for a symbol
// GET /support-resistance?symbol=AAPL
//
// Returns S/R levels including:
// - Pivot points (classical)
// - Fibonacci retracement levels
// - ZigZag swing points
// - Nearest support/resistance
// - Distance percentages

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

// Response interfaces
interface PivotPoints {
  PP: number;
  R1: number;
  R2: number;
  R3: number;
  S1: number;
  S2: number;
  S3: number;
}

interface FibonacciLevels {
  "0.0": number;
  "23.6": number;
  "38.2": number;
  "50.0": number;
  "61.8": number;
  "78.6": number;
  "100.0": number;
  trend: "uptrend" | "downtrend";
  rangeHigh: number;
  rangeLow: number;
}

interface SwingPoint {
  type: "high" | "low";
  price: number;
  ts: string;
  index: number;
}

interface SupportResistanceResponse {
  symbol: string;
  currentPrice: number;
  lastUpdated: string;
  nearestSupport: number | null;
  nearestResistance: number | null;
  supportDistancePct: number | null;
  resistanceDistancePct: number | null;
  pivotPoints: PivotPoints;
  fibonacci: FibonacciLevels;
  zigzagSwings: SwingPoint[];
  allSupports: number[];
  allResistances: number[];
  priceData: {
    high: number;
    low: number;
    close: number;
    periodHigh: number;
    periodLow: number;
  };
}

// Calculate pivot points from OHLC data
function calculatePivotPoints(high: number, low: number, close: number): PivotPoints {
  const pp = (high + low + close) / 3;
  return {
    PP: Math.round(pp * 100) / 100,
    R1: Math.round((2 * pp - low) * 100) / 100,
    R2: Math.round((pp + (high - low)) * 100) / 100,
    R3: Math.round((high + 2 * (pp - low)) * 100) / 100,
    S1: Math.round((2 * pp - high) * 100) / 100,
    S2: Math.round((pp - (high - low)) * 100) / 100,
    S3: Math.round((low - 2 * (high - pp)) * 100) / 100,
  };
}

// Calculate Fibonacci retracement levels
function calculateFibonacci(
  prices: number[],
  lookback: number = 50
): FibonacciLevels {
  const recentPrices = prices.slice(-lookback);
  const rangeHigh = Math.max(...recentPrices);
  const rangeLow = Math.min(...recentPrices);
  const diff = rangeHigh - rangeLow;

  // Determine trend
  const firstPrice = recentPrices[0];
  const lastPrice = recentPrices[recentPrices.length - 1];
  const trend = lastPrice > firstPrice ? "uptrend" : "downtrend";

  const fibRatios = {
    "0.0": 0.0,
    "23.6": 0.236,
    "38.2": 0.382,
    "50.0": 0.5,
    "61.8": 0.618,
    "78.6": 0.786,
    "100.0": 1.0,
  };

  const levels: Record<string, number> = {};
  for (const [name, ratio] of Object.entries(fibRatios)) {
    if (trend === "uptrend") {
      levels[name] = Math.round((rangeHigh - diff * ratio) * 100) / 100;
    } else {
      levels[name] = Math.round((rangeLow + diff * ratio) * 100) / 100;
    }
  }

  return {
    ...levels,
    trend,
    rangeHigh: Math.round(rangeHigh * 100) / 100,
    rangeLow: Math.round(rangeLow * 100) / 100,
  } as FibonacciLevels;
}

// Calculate ZigZag swing points
function calculateZigZag(
  prices: number[],
  timestamps: string[],
  thresholdPct: number = 5
): SwingPoint[] {
  if (prices.length < 3) return [];

  const swings: SwingPoint[] = [];
  let lastPivotIdx = 0;
  let lastPivotPrice = prices[0];
  let direction = 0; // 1 = up, -1 = down

  // Find initial direction
  for (let i = 1; i < Math.min(prices.length, 20); i++) {
    const pctChange = ((prices[i] - lastPivotPrice) / lastPivotPrice) * 100;
    if (Math.abs(pctChange) >= thresholdPct) {
      direction = pctChange > 0 ? 1 : -1;
      break;
    }
  }

  if (direction === 0) {
    direction = prices[prices.length - 1] > prices[0] ? 1 : -1;
  }

  // Process each bar
  for (let i = 1; i < prices.length; i++) {
    const pctChange = ((prices[i] - lastPivotPrice) / lastPivotPrice) * 100;

    if (direction === 1) {
      if (prices[i] > lastPivotPrice) {
        lastPivotPrice = prices[i];
        lastPivotIdx = i;
      } else if (pctChange <= -thresholdPct) {
        swings.push({
          type: "high",
          price: Math.round(lastPivotPrice * 100) / 100,
          ts: timestamps[lastPivotIdx],
          index: lastPivotIdx,
        });
        direction = -1;
        lastPivotPrice = prices[i];
        lastPivotIdx = i;
      }
    } else {
      if (prices[i] < lastPivotPrice) {
        lastPivotPrice = prices[i];
        lastPivotIdx = i;
      } else if (pctChange >= thresholdPct) {
        swings.push({
          type: "low",
          price: Math.round(lastPivotPrice * 100) / 100,
          ts: timestamps[lastPivotIdx],
          index: lastPivotIdx,
        });
        direction = 1;
        lastPivotPrice = prices[i];
        lastPivotIdx = i;
      }
    }
  }

  // Add last pivot
  swings.push({
    type: direction === 1 ? "high" : "low",
    price: Math.round(lastPivotPrice * 100) / 100,
    ts: timestamps[lastPivotIdx],
    index: lastPivotIdx,
  });

  return swings;
}

serve(async (req: Request): Promise<Response> => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return handleCorsOptions();
  }

  // Only allow GET requests
  if (req.method !== "GET") {
    return errorResponse("Method not allowed", 405);
  }

  try {
    const url = new URL(req.url);
    const symbol = url.searchParams.get("symbol");
    const lookback = parseInt(url.searchParams.get("lookback") || "100");
    const zigzagThreshold = parseFloat(url.searchParams.get("threshold") || "5");

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
    const { data: ohlcData, error: ohlcError } = await supabase
      .from("ohlc_1d")
      .select("ts, open, high, low, close, volume")
      .eq("symbol_id", symbolData.id)
      .order("ts", { ascending: true })
      .limit(lookback);

    if (ohlcError) {
      console.error("[support-resistance] OHLC query error:", ohlcError);
      return errorResponse(`Database error: ${ohlcError.message}`, 500);
    }

    if (!ohlcData || ohlcData.length < 5) {
      return errorResponse(`Insufficient data for ${symbol}`, 400);
    }

    // Extract price arrays
    const closes = ohlcData.map((d) => d.close);
    const highs = ohlcData.map((d) => d.high);
    const lows = ohlcData.map((d) => d.low);
    const timestamps = ohlcData.map((d) => d.ts);

    const lastBar = ohlcData[ohlcData.length - 1];
    const currentPrice = lastBar.close;
    const periodHigh = Math.max(...highs);
    const periodLow = Math.min(...lows);

    // Calculate pivot points (from last bar)
    const pivotPoints = calculatePivotPoints(
      lastBar.high,
      lastBar.low,
      lastBar.close
    );

    // Calculate Fibonacci levels
    const fibonacci = calculateFibonacci(closes, Math.min(50, closes.length));

    // Calculate ZigZag swings
    const zigzagSwings = calculateZigZag(closes, timestamps, zigzagThreshold);

    // Collect all support and resistance levels
    const allSupports: number[] = [];
    const allResistances: number[] = [];

    // From pivot points
    allSupports.push(pivotPoints.S1, pivotPoints.S2, pivotPoints.S3);
    allResistances.push(pivotPoints.R1, pivotPoints.R2, pivotPoints.R3);

    // From ZigZag
    for (const swing of zigzagSwings) {
      if (swing.type === "low" && swing.price < currentPrice) {
        allSupports.push(swing.price);
      } else if (swing.type === "high" && swing.price > currentPrice) {
        allResistances.push(swing.price);
      }
    }

    // From Fibonacci
    for (const [_, level] of Object.entries(fibonacci)) {
      if (typeof level === "number") {
        if (level < currentPrice) {
          allSupports.push(level);
        } else if (level > currentPrice) {
          allResistances.push(level);
        }
      }
    }

    // Sort and deduplicate
    const uniqueSupports = [...new Set(allSupports)]
      .filter((s) => s < currentPrice)
      .sort((a, b) => b - a);
    const uniqueResistances = [...new Set(allResistances)]
      .filter((r) => r > currentPrice)
      .sort((a, b) => a - b);

    // Find nearest levels
    const nearestSupport = uniqueSupports[0] || null;
    const nearestResistance = uniqueResistances[0] || null;

    // Calculate distances
    const supportDistancePct = nearestSupport
      ? Math.round(((currentPrice - nearestSupport) / currentPrice) * 10000) / 100
      : null;
    const resistanceDistancePct = nearestResistance
      ? Math.round(((nearestResistance - currentPrice) / currentPrice) * 10000) / 100
      : null;

    const response: SupportResistanceResponse = {
      symbol: symbolData.ticker,
      currentPrice: Math.round(currentPrice * 100) / 100,
      lastUpdated: lastBar.ts,
      nearestSupport,
      nearestResistance,
      supportDistancePct,
      resistanceDistancePct,
      pivotPoints,
      fibonacci,
      zigzagSwings: zigzagSwings.slice(-10), // Last 10 swings
      allSupports: uniqueSupports.slice(0, 5),
      allResistances: uniqueResistances.slice(0, 5),
      priceData: {
        high: lastBar.high,
        low: lastBar.low,
        close: lastBar.close,
        periodHigh: Math.round(periodHigh * 100) / 100,
        periodLow: Math.round(periodLow * 100) / 100,
      },
    };

    // Store S/R levels in database
    const { error: insertError } = await supabase
      .from("sr_levels")
      .upsert({
        symbol_id: symbolData.id,
        timeframe: "1d",
        current_price: currentPrice,
        pivot_pp: pivotPoints.PP,
        pivot_r1: pivotPoints.R1,
        pivot_r2: pivotPoints.R2,
        pivot_r3: pivotPoints.R3,
        pivot_s1: pivotPoints.S1,
        pivot_s2: pivotPoints.S2,
        pivot_s3: pivotPoints.S3,
        fib_trend: fibonacci.trend,
        fib_range_high: fibonacci.rangeHigh,
        fib_range_low: fibonacci.rangeLow,
        fib_0: fibonacci["0.0"],
        fib_236: fibonacci["23.6"],
        fib_382: fibonacci["38.2"],
        fib_500: fibonacci["50.0"],
        fib_618: fibonacci["61.8"],
        fib_786: fibonacci["78.6"],
        fib_100: fibonacci["100.0"],
        nearest_support: nearestSupport,
        nearest_resistance: nearestResistance,
        support_distance_pct: supportDistancePct,
        resistance_distance_pct: resistanceDistancePct,
        sr_ratio: nearestSupport && nearestResistance
          ? (nearestResistance - currentPrice) / (currentPrice - nearestSupport)
          : null,
        zigzag_swings: zigzagSwings,
        all_supports: uniqueSupports.slice(0, 10),
        all_resistances: uniqueResistances.slice(0, 10),
        period_high: periodHigh,
        period_low: periodLow,
        lookback_bars: lookback,
        computed_at: new Date().toISOString(),
      }, {
        onConflict: "symbol_id,timeframe,DATE(computed_at)",
        ignoreDuplicates: false,
      });

    if (insertError) {
      console.warn("[support-resistance] Failed to store S/R levels:", insertError.message);
    } else {
      console.log(`[support-resistance] Stored S/R levels for ${symbol}`);
    }

    console.log(
      `[support-resistance] ${symbol}: price=${currentPrice}, ` +
      `support=${nearestSupport}, resistance=${nearestResistance}`
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
