// YahooFinanceClient: DataProviderAbstraction implementation for Yahoo Finance
// Free options data with 15-minute delay
// Real-time intraday candle data (no delay!)
// Greeks calculated from Black-Scholes model

import type {
  HistoricalBarsRequest,
  OptionsChainRequest,
} from "./abstraction.ts";
import type { Bar, OptionContract, OptionsChain, OptionType } from "./types.ts";
import type { Cache } from "../cache/interface.ts";
import { CACHE_TTL } from "../config/rate-limits.ts";

// Yahoo Finance chart response interfaces
interface YahooChartResult {
  meta: {
    currency: string;
    symbol: string;
    exchangeName: string;
    regularMarketPrice: number;
    regularMarketTime: number;
  };
  timestamp: number[];
  indicators: {
    quote: Array<{
      open: number[];
      high: number[];
      low: number[];
      close: number[];
      volume: number[];
    }>;
  };
}

interface YahooChartResponse {
  chart: {
    result: YahooChartResult[] | null;
    error: { code: string; description: string } | null;
  };
}

// Map our timeframes to Yahoo Finance intervals
const TIMEFRAME_TO_YAHOO_INTERVAL: Record<string, string> = {
  m1: "1m",
  m5: "5m",
  m15: "15m",
  m30: "30m",
  h1: "1h",
  h4: "4h", // Yahoo doesn't support 4h, we'll use 1h and aggregate
  d1: "1d",
  w1: "1wk",
  mn1: "1mo",
};

// Yahoo Finance range limits by interval
const YAHOO_RANGE_LIMITS: Record<string, string> = {
  "1m": "7d", // 1-minute data available for last 7 days
  "5m": "60d", // 5-minute data available for last 60 days
  "15m": "60d", // 15-minute data available for last 60 days
  "30m": "60d", // 30-minute data available for last 60 days
  "1h": "730d", // 1-hour data available for last 2 years
  "1d": "max", // Daily data available for max history
  "1wk": "max", // Weekly data available for max history
  "1mo": "max", // Monthly data available for max history
};

// Yahoo Finance doesn't need rate limiting - it's very generous with free tier
// But we'll still use caching to be respectful and improve performance

interface YahooOptionContract {
  contractSymbol: string;
  strike: number;
  currency: string;
  lastPrice: number;
  change: number;
  percentChange: number;
  volume: number;
  openInterest: number;
  bid: number;
  ask: number;
  contractSize: string;
  expiration: number; // Unix timestamp in seconds
  lastTradeDate: number; // Unix timestamp in seconds
  impliedVolatility: number;
  inTheMoney: boolean;
}

interface YahooOptionsChainResponse {
  underlyingSymbol: string;
  expirationDates: number[]; // Unix timestamps in seconds
  strikes: number[];
  hasMiniOptions: boolean;
  quote: {
    regularMarketPrice: number;
    regularMarketTime: number;
  };
  options: Array<{
    expirationDate: number;
    hasMiniOptions: boolean;
    calls: YahooOptionContract[];
    puts: YahooOptionContract[];
  }>;
}

export class YahooFinanceClient {
  private readonly cache: Cache;
  private readonly baseURL: string;
  private cookie: string | null = null;
  private crumb: string | null = null;
  private crumbExpiry: number = 0;

  constructor(
    cache: Cache,
    baseURL: string = "https://query2.finance.yahoo.com",
  ) {
    this.cache = cache;
    this.baseURL = baseURL;
  }

