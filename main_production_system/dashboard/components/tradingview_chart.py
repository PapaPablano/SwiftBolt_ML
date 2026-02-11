"""
TradingView Lightweight Charts Component for Streamlit

Professional-grade trading chart with multi-pane support
"""

import streamlit as st
from streamlit_lightweight_charts import renderLightweightCharts
import json
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def render_professional_chart(
    df_ohlcv,
    symbol="AAPL",
    timeframe="1d",
    show_volume=True,
    indicators=None
):
    """
    Render professional trading chart using TradingView Lightweight Charts.
    
    Args:
        df_ohlcv: DataFrame with [Date, Open, High, Low, Close, Volume]
        symbol: Stock symbol
        timeframe: Chart timeframe
        show_volume: Show volume histogram (True/False)
        indicators: List of indicators (placeholder for future)
    
    Returns:
        True if successful, False otherwise
    """
    
    try:
        logger.info(f"[LIGHTWEIGHT] Rendering {symbol} {timeframe} with TradingView Lightweight Charts")
        
        # Prepare data
        df = df_ohlcv.copy()
        df.columns = df.columns.str.lower()
        
        if 'date' in df.columns:
            df = df.rename(columns={'date': 'time'})
        
        # Format time as YYYY-MM-DD
        df['time'] = pd.to_datetime(df['time']).dt.strftime('%Y-%m-%d')
        
        # Color candles: Red if down, Green if up
        df['color'] = np.where(
            df['close'] < df['open'],
            'rgba(239,83,80,0.9)',    # Red (down)
            'rgba(38,166,154,0.9)'    # Green (up)
        )
        
        # Create candle data
        candles = []
        for _, row in df.iterrows():
            candle = {
                "time": row['time'],
                "open": float(row['open']),
                "high": float(row['high']),
                "low": float(row['low']),
                "close": float(row['close']),
                "color": row['color']
            }
            candles.append(candle)
        
        logger.info(f"[LIGHTWEIGHT] Prepared {len(candles)} candles")
        
        # Chart configuration
        chart_options = {
            "height": 500,
            "layout": {
                "background": {"type": "solid", "color": '#131722'},
                "textColor": '#d1d4dc',
            },
            "grid": {
                "vertLines": {"color": 'rgba(42, 46, 57, 0.3)'},
                "horzLines": {"color": 'rgba(42, 46, 57, 0.6)'}
            },
            "watermark": {
                "visible": True,
                "fontSize": 20,
                "horzAlign": 'center',
                "vertAlign": 'center',
                "color": 'rgba(255, 255, 255, 0.08)',
                "text": f'{symbol} • {timeframe.upper()}'
            }
        }
        
        # Price series (candlestick)
        price_series = [{
            "type": 'Candlestick',
            "data": candles,
            "options": {
                "upColor": 'rgba(38,166,154,0.9)',
                "downColor": 'rgba(239,83,80,0.9)',
                "borderVisible": False,
                "wickUpColor": 'rgba(38,166,154,0.9)',
                "wickDownColor": 'rgba(239,83,80,0.9)',
            }
        }]
        
        # Build chart configuration
        chart_configs = [{"chart": chart_options, "series": price_series}]
        
        # Add volume if requested
        if show_volume:
            volume_data = []
            for _, row in df.iterrows():
                vol = {
                    "time": row['time'],
                    "value": float(row['volume']),
                    "color": row['color']
                }
                volume_data.append(vol)
            
            volume_config = {
                "height": 80,
                "layout": {
                    "background": {"type": "solid", "color": '#0a0e27'},
                    "textColor": '#d1d4dc',
                },
                "grid": {
                    "vertLines": {"color": 'rgba(42, 46, 57, 0)'},
                    "horzLines": {"color": 'rgba(42, 46, 57, 0.3)'}
                },
                "timeScale": {"visible": False},
            }
            
            volume_series = [{
                "type": 'Histogram',
                "data": volume_data,
                "options": {
                    "color": 'rgba(38,166,154,0.5)',
                    "priceFormat": {"type": 'volume'},
                }
            }]
            
            chart_configs.append({"chart": volume_config, "series": volume_series})
        
        # Render chart
        renderLightweightCharts(
            chart_configs,
            f'chart_{symbol}_{timeframe}'
        )
        
        logger.info(f"[LIGHTWEIGHT] ✅ Chart rendered successfully")
        return True
        
    except Exception as e:
        logger.error(f"[LIGHTWEIGHT] ❌ Rendering failed: {e}", exc_info=True)
        st.error(f"📊 Chart Error: {str(e)}")
        return False
