// ProviderRouter: Orchestrates provider selection and fallback logic
// Routes requests to the best available provider based on health, rate limits, and data type

import type {
  DataProviderAbstraction,
  HistoricalBarsRequest,
  NewsRequest,
  OptionsChainRequest,
} from "./abstraction.ts";
import type { Bar, NewsItem, OptionsChain, Quote, ProviderId } from "./types.ts";
import {
  ProviderUnavailableError,
  RateLimitExceededError,
} from "./types.ts";

export interface ProviderHealth {
  provider: ProviderId;
  isHealthy: boolean;
  lastCheck: number;
  consecutiveFailures: number;
}

export interface RouterPolicy {
  // Primary provider for each operation type
  quote: {
    primary: ProviderId;
    fallback?: ProviderId;
  };
  historicalBars: {
    primary: ProviderId;
    fallback?: ProviderId;
  };
  news: {
    primary: ProviderId;
    fallback?: ProviderId;
  };
  optionsChain: {
    primary: ProviderId;
    fallback?: ProviderId;
  };
}

const DEFAULT_POLICY: RouterPolicy = {
  quote: {
    primary: "finnhub",
    fallback: "massive",
  },
  historicalBars: {
    primary: "yahoo", // Yahoo Finance has real-time intraday data (no delay!)
    fallback: "finnhub", // Finnhub as fallback
  },
  news: {
    primary: "finnhub", // Massive free tier doesn't support news
    fallback: undefined,
  },
  optionsChain: {
    primary: "yahoo", // Yahoo Finance provides free options data with 15-min delay
    fallback: undefined,
  },
};

export class ProviderRouter {
  private providers: Map<ProviderId, DataProviderAbstraction>;
  private health: Map<ProviderId, ProviderHealth>;
  private policy: RouterPolicy;
  private readonly healthCheckInterval: number = 60000; // 1 minute
  private readonly maxConsecutiveFailures: number = 3;
  private readonly cooldownPeriod: number = 300000; // 5 minutes

  constructor(
    providers: Record<ProviderId, DataProviderAbstraction>,
    policy: RouterPolicy = DEFAULT_POLICY
  ) {
    this.providers = new Map(Object.entries(providers) as [ProviderId, DataProviderAbstraction][]);
    this.policy = policy;
    this.health = new Map();

    // Initialize health status for all providers
    for (const providerId of this.providers.keys()) {
      this.health.set(providerId, {
        provider: providerId,
        isHealthy: true,
        lastCheck: Date.now(),
        consecutiveFailures: 0,
      });
    }

    // Start background health checks
    this.startHealthChecks();
  }

  async getQuote(symbols: string[]): Promise<Quote[]> {
    const { primary, fallback } = this.policy.quote;

    try {
      const provider = await this.selectProvider(primary, fallback);
      const result = await provider.getQuote(symbols);
      this.recordSuccess(primary);
      return result;
    } catch (error) {
      console.error(`[Router] getQuote failed:`, error);
      this.recordFailure(primary);

      // Try fallback if available and not a rate limit error
      if (fallback && !(error instanceof RateLimitExceededError)) {
        try {
          console.log(`[Router] Attempting fallback to ${fallback}`);
          const fallbackProvider = this.providers.get(fallback);
          if (fallbackProvider) {
            const result = await fallbackProvider.getQuote(symbols);
            this.recordSuccess(fallback);
            return result;
          }
        } catch (fallbackError) {
          console.error(`[Router] Fallback also failed:`, fallbackError);
          this.recordFailure(fallback);
        }
      }

      throw error;
    }
  }

  async getHistoricalBars(request: HistoricalBarsRequest): Promise<Bar[]> {
    const { primary, fallback } = this.policy.historicalBars;

    try {
      const provider = await this.selectProvider(primary, fallback);
      const result = await provider.getHistoricalBars(request);
      this.recordSuccess(primary);
      return result;
    } catch (error) {
      console.error(`[Router] getHistoricalBars failed:`, error);
      this.recordFailure(primary);

      // Try fallback if available and not a rate limit error
      if (fallback && !(error instanceof RateLimitExceededError)) {
        try {
          console.log(`[Router] Attempting fallback to ${fallback}`);
          const fallbackProvider = this.providers.get(fallback);
          if (fallbackProvider) {
            const result = await fallbackProvider.getHistoricalBars(request);
            this.recordSuccess(fallback);
            return result;
          }
        } catch (fallbackError) {
          console.error(`[Router] Fallback also failed:`, fallbackError);
          this.recordFailure(fallback);
        }
      }

      throw error;
    }
  }

