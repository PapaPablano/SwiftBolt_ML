// Alpaca Market Data Client
// Provides historical and real-time market data via Alpaca's Market Data API v2
// Documentation: https://docs.alpaca.markets/docs/getting-started-with-alpaca-market-data

import type { DataProviderAbstraction, HistoricalBarsRequest } from "./abstraction.ts";
import type { Bar, Quote, NewsItem } from "./types.ts";
import type { TokenBucketRateLimiter } from "../rate-limiter/token-bucket.ts";
import type { Cache } from "../cache/interface.ts";
import { CACHE_TTL } from "../config/rate-limits.ts";
import {
  ProviderError,
  RateLimitExceededError,
  AuthenticationError,
  ValidationError,
  ServiceUnavailableError,
  InvalidSymbolError
} from "./types.ts";

interface AlpacaBar {
  t: string; // RFC-3339 timestamp
  o: number; // open
  h: number; // high
  l: number; // low
  c: number; // close
  v: number; // volume
  n?: number; // trade count
  vw?: number; // volume weighted average price
}

interface AlpacaBarsResponse {
  bars: Record<string, AlpacaBar[]>;
  next_page_token?: string;
}

interface AlpacaQuote {
  t: string; // timestamp
  ax: string; // ask exchange
  ap: number; // ask price
  as: number; // ask size
  bx: string; // bid exchange
  bp: number; // bid price
  bs: number; // bid size
  c: string[]; // conditions
}

interface AlpacaLatestQuoteResponse {
  symbol: string;
  quote: AlpacaQuote;
}

interface AlpacaSnapshot {
  symbol: string;
  latestTrade: {
    t: string;
    x: string;
    p: number;
    s: number;
    c: string[];
    i: number;
    z: string;
  };
  latestQuote: AlpacaQuote;
  minuteBar: AlpacaBar;
  dailyBar: AlpacaBar;
  prevDailyBar: AlpacaBar;
}

interface AlpacaAsset {
  id: string;
  class: string;
  exchange: string;
  symbol: string;
  name: string;
  status: string;
  tradable: boolean;
  marginable: boolean;
  shortable: boolean;
  easy_to_borrow: boolean;
  fractionable: boolean;
  min_order_size?: string;
  min_trade_increment?: string;
  price_increment?: string;
}

interface AlpacaClock {
  timestamp: string;
  is_open: boolean;
  next_open: string;
  next_close: string;
}

interface AlpacaCalendarDay {
  date: string;
  open: string;
  close: string;
  session_open?: string;
  session_close?: string;
}

interface AlpacaCorporateAction {
  id: string;
  corporate_action_id: string;
  ca_type: string;
  ca_sub_type: string;
  initiating_symbol: string;
  initiating_original_cusip: string;
  target_symbol: string;
  target_original_cusip: string;
  declaration_date: string;
  ex_date: string;
  record_date: string;
  payable_date: string;
  cash: number;
  old_rate: number;
  new_rate: number;
}

export class AlpacaClient implements DataProviderAbstraction {
  private readonly apiKey: string;
  private readonly apiSecret: string;
  private readonly baseUrl = "https://data.alpaca.markets/v2";
  private readonly tradingBaseUrl = "https://api.alpaca.markets/v2";
  private readonly rateLimiter: TokenBucketRateLimiter;
  private readonly cache: Cache;
  private assetsCache: Map<string, AlpacaAsset> | null = null;
  private assetsCacheExpiry = 0;

  constructor(
    apiKey: string,
    apiSecret: string,
    rateLimiter: TokenBucketRateLimiter,
    cache: Cache
  ) {
    this.apiKey = apiKey;
    this.apiSecret = apiSecret;
    this.rateLimiter = rateLimiter;
    this.cache = cache;
  }

  /**
   * Get common headers for Market Data API
   * Uses Trading API authentication (APCA-API-KEY-ID and APCA-API-SECRET-KEY headers)
   */
  private getHeaders(): Record<string, string> {
    return {
      "APCA-API-KEY-ID": this.apiKey,
      "APCA-API-SECRET-KEY": this.apiSecret,
      "Accept": "application/json",
    };
  }

