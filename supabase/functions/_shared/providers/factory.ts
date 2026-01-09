// Provider Factory: Initializes and exports singleton provider router
// This is the main entry point for using the data provider abstraction layer

import { TokenBucketRateLimiter } from "../rate-limiter/token-bucket.ts";
import { MemoryCache } from "../cache/memory-cache.ts";
import { getRateLimits } from "../config/rate-limits.ts";
import { FinnhubClient } from "./finnhub-client.ts";
import { MassiveClient } from "./massive-client.ts";
import { YahooFinanceClient } from "./yahoo-finance-client.ts";
import { ProviderRouter } from "./router.ts";
import type { ProviderId } from "./types.ts";

// Singleton instances
let routerInstance: ProviderRouter | null = null;
let rateLimiterInstance: TokenBucketRateLimiter | null = null;
let cacheInstance: MemoryCache | null = null;
let massiveClientInstance: MassiveClient | null = null;

/**
 * Initialize the provider system with rate limiting and caching
 * Call this once at application startup
 */
export function initializeProviders(): ProviderRouter {
  if (routerInstance) {
    return routerInstance;
  }

  console.log("[Provider Factory] Initializing provider system...");

  // Initialize rate limiter
  const rateLimits = getRateLimits();
  rateLimiterInstance = new TokenBucketRateLimiter(rateLimits, 5000);
  console.log("[Provider Factory] Rate limiter initialized:", rateLimits);

  // Initialize cache
  cacheInstance = new MemoryCache(1000);
  console.log("[Provider Factory] Memory cache initialized (max 1000 entries)");

  // Initialize provider clients
  const finnhubApiKey = Deno.env.get("FINNHUB_API_KEY");
  const massiveApiKey = Deno.env.get("MASSIVE_API_KEY");

  if (!finnhubApiKey || !massiveApiKey) {
    throw new Error("Missing required API keys: FINNHUB_API_KEY and MASSIVE_API_KEY");
  }

  const finnhubClient = new FinnhubClient(
    finnhubApiKey,
    rateLimiterInstance,
    cacheInstance
  );

  massiveClientInstance = new MassiveClient(
    massiveApiKey,
    rateLimiterInstance,
    cacheInstance
  );

  const yahooFinanceClient = new YahooFinanceClient(
    cacheInstance
  );

  console.log("[Provider Factory] Provider clients initialized");

  // Initialize router with default policy
  routerInstance = new ProviderRouter({
    finnhub: finnhubClient,
    massive: massiveClientInstance,
    yahoo: yahooFinanceClient,
  });

  console.log("[Provider Factory] Provider router initialized");

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
 * Get the singleton MassiveClient (Polygon) instance
 * Initializes providers if not already initialized
 * Returns null if initialization fails
 */
export function getMassiveClient(): MassiveClient | null {
  if (!massiveClientInstance) {
    try {
      initializeProviders();
    } catch (error) {
      console.error("[Provider Factory] Failed to initialize providers:", error);
      return null;
    }
  }
  return massiveClientInstance;
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
