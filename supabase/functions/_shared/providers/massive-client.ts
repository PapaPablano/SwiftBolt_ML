// MassiveClient: DataProviderAbstraction implementation for Polygon.io (Massive) API
// Includes strict 5 req/min rate limiting, caching, and unified error handling

import type {
  DataProviderAbstraction,
  HistoricalBarsRequest,
  NewsRequest,
  OptionsChainRequest,
} from "./abstraction.ts";
import type { Bar, NewsItem, OptionContract, OptionsChain, OptionType, Quote, FuturesRoot, FuturesContract, FuturesChain, FuturesSector } from "./types.ts";
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

interface PolygonOptionDetails {
  contract_type: string; // "call" or "put"
  exercise_style: string;
  expiration_date: string; // "YYYY-MM-DD"
  shares_per_contract: number;
  strike_price: number;
  ticker: string; // Full option symbol
}

interface PolygonOptionQuote {
  ask: number;
  ask_size: number;
  bid: number;
  bid_size: number;
  last_updated: number; // Unix timestamp (nanoseconds)
}

interface PolygonOptionTrade {
  conditions: number[];
  exchange: number;
  price: number;
  sip_timestamp: number; // Unix timestamp (nanoseconds)
  size: number;
}

interface PolygonOptionGreeks {
  delta?: number;
  gamma?: number;
  theta?: number;
  vega?: number;
}

interface PolygonOptionDay {
  change: number;
  change_percent: number;
  close: number;
  high: number;
  last_updated: number; // Unix timestamp (milliseconds)
  low: number;
  open: number;
  previous_close: number;
  volume: number;
  vwap: number;
}

interface PolygonOptionContract {
  break_even_price: number;
  day?: PolygonOptionDay;
  details: PolygonOptionDetails;
  greeks?: PolygonOptionGreeks;
  implied_volatility?: number;
  last_quote?: PolygonOptionQuote;
  last_trade?: PolygonOptionTrade;
  open_interest?: number;
  underlying_asset?: {
    change_to_break_even?: number;
    last_updated?: number;
    price?: number;
    ticker?: string;
    timeframe?: string;
    value?: number;
  };
}

interface PolygonOptionsChainResponse {
  status: string;
  results?: PolygonOptionContract[];
  next_url?: string;
  request_id: string;
  count?: number;
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
    url.searchParams.set("adjusted", "false");  // ALWAYS use unadjusted prices
    url.searchParams.set("sort", "asc");
    url.searchParams.set("limit", "50000"); // Max limit
    url.searchParams.set("apiKey", this.apiKey);

