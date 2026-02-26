// FinnhubClient: DataProviderAbstraction implementation for Finnhub API
// Includes rate limiting, caching, and unified error handling

import type {
  DataProviderAbstraction,
  HistoricalBarsRequest,
  NewsRequest,
} from "./abstraction.ts";
import type { Bar, NewsItem, Quote, Symbol } from "./types.ts";
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

interface FinnhubCandleResponse {
  c: number[]; // Close prices
  h: number[]; // High prices
  l: number[]; // Low prices
  o: number[]; // Open prices
  t: number[]; // Timestamps (Unix seconds)
  v: number[]; // Volume
  s: string; // Status: "ok" or "no_data"
}

interface FinnhubNewsItem {
  category: string;
  datetime: number; // Unix timestamp
  headline: string;
  id: number;
  image: string;
  related: string; // Ticker symbols
  source: string;
  summary: string;
  url: string;
}

interface FinnhubQuoteResponse {
  c: number; // Current price
  d: number; // Change
  dp: number; // Percent change
  h: number; // High price of the day
  l: number; // Low price of the day
  o: number; // Open price of the day
  pc: number; // Previous close price
  t: number; // Timestamp
}

// Map our timeframes to Finnhub resolutions
const TIMEFRAME_TO_RESOLUTION: Record<string, string> = {
  m1: "1",
  m5: "5",
  m15: "15",
  m30: "30",
  h1: "60",
  h4: "240",
  d1: "D",
  w1: "W",
  mn1: "M",
};

export class FinnhubClient implements DataProviderAbstraction {
  private readonly apiKey: string;
  private readonly baseURL: string;
  private readonly rateLimiter: TokenBucketRateLimiter;
  private readonly cache: Cache;

  constructor(
    apiKey: string,
    rateLimiter: TokenBucketRateLimiter,
    cache: Cache,
    baseURL: string = "https://finnhub.io/api/v1",
  ) {
    this.apiKey = apiKey;
    this.baseURL = baseURL;
    this.rateLimiter = rateLimiter;
    this.cache = cache;
  }

  async getQuote(symbols: string[]): Promise<Quote[]> {
    const quotes: Quote[] = [];

    for (const symbol of symbols) {
      const cacheKey = `quote:finnhub:${symbol}`;
      const cached = await this.cache.get<Quote>(cacheKey);

      if (cached) {
        quotes.push(cached);
        continue;
      }

      // Acquire rate limit token
      await this.rateLimiter.acquire("finnhub");

      const url = new URL(`${this.baseURL}/quote`);
      url.searchParams.set("symbol", symbol.toUpperCase());
      url.searchParams.set("token", this.apiKey);

      try {
        const response = await fetch(url.toString());
        await this.handleHttpErrors(response);

        const data: FinnhubQuoteResponse = await response.json();

        const quote: Quote = {
          symbol,
          price: data.c,
          timestamp: data.t * 1000, // Convert to milliseconds
          volume: undefined, // Finnhub quote doesn't include volume
          change: data.d,
          changePercent: data.dp,
          high: data.h,
          low: data.l,
          open: data.o,
          previousClose: data.pc,
        };

        await this.cache.set(cacheKey, quote, CACHE_TTL.quote, [
          `symbol:${symbol}`,
        ]);
        quotes.push(quote);
      } catch (error) {
        console.error(`Error fetching quote for ${symbol}:`, error);
        throw this.mapError(error);
      }
    }

    return quotes;
  }

  async getHistoricalBars(request: HistoricalBarsRequest): Promise<Bar[]> {
    const { symbol, timeframe, start, end } = request;
    const cacheKey = `bars:finnhub:${symbol}:${timeframe}:${start}:${end}`;
    const cached = await this.cache.get<Bar[]>(cacheKey);

    if (cached) {
      return cached;
    }

    // Acquire rate limit token
    await this.rateLimiter.acquire("finnhub");

    const resolution = TIMEFRAME_TO_RESOLUTION[timeframe];
    if (!resolution) {
      throw new InvalidSymbolError(
        "finnhub",
        `Invalid timeframe: ${timeframe}`,
      );
    }

    const url = new URL(`${this.baseURL}/stock/candle`);
    url.searchParams.set("symbol", symbol.toUpperCase());
    url.searchParams.set("resolution", resolution);
    url.searchParams.set("from", start.toString());
    url.searchParams.set("to", end.toString());
    url.searchParams.set("token", this.apiKey);

    try {
      console.log(`[Finnhub] Fetching candles: ${symbol} ${timeframe}`);
      const response = await fetch(url.toString());
      await this.handleHttpErrors(response);

      const data: FinnhubCandleResponse = await response.json();

      if (data.s === "no_data") {
        console.log(`[Finnhub] No data available for ${symbol} ${timeframe}`);
        return [];
      }

      if (data.s !== "ok") {
        throw new ProviderError(
          `Unexpected status: ${data.s}`,
          "finnhub",
          "UNEXPECTED_STATUS",
        );
      }

      // Transform to unified Bar format
      const bars: Bar[] = [];
      const count = data.t?.length || 0;

      for (let i = 0; i < count; i++) {
        bars.push({
          timestamp: data.t[i] * 1000, // Convert to milliseconds
          open: data.o[i],
          high: data.h[i],
          low: data.l[i],
          close: data.c[i],
          volume: data.v[i],
        });
      }

      console.log(`[Finnhub] Fetched ${bars.length} bars`);

      // Use shorter cache TTL for intraday timeframes to get fresh data
      const isIntraday = ["m1", "m5", "m15", "m30", "h1", "h4"].includes(
        timeframe,
      );
      const cacheTTL = isIntraday ? 60 : CACHE_TTL.bars; // 1 min for intraday, 24h for daily+

      await this.cache.set(cacheKey, bars, cacheTTL, [
        `symbol:${symbol}`,
        `timeframe:${timeframe}`,
      ]);

      return bars;
    } catch (error) {
      console.error(`[Finnhub] Error fetching bars:`, error);
      throw this.mapError(error);
    }
  }

