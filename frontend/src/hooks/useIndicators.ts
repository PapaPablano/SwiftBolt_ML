/**
 * Hook to access technical indicator data (Polynomial S/R, Pivot Levels, etc.)
 *
 * Data fetching is handled by useSupportResistance to avoid duplicate polls.
 * This hook is now a thin re-export of the srData slice from that shared hook.
 */

import { useSupportResistance } from './useSupportResistance';

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
  high_status?: 'support' | 'resistance' | 'active' | 'inactive';
  low_status?: 'support' | 'resistance' | 'active' | 'inactive';
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
  const { srData, loading, error, refetch } = useSupportResistance(symbol, timeframe);
  return { data: srData, loading, error, refetch };
};
