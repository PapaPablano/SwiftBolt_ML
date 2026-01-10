// Alpaca Market Data Client
// Provides historical and real-time market data via Alpaca's Market Data API v2
// Documentation: https://docs.alpaca.markets/docs/getting-started-with-alpaca-market-data

import type { DataProviderAbstraction, HistoricalBarsRequest, OptionsChainRequest, NewsRequest } from "./abstraction.ts";
import type { Bar, Quote, NewsItem, CryptoBar, CryptoQuote, CryptoSnapshot, OptionsChain, OptionContract } from "./types.ts";
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

export class AlpacaClient implements DataProviderAbstraction {
  private readonly apiKey: string;
  private readonly apiSecret: string;
  private readonly baseUrl = "https://data.alpaca.markets/v2";
  private readonly newsBaseUrl = "https://data.alpaca.markets/v1beta1";
  private readonly cryptoBaseUrl = "https://data.alpaca.markets/v1beta3/crypto";
  private readonly optionsBaseUrl = "https://data.alpaca.markets/v1beta1/options";
  private readonly tradingBaseUrl = "https://api.alpaca.markets/v2";
  private readonly rateLimiter: TokenBucketRateLimiter;
  private readonly cache: Cache;
  private assetsCache: Map<string, AlpacaAsset> | null = null;
  private cryptoAssetsCache: Map<string, AlpacaAsset> | null = null;
  private assetsCacheExpiry = 0;
  private cryptoAssetsCacheExpiry = 0;

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
   * Get historical bars for multiple symbols in a single API call (BATCH OPTIMIZATION)
   * This is 50x more efficient than calling getHistoricalBars() for each symbol individually
   * Alpaca supports up to 100 symbols per request
   */
  async getHistoricalBarsBatch(request: {
    symbols: string[];
    timeframe: string;
    start: number;
    end: number;
  }): Promise<Map<string, Bar[]>> {
    const { symbols, timeframe, start, end } = request;
    
    if (symbols.length === 0) {
      return new Map();
    }

    // Alpaca supports up to 100 symbols per request
    if (symbols.length > 100) {
      throw new ValidationError("alpaca", `Too many symbols (${symbols.length}). Maximum is 100 per batch.`);
    }

    const alpacaTimeframe = this.convertTimeframe(timeframe);
    const symbolsParam = symbols.join(",");
    
    console.log(`[Alpaca] Fetching historical bars BATCH: ${symbols.length} symbols, ${timeframe} (${alpacaTimeframe})`);

    try {
      const resultMap = new Map<string, Bar[]>();
      let nextPageToken: string | undefined;
      let pageCount = 0;
      const maxPages = 100;

      do {
        // Acquire rate limit token (1 token for entire batch!)
        await this.rateLimiter.acquire("alpaca");

        const startDate = this.toUTCISOString(start);
        const endDate = this.toUTCISOString(end);

        let url = `${this.baseUrl}/stocks/bars?` +
          `symbols=${symbolsParam}&` +
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
        
        // Process bars for each symbol
        for (const symbol of symbols) {
          const alpacaBars = data.bars?.[symbol] || [];
          
          if (alpacaBars.length > 0) {
            const bars: Bar[] = alpacaBars.map((bar) => ({
              timestamp: Math.floor(new Date(bar.t).getTime() / 1000),
              open: bar.o,
              high: bar.h,
              low: bar.l,
              close: bar.c,
              volume: bar.v,
            }));

            // Append to existing bars for this symbol
            const existing = resultMap.get(symbol) || [];
            resultMap.set(symbol, [...existing, ...bars]);
          }
        }

        nextPageToken = data.next_page_token;
        pageCount++;

        if (nextPageToken) {
          console.log(`[Alpaca] Batch fetched page ${pageCount}, continuing...`);
        }

        if (pageCount >= maxPages) {
          console.warn(`[Alpaca] Reached maximum page limit (${maxPages}) for batch`);
          break;
        }
      } while (nextPageToken);

      // Log results
      let totalBars = 0;
      for (const [symbol, bars] of resultMap.entries()) {
        totalBars += bars.length;
        if (bars.length > 0) {
          const firstDate = new Date(bars[0].timestamp * 1000).toISOString();
          const lastDate = new Date(bars[bars.length - 1].timestamp * 1000).toISOString();
          console.log(`[Alpaca] ${symbol}: ${bars.length} bars (${firstDate} to ${lastDate})`);
        }
      }
      
      console.log(`[Alpaca] Batch complete: ${symbols.length} symbols, ${totalBars} total bars across ${pageCount} page(s)`);
      console.log(`[Alpaca] API efficiency: 1 request for ${symbols.length} symbols (${symbols.length}x savings!)`);

      return resultMap;
    } catch (error) {
      console.error(`[Alpaca] Error fetching batch bars:`, error);
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

      const url = `${this.newsBaseUrl}/news?symbols=${symbol}&limit=${limit}&sort=desc`;

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

  // ============================================================================
  // CRYPTO DATA METHODS (v1beta3 API)
  // ============================================================================

  /**
   * Get crypto assets (tradable cryptocurrencies)
   * Results are cached for 1 hour
   */
  async getCryptoAssets(): Promise<AlpacaAsset[]> {
    const now = Date.now();

    if (this.cryptoAssetsCache && now < this.cryptoAssetsCacheExpiry) {
      return Array.from(this.cryptoAssetsCache.values());
    }

    console.log(`[Alpaca] Fetching crypto assets`);

    try {
      await this.rateLimiter.acquire("alpaca");

      const url = `${this.tradingBaseUrl}/assets?asset_class=crypto&status=active`;
      const response = await this.fetchWithRetry(url);

      if (!response.ok) {
        await this.handleErrorResponse(response);
      }

      const assets = await response.json() as AlpacaAsset[];

      this.cryptoAssetsCache = new Map();
      for (const asset of assets) {
        this.cryptoAssetsCache.set(asset.symbol, asset);
      }
      this.cryptoAssetsCacheExpiry = now + (60 * 60 * 1000);

      console.log(`[Alpaca] Cached ${assets.length} crypto assets`);
      return assets;
    } catch (error) {
      console.error(`[Alpaca] Error fetching crypto assets:`, error);
      throw error;
    }
  }

  /**
   * Get real-time crypto quotes
   * @param symbols - Crypto symbols in format "BTC/USD", "ETH/USD", etc.
   */
  async getCryptoQuotes(symbols: string[]): Promise<CryptoQuote[]> {
    if (symbols.length === 0) {
      return [];
    }

    console.log(`[Alpaca] Fetching crypto quotes for ${symbols.length} symbols`);

    try {
      await this.rateLimiter.acquire("alpaca");

      // Alpaca crypto uses symbols like "BTC/USD" - need to encode the slash
      const symbolsParam = symbols.map(s => encodeURIComponent(s)).join(",");
      const url = `${this.cryptoBaseUrl}/us/latest/quotes?symbols=${symbolsParam}`;

      const response = await fetch(url, {
        headers: this.getHeaders(),
      });

      if (!response.ok) {
        await this.handleErrorResponse(response);
      }

      const data = await response.json();
      const quotes: CryptoQuote[] = [];

      for (const [symbol, quoteData] of Object.entries(data.quotes || {})) {
        const q = quoteData as any;
        quotes.push({
          symbol,
          price: (q.ap + q.bp) / 2, // midpoint
          timestamp: Math.floor(new Date(q.t).getTime() / 1000),
          bidPrice: q.bp,
          bidSize: q.bs,
          askPrice: q.ap,
          askSize: q.as,
        });
      }

      console.log(`[Alpaca] Retrieved ${quotes.length} crypto quotes`);
      return quotes;
    } catch (error) {
      console.error(`[Alpaca] Error fetching crypto quotes:`, error);
      throw error;
    }
  }

  /**
   * Get crypto snapshots (latest trade, quote, and bars)
   * @param symbols - Crypto symbols in format "BTC/USD", "ETH/USD", etc.
   */
  async getCryptoSnapshots(symbols: string[]): Promise<CryptoSnapshot[]> {
    if (symbols.length === 0) {
      return [];
    }

    console.log(`[Alpaca] Fetching crypto snapshots for ${symbols.length} symbols`);

    try {
      await this.rateLimiter.acquire("alpaca");

      const symbolsParam = symbols.map(s => encodeURIComponent(s)).join(",");
      const url = `${this.cryptoBaseUrl}/us/snapshots?symbols=${symbolsParam}`;

      const response = await fetch(url, {
        headers: this.getHeaders(),
      });

      if (!response.ok) {
        await this.handleErrorResponse(response);
      }

      const data = await response.json();
      const snapshots: CryptoSnapshot[] = [];

      for (const [symbol, snap] of Object.entries(data.snapshots || {})) {
        const s = snap as any;
        snapshots.push({
          symbol,
          latestTrade: {
            price: s.latestTrade?.p || 0,
            size: s.latestTrade?.s || 0,
            timestamp: s.latestTrade?.t ? Math.floor(new Date(s.latestTrade.t).getTime() / 1000) : 0,
            exchange: s.latestTrade?.x || "",
          },
          latestQuote: {
            symbol,
            price: s.latestQuote ? (s.latestQuote.ap + s.latestQuote.bp) / 2 : 0,
            timestamp: s.latestQuote?.t ? Math.floor(new Date(s.latestQuote.t).getTime() / 1000) : 0,
            bidPrice: s.latestQuote?.bp,
            bidSize: s.latestQuote?.bs,
            askPrice: s.latestQuote?.ap,
            askSize: s.latestQuote?.as,
          },
          minuteBar: s.minuteBar ? this.convertCryptoBar(s.minuteBar) : undefined,
          dailyBar: s.dailyBar ? this.convertCryptoBar(s.dailyBar) : undefined,
          prevDailyBar: s.prevDailyBar ? this.convertCryptoBar(s.prevDailyBar) : undefined,
        });
      }

      console.log(`[Alpaca] Retrieved ${snapshots.length} crypto snapshots`);
      return snapshots;
    } catch (error) {
      console.error(`[Alpaca] Error fetching crypto snapshots:`, error);
      throw error;
    }
  }

  /**
   * Get historical crypto bars
   * @param symbol - Crypto symbol in format "BTC/USD"
   */
  async getCryptoHistoricalBars(request: {
    symbol: string;
    timeframe: string;
    start: number;
    end: number;
  }): Promise<CryptoBar[]> {
    const { symbol, timeframe, start, end } = request;
    const alpacaTimeframe = this.convertTimeframe(timeframe);

    console.log(`[Alpaca] Fetching crypto historical bars: ${symbol} ${timeframe}`);

    try {
      const allBars: CryptoBar[] = [];
      let nextPageToken: string | undefined;
      let pageCount = 0;
      const maxPages = 100;

      do {
        await this.rateLimiter.acquire("alpaca");

        const startDate = this.toUTCISOString(start);
        const endDate = this.toUTCISOString(end);
        const encodedSymbol = encodeURIComponent(symbol);

        let url = `${this.cryptoBaseUrl}/us/bars?` +
          `symbols=${encodedSymbol}&` +
          `timeframe=${alpacaTimeframe}&` +
          `start=${startDate}&` +
          `end=${endDate}&` +
          `limit=10000&` +
          `sort=asc`;

        if (nextPageToken) {
          url += `&page_token=${nextPageToken}`;
        }

        const response = await this.fetchWithRetry(url);

        if (!response.ok) {
          await this.handleErrorResponse(response);
        }

        const data = await response.json();
        const cryptoBars = data.bars?.[symbol] || [];

        if (cryptoBars.length === 0 && pageCount === 0) {
          console.log(`[Alpaca] No crypto data returned for ${symbol}`);
          return [];
        }

        const pageBars: CryptoBar[] = cryptoBars.map((bar: any) => this.convertCryptoBar(bar));
        allBars.push(...pageBars);
        nextPageToken = data.next_page_token;
        pageCount++;

        if (nextPageToken) {
          console.log(`[Alpaca] Crypto fetched page ${pageCount} with ${pageBars.length} bars, continuing...`);
        }

        if (pageCount >= maxPages) {
          console.warn(`[Alpaca] Reached maximum page limit for crypto ${symbol}`);
          break;
        }
      } while (nextPageToken);

      console.log(`[Alpaca] Retrieved ${allBars.length} crypto bars for ${symbol}`);
      return allBars;
    } catch (error) {
      console.error(`[Alpaca] Error fetching crypto bars:`, error);
      throw error;
    }
  }

  /**
   * Convert Alpaca crypto bar to our format
   */
  private convertCryptoBar(bar: any): CryptoBar {
    return {
      timestamp: Math.floor(new Date(bar.t).getTime() / 1000),
      open: bar.o,
      high: bar.h,
      low: bar.l,
      close: bar.c,
      volume: bar.v,
      vwap: bar.vw,
      tradeCount: bar.n,
    };
  }

  // ============================================================================
  // OPTIONS DATA METHODS (v1beta1 API)
  // ============================================================================

  /**
   * Get options chain for an underlying symbol
   * Implements the DataProviderAbstraction interface
   */
  async getOptionsChain(request: OptionsChainRequest): Promise<OptionsChain> {
    const { underlying, expiration } = request;

    console.log(`[Alpaca] Fetching options chain for ${underlying}`);

    try {
      await this.rateLimiter.acquire("alpaca");

      // First, get available option contracts for this underlying
      let url = `${this.optionsBaseUrl}/snapshots/${underlying}?feed=indicative`;

      if (expiration) {
        const expDate = new Date(expiration * 1000).toISOString().split('T')[0];
        url += `&expiration_date=${expDate}`;
      }

      const response = await fetch(url, {
        headers: this.getHeaders(),
      });

      if (!response.ok) {
        await this.handleErrorResponse(response);
      }

      const data = await response.json();
      const snapshots = data.snapshots || {};

      const calls: OptionContract[] = [];
      const puts: OptionContract[] = [];
      const expirations = new Set<number>();

      for (const [optionSymbol, snapshot] of Object.entries(snapshots)) {
        const s = snapshot as any;
        const contract = this.parseOptionContract(optionSymbol, s);

        if (contract) {
          expirations.add(contract.expiration);
          if (contract.type === "call") {
            calls.push(contract);
          } else {
            puts.push(contract);
          }
        }
      }

      // Sort by strike price
      calls.sort((a, b) => a.strike - b.strike);
      puts.sort((a, b) => a.strike - b.strike);

      console.log(`[Alpaca] Retrieved ${calls.length} calls and ${puts.length} puts for ${underlying}`);

      return {
        underlying,
        timestamp: Math.floor(Date.now() / 1000),
        expirations: Array.from(expirations).sort((a, b) => a - b),
        calls,
        puts,
      };
    } catch (error) {
      console.error(`[Alpaca] Error fetching options chain:`, error);
      throw error;
    }
  }

  /**
   * Get quotes for specific option contracts
   * @param optionSymbols - Option symbols like "AAPL250117C00150000"
   */
  async getOptionsQuotes(optionSymbols: string[]): Promise<OptionContract[]> {
    if (optionSymbols.length === 0) {
      return [];
    }

    console.log(`[Alpaca] Fetching quotes for ${optionSymbols.length} option contracts`);

    try {
      await this.rateLimiter.acquire("alpaca");

      const symbolsParam = optionSymbols.join(",");
      const url = `${this.optionsBaseUrl}/quotes/latest?symbols=${symbolsParam}&feed=indicative`;

      const response = await fetch(url, {
        headers: this.getHeaders(),
      });

      if (!response.ok) {
        await this.handleErrorResponse(response);
      }

      const data = await response.json();
      const contracts: OptionContract[] = [];

      for (const [symbol, quoteData] of Object.entries(data.quotes || {})) {
        const q = quoteData as any;
        const contract = this.parseOptionSymbol(symbol);

        if (contract) {
          contracts.push({
            ...contract,
            bid: q.bp || 0,
            ask: q.ap || 0,
            last: q.bp && q.ap ? (q.bp + q.ap) / 2 : 0,
            mark: q.bp && q.ap ? (q.bp + q.ap) / 2 : 0,
            volume: 0,
            openInterest: 0,
          });
        }
      }

      console.log(`[Alpaca] Retrieved ${contracts.length} option quotes`);
      return contracts;
    } catch (error) {
      console.error(`[Alpaca] Error fetching option quotes:`, error);
      throw error;
    }
  }

  /**
   * Get historical bars for option contracts
   */
  async getOptionsHistoricalBars(request: {
    optionSymbol: string;
    timeframe: string;
    start: number;
    end: number;
  }): Promise<Bar[]> {
    const { optionSymbol, timeframe, start, end } = request;
    const alpacaTimeframe = this.convertTimeframe(timeframe);

    console.log(`[Alpaca] Fetching option bars: ${optionSymbol} ${timeframe}`);

    try {
      await this.rateLimiter.acquire("alpaca");

      const startDate = this.toUTCISOString(start);
      const endDate = this.toUTCISOString(end);

      const url = `${this.optionsBaseUrl}/bars?` +
        `symbols=${optionSymbol}&` +
        `timeframe=${alpacaTimeframe}&` +
        `start=${startDate}&` +
        `end=${endDate}&` +
        `limit=10000`;

      const response = await this.fetchWithRetry(url);

      if (!response.ok) {
        await this.handleErrorResponse(response);
      }

      const data = await response.json();
      const bars = data.bars?.[optionSymbol] || [];

      const result: Bar[] = bars.map((bar: any) => ({
        timestamp: Math.floor(new Date(bar.t).getTime() / 1000),
        open: bar.o,
        high: bar.h,
        low: bar.l,
        close: bar.c,
        volume: bar.v,
      }));

      console.log(`[Alpaca] Retrieved ${result.length} option bars for ${optionSymbol}`);
      return result;
    } catch (error) {
      console.error(`[Alpaca] Error fetching option bars:`, error);
      throw error;
    }
  }

  /**
   * Parse option symbol to extract contract details
   * Format: AAPL250117C00150000 (underlying + YYMMDD + C/P + strike*1000)
   */
  private parseOptionSymbol(optionSymbol: string): Omit<OptionContract, 'bid' | 'ask' | 'last' | 'mark' | 'volume' | 'openInterest'> | null {
    // Match pattern: UNDERLYING + YYMMDD + C/P + STRIKE
    const match = optionSymbol.match(/^([A-Z]+)(\d{6})([CP])(\d{8})$/);

    if (!match) {
      console.warn(`[Alpaca] Could not parse option symbol: ${optionSymbol}`);
      return null;
    }

    const [, underlying, dateStr, typeChar, strikeStr] = match;

    // Parse date: YYMMDD
    const year = 2000 + parseInt(dateStr.substring(0, 2));
    const month = parseInt(dateStr.substring(2, 4)) - 1;
    const day = parseInt(dateStr.substring(4, 6));
    const expiration = Math.floor(new Date(year, month, day).getTime() / 1000);

    // Parse strike (stored as strike * 1000)
    const strike = parseInt(strikeStr) / 1000;

    return {
      symbol: optionSymbol,
      underlying,
      strike,
      expiration,
      type: typeChar === "C" ? "call" : "put",
    };
  }

  /**
   * Parse option contract from snapshot data
   */
  private parseOptionContract(optionSymbol: string, snapshot: any): OptionContract | null {
    const base = this.parseOptionSymbol(optionSymbol);
    if (!base) return null;

    const quote = snapshot.latestQuote || {};
    const trade = snapshot.latestTrade || {};
    const greeks = snapshot.greeks || {};

    return {
      ...base,
      bid: quote.bp || 0,
      ask: quote.ap || 0,
      last: trade.p || 0,
      mark: quote.bp && quote.ap ? (quote.bp + quote.ap) / 2 : trade.p || 0,
      volume: snapshot.dailyBar?.v || 0,
      openInterest: snapshot.openInterest || 0,
      delta: greeks.delta,
      gamma: greeks.gamma,
      theta: greeks.theta,
      vega: greeks.vega,
      rho: greeks.rho,
      impliedVolatility: snapshot.impliedVolatility,
      lastTradeTime: trade.t ? Math.floor(new Date(trade.t).getTime() / 1000) : undefined,
    };
  }

  // ============================================================================
  // ENHANCED NEWS METHODS
  // ============================================================================

  /**
   * Get news with advanced filtering options
   * Enhanced version with date range and multi-symbol support
   */
  async getNewsAdvanced(request: NewsRequest): Promise<NewsItem[]> {
    const { symbol, from, to, limit = 50 } = request;

    console.log(`[Alpaca] Fetching news (advanced)${symbol ? ` for ${symbol}` : ''}`);

    try {
      await this.rateLimiter.acquire("alpaca");

      let url = `${this.newsBaseUrl}/news?limit=${limit}&sort=desc`;

      if (symbol) {
        url += `&symbols=${symbol}`;
      }

      if (from) {
        url += `&start=${this.toUTCISOString(from)}`;
      }

      if (to) {
        url += `&end=${this.toUTCISOString(to)}`;
      }

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
        symbols: item.symbols || (symbol ? [symbol] : []),
        sentiment: this.mapSentiment(item.sentiment),
      }));

      console.log(`[Alpaca] Retrieved ${news.length} news items (advanced)`);
      return news;
    } catch (error) {
      console.error(`[Alpaca] Error fetching news:`, error);
      throw error;
    }
  }

  /**
   * Get news for multiple symbols at once
   */
  async getMultiSymbolNews(symbols: string[], limit: number = 50): Promise<NewsItem[]> {
    if (symbols.length === 0) {
      return [];
    }

    console.log(`[Alpaca] Fetching news for ${symbols.length} symbols`);

    try {
      await this.rateLimiter.acquire("alpaca");

      const symbolsParam = symbols.join(",");
      const url = `${this.newsBaseUrl}/news?symbols=${symbolsParam}&limit=${limit}&sort=desc`;

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
        symbols: item.symbols || [],
        sentiment: this.mapSentiment(item.sentiment),
      }));

      console.log(`[Alpaca] Retrieved ${news.length} news items for ${symbols.length} symbols`);
      return news;
    } catch (error) {
      console.error(`[Alpaca] Error fetching multi-symbol news:`, error);
      throw error;
    }
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
   * Sleep utility for retry delays
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
