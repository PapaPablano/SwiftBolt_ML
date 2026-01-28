/**
 * Hook to fetch pivot levels from the API
 * Handles real-time streaming via WebSocket
 *
 * Features:
 * - Multi-period pivot detection
 * - Real-time updates via WebSocket
 * - Caching and memoization
 * - Automatic refresh intervals
 * - Confluence zone detection
 */

import { useState, useEffect, useCallback, useRef } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

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
  const [data, setData] = useState<PivotLevelsResponse | null>(null);
  const [pivotLevels, setPivotLevels] = useState<PivotLevelData[]>([]);
  const [metrics, setMetrics] = useState<PivotMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();

  // Fetch pivot levels from REST API
  const fetchPivotLevels = useCallback(async () => {
    if (!symbol || !timeframe) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/pivot-levels?symbol=${symbol}&timeframe=${timeframe}`
      );

      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }

      const result: PivotLevelsResponse = await response.json();
      setData(result);
      setPivotLevels(
        result.pivot_levels.map((level) => ({
          ...level,
          color: PERIOD_COLORS[level.period] || '#808080',
        }))
      );
      setMetrics(result.metrics);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch pivot levels');
      console.error('Error fetching pivot levels:', err);
    } finally {
      setLoading(false);
    }
  }, [symbol, timeframe]);

  // WebSocket connection for real-time updates
  const connectWebSocket = useCallback(() => {
    if (!symbol) return;

    try {
      const wsUrl = `${WS_BASE_URL}/ws/pivot/${symbol}`;
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log(`[Pivot WS] Connected for ${symbol}`);
        setIsConnected(true);
        setError(null);
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);

          if (message.pivot_levels) {
            setPivotLevels(
              message.pivot_levels.map((level: PivotLevelData) => ({
                ...level,
                color: PERIOD_COLORS[level.period] || '#808080',
              }))
            );
          }

          if (message.metrics) {
            setMetrics(message.metrics);
          }
        } catch (e) {
          console.error('[Pivot WS] Parse error:', e);
        }
      };

      ws.onerror = (event) => {
        console.error('[Pivot WS] Error:', event);
        setError('WebSocket connection error');
        setIsConnected(false);
      };

      ws.onclose = () => {
        console.log(`[Pivot WS] Disconnected for ${symbol}`);
        setIsConnected(false);

        // Attempt to reconnect after 3 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          connectWebSocket();
        }, 3000);
      };

      wsRef.current = ws;
    } catch (err) {
      console.error('[Pivot WS] Connection error:', err);
      setError('Failed to connect WebSocket');
    }
  }, [symbol]);

  // Initial fetch and setup
  useEffect(() => {
    fetchPivotLevels();
    connectWebSocket();

    // Refresh every 30 seconds
    const interval = setInterval(fetchPivotLevels, 30000);

    return () => {
      clearInterval(interval);
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [symbol, timeframe, fetchPivotLevels, connectWebSocket]);

  return {
    pivotLevels,
    metrics,
    loading,
    error,
    isConnected,
    refetch: fetchPivotLevels,
  };
};
