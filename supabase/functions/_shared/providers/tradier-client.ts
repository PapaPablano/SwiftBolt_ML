// Tradier Client: Real-time intraday market data provider
// Provides live quotes and intraday bars (m15, h1) for active trading

import type {
  DataProviderAbstraction,
  HistoricalBarsRequest,
  NewsRequest,
} from "./abstraction.ts";
import type { Bar, NewsItem, Quote, Timeframe } from "./types.ts";

export class TradierClient implements DataProviderAbstraction {
  private apiKey: string;
  private baseUrl: string = "https://api.tradier.com/v1";

  constructor(apiKey: string) {
    this.apiKey = apiKey;
  }

  async getQuote(symbols: string[]): Promise<Quote[]> {
    const symbolsParam = symbols.join(",");
    const url = `${this.baseUrl}/markets/quotes?symbols=${symbolsParam}`;

    const response = await fetch(url, {
      headers: {
        Authorization: `Bearer ${this.apiKey}`,
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`Tradier API error: ${response.status}`);
    }

    const data = await response.json();
    const quotes = Array.isArray(data.quotes.quote)
      ? data.quotes.quote
      : [data.quotes.quote];

    return quotes.map((q: any) => ({
      symbol: q.symbol,
      price: q.last || q.close,
      change: q.change,
      changePercent: q.change_percentage,
      volume: q.volume,
      timestamp: Date.now(),
      bid: q.bid,
      ask: q.ask,
      open: q.open,
      high: q.high,
      low: q.low,
      previousClose: q.prevclose,
    }));
  }

  async getHistoricalBars(request: HistoricalBarsRequest): Promise<Bar[]> {
    const { symbol, timeframe, start, end } = request;

    // Convert timeframe to Tradier interval
    const interval = this.convertTimeframe(timeframe);

    // Tradier uses dates in YYYY-MM-DD format
    const startDate = new Date(start * 1000).toISOString().split("T")[0];
    const endDate = new Date(end * 1000).toISOString().split("T")[0];

    const url =
      `${this.baseUrl}/markets/timesales?symbol=${symbol}&interval=${interval}&start=${startDate}&end=${endDate}`;

    const response = await fetch(url, {
      headers: {
        Authorization: `Bearer ${this.apiKey}`,
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`Tradier API error: ${response.status}`);
    }

    const data = await response.json();

    if (!data.series || !data.series.data) {
      return [];
    }

    const bars = Array.isArray(data.series.data)
      ? data.series.data
      : [data.series.data];

    return bars.map((bar: any) => ({
      timestamp: new Date(bar.time).getTime(),
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
      volume: bar.volume,
    }));
  }

  async getNews(_request: NewsRequest): Promise<NewsItem[]> {
    // Tradier doesn't provide news - return empty array
    return [];
  }

  async healthCheck(): Promise<boolean> {
    try {
      // Quick health check with a simple quote request
      const url = `${this.baseUrl}/markets/quotes?symbols=SPY`;
      const response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          Accept: "application/json",
        },
      });
      return response.ok;
    } catch {
      return false;
    }
  }

  private convertTimeframe(timeframe: Timeframe): string {
    // Tradier intervals: tick, 1min, 5min, 15min
    const mapping: Record<Timeframe, string> = {
      m1: "1min",
      m5: "5min",
      m15: "15min",
      m30: "15min", // Use 15min and aggregate
      h1: "15min", // Use 15min and aggregate
      h4: "15min", // Use 15min and aggregate
      d1: "daily",
      w1: "weekly",
      mn1: "monthly",
    };
    return mapping[timeframe] || "15min";
  }
}
