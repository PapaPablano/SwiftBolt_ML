/**
 * Hook to access pivot level data
 *
 * Data fetching is handled by useSupportResistance to avoid duplicate polls.
 * This hook is now a thin re-export of the pivotLevels/pivotMetrics slice
 * from that shared hook.
 *
 * Features:
 * - Multi-period pivot detection
 * - Automatic refresh intervals (via useSupportResistance)
 * - Falls back gracefully on errors
 */

import { useSupportResistance } from './useSupportResistance';

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

export const usePivotLevels = (symbol: string, timeframe: string) => {
  const { pivotLevels, pivotMetrics, loading, error, refetch } = useSupportResistance(
    symbol,
    timeframe
  );
  return {
    pivotLevels,
    metrics: pivotMetrics,
    loading,
    error,
    refetch,
  };
};
