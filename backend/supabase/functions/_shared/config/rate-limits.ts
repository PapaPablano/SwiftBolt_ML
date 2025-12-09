// Rate limit configuration for market data providers
// Values can be overridden via environment variables when upgrading to paid tiers

import type { ProviderId } from "../providers/types.ts";
import type { RateLimitConfig } from "../rate-limiter/token-bucket.ts";

export interface ProviderRateLimits {
  finnhub: RateLimitConfig;
  massive: RateLimitConfig;
}

/**
 * Default rate limits for free tier
 * Override via environment variables:
 * - FINNHUB_MAX_RPS, FINNHUB_MAX_RPM
 * - MASSIVE_MAX_RPS, MASSIVE_MAX_RPM
 */
export function getRateLimits(): Record<ProviderId, RateLimitConfig> {
  return {
    finnhub: {
      maxPerSecond: parseInt(Deno.env.get("FINNHUB_MAX_RPS") || "30", 10),
      maxPerMinute: parseInt(Deno.env.get("FINNHUB_MAX_RPM") || "60", 10),
    },
    massive: {
      maxPerSecond: parseInt(Deno.env.get("MASSIVE_MAX_RPS") || "1", 10),
      maxPerMinute: parseInt(Deno.env.get("MASSIVE_MAX_RPM") || "5", 10),
    },
  };
}

/**
 * Cache TTL configuration (in seconds)
 * Defines how long different data types should be cached
 */
export const CACHE_TTL = {
  // Quotes: 1-5 seconds for interactive UI
  quote: parseInt(Deno.env.get("CACHE_TTL_QUOTE") || "5", 10),

  // Historical bars: effectively immutable, cache long term
  bars: parseInt(Deno.env.get("CACHE_TTL_BARS") || "86400", 10), // 24 hours

  // News: 15-60 seconds
  news: parseInt(Deno.env.get("CACHE_TTL_NEWS") || "60", 10),

  // Fundamentals/reference: hours or days
  fundamentals: parseInt(Deno.env.get("CACHE_TTL_FUNDAMENTALS") || "3600", 10), // 1 hour

  // Symbol search: moderate TTL
  symbols: parseInt(Deno.env.get("CACHE_TTL_SYMBOLS") || "300", 10), // 5 minutes
} as const;