  /**
   * Get real-time quotes for symbols
   * Uses Alpaca's snapshot endpoint for latest data
   */
  async getQuote(symbols: string[]): Promise<Quote[]> {
    if (symbols.length === 0) {
      return [];
    }

    console.log(`[Alpaca] Fetching quotes for ${symbols.length} symbols`);

    try {
      // Acquire rate limit token
      await this.rateLimiter.acquire("alpaca");

      // Use snapshots endpoint for latest data
      const symbolsParam = symbols.join(",");
      const url = `${this.baseUrl}/stocks/snapshots?symbols=${symbolsParam}&feed=iex`;

      const response = await fetch(url, {
        headers: this.getHeaders(),
      });

      if (!response.ok) {
        await this.handleErrorResponse(response);
      }

      const data = await response.json() as Record<string, AlpacaSnapshot>;

      const quotes: Quote[] = [];
      for (const [symbol, snapshot] of Object.entries(data)) {
        if (!snapshot || !snapshot.latestTrade) {
          continue;
        }

        const trade = snapshot.latestTrade;
        const quote = snapshot.latestQuote;
        const prevClose = snapshot.prevDailyBar?.c;

        quotes.push({
          symbol,
          price: trade.p,
          timestamp: Math.floor(new Date(trade.t).getTime() / 1000),
          volume: snapshot.dailyBar?.v || 0,
          high: snapshot.dailyBar?.h,
          low: snapshot.dailyBar?.l,
          open: snapshot.dailyBar?.o,
          previousClose: prevClose,
          change: prevClose ? trade.p - prevClose : undefined,
          changePercent: prevClose ? ((trade.p - prevClose) / prevClose) * 100 : undefined,
        });
      }

      console.log(`[Alpaca] Retrieved ${quotes.length} quotes`);
      return quotes;
    } catch (error) {
      console.error(`[Alpaca] Error fetching quotes:`, error);
      throw error;
    }
  }

  /**
   * Get historical bars (OHLCV data)
   * Supports multiple timeframes and date ranges
   * Automatically handles pagination for large result sets
   */
  async getHistoricalBars(request: HistoricalBarsRequest): Promise<Bar[]> {
    const { symbol, timeframe, start, end } = request;

    // Convert timeframe to Alpaca format
    const alpacaTimeframe = this.convertTimeframe(timeframe);
    
    console.log(`[Alpaca] Fetching historical bars: ${symbol} ${timeframe} (${alpacaTimeframe})`);

    try {
      // Validate symbol before making API call
      const isValid = await this.validateSymbol(symbol);
      if (!isValid) {
        throw new InvalidSymbolError("alpaca", symbol);
      }

      const allBars: Bar[] = [];
      let nextPageToken: string | undefined;
      let pageCount = 0;
      const maxPages = 100; // Safety limit to prevent infinite loops

      do {
        // Acquire rate limit token before each API call
        await this.rateLimiter.acquire("alpaca");

        // Build URL with parameters
        const startDate = this.toUTCISOString(start);
        const endDate = this.toUTCISOString(end);

        // Alpaca API uses /stocks/bars?symbols= not /stocks/{symbol}/bars
        let url = `${this.baseUrl}/stocks/bars?` +
          `symbols=${symbol}&` +
          `timeframe=${alpacaTimeframe}&` +
          `start=${startDate}&` +
          `end=${endDate}&` +
          `limit=10000&` +
          `adjustment=raw&` +
          `feed=sip&` +
          `sort=asc`;

        if (nextPageToken) {
          url += `&page_token=${nextPageToken}`;
        }

        const response = await this.fetchWithRetry(url);

        if (!response.ok) {
          await this.handleErrorResponse(response);
        }

        const data = await response.json() as AlpacaBarsResponse;
        const alpacaBars = data.bars?.[symbol] || [];

        if (alpacaBars.length === 0 && pageCount === 0) {
          console.log(`[Alpaca] No data returned for ${symbol}`);
          return [];
        }

        // Convert Alpaca bars to our Bar format
        const pageBars: Bar[] = alpacaBars.map((bar) => ({
          timestamp: Math.floor(new Date(bar.t).getTime() / 1000),
          open: bar.o,
          high: bar.h,
          low: bar.l,
          close: bar.c,
          volume: bar.v,
        }));

        allBars.push(...pageBars);
        nextPageToken = data.next_page_token;
        pageCount++;

        if (nextPageToken) {
          console.log(`[Alpaca] Fetched page ${pageCount} with ${pageBars.length} bars, continuing...`);
        }

        // Safety check
        if (pageCount >= maxPages) {
          console.warn(`[Alpaca] Reached maximum page limit (${maxPages}) for ${symbol}`);
          break;
        }
      } while (nextPageToken);

      if (allBars.length > 0) {
        const firstDate = new Date(allBars[0].timestamp * 1000).toISOString();
        const lastDate = new Date(allBars[allBars.length - 1].timestamp * 1000).toISOString();
        console.log(`[Alpaca] Retrieved ${allBars.length} bars for ${symbol} ${timeframe} across ${pageCount} page(s) (${firstDate} to ${lastDate})`);
      }

      return allBars;
    } catch (error) {
      console.error(`[Alpaca] Error fetching bars:`, error);
      throw error;
    }
  }

