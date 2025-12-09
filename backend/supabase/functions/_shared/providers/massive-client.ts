// MassiveClient: DataProviderAbstraction implementation for Polygon.io (Massive) API
// Includes strict 5 req/min rate limiting, caching, and unified error handling

import type {
  DataProviderAbstraction,
  HistoricalBarsRequest,
  NewsRequest,
} from "./abstraction.ts";
import type { Bar, NewsItem, Quote } from "./types.ts";
import {
  InvalidSymbolError,
  PermissionDeniedError,
  ProviderError,
  ProviderUnavailableError,
  RateLimitExceededError,
} from "./types.ts";
import type { TokenBucketRateLimiter } from "../rate-limiter/token-bucket.ts";
import type { Cache } from "../cache/interface.ts";
import { CACHE_TTL } from "../config/rate-limits.ts";

interface PolygonAggregateResult {
  v: number; // Volume
  vw: number; // Volume weighted average price
  o: number; // Open
  c: number; // Close
  h: number; // High
  l: number; // Low
  t: number; // Timestamp (Unix ms)
  n: number; // Number of transactions
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

interface PolygonSnapshotQuote {
  t: number; // Ticker timestamp
  p: number; // Price
  s: number; // Size
}

interface PolygonSnapshotDay {
  c: number; // Close
  h: number; // High
  l: number; // Low
  o: number; // Open
  v: number; // Volume
  vw: number; // Volume weighted average price
}

interface PolygonSnapshotResponse {
  ticker: string;
  todaysChange: number;
  todaysChangePerc: number;
  updated: number;
  day?: PolygonSnapshotDay;
  lastQuote?: PolygonSnapshotQuote;
  prevDay?: PolygonSnapshotDay;
}

// Map our timeframes to Polygon multiplier + timespan
const TIMEFRAME_CONFIG: Record<string, { multiplier: number; timespan: string }> = {
  m1: { multiplier: 1, timespan: "minute" },
  m5: { multiplier: 5, timespan: "minute" },
  m15: { multiplier: 15, timespan: "minute" },
  m30: { multiplier: 30, timespan: "minute" },
  h1: { multiplier: 1, timespan: "hour" },
  h4: { multiplier: 4, timespan: "hour" },
  d1: { multiplier: 1, timespan: "day" },
  w1: { multiplier: 1, timespan: "week" },
  mn1: { multiplier: 1, timespan: "month" },
};

export class MassiveClient implements DataProviderAbstraction {
  private readonly apiKey: string;
  private readonly baseURL: string;
  private readonly rateLimiter: TokenBucketRateLimiter;
  private readonly cache: Cache;

  constructor(
    apiKey: string,
    rateLimiter: TokenBucketRateLimiter,
    cache: Cache,
    baseURL: string = "https://api.polygon.io"
  ) {
    this.apiKey = apiKey;
    this.baseURL = baseURL;
    this.rateLimiter = rateLimiter;
    this.cache = cache;
  }

  async getQuote(symbols: string[]): Promise<Quote[]> {
    const quotes: Quote[] = [];

    for (const symbol of symbols) {
      const cacheKey = `quote:massive:${symbol}`;
      const cached = await this.cache.get<Quote>(cacheKey);

      if (cached) {
        quotes.push(cached);
        continue;
      }

      // Acquire rate limit token (strict 5/min limit)
      await this.rateLimiter.acquire("massive");

      const url = new URL(`${this.baseURL}/v2/snapshot/locale/us/markets/stocks/tickers/${symbol.toUpperCase()}`);
      url.searchParams.set("apiKey", this.apiKey);

      try {
        console.log(`[Massive] Fetching quote: ${symbol}`);
        const response = await fetch(url.toString());
        await this.handleHttpErrors(response);

        const data: { ticker: PolygonSnapshotResponse } = await response.json();
        const snapshot = data.ticker;

        const quote: Quote = {
          symbol,
          price: snapshot.lastQuote?.p || snapshot.day?.c || 0,
          timestamp: snapshot.updated || Date.now(),
          volume: snapshot.day?.v,
          change: snapshot.todaysChange,
          changePercent: snapshot.todaysChangePerc,
          high: snapshot.day?.h,
          low: snapshot.day?.l,
          open: snapshot.day?.o,
          previousClose: snapshot.prevDay?.c,
        };

        await this.cache.set(cacheKey, quote, CACHE_TTL.quote, [
          `symbol:${symbol}`,
        ]);
        quotes.push(quote);
      } catch (error) {
        console.error(`[Massive] Error fetching quote for ${symbol}:`, error);
        throw this.mapError(error);
      }
    }

    return quotes;
  }

