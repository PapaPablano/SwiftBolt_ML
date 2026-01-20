// Provider Factory: Initializes and exports singleton provider router
// This is the main entry point for using the data provider abstraction layer

import { TokenBucketRateLimiter } from "../rate-limiter/token-bucket.ts";
import { MemoryCache } from "../cache/memory-cache.ts";
import { getRateLimits } from "../config/rate-limits.ts";
import { FinnhubClient } from "./finnhub-client.ts";
import { MassiveClient } from "./massive-client.ts";
import { TradierClient } from "./tradier-client.ts";
import { AlpacaClient } from "./alpaca-client.ts";
import { YahooFinanceClient } from "./yahoo-finance-client.ts";
import { ProviderRouter } from "./router.ts";
import type { DataProviderAbstraction } from "./abstraction.ts";
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
  const tradierApiKey = Deno.env.get("TRADIER_API_KEY");
  const alpacaApiKey = Deno.env.get("ALPACA_API_KEY");
  const alpacaApiSecret = Deno.env.get("ALPACA_API_SECRET");

  if (!finnhubApiKey) {
    throw new Error("Missing required API key: FINNHUB_API_KEY");
  }

  if (!alpacaApiKey || !alpacaApiSecret) {
    console.warn("[Provider Factory] ALPACA_API_KEY or ALPACA_API_SECRET not set - Alpaca provider will not be available");
  }

  if (!massiveApiKey) {
    console.warn("[Provider Factory] MASSIVE_API_KEY not set - Polygon/Massive provider will not be available");
  }

  if (!tradierApiKey) {
    console.warn("[Provider Factory] TRADIER_API_KEY not set - Tradier provider will not be available");
  }

  const finnhubClient = new FinnhubClient(
    finnhubApiKey,
    rateLimiterInstance,
    cacheInstance
  );

  const yahooClient = new YahooFinanceClient(cacheInstance);

  const massiveClient = massiveApiKey ? new MassiveClient(
    massiveApiKey,
    rateLimiterInstance,
    cacheInstance
  ) : null;

  const tradierClient = tradierApiKey ? new TradierClient(tradierApiKey) : null;
  const alpacaClient = (alpacaApiKey && alpacaApiSecret) ? new AlpacaClient(
    alpacaApiKey,
    alpacaApiSecret,
    rateLimiterInstance,
    cacheInstance
  ) : null;

  // Warm Alpaca assets cache on startup to avoid validation delays
  if (alpacaClient) {
    console.log("[Provider Factory] Alpaca credentials check: {");
    console.log(`  hasApiKey: ${!!alpacaApiKey},`);
    console.log(`  apiKeyLength: ${alpacaApiKey?.length},`);
    console.log(`  hasApiSecret: ${!!alpacaApiSecret},`);
    console.log(`  apiSecretLength: ${alpacaApiSecret?.length}`);
    console.log("}");

    console.log("[Provider Factory] Alpaca client status: { initialized: true, willUsePrimary: \"alpaca\" }");

    alpacaClient.getAssets().then(() => {
      console.log("[Provider Factory] Alpaca assets cache warmed successfully");
    }).catch((error) => {
      console.warn("[Provider Factory] Failed to warm Alpaca assets cache:", error);
    });
  }

  console.log("[Provider Factory] Provider clients initialized");

  // Initialize router with Alpaca-only policy for OHLCV data
  const providers = new Map<ProviderId, DataProviderAbstraction>([
    ["finnhub", finnhubClient],
  ]);

  if (massiveClient) {
    providers.set("massive", massiveClient);
  }

  if (tradierClient) {
    providers.set("tradier", tradierClient);
  }

  if (alpacaClient) {
    providers.set("alpaca", alpacaClient);
  }

  providers.set("yahoo", yahooClient);

  // Alpaca-only policy: Single source of truth for all OHLCV data
  // Finnhub remains for news only (no options chain support in current implementation)
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
      primary: alpacaClient ? "alpaca" as ProviderId : "finnhub" as ProviderId,
      fallback: "finnhub" as ProviderId,
    },
    optionsChain: {
      primary: "yahoo" as ProviderId,
      fallback: alpacaClient ? "alpaca" as ProviderId : undefined,
    },
  };

  routerInstance = new ProviderRouter(Object.fromEntries(providers), policy);

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
type ProviderWithSupabase = {
  setSupabaseClient?: (supabase: unknown) => void;
};

export function injectSupabaseClient(supabase: unknown): void {
  if (!routerInstance) {
    initializeProviders();
  }

  // Inject into Massive/Polygon client (if available)
  const router = routerInstance as unknown as { providers?: Map<string, ProviderWithSupabase> };
  const massiveProvider = router.providers?.get("massive");
  if (massiveProvider?.setSupabaseClient) {
    massiveProvider.setSupabaseClient(supabase);
    console.log("[Provider Factory] Injected Supabase client into Massive provider");
  } else {
    console.log("[Provider Factory] Massive provider not available, skipping Supabase client injection");
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

/**
 * Get the Alpaca client directly for crypto/options operations
 * Returns null if Alpaca is not configured
 */
export function getAlpacaClient(): AlpacaClient | null {
  // Initialize if not already done
  if (!routerInstance) {
    initializeProviders();
  }

  const alpacaApiKey = Deno.env.get("ALPACA_API_KEY");
  const alpacaApiSecret = Deno.env.get("ALPACA_API_SECRET");

  if (!alpacaApiKey || !alpacaApiSecret) {
    return null;
  }

  // Create a new Alpaca client instance (shares the same rate limiter and cache)
  if (!rateLimiterInstance || !cacheInstance) {
    return null;
  }

  return new AlpacaClient(
    alpacaApiKey,
    alpacaApiSecret,
    rateLimiterInstance,
    cacheInstance
  );
}