  /**
   * Get news for a symbol
   * Alpaca provides news from multiple sources
   */
  async getNews(request: { symbol: string; limit?: number }): Promise<NewsItem[]> {
    const { symbol, limit = 50 } = request;

    console.log(`[Alpaca] Fetching news for ${symbol}`);

    try {
      // Acquire rate limit token
      await this.rateLimiter.acquire("alpaca");

      const url = `${this.baseUrl}/news?symbols=${symbol}&limit=${limit}&sort=desc`;

      const response = await fetch(url, {
        headers: this.getHeaders(),
      });

      if (!response.ok) {
        await this.handleErrorResponse(response);
      }

      const data = await response.json();
      const newsItems = data.news || [];

      const news: NewsItem[] = newsItems.map((item: any) => ({
        id: item.id.toString(),
        headline: item.headline,
        summary: item.summary || item.headline,
        source: item.source,
        url: item.url,
        publishedAt: Math.floor(new Date(item.created_at).getTime() / 1000),
        symbols: item.symbols || [symbol],
        sentiment: this.mapSentiment(item.sentiment),
      }));

      console.log(`[Alpaca] Retrieved ${news.length} news items`);
      return news;
    } catch (error) {
      console.error(`[Alpaca] Error fetching news:`, error);
      throw error;
    }
  }

  /**
   * Health check - verify API connectivity
   */
  async healthCheck(): Promise<boolean> {
    try {
      // Acquire rate limit token
      await this.rateLimiter.acquire("alpaca");

      // Quick check with AAPL snapshot
      const url = `${this.baseUrl}/stocks/snapshots?symbols=AAPL&feed=iex`;
      const response = await fetch(url, {
        headers: this.getHeaders(),
      });
      return response.ok;
    } catch {
      return false;
    }
  }

  /**
   * Get all tradable assets
   * Results are cached for 1 hour to minimize API calls
   */
  async getAssets(assetClass: "us_equity" | "crypto" = "us_equity"): Promise<AlpacaAsset[]> {
    const now = Date.now();
    
    // Return cached results if still valid
    if (this.assetsCache && now < this.assetsCacheExpiry) {
      return Array.from(this.assetsCache.values());
    }

    console.log(`[Alpaca] Fetching assets (class: ${assetClass})`);

    try {
      // Acquire rate limit token
      await this.rateLimiter.acquire("alpaca");

      const url = `${this.tradingBaseUrl}/assets?asset_class=${assetClass}&status=active`;
      const response = await this.fetchWithRetry(url);

      if (!response.ok) {
        await this.handleErrorResponse(response);
      }

      const assets = await response.json() as AlpacaAsset[];
      
      // Update cache
      this.assetsCache = new Map();
      for (const asset of assets) {
        this.assetsCache.set(asset.symbol, asset);
      }
      this.assetsCacheExpiry = now + (60 * 60 * 1000); // 1 hour

      console.log(`[Alpaca] Cached ${assets.length} assets`);
      return assets;
    } catch (error) {
      console.error(`[Alpaca] Error fetching assets:`, error);
      throw error;
    }
  }

