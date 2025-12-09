// chart: Fetch OHLC candle data for a symbol
// GET /chart?symbol=AAPL&timeframe=d1

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";
import { fetchCandles, isValidTimeframe, type Timeframe, type OHLCBar } from "../_shared/massive-client.ts";

// Cache staleness threshold (15 minutes)
const CACHE_TTL_MS = 15 * 60 * 1000;

interface ChartResponse {
  symbol: string;
  assetType: string;
  timeframe: string;
  bars: OHLCBar[];
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
        "Invalid timeframe. Must be one of: m15, h1, h4, d1, w1",
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
    const { data: cachedBars, error: cacheError } = await supabase
      .from("ohlc_bars")
      .select("ts, open, high, low, close, volume")
      .eq("symbol_id", symbolId)
      .eq("timeframe", timeframe)
      .order("ts", { ascending: true })
      .limit(100);

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
        bars = cachedBars.map((bar) => ({
          ts: bar.ts,
          open: Number(bar.open),
          high: Number(bar.high),
          low: Number(bar.low),
          close: Number(bar.close),
          volume: Number(bar.volume),
        }));
      }
    }

    // 4. If cache is stale or empty, fetch from Polygon (Massive API)
    if (!cacheIsFresh) {
      console.log(`Cache miss for ${ticker} ${timeframe}, fetching from Polygon`);

      try {
        const freshBars = await fetchCandles(ticker, timeframe as Timeframe, 100);

        if (freshBars.length > 0) {
          // 5. Upsert bars into database
          const barsToInsert = freshBars.map((bar) => ({
            symbol_id: symbolId,
            timeframe: timeframe,
            ts: bar.ts,
            open: bar.open,
            high: bar.high,
            low: bar.low,
            close: bar.close,
            volume: bar.volume,
            provider: "massive",
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

          bars = freshBars;
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
        console.error("Polygon fetch error:", fetchError);

        // Fall back to stale cache if available
        if (cachedBars && cachedBars.length > 0) {
          console.log(`Polygon error, using stale cache for ${ticker} ${timeframe}`);
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
