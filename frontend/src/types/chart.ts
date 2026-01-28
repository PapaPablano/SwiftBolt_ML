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

export interface OHLCBar {
  time: number; // Unix timestamp
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
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
