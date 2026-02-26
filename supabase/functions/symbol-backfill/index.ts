// symbol-backfill: Deep backfill OHLC data for a symbol using Alpaca API
// POST /symbol-backfill { symbol, timeframes?, force? }
//
// Triggered when a symbol is added to a watchlist to ensure historical data is available.
// Uses Alpaca API for maximum historical data (7+ years for daily).

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import {
  errorResponse,
  handleCorsOptions,
  jsonResponse,
} from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

const ALPACA_API_KEY = Deno.env.get("ALPACA_API_KEY");
const ALPACA_API_SECRET = Deno.env.get("ALPACA_API_SECRET");
const ALPACA_BASE_URL = "https://data.alpaca.markets/v2";

// Timeframe configurations: how much history to fetch (Alpaca format)
const TIMEFRAME_CONFIG: Record<string, { alpacaTf: string; maxDays: number }> =
  {
    m15: { alpacaTf: "15Min", maxDays: 60 },
    h1: { alpacaTf: "1Hour", maxDays: 180 },
    h4: { alpacaTf: "4Hour", maxDays: 365 },
    d1: { alpacaTf: "1Day", maxDays: 2555 }, // 7 years
    w1: { alpacaTf: "1Week", maxDays: 2555 }, // 7 years
  };

// Default timeframes to backfill (most important first)
const DEFAULT_TIMEFRAMES = ["d1", "h1", "w1"];

// Rate limiting: Alpaca allows 200 requests/minute
const RATE_LIMIT_DELAY = 300; // 0.3 seconds in ms

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

function getAlpacaHeaders(): Record<string, string> {
  return {
    "APCA-API-KEY-ID": ALPACA_API_KEY!,
    "APCA-API-SECRET-KEY": ALPACA_API_SECRET!,
    "Accept": "application/json",
  };
}

async function fetchAlpacaBars(
  symbol: string,
  timeframe: string,
  startDate: Date,
  endDate: Date,
): Promise<
  {
    ts: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }[]
