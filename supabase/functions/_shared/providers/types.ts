// Provider-agnostic types for market data
// These types define the unified abstraction layer over Finnhub and Massive

export type ProviderId = "finnhub" | "massive" | "yahoo" | "alpaca" | "tradier";

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

export type OptionType = "call" | "put";

// ============================================================================
// FUTURES TYPES
// ============================================================================

export type FuturesSector = "indices" | "metals" | "energy" | "rates" | "agriculture" | "softs";

export interface FuturesRoot {
  symbol: string; // Root symbol (e.g., "GC", "ES")
  name: string; // Full name (e.g., "Gold")
  exchange: string; // e.g., "COMEX", "CME"
  sector: FuturesSector;
  tickSize: number;
  pointValue: number;
  currency: string;
  sessionTemplate?: string;
}

export interface FuturesContract {
  symbol: string; // Full contract symbol (e.g., "GCZ25")
  rootSymbol: string; // Root symbol (e.g., "GC")
  contractCode: string; // Month code + year (e.g., "Z25")
  expiryMonth: number;
  expiryYear: number;
  lastTradeDate?: string; // ISO date string
  firstNoticeDate?: string; // For physically delivered
  settlementDate?: string; // For cash-settled
  isActive: boolean;
  isSpot: boolean; // Is this the front month?
  volume30d?: number;
  openInterest?: number;
}

export interface FuturesChain {
  root: FuturesRoot;
  contracts: FuturesContract[];
  continuousAliases: {
    depth: number;
    alias: string; // e.g., "GC1!"
    contract: FuturesContract;
  }[];
}

export interface FuturesContinuousMapping {
  alias: string; // e.g., "GC1!"
  rootSymbol: string;
  depth: number;
  contractSymbol: string;
  validFrom: string; // ISO date
  validUntil?: string; // ISO date, null if active
}

export interface OptionContract {
  symbol: string; // Option symbol (e.g., "AAPL250117C00150000")
  underlying: string; // Underlying symbol (e.g., "AAPL")
  strike: number;
  expiration: number; // Unix timestamp (seconds)
  type: OptionType;

  // Pricing
  bid: number;
  ask: number;
  last: number;
  mark: number; // Midpoint of bid/ask

  // Volume & Open Interest
  volume: number;
  openInterest: number;

  // Greeks (optional, may not always be available)
  delta?: number;
  gamma?: number;
  theta?: number;
  vega?: number;
  rho?: number;

  // Implied Volatility
  impliedVolatility?: number;

  // Additional data
  lastTradeTime?: number;
  changePercent?: number;
  change?: number;
}

export interface OptionsChain {
  underlying: string;
  timestamp: number;
  expirations: number[]; // Array of expiration timestamps
  calls: OptionContract[];
  puts: OptionContract[];
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

export class AuthenticationError extends ProviderError {
  constructor(provider: ProviderId, message: string = "Authentication failed") {
    super(
      message,
      provider,
      "AUTHENTICATION_ERROR",
      401
    );
    this.name = "AuthenticationError";
  }
}

export class ValidationError extends ProviderError {
  constructor(provider: ProviderId, message: string) {
    super(
      message,
      provider,
      "VALIDATION_ERROR",
      400
    );
    this.name = "ValidationError";
  }
}

export class ServiceUnavailableError extends ProviderError {
  constructor(provider: ProviderId, message: string = "Service unavailable") {
    super(
      message,
      provider,
      "SERVICE_UNAVAILABLE",
      503
    );
    this.name = "ServiceUnavailableError";
  }
}