    try {
      console.log(`[Massive] Fetching candles: ${symbol} ${timeframe}`);
      const response = await fetch(url.toString());
      await this.handleHttpErrors(response);

      const data: PolygonAggregatesResponse = await response.json();

      if (data.status === "ERROR") {
        console.error(`[Massive] Polygon ERROR for ${symbol}:`, data);
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

      // Use shorter cache TTL for intraday timeframes
      const isIntraday = ["m1", "m5", "m15", "m30", "h1", "h4"].includes(timeframe);
      const cacheTTL = isIntraday ? 300 : CACHE_TTL.bars; // 5 min for intraday, 24h for daily+
      
      await this.cache.set(cacheKey, bars, cacheTTL, [
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

  async getOptionsChain(request: OptionsChainRequest): Promise<OptionsChain> {
    const { underlying, expiration } = request;
    const cacheKey = `options:massive:${underlying}:${expiration || "all"}`;
    const cached = await this.cache.get<OptionsChain>(cacheKey);

    if (cached) {
      return cached;
    }

    // Acquire rate limit token (strict 5/min limit)
    await this.rateLimiter.acquire("massive");

    const ticker = underlying.toUpperCase();
    const url = new URL(`${this.baseURL}/v3/snapshot/options/${ticker}`);

    // Add optional filters
    if (expiration) {
      // Convert Unix timestamp to YYYY-MM-DD format
      const expirationDate = new Date(expiration * 1000).toISOString().split("T")[0];
      url.searchParams.set("expiration_date", expirationDate);
    }

    // Set limit to max to get full chain
    url.searchParams.set("limit", "250");
    url.searchParams.set("apiKey", this.apiKey);

    try {
      console.log(`[Massive] Fetching options chain: ${underlying}`);
      const response = await fetch(url.toString());
      await this.handleHttpErrors(response);

      const data: PolygonOptionsChainResponse = await response.json();

      if (data.status !== "OK" || !data.results || data.results.length === 0) {
        console.log(`[Massive] No options data available for ${underlying}`);
        return {
          underlying,
          timestamp: Date.now(),
          expirations: [],
          calls: [],
          puts: [],
        };
      }

      // Transform to unified OptionsChain format
      const calls: OptionContract[] = [];
      const puts: OptionContract[] = [];
      const expirationSet = new Set<number>();

      for (const contract of data.results) {
        const expirationTimestamp = Math.floor(
          new Date(contract.details.expiration_date).getTime() / 1000
        );
        expirationSet.add(expirationTimestamp);

        const optionContract: OptionContract = {
          symbol: contract.details.ticker,
          underlying: ticker,
          strike: contract.details.strike_price,
          expiration: expirationTimestamp,
          type: contract.details.contract_type.toLowerCase() as OptionType,
          bid: contract.last_quote?.bid || 0,
          ask: contract.last_quote?.ask || 0,
          last: contract.last_trade?.price || contract.day?.close || 0,
          mark: contract.last_quote
            ? (contract.last_quote.bid + contract.last_quote.ask) / 2
            : 0,
          volume: contract.day?.volume || 0,
          openInterest: contract.open_interest || 0,
          delta: contract.greeks?.delta,
          gamma: contract.greeks?.gamma,
          theta: contract.greeks?.theta,
          vega: contract.greeks?.vega,
          impliedVolatility: contract.implied_volatility,
          lastTradeTime: contract.last_trade
            ? Math.floor(contract.last_trade.sip_timestamp / 1_000_000)
            : undefined,
          changePercent: contract.day?.change_percent,
          change: contract.day?.change,
        };

        if (contract.details.contract_type.toLowerCase() === "call") {
          calls.push(optionContract);
        } else {
          puts.push(optionContract);
        }
      }

      const optionsChain: OptionsChain = {
        underlying: ticker,
        timestamp: Date.now(),
        expirations: Array.from(expirationSet).sort((a, b) => a - b),
        calls,
        puts,
      };

      console.log(
        `[Massive] Fetched ${calls.length} calls and ${puts.length} puts for ${underlying}`
      );

      await this.cache.set(cacheKey, optionsChain, CACHE_TTL.quote, [
        `symbol:${underlying}`,
        "options",
      ]);

      return optionsChain;
    } catch (error) {
      console.error(`[Massive] Error fetching options chain:`, error);
      throw this.mapError(error);
    }
  }

  // ============================================================================
  // FUTURES METHODS
  // ============================================================================

  async getFuturesRoots(sector?: FuturesSector): Promise<FuturesRoot[]> {
    const cacheKey = `futures_roots:massive:${sector || "all"}`;
    const cached = await this.cache.get<FuturesRoot[]>(cacheKey);

    if (cached) {
      return cached;
    }

    await this.rateLimiter.acquire("massive");

    try {
      // Polygon/Massive doesn't have a dedicated futures roots endpoint
      // We'll use a curated list for MVP and enhance with API data later
      const roots: FuturesRoot[] = [
        // US Index Futures
        { symbol: "ES", name: "E-mini S&P 500", exchange: "CME", sector: "indices", tickSize: 0.25, pointValue: 50, currency: "USD" },
        { symbol: "NQ", name: "E-mini NASDAQ-100", exchange: "CME", sector: "indices", tickSize: 0.25, pointValue: 20, currency: "USD" },
        { symbol: "RTY", name: "E-mini Russell 2000", exchange: "CME", sector: "indices", tickSize: 0.1, pointValue: 50, currency: "USD" },
        { symbol: "YM", name: "E-mini Dow ($5)", exchange: "CBOT", sector: "indices", tickSize: 1, pointValue: 5, currency: "USD" },
        { symbol: "EMD", name: "E-mini S&P MidCap 400", exchange: "CME", sector: "indices", tickSize: 0.1, pointValue: 100, currency: "USD" },
        // Metals Futures
        { symbol: "GC", name: "Gold", exchange: "COMEX", sector: "metals", tickSize: 0.1, pointValue: 100, currency: "USD" },
        { symbol: "SI", name: "Silver", exchange: "COMEX", sector: "metals", tickSize: 0.005, pointValue: 5000, currency: "USD" },
        { symbol: "HG", name: "Copper", exchange: "COMEX", sector: "metals", tickSize: 0.0005, pointValue: 25000, currency: "USD" },
      ];

      const filtered = sector ? roots.filter(r => r.sector === sector) : roots;
      
      await this.cache.set(cacheKey, filtered, CACHE_TTL.bars, ["futures", "roots"]);
      return filtered;
    } catch (error) {
      console.error(`[Massive] Error fetching futures roots:`, error);
      throw this.mapError(error);
    }
  }

  async getFuturesChain(root: string): Promise<FuturesChain> {
    const cacheKey = `futures_chain:massive:${root}`;
    const cached = await this.cache.get<FuturesChain>(cacheKey);

    if (cached) {
      return cached;
    }

    await this.rateLimiter.acquire("massive");

    try {
      // Get the root info
      const roots = await this.getFuturesRoots();
      const rootInfo = roots.find(r => r.symbol === root.toUpperCase());
      
      if (!rootInfo) {
        throw new Error(`Unknown futures root: ${root}`);
      }

      // Generate contracts for the next 12 months
      const contracts: FuturesContract[] = [];
      const now = new Date();
      const currentYear = now.getFullYear();
      
      // CME standard contract months per product
      const contractMonths = this.getContractMonths(root);
      
      for (let year = currentYear; year <= currentYear + 2; year++) {
        for (const month of contractMonths) {
          const expiryDate = this.calculateExpiryDate(root, year, month);
          const contractCode = this.getMonthCode(month) + String(year).slice(-2);
          
          contracts.push({
            symbol: `${root}${contractCode}`,
            rootSymbol: root,
            contractCode,
            expiryMonth: month,
            expiryYear: year,
            lastTradeDate: expiryDate?.toISOString().split("T")[0],
            isActive: expiryDate ? expiryDate > now : true,
            isSpot: false, // Will be determined by volume/OI later
          });
        }
      }

      // Sort by expiry
      contracts.sort((a, b) => {
        if (a.expiryYear !== b.expiryYear) return a.expiryYear - b.expiryYear;
        return a.expiryMonth - b.expiryMonth;
      });

      // Mark first active as spot
      const firstActive = contracts.find(c => c.isActive);
      if (firstActive) {
        firstActive.isSpot = true;
      }

      // Generate continuous aliases
      const continuousAliases = contracts
        .filter(c => c.isActive)
        .slice(0, 4)
        .map((c, i) => ({
          depth: i + 1,
          alias: `${root}${i + 1}!`,
          contract: c,
        }));

      const chain: FuturesChain = {
        root: rootInfo,
        contracts,
        continuousAliases,
      };

      await this.cache.set(cacheKey, chain, CACHE_TTL.bars, [
        `futures:${root}`,
        "chain",
      ]);

      return chain;
    } catch (error) {
      console.error(`[Massive] Error fetching futures chain for ${root}:`, error);
      throw this.mapError(error);
    }
  }

  async getFuturesContract(contractSymbol: string): Promise<FuturesContract | null> {
    // Extract root from contract symbol (e.g., "GCZ25" -> "GC")
    const match = contractSymbol.match(/^([A-Z]{1,4})([FGHJKMNQUVXZ])(\d{2})$/);
    if (!match) {
      return null;
    }

    const [, root, monthCode, yearSuffix] = match;
    const chain = await this.getFuturesChain(root);
    return chain.contracts.find(c => c.symbol === contractSymbol) || null;
  }

  private getContractMonths(root: string): number[] {
    // Standard CME contract months
    const monthMap: Record<string, number[]> = {
      "ES": [3, 6, 9, 12], // Quarterly
      "NQ": [3, 6, 9, 12],
      "RTY": [3, 6, 9, 12],
      "YM": [3, 6, 9, 12],
      "EMD": [3, 6, 9, 12],
      "GC": [2, 4, 6, 8, 10, 12], // Feb, Apr, Jun, Aug, Oct, Dec
      "SI": [3, 5, 7, 9, 12],
      "HG": [3, 5, 7, 9, 12],
    };
    
    return monthMap[root] || [3, 6, 9, 12];
  }

  private getMonthCode(month: number): string {
    const codes = ["F", "G", "H", "J", "K", "M", "N", "Q", "U", "V", "X", "Z"];
    return codes[month - 1];
  }

  private calculateExpiryDate(root: string, year: number, month: number): Date | null {
    // Simplified expiry calculation - for production, use CME calendar data
    const lastDay = new Date(year, month, 0);
    
    // Most CME contracts expire on the third Friday
    // or have specific rules per product
    const dayOfWeek = lastDay.getDay();
    const offset = (dayOfWeek + 5) % 7; // Days since last Friday
    const thirdFriday = new Date(year, month - 1, lastDay.getDate() - offset - 7);
    
    return thirdFriday;
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