  async getNews(request: NewsRequest): Promise<NewsItem[]> {
    const { symbol, from, to, limit = 20 } = request;

    const cacheKey = symbol
      ? `news:finnhub:${symbol}:${from || ""}:${to || ""}`
      : `news:finnhub:market:${from || ""}:${to || ""}`;

    const cached = await this.cache.get<NewsItem[]>(cacheKey);
    if (cached) {
      return cached.slice(0, limit);
    }

    // Acquire rate limit token
    await this.rateLimiter.acquire("finnhub");

    try {
      const items = symbol
        ? await this.fetchCompanyNews(symbol, from, to)
        : await this.fetchMarketNews(from, to);

      const limited = items.slice(0, limit);

      await this.cache.set(cacheKey, items, CACHE_TTL.news, [
        symbol ? `symbol:${symbol}` : "market",
      ]);

      return limited;
    } catch (error) {
      console.error(`[Finnhub] Error fetching news:`, error);
      throw this.mapError(error);
    }
  }

  private async fetchCompanyNews(
    symbol: string,
    from?: number,
    to?: number,
  ): Promise<NewsItem[]> {
    const toDate = to ? new Date(to * 1000) : new Date();
    const fromDate = from
      ? new Date(from * 1000)
      : new Date(toDate.getTime() - 7 * 24 * 60 * 60 * 1000); // 7 days back

    const formatDate = (d: Date): string => d.toISOString().split("T")[0];

    const url = new URL(`${this.baseURL}/company-news`);
    url.searchParams.set("symbol", symbol.toUpperCase());
    url.searchParams.set("from", formatDate(fromDate));
    url.searchParams.set("to", formatDate(toDate));
    url.searchParams.set("token", this.apiKey);

    console.log(`[Finnhub] Fetching company news: ${symbol}`);
    const response = await fetch(url.toString());
    await this.handleHttpErrors(response);

    const data: FinnhubNewsItem[] = await response.json();

    return data.map((item) => ({
      id: `finnhub:${item.id}`,
      headline: item.headline,
      summary: item.summary,
      source: item.source,
      url: item.url,
      publishedAt: item.datetime * 1000, // Convert to milliseconds
      symbols: item.related ? [item.related] : undefined,
    }));
  }

  private async fetchMarketNews(
    from?: number,
    to?: number,
  ): Promise<NewsItem[]> {
    const url = new URL(`${this.baseURL}/news`);
    url.searchParams.set("category", "general");
    url.searchParams.set("token", this.apiKey);

    console.log(`[Finnhub] Fetching market news`);
    const response = await fetch(url.toString());
    await this.handleHttpErrors(response);

    const data: FinnhubNewsItem[] = await response.json();

    // Filter by date range if provided
    let filtered = data;
    if (from || to) {
      filtered = data.filter((item) => {
        const timestamp = item.datetime * 1000;
        if (from && timestamp < from * 1000) return false;
        if (to && timestamp > to * 1000) return false;
        return true;
      });
    }

    return filtered.map((item) => ({
      id: `finnhub:${item.id}`,
      headline: item.headline,
      summary: item.summary,
      source: item.source,
      url: item.url,
      publishedAt: item.datetime * 1000,
      symbols: item.related ? [item.related] : undefined,
    }));
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
        "finnhub",
        retryAfter ? parseInt(retryAfter, 10) : undefined,
      );
    }

    if (response.status === 401 || response.status === 403) {
      throw new PermissionDeniedError(
        "finnhub",
        text || "Authentication failed",
      );
    }

    if (response.status >= 500) {
      throw new ProviderUnavailableError("finnhub");
    }

    throw new ProviderError(
      text || "Unknown error",
      "finnhub",
      "HTTP_ERROR",
      response.status,
    );
  }

  private mapError(error: unknown): Error {
    if (error instanceof ProviderError) {
      return error;
    }

    if (error instanceof Error) {
      return new ProviderUnavailableError("finnhub", error);
    }

    return new ProviderError(
      String(error),
      "finnhub",
      "UNKNOWN_ERROR",
    );
  }
}
