# Path C: Professional Trading Platform Implementation
## TradingView Lightweight Charts + Real-time WebSocket Updates

**Timeline:** 4-6 hours  
**Result:** Professional-grade multi-timeframe forecast visualization

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Frontend (React/TypeScript)                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  TradingView Lightweight Charts (Intraday Real-time)     │   │
│  │  - 15m, 1h, 4h horizons                                  │   │
│  │  - OHLC candles + forecast target overlay               │   │
│  │  - Confidence bands as area series                       │   │
│  │  - WebSocket live updates                                │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Plotly Charts (Daily Multi-timeframe)                   │   │
│  │  - 1D, 5D, 10D, 20D horizons                            │   │
│  │  - Target progression with confidence                    │   │
│  │  - Signal heatmap                                        │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ↕ HTTP + WebSocket
┌─────────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  REST Endpoints                                          │   │
│  │  - /forecast-progression/{symbol}/{horizon}             │   │
│  │  - /ohlc-bars/{symbol}/{horizon}                        │   │
│  │  - /signal-matrix                                       │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  WebSocket Endpoint                                      │   │
│  │  - /ws/live-forecasts/{symbol}/{horizon}                │   │
│  │  - Pushes updates when new forecasts arrive             │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────────┐
│                 Database (Supabase/PostgreSQL)                  │
│  - ml_forecasts_intraday (15m, 1h, 4h)                         │
│  - ml_forecasts (1D, 5D, 10D, 20D)                             │
│  - ohlc_bars_v2 (historical price data)                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Backend Setup (90 minutes)

### 1.1 Create Enhanced Forecast Endpoints

**File:** `ml/api/routers/forecast_charts.py` (append to existing)

