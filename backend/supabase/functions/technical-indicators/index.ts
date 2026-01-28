import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";

/**
 * Technical Indicators Edge Function with Caching
 *
 * Caches technical indicators in Supabase to avoid expensive recalculations.
 * First request: slow (calls FastAPI), cached requests: fast (~50ms)
 *
 * Query parameters:
 * - symbol: Stock ticker symbol (required)
 * - timeframe: d1, h1, m15, etc. (default: d1)
 * - lookback: Number of bars to fetch (default: 500)
 * - force: Force recalculation, bypass cache (optional)
 */

declare const Deno: {
  env: {
    get(key: string): string | undefined;
  };
};

interface CachedIndicators {
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
  cached_at: string;
}

const CACHE_TTL_SECONDS = 300; // 5 minutes

serve(async (req: Request): Promise<Response> => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return handleCorsOptions();
  }

  if (req.method !== "GET") {
    return errorResponse("Method not allowed", 405);
  }

  try {
    const url = new URL(req.url);
    const symbol = url.searchParams.get("symbol");
    const timeframe = url.searchParams.get("timeframe") || "d1";
    const lookback = parseInt(url.searchParams.get("lookback") || "500");
    const forceRefresh = url.searchParams.get("force") === "true";

    if (!symbol) {
      return errorResponse("Missing symbol parameter", 400);
    }

    const supabaseUrl = Deno.env.get("SUPABASE_URL");
    const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");

    if (!supabaseUrl || !supabaseKey) {
      return errorResponse("Supabase configuration missing", 500);
    }

    const supabase = createClient(supabaseUrl, supabaseKey);
    const cacheKey = `${symbol.toUpperCase()}_${timeframe}`;

    // 1. Check cache if not forcing refresh
    if (!forceRefresh) {
      console.log(`[TI] Checking cache for ${cacheKey}`);

      const { data: cachedData, error: cacheError } = await supabase
        .from("technical_indicators_cache")
        .select("*")
        .eq("cache_key", cacheKey)
        .single();

      if (!cacheError && cachedData) {
        const cachedAt = new Date(cachedData.cached_at).getTime();
        const ageSeconds = (Date.now() - cachedAt) / 1000;

        if (ageSeconds < CACHE_TTL_SECONDS) {
          console.log(
            `[TI] Cache hit for ${cacheKey} (age: ${ageSeconds.toFixed(1)}s)`
          );
          return jsonResponse({
            ...JSON.parse(cachedData.data),
            cached: true,
            cache_age_seconds: Math.round(ageSeconds),
          });
        } else {
          console.log(
            `[TI] Cache expired for ${cacheKey} (age: ${ageSeconds.toFixed(1)}s)`
          );
        }
      }
    }

    // 2. Cache miss or expired - fetch from FastAPI
    console.log(`[TI] Cache miss/expired for ${cacheKey}, calling FastAPI`);

    const backendUrl = Deno.env.get("ML_BACKEND_URL") || "http://localhost:8000";
    const technicalUrl = new URL(
      `/api/v1/technical-indicators?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}&lookback=${lookback}`,
      backendUrl
    );

    const response = await fetch(technicalUrl.toString(), {
      method: "GET",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error(
        `[TI] FastAPI error: ${response.status} ${errorText.substring(0, 200)}`
      );

      // Try to return stale cache if FastAPI is down
      const { data: staleData } = await supabase
        .from("technical_indicators_cache")
        .select("*")
        .eq("cache_key", cacheKey)
        .single();

      if (staleData) {
        console.log(`[TI] Returning stale cache for ${cacheKey}`);
        return jsonResponse(
          {
            ...JSON.parse(staleData.data),
            cached: true,
            cache_stale: true,
            cache_age_seconds: Math.round(
              (Date.now() - new Date(staleData.cached_at).getTime()) / 1000
            ),
          },
          200
        );
      }

      return errorResponse(
        `FastAPI backend error: ${response.statusText}`,
        response.status
      );
    }

    const data = await response.json();

    // 3. Cache the result
    console.log(`[TI] Caching result for ${cacheKey}`);

    const { error: cacheInsertError } = await supabase
      .from("technical_indicators_cache")
      .upsert(
        {
          cache_key: cacheKey,
          symbol: symbol.toUpperCase(),
          timeframe,
          data: JSON.stringify(data),
          cached_at: new Date().toISOString(),
        },
        { onConflict: "cache_key" }
      );

    if (cacheInsertError) {
      console.warn(`[TI] Failed to cache result: ${cacheInsertError.message}`);
      // Don't fail the request, just return the data without caching
    }

    return jsonResponse({
      ...data,
      cached: false,
    });
  } catch (err) {
    console.error("[TI] Unexpected error:", err);
    return errorResponse(
      `Internal server error: ${err instanceof Error ? err.message : String(err)}`,
      500
    );
  }
});
