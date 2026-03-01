// technical-indicators: Get technical indicators for a symbol/timeframe
// GET /technical-indicators?symbol=AAPL&timeframe=d1
//
// Calls Python script to calculate all technical indicators and returns JSON.
// Caches results for 5 minutes (intraday) or 1 hour (daily+).

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { corsResponse, handlePreflight } from "../_shared/cors.ts";
import { callFastApi } from "../_shared/fastapi-client.ts";
import { MemoryCache } from "../_shared/cache/memory-cache.ts";

const CACHE_DURATION_INTRADAY = 5 * 60; // 5 minutes for intraday (seconds)
const CACHE_DURATION_DAILY = 60 * 60; // 1 hour for daily+ (seconds)

// Module-level in-memory cache shared across requests within the same isolate
const indicatorCache = new MemoryCache();

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
 * Call FastAPI to calculate indicators
 */
async function calculateIndicators(
  symbol: string,
  timeframe: string,
): Promise<TechnicalIndicatorsResponse> {
  const endpoint = `/api/v1/technical-indicators?symbol=${
    encodeURIComponent(symbol)
  }&timeframe=${encodeURIComponent(timeframe)}&lookback=500`;
  return await callFastApi<TechnicalIndicatorsResponse>(endpoint, {
    method: "GET",
  });
}

/**
 * Get cached indicators from in-memory cache
 */
async function getCachedIndicators(
  symbol: string,
  timeframe: string,
): Promise<TechnicalIndicatorsResponse | null> {
  const key = `${symbol}:${timeframe}`;
  return (await indicatorCache.get<TechnicalIndicatorsResponse>(key)) ?? null;
}

/**
 * Store indicators in in-memory cache with timeframe-appropriate TTL
 */
function setCachedIndicators(
  symbol: string,
  timeframe: string,
  data: TechnicalIndicatorsResponse,
): void {
  const key = `${symbol}:${timeframe}`;
  const ttlSeconds = isIntraday(timeframe)
    ? CACHE_DURATION_INTRADAY
    : CACHE_DURATION_DAILY;
  indicatorCache.set(key, data, ttlSeconds);
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
        origin,
      );
    }

    // Validate timeframe
    const validTimeframes = ["m15", "m30", "h1", "h4", "d1", "w1"];
    if (!validTimeframes.includes(timeframe)) {
      return corsResponse(
        {
          error: `Invalid timeframe: ${timeframe}. Valid: ${
            validTimeframes.join(", ")
          }`,
        },
        400,
        origin,
      );
    }

    console.log(
      `[TechnicalIndicators] Fetching indicators for ${symbol}/${timeframe}`,
    );

    // Try to get from cache first
    const cached = await getCachedIndicators(symbol, timeframe);

    if (cached) {
      console.log(
        `[TechnicalIndicators] Returning cached result for ${symbol}/${timeframe}`,
      );
      return corsResponse({ ...cached, cached: true }, 200, origin);
    }

    // Calculate indicators
    const result = await calculateIndicators(symbol, timeframe);

    if (result.error) {
      return corsResponse(
        { error: result.error, symbol, timeframe },
        500,
        origin,
      );
    }

    console.log(
      `[TechnicalIndicators] Calculated ${
        Object.keys(result.indicators).length
      } indicators for ${symbol}/${timeframe}`,
    );

    // Persist result in in-memory cache for subsequent requests
    setCachedIndicators(symbol, timeframe, result);

    return corsResponse(result, 200, origin);
  } catch (error) {
    console.error("[TechnicalIndicators] Error:", error);
    return corsResponse(
      {
        error: error instanceof Error ? error.message : "Internal server error",
      },
      500,
      origin,
    );
  }
});
