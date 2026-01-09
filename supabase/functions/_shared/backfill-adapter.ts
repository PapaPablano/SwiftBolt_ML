// Backfill adapter: Wraps ProviderRouter for backfill worker consumption
// Provides day-bounded intraday fetching with normalized output for ohlc_bars_v2
// Uses Polygon (massive) for historical intraday data via router

import { getProviderRouter } from "./providers/factory.ts";
import type { Bar, Timeframe } from "./providers/types.ts";

// Symbol ID cache to avoid repeated lookups
const symbolIdCache = new Map<string, string>();

export interface BackfillBar {
  symbol_id: string; // UUID - required for ohlc_bars_v2
  timeframe: string;
  ts: string; // ISO 8601
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  provider: string;
  is_intraday: boolean;
  is_forecast: boolean;
  data_status: string;
}

export interface BackfillRequest {
  symbol: string;
  timeframe: string; // '15m' | '1h' | '4h' | '1d' | '1w'
  day: string; // YYYY-MM-DD
  supabase?: any; // Supabase client - will create if not provided
}

// Map our timeframe tokens to provider Timeframe enum
function mapTimeframeToProvider(tf: string): Timeframe {
  const map: Record<string, Timeframe> = {
    "15m": "m15",
    "1h": "h1",
    "4h": "h4",
    "1d": "d1",
    "1w": "w1",
  };
  return map[tf] || "h1";
}

// Check if timeframe is intraday (should use Polygon)
function isIntradayTimeframe(tf: string): boolean {
  return ["15m", "1h", "4h", "m15", "h1", "h4"].includes(tf);
}

// Calculate day boundaries in UTC
function dayBoundsUTC(day: string): { start: Date; end: Date } {
  const start = new Date(`${day}T00:00:00.000Z`);
  const end = new Date(`${day}T23:59:59.999Z`);
  return { start, end };
}

/**
 * Lookup symbol_id from symbols table (with caching)
 */
async function getSymbolId(supabase: any, ticker: string): Promise<string> {
  // Check cache first
  const cached = symbolIdCache.get(ticker.toUpperCase());
  if (cached) {
    return cached;
  }

  const { data, error } = await supabase
    .from("symbols")
    .select("id")
    .eq("ticker", ticker.toUpperCase())
    .single();

  if (error || !data) {
    throw new Error(`Symbol not found: ${ticker}`);
  }

  // Cache for future lookups
  symbolIdCache.set(ticker.toUpperCase(), data.id);
  return data.id;
}

/**
 * Fetch intraday bars for a single day using the provider router
 * Returns normalized bars ready for ohlc_bars_v2 upsert
 */
export async function fetchIntradayForDay(
  request: BackfillRequest
): Promise<BackfillBar[]> {
  const { symbol, timeframe, day, supabase } = request;

  if (!supabase) {
    throw new Error("Supabase client is required for symbol_id lookup");
  }

  const { start, end } = dayBoundsUTC(day);

  // Convert to Unix timestamps (seconds)
  const fromTs = Math.floor(start.getTime() / 1000);
  const toTs = Math.floor(end.getTime() / 1000);

  console.log(
    `[BackfillAdapter] Fetching ${symbol} ${timeframe} for ${day} (${fromTs} - ${toTs})`
  );

  // Lookup symbol_id first
  const symbolId = await getSymbolId(supabase, symbol);
  const isIntraday = isIntradayTimeframe(timeframe);
  const providerTimeframe = mapTimeframeToProvider(timeframe);

  try {
    // Use router to fetch bars - it will use the configured provider
    const router = getProviderRouter();
    const bars = await router.getHistoricalBars({
      symbol,
      timeframe: providerTimeframe,
      start: fromTs,
      end: toTs,
    });

    // Determine provider based on timeframe
    // Intraday should come from Polygon (massive), daily from Yahoo
    const provider = isIntraday ? "polygon" : "yfinance";

    console.log(`[BackfillAdapter] Received ${bars.length} bars for ${symbol} ${day} (provider: ${provider})`);

    // Normalize to ohlc_bars_v2 schema
    return bars.map((bar: Bar) => ({
      symbol_id: symbolId,
      timeframe: providerTimeframe, // Use canonical format (m15, h1, etc.)
      ts: new Date(bar.timestamp).toISOString(), // timestamp is in ms from Polygon
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
      volume: bar.volume,
      provider: provider,
      is_intraday: isIntraday,
      is_forecast: false,
      data_status: "verified", // Historical data is verified
    }));
  } catch (error) {
    console.error(`[BackfillAdapter] Error fetching ${symbol} ${timeframe} ${day}:`, error);
    throw error;
  }
}

/**
 * Batch fetch multiple days for a symbol/timeframe
 * Useful for initial seeding or catch-up
 */
export async function fetchIntradayBatch(
  symbol: string,
  timeframe: string,
  days: string[],
  supabase: any
): Promise<BackfillBar[]> {
  if (!supabase) {
    throw new Error("Supabase client is required for symbol_id lookup");
  }

  const results: BackfillBar[] = [];

  // Process in small batches to avoid overwhelming the provider
  const batchSize = 3;
  for (let i = 0; i < days.length; i += batchSize) {
    const batch = days.slice(i, i + batchSize);
    const promises = batch.map((day) =>
      fetchIntradayForDay({ symbol, timeframe, day, supabase })
    );

    const batchResults = await Promise.allSettled(promises);
    for (const result of batchResults) {
      if (result.status === "fulfilled") {
        results.push(...result.value);
      } else {
        console.error(`[BackfillAdapter] Batch fetch failed:`, result.reason);
      }
    }

    // Small delay between batches to respect rate limits
    if (i + batchSize < days.length) {
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
  }

  return results;
}
