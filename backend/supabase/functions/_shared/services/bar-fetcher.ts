// Bar fetcher service with resampling support
// Integrates feature flags, provider routing, and resampling logic

import type { Bar } from "../providers/types.ts";
import type { ProviderRouter } from "../providers/router.ts";
import { MassiveClient } from "../providers/massive-client.ts";
import { resampleBars } from "../utils/resampler.ts";
import { attachIndicators, type BarWithIndicators } from "../utils/indicators.ts";
import { FEATURE_FLAGS, shouldResample } from "../config/feature-flags.ts";

export interface FetchBarsOptions {
  symbol: string;
  timeframe: string;
  startTimestamp: number; // Unix seconds
  endTimestamp: number;   // Unix seconds
  includeIndicators?: boolean;
}

export interface FetchBarsResult {
  bars: Bar[] | BarWithIndicators[];
  provider: string;
  wasResampled: boolean;
  originalCount?: number; // If resampled, count of m15 bars
}

/**
 * Fetch bars with optional resampling based on feature flags
 * This is the main entry point for data fetching with resampling support
 */
export async function fetchBarsWithResampling(
  router: ProviderRouter,
  options: FetchBarsOptions
): Promise<FetchBarsResult> {
  const { symbol, timeframe, startTimestamp, endTimestamp, includeIndicators = false } = options;
  
  // Check if resampling is enabled for this timeframe
  const shouldResampleTF = shouldResample(timeframe);
  
  if (!shouldResampleTF) {
    // Original path: fetch directly from provider
    console.log(`[BarFetcher] Direct fetch: ${symbol}/${timeframe}`);
    
    const bars = await router.getHistoricalBars({
      symbol,
      timeframe: timeframe as any,
      start: startTimestamp,
      end: endTimestamp,
    });
    
    // Determine provider
    const healthStatus = router.getHealthStatus();
    const isIntraday = ["m15", "h1", "h4"].includes(timeframe);
    const provider = isIntraday ? "tradier" : "yahoo";
    
    // Attach indicators if requested
    const finalBars = includeIndicators 
      ? attachIndicators(bars, FEATURE_FLAGS.INCLUDE_SUPERTREND)
      : bars;
    
    return {
      bars: finalBars,
      provider,
      wasResampled: false,
    };
  }
  
  // New path: fetch m15 and resample
  console.log(`[BarFetcher] Resampling ${timeframe} from m15 for ${symbol}`);
  
  // Get MassiveClient from router (assumes router has massive client)
  // For now, we'll fetch m15 via router and resample
  // TODO: In production, extract MassiveClient directly for pagination
  
  let m15Bars: Bar[];
  
  try {
    // Try to get m15 bars - this will use the router's provider selection
    m15Bars = await router.getHistoricalBars({
      symbol,
      timeframe: "m15" as any,
      start: startTimestamp,
      end: endTimestamp,
    });
    
    console.log(`[BarFetcher] Fetched ${m15Bars.length} m15 bars for resampling`);
  } catch (error) {
    console.error(`[BarFetcher] Failed to fetch m15 bars:`, error);
    throw error;
  }
  
  // Resample to target timeframe
  const resampled = resampleBars(
    m15Bars,
    timeframe as 'h1' | 'h4' | 'd1',
    { 
      session: FEATURE_FLAGS.DAILY_SESSION_POLICY,
      symbol 
    }
  );
  
  console.log(`[BarFetcher] Resampled ${m15Bars.length} m15 bars → ${resampled.length} ${timeframe} bars`);
  
  // Attach indicators if requested
  const finalBars = includeIndicators
    ? attachIndicators(resampled, FEATURE_FLAGS.INCLUDE_SUPERTREND)
    : resampled;
  
  return {
    bars: finalBars,
    provider: "polygon", // Resampled data comes from Polygon m15
    wasResampled: true,
    originalCount: m15Bars.length,
  };
}

/**
 * Helper to extract MassiveClient from router for direct pagination
 * This is more efficient than going through router for large date ranges
 */
export function getMassiveClientFromRouter(router: ProviderRouter): MassiveClient | null {
  // This requires accessing router internals
  // For now, return null and use router path
  // TODO: Expose MassiveClient getter in router
  return null;
}
