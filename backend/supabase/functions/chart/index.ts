// chart: Fetch OHLC candle data for a symbol via ProviderRouter
// GET /chart?symbol=AAPL&timeframe=d1
//
// Uses the unified ProviderRouter with rate limiting, caching, and fallback logic.
// DB persistence is used for long-term storage; ProviderRouter handles live fetching.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";
import { getProviderRouter } from "../_shared/providers/factory.ts";
import type { Timeframe } from "../_shared/providers/types.ts";

// Cache staleness threshold (15 minutes)
const CACHE_TTL_MS = 15 * 60 * 1000;

const VALID_TIMEFRAMES: Timeframe[] = ["m1", "m5", "m15", "m30", "h1", "h4", "d1", "w1", "mn1"];

function isValidTimeframe(value: string): value is Timeframe {
  return VALID_TIMEFRAMES.includes(value as Timeframe);
}

interface ChartResponse {
  symbol: string;
  assetType: string;
  timeframe: string;
  bars: {
    ts: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }[];
}

interface SymbolRecord {
  id: string;
  ticker: string;
  asset_type: string;
}

interface OHLCRecord {
  ts: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
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
    // Parse query parameters
    const url = new URL(req.url);
    const symbol = url.searchParams.get("symbol");
    const timeframe = url.searchParams.get("timeframe") || "d1";

    if (!symbol || symbol.trim().length === 0) {
      return errorResponse("Missing required parameter: symbol", 400);
    }

    if (!isValidTimeframe(timeframe)) {
      return errorResponse(
        `Invalid timeframe. Must be one of: ${VALID_TIMEFRAMES.join(", ")}`,
        400
      );
    }

    const ticker = symbol.trim().toUpperCase();
    const supabase = getSupabaseClient();

    // 1. Look up symbol in database
    const { data: symbolData, error: symbolError } = await supabase
      .from("symbols")
      .select("id, ticker, asset_type")
      .eq("ticker", ticker)
      .single();

    if (symbolError || !symbolData) {
      return errorResponse(`Symbol not found: ${ticker}`, 404);
    }

    const symbolRecord = symbolData as SymbolRecord;
    const symbolId = symbolRecord.id;
    const assetType = symbolRecord.asset_type;

    // 2. Check for cached data
    // For intraday timeframes, request more bars to account for market hours filtering
    const isIntradayTimeframe = ["m1", "m5", "m15", "m30", "h1", "h4"].includes(timeframe);
    const cacheLimit = isIntradayTimeframe ? 300 : 100;

    const { data: cachedBars, error: cacheError } = await supabase
      .from("ohlc_bars")
      .select("ts, open, high, low, close, volume")
      .eq("symbol_id", symbolId)
      .eq("timeframe", timeframe)
      .order("ts", { ascending: true })
      .limit(cacheLimit);

    if (cacheError) {
      console.error("Cache query error:", cacheError);
    }

    // 3. Determine if cache is fresh
    let bars: OHLCBar[] = [];
    let cacheIsFresh = false;

    if (cachedBars && cachedBars.length > 0) {
      // Check if most recent bar is within TTL
      const latestBar = cachedBars[cachedBars.length - 1] as OHLCRecord;
      const latestTs = new Date(latestBar.ts).getTime();
      const now = Date.now();

      cacheIsFresh = (now - latestTs) < CACHE_TTL_MS;

      if (cacheIsFresh) {
        console.log(`Cache hit for ${ticker} ${timeframe} (${cachedBars.length} bars)`);

        // Filter cached bars to market hours for intraday timeframes
        const isIntraday = ["m1", "m5", "m15", "m30", "h1", "h4"].includes(timeframe);
        let filteredCachedBars = cachedBars;

        if (isIntraday) {
          filteredCachedBars = cachedBars.filter((bar) => {
            const date = new Date(bar.ts);
            const utcHours = date.getUTCHours();
            const utcMinutes = date.getUTCMinutes();

            // Determine DST offset
            const month = date.getUTCMonth();
            const isDST = month >= 2 && month <= 10;
            const offset = isDST ? 4 : 5;

            // Convert to ET
            const etHours = (utcHours - offset + 24) % 24;
            const etTotalMinutes = etHours * 60 + utcMinutes;

            // Market hours: 9:30 AM - 4:00 PM ET
            const marketOpen = 9 * 60 + 30;
            const marketClose = 16 * 60;

            return etTotalMinutes >= marketOpen && etTotalMinutes < marketClose;
          });

          console.log(`[Chart] Filtered cached to ${filteredCachedBars.length} market-hours bars (from ${cachedBars.length} total)`);
        }

        bars = filteredCachedBars.map((bar) => ({
          ts: bar.ts,
          open: Number(bar.open),
          high: Number(bar.high),
          low: Number(bar.low),
          close: Number(bar.close),
          volume: Number(bar.volume),
        }));
      }
    }