```python
"""Enhanced endpoints for TradingView Lightweight Charts integration."""

import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from pydantic import BaseModel
import pandas as pd

router = APIRouter()


# ============================================================================
# DATA MODELS
# ============================================================================


class OHLCBar(BaseModel):
    """OHLC bar for TradingView Lightweight Charts."""
    time: int  # Unix timestamp
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None


class ForecastOverlay(BaseModel):
    """Forecast target overlay for chart."""
    time: int
    price: float
    confidence: float
    direction: str  # 'bullish', 'bearish', 'neutral'


class ChartData(BaseModel):
    """Complete chart data bundle."""
    symbol: str
    horizon: str
    bars: List[OHLCBar]
    forecasts: List[ForecastOverlay]
    latest_price: float
    latest_forecast: Optional[ForecastOverlay] = None
    timestamp: int


# ============================================================================
# DATABASE HELPERS
# ============================================================================


def fetch_ohlc_bars(symbol: str, horizon: str, days_back: int = 30) -> List[OHLCBar]:
    """
    Fetch historical OHLC bars from database.
    
    Returns bars in format required by TradingView Lightweight Charts.
    """
    from src.data.supabase_db import SupabaseDatabase
    
    db = SupabaseDatabase()
    
    # Map horizon to timeframe
    timeframe_map = {
        '15m': 'm15',
        '1h': 'h1',
        '4h': 'h4',
        '1D': 'd1',
    }
    
    timeframe = timeframe_map.get(horizon, 'd1')
    cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()
    
    try:
        # Fetch bars
        result = db.client.table('ohlc_bars_v2').select(
            'ts, open, high, low, close, volume'
        ).eq('symbol_id', f'(SELECT id FROM symbols WHERE ticker = \'{symbol}\')').eq(
            'timeframe', timeframe
        ).eq('is_forecast', False).gte('ts', cutoff).order('ts', desc=False).limit(
            1000
        ).execute()
        
        bars = []
        for row in result.data or []:
            bars.append(OHLCBar(
                time=int(pd.Timestamp(row['ts']).timestamp()),
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=float(row['volume']) if row.get('volume') else None
            ))
        
        return bars
    
    except Exception as e:
        logger.error(f"Error fetching OHLC bars: {e}")
        return []


def fetch_forecast_overlays(symbol: str, horizon: str, days_back: int = 30) -> List[ForecastOverlay]:
    """
    Fetch forecast targets as overlay data.
    
    Returns targets in chronological order for charting.
    """
    from src.data.supabase_db import SupabaseDatabase
    
    db = SupabaseDatabase()
    cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()
    
    try:
        # Determine table
        if horizon in ['15m', '1h', '4h', '8h']:
            result = db.client.table('ml_forecasts_intraday').select(
                'symbol, target_price, confidence, overall_label, created_at'
            ).eq('symbol', symbol).eq('horizon', horizon).gte(
                'created_at', cutoff
            ).order('created_at', desc=False).execute()
        else:
            result = db.client.table('ml_forecasts').select(
                'symbols(ticker), points, confidence, overall_label, created_at'
            ).eq('symbols.ticker', symbol).eq('horizon', horizon).gte(
                'created_at', cutoff
            ).order('created_at', desc=False).execute()
        
        overlays = []
        for row in result.data or []:
            # Extract target price
            if horizon in ['15m', '1h', '4h', '8h']:
                target = float(row['target_price'])
            else:
                points = row.get('points', [])
                target = float(points[-1]['value']) if points else None
            
            if target:
                overlays.append(ForecastOverlay(
                    time=int(pd.Timestamp(row['created_at']).timestamp()),
                    price=target,
                    confidence=float(row['confidence']),
                    direction=row['overall_label'].lower()
                ))
        
        return overlays
    
    except Exception as e:
        logger.error(f"Error fetching forecast overlays: {e}")
        return []


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.get('/chart-data/{symbol}/{horizon}', response_model=ChartData)
async def get_chart_data(
    symbol: str = Query(..., description='Stock symbol (e.g., AAPL)'),
    horizon: str = Query(..., description='Timeframe (15m, 1h, 4h, 1D, 5D, 10D, 20D)'),
    days_back: int = Query(30, description='Days of historical data')
):
    """
    Get complete chart data bundle for TradingView Lightweight Charts.
    
    Includes:
    - Historical OHLC bars
    - Forecast target overlays
    - Latest price & forecast
    
    Perfect for initializing real-time chart on page load.
    
    Example:
        GET /api/v1/chart-data/AAPL/1h?days_back=7
        
    Response:
        {
            "symbol": "AAPL",
            "horizon": "1h",
            "bars": [{time: 1674000000, open: 145.5, ...}, ...],
            "forecasts": [{time: 1674001000, price: 146.2, confidence: 0.85}, ...],
            "latest_price": 145.75,
            "latest_forecast": {...},
            "timestamp": 1674005000
        }
    """
    try:
        # Fetch OHLC bars
        bars = fetch_ohlc_bars(symbol.upper(), horizon, days_back)
        
        if not bars:
            raise HTTPException(
                status_code=404,
                detail=f'No OHLC data found for {symbol}/{horizon}'
            )
        
        # Fetch forecast overlays
        forecasts = fetch_forecast_overlays(symbol.upper(), horizon, days_back)
        
        # Latest price
        latest_price = bars[-1].close if bars else 0.0
        
        # Latest forecast
        latest_forecast = forecasts[-1] if forecasts else None
        
        return ChartData(
            symbol=symbol.upper(),
            horizon=horizon,
            bars=bars,
            forecasts=forecasts,
            latest_price=latest_price,
            latest_forecast=latest_forecast,
            timestamp=int(datetime.now().timestamp())
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error in chart_data endpoint: {e}')
        raise HTTPException(status_code=500, detail=f'Internal error: {str(e)}')


# ============================================================================
# WEBSOCKET FOR REAL-TIME UPDATES
# ============================================================================


class ConnectionManager:
    """Manage WebSocket connections for real-time forecast updates."""
    
    def __init__(self):
        self.active_connections: dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, key: str):
        """Accept new WebSocket connection."""
        await websocket.accept()
        if key not in self.active_connections:
            self.active_connections[key] = []
        self.active_connections[key].append(websocket)
    
    def disconnect(self, websocket: WebSocket, key: str):
        """Remove WebSocket connection."""
        if key in self.active_connections:
            self.active_connections[key].remove(websocket)
    
    async def broadcast(self, key: str, message: dict):
        """Broadcast message to all connections for a symbol/horizon."""
        if key in self.active_connections:
            for connection in self.active_connections[key]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f'Error broadcasting to {key}: {e}')


manager = ConnectionManager()


@router.websocket('/ws/live-forecasts/{symbol}/{horizon}')
async def websocket_live_forecasts(websocket: WebSocket, symbol: str, horizon: str):
    """
    WebSocket endpoint for real-time forecast updates.
    
    Streams new forecasts as they are generated.
    Client connects once and receives push notifications.
    
    Usage (JavaScript):
        const ws = new WebSocket('ws://localhost:8000/api/v1/ws/live-forecasts/AAPL/1h');
        ws.onmessage = (event) => {
            const update = JSON.parse(event.data);
            // update.type: 'new_forecast' | 'price_update'
            // update. { time, price, confidence, direction }
        };
    """
    key = f'{symbol.upper()}_{horizon}'
    await manager.connect(websocket, key)
    
    try:
        while True:
            # Poll for new forecasts every 60 seconds
            # (In production, use database triggers or message queue)
            await asyncio.sleep(60)
            
            # Fetch latest forecast
            forecasts = fetch_forecast_overlays(symbol.upper(), horizon, days_back=1)
            
            if forecasts:
                latest = forecasts[-1]
                
                # Check if this is a new forecast (less than 2 min old)
                age_seconds = int(datetime.now().timestamp()) - latest.time
                
                if age_seconds < 120:  # Less than 2 minutes old = new
                    await manager.broadcast(key, {
                        'type': 'new_forecast',
                        'symbol': symbol.upper(),
                        'horizon': horizon,
                        'data': {
                            'time': latest.time,
                            'price': latest.price,
                            'confidence': latest.confidence,
                            'direction': latest.direction
                        },
                        'timestamp': int(datetime.now().timestamp())
                    })
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, key)
        logger.info(f'WebSocket disconnected: {key}')
    except Exception as e:
        logger.error(f'WebSocket error for {key}: {e}')
        manager.disconnect(websocket, key)


# ============================================================================
# TRIGGER ENDPOINT (For Manual Testing)
# ============================================================================


@router.post('/trigger-forecast-update/{symbol}/{horizon}')
async def trigger_forecast_update(symbol: str, horizon: str):
    """
    Manually trigger a forecast update broadcast.
    
    Useful for testing WebSocket functionality without waiting for real forecasts.
    """
    key = f'{symbol.upper()}_{horizon}'
    
    # Fetch latest forecast
    forecasts = fetch_forecast_overlays(symbol.upper(), horizon, days_back=1)
    
    if not forecasts:
        raise HTTPException(status_code=404, detail='No recent forecasts found')
    
    latest = forecasts[-1]
    
    await manager.broadcast(key, {
        'type': 'new_forecast',
        'symbol': symbol.upper(),
        'horizon': horizon,
        'data': {
            'time': latest.time,
            'price': latest.price,
            'confidence': latest.confidence,
            'direction': latest.direction
        },
        'timestamp': int(datetime.now().timestamp())
    })
    
    return {'status': 'broadcast_sent', 'connections': len(manager.active_connections.get(key, []))}
```