  async getNews(request: NewsRequest): Promise<NewsItem[]> {
    const { primary, fallback } = this.policy.news;

    try {
      const provider = await this.selectProvider(primary, fallback);
      const result = await provider.getNews(request);
      this.recordSuccess(primary);
      return result;
    } catch (error) {
      console.error(`[Router] getNews failed:`, error);
      this.recordFailure(primary);

      // Try fallback if available and not a rate limit error
      if (fallback && !(error instanceof RateLimitExceededError)) {
        try {
          console.log(`[Router] Attempting fallback to ${fallback}`);
          const fallbackProvider = this.providers.get(fallback);
          if (fallbackProvider) {
            const result = await fallbackProvider.getNews(request);
            this.recordSuccess(fallback);
            return result;
          }
        } catch (fallbackError) {
          console.error(`[Router] Fallback also failed:`, fallbackError);
          this.recordFailure(fallback);
        }
      }

      throw error;
    }
  }

  async getOptionsChain(request: OptionsChainRequest): Promise<OptionsChain> {
    const { primary, fallback } = this.policy.optionsChain;

    try {
      const provider = await this.selectProvider(primary, fallback);

      // Check if provider supports options chain
      if (!provider.getOptionsChain) {
        throw new ProviderUnavailableError(primary);
      }

      const result = await provider.getOptionsChain(request);
      this.recordSuccess(primary);
      return result;
    } catch (error) {
      console.error(`[Router] getOptionsChain failed:`, error);
      this.recordFailure(primary);

      // Try fallback if available and not a rate limit error
      if (fallback && !(error instanceof RateLimitExceededError)) {
        try {
          console.log(`[Router] Attempting fallback to ${fallback}`);
          const fallbackProvider = this.providers.get(fallback);
          if (fallbackProvider && fallbackProvider.getOptionsChain) {
            const result = await fallbackProvider.getOptionsChain(request);
            this.recordSuccess(fallback);
            return result;
          }
        } catch (fallbackError) {
          console.error(`[Router] Fallback also failed:`, fallbackError);
          this.recordFailure(fallback);
        }
      }

      throw error;
    }
  }

  /**
   * Select the best provider based on health status
   * If primary is unhealthy and in cooldown, use fallback
   */
  private async selectProvider(
    primary: ProviderId,
    fallback?: ProviderId
  ): Promise<DataProviderAbstraction> {
    const primaryHealth = this.health.get(primary);
    const now = Date.now();

    // Check if primary is in cooldown period
    if (
      primaryHealth &&
      !primaryHealth.isHealthy &&
      now - primaryHealth.lastCheck < this.cooldownPeriod
    ) {
      console.log(`[Router] Primary provider ${primary} is in cooldown, using fallback`);

      if (fallback) {
        const fallbackHealth = this.health.get(fallback);
        if (fallbackHealth?.isHealthy) {
          const fallbackProvider = this.providers.get(fallback);
          if (fallbackProvider) {
            return fallbackProvider;
          }
        }
      }
    }

    // Use primary provider
    const provider = this.providers.get(primary);
    if (!provider) {
      throw new ProviderUnavailableError(primary);
    }

    return provider;
  }

  private recordSuccess(providerId: ProviderId): void {
    const health = this.health.get(providerId);
    if (health) {
      health.isHealthy = true;
      health.consecutiveFailures = 0;
      health.lastCheck = Date.now();
    }
  }

  private recordFailure(providerId: ProviderId): void {
    const health = this.health.get(providerId);
    if (health) {
      health.consecutiveFailures++;
      health.lastCheck = Date.now();

      if (health.consecutiveFailures >= this.maxConsecutiveFailures) {
        console.warn(`[Router] Marking provider ${providerId} as unhealthy`);
        health.isHealthy = false;
      }
    }
  }

  /**
   * Periodic health checks for all providers
   */
  private startHealthChecks(): void {
    setInterval(async () => {
      for (const [providerId, provider] of this.providers.entries()) {
        try {
          const isHealthy = await provider.healthCheck();
          const health = this.health.get(providerId);
          if (health) {
            health.isHealthy = isHealthy;
            health.lastCheck = Date.now();
            if (isHealthy) {
              health.consecutiveFailures = 0;
            }
          }
          console.log(`[Router] Health check for ${providerId}: ${isHealthy ? "healthy" : "unhealthy"}`);
        } catch (error) {
          console.error(`[Router] Health check failed for ${providerId}:`, error);
          this.recordFailure(providerId);
        }
      }
    }, this.healthCheckInterval);
  }

  /**
   * Get current health status for all providers (for observability)
   */
  getHealthStatus(): Map<ProviderId, ProviderHealth> {
    return new Map(this.health);
  }

  /**
   * Manually mark a provider as healthy (for testing or recovery)
   */
  markHealthy(providerId: ProviderId): void {
    const health = this.health.get(providerId);
    if (health) {
      health.isHealthy = true;
      health.consecutiveFailures = 0;
      health.lastCheck = Date.now();
    }
  }
}