  /**
   * Validate if a symbol is tradable
   * Uses cached assets to minimize API calls
   */
  async validateSymbol(symbol: string): Promise<boolean> {
    try {
      await this.getAssets();
      return this.assetsCache?.has(symbol) ?? false;
    } catch (error) {
      // If assets endpoint fails, assume symbol is valid (fail open)
      console.warn(`[Alpaca] Could not validate symbol ${symbol}, assuming valid:`, error);
      return true;
    }
  }

  /**
   * Get asset details for a symbol
   */
  async getAsset(symbol: string): Promise<AlpacaAsset | null> {
    await this.getAssets();
    return this.assetsCache?.get(symbol) ?? null;
  }

  /**
   * Convert our timeframe format to Alpaca's format
   * Alpaca uses: 1Min, 5Min, 15Min, 30Min, 1Hour, 4Hour, 1Day, 1Week, 1Month
   */
  private convertTimeframe(timeframe: string): string {
    const mapping: Record<string, string> = {
      m1: "1Min",
      m5: "5Min",
      m15: "15Min",
      m30: "30Min",
      h1: "1Hour",
      h4: "4Hour",
      d1: "1Day",
      w1: "1Week",
      mn1: "1Month",
    };

    return mapping[timeframe] || "1Day";
  }

  /**
   * Map Alpaca sentiment to our format
   */
  private mapSentiment(sentiment?: string): "positive" | "negative" | "neutral" {
    if (!sentiment) return "neutral";
    
    const s = sentiment.toLowerCase();
    if (s === "positive" || s === "bullish") return "positive";
    if (s === "negative" || s === "bearish") return "negative";
    return "neutral";
  }