  /**
   * Get historical OHLC bars from Yahoo Finance
   * Provides real-time intraday data with no delay!
   */
  async getHistoricalBars(request: HistoricalBarsRequest): Promise<Bar[]> {
    const { symbol, timeframe, start, end } = request;

    // Use shorter cache key without timestamps for intraday to get fresh data
    const isIntraday = ["m1", "m5", "m15", "m30", "h1", "h4"].includes(
      timeframe,
    );
    const cacheKey = isIntraday
      ? `bars:yahoo:${symbol}:${timeframe}:recent`
      : `bars:yahoo:${symbol}:${timeframe}:${start}:${end}`;

    const cached = await this.cache.get<Bar[]>(cacheKey);
    if (cached && !isIntraday) {
      console.log(`[Yahoo Finance] Cache hit for ${symbol} ${timeframe}`);
      return cached;
    }

    const ticker = symbol.toUpperCase();
    const interval = TIMEFRAME_TO_YAHOO_INTERVAL[timeframe];

    if (!interval) {
      console.error(`[Yahoo Finance] Unsupported timeframe: ${timeframe}`);
      return [];
    }

    // For h4, we need to fetch h1 and aggregate (Yahoo doesn't support 4h)
    const actualInterval = timeframe === "h4" ? "1h" : interval;
    const range = YAHOO_RANGE_LIMITS[actualInterval] || "1mo";

    try {
      // Yahoo Finance chart API - no authentication needed for basic data
      const url = new URL(
        `https://query1.finance.yahoo.com/v8/finance/chart/${ticker}`,
      );
      url.searchParams.set("interval", actualInterval);
      url.searchParams.set("range", range);
      url.searchParams.set("includePrePost", "false"); // Only regular market hours

      console.log(
        `[Yahoo Finance] Fetching bars: ${ticker} ${timeframe} (interval=${actualInterval}, range=${range})`,
      );

      const response = await fetch(url.toString(), {
        headers: {
          "User-Agent":
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
          "Accept": "application/json",
        },
      });

      if (!response.ok) {
        console.error(
          `[Yahoo Finance] API error: ${response.status} ${response.statusText}`,
        );
        return [];
      }

      const data: YahooChartResponse = await response.json();

      if (data.chart.error) {
        console.error(
          `[Yahoo Finance] Chart error: ${data.chart.error.description}`,
        );
        return [];
      }

      const result = data.chart.result?.[0];
      if (!result || !result.timestamp || result.timestamp.length === 0) {
        console.log(
          `[Yahoo Finance] No data available for ${ticker} ${timeframe}`,
        );
        return [];
      }

      const quotes = result.indicators.quote[0];
      const bars: Bar[] = [];

      for (let i = 0; i < result.timestamp.length; i++) {
        // Skip bars with null values
        if (quotes.open[i] == null || quotes.close[i] == null) continue;

        const timestamp = result.timestamp[i] * 1000; // Convert to milliseconds

        // Filter by requested time range
        if (timestamp < start * 1000 || timestamp > end * 1000) continue;

        bars.push({
          timestamp,
          open: quotes.open[i],
          high: quotes.high[i],
          low: quotes.low[i],
          close: quotes.close[i],
          volume: quotes.volume[i] || 0,
        });
      }

      // For h4 timeframe, aggregate 1h bars into 4h bars
      let finalBars = bars;
      if (timeframe === "h4") {
        finalBars = this.aggregateBars(bars, 4);
      }

      console.log(
        `[Yahoo Finance] Fetched ${finalBars.length} bars for ${ticker} ${timeframe}`,
      );

      // Use shorter cache TTL for intraday (1 min) vs daily (24h)
      const cacheTTL = isIntraday ? 60 : CACHE_TTL.bars;
      await this.cache.set(cacheKey, finalBars, cacheTTL, [
        `symbol:${symbol}`,
        `timeframe:${timeframe}`,
      ]);

      return finalBars;
    } catch (error) {
      console.error(`[Yahoo Finance] Error fetching bars:`, error);
      return [];
    }
  }

