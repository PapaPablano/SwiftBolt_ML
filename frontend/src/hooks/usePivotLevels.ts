/**
 * Hook to fetch pivot levels from the API
 * Uses support-resistance endpoint with polling for updates
 *
 * Features:
 * - Multi-period pivot detection
 * - Automatic refresh intervals
 * - Falls back gracefully on errors
 */

import { useState, useEffect, useCallback } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface PivotLevelData {
  period: number;
  level_high?: number;
  level_low?: number;
  high_status?: 'support' | 'resistance' | 'active' | 'inactive';
  low_status?: 'support' | 'resistance' | 'active' | 'inactive';
  label: string;
  color: string;
}

export interface PivotMetrics {
  overall_strength: number;
  pivot_count: number;
  confidence: number;
  high_pivot_count: number;
  low_pivot_count: number;
  top_period?: number;
  period_effectiveness: Array<{
    period: number;
    effectiveness: number;
    pivot_count: number;
  }>;
}

export interface PivotLevelsResponse {
  symbol: string;
  timeframe: string;
  pivot_levels: PivotLevelData[];
  metrics: PivotMetrics;
  timestamp: string;
  last_updated: string;
}

// Period-based color scheme (matching TradingView)
const PERIOD_COLORS: Record<number, string> = {
  3: '#A9A9A9',      // Dark gray (ultra micro)
  5: '#C0C0C0',      // Silver (micro)
  10: '#4D94FF',     // Blue (short-short)
  13: '#5CA7FF',     // Light blue
  25: '#3399FF',     // Cyan (short)
  50: '#00CCCC',     // Bright cyan (medium)
  100: '#FFD700',    // Gold (long)
  200: '#FF8C00',    // Dark orange (very long)
};

export const usePivotLevels = (symbol: string, timeframe: string) => {
  const [pivotLevels, setPivotLevels] = useState<PivotLevelData[]>([]);
  const [metrics, setMetrics] = useState<PivotMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch pivot levels from REST API
  const fetchPivotLevels = useCallback(async () => {
    if (!symbol || !timeframe) return;

    setLoading(true);
    setError(null);

    try {
      // Map horizon to timeframe format expected by backend
      const timeframeMap: Record<string, string> = {
        '15m': 'm15',
        '1h': 'h1',
        '4h': 'h4',
        '1D': 'd1'
      };
      const mappedTimeframe = timeframeMap[timeframe] || timeframe;
      
      // Use the existing support-resistance endpoint which includes pivot levels
      const response = await fetch(
        `${API_BASE_URL}/api/v1/support-resistance?symbol=${symbol}&timeframe=${mappedTimeframe}`
      );

      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }

      const result = await response.json();
      
      // Extract pivot levels from the support-resistance response
      const pivotData = result.pivot_levels || [];
      setPivotLevels(
        pivotData.map((level: any) => ({
          ...level,
          label: `P${level.period}`,
          color: PERIOD_COLORS[level.period] || '#808080',
        }))
      );
      
      // Build metrics from available data
      if (result.nearest_support || result.nearest_resistance) {
        setMetrics({
          overall_strength: 0.5,
          pivot_count: pivotData.length,
          confidence: result.confidence || 0.5,
          high_pivot_count: pivotData.filter((l: any) => l.level_high).length,
          low_pivot_count: pivotData.filter((l: any) => l.level_low).length,
          period_effectiveness: [],
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch pivot levels');
      console.error('Error fetching pivot levels:', err);
    } finally {
      setLoading(false);
    }
  }, [symbol, timeframe]);

  // Initial fetch and setup
  useEffect(() => {
    fetchPivotLevels();

    // Refresh every 30 seconds (polling instead of WebSocket)
    const interval = setInterval(fetchPivotLevels, 30000);

    return () => {
      clearInterval(interval);
    };
  }, [symbol, timeframe, fetchPivotLevels]);

  return {
    pivotLevels,
    metrics,
    loading,
    error,
    refetch: fetchPivotLevels,
  };
};
