// TokenBucketRateLimiter: Pre-emptive rate limiting to avoid 429 errors
// Supports both per-second and per-minute buckets for fine-grained control

import type { ProviderId } from "../providers/types.ts";
import { RateLimitExceededError } from "../providers/types.ts";

export interface RateLimitConfig {
  maxPerSecond: number;
  maxPerMinute: number;
}

export interface TokenBucket {
  capacity: number;
  tokens: number;
  refillRate: number; // tokens per millisecond
  lastRefill: number; // timestamp in milliseconds
}

/**
 * Token bucket rate limiter with dual buckets (per-second and per-minute)
 * Both buckets must have capacity for a request to proceed
 */
export class TokenBucketRateLimiter {
  private buckets: Map<
    ProviderId,
    { second: TokenBucket; minute: TokenBucket }
  >;
  private config: Map<ProviderId, RateLimitConfig>;
  private readonly maxWaitMs: number;

  constructor(
    configs: Record<ProviderId, RateLimitConfig>,
    maxWaitMs: number = 5000,
  ) {
    this.buckets = new Map();
    this.config = new Map(
      Object.entries(configs) as [ProviderId, RateLimitConfig][],
    );
    this.maxWaitMs = maxWaitMs;

    // Initialize buckets for each provider
    for (const [provider, config] of this.config.entries()) {
      const now = Date.now();
      this.buckets.set(provider, {
        second: {
          capacity: config.maxPerSecond,
          tokens: config.maxPerSecond,
          refillRate: config.maxPerSecond / 1000, // tokens per ms
          lastRefill: now,
        },
        minute: {
          capacity: config.maxPerMinute,
          tokens: config.maxPerMinute,
          refillRate: config.maxPerMinute / 60000, // tokens per ms
          lastRefill: now,
        },
      });
    }
  }

  /**
   * Attempt to acquire a token from both buckets
   * Throws RateLimitExceededError if unable to acquire within maxWaitMs
   */
  async acquire(provider: ProviderId, cost: number = 1): Promise<void> {
    const buckets = this.buckets.get(provider);
    if (!buckets) {
      throw new Error(`Unknown provider: ${provider}`);
    }

    const startTime = Date.now();

    while (true) {
      const now = Date.now();

      // Refill both buckets
      this.refillBucket(buckets.second, now);
      this.refillBucket(buckets.minute, now);

      // Check if both buckets have capacity
      if (buckets.second.tokens >= cost && buckets.minute.tokens >= cost) {
        // Consume tokens from both buckets
        buckets.second.tokens -= cost;
        buckets.minute.tokens -= cost;
        return;
      }

      // Check if we've exceeded max wait time
      if (now - startTime >= this.maxWaitMs) {
        const retryAfter = this.calculateRetryAfter(buckets);
        throw new RateLimitExceededError(provider, retryAfter);
      }

      // Calculate how long to wait before next attempt
      const waitMs = this.calculateWaitTime(buckets, cost);
      await this.sleep(Math.min(waitMs, 100)); // Poll every 100ms max
    }
  }

  /**
   * Refill a bucket based on elapsed time since last refill
   */
  private refillBucket(bucket: TokenBucket, now: number): void {
    const elapsedMs = now - bucket.lastRefill;
    const tokensToAdd = elapsedMs * bucket.refillRate;

    bucket.tokens = Math.min(bucket.capacity, bucket.tokens + tokensToAdd);
    bucket.lastRefill = now;
  }

  /**
   * Calculate how long to wait before tokens become available
   */
  private calculateWaitTime(
    buckets: { second: TokenBucket; minute: TokenBucket },
    cost: number,
  ): number {
    const secondWait = buckets.second.tokens < cost
      ? (cost - buckets.second.tokens) / buckets.second.refillRate
      : 0;

    const minuteWait = buckets.minute.tokens < cost
      ? (cost - buckets.minute.tokens) / buckets.minute.refillRate
      : 0;

    return Math.max(secondWait, minuteWait);
  }

  /**
   * Calculate retry-after time in seconds
   */
  private calculateRetryAfter(
    buckets: { second: TokenBucket; minute: TokenBucket },
  ): number {
    const secondRetry = Math.ceil(
      (buckets.second.capacity - buckets.second.tokens) /
        buckets.second.refillRate / 1000,
    );
    const minuteRetry = Math.ceil(
      (buckets.minute.capacity - buckets.minute.tokens) /
        buckets.minute.refillRate / 1000,
    );
    return Math.max(secondRetry, minuteRetry);
  }

  /**
   * Query current token availability for observability
   */
  getStatus(provider: ProviderId): { second: number; minute: number } | null {
    const buckets = this.buckets.get(provider);
    if (!buckets) return null;

    const now = Date.now();
    this.refillBucket(buckets.second, now);
    this.refillBucket(buckets.minute, now);

    return {
      second: buckets.second.tokens,
      minute: buckets.minute.tokens,
    };
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}
