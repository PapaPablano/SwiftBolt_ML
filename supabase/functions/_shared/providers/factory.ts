// Provider Factory: Initializes and exports singleton provider router
// This is the main entry point for using the data provider abstraction layer

import { TokenBucketRateLimiter } from "../rate-limiter/token-bucket.ts";
import { MemoryCache } from "../cache/memory-cache.ts";
import { getRateLimits } from "../config/rate-limits.ts";
import { FinnhubClient } from "./finnhub-client.ts";
import { MassiveClient } from "./massive-client.ts";
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
  const alpacaApiKey = Deno.env.get("ALPACA_API_KEY");
  const alpacaApiSecret = Deno.env.get("ALPACA_API_SECRET");

  if (!finnhubApiKey || !massiveApiKey) {
    throw new Error("Missing required API keys: FINNHUB_API_KEY and MASSIVE_API_KEY");
  }

  if (!alpacaApiKey || !alpacaApiSecret) {
    console.warn("[Provider Factory] ALPACA_API_KEY or ALPACA_API_SECRET not set - Alpaca provider will not be available");
  }

  const finnhubClient = new FinnhubClient(
    finnhubApiKey,
    rateLimiterInstance,
    cacheInstance
  );

  const massiveClient = new MassiveClient(
    massiveApiKey,
    rateLimiterInstance,
    cacheInstance
  );

  const yahooFinanceClient = new YahooFinanceClient(
    cacheInstance
  );

  const alpacaClient = (alpacaApiKey && alpacaApiSecret) ? new AlpacaClient(alpacaApiKey, alpacaApiSecret) : null;

  // Warm Alpaca assets cache on startup to avoid validation delays
  if (alpacaClient) {
    alpacaClient.getAssets().then(() => {
      console.log("[Provider Factory] Alpaca assets cache warmed");
    }).catch((error) => {
      console.warn("[Provider Factory] Failed to warm Alpaca assets cache:", error);
    });
  }

  console.log("[Provider Factory] Provider clients initialized");

  // Initialize router with custom policy for intraday vs historical data
  const providers: Record<string, any> = {
    finnhub: finnhubClient,
    massive: massiveClient,
    yahoo: yahooFinanceClient,
  };

  if (alpacaClient) {
    providers.alpaca = alpacaClient;
  }

  // Custom policy: Alpaca for real-time and historical data
  const policy = {
    quote: {
      primary: alpacaClient ? "alpaca" as ProviderId : "finnhub" as ProviderId,
      fallback: "finnhub" as ProviderId,
    },
    historicalBars: {
      primary: alpacaClient ? "alpaca" as ProviderId : "massive" as ProviderId, // Alpaca preferred, fallback to Polygon
      fallback: "finnhub" as ProviderId,
    },
    news: {
      primary: alpacaClient ? "alpaca" as ProviderId : "finnhub" as ProviderId,
      fallback: "finnhub" as ProviderId,
    },
    optionsChain: {
      primary: "yahoo" as ProviderId,
      fallback: undefined,
    },
  };

  routerInstance = new ProviderRouter(providers, policy);

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
 * Inject Supabase client into providers for distributed rate limiting
 * Call this in Edge functions that need coordinated rate limiting
 */
export function injectSupabaseClient(supabase: any): void {
  if (!routerInstance) {
    initializeProviders();
  }
  
  // Inject into Massive/Polygon client
  const router = routerInstance as any;
  const massiveProvider = router.providers?.get("massive");
  if (massiveProvider && typeof massiveProvider.setSupabaseClient === "function") {
    massiveProvider.setSupabaseClient(supabase);
    console.log("[Provider Factory] Injected Supabase client into Massive provider");
  }
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
