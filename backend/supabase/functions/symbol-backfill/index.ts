// symbol-backfill: Deep backfill OHLC data for a symbol using Polygon API
// POST /symbol-backfill { symbol, timeframes?, force? }
//
// Triggered when a symbol is added to a watchlist to ensure historical data is available.
// Uses Polygon (Massive) API for maximum historical data (2+ years for daily).

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

const POLYGON_API_KEY = Deno.env.get("MASSIVE_API_KEY") || Deno.env.get("POLYGON_API_KEY");
const POLYGON_BASE_URL = "https://api.polygon.io";

// Timeframe configurations: how much history to fetch
const TIMEFRAME_CONFIG: Record<string, { multiplier: number; timespan: string; maxDays: number }> = {
  m15: { multiplier: 15, timespan: "minute", maxDays: 60 },
  h1: { multiplier: 1, timespan: "hour", maxDays: 180 },
  h4: { multiplier: 4, timespan: "hour", maxDays: 365 },
  d1: { multiplier: 1, timespan: "day", maxDays: 730 },  // 2 years
  w1: { multiplier: 1, timespan: "week", maxDays: 1825 }, // 5 years
};

// Default timeframes to backfill (most important first)
const DEFAULT_TIMEFRAMES = ["d1", "h1", "w1"];

interface BackfillRequest {
  symbol: string;
  timeframes?: string[];
  force?: boolean;
}

interface BackfillResult {
  timeframe: string;
  barsInserted: number;
  earliest?: string;
  latest?: string;
  error?: string;
}

interface BackfillResponse {
  symbol: string;
  results: BackfillResult[];
  totalBars: number;
  durationMs: number;
}

