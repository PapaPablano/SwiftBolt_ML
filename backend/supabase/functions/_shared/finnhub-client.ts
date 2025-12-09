// Finnhub API client for fetching market data
// Docs: https://finnhub.io/docs/api/stock-candles

export type Timeframe = "m15" | "h1" | "h4" | "d1" | "w1";

interface FinnhubCandleResponse {
  c: number[]; // Close prices
  h: number[]; // High prices
  l: number[]; // Low prices
  o: number[]; // Open prices
  t: number[]; // Timestamps (Unix seconds)
  v: number[]; // Volume
  s: string;   // Status: "ok" or "no_data"
}

export interface OHLCBar {
  ts: string;      // ISO8601 timestamp
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// Map our timeframes to Finnhub resolutions
const TIMEFRAME_TO_RESOLUTION: Record<Timeframe, string> = {
  m15: "15",
  h1: "60",
  h4: "240",  // Note: Finnhub uses "240" for 4-hour, not all plans support this
  d1: "D",
  w1: "W",
};

// Calculate seconds per bar for each timeframe
const TIMEFRAME_SECONDS: Record<Timeframe, number> = {
  m15: 15 * 60,
  h1: 60 * 60,
  h4: 4 * 60 * 60,
  d1: 24 * 60 * 60,
  w1: 7 * 24 * 60 * 60,
};

/**
 * Fetches OHLC candle data from Finnhub API
 */
export async function fetchCandles(
  symbol: string,
  timeframe: Timeframe,
  barCount = 100
): Promise<OHLCBar[]> {
  const apiKey = Deno.env.get("FINNHUB_API_KEY");
  if (!apiKey) {
    throw new Error("FINNHUB_API_KEY environment variable not set");
  }

  const resolution = TIMEFRAME_TO_RESOLUTION[timeframe];
  if (!resolution) {
    throw new Error(`Invalid timeframe: ${timeframe}`);
  }

  // Calculate time range
  const now = Math.floor(Date.now() / 1000);
  const secondsPerBar = TIMEFRAME_SECONDS[timeframe];
  const from = now - (barCount * secondsPerBar);

  const url = new URL("https://finnhub.io/api/v1/stock/candle");
  url.searchParams.set("symbol", symbol.toUpperCase());
  url.searchParams.set("resolution", resolution);
  url.searchParams.set("from", from.toString());
  url.searchParams.set("to", now.toString());
  url.searchParams.set("token", apiKey);

  console.log(`Fetching candles from Finnhub: ${symbol} ${timeframe}`);

  const response = await fetch(url.toString());

  if (!response.ok) {
    throw new Error(`Finnhub API error: ${response.status} ${response.statusText}`);
  }

  const data: FinnhubCandleResponse = await response.json();

  if (data.s === "no_data") {
    console.log(`No data available for ${symbol} ${timeframe}`);
    return [];
  }

  if (data.s !== "ok") {
    throw new Error(`Finnhub returned unexpected status: ${data.s}`);
  }

  // Transform to our OHLC bar format
  const bars: OHLCBar[] = [];
  const count = data.t?.length || 0;

  for (let i = 0; i < count; i++) {
    bars.push({
      ts: new Date(data.t[i] * 1000).toISOString(),
      open: data.o[i],
      high: data.h[i],
      low: data.l[i],
      close: data.c[i],
      volume: data.v[i],
    });
  }

  console.log(`Fetched ${bars.length} bars for ${symbol} ${timeframe}`);
  return bars;
}

/**
 * Validates that a string is a valid timeframe
 */
export function isValidTimeframe(value: string): value is Timeframe {
  return ["m15", "h1", "h4", "d1", "w1"].includes(value);
}
