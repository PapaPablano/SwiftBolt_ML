// Resample m15 → h1/h4/d1 with START timestamps (preserves existing convention)
// Lightweight RTH detection without external dependencies

import type { Bar } from "../providers/types.ts";

type SessionPolicy = 'rth' | 'all';
type ResampleTarget = 'h1' | 'h4' | 'd1';

/**
 * Check if timestamp (ms) falls within RTH (09:30-16:00 ET)
 * Simplified DST handling - covers both EST/EDT windows
 */
function isWithinRTH(timestampMs: number): boolean {
  const d = new Date(timestampMs);
  const utcHour = d.getUTCHours();
  const utcMin = d.getUTCMinutes();
  const dayOfWeek = d.getUTCDay();
  
  // Weekend check
  if (dayOfWeek === 0 || dayOfWeek === 6) return false;
  
  // RTH: 09:30-16:00 ET
  // EST (winter): UTC-5 → RTH is 14:30-21:00 UTC
  // EDT (summer): UTC-4 → RTH is 13:30-20:00 UTC
  // Conservative window: 13:30-21:00 UTC covers both
  const utcMinutes = utcHour * 60 + utcMin;
  const rthStartUTC = 13 * 60 + 30; // 13:30 UTC
  const rthEndUTC = 21 * 60; // 21:00 UTC
  
  return utcMinutes >= rthStartUTC && utcMinutes < rthEndUTC;
}

/**
 * Compute bucket START timestamp (ms) for a given bar
 * Returns window start, not close (preserves existing convention)
 */
function getBucketStart(timestampMs: number, target: ResampleTarget, session: SessionPolicy): number {
  const d = new Date(timestampMs);
  
  if (target === 'h1') {
    // Truncate to hour start
    return new Date(d.getFullYear(), d.getMonth(), d.getDate(), d.getHours(), 0, 0, 0).getTime();
  }
  
  if (target === 'h4') {
    // Truncate to 4-hour blocks: 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC
    const blockHour = Math.floor(d.getHours() / 4) * 4;
    return new Date(d.getFullYear(), d.getMonth(), d.getDate(), blockHour, 0, 0, 0).getTime();
  }
  
  if (target === 'd1') {
    if (session === 'rth') {
      // RTH daily: bucket starts at calendar day (00:00 local)
      // This aligns with market session boundaries
      const dayStart = new Date(d.getFullYear(), d.getMonth(), d.getDate(), 0, 0, 0, 0);
      return dayStart.getTime();
    } else {
      // All-sessions: calendar day start UTC
      return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate(), 0, 0, 0, 0)).getTime();
    }
  }
  
  return timestampMs;
}

/**
 * Resample m15 bars to h1/h4/d1
 * Preserves START timestamp convention for backward compatibility
 * 
 * @param m15Bars - Array of 15-minute bars (must have timestamp in ms)
 * @param target - Target timeframe ('h1', 'h4', or 'd1')
 * @param options - Optional configuration
 * @returns Resampled bars with START timestamps
 */
export function resampleBars(
  m15Bars: Bar[],
  target: ResampleTarget,
  options: { session?: SessionPolicy; symbol?: string } = {}
): Bar[] {
  if (!m15Bars.length) return [];
  
  const session = options.session ?? 'all';
  const buckets = new Map<number, Bar[]>();
  
  // Group bars by bucket
  for (const bar of m15Bars) {
    // Filter RTH if needed
    if (session === 'rth' && !isWithinRTH(bar.timestamp)) continue;
    
    const bucketStart = getBucketStart(bar.timestamp, target, session);
    const existing = buckets.get(bucketStart);
    if (existing) {
      existing.push(bar);
    } else {
      buckets.set(bucketStart, [bar]);
    }
  }
  
  // Aggregate each bucket
  const resampled: Bar[] = [];
  for (const [bucketStart, bars] of buckets) {
    bars.sort((a, b) => a.timestamp - b.timestamp);
    
    resampled.push({
      timestamp: bucketStart, // ← START timestamp (preserves convention)
      open: bars[0].open,
      high: Math.max(...bars.map(b => b.high)),
      low: Math.min(...bars.map(b => b.low)),
      close: bars[bars.length - 1].close,
      volume: bars.reduce((sum, b) => sum + b.volume, 0),
    });
  }
  
  resampled.sort((a, b) => a.timestamp - b.timestamp);
  return resampled;
}

/**
 * Stitch daily series: older Yahoo + newer Polygon-derived
 * Deduplicates on timestamp, prefers newer data at seam
 * 
 * @param olderBars - Bars before seam (e.g., from Yahoo)
 * @param newerBars - Bars at/after seam (e.g., from Polygon-derived)
 * @param seamTimestampMs - Boundary timestamp in milliseconds
 * @returns Merged and deduplicated bars
 */
export function stitchDailySeries(
  olderBars: Bar[],
  newerBars: Bar[],
  seamTimestampMs: number
): Bar[] {
  const older = olderBars.filter(b => b.timestamp < seamTimestampMs);
  const newer = newerBars.filter(b => b.timestamp >= seamTimestampMs);
  
  // Deduplicate by timestamp (keep first occurrence)
  const seen = new Set<number>();
  const merged: Bar[] = [];
  
  for (const bar of [...older, ...newer]) {
    if (!seen.has(bar.timestamp)) {
      seen.add(bar.timestamp);
      merged.push(bar);
    }
  }
  
  merged.sort((a, b) => a.timestamp - b.timestamp);
  return merged;
}
