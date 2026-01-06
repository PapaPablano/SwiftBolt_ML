// Backfill adapter: Wraps ProviderRouter for backfill worker consumption
// Provides day-bounded intraday fetching with normalized output for ohlc_bars_v2

import { getProviderRouter } from "./providers/factory.ts";
import type { Bar, Timeframe } from "./providers/types.ts";

export interface BackfillBar {
  symbol: string;
  timeframe: string;
  ts: string; // ISO 8601
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  provider: string;
}

export interface BackfillRequest {
  symbol: string;
  timeframe: string; // '15m' | '1h' | '4h' | '1d' | '1w'
  day: string; // YYYY-MM-DD
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

// Calculate day boundaries in UTC
function dayBoundsUTC(day: string): { start: Date; end: Date } {
  const start = new Date(`${day}T00:00:00.000Z`);
  const end = new Date(`${day}T23:59:59.999Z`);
  return { start, end };
}

/**
 * Fetch intraday bars for a single day using the provider router
 * Returns normalized bars ready for ohlc_bars_v2 upsert
 */
export async function fetchIntradayForDay(
  request: BackfillRequest
): Promise<BackfillBar[]> {
  const { symbol, timeframe, day } = request;
  const router = getProviderRouter();
  const { start, end } = dayBoundsUTC(day);

  // Convert to Unix timestamps (seconds)
  const fromTs = Math.floor(start.getTime() / 1000);
  const toTs = Math.floor(end.getTime() / 1000);

  console.log(
    `[BackfillAdapter] Fetching ${symbol} ${timeframe} for ${day} (${fromTs} - ${toTs})`
  );

  try {
    const bars = await router.getHistoricalBars({
      symbol,
      timeframe: mapTimeframeToProvider(timeframe),
      start: fromTs,
      end: toTs,
    });

    console.log(`[BackfillAdapter] Received ${bars.length} bars for ${symbol} ${day}`);

    // Normalize to DB schema
    return bars.map((bar: Bar) => ({
      symbol,
      timeframe,
      ts: new Date(bar.timestamp * 1000).toISOString(),
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
      volume: bar.volume,
      provider: "yahoo", // Router uses yahoo as primary for historical
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
  days: string[]
): Promise<BackfillBar[]> {
  const results: BackfillBar[] = [];

  // Process in small batches to avoid overwhelming the provider
  const batchSize = 3;
  for (let i = 0; i < days.length; i += batchSize) {
    const batch = days.slice(i, i + batchSize);
    const promises = batch.map((day) =>
      fetchIntradayForDay({ symbol, timeframe, day })
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