### 1.2 Update FastAPI Main App

**File:** `ml/api/main.py`

```python
# Add to imports
from api.routers import forecast_charts

# Add to router includes
app.include_router(forecast_charts.router, prefix="/api/v1", tags=["Forecast Charts"])
```

### 1.3 Test Backend Endpoints

```bash
# Terminal 1: Start FastAPI
cd /Users/ericpeterson/SwiftBolt_ML/ml
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Test endpoints
curl http://localhost:8000/api/v1/chart-data/AAPL/1h?days_back=7

# Expected: JSON with bars + forecasts
```

**Time checkpoint:** 90 minutes (Backend complete ✅)

---

## Phase 2: Frontend Setup (120 minutes)

### 2.1 Create React App Structure

```bash
cd /Users/ericpeterson/SwiftBolt_ML
mkdir -p frontend/src/components
mkdir -p frontend/src/hooks
mkdir -p frontend/src/types
mkdir -p frontend/src/utils

# Initialize npm project
cd frontend
npm init -y
```

### 2.2 Install Dependencies

```bash
npm install --save \
  lightweight-charts \
  react \
  react-dom \
  typescript \
  @types/react \
  @types/react-dom \
  axios

npm install --save-dev \
  @vitejs/plugin-react \
  vite \
  tailwindcss \
  postcss \
  autoprefixer
```

