/**
 * Shared hook for Support/Resistance polling
 * ============================================
 *
 * Single source of truth for the /api/v1/support-resistance endpoint.
 * Both useIndicators and usePivotLevels previously polled this same URL
 * independently every 30 seconds. This hook consolidates to one fetch per
 * 30-second cycle and returns typed data for both consumers.
 *
 * Usage:
 *   const { srData, pivotLevels, loading, error } = useSupportResistance('AAPL', '1h');
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import type { SupportResistanceData } from './useIndicators';
import type { PivotLevelData, PivotMetrics } from './usePivotLevels';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Period-based color scheme (matching TradingView) — duplicated here to keep
// usePivotLevels free of its own fetch logic while retaining the mapping.
const PERIOD_COLORS: Record<number, string> = {
  3: '#A9A9A9',   // Dark gray (ultra micro)
  5: '#C0C0C0',   // Silver (micro)
  10: '#4D94FF',  // Blue (short-short)
  13: '#5CA7FF',  // Light blue
  25: '#3399FF',  // Cyan (short)
  50: '#00CCCC',  // Bright cyan (medium)
  100: '#FFD700', // Gold (long)
  200: '#FF8C00', // Dark orange (very long)
};

/**
 * Convert frontend timeframe format (1h, 4h, 1D, 15m) to backend format (h1, h4, d1, m15)
 */
function convertTimeframeFormat(frontendTimeframe: string): string {
  const mapping: Record<string, string> = {
    '15m': 'm15',
    '1h': 'h1',
    '4h': 'h4',
    '1D': 'd1',
    D: 'd1',
  };
  return mapping[frontendTimeframe] || frontendTimeframe;
}

export interface SupportResistanceResult {
  /** Full S/R response (used by IndicatorPanel / TradingViewChart) */
  srData: SupportResistanceData | null;
  /** Pivot levels with presentation metadata (used by PivotLevelsPanel) */
  pivotLevels: PivotLevelData[];
  /** Pivot summary metrics derived from the same response */
  pivotMetrics: PivotMetrics | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useSupportResistance(symbol: string, timeframe: string): SupportResistanceResult {
  const [srData, setSrData] = useState<SupportResistanceData | null>(null);
  const [pivotLevels, setPivotLevels] = useState<PivotLevelData[]>([]);
  const [pivotMetrics, setPivotMetrics] = useState<PivotMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const fetchData = useCallback(async () => {
    if (!symbol || !timeframe) return;

    setLoading(true);
    setError(null);

    try {
      const backendTimeframe = convertTimeframeFormat(timeframe);
      const url = `${API_BASE_URL}/api/v1/support-resistance?symbol=${symbol}&timeframe=${backendTimeframe}`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }

      const result: SupportResistanceData = await response.json();

      // Provide full response to srData consumers (useIndicators)
      setSrData(result);

      // Derive pivot level presentation data for usePivotLevels consumers
      const rawPivots = result.pivot_levels || [];
      setPivotLevels(
        rawPivots.map((level) => ({
          ...level,
          high_status: level.high_status as PivotLevelData['high_status'],
          low_status: level.low_status as PivotLevelData['low_status'],
          label: `P${level.period}`,
          color: PERIOD_COLORS[level.period] || '#808080',
        }))
      );

      // Build pivot metrics from the available S/R fields
      if (result.nearest_support || result.nearest_resistance) {
        setPivotMetrics({
          overall_strength: 0.5,
          pivot_count: rawPivots.length,
          confidence: (result as any).confidence || 0.5,
          high_pivot_count: rawPivots.filter((l) => l.level_high != null).length,
          low_pivot_count: rawPivots.filter((l) => l.level_low != null).length,
          period_effectiveness: [],
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch support/resistance data');
      console.error('Error fetching support/resistance:', err);
    } finally {
      setLoading(false);
    }
  }, [symbol, timeframe]);

  useEffect(() => {
    fetchData();
    intervalRef.current = setInterval(fetchData, 30_000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchData]);

  return { srData, pivotLevels, pivotMetrics, loading, error, refetch: fetchData };
}