  /**
   * Fetch with automatic retry logic for transient failures
   */
  private async fetchWithRetry(
    url: string,
    maxRetries = 3,
    initialDelayMs = 1000
  ): Promise<Response> {
    let lastError: Error | null = null;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        const response = await fetch(url, {
          headers: this.getHeaders(),
        });

        // Don't retry on client errors (4xx except 429)
        if (response.status >= 400 && response.status < 500 && response.status !== 429) {
          return response;
        }

        // Retry on rate limits and server errors
        if (response.status === 429 || response.status >= 500) {
          if (attempt < maxRetries) {
            const retryAfter = response.headers.get("Retry-After");
            const delayMs = retryAfter 
              ? parseInt(retryAfter) * 1000 
              : initialDelayMs * Math.pow(2, attempt);
            
            console.log(`[Alpaca] Status ${response.status}, retrying in ${delayMs}ms (attempt ${attempt + 1}/${maxRetries})`);
            await this.sleep(delayMs);
            continue;
          }
        }

        return response;
      } catch (error) {
        lastError = error as Error;
        if (attempt < maxRetries) {
          const delayMs = initialDelayMs * Math.pow(2, attempt);
          console.log(`[Alpaca] Network error, retrying in ${delayMs}ms (attempt ${attempt + 1}/${maxRetries}):`, error);
          await this.sleep(delayMs);
        }
      }
    }

    throw new ServiceUnavailableError(
      "alpaca",
      `Failed after ${maxRetries} retries: ${lastError?.message || 'Unknown error'}`
    );
  }

  /**
   * Handle API error responses with specific error types
   */
  private async handleErrorResponse(response: Response): Promise<never> {
    const status = response.status;
    let errorMessage = `Alpaca API error: ${status} ${response.statusText}`;
    let errorData: any = null;

    try {
      errorData = await response.json();
      errorMessage = errorData.message || errorMessage;
    } catch {
      // Ignore JSON parse errors
    }

    // Handle authentication errors
    if (status === 401) {
      throw new AuthenticationError("alpaca", "Invalid or expired API credentials. Check ALPACA_API_KEY and ALPACA_API_SECRET.");
    }

    // Handle permission errors
    if (status === 403) {
      throw new AuthenticationError("alpaca", errorMessage || "Insufficient permissions. Check your API key permissions.");
    }

    // Handle not found (invalid symbol)
    if (status === 404) {
      throw new InvalidSymbolError("alpaca", errorMessage || "Symbol not found");
    }

    // Handle validation errors
    if (status === 400 || status === 422) {
      throw new ValidationError("alpaca", errorMessage || "Invalid request parameters");
    }

    // Handle rate limiting
    if (status === 429) {
      const retryAfter = response.headers.get("Retry-After");
      const retrySeconds = retryAfter ? parseInt(retryAfter) : undefined;
      throw new RateLimitExceededError("alpaca", retrySeconds);
    }

    // Handle server errors
    if (status >= 500) {
      throw new ServiceUnavailableError("alpaca", errorMessage || "Alpaca API temporarily unavailable");
    }

    // Handle other errors
    throw new ProviderError(errorMessage, "alpaca", status.toString(), status);
  }

  /**
   * Convert Unix timestamp to UTC ISO string
   * Ensures all timestamps are explicitly UTC
   */
  private toUTCISOString(timestamp: number): string {
    return new Date(timestamp * 1000).toISOString();
  }

  /**
   * Get market clock status
   * Returns current market open/close status and next open/close times
   */
  async queryMarketClock(): Promise<AlpacaClock> {
    console.log(`[Alpaca] Fetching market clock`);

    try {
      await this.rateLimiter.acquire("alpaca");

      const url = `${this.tradingBaseUrl}/clock`;
      const response = await this.fetchWithRetry(url);

      if (!response.ok) {
        await this.handleErrorResponse(response);
      }

      const clock = await response.json() as AlpacaClock;
      console.log(`[Alpaca] Market is ${clock.is_open ? 'OPEN' : 'CLOSED'}`);
      return clock;
    } catch (error) {
      console.error(`[Alpaca] Error fetching market clock:`, error);
      throw error;
    }
  }

  /**
   * Get market calendar
   * Returns trading days with open/close times for a date range
   */
  async queryMarketCalendar(params: { start: string; end: string }): Promise<AlpacaCalendarDay[]> {
    const { start, end } = params;
    console.log(`[Alpaca] Fetching market calendar: ${start} to ${end}`);

    try {
      await this.rateLimiter.acquire("alpaca");

      const url = `${this.tradingBaseUrl}/calendar?start=${start}&end=${end}`;
      const response = await this.fetchWithRetry(url);

      if (!response.ok) {
        await this.handleErrorResponse(response);
      }

      const calendar = await response.json() as AlpacaCalendarDay[];
      console.log(`[Alpaca] Retrieved ${calendar.length} trading days`);
      return calendar;
    } catch (error) {
      console.error(`[Alpaca] Error fetching market calendar:`, error);
      throw error;
    }
  }

  /**
   * Get corporate actions
   * Returns stock splits, dividends, mergers, etc.
   */
  async queryCorporateActions(params: {
    symbols: string;
    types: string;
    start: string;
    end: string;
  }): Promise<AlpacaCorporateAction[]> {
    const { symbols, types, start, end } = params;
    console.log(`[Alpaca] Fetching corporate actions: ${symbols} (${types})`);

    try {
      await this.rateLimiter.acquire("alpaca");

      const url = `${this.tradingBaseUrl}/corporate_actions/announcements?` +
        `ca_types=${types}&` +
        `since=${start}&` +
        `until=${end}&` +
        `symbols=${symbols}`;

      const response = await this.fetchWithRetry(url);

      if (!response.ok) {
        await this.handleErrorResponse(response);
      }

      const data = await response.json();
      const actions = Array.isArray(data) ? data : (data.data || []);
      console.log(`[Alpaca] Retrieved ${actions.length} corporate actions`);
      return actions as AlpacaCorporateAction[];
    } catch (error) {
      console.error(`[Alpaca] Error fetching corporate actions:`, error);
      throw error;
    }
  }

  /**
   * Sleep utility for retry delays
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