### 2.3 Create TypeScript Types

**File:** `frontend/src/types/chart.ts`

```typescript
export interface OHLCBar {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export interface ForecastOverlay {
  time: number;
  price: number;
  confidence: number;
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
  type: 'new_forecast' | 'price_update';
  symbol: string;
  horizon: string;
   ForecastOverlay;
  timestamp: number;
}
```

### 2.4 Create WebSocket Hook

**File:** `frontend/src/hooks/useWebSocket.ts`

```typescript
import { useEffect, useRef, useState } from 'react';
import { WebSocketUpdate } from '../types/chart';

export function useWebSocket(symbol: string, horizon: string) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<WebSocketUpdate | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const wsUrl = `ws://localhost:8000/api/v1/ws/live-forecasts/${symbol}/${horizon}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log(`WebSocket connected: ${symbol}/${horizon}`);
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      const update: WebSocketUpdate = JSON.parse(event.data);
      console.log('Received update:', update);
      setLastUpdate(update);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
    };

    wsRef.current = ws;

    return () => {
      ws.close();
    };
  }, [symbol, horizon]);

  return { isConnected, lastUpdate };
}
```

### 2.5 Create Main Chart Component

**File:** `frontend/src/components/TradingViewChart.tsx`

```typescript
import React, { useEffect, useRef, useState } from 'react';
import { createChart, IChartApi, ISeriesApi } from 'lightweight-charts';
import axios from 'axios';
import { ChartData, OHLCBar, ForecastOverlay } from '../types/chart';
import { useWebSocket } from '../hooks/useWebSocket';

interface TradingViewChartProps {
  symbol: string;
  horizon: string;
  daysBack?: number;
}

