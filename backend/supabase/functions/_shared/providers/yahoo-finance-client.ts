// YahooFinanceClient: DataProviderAbstraction implementation for Yahoo Finance
// Free options data with 15-minute delay
// Greeks calculated from Black-Scholes model

import type {
  OptionsChainRequest,
} from "./abstraction.ts";
import type { OptionContract, OptionsChain, OptionType } from "./types.ts";
import type { Cache } from "../cache/interface.ts";
import { CACHE_TTL } from "../config/rate-limits.ts";

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
    baseURL: string = "https://query2.finance.yahoo.com"
  ) {
    this.cache = cache;
    this.baseURL = baseURL;
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
          "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
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
      const crumbResponse = await fetch("https://query2.finance.yahoo.com/v1/test/getcrumb", {
        headers: {
          "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
          "Cookie": this.cookie,
          "Accept": "*/*",
        },
      });

      if (!crumbResponse.ok) {
        throw new Error(`Failed to fetch crumb: ${crumbResponse.status} ${crumbResponse.statusText}`);
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

    // Get authentication crumb and cookie
    const { cookie, crumb } = await this.getCrumb();

    // Build Yahoo Finance API URL
    const url = new URL(`${this.baseURL}/v7/finance/options/${ticker}`);

    // Add crumb parameter
    url.searchParams.set("crumb", crumb);

    // Add expiration date if specified
    if (expiration) {
      url.searchParams.set("date", expiration.toString());
    }

    try {
      console.log(`[Yahoo Finance] Fetching options chain: ${underlying}`);
      const response = await fetch(url.toString(), {
        headers: {
          "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
          "Accept": "application/json",
          "Accept-Language": "en-US,en;q=0.9",
          "Referer": "https://finance.yahoo.com/",
          "Cookie": cookie,
        },
      });

      if (!response.ok) {
        throw new Error(`Yahoo Finance API error: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      const result = data.optionChain?.result?.[0] as YahooOptionsChainResponse;

      if (!result || !result.options || result.options.length === 0) {
        console.log(`[Yahoo Finance] No options data available for ${underlying}`);
        return {
          underlying: ticker,
          timestamp: Date.now(),
          expirations: [],
          calls: [],
          puts: [],
        };
      }

      // Get underlying stock price for Greeks calculations
      const underlyingPrice = result.quote?.regularMarketPrice || 0;

      const calls: OptionContract[] = [];
      const puts: OptionContract[] = [];
      const expirationSet = new Set<number>();

      // Process all expiration dates
      for (const optionData of result.options) {
        expirationSet.add(optionData.expirationDate);

        // Process calls
        for (const call of optionData.calls || []) {
          const greeks = this.calculateGreeks(
            underlyingPrice,
            call.strike,
            call.expiration,
            call.impliedVolatility,
            "call"
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
            mark: call.bid && call.ask ? (call.bid + call.ask) / 2 : call.lastPrice || 0,
            volume: call.volume || 0,
            openInterest: call.openInterest || 0,
            delta: greeks.delta,
            gamma: greeks.gamma,
            theta: greeks.theta,
            vega: greeks.vega,
            rho: greeks.rho,
            impliedVolatility: call.impliedVolatility,
            lastTradeTime: call.lastTradeDate ? call.lastTradeDate * 1000 : undefined,
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
            "put"
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
            mark: put.bid && put.ask ? (put.bid + put.ask) / 2 : put.lastPrice || 0,
            volume: put.volume || 0,
            openInterest: put.openInterest || 0,
            delta: greeks.delta,
            gamma: greeks.gamma,
            theta: greeks.theta,
            vega: greeks.vega,
            rho: greeks.rho,
            impliedVolatility: put.impliedVolatility,
            lastTradeTime: put.lastTradeDate ? put.lastTradeDate * 1000 : undefined,
            changePercent: put.percentChange,
            change: put.change,
          });
        }
      }

      // Use expirationDates from API response (all available expirations)
      // rather than just the ones we have data for
      const allExpirations = result.expirationDates || Array.from(expirationSet);

      const optionsChain: OptionsChain = {
        underlying: ticker,
        timestamp: Date.now(),
        expirations: allExpirations.sort((a, b) => a - b),
        calls,
        puts,
      };

      console.log(
        `[Yahoo Finance] Fetched ${calls.length} calls and ${puts.length} puts for ${underlying}`
      );

      // Cache for 15 minutes (data is 15 min delayed anyway)
      await this.cache.set(cacheKey, optionsChain, 15 * 60 * 1000, [
        `symbol:${underlying}`,
        "options",
      ]);

      return optionsChain;
    } catch (error) {
      console.error(`[Yahoo Finance] Error fetching options chain:`, error);
      throw error;
    }
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
    optionType: OptionType
  ): {
    delta: number;
    gamma: number;
    theta: number;
    vega: number;
    rho: number;
  } {
    // Time to expiration in years
    const now = Date.now() / 1000; // Current time in seconds
    const timeToExpiry = Math.max((expirationTimestamp - now) / (365.25 * 24 * 60 * 60), 0.0001);

    // Risk-free rate (approximation - using 5% annual)
    const riskFreeRate = 0.05;

    // Volatility (convert from decimal to annual)
    const sigma = impliedVolatility;

    // Black-Scholes intermediate calculations
    const d1 = (Math.log(spotPrice / strikePrice) + (riskFreeRate + 0.5 * sigma * sigma) * timeToExpiry) /
               (sigma * Math.sqrt(timeToExpiry));
    const d2 = d1 - sigma * Math.sqrt(timeToExpiry);

    // Standard normal CDF approximation
    const N = (x: number): number => {
      const t = 1 / (1 + 0.2316419 * Math.abs(x));
      const d = 0.3989423 * Math.exp(-x * x / 2);
      const probability = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
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
              riskFreeRate * strikePrice * Math.exp(-riskFreeRate * timeToExpiry) * N(d2);
      rho = strikePrice * timeToExpiry * Math.exp(-riskFreeRate * timeToExpiry) * N(d2) / 100;
    } else {
      delta = N(d1) - 1;
      theta = -(spotPrice * n(d1) * sigma) / (2 * Math.sqrt(timeToExpiry)) +
              riskFreeRate * strikePrice * Math.exp(-riskFreeRate * timeToExpiry) * N(-d2);
      rho = -strikePrice * timeToExpiry * Math.exp(-riskFreeRate * timeToExpiry) * N(-d2) / 100;
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