async function fetchPolygonBars(
  symbol: string,
  timeframe: string,
  startDate: Date,
  endDate: Date
): Promise<{ ts: string; open: number; high: number; low: number; close: number; volume: number }[]> {
  const config = TIMEFRAME_CONFIG[timeframe];
  if (!config) {
    throw new Error(`Invalid timeframe: ${timeframe}`);
  }

  const { multiplier, timespan } = config;

  // Format dates based on timespan
  let fromStr: string;
  let toStr: string;
  if (timespan === "day" || timespan === "week" || timespan === "month") {
    fromStr = startDate.toISOString().split("T")[0];
    toStr = endDate.toISOString().split("T")[0];
  } else {
    fromStr = startDate.getTime().toString();
    toStr = endDate.getTime().toString();
  }

  const url = new URL(
    `${POLYGON_BASE_URL}/v2/aggs/ticker/${symbol.toUpperCase()}/range/${multiplier}/${timespan}/${fromStr}/${toStr}`
  );
  url.searchParams.set("adjusted", "false"); // Use unadjusted prices for accurate historical data
  url.searchParams.set("sort", "asc");
  url.searchParams.set("limit", "50000");
  url.searchParams.set("apiKey", POLYGON_API_KEY!);

  console.log(`[SymbolBackfill] Fetching ${symbol} ${timeframe} from ${fromStr} to ${toStr}`);

  const response = await fetch(url.toString());
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Polygon API error: ${response.status} - ${text}`);
  }

  const data = await response.json();

  if (data.status === "ERROR") {
    throw new Error(`Polygon API error: ${JSON.stringify(data)}`);
  }

  const results = data.results || [];
  console.log(`[SymbolBackfill] Received ${results.length} bars for ${symbol} ${timeframe}`);

  // Transform to our format
  return results.map((r: { t: number; o: number; h: number; l: number; c: number; v: number }) => ({
    ts: new Date(r.t).toISOString(),
    open: r.o,
    high: r.h,
    low: r.l,
    close: r.c,
    volume: r.v,
  }));
}

async function getExistingCoverage(
  supabase: ReturnType<typeof getSupabaseClient>,
  symbolId: string,
  timeframe: string
): Promise<{ count: number; latest: Date | null }> {
  const { data, error } = await supabase
    .from("ohlc_bars")
    .select("ts")
    .eq("symbol_id", symbolId)
    .eq("timeframe", timeframe)
    .order("ts", { ascending: false })
    .limit(1);

  if (error || !data || data.length === 0) {
    return { count: 0, latest: null };
  }

  // Get count
  const { count } = await supabase
    .from("ohlc_bars")
    .select("id", { count: "exact", head: true })
    .eq("symbol_id", symbolId)
    .eq("timeframe", timeframe);

  return {
    count: count || 0,
    latest: new Date(data[0].ts),
  };
}

async function backfillTimeframe(
  supabase: ReturnType<typeof getSupabaseClient>,
  symbol: string,
  symbolId: string,
  timeframe: string,
  force: boolean
): Promise<BackfillResult> {
  const config = TIMEFRAME_CONFIG[timeframe];
  if (!config) {
    return { timeframe, barsInserted: 0, error: `Invalid timeframe: ${timeframe}` };
  }

  try {
    // Check existing coverage
    const coverage = await getExistingCoverage(supabase, symbolId, timeframe);
    console.log(`[SymbolBackfill] ${symbol} ${timeframe}: ${coverage.count} existing bars, latest=${coverage.latest?.toISOString()}`);

    // Skip if we have recent data and not forcing
    if (!force && coverage.latest) {
      const ageMs = Date.now() - coverage.latest.getTime();
      const maxAgeMs = timeframe === "d1" ? 24 * 60 * 60 * 1000 : 4 * 60 * 60 * 1000;
      if (ageMs < maxAgeMs && coverage.count >= 100) {
        console.log(`[SymbolBackfill] ${symbol} ${timeframe}: Data is current, skipping`);
        return {
          timeframe,
          barsInserted: 0,
          earliest: coverage.latest.toISOString(),
          latest: coverage.latest.toISOString(),
        };
      }
    }

    // Calculate date range
    const endDate = new Date();
    const startDate = new Date(endDate.getTime() - config.maxDays * 24 * 60 * 60 * 1000);

    // Fetch from Polygon
    const bars = await fetchPolygonBars(symbol, timeframe, startDate, endDate);

    if (bars.length === 0) {
      return { timeframe, barsInserted: 0, error: "No data returned from Polygon" };
    }

    // Upsert to database
    const barsToInsert = bars.map((bar) => ({
      symbol_id: symbolId,
      timeframe,
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
      });

    if (upsertError) {
      console.error(`[SymbolBackfill] Upsert error for ${symbol} ${timeframe}:`, upsertError);
      return { timeframe, barsInserted: 0, error: upsertError.message };
    }

    console.log(`[SymbolBackfill] Inserted ${bars.length} bars for ${symbol} ${timeframe}`);

    return {
      timeframe,
      barsInserted: bars.length,
      earliest: bars[0].ts,
      latest: bars[bars.length - 1].ts,
    };
  } catch (error) {
    console.error(`[SymbolBackfill] Error for ${symbol} ${timeframe}:`, error);
    return {
      timeframe,
      barsInserted: 0,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

serve(async (req: Request): Promise<Response> => {
  if (req.method === "OPTIONS") {
    return handleCorsOptions();
  }

  if (req.method !== "POST") {
    return errorResponse("Method not allowed", 405);
  }

  // Check API key
  if (!POLYGON_API_KEY) {
    return errorResponse("MASSIVE_API_KEY not configured", 500);
  }

  const startTime = Date.now();

  try {
    const body: BackfillRequest = await req.json();
    const { symbol, timeframes = DEFAULT_TIMEFRAMES, force = false } = body;

    if (!symbol || symbol.trim().length === 0) {
      return errorResponse("Missing required field: symbol", 400);
    }

    const ticker = symbol.trim().toUpperCase();
    const supabase = getSupabaseClient();

    // 1. Look up or create symbol
    let symbolId: string;
    const { data: symbolData, error: symbolError } = await supabase
      .from("symbols")
      .select("id")
      .eq("ticker", ticker)
      .single();

    if (symbolError || !symbolData) {
      // Create symbol if it doesn't exist
      const { data: newSymbol, error: createError } = await supabase
        .from("symbols")
        .insert({
          ticker,
          asset_type: "stock",
          description: ticker,
        })
        .select("id")
        .single();

      if (createError || !newSymbol) {
        return errorResponse(`Failed to create symbol: ${ticker}`, 500);
      }

      symbolId = newSymbol.id;
      console.log(`[SymbolBackfill] Created new symbol: ${ticker} (${symbolId})`);
    } else {
      symbolId = symbolData.id;
    }

    // 2. Backfill each timeframe
    const results: BackfillResult[] = [];
    let totalBars = 0;

    for (const tf of timeframes) {
      if (!TIMEFRAME_CONFIG[tf]) {
        results.push({ timeframe: tf, barsInserted: 0, error: `Invalid timeframe: ${tf}` });
        continue;
      }

      const result = await backfillTimeframe(supabase, ticker, symbolId, tf, force);
      results.push(result);
      totalBars += result.barsInserted;

      // Rate limiting: Polygon free tier = 5 req/min
      // Wait 12 seconds between timeframes to stay under limit
      if (timeframes.indexOf(tf) < timeframes.length - 1) {
        console.log(`[SymbolBackfill] Rate limit delay (12s)...`);
        await new Promise((resolve) => setTimeout(resolve, 12000));
      }
    }

    const response: BackfillResponse = {
      symbol: ticker,
      results,
      totalBars,
      durationMs: Date.now() - startTime,
    };

    console.log(`[SymbolBackfill] Complete for ${ticker}: ${totalBars} total bars in ${response.durationMs}ms`);

    return jsonResponse(response);
  } catch (err) {
    console.error("[SymbolBackfill] Error:", err);
    return errorResponse("Internal server error", 500);
  }
});