export const TradingViewChart: React.FC<TradingViewChartProps> = ({
  symbol,
  horizon,
  daysBack = 7,
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const forecastSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const confidenceBandRef = useRef<ISeriesApi<'Area'> | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // WebSocket for real-time updates
  const { isConnected, lastUpdate } = useWebSocket(symbol, horizon);

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: '#1a1a1a' },
        textColor: '#e0e0e0',
      },
      grid: {
        vertLines: { color: '#2a2a2a' },
        horzLines: { color: '#2a2a2a' },
      },
      width: chartContainerRef.current.clientWidth,
      height: 500,
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: '#3a3a3a',
      },
      rightPriceScale: {
        borderColor: '#3a3a3a',
      },
    });

    chartRef.current = chart;

    // Add candlestick series
    const candleSeries = chart.addCandlestickSeries({
      upColor: '#00c853',
      downColor: '#ff5252',
      borderUpColor: '#00c853',
      borderDownColor: '#ff5252',
      wickUpColor: '#00c853',
      wickDownColor: '#ff5252',
    });
    candleSeriesRef.current = candleSeries;

    // Add forecast target line
    const forecastSeries = chart.addLineSeries({
      color: '#0088cc',
      lineWidth: 3,
      title: 'Target Price',
      priceLineVisible: true,
      lastValueVisible: true,
    });
    forecastSeriesRef.current = forecastSeries;

    // Add confidence band (area series)
    const confidenceBand = chart.addAreaSeries({
      topColor: 'rgba(0, 136, 204, 0.3)',
      bottomColor: 'rgba(0, 136, 204, 0.05)',
      lineColor: 'rgba(0, 136, 204, 0.5)',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    confidenceBandRef.current = confidenceBand;

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, []);

  // Fetch initial data
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await axios.get<ChartData>(
          `http://localhost:8000/api/v1/chart-data/${symbol}/${horizon}`,
          { params: { days_back: daysBack } }
        );

        const data = response.data;

        // Update candle series
        if (candleSeriesRef.current) {
          candleSeriesRef.current.setData(data.bars);
        }

        // Update forecast series
        if (forecastSeriesRef.current && data.forecasts.length > 0) {
          const forecastData = data.forecasts.map((f) => ({
            time: f.time,
            value: f.price,
          }));
          forecastSeriesRef.current.setData(forecastData);
        }

        // Update confidence band
        if (confidenceBandRef.current && data.forecasts.length > 0) {
          const bandData = data.forecasts.map((f) => ({
            time: f.time,
            value: f.price * (1 + f.confidence * 0.02), // Upper bound
          }));
          confidenceBandRef.current.setData(bandData);
        }

        // Fit content
        if (chartRef.current) {
          chartRef.current.timeScale().fitContent();
        }

        setLoading(false);
      } catch (err) {
        console.error('Error fetching chart ', err);
        setError('Failed to load chart data');
        setLoading(false);
      }
    };

    fetchData();
  }, [symbol, horizon, daysBack]);

  // Handle real-time updates
  useEffect(() => {
    if (lastUpdate && lastUpdate.type === 'new_forecast') {
      const { data } = lastUpdate;

      // Add new forecast point
      if (forecastSeriesRef.current) {
        forecastSeriesRef.current.update({
          time: data.time,
          value: data.price,
        });
      }

      // Update confidence band
      if (confidenceBandRef.current) {
        confidenceBandRef.current.update({
          time: data.time,
          value: data.price * (1 + data.confidence * 0.02),
        });
      }

      console.log('Chart updated with new forecast:', data);
    }
  }, [lastUpdate]);

  return (
    <div className="relative w-full">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">
            {symbol} <span className="text-gray-400">| {horizon}</span>
          </h2>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div
              className={`h-2 w-2 rounded-full ${
                isConnected ? 'bg-green-500' : 'bg-red-500'
              }`}
            />
            <span className="text-sm text-gray-400">
              {isConnected ? 'Live' : 'Disconnected'}
            </span>
          </div>
        </div>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="flex h-[500px] items-center justify-center bg-gray-900">
          <div className="text-gray-400">Loading chart...</div>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="flex h-[500px] items-center justify-center bg-gray-900">
          <div className="text-red-500">{error}</div>
        </div>
      )}

      {/* Chart container */}
      <div
        ref={chartContainerRef}
        className={loading || error ? 'hidden' : ''}
      />

      {/* Legend */}
      <div className="mt-2 flex gap-4 text-sm text-gray-400">
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 bg-green-500" />
          <span>Price Up</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 bg-red-500" />
          <span>Price Down</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 bg-blue-500" />
          <span>Forecast Target</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 bg-blue-300 opacity-30" />
          <span>Confidence Band</span>
        </div>
      </div>
    </div>
  );
};
```

### 2.6 Create Main App Component

**File:** `frontend/src/App.tsx`

```typescript
import React, { useState } from 'react';
import { TradingViewChart } from './components/TradingViewChart';

