// Feature flags for gradual rollout of resampling and indicator features
// Set via environment variables in Supabase dashboard

/**
 * Feature flags for data processing
 * All flags default to false for safety
 */
export const FEATURE_FLAGS = {
  // Resample from m15 instead of fetching directly from provider
  // Enable per-timeframe for gradual rollout
  RESAMPLE_H1_FROM_M15: Deno.env.get("RESAMPLE_H1_FROM_M15") === "true",
  RESAMPLE_H4_FROM_M15: Deno.env.get("RESAMPLE_H4_FROM_M15") === "true",
  RESAMPLE_D1_FROM_M15: Deno.env.get("RESAMPLE_D1_FROM_M15") === "true",
  
  // Attach indicators on-read (EMA, RSI, ATR)
  ATTACH_INDICATORS: Deno.env.get("ATTACH_INDICATORS") === "true",
  
  // Include SuperTrend in indicators (more compute-intensive)
  INCLUDE_SUPERTREND: Deno.env.get("INCLUDE_SUPERTREND") === "true",
  
  // Session policy for daily resampling
  // 'rth' = Regular Trading Hours only (09:30-16:00 ET)
  // 'all' = Include pre/post market
  DAILY_SESSION_POLICY: (Deno.env.get("DAILY_SESSION_POLICY") || "all") as "rth" | "all",
  
  // Seam timestamp for daily stitching (Unix seconds)
  // Default: 2 years ago from now
  DAILY_STITCH_SEAM_TS: parseInt(
    Deno.env.get("DAILY_STITCH_SEAM_TS") || 
    String(Math.floor(Date.now() / 1000) - 365 * 2 * 24 * 3600),
    10
  ),
} as const;

/**
 * Check if resampling is enabled for a given timeframe
 */
export function shouldResample(timeframe: string): boolean {
  switch (timeframe) {
    case "h1":
      return FEATURE_FLAGS.RESAMPLE_H1_FROM_M15;
    case "h4":
      return FEATURE_FLAGS.RESAMPLE_H4_FROM_M15;
    case "d1":
      return FEATURE_FLAGS.RESAMPLE_D1_FROM_M15;
    default:
      return false;
  }
}

/**
 * Log current feature flag state (useful for debugging)
 */
export function logFeatureFlags(): void {
  console.log("[FeatureFlags] Current configuration:", {
    resample_h1: FEATURE_FLAGS.RESAMPLE_H1_FROM_M15,
    resample_h4: FEATURE_FLAGS.RESAMPLE_H4_FROM_M15,
    resample_d1: FEATURE_FLAGS.RESAMPLE_D1_FROM_M15,
    attach_indicators: FEATURE_FLAGS.ATTACH_INDICATORS,
    include_supertrend: FEATURE_FLAGS.INCLUDE_SUPERTREND,
    daily_session: FEATURE_FLAGS.DAILY_SESSION_POLICY,
    seam_ts: new Date(FEATURE_FLAGS.DAILY_STITCH_SEAM_TS * 1000).toISOString(),
  });
}
