/**
 * WebSocket Hook for Real-time Forecast Updates
 * ==============================================
 * 
 * Custom React hook that manages WebSocket connection to backend.
 * 
 * Features:
 * - Automatic connection/reconnection
 * - Connection status tracking
 * - Message parsing and validation
 * - Auto-cleanup on unmount
 * 
 * Usage:
 *   const { isConnected, lastUpdate } = useWebSocket('AAPL', '1h');
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { WebSocketUpdate } from '../types/chart';

const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

interface UseWebSocketReturn {
  isConnected: boolean;
  lastUpdate: WebSocketUpdate | null;
  error: string | null;
  reconnect: () => void;
}

export function useWebSocket(
  symbol: string,
  horizon: string
): UseWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<WebSocketUpdate | null>(null);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    // Clear any existing connection
    if (wsRef.current) {
      wsRef.current.close();
    }

    const wsUrl = `${WS_BASE_URL}/api/v1/ws/live-forecasts/${symbol}/${horizon}`;
    console.log(`[WebSocket] Connecting to: ${wsUrl}`);

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log(`[WebSocket] Connected: ${symbol}/${horizon}`);
      setIsConnected(true);
      setError(null);
    };

    ws.onmessage = (event) => {
      try {
        const update: WebSocketUpdate = JSON.parse(event.data);
        console.log('[WebSocket] Received update:', update);
        setLastUpdate(update);

        // Log specific update types
        if (update.type === 'connection_confirmed') {
          console.log('[WebSocket] Connection confirmed:', update.message);
        } else if (update.type === 'new_forecast') {
          console.log(
            `[WebSocket] New forecast: $${update.data?.price.toFixed(2)} (${update.data?.direction})`
          );
        }
      } catch (err) {
        console.error('[WebSocket] Error parsing message:', err);
        setError('Invalid message format');
      }
    };

    ws.onerror = (event) => {
      console.error('[WebSocket] Error:', event);
      setError('WebSocket connection error');
    };

    ws.onclose = (event) => {
      console.log(`[WebSocket] Disconnected: ${event.code} ${event.reason}`);
      setIsConnected(false);

      // Attempt reconnection after 5 seconds
      if (!event.wasClean) {
        console.log('[WebSocket] Attempting reconnection in 5s...');
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, 5000);
      }
    };

    wsRef.current = ws;
  }, [symbol, horizon]);

  useEffect(() => {
    connect();

    return () => {
      // Cleanup on unmount
      if (wsRef.current) {
        console.log('[WebSocket] Closing connection (unmount)');
        wsRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [connect]);

  return {
    isConnected,
    lastUpdate,
    error,
    reconnect: connect,
  };
}
