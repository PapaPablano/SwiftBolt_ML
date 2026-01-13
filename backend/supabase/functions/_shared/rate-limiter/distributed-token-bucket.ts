// Distributed Token Bucket Rate Limiter
// Uses Postgres-backed token bucket for coordinated rate limiting across all workers

import type { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";
import type { ProviderId } from "../providers/types.ts";

type DistributedProviderId = ProviderId | "polygon";

export interface TokenStatus {
  provider: DistributedProviderId;
  available_tokens: number;
  capacity: number;
  refill_rate: number;
  seconds_until_full: number;
}

/**
 * Acquire a token from the distributed token bucket
 * Returns true if token was acquired, false if bucket is empty
 */
export async function acquireToken(
  supabase: SupabaseClient,
  provider: DistributedProviderId,
  cost: number = 1
): Promise<boolean> {
  const { data, error } = await supabase.rpc("take_token", {
    p_provider: provider,
    p_cost: cost,
  });

  if (error) {
    console.error(`[TokenBucket] Error acquiring token for ${provider}:`, error);
    throw error;
  }

  return data === true;
}

/**
 * Wait for a token to become available, with randomized backoff
 * This prevents thundering herd when multiple workers are waiting
 */
export async function waitForToken(
  supabase: SupabaseClient,
  provider: DistributedProviderId,
  cost: number = 1,
  maxWaitMs: number = 60000
): Promise<void> {
  const startTime = Date.now();
  let attempts = 0;

  while (Date.now() - startTime < maxWaitMs) {
    const acquired = await acquireToken(supabase, provider, cost);
    
    if (acquired) {
      if (attempts > 0) {
        console.log(`[TokenBucket] Acquired token for ${provider} after ${attempts} attempts`);
      }
      return;
    }

    attempts++;
    
    // Randomized backoff between 700-1300ms to avoid stampede
    const backoffMs = 700 + Math.random() * 600;
    await new Promise((resolve) => setTimeout(resolve, backoffMs));
  }

  throw new Error(`[TokenBucket] Timeout waiting for token (${provider}, cost=${cost})`);
}

/**
 * Get current token bucket status for a provider
 */
export async function getTokenStatus(
  supabase: SupabaseClient,
  provider: DistributedProviderId
): Promise<TokenStatus | null> {
  const { data, error } = await supabase.rpc("get_token_status", {
    p_provider: provider,
  });

  if (error) {
    console.error(`[TokenBucket] Error getting status for ${provider}:`, error);
    return null;
  }

  return data?.[0] || null;
}

/**
 * Estimate token cost for a historical bars request
 * Based on expected number of API pages needed
 */
export function estimatePolygonCost(params: {
  fromTimestamp: number;
  toTimestamp: number;
  timeframe: string;
}): number {
  const { fromTimestamp, toTimestamp, timeframe } = params;
  
  // Bars per day (RTH - Regular Trading Hours)
  const barsPerDay: Record<string, number> = {
    m15: 26,  // 6.5 hours / 15 min
    h1: 6,    // 6.5 hours
    h4: 2,    // 6.5 hours / 4
    d1: 1,
  };

  const bars = barsPerDay[timeframe] || 26;
  const days = Math.ceil((toTimestamp - fromTimestamp) / 86400);
  const totalBars = days * bars;
  
  // Polygon page size is 50,000 results
  const pageSize = 50000;
  const estimatedPages = Math.max(1, Math.ceil(totalBars / pageSize));

  return estimatedPages;
}

/**
 * Sleep with jitter to avoid synchronized retries
 */
export async function sleepWithJitter(baseMs: number, jitterMs: number = 500): Promise<void> {
  const totalMs = baseMs + Math.random() * jitterMs;
  await new Promise((resolve) => setTimeout(resolve, totalMs));
}