  /**
   * Aggregate smaller timeframe bars into larger timeframe
   * e.g., aggregate 1h bars into 4h bars
   */
  private aggregateBars(bars: Bar[], factor: number): Bar[] {
    if (bars.length === 0) return [];

    const aggregated: Bar[] = [];

    for (let i = 0; i < bars.length; i += factor) {
      const chunk = bars.slice(i, i + factor);
      if (chunk.length === 0) continue;

      aggregated.push({
        timestamp: chunk[0].timestamp,
        open: chunk[0].open,
        high: Math.max(...chunk.map((b) => b.high)),
        low: Math.min(...chunk.map((b) => b.low)),
        close: chunk[chunk.length - 1].close,
        volume: chunk.reduce((sum, b) => sum + b.volume, 0),
      });
    }

    return aggregated;
  }

  /**
   * Get a valid crumb and cookie for Yahoo Finance API authentication
   * Caches the crumb for 1 hour to avoid excessive requests
   */
  private async getCrumb(): Promise<{ cookie: string; crumb: string }> {
    const now = Date.now();

    // Return cached crumb if still valid
    if (this.cookie && this.crumb && now < this.crumbExpiry) {
      return { cookie: this.cookie, crumb: this.crumb };
    }

    console.log("[Yahoo Finance] Fetching new crumb and cookie...");

    try {
      // First, get a cookie by visiting the consent page
      const consentResponse = await fetch("https://fc.yahoo.com", {
        headers: {
          "User-Agent":
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
        redirect: "manual",
      });

      // Extract cookies from response
      const setCookieHeaders = consentResponse.headers.getSetCookie?.() || [];
      const cookies = setCookieHeaders.map((header) => {
        const cookiePart = header.split(";")[0];
        return cookiePart;
      }).filter(Boolean);

      if (cookies.length === 0) {
        throw new Error("No cookies received from Yahoo Finance");
      }

      this.cookie = cookies.join("; ");
      console.log("[Yahoo Finance] Received cookies");

      // Now fetch the crumb using the cookies
      const crumbResponse = await fetch(
        "https://query2.finance.yahoo.com/v1/test/getcrumb",
        {
          headers: {
            "User-Agent":
              "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Cookie": this.cookie,
            "Accept": "*/*",
          },
        },
      );

      if (!crumbResponse.ok) {
        throw new Error(
          `Failed to fetch crumb: ${crumbResponse.status} ${crumbResponse.statusText}`,
        );
      }

      this.crumb = await crumbResponse.text();
      this.crumbExpiry = now + (60 * 60 * 1000); // 1 hour

      console.log("[Yahoo Finance] Crumb acquired successfully");

      return { cookie: this.cookie, crumb: this.crumb };
    } catch (error) {
      console.error("[Yahoo Finance] Failed to get crumb:", error);
      throw error;
    }
  }

  async getOptionsChain(request: OptionsChainRequest): Promise<OptionsChain> {
    const { underlying, expiration } = request;
    const cacheKey = `options:yahoo:${underlying}:${expiration || "all"}`;
    const cached = await this.cache.get<OptionsChain>(cacheKey);

    if (cached) {
      console.log(`[Yahoo Finance] Cache hit for ${underlying} options`);
      return cached;
    }

    const ticker = underlying.toUpperCase();

    // If a specific expiration is requested, fetch only that one
    if (expiration) {
      return this.fetchSingleExpiration(ticker, expiration);
    }

    // Otherwise, fetch all expirations
    return this.fetchAllExpirations(ticker);
  }

  /**
   * Fetch options for a single expiration date
   */
  private async fetchSingleExpiration(
    ticker: string,
    expiration: number,
  ): Promise<OptionsChain> {
    const { cookie, crumb } = await this.getCrumb();
    const url = new URL(`${this.baseURL}/v7/finance/options/${ticker}`);
    url.searchParams.set("crumb", crumb);
    url.searchParams.set("date", expiration.toString());

    try {
      console.log(
        `[Yahoo Finance] Fetching options chain: ${ticker} (expiration: ${expiration})`,
      );
      const response = await fetch(url.toString(), {
        headers: {
          "User-Agent":
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
          "Accept": "application/json",
          "Accept-Language": "en-US,en;q=0.9",
          "Referer": "https://finance.yahoo.com/",
          "Cookie": cookie,
        },
      });

      if (!response.ok) {
        throw new Error(
          `Yahoo Finance API error: ${response.status} ${response.statusText}`,
        );
      }

      const data = await response.json();
      const result = data.optionChain?.result?.[0] as YahooOptionsChainResponse;

      if (!result || !result.options || result.options.length === 0) {
        console.log(
          `[Yahoo Finance] No options data for ${ticker} expiration ${expiration}`,
        );
        return {
          underlying: ticker,
          timestamp: Date.now(),
          expirations: [expiration],
          calls: [],
          puts: [],
        };
      }

      const underlyingPrice = result.quote?.regularMarketPrice || 0;
      const { calls, puts } = this.processOptionsData(
        result.options,
        ticker,
        underlyingPrice,
      );

      const optionsChain: OptionsChain = {
        underlying: ticker,
        timestamp: Date.now(),
        expirations: [expiration],
        calls,
        puts,
      };

      // Cache for 15 minutes
      const cacheKey = `options:yahoo:${ticker}:${expiration}`;
      await this.cache.set(cacheKey, optionsChain, 15 * 60 * 1000, [
        `symbol:${ticker}`,
        "options",
      ]);

      return optionsChain;
    } catch (error) {
      console.error(`[Yahoo Finance] Error fetching single expiration:`, error);
      throw error;
    }
  }

  /**
   * Fetch options for all available expirations
   * Yahoo Finance API returns only the nearest expiration by default,
   * so we need to make multiple calls to get all expirations
   */
  private async fetchAllExpirations(ticker: string): Promise<OptionsChain> {
    const { cookie, crumb } = await this.getCrumb();

    try {
      // First, fetch the base options chain to get the list of all expiration dates
      console.log(`[Yahoo Finance] Fetching expiration dates for ${ticker}`);
      const baseUrl = new URL(`${this.baseURL}/v7/finance/options/${ticker}`);
      baseUrl.searchParams.set("crumb", crumb);

      const baseResponse = await fetch(baseUrl.toString(), {
        headers: {
          "User-Agent":
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
          "Accept": "application/json",
          "Accept-Language": "en-US,en;q=0.9",
          "Referer": "https://finance.yahoo.com/",
          "Cookie": cookie,
        },
      });

      if (!baseResponse.ok) {
        throw new Error(
          `Yahoo Finance API error: ${baseResponse.status} ${baseResponse.statusText}`,
        );
      }

      const baseData = await baseResponse.json();
      const baseResult = baseData.optionChain?.result
        ?.[0] as YahooOptionsChainResponse;

      if (
        !baseResult || !baseResult.expirationDates ||
        baseResult.expirationDates.length === 0
      ) {
        console.log(
          `[Yahoo Finance] No expiration dates available for ${ticker}`,
        );
        return {
          underlying: ticker,
          timestamp: Date.now(),
          expirations: [],
          calls: [],
          puts: [],
        };
      }

      const allExpirations = baseResult.expirationDates;
      const underlyingPrice = baseResult.quote?.regularMarketPrice || 0;

      console.log(
        `[Yahoo Finance] Found ${allExpirations.length} expirations for ${ticker}, fetching all...`,
      );

      // Fetch options for each expiration date
      // To avoid rate limiting, we'll fetch them sequentially with a small delay
      const allCalls: OptionContract[] = [];
      const allPuts: OptionContract[] = [];

      for (let i = 0; i < allExpirations.length; i++) {
        const exp = allExpirations[i];

        try {
          const expUrl = new URL(
            `${this.baseURL}/v7/finance/options/${ticker}`,
          );
          expUrl.searchParams.set("crumb", crumb);
          expUrl.searchParams.set("date", exp.toString());

          const expResponse = await fetch(expUrl.toString(), {
            headers: {
              "User-Agent":
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
              "Accept": "application/json",
              "Accept-Language": "en-US,en;q=0.9",
              "Referer": "https://finance.yahoo.com/",
              "Cookie": cookie,
            },
          });

          if (expResponse.ok) {
            const expData = await expResponse.json();
            const expResult = expData.optionChain?.result
              ?.[0] as YahooOptionsChainResponse;

            if (
              expResult && expResult.options && expResult.options.length > 0
            ) {
              const { calls, puts } = this.processOptionsData(
                expResult.options,
                ticker,
                underlyingPrice,
              );
              allCalls.push(...calls);
              allPuts.push(...puts);
            }
          }

          // Small delay to avoid rate limiting (100ms between requests)
          if (i < allExpirations.length - 1) {
            await new Promise((resolve) => setTimeout(resolve, 100));
          }
        } catch (expError) {
          console.error(
            `[Yahoo Finance] Error fetching expiration ${exp}:`,
            expError,
          );
          // Continue with other expirations
        }
      }

      const optionsChain: OptionsChain = {
        underlying: ticker,
        timestamp: Date.now(),
        expirations: allExpirations.sort((a, b) => a - b),
        calls: allCalls,
        puts: allPuts,
      };

      console.log(
        `[Yahoo Finance] Fetched ${allCalls.length} calls and ${allPuts.length} puts across ${allExpirations.length} expirations for ${ticker}`,
      );

      // Cache for 15 minutes
      const cacheKey = `options:yahoo:${ticker}:all`;
      await this.cache.set(cacheKey, optionsChain, 15 * 60 * 1000, [
        `symbol:${ticker}`,
        "options",
      ]);

      return optionsChain;
    } catch (error) {
      console.error(`[Yahoo Finance] Error fetching all expirations:`, error);
      throw error;
    }
  }

  /**
   * Process options data from Yahoo Finance API response
   */
  private processOptionsData(
    optionsData: any[],
    ticker: string,
    underlyingPrice: number,
  ): { calls: OptionContract[]; puts: OptionContract[] } {
    const calls: OptionContract[] = [];
    const puts: OptionContract[] = [];

    for (const optionData of optionsData) {
      // Process calls
      for (const call of optionData.calls || []) {
        const greeks = this.calculateGreeks(
          underlyingPrice,
          call.strike,
          call.expiration,
          call.impliedVolatility,
          "call",
        );

        calls.push({
          symbol: call.contractSymbol,
          underlying: ticker,
          strike: call.strike,
          expiration: call.expiration,
          type: "call",
          bid: call.bid || 0,
          ask: call.ask || 0,
          last: call.lastPrice || 0,
          mark: call.bid && call.ask
            ? (call.bid + call.ask) / 2
            : call.lastPrice || 0,
          volume: call.volume || 0,
          openInterest: call.openInterest || 0,
          delta: greeks.delta,
          gamma: greeks.gamma,
          theta: greeks.theta,
          vega: greeks.vega,
          rho: greeks.rho,
          impliedVolatility: call.impliedVolatility,
          lastTradeTime: call.lastTradeDate
            ? call.lastTradeDate * 1000
            : undefined,
          changePercent: call.percentChange,
          change: call.change,
        });
      }

      // Process puts
      for (const put of optionData.puts || []) {
        const greeks = this.calculateGreeks(
          underlyingPrice,
          put.strike,
          put.expiration,
          put.impliedVolatility,
          "put",
        );

        puts.push({
          symbol: put.contractSymbol,
          underlying: ticker,
          strike: put.strike,
          expiration: put.expiration,
          type: "put",
          bid: put.bid || 0,
          ask: put.ask || 0,
          last: put.lastPrice || 0,
          mark: put.bid && put.ask
            ? (put.bid + put.ask) / 2
            : put.lastPrice || 0,
          volume: put.volume || 0,
          openInterest: put.openInterest || 0,
          delta: greeks.delta,
          gamma: greeks.gamma,
          theta: greeks.theta,
          vega: greeks.vega,
          rho: greeks.rho,
          impliedVolatility: put.impliedVolatility,
          lastTradeTime: put.lastTradeDate
            ? put.lastTradeDate * 1000
            : undefined,
          changePercent: put.percentChange,
          change: put.change,
        });
      }
    }

    return { calls, puts };
  }

  /**
   * Calculate option Greeks using Black-Scholes model
   * This is a simplified implementation - for production, consider using a dedicated library
   */
  private calculateGreeks(
    spotPrice: number,
    strikePrice: number,
    expirationTimestamp: number,
    impliedVolatility: number,
    optionType: OptionType,
  ): {
    delta: number;
    gamma: number;
    theta: number;
    vega: number;
    rho: number;
  } {
    // Time to expiration in years
    const now = Date.now() / 1000; // Current time in seconds
    const timeToExpiry = Math.max(
      (expirationTimestamp - now) / (365.25 * 24 * 60 * 60),
      0.0001,
    );

    // Risk-free rate (approximation - using 5% annual)
    const riskFreeRate = 0.05;

    // Volatility (convert from decimal to annual)
    const sigma = impliedVolatility;

    // Black-Scholes intermediate calculations
    const d1 = (Math.log(spotPrice / strikePrice) +
      (riskFreeRate + 0.5 * sigma * sigma) * timeToExpiry) /
      (sigma * Math.sqrt(timeToExpiry));
    const d2 = d1 - sigma * Math.sqrt(timeToExpiry);

    // Standard normal CDF approximation
    const N = (x: number): number => {
      const t = 1 / (1 + 0.2316419 * Math.abs(x));
      const d = 0.3989423 * Math.exp(-x * x / 2);
      const probability = d * t *
        (0.3193815 +
          t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
      return x > 0 ? 1 - probability : probability;
    };

    // Standard normal PDF
    const n = (x: number): number => {
      return Math.exp(-x * x / 2) / Math.sqrt(2 * Math.PI);
    };

    // Calculate Greeks
    let delta: number;
    let theta: number;
    let rho: number;

    if (optionType === "call") {
      delta = N(d1);
      theta = -(spotPrice * n(d1) * sigma) / (2 * Math.sqrt(timeToExpiry)) -
        riskFreeRate * strikePrice * Math.exp(-riskFreeRate * timeToExpiry) *
          N(d2);
      rho = strikePrice * timeToExpiry *
        Math.exp(-riskFreeRate * timeToExpiry) * N(d2) / 100;
    } else {
      delta = N(d1) - 1;
      theta = -(spotPrice * n(d1) * sigma) / (2 * Math.sqrt(timeToExpiry)) +
        riskFreeRate * strikePrice * Math.exp(-riskFreeRate * timeToExpiry) *
          N(-d2);
      rho = -strikePrice * timeToExpiry *
        Math.exp(-riskFreeRate * timeToExpiry) * N(-d2) / 100;
    }

    // Gamma and Vega are same for calls and puts
    const gamma = n(d1) / (spotPrice * sigma * Math.sqrt(timeToExpiry));
    const vega = spotPrice * n(d1) * Math.sqrt(timeToExpiry) / 100;

    // Theta is typically expressed per day
    theta = theta / 365.25;

    return {
      delta: Number(delta.toFixed(4)),
      gamma: Number(gamma.toFixed(6)),
      theta: Number(theta.toFixed(4)),
      vega: Number(vega.toFixed(4)),
      rho: Number(rho.toFixed(4)),
    };
  }

  async healthCheck(): Promise<boolean> {
    try {
      // Try to get a crumb - if this works, the API is healthy
      await this.getCrumb();
      return true;
    } catch {
      return false;
    }
  }
}
