// technical-indicators: Get technical indicators for a symbol/timeframe
// GET /technical-indicators?symbol=AAPL&timeframe=d1
//
// Calls Python script to calculate all technical indicators and returns JSON.
// Caches results for 5 minutes (intraday) or 1 hour (daily+).

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { corsResponse, handlePreflight } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

const CACHE_DURATION_INTRADAY = 5 * 60; // 5 minutes for intraday
const CACHE_DURATION_DAILY = 60 * 60; // 1 hour for daily+

/**
 * Get Python script path from environment or use default
 * In production, this should point to a deployed script or FastAPI endpoint
 */
function getPythonScriptPath(): string {
  return (
    Deno.env.get("TECHNICAL_INDICATORS_SCRIPT_PATH") ||
    "/Users/ericpeterson/SwiftBolt_ML/ml/scripts/get_technical_indicators.py"
  );
}

interface TechnicalIndicatorsResponse {
  symbol: string;
  timeframe: string;
  timestamp: string;
  indicators: Record<string, number | null>;
  price: {
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  };
  bars_used: number;
  cached?: boolean;
  error?: string;
}

/**
 * Check if timeframe is intraday (needs shorter cache)
 */
function isIntraday(timeframe: string): boolean {
  return timeframe.startsWith("m") || timeframe === "h1" || timeframe === "h4";
}

/**
 * Get cache key for symbol/timeframe
 */
function getCacheKey(symbol: string, timeframe: string): string {
  return `indicators:${symbol}:${timeframe}`;
}

/**
 * Call Python script to calculate indicators
 */
async function calculateIndicators(
  symbol: string,
  timeframe: string
): Promise<TechnicalIndicatorsResponse> {
  const scriptPath = getPythonScriptPath();
  const pythonCmd = new Deno.Command("python3", {
    args: [
      scriptPath,
      "--symbol",
      symbol,
      "--timeframe",
      timeframe,
      "--lookback",
      "500",
    ],
    stdout: "piped",
    stderr: "piped",
  });

  try {
    const { code, stdout, stderr } = await pythonCmd.output();

    if (code !== 0) {
      const errorText = new TextDecoder().decode(stderr);
      console.error(`Python script error: ${errorText}`);
      throw new Error(`Python script failed: ${errorText}`);
    }

    const output = new TextDecoder().decode(stdout);
    const result = JSON.parse(output) as TechnicalIndicatorsResponse;

    if (result.error) {
      throw new Error(result.error);
    }

    return result;
  } catch (error) {
    console.error(`Error running Python script: ${error}`);
    throw error;
  }
}

/**
 * Get cached indicators from database
 */
async function getCachedIndicators(
  supabase: ReturnType<typeof getSupabaseClient>,
  symbol: string,
  timeframe: string
): Promise<TechnicalIndicatorsResponse | null> {
  const cacheKey = getCacheKey(symbol, timeframe);
  const cacheDuration = isIntraday(timeframe)
    ? CACHE_DURATION_INTRADAY
    : CACHE_DURATION_DAILY;

  // For now, we'll skip database caching and just use in-memory cache
  // TODO: Implement Redis or database caching if needed
  return null;
}

serve(async (req: Request) => {
  const origin = req.headers.get("origin");

  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return handlePreflight(origin);
  }

  try {
    const url = new URL(req.url);
    const symbol = url.searchParams.get("symbol")?.toUpperCase();
    const timeframe = url.searchParams.get("timeframe") || "d1";

    if (!symbol) {
      return corsResponse(
        { error: "Missing required parameter: symbol" },
        400,
        origin
      );
    }

    // Validate timeframe
    const validTimeframes = ["m15", "m30", "h1", "h4", "d1", "w1"];
    if (!validTimeframes.includes(timeframe)) {
      return corsResponse(
        {
          error: `Invalid timeframe: ${timeframe}. Valid: ${validTimeframes.join(", ")}`,
        },
        400,
        origin
      );
    }

    console.log(`[TechnicalIndicators] Fetching indicators for ${symbol}/${timeframe}`);

    // Try to get from cache first
    const supabase = getSupabaseClient();
    const cached = await getCachedIndicators(supabase, symbol, timeframe);

    if (cached) {
      console.log(`[TechnicalIndicators] Returning cached result for ${symbol}/${timeframe}`);
      return corsResponse({ ...cached, cached: true }, 200, origin);
    }

    // Calculate indicators
    const result = await calculateIndicators(symbol, timeframe);

    if (result.error) {
      return corsResponse(
        { error: result.error, symbol, timeframe },
        500,
        origin
      );
    }

    console.log(
      `[TechnicalIndicators] Calculated ${Object.keys(result.indicators).length} indicators for ${symbol}/${timeframe}`
    );

    return corsResponse(result, 200, origin);
  } catch (error) {
    console.error("[TechnicalIndicators] Error:", error);
    return corsResponse(
      {
        error: error instanceof Error ? error.message : "Internal server error",
      },
      500,
      origin
    );
  }
});
