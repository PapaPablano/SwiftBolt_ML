/**
 * Hook to fetch technical indicators from the API
 * Includes: Polynomial S/R, Pivot Levels, Logistic Regression
 */

import { useState, useEffect, useCallback } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface PolynomialSRData {
  level: number;
  slope: number;
  trend: 'rising' | 'falling' | 'flat';
  forecast?: number[];
}

export interface PivotLevel {
  period: number;
  level_high?: number;
  level_low?: number;
  high_status?: string;
  low_status?: string;
}

export interface SupportResistanceData {
  symbol: string;
  current_price: number;
  last_updated?: string;
  nearest_support?: number;
  nearest_resistance?: number;
  support_distance_pct?: number;
  resistance_distance_pct?: number;
  bias?: 'bullish' | 'bearish' | 'neutral';
  polynomial_support?: PolynomialSRData;
  polynomial_resistance?: PolynomialSRData;
  pivot_levels: PivotLevel[];
  all_supports: number[];
  all_resistances: number[];
}

export const useIndicators = (symbol: string, timeframe: string) => {
  const [data, setData] = useState<SupportResistanceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchIndicators = useCallback(async () => {
    if (!symbol || !timeframe) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/support-resistance?symbol=${symbol}&timeframe=${timeframe}`
      );

      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }

      const result = await response.json();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch indicators');
      console.error('Error fetching indicators:', err);
    } finally {
      setLoading(false);
    }
  }, [symbol, timeframe]);

  useEffect(() => {
    fetchIndicators();
    // Refresh every 30 seconds
    const interval = setInterval(fetchIndicators, 30000);
    return () => clearInterval(interval);
  }, [fetchIndicators]);

  return { data, loading, error, refetch: fetchIndicators };
};
