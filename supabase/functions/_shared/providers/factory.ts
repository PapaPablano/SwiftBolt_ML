// Provider Factory: Initializes and exports singleton provider router
// This is the main entry point for using the data provider abstraction layer
// Alpaca-only strategy: Alpaca is the single source of truth for all OHLCV data

import { TokenBucketRateLimiter } from "../rate-limiter/token-bucket.ts";
import { MemoryCache } from "../cache/memory-cache.ts";
import { getRateLimits } from "../config/rate-limits.ts";
import { FinnhubClient } from "./finnhub-client.ts";
import { YahooFinanceClient } from "./yahoo-finance-client.ts";
import { AlpacaClient } from "./alpaca-client.ts";
import { ProviderRouter } from "./router.ts";
import type { ProviderId } from "./types.ts";

// Singleton instances
let routerInstance: ProviderRouter | null = null;
let rateLimiterInstance: TokenBucketRateLimiter | null = null;
let cacheInstance: MemoryCache | null = null;

/**
 * Initialize the provider system with rate limiting and caching
 * Call this once at application startup
 *
 * Alpaca-only strategy:
 * - Alpaca: PRIMARY provider for all OHLCV data (historical + real-time)
 * - Finnhub: News only
 * - Yahoo: Options chain only (Alpaca doesn't provide options)
 */
export function initializeProviders(): ProviderRouter {
  if (routerInstance) {
    return routerInstance;
  }

  console.log(
    "[Provider Factory] Initializing provider system (Alpaca-only strategy)...",
  );

  // Initialize rate limiter
  const rateLimits = getRateLimits();
  rateLimiterInstance = new TokenBucketRateLimiter(rateLimits, 5000);
  console.log("[Provider Factory] Rate limiter initialized:", rateLimits);

  // Initialize cache
  cacheInstance = new MemoryCache(1000);
  console.log("[Provider Factory] Memory cache initialized (max 1000 entries)");

  // Initialize provider clients
  const finnhubApiKey = Deno.env.get("FINNHUB_API_KEY");
  const alpacaApiKey = Deno.env.get("ALPACA_API_KEY");
  const alpacaApiSecret = Deno.env.get("ALPACA_API_SECRET");

  if (!finnhubApiKey) {
    throw new Error("Missing required API key: FINNHUB_API_KEY");
  }

  if (!alpacaApiKey || !alpacaApiSecret) {
    throw new Error(
      "Missing required API keys: ALPACA_API_KEY and ALPACA_API_SECRET are required for Alpaca-only strategy",
    );
  }

  const finnhubClient = new FinnhubClient(
    finnhubApiKey,
    rateLimiterInstance,
    cacheInstance,
  );

  const yahooFinanceClient = new YahooFinanceClient(
    cacheInstance,
  );

  const alpacaClient = new AlpacaClient(
    alpacaApiKey,
    alpacaApiSecret,
    rateLimiterInstance,
    cacheInstance,
  );

  // Warm Alpaca assets cache on startup to avoid validation delays
  console.log("[Provider Factory] Alpaca credentials check: {");
  console.log(`  hasApiKey: ${!!alpacaApiKey},`);
  console.log(`  apiKeyLength: ${alpacaApiKey?.length},`);
  console.log(`  hasApiSecret: ${!!alpacaApiSecret},`);
  console.log(`  apiSecretLength: ${alpacaApiSecret?.length}`);
  console.log("}");

  console.log(
    '[Provider Factory] Alpaca client status: { initialized: true, willUsePrimary: "alpaca" }',
  );

  alpacaClient.getAssets().then(() => {
    console.log("[Provider Factory] Alpaca assets cache warmed successfully");
  }).catch((error) => {
    console.warn(
      "[Provider Factory] Failed to warm Alpaca assets cache:",
      error,
    );
  });

  console.log("[Provider Factory] Provider clients initialized");

  // Initialize router with Alpaca-only policy for OHLCV data
  const providers: Record<string, any> = {
    finnhub: finnhubClient,
    yahoo: yahooFinanceClient,
    alpaca: alpacaClient,
  };

  // Alpaca-only policy: Single source of truth for all OHLCV data
  // No fallbacks for OHLCV - if Alpaca fails, we want to know about it
  const policy = {
    quote: {
      primary: "alpaca" as ProviderId,
      fallback: "finnhub" as ProviderId,
    },
    historicalBars: {
      primary: "alpaca" as ProviderId,
      fallback: undefined, // No fallback - Alpaca is single source of truth
    },
    news: {
      primary: "alpaca" as ProviderId,
      fallback: "finnhub" as ProviderId,
    },
    optionsChain: {
      primary: "yahoo" as ProviderId, // Alpaca doesn't provide options data
      fallback: undefined,
    },
  };

  routerInstance = new ProviderRouter(providers, policy);

  console.log(
    "[Provider Factory] Provider router initialized (Alpaca-only strategy)",
  );

  return routerInstance;
}

/**
 * Get the singleton router instance
 * Initializes if not already initialized
 */
export function getProviderRouter(): ProviderRouter {
  if (!routerInstance) {
    return initializeProviders();
  }
  return routerInstance;
}

/**
 * Inject Supabase client into providers for distributed rate limiting
 * Call this in Edge functions that need coordinated rate limiting
 */
export function injectSupabaseClient(_supabase: any): void {
  if (!routerInstance) {
    initializeProviders();
  }

  // Note: With Alpaca-only strategy, we don't need to inject Supabase client
  // into Massive/Polygon provider since it's no longer used
  console.log(
    "[Provider Factory] Supabase client injection not needed for Alpaca-only strategy",
  );
}

/**
 * Get cache statistics for observability
 */
export async function getCacheStats() {
  if (!cacheInstance) {
    return null;
  }
  return await cacheInstance.getStats();
}

/**
 * Get rate limiter status for observability
 */
export function getRateLimiterStatus(provider: ProviderId) {
  if (!rateLimiterInstance) {
    return null;
  }
  return rateLimiterInstance.getStatus(provider);
}

/**
 * Clear cache (useful for testing or forced refresh)
 */
export async function clearCache() {
  if (cacheInstance) {
    await cacheInstance.clear();
    console.log("[Provider Factory] Cache cleared");
  }
}

/**
 * Invalidate cache entries by tag
 */
export async function invalidateCacheTag(tag: string) {
  if (cacheInstance) {
    await cacheInstance.invalidateByTag(tag);
    console.log(`[Provider Factory] Cache invalidated for tag: ${tag}`);
  }
}