function App() {
  const [selectedSymbol, setSelectedSymbol] = useState('AAPL');
  const [selectedHorizon, setSelectedHorizon] = useState('1h');

  const symbols = ['AAPL', 'NVDA', 'TSLA', 'CRWD', 'MU', 'PLTR', 'AMD', 'GOOG'];
  const horizons = [
    { value: '15m', label: '15 Minutes' },
    { value: '1h', label: '1 Hour' },
    { value: '4h', label: '4 Hours' },
    { value: '1D', label: '1 Day' },
  ];

  return (
    <div className="min-h-screen bg-gray-950 p-8">
      <div className="mx-auto max-w-7xl">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white">
            SwiftBolt <span className="text-blue-500">Forecast Charts</span>
          </h1>
          <p className="mt-2 text-gray-400">
            Real-time multi-timeframe forecast visualization
          </p>
        </div>

        {/* Controls */}
        <div className="mb-6 flex gap-4">
          {/* Symbol selector */}
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-300">
              Symbol
            </label>
            <select
              value={selectedSymbol}
              onChange={(e) => setSelectedSymbol(e.target.value)}
              className="rounded-lg bg-gray-800 px-4 py-2 text-white"
            >
              {symbols.map((symbol) => (
                <option key={symbol} value={symbol}>
                  {symbol}
                </option>
              ))}
            </select>
          </div>

          {/* Horizon selector */}
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-300">
              Timeframe
            </label>
            <select
              value={selectedHorizon}
              onChange={(e) => setSelectedHorizon(e.target.value)}
              className="rounded-lg bg-gray-800 px-4 py-2 text-white"
            >
              {horizons.map((h) => (
                <option key={h.value} value={h.value}>
                  {h.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Chart */}
        <div className="rounded-lg bg-gray-900 p-6">
          <TradingViewChart
            symbol={selectedSymbol}
            horizon={selectedHorizon}
            daysBack={7}
          />
        </div>
      </div>
    </div>
  );
}

export default App;
```

### 2.7 Create Vite Config

**File:** `frontend/vite.config.ts`

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
```

### 2.8 Create Tailwind Config

```bash
npx tailwindcss init -p
```

**File:** `frontend/tailwind.config.js`

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {},
  },
  plugins: [],
};
```

### 2.9 Create Entry Point

**File:** `frontend/index.html`

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>SwiftBolt Forecast Charts</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

**File:** `frontend/src/main.tsx`

```typescript
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

**File:** `frontend/src/index.css`

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto',
    'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans',
    'Helvetica Neue', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
```

### 2.10 Update Package.json Scripts

**File:** `frontend/package.json`

```json
{
  "name": "swiftbolt-forecast-charts",
  "version": "1.0.0",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  }
}
```

**Time checkpoint:** 210 minutes (Frontend complete ✅)

---

## Phase 3: Testing & Deployment (60 minutes)

### 3.1 Start Backend

```bash
# Terminal 1
cd /Users/ericpeterson/SwiftBolt_ML/ml
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### 3.2 Start Frontend

```bash
# Terminal 2
cd /Users/ericpeterson/SwiftBolt_ML/frontend
npm run dev

# Open browser: http://localhost:3000
```

### 3.3 Test Real-time Updates

```bash
# Terminal 3: Trigger manual update
curl -X POST http://localhost:8000/api/v1/trigger-forecast-update/AAPL/1h

# Expected: Chart updates in browser within 1-2 seconds
```

### 3.4 Verification Checklist

- [ ] Chart loads OHLC candles correctly
- [ ] Forecast target line overlays on chart
- [ ] Confidence band shows as transparent area
- [ ] WebSocket connection indicator shows "Live"
- [ ] Manual trigger updates chart in real-time
- [ ] Symbol/horizon selectors work
- [ ] Chart is responsive (resize browser window)
- [ ] Colors match theme (green up, red down, blue forecast)

### 3.5 Production Build

```bash
cd /Users/ericpeterson/SwiftBolt_ML/frontend
npm run build

# Outputs to: frontend/dist/
# Serve with: nginx, Vercel, or Cloudflare Pages
```

**Time checkpoint:** 270 minutes (4.5 hours, Full system working ✅)

---

## Phase 4: Enhancements (Optional, +90 minutes)

### 4.1 Add Multiple Charts (Multi-Panel View)

**File:** `frontend/src/components/MultiChartView.tsx`

```typescript
import React from 'react';
import { TradingViewChart } from './TradingViewChart';

interface MultiChartViewProps {
  symbol: string;
}

export const MultiChartView: React.FC<MultiChartViewProps> = ({ symbol }) => {
  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="rounded-lg bg-gray-900 p-4">
        <TradingViewChart symbol={symbol} horizon="15m" daysBack={1} />
      </div>
      <div className="rounded-lg bg-gray-900 p-4">
        <TradingViewChart symbol={symbol} horizon="1h" daysBack={3} />
      </div>
      <div className="rounded-lg bg-gray-900 p-4">
        <TradingViewChart symbol={symbol} horizon="4h" daysBack={7} />
      </div>
      <div className="rounded-lg bg-gray-900 p-4">
        <TradingViewChart symbol={symbol} horizon="1D" daysBack={30} />
      </div>
    </div>
  );
};
```

