/**
 * TypeScript Type Definitions for Chart Components
 * =================================================
 *
 * Defines interfaces for:
 * - OHLC bar data
 * - Forecast overlays
 * - Chart data bundles
 * - WebSocket messages
 *
 * These types match the backend Pydantic models exactly.
 */

// OHLCBar uses TradingView Lightweight Charts convention (time: Unix seconds)
// Backend returns ts: ISO 8601 string — convert with: Math.floor(new Date(bar.ts).getTime() / 1000)
export interface OHLCBar {
  time: number; // Unix timestamp in seconds (converted from backend ts: string)
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

// Helper to convert backend bar to OHLCBar
export function backendBarToOHLC(bar: {
  ts: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}): OHLCBar {
  return {
    time: Math.floor(new Date(bar.ts).getTime() / 1000),
    open: bar.open,
    high: bar.high,
    low: bar.low,
    close: bar.close,
    volume: bar.volume,
  };
}

export interface ForecastPoint {
  time: number; // converted from ts
  value: number; // backend field name
  price?: number; // alias for backwards compatibility
}

export interface ForecastOverlay {
  time: number; // Unix timestamp
  price: number;
  confidence: number; // 0-1
  direction: 'bullish' | 'bearish' | 'neutral';
}

export interface ChartData {
  symbol: string;
  horizon: string;
  bars: OHLCBar[];
  forecasts: ForecastOverlay[];
  latest_price: number;
  latest_forecast: ForecastOverlay | null;
  timestamp: number;
}

export interface WebSocketUpdate {
  type: 'new_forecast' | 'price_update' | 'connection_confirmed';
  symbol: string;
  horizon: string;
  data?: ForecastOverlay;
  timestamp: number;
  message?: string;
}

export interface ChartOptions {
  symbol: string;
  horizon: string;
  daysBack?: number;
  showVolume?: boolean;
  showConfidenceBands?: boolean;
}