    // 4. If cache is stale or empty, fetch via ProviderRouter
    if (!cacheIsFresh) {
      console.log(`Cache miss for ${ticker} ${timeframe}, fetching via ProviderRouter`);

      try {
        const router = getProviderRouter();

        // Calculate time range based on timeframe
        // For intraday: request more data to account for market hours filtering
        // Market hours = 6.5 hours/day, so we need ~3.7x more calendar time to get same number of bars
        const now = Math.floor(Date.now() / 1000);
        const timeframeSeconds: Record<Timeframe, number> = {
          m1: 60,
          m5: 5 * 60,
          m15: 15 * 60,
          m30: 30 * 60,
          h1: 60 * 60,
          h4: 4 * 60 * 60,
          d1: 24 * 60 * 60,
          w1: 7 * 24 * 60 * 60,
          mn1: 30 * 24 * 60 * 60,
        };
        const secondsPerBar = timeframeSeconds[timeframe];

        // For intraday timeframes, request more bars to compensate for filtering
        const isIntraday = ["m1", "m5", "m15", "m30", "h1", "h4"].includes(timeframe);
        const barsToRequest = isIntraday ? 300 : 100; // Request 300 bars for intraday to get ~100 market-hours bars
        const from = now - (barsToRequest * secondsPerBar);

        const freshBars = await router.getHistoricalBars({
          symbol: ticker,
          timeframe: timeframe,
          start: from,
          end: now,
        });

        console.log(`[Chart] Received ${freshBars.length} bars from provider`);

        // Filter to regular market hours for intraday timeframes (9:30 AM - 4:00 PM ET)
        let marketHoursBars = freshBars;
        if (isIntraday) {
          marketHoursBars = freshBars.filter((bar) => {
            const date = new Date(bar.timestamp);

            // Get ET time components
            // Note: This is a simplified approach. For production, consider using a proper timezone library
            // EST is UTC-5, EDT is UTC-4. The market uses ET year-round.
            const utcHours = date.getUTCHours();
            const utcMinutes = date.getUTCMinutes();

            // Determine if we're in EDT (roughly March-November) or EST
            const month = date.getUTCMonth(); // 0-11
            const isDST = month >= 2 && month <= 10; // Approximate DST months (March-November)
            const offset = isDST ? 4 : 5; // EDT = UTC-4, EST = UTC-5

            // Convert to ET
            const etHours = (utcHours - offset + 24) % 24;
            const etMinutes = utcMinutes;
            const etTotalMinutes = etHours * 60 + etMinutes;

            // Market hours: 9:30 AM (570 minutes) to 4:00 PM (960 minutes) ET
            const marketOpen = 9 * 60 + 30;  // 9:30 AM
            const marketClose = 16 * 60;     // 4:00 PM

            return etTotalMinutes >= marketOpen && etTotalMinutes < marketClose;
          });

          console.log(`[Chart] Filtered to ${marketHoursBars.length} market-hours bars (from ${freshBars.length} total)`);
        }

        if (marketHoursBars.length > 0) {
          // 5. Upsert bars into database
          const barsToInsert = freshBars.map((bar) => ({
            symbol_id: symbolId,
            timeframe: timeframe,
            ts: new Date(bar.timestamp).toISOString(),
            open: bar.open,
            high: bar.high,
            low: bar.low,
            close: bar.close,
            volume: bar.volume,
            provider: "router", // Using router (could be finnhub or massive)
          }));

          const { error: upsertError } = await supabase
            .from("ohlc_bars")
            .upsert(barsToInsert, {
              onConflict: "symbol_id,timeframe,ts",
              ignoreDuplicates: false,
            });

          if (upsertError) {
            console.error("Upsert error:", upsertError);
            // Continue with fresh data even if upsert fails
          } else {
            console.log(`Cached ${freshBars.length} bars for ${ticker} ${timeframe}`);
          }

          // Convert router Bar format to response format (use filtered bars for intraday)
          bars = marketHoursBars.map((bar) => ({
            ts: new Date(bar.timestamp).toISOString(),
            open: bar.open,
            high: bar.high,
            low: bar.low,
            close: bar.close,
            volume: bar.volume,
          }));
        } else if (cachedBars && cachedBars.length > 0) {
          // No fresh data, fall back to stale cache
          console.log(`No fresh data, using stale cache for ${ticker} ${timeframe}`);
          bars = cachedBars.map((bar) => ({
            ts: bar.ts,
            open: Number(bar.open),
            high: Number(bar.high),
            low: Number(bar.low),
            close: Number(bar.close),
            volume: Number(bar.volume),
          }));
        }
      } catch (fetchError) {
        console.error("Provider router error:", fetchError);

        // Fall back to stale cache if available
        if (cachedBars && cachedBars.length > 0) {
          console.log(`Provider error, using stale cache for ${ticker} ${timeframe}`);
          bars = cachedBars.map((bar) => ({
            ts: bar.ts,
            open: Number(bar.open),
            high: Number(bar.high),
            low: Number(bar.low),
            close: Number(bar.close),
            volume: Number(bar.volume),
          }));
        } else {
          return errorResponse("Failed to fetch market data", 502);
        }
      }
    }

    // 6. Return response
    const response: ChartResponse = {
      symbol: ticker,
      assetType: assetType,
      timeframe: timeframe,
      bars: bars,
    };

    return jsonResponse(response);
  } catch (err) {
    console.error("Unexpected error:", err);
    return errorResponse("Internal server error", 500);
  }
});
