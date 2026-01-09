// Alpaca Market Data Client
// Provides historical and real-time market data via Alpaca's Market Data API v2
// Documentation: https://docs.alpaca.markets/docs/getting-started-with-alpaca-market-data

import type { DataProviderAbstraction, HistoricalBarsRequest } from "./abstraction.ts";
import type { Bar, Quote, NewsItem } from "./types.ts";
import { ProviderError, RateLimitExceededError } from "./types.ts";

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

export class AlpacaClient implements DataProviderAbstraction {
  private readonly apiKey: string;
  private readonly apiSecret: string;
  private readonly baseUrl = "https://data.alpaca.markets/v2";

  constructor(apiKey: string, apiSecret: string) {
    this.apiKey = apiKey;
    this.apiSecret = apiSecret;
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
   */
  async getHistoricalBars(request: HistoricalBarsRequest): Promise<Bar[]> {
    const { symbol, timeframe, start, end } = request;

    // Convert timeframe to Alpaca format
    const alpacaTimeframe = this.convertTimeframe(timeframe);
    
    console.log(`[Alpaca] Fetching historical bars: ${symbol} ${timeframe} (${alpacaTimeframe})`);

    try {
      // Build URL with parameters
      const startDate = new Date(start * 1000).toISOString();
      const endDate = new Date(end * 1000).toISOString();
      
      const url = `${this.baseUrl}/stocks/${symbol}/bars?` +
        `timeframe=${alpacaTimeframe}&` +
        `start=${startDate}&` +
        `end=${endDate}&` +
        `limit=10000&` +
        `adjustment=split&` +
        `feed=iex`;

      const response = await fetch(url, {
        headers: this.getHeaders(),
      });

      if (!response.ok) {
        await this.handleErrorResponse(response);
      }

      const data = await response.json() as AlpacaBarsResponse;
      const alpacaBars = data.bars?.[symbol] || [];

      if (alpacaBars.length === 0) {
        console.log(`[Alpaca] No data returned for ${symbol}`);
        return [];
      }

      // Convert Alpaca bars to our Bar format
      const bars: Bar[] = alpacaBars.map((bar) => ({
        timestamp: Math.floor(new Date(bar.t).getTime() / 1000),
        open: bar.o,
        high: bar.h,
        low: bar.l,
        close: bar.c,
        volume: bar.v,
      }));

      if (bars.length > 0) {
        const firstDate = new Date(bars[0].timestamp * 1000).toISOString();
        const lastDate = new Date(bars[bars.length - 1].timestamp * 1000).toISOString();
        console.log(`[Alpaca] Retrieved ${bars.length} bars for ${symbol} ${timeframe} (${firstDate} to ${lastDate})`);
      }

      return bars;
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
   * Handle API error responses
   */
  private async handleErrorResponse(response: Response): Promise<never> {
    const status = response.status;
    let errorMessage = `Alpaca API error: ${status} ${response.statusText}`;

    try {
      const errorData = await response.json();
      errorMessage = errorData.message || errorMessage;
    } catch {
      // Ignore JSON parse errors
    }

    // Handle rate limiting
    if (status === 429) {
      const retryAfter = response.headers.get("Retry-After");
      const retrySeconds = retryAfter ? parseInt(retryAfter) : undefined;
      throw new RateLimitExceededError("alpaca", retrySeconds);
    }

    // Handle other errors
    throw new ProviderError(errorMessage, "alpaca", status.toString(), status);
  }
}
