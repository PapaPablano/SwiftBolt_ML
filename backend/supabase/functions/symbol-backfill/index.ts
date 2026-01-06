// symbol-backfill: Deep backfill OHLC data for a symbol using Yahoo Finance
// POST /symbol-backfill { symbol, timeframes?, force? }
//
// Triggered when a symbol is added to a watchlist to ensure historical data is available.
// Uses Yahoo Finance for historical data (free, reliable, no API key required).

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";
import { getSupabaseClient } from "../_shared/supabase-client.ts";

const YFINANCE_BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart";

// Timeframe configurations: how much history to fetch
// Yahoo Finance intervals: 1m, 5m, 15m, 30m, 1h, 1d, 1wk, 1mo
const TIMEFRAME_CONFIG: Record<string, { interval: string; maxDays: number }> = {
  m15: { interval: "15m", maxDays: 60 },
  h1: { interval: "1h", maxDays: 730 },
  h4: { interval: "1h", maxDays: 730 }, // Use 1h, aggregate if needed
  d1: { interval: "1d", maxDays: 730 },  // 2 years
  w1: { interval: "1wk", maxDays: 1825 }, // 5 years
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

async function fetchYahooFinanceBars(
  symbol: string,
  timeframe: string,
  startDate: Date,
  endDate: Date
): Promise<{ ts: string; open: number; high: number; low: number; close: number; volume: number }[]> {
  const config = TIMEFRAME_CONFIG[timeframe];
  if (!config) {
    throw new Error(`Invalid timeframe: ${timeframe}`);
  }

  const { interval } = config;

  // Yahoo Finance uses Unix timestamps in seconds
  const period1 = Math.floor(startDate.getTime() / 1000);
  const period2 = Math.floor(endDate.getTime() / 1000);

  const url = `${YFINANCE_BASE_URL}/${symbol.toUpperCase()}?interval=${interval}&period1=${period1}&period2=${period2}`;

  console.log(`[SymbolBackfill] Fetching ${symbol} ${timeframe} from Yahoo Finance (${interval})`);

  const response = await fetch(url, {
    headers: { "User-Agent": "Mozilla/5.0" },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Yahoo Finance API error: ${response.status} - ${text}`);
  }

  const data = await response.json();
  const result = data.chart?.result?.[0];

  if (!result) {
    console.log(`[SymbolBackfill] No data returned from Yahoo Finance for ${symbol}`);
    return [];
  }

  const timestamps = result.timestamp || [];
  const quotes = result.indicators?.quote?.[0];

  if (!quotes || timestamps.length === 0) {
    console.log(`[SymbolBackfill] Empty dataset from Yahoo Finance for ${symbol}`);
    return [];
  }

  const bars: { ts: string; open: number; high: number; low: number; close: number; volume: number }[] = [];

  for (let i = 0; i < timestamps.length; i++) {
    // Skip bars with null values
    if (
      quotes.open[i] === null ||
      quotes.high[i] === null ||
      quotes.low[i] === null ||
      quotes.close[i] === null
    ) {
      continue;
    }

    // Validate data quality - skip bars with extreme intraday ranges (>25%)
    const intradayRange = (quotes.high[i] - quotes.low[i]) / quotes.close[i];
    if (intradayRange > 0.25) {
      console.log(`[SymbolBackfill] Skipping bar with extreme range: ${intradayRange * 100}%`);
      continue;
    }

    bars.push({
      ts: new Date(timestamps[i] * 1000).toISOString(),
      open: quotes.open[i],
      high: quotes.high[i],
      low: quotes.low[i],
      close: quotes.close[i],
      volume: quotes.volume[i] || 0,
    });
  }

  console.log(`[SymbolBackfill] Received ${bars.length} valid bars for ${symbol} ${timeframe}`);
  return bars;
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

    // Fetch from Yahoo Finance
    const bars = await fetchYahooFinanceBars(symbol, timeframe, startDate, endDate);

    if (bars.length === 0) {
      return { timeframe, barsInserted: 0, error: "No data returned from Yahoo Finance" };
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
      provider: "yfinance",
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

  // Yahoo Finance doesn't require an API key

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

      // Yahoo Finance has no rate limits, but add small delay to be polite
      if (timeframes.indexOf(tf) < timeframes.length - 1) {
        await new Promise((resolve) => setTimeout(resolve, 500));
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
