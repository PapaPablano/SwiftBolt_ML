"""
Real-time Forecast Charts API Router
=====================================

Provides REST and WebSocket endpoints for TradingView Lightweight Charts integration.

Features:
- REST endpoint for chart initialization data
- WebSocket endpoint for live forecast updates
- Support for multiple symbol/horizon combinations
- Connection management for broadcast updates

Author: SwiftBolt ML
Date: January 27, 2026
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from pydantic import BaseModel
import pandas as pd

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# DATA MODELS (Pydantic)
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


class WebSocketUpdate(BaseModel):
    """WebSocket message format."""
    type: str  # 'new_forecast', 'price_update', 'connection_confirmed'
    symbol: str
    horizon: str
    data: Optional[ForecastOverlay] = None
    timestamp: int
    message: Optional[str] = None


# ============================================================================
# DATABASE HELPERS
# ============================================================================


def get_db():
    """Get database connection."""
    try:
        from src.data.supabase_db import SupabaseDatabase
        return SupabaseDatabase()
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")


def fetch_ohlc_bars(symbol: str, horizon: str, days_back: int = 30) -> List[OHLCBar]:
    """
    Fetch historical OHLC bars from database.
    
    Args:
        symbol: Stock ticker (e.g., 'AAPL')
        horizon: Timeframe ('15m', '1h', '4h', '1D', etc.)
        days_back: Number of days of historical data
    
    Returns:
        List of OHLC bars in TradingView format
    """
    db = get_db()
    
    # Map horizon to timeframe
    timeframe_map = {
        '15m': 'm15',
        '1h': 'h1',
        '4h': 'h4',
        '8h': 'h8',
        '1D': 'd1',
    }
    
    timeframe = timeframe_map.get(horizon, 'd1')
    # Use UTC time for database queries (database stores UTC timestamps)
    cutoff = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
    
    try:
        # Get symbol_id
        symbol_result = db.client.table('symbols').select('id').eq('ticker', symbol.upper()).limit(1).execute()

        if not symbol_result.data:
            logger.warning(f"Symbol not found: {symbol}")
            return []
        
        symbol_id = symbol_result.data[0]['id']
        
        # Fetch OHLC bars
        result = db.client.table('ohlc_bars_v2').select(
            'ts, open, high, low, close, volume'
        ).eq('symbol_id', symbol_id).eq(
            'timeframe', timeframe
        ).eq('is_forecast', False).gte('ts', cutoff).order('ts', desc=False).limit(
            2000  # Limit to prevent overload
        ).execute()
        
        bars = []
        for row in result.data or []:
            try:
                # Normalize timestamp to noon UTC for consistent chart rendering
                # This ensures daily bars align properly across timezones
                ts = pd.Timestamp(row['ts']).normalize() + pd.Timedelta(hours=12)

                bars.append(OHLCBar(
                    time=int(ts.timestamp()),
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=float(row['volume']) if row.get('volume') else None
                ))
            except Exception as e:
                logger.error(f"Error parsing OHLC bar: {e}")
                continue
        
        logger.info(f"Fetched {len(bars)} OHLC bars for {symbol}/{horizon}")
        return bars
    
    except Exception as e:
        logger.error(f"Error fetching OHLC bars: {e}")
        return []


def fetch_forecast_overlays(symbol: str, horizon: str, days_back: int = 30) -> List[ForecastOverlay]:
    """
    Fetch forecast targets as overlay data.

    Args:
        symbol: Stock ticker
        horizon: Timeframe
        days_back: Number of days of forecast history

    Returns:
        List of forecast overlays for chart rendering
    """
    db = get_db()
    # Use UTC time for database queries (database stores UTC timestamps)
    cutoff = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
    
    try:
        # Determine table based on horizon type
        if horizon in ['15m', '1h', '4h', '8h']:
            # Intraday table
            result = db.client.table('ml_forecasts_intraday').select(
                'target_price, confidence, overall_label, created_at'
            ).eq('symbol', symbol.upper()).eq('horizon', horizon).gte(
                'created_at', cutoff
            ).order('created_at', desc=False).limit(500).execute()
            
            overlays = []
            for row in result.data or []:
                try:
                    # Use forecast creation time as-is for intraday
                    ts = int(pd.Timestamp(row['created_at']).timestamp())
                    overlays.append(ForecastOverlay(
                        time=ts,
                        price=float(row['target_price']),
                        confidence=float(row['confidence']),
                        direction=row['overall_label'].lower()
                    ))
                except Exception as e:
                    logger.error(f"Error parsing intraday forecast: {e}")
                    continue
        
        else:
            # Daily table (requires JOIN)
            symbol_result = db.client.table('symbols').select('id').eq('ticker', symbol.upper()).limit(1).execute()

            if not symbol_result.data:
                return []
            
            symbol_id = symbol_result.data[0]['id']
            
            result = db.client.table('ml_forecasts').select(
                'points, confidence, overall_label, created_at'
            ).eq('symbol_id', symbol_id).eq('horizon', horizon).gte(
                'created_at', cutoff
            ).order('created_at', desc=False).limit(500).execute()
            
            overlays = []
            for row in result.data or []:
                try:
                    # Extract target price from points array
                    points = row.get('points', [])
                    if not points or not isinstance(points, list):
                        continue

                    # Last point is the target
                    target = float(points[-1]['value']) if points else None

                    if target:
                        # Normalize forecast timestamp to noon UTC for chart alignment
                        ts = pd.Timestamp(row['created_at']).normalize() + pd.Timedelta(hours=12)
                        overlays.append(ForecastOverlay(
                            time=int(ts.timestamp()),
                            price=target,
                            confidence=float(row['confidence']),
                            direction=row['overall_label'].lower()
                        ))
                except Exception as e:
                    logger.error(f"Error parsing daily forecast: {e}")
                    continue
        
        logger.info(f"Fetched {len(overlays)} forecast overlays for {symbol}/{horizon}")
        return overlays
    
    except Exception as e:
        logger.error(f"Error fetching forecast overlays: {e}")
        return []


# ============================================================================
# REST ENDPOINTS
# ============================================================================


@router.get('/chart-data/{symbol}/{horizon}', response_model=ChartData)
async def get_chart_data(
    symbol: str,
    horizon: str,
    days_back: int = Query(30, description='Days of historical data', ge=1, le=365)
):
    """
    Get complete chart data bundle for TradingView Lightweight Charts.
    """
    try:
        logger.info(f"Chart data requested: {symbol}/{horizon} (days_back={days_back})")
        
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
        logger.error(f'Error in chart_data endpoint: {e}', exc_info=True)
        raise HTTPException(status_code=500, detail=f'Internal error: {str(e)}')


# ============================================================================
# WEBSOCKET FOR REAL-TIME UPDATES
# ============================================================================


class ConnectionManager:
    """Manage WebSocket connections for real-time forecast updates."""
    
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, key: str):
        """Accept new WebSocket connection."""
        await websocket.accept()
        if key not in self.active_connections:
            self.active_connections[key] = []
        self.active_connections[key].append(websocket)
        logger.info(f"WebSocket connected: {key} (total: {len(self.active_connections[key])})")
    
    def disconnect(self, websocket: WebSocket, key: str):
        """Remove WebSocket connection."""
        if key in self.active_connections:
            try:
                self.active_connections[key].remove(websocket)
                logger.info(f"WebSocket disconnected: {key} (remaining: {len(self.active_connections[key])})")
            except ValueError:
                pass
    
    async def broadcast(self, key: str, message: dict):
        """Broadcast message to all connections for a symbol/horizon."""
        if key in self.active_connections:
            disconnected = []
            for connection in self.active_connections[key]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f'Error broadcasting to {key}: {e}')
                    disconnected.append(connection)
            
            # Clean up disconnected websockets
            for conn in disconnected:
                self.disconnect(conn, key)
    
    def get_connection_count(self, key: str) -> int:
        """Get number of active connections for a key."""
        return len(self.active_connections.get(key, []))


manager = ConnectionManager()


@router.websocket('/ws/live-forecasts/{symbol}/{horizon}')
async def websocket_live_forecasts(websocket: WebSocket, symbol: str, horizon: str):
    """WebSocket endpoint for real-time forecast updates."""
    key = f'{symbol.upper()}_{horizon}'
    await manager.connect(websocket, key)
    
    # Send confirmation message
    try:
        await websocket.send_json({
            'type': 'connection_confirmed',
            'symbol': symbol.upper(),
            'horizon': horizon,
            'timestamp': int(datetime.now().timestamp()),
            'message': f'Connected to live forecasts for {symbol.upper()}/{horizon}'
        })
    except Exception as e:
        logger.error(f"Error sending confirmation: {e}")
    
    try:
        # Keep connection alive and check for updates
        last_forecast_time = 0
        
        while True:
            # Poll for new forecasts every 60 seconds
            await asyncio.sleep(60)
            
            try:
                # Fetch latest forecast
                forecasts = fetch_forecast_overlays(symbol.upper(), horizon, days_back=1)
                
                if forecasts:
                    latest = forecasts[-1]
                    
                    # Check if this is a new forecast (not seen before)
                    if latest.time > last_forecast_time:
                        age_seconds = int(datetime.now().timestamp()) - latest.time
                        
                        # Only broadcast if less than 5 minutes old
                        if age_seconds < 300:
                            update = WebSocketUpdate(
                                type='new_forecast',
                                symbol=symbol.upper(),
                                horizon=horizon,
                                data=latest,
                                timestamp=int(datetime.now().timestamp())
                            )
                            
                            await manager.broadcast(key, update.dict())
                            last_forecast_time = latest.time
                            
                            logger.info(f"Broadcast new forecast: {symbol}/{horizon} @ ${latest.price:.2f}")
            
            except Exception as e:
                logger.error(f"Error in WebSocket polling loop: {e}")
                continue
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, key)
        logger.info(f'WebSocket disconnected normally: {key}')
    except Exception as e:
        logger.error(f'WebSocket error for {key}: {e}', exc_info=True)
        manager.disconnect(websocket, key)


# ============================================================================
# TRIGGER ENDPOINT (For Manual Testing)
# ============================================================================


@router.post('/trigger-forecast-update/{symbol}/{horizon}')
async def trigger_forecast_update(symbol: str, horizon: str):
    """Manually trigger a forecast update broadcast."""
    key = f'{symbol.upper()}_{horizon}'
    
    try:
        # Fetch latest forecast
        forecasts = fetch_forecast_overlays(symbol.upper(), horizon, days_back=7)
        
        if not forecasts:
            raise HTTPException(status_code=404, detail='No recent forecasts found')
        
        latest = forecasts[-1]
        
        # Create update message
        update = WebSocketUpdate(
            type='new_forecast',
            symbol=symbol.upper(),
            horizon=horizon,
            data=latest,
            timestamp=int(datetime.now().timestamp()),
            message='Manual trigger'
        )
        
        # Broadcast to all connected clients
        await manager.broadcast(key, update.dict())
        
        connection_count = manager.get_connection_count(key)
        
        logger.info(f"Manual trigger: {symbol}/{horizon} broadcast to {connection_count} clients")
        
        return {
            'status': 'broadcast_sent',
            'symbol': symbol.upper(),
            'horizon': horizon,
            'connections': connection_count,
            'forecast': latest.dict()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in trigger endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Trigger failed: {str(e)}")


# ============================================================================
# HEALTH CHECK
# ============================================================================


@router.get('/health/realtime-charts')
async def health_check():
    """Health check for real-time chart endpoints."""
    total_connections = sum(len(conns) for conns in manager.active_connections.values())
    
    return {
        'status': 'healthy',
        'service': 'real-time forecast charts',
        'endpoints': {
            'chart_data': 'GET /api/v1/chart-data/{symbol}/{horizon}',
            'websocket': 'WS /api/v1/ws/live-forecasts/{symbol}/{horizon}',
            'trigger': 'POST /api/v1/trigger-forecast-update/{symbol}/{horizon}',
        },
        'active_connections': total_connections,
        'connection_keys': list(manager.active_connections.keys()),
        'timestamp': datetime.now().isoformat()
    }