  async getHistoricalBars(request: HistoricalBarsRequest): Promise<Bar[]> {
    const { symbol, timeframe, start, end } = request;
    const cacheKey = `bars:massive:${symbol}:${timeframe}:${start}:${end}`;
    const cached = await this.cache.get<Bar[]>(cacheKey);

    if (cached) {
      return cached;
    }

    // Acquire rate limit token (strict 5/min limit)
    await this.rateLimiter.acquire("massive");

    const config = TIMEFRAME_CONFIG[timeframe];
    if (!config) {
      throw new InvalidSymbolError("massive", `Invalid timeframe: ${timeframe}`);
    }

    const ticker = symbol.toUpperCase();
    const { multiplier, timespan } = config;

    // Format timestamps based on timespan
    const formatTimestamp = (ts: number): string => {
      if (timespan === "day" || timespan === "week" || timespan === "month") {
        return new Date(ts * 1000).toISOString().split("T")[0];
      }
      return (ts * 1000).toString(); // Convert to milliseconds
    };

    const url = new URL(
      `${this.baseURL}/v2/aggs/ticker/${ticker}/range/${multiplier}/${timespan}/${formatTimestamp(start)}/${formatTimestamp(end)}`
    );
    url.searchParams.set("adjusted", "true");
    url.searchParams.set("sort", "asc");
    url.searchParams.set("limit", "50000"); // Max limit
    url.searchParams.set("apiKey", this.apiKey);

    try {
      console.log(`[Massive] Fetching candles: ${symbol} ${timeframe}`);
      const response = await fetch(url.toString());
      await this.handleHttpErrors(response);

      const data: PolygonAggregatesResponse = await response.json();

      if (data.status === "ERROR") {
        throw new ProviderError(
          "Polygon returned error status",
          "massive",
          "API_ERROR"
        );
      }

      if (!data.results || data.results.length === 0) {
        console.log(`[Massive] No data available for ${symbol} ${timeframe}`);
        return [];
      }

      // Transform to unified Bar format
      const bars: Bar[] = data.results.map((bar) => ({
        timestamp: bar.t, // Already in milliseconds
        open: bar.o,
        high: bar.h,
        low: bar.l,
        close: bar.c,
        volume: bar.v,
      }));

      console.log(`[Massive] Fetched ${bars.length} bars`);

      await this.cache.set(cacheKey, bars, CACHE_TTL.bars, [
        `symbol:${symbol}`,
        `timeframe:${timeframe}`,
      ]);

      return bars;
    } catch (error) {
      console.error(`[Massive] Error fetching bars:`, error);
      throw this.mapError(error);
    }
  }

  async getNews(_request: NewsRequest): Promise<NewsItem[]> {
    // Polygon.io free tier doesn't include news API
    // Return empty array or throw PermissionDeniedError
    throw new PermissionDeniedError(
      "massive",
      "News API not available on free tier"
    );
  }

  async healthCheck(): Promise<boolean> {
    try {
      // Simple health check: fetch quote for a known symbol
      await this.getQuote(["AAPL"]);
      return true;
    } catch {
      return false;
    }
  }

  private async handleHttpErrors(response: Response): Promise<void> {
    if (response.ok) return;

    const text = await response.text();

    if (response.status === 429) {
      const retryAfter = response.headers.get("Retry-After");
      throw new RateLimitExceededError(
        "massive",
        retryAfter ? parseInt(retryAfter, 10) : undefined
      );
    }

    if (response.status === 401 || response.status === 403) {
      throw new PermissionDeniedError("massive", text || "Authentication failed");
    }

    if (response.status >= 500) {
      throw new ProviderUnavailableError("massive");
    }

    throw new ProviderError(
      text || "Unknown error",
      "massive",
      "HTTP_ERROR",
      response.status
    );
  }

  private mapError(error: unknown): Error {
    if (error instanceof ProviderError) {
      return error;
    }

    if (error instanceof Error) {
      return new ProviderUnavailableError("massive", error);
    }

    return new ProviderError(
      String(error),
      "massive",
      "UNKNOWN_ERROR"
    );
  }
}