### 4.2 Add Volume Profile

```typescript
// In TradingViewChart.tsx, add volume series:
const volumeSeries = chart.addHistogramSeries({
  color: '#26a69a',
  priceFormat: {
    type: 'volume',
  },
  priceScaleId: '',
  scaleMargins: {
    top: 0.8,
    bottom: 0,
  },
});

// Map volume data
const volumeData = data.bars.map((bar) => ({
  time: bar.time,
  value: bar.volume || 0,
  color: bar.close >= bar.open ? '#00c85340' : '#ff525240',
}));

volumeSeries.setData(volumeData);
```

### 4.3 Add Drawing Tools

```bash
npm install @trading-view/charting-library
# Follow TradingView Charting Library advanced setup
```

### 4.4 Add Alerts/Notifications

```typescript
// When new forecast arrives with high confidence
if (lastUpdate && lastUpdate.data.confidence > 0.85) {
  new Notification('High-Confidence Forecast', {
    body: `${symbol} ${horizon}: ${lastUpdate.data.direction} target at $${lastUpdate.data.price}`,
    icon: '/logo.png',
  });
}
```

---

## Deployment Options

### Option 1: Vercel (Frontend) + Railway (Backend)

```bash
# Frontend
cd frontend
vercel deploy --prod

# Backend
# Push to GitHub, connect Railway to repo
```

### Option 2: Docker Compose (All-in-One)

**File:** `docker-compose.yml`

```yaml
version: '3.8'

services:
  backend:
    build: ./ml
    ports:
      - '8000:8000'
    environment:
      - DATABASE_URL=${DATABASE_URL}
    restart: always

  frontend:
    build: ./frontend
    ports:
      - '3000:80'
    depends_on:
      - backend
    restart: always
```

### Option 3: AWS (Production-Ready)

- Backend: AWS ECS Fargate
- Frontend: AWS CloudFront + S3
- WebSocket: AWS API Gateway WebSocket API
- Database: Already on Supabase ✅

---

## Performance Optimization

### Backend:
- [ ] Add Redis caching for chart data (5 min expiry)
- [ ] Use connection pooling for database (asyncpg)
- [ ] Implement rate limiting (10 req/sec per IP)

### Frontend:
- [ ] Lazy load charts (only render visible ones)
- [ ] Debounce WebSocket updates (max 1 update/sec)
- [ ] Use React.memo() for TradingViewChart component

---

## Monitoring

### Add Logging

```python
# Backend: ml/api/routers/forecast_charts.py
import logging

logger = logging.getLogger(__name__)

@router.get('/chart-data/{symbol}/{horizon}')
async def get_chart_data(...):
    logger.info(f'Chart data requested: {symbol}/{horizon}')
    # ... rest of endpoint
```

### Add Analytics

```typescript
// Frontend: src/components/TradingViewChart.tsx
useEffect(() => {
  // Track chart views
  gtag('event', 'chart_view', {
    symbol: symbol,
    horizon: horizon,
  });
}, [symbol, horizon]);
```

---

## Troubleshooting

### WebSocket not connecting:
```bash
# Check CORS settings in FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Chart not rendering:
```javascript
// Check browser console for errors
// Verify API endpoint returns 
curl http://localhost:8000/api/v1/chart-data/AAPL/1h
```

### No real-time updates:
```bash
# Test WebSocket manually
wscat -c ws://localhost:8000/api/v1/ws/live-forecasts/AAPL/1h

# Trigger update
curl -X POST http://localhost:8000/api/v1/trigger-forecast-update/AAPL/1h
```

---

## Success Criteria

✅ **Professional Trading Platform Complete:**
- Real-time OHLC charts with TradingView Lightweight Charts
- Forecast target overlay with confidence bands
- Live WebSocket updates (forecasts appear instantly)
- Multi-symbol, multi-timeframe support
- Production-ready deployment
- Responsive design

**Total Time:** 4.5-6 hours
**Result:** Professional-grade forecast visualization platform 🚀

---

Next: See `PATH_C_COMPONENT_FILES/` for complete, copy-paste-ready code files.