> {
  const config = TIMEFRAME_CONFIG[timeframe];
  if (!config) {
    throw new Error(`Invalid timeframe: ${timeframe}`);
  }

  const { alpacaTf } = config;

  // Format dates to RFC-3339
  const startStr = startDate.toISOString();
  const endStr = endDate.toISOString();

  console.log(
    `[SymbolBackfill] Fetching ${symbol} ${timeframe} from ${startStr} to ${endStr}`,
  );

  const allBars: {
    ts: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }[] = [];
  let pageToken: string | undefined;
  let pageCount = 0;
  const maxPages = 100; // Safety limit

  while (pageCount < maxPages) {
    let url = `${ALPACA_BASE_URL}/stocks/bars?` +
      `symbols=${symbol.toUpperCase()}&` +
      `timeframe=${alpacaTf}&` +
      `start=${startStr}&` +
      `end=${endStr}&` +
      `limit=10000&` +
      `adjustment=raw&` +
      `feed=iex&` +
      `sort=asc`;

    if (pageToken) {
      url += `&page_token=${pageToken}`;
    }

    const response = await fetch(url, {
      headers: getAlpacaHeaders(),
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Alpaca API error: ${response.status} - ${text}`);
    }

    const data = await response.json();
    const barsData = data.bars?.[symbol.toUpperCase()] || [];

    if (barsData.length === 0 && pageCount === 0) {
      console.log(
        `[SymbolBackfill] No data returned for ${symbol} ${timeframe}`,
      );
      return [];
    }

    // Transform to our format
    for (const bar of barsData) {
      allBars.push({
        ts: bar.t,
        open: bar.o,
        high: bar.h,
        low: bar.l,
        close: bar.c,
        volume: bar.v,
      });
    }

    pageToken = data.next_page_token;
    pageCount++;

    if (pageToken) {
      console.log(
        `[SymbolBackfill] Fetched page ${pageCount} with ${barsData.length} bars, continuing...`,
      );
      await new Promise((resolve) => setTimeout(resolve, RATE_LIMIT_DELAY));
    } else {
      break;
    }
  }

  console.log(
    `[SymbolBackfill] Received ${allBars.length} bars for ${symbol} ${timeframe}`,
  );
  return allBars;
}

async function getExistingCoverage(
  supabase: ReturnType<typeof getSupabaseClient>,
  symbolId: string,
  timeframe: string,
): Promise<{ count: number; latest: Date | null }> {
  const { data, error } = await supabase
    .from("ohlc_bars_v2")
    .select("ts")
    .eq("symbol_id", symbolId)
    .eq("timeframe", timeframe)
    .eq("is_forecast", false)
    .order("ts", { ascending: false })
    .limit(1);

  if (error || !data || data.length === 0) {
    return { count: 0, latest: null };
  }

  // Get count
  const { count } = await supabase
    .from("ohlc_bars_v2")
    .select("id", { count: "exact", head: true })
    .eq("symbol_id", symbolId)
    .eq("timeframe", timeframe)
    .eq("is_forecast", false);

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
  force: boolean,
): Promise<BackfillResult> {
  const config = TIMEFRAME_CONFIG[timeframe];
  if (!config) {
    return {
      timeframe,
      barsInserted: 0,
      error: `Invalid timeframe: ${timeframe}`,
    };
  }

  try {
    // Check existing coverage
    const coverage = await getExistingCoverage(supabase, symbolId, timeframe);
    console.log(
      `[SymbolBackfill] ${symbol} ${timeframe}: ${coverage.count} existing bars, latest=${coverage.latest?.toISOString()}`,
    );

    // Skip if we have recent data and not forcing
    if (!force && coverage.latest) {
      const ageMs = Date.now() - coverage.latest.getTime();
      const maxAgeMs = timeframe === "d1"
        ? 24 * 60 * 60 * 1000
        : 4 * 60 * 60 * 1000;
      if (ageMs < maxAgeMs && coverage.count >= 100) {
        console.log(
          `[SymbolBackfill] ${symbol} ${timeframe}: Data is current, skipping`,
        );
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
    const startDate = new Date(
      endDate.getTime() - config.maxDays * 24 * 60 * 60 * 1000,
    );

    // Fetch from Alpaca
    const bars = await fetchAlpacaBars(symbol, timeframe, startDate, endDate);

    if (bars.length === 0) {
      return {
        timeframe,
        barsInserted: 0,
        error: "No data returned from Alpaca",
      };
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
      provider: "alpaca",
      is_forecast: false,
      data_status: "verified",
    }));

    const { error: upsertError } = await supabase
      .from("ohlc_bars_v2")
      .upsert(barsToInsert, {
        onConflict: "symbol_id,timeframe,ts,provider,is_forecast",
      });

    if (upsertError) {
      console.error(
        `[SymbolBackfill] Upsert error for ${symbol} ${timeframe}:`,
        upsertError,
      );
      return { timeframe, barsInserted: 0, error: upsertError.message };
    }

    console.log(
      `[SymbolBackfill] Inserted ${bars.length} bars for ${symbol} ${timeframe}`,
    );

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
  if (!ALPACA_API_KEY || !ALPACA_API_SECRET) {
    return errorResponse(
      "ALPACA_API_KEY or ALPACA_API_SECRET not configured",
      500,
    );
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
      console.log(
        `[SymbolBackfill] Created new symbol: ${ticker} (${symbolId})`,
      );
    } else {
      symbolId = symbolData.id;
    }

    // 2. Backfill each timeframe
    const results: BackfillResult[] = [];
    let totalBars = 0;

    for (const tf of timeframes) {
      if (!TIMEFRAME_CONFIG[tf]) {
        results.push({
          timeframe: tf,
          barsInserted: 0,
          error: `Invalid timeframe: ${tf}`,
        });
        continue;
      }

      const result = await backfillTimeframe(
        supabase,
        ticker,
        symbolId,
        tf,
        force,
      );
      results.push(result);
      totalBars += result.barsInserted;

      // Rate limiting: Alpaca allows 200 req/min
      // Wait 0.3 seconds between timeframes
      if (timeframes.indexOf(tf) < timeframes.length - 1) {
        console.log(
          `[SymbolBackfill] Rate limit delay (${RATE_LIMIT_DELAY}ms)...`,
        );
        await new Promise((resolve) => setTimeout(resolve, RATE_LIMIT_DELAY));
      }
    }

    const response: BackfillResponse = {
      symbol: ticker,
      results,
      totalBars,
      durationMs: Date.now() - startTime,
    };

    console.log(
      `[SymbolBackfill] Complete for ${ticker}: ${totalBars} total bars in ${response.durationMs}ms`,
    );

    return jsonResponse(response);
  } catch (err) {
    console.error("[SymbolBackfill] Error:", err);
    return errorResponse("Internal server error", 500);
  }
});
