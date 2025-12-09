// Provider-agnostic types for market data
// These types define the unified abstraction layer over Finnhub and Massive

export type ProviderId = "finnhub" | "massive";

export type Timeframe = "m1" | "m5" | "m15" | "m30" | "h1" | "h4" | "d1" | "w1" | "mn1";

export interface Quote {
  symbol: string;
  price: number;
  timestamp: number;
  volume?: number;
  change?: number;
  changePercent?: number;
  high?: number;
  low?: number;
  open?: number;
  previousClose?: number;
}

export interface Bar {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface NewsItem {
  id: string;
  headline: string;
  summary: string;
  source: string;
  url: string;
  publishedAt: number;
  symbols?: string[];
  sentiment?: "positive" | "negative" | "neutral";
}

export interface Symbol {
  ticker: string;
  description: string;
  assetType: "stock" | "future" | "option" | "crypto";
  exchange?: string;
  currency?: string;
}

// Error types for unified error handling
export class ProviderError extends Error {
  constructor(
    message: string,
    public readonly provider: ProviderId,
    public readonly code: string,
    public readonly statusCode?: number
  ) {
    super(message);
    this.name = "ProviderError";
  }
}

export class RateLimitExceededError extends ProviderError {
  constructor(provider: ProviderId, retryAfter?: number) {
    super(
      `Rate limit exceeded for ${provider}`,
      provider,
      "RATE_LIMIT_EXCEEDED",
      429
    );
    this.name = "RateLimitExceededError";
    this.retryAfter = retryAfter;
  }
  retryAfter?: number;
}

export class ProviderUnavailableError extends ProviderError {
  constructor(provider: ProviderId, cause?: Error) {
    super(
      `Provider ${provider} is unavailable`,
      provider,
      "PROVIDER_UNAVAILABLE",
      503
    );
    this.name = "ProviderUnavailableError";
    this.cause = cause;
  }
}

export class InvalidSymbolError extends ProviderError {
  constructor(provider: ProviderId, symbol: string) {
    super(
      `Invalid symbol: ${symbol}`,
      provider,
      "INVALID_SYMBOL",
      400
    );
    this.name = "InvalidSymbolError";
  }
}

export class PermissionDeniedError extends ProviderError {
  constructor(provider: ProviderId, message: string) {
    super(
      message,
      provider,
      "PERMISSION_DENIED",
      403
    );
    this.name = "PermissionDeniedError";
  }
}
