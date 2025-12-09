// DataProviderAbstraction: unified interface for market data providers
// All provider clients (Finnhub, Massive) must implement this interface

import type { Bar, NewsItem, Quote, Symbol, Timeframe } from "./types.ts";

export interface HistoricalBarsRequest {
  symbol: string;
  timeframe: Timeframe;
  start: number; // Unix timestamp (seconds)
  end: number; // Unix timestamp (seconds)
}

export interface NewsRequest {
  symbol?: string;
  from?: number; // Unix timestamp (seconds)
  to?: number; // Unix timestamp (seconds)
  limit?: number;
}

export interface DataProviderAbstraction {
  /**
   * Get real-time or near real-time quote for one or more symbols
   */
  getQuote(symbols: string[]): Promise<Quote[]>;

  /**
   * Get historical OHLCV bars for a symbol
   */
  getHistoricalBars(request: HistoricalBarsRequest): Promise<Bar[]>;

  /**
   * Get news items, optionally filtered by symbol
   */
  getNews(request: NewsRequest): Promise<NewsItem[]>;

  /**
   * Search for symbols by ticker or description
   * Optional - not all providers may support this
   */
  searchSymbols?(query: string): Promise<Symbol[]>;

  /**
   * Check if provider is healthy and available
   */
  healthCheck(): Promise<boolean>;
}
