// Yahoo Finance Client: Free historical data provider (no API key required)
// Used primarily for backfilling historical data

import type { DataProviderAbstraction, HistoricalBarsRequest } from "./abstraction.ts";
import type { Bar, Quote, NewsItem } from "./types.ts";

export class YFinanceClient implements DataProviderAbstraction {
  private baseUrl = "https://query1.finance.yahoo.com/v8/finance/chart";

  async getQuote(_symbols: string[]): Promise<Quote[]> {
    throw new Error("YFinance client only supports historical data");
  }

  async getHistoricalBars(request: HistoricalBarsRequest): Promise<Bar[]> {
    const { symbol, timeframe, start, end } = request;

    // Convert our timeframe to yfinance interval
    const interval = this.convertTimeframe(timeframe);

    // Build URL
    const url = `${this.baseUrl}/${symbol}?interval=${interval}&period1=${start}&period2=${end}`;

    console.log(`[YFinance] Fetching historical bars: ${symbol} ${timeframe} (${interval})`);

    try {
      const response = await fetch(url, {
        headers: {
          "User-Agent": "Mozilla/5.0",
        },
      });

      if (!response.ok) {
        throw new Error(`YFinance API error: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();

      // Parse yfinance response
      const result = data.chart?.result?.[0];
      if (!result) {
        console.log(`[YFinance] No data returned for ${symbol}`);
        return [];
      }

      const timestamps = result.timestamp || [];
      const quotes = result.indicators?.quote?.[0];

      if (!quotes || timestamps.length === 0) {
        console.log(`[YFinance] Empty dataset for ${symbol}`);
        return [];
      }

      const bars: Bar[] = [];
      for (let i = 0; i < timestamps.length; i++) {
        // Skip bars with null values
        if (
          quotes.open[i] === null ||
          quotes.high[i] === null ||
          quotes.low[i] === null ||
          quotes.close[i] === null
        ) {
          continue;
        }

        bars.push({
          timestamp: timestamps[i],
          open: quotes.open[i],
          high: quotes.high[i],
          low: quotes.low[i],
          close: quotes.close[i],
          volume: quotes.volume[i] || 0,
        });
      }

      if (bars.length > 0) {
        const firstDate = new Date(bars[0].timestamp * 1000).toISOString();
        const lastDate = new Date(bars[bars.length - 1].timestamp * 1000).toISOString();
        console.log(`[YFinance] Retrieved ${bars.length} bars for ${symbol} ${timeframe} (${firstDate} to ${lastDate})`);
      } else {
        console.log(`[YFinance] No bars retrieved for ${symbol} ${timeframe}`);
      }
      return bars;
    } catch (error) {
      console.error(`[YFinance] Error fetching bars:`, error);
      throw error;
    }
  }

  async getNews(_request: { symbol: string; limit?: number }): Promise<NewsItem[]> {
    throw new Error("YFinance client does not support news");
  }

  private convertTimeframe(timeframe: string): string {
    // Map our timeframes to yfinance intervals
    const mapping: Record<string, string> = {
      m1: "1m",
      m5: "5m",
      m15: "15m",
      m30: "30m",
      h1: "1h",
      h4: "1h", // yfinance doesn't have 4h, use 1h and we'll aggregate if needed
      d1: "1d",
      w1: "1wk",
      mn1: "1mo",
    };

    return mapping[timeframe] || "1d";
  }
}
