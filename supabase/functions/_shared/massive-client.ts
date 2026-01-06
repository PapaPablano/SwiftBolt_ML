// Massive API client (Polygon.io) for fetching market data
// Docs: https://polygon.io/docs/stocks/get_v2_aggs_ticker__stocksticker__range__multiplier___timespan___from___to

export type Timeframe = "m15" | "h1" | "h4" | "d1" | "w1";

interface PolygonAggregateResult {
  v: number;   // Volume
  vw: number;  // Volume weighted average price
  o: number;   // Open
  c: number;   // Close
  h: number;   // High
  l: number;   // Low
  t: number;   // Timestamp (Unix ms)
  n: number;   // Number of transactions
}

interface PolygonAggregatesResponse {
  ticker: string;
  queryCount: number;
  resultsCount: number;
  adjusted: boolean;
  results?: PolygonAggregateResult[];
  status: string;
  request_id: string;
  count?: number;
  next_url?: string;
}

export interface OHLCBar {
  ts: string;      // ISO8601 timestamp
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// Map our timeframes to Polygon multiplier + timespan
const TIMEFRAME_CONFIG: Record<Timeframe, { multiplier: number; timespan: string }> = {
  m15: { multiplier: 15, timespan: "minute" },
  h1:  { multiplier: 1,  timespan: "hour" },
  h4:  { multiplier: 4,  timespan: "hour" },
  d1:  { multiplier: 1,  timespan: "day" },
  w1:  { multiplier: 1,  timespan: "week" },
};

// Calculate milliseconds per bar for each timeframe
const TIMEFRAME_MS: Record<Timeframe, number> = {
  m15: 15 * 60 * 1000,
  h1:  60 * 60 * 1000,
  h4:  4 * 60 * 60 * 1000,
  d1:  24 * 60 * 60 * 1000,
  w1:  7 * 24 * 60 * 60 * 1000,
};

/**
 * Fetches OHLC candle data from Polygon.io (Massive API)
 *
 * Note: Free tier limit is 5 requests/minute.
 * Consider implementing rate limiting for production use.
 */
export async function fetchCandles(
  symbol: string,
  timeframe: Timeframe,
  barCount = 100
): Promise<OHLCBar[]> {
  const apiKey = Deno.env.get("MASSIVE_API_KEY");
  if (!apiKey) {
    throw new Error("MASSIVE_API_KEY environment variable not set");
  }

  const config = TIMEFRAME_CONFIG[timeframe];
  if (!config) {
    throw new Error(`Invalid timeframe: ${timeframe}`);
  }

  // Calculate time range
  const now = Date.now();
  const msPerBar = TIMEFRAME_MS[timeframe];
  const from = now - (barCount * msPerBar);

  // Format dates as YYYY-MM-DD for daily/weekly, or Unix ms for intraday
  const formatDate = (ms: number): string => {
    if (timeframe === "d1" || timeframe === "w1") {
      return new Date(ms).toISOString().split("T")[0];
    }
    return ms.toString();
  };

  const ticker = symbol.toUpperCase();
  const { multiplier, timespan } = config;

  // Build Polygon aggregates URL
  // /v2/aggs/ticker/{stocksTicker}/range/{multiplier}/{timespan}/{from}/{to}
  const url = new URL(
    `https://api.polygon.io/v2/aggs/ticker/${ticker}/range/${multiplier}/${timespan}/${formatDate(from)}/${formatDate(now)}`
  );
  url.searchParams.set("adjusted", "false");  // ALWAYS use unadjusted prices
  url.searchParams.set("sort", "asc");
  url.searchParams.set("limit", barCount.toString());
  url.searchParams.set("apiKey", apiKey);

  console.log(`Fetching candles from Polygon: ${ticker} ${timeframe}`);

  const response = await fetch(url.toString());

  if (!response.ok) {
    const errorText = await response.text();
    console.error(`Polygon API error: ${response.status} - ${errorText}`);
    throw new Error(`Polygon API error: ${response.status} ${response.statusText}`);
  }

  const data: PolygonAggregatesResponse = await response.json();

  if (data.status === "ERROR") {
    throw new Error(`Polygon returned error status`);
  }

  if (!data.results || data.results.length === 0) {
    console.log(`No data available for ${ticker} ${timeframe}`);
    return [];
  }

  // Transform to our OHLC bar format
  const bars: OHLCBar[] = data.results.map((bar) => ({
    ts: new Date(bar.t).toISOString(),
    open: bar.o,
    high: bar.h,
    low: bar.l,
    close: bar.c,
    volume: bar.v,
  }));

  console.log(`Fetched ${bars.length} bars for ${ticker} ${timeframe}`);
  return bars;
}

/**
 * Validates that a string is a valid timeframe
 */
export function isValidTimeframe(value: string): value is Timeframe {
  return ["m15", "h1", "h4", "d1", "w1"].includes(value);
}