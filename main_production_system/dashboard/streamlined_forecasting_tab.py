#!/usr/bin/env python3
"""
Streamlined Forecasting Tab - Clean & Efficient Dashboard

Focuses on:
1. Smart API data fetching based on market hours
2. Single model load (no excessive retraining)
3. Clean visual interface
4. Fast response times
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import os
import sys
from pathlib import Path
from typing import Dict, Optional

# Add forecasting platform to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(parent_dir)
sys.path.insert(0, root_dir)

# Import streamlined forecaster
try:
    from forecasting_platform.streamlined_forecaster import StreamlinedForecaster
    STREAMLINED_AVAILABLE = True
except ImportError as e:
    STREAMLINED_AVAILABLE = False
    st.error(f"Streamlined forecaster not available: {e}")


def render_streamlined_forecasting_tab():
    """Render the streamlined forecasting tab."""
    st.header("🚀 Live Forecasting - Streamlined")
    
    if not STREAMLINED_AVAILABLE:
        st.error("❌ Streamlined forecasting not available. Please check installation.")
        return
    
    # Initialize session state
    if 'streamlined_forecaster' not in st.session_state:
        st.session_state.streamlined_forecaster = StreamlinedForecaster()
    if 'last_forecast' not in st.session_state:
        st.session_state.last_forecast = None
    if 'last_forecast_time' not in st.session_state:
        st.session_state.last_forecast_time = None
    
    # Clean sidebar
    render_streamlined_sidebar()
    
    # Main content
    col1, col2 = st.columns([3, 1])
    
    with col1:
        render_streamlined_display()
    
    with col2:
        render_streamlined_controls()
    
    # Price chart
    render_streamlined_chart()


def render_streamlined_sidebar():
    """Clean, focused sidebar."""
    st.sidebar.header("📊 Controls")
    
    # Symbol input
    symbol = st.sidebar.text_input(
        "Symbol",
        value="TSM",
        help="Stock symbol (e.g., TSM, AAPL, SPY)"
    )
    
    # Auto refresh
    auto_refresh = st.sidebar.checkbox("Auto-Refresh", value=False)
    if auto_refresh:
        refresh_interval = st.sidebar.selectbox(
            "Interval",
            [300, 900, 1800, 3600],  # 5min, 15min, 30min, 1hr
            index=1,
            format_func=lambda x: f"{x//60} min"
        )
        st.session_state.auto_refresh = True
        st.session_state.refresh_interval = refresh_interval
    else:
        st.session_state.auto_refresh = False
    
    # Store symbol
    st.session_state.symbol = symbol
    
    # Status
    if hasattr(st.session_state, 'streamlined_forecaster'):
        forecaster = st.session_state.streamlined_forecaster
        if forecaster.model_loaded:
            st.sidebar.success("✅ Model Ready")
        else:
            st.sidebar.info("⏳ Model Loading...")
        
        if forecaster.cached_data:
            data_age = (datetime.now() - forecaster.last_data_fetch).total_seconds() / 60
            st.sidebar.caption(f"📡 Data: {data_age:.0f}m old")


def render_streamlined_controls():
    """Simple, clean controls."""
    st.subheader("🎯 Actions")
    
    if st.button("🔄 Generate Forecast", type="primary", use_container_width=True):
        with st.spinner("Generating..."):
            forecaster = st.session_state.streamlined_forecaster
            forecast = forecaster.generate_simple_forecast(st.session_state.symbol)
            
            if 'error' not in forecast:
                st.session_state.last_forecast = forecast
                st.session_state.last_forecast_time = datetime.now()
                st.success("✅ Updated!")
                st.rerun()
            else:
                st.error(f"❌ {forecast['error']}")
    
    if st.button("⚡ Refresh Data", use_container_width=True):
        with st.spinner("Refreshing..."):
            forecaster = st.session_state.streamlined_forecaster
            # Force refresh data
            forecaster.cached_data = None
            forecast = forecaster.generate_simple_forecast(st.session_state.symbol)
            
            if 'error' not in forecast:
                st.session_state.last_forecast = forecast
                st.session_state.last_forecast_time = datetime.now()
                st.success("✅ Refreshed!")
                st.rerun()
            else:
                st.error(f"❌ {forecast['error']}")
    
    # Status
    if st.session_state.last_forecast_time:
        age = datetime.now() - st.session_state.last_forecast_time
        st.caption(f"🕐 {age.total_seconds()/60:.0f}m ago")
    
    if st.session_state.auto_refresh:
        st.caption(f"🔄 Auto: {st.session_state.refresh_interval//60}min")


def render_streamlined_display():
    """Clean forecast display."""
    st.subheader("📊 Current Forecast")
    
    forecast = st.session_state.last_forecast
    
    if not forecast:
        st.info("👆 Generate a forecast to see predictions")
        return
    
    if 'error' in forecast:
        st.error(f"❌ {forecast['error']}")
        return
    
    # Main metrics - clean layout
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Direction",
            forecast['4hr_direction'],
            f"{forecast['4hr_confidence']:.0f}% confidence"
        )
    
    with col2:
        st.metric(
            "Current Price",
            f"${forecast['current_price']:.2f}",
            f"±{forecast['expected_move_pct']:.1f}%"
        )
    
    with col3:
        market_status = "🟢 OPEN" if forecast['market_open'] else "🔴 CLOSED"
        st.metric("Market", market_status)
    
    with col4:
        st.metric("Data Quality", forecast['data_quality'])
    
    # Technical levels - compact
    st.subheader("📈 Technical Levels")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("SMA 20", f"${forecast['sma_20']:.2f}")
    with col2:
        st.metric("Current", f"${forecast['current_price']:.2f}")  
    with col3:
        st.metric("RSI", f"{forecast['rsi']:.0f}")
    
    # Recommendation - prominent
    recommendation = forecast['recommendation']
    if "HIGH CONFIDENCE" in recommendation:
        st.success(f"✅ {recommendation}")
    elif "MODERATE" in recommendation:
        st.info(f"ℹ️ {recommendation}")
    else:
        st.warning(f"⚠️ {recommendation}")
    
    # Market info - when closed
    if not forecast['market_open']:
        st.info(f"📅 Using last market close: {forecast['last_close_time']}")


def render_streamlined_chart():
    """Simple, focused price chart."""
    st.subheader("📈 Price Chart")
    
    forecast = st.session_state.last_forecast
    if not forecast:
        st.info("Generate forecast to see chart")
        return
    
    # Get the cached data for charting
    forecaster = st.session_state.streamlined_forecaster
    if not forecaster.cached_data:
        st.info("No chart data available")
        return
    
    data = forecaster.cached_data['data']
    
    # Create simple candlestick chart
    fig = go.Figure(data=go.Candlestick(
        x=data.index,
        open=data['open'],
        high=data['high'],
        low=data['low'],
        close=data['close'],
        name="Price"
    ))
    
    # Add SMA lines
    if 'sma_20' in data.columns:
        fig.add_trace(go.Scatter(
            x=data.index,
            y=data['sma_20'],
            mode='lines',
            name='SMA 20',
            line=dict(color='orange', width=2)
        ))
    
    if 'sma_50' in data.columns:
        fig.add_trace(go.Scatter(
            x=data.index,
            y=data['sma_50'],
            mode='lines',
            name='SMA 50',
            line=dict(color='blue', width=2)
        ))
    
    # Clean layout
    fig.update_layout(
        title=f"{forecast['symbol']} - Recent Price Action",
        xaxis_title="Time",
        yaxis_title="Price ($)",
        height=400,
        showlegend=True,
        template='plotly_white'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Simple stats
    col1, col2, col3 = st.columns(3)
    with col1:
        daily_change = (data['close'].iloc[-1] / data['close'].iloc[-2] - 1) * 100
        st.metric("Daily Change", f"{daily_change:+.2f}%")
    with col2:
        high_52w = data['high'].max()
        st.metric("Period High", f"${high_52w:.2f}")
    with col3:
        low_52w = data['low'].min()
        st.metric("Period Low", f"${low_52w:.2f}")


# Auto-refresh logic
def check_auto_refresh():
    """Handle auto-refresh logic."""
    if not hasattr(st.session_state, 'auto_refresh') or not st.session_state.auto_refresh:
        return
    
    if not st.session_state.last_forecast_time:
        return
    
    time_since_last = datetime.now() - st.session_state.last_forecast_time
    should_refresh = time_since_last.total_seconds() > st.session_state.refresh_interval
    
    if should_refresh:
        # Trigger refresh
        forecaster = st.session_state.streamlined_forecaster
        forecast = forecaster.generate_simple_forecast(st.session_state.symbol)
        
        if 'error' not in forecast:
            st.session_state.last_forecast = forecast
            st.session_state.last_forecast_time = datetime.now()
            st.rerun()


# Main function for testing
if __name__ == "__main__":
    st.set_page_config(
        page_title="Streamlined Forecasting",
        page_icon="🚀",
        layout="wide"
    )
    
    render_streamlined_forecasting_tab()
