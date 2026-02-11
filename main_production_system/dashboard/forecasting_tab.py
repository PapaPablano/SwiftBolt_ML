#!/usr/bin/env python3
"""
Live Forecasting Tab - Smart Workflow Dashboard Integration

Provides real-time forecasting with wave analogy strategy and regime detection.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from datetime import datetime, timedelta
import time
import os
import sys
from pathlib import Path
from typing import Dict, Optional
import logging

# Add forecasting platform to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(parent_dir)
sys.path.insert(0, root_dir)

# Import streamlined forecasting components
try:
    from forecasting_platform.streamlined_forecaster import StreamlinedForecaster
    FORECASTING_AVAILABLE = True
except ImportError as e:
    FORECASTING_AVAILABLE = False
    st.error(f"Streamlined forecasting not available: {e}")

logger = logging.getLogger(__name__)


def render_forecasting_tab():
    """Render the Live Forecasting tab."""
    st.header("🌊 Live Forecasting")
    
    if not FORECASTING_AVAILABLE:
        st.error("❌ Forecasting platform not available. Please check installation.")
        return
    
    # Initialize session state with streamlined forecaster
    if 'streamlined_forecaster' not in st.session_state:
        st.session_state.streamlined_forecaster = StreamlinedForecaster()
    if 'forecast_history' not in st.session_state:
        st.session_state.forecast_history = []
    if 'last_forecast_time' not in st.session_state:
        st.session_state.last_forecast_time = None
    
    # Sidebar controls
    render_forecasting_sidebar()
    
    # Main content - focused layout
    col1, col2 = st.columns([3, 1])
    
    with col1:
        render_forecast_display()
    
    with col2:
        render_forecast_controls()
    
    # Price Projections Chart (primary focus)
    render_price_projections_chart()
    
    # Compact analysis row
    col3, col4 = st.columns(2)
    with col3:
        render_wave_analogy_breakdown()
    with col4:
        render_regime_analysis()
    
    # History (collapsible)
    if st.session_state.forecast_history:
        with st.expander("📚 Forecast History"):
            render_forecast_history()


def render_forecasting_sidebar():
    """Render forecasting controls in sidebar."""
    st.sidebar.header("🎯 Controls")
    
    # Symbol input
    symbol = st.sidebar.text_input(
        "Symbol",
        value="TSM",
        help="Stock symbol (TSM, SPY, QQQ)"
    )
    
    # Quick settings
    col1, col2 = st.sidebar.columns(2)
    with col1:
        training_period = st.selectbox(
            "Training",
            ["1y", "2y", "3y"],
            index=1
        )
    with col2:
        live_period = st.selectbox(
            "Live Data",
            ["1d", "3d", "5d", "7d"],
            index=2
        )
    
    # Auto-refresh (compact)
    auto_refresh = st.sidebar.checkbox("Auto-Refresh", value=False)
    if auto_refresh:
        refresh_interval = st.sidebar.selectbox(
            "Interval",
            [300, 900, 1800, 3600],
            index=1,
            format_func=lambda x: f"{x//60}min"
        )
    
    # Advanced settings (collapsible)
    with st.sidebar.expander("⚙️ Advanced"):
        st.markdown("**Timeframes:**")
        st.markdown("• 4hr: Decision timeframe")
        st.markdown("• Daily: Context")
        st.markdown("• Weekly: Trend")
    
    if st.sidebar.button("🎯 Load Model"):
        with st.spinner("Loading model..."):
            try:
                forecaster = st.session_state.streamlined_forecaster
                if forecaster.load_model_if_needed():
                    st.session_state.last_forecast_time = None  # Force refresh
                    st.sidebar.success("✅ Model Ready!")
                else:
                    st.sidebar.error("❌ Model not found!")
            except Exception as e:
                st.sidebar.error(f"❌ Failed: {str(e)}")
    
    # Store settings in session state
    st.session_state.symbol = symbol
    st.session_state.auto_refresh = auto_refresh
    st.session_state.refresh_interval = refresh_interval if auto_refresh else None
    st.session_state.training_period = training_period
    st.session_state.live_period = live_period


def render_forecast_display():
    """Render the main forecast display."""
    st.subheader("📊 Current Forecast")
    
    # Display ES Context (Market Current)
    try:
        from core.volatility_models.es_data_fetcher import fetch_es_futures
        from core.data_pipeline import load_es_and_stock_aligned
        
        symbol = st.session_state.get('symbol', 'TSM')
        
        with st.expander("📊 MARKET CURRENT (ES Futures)", expanded=True):
            # Fetch ES context
            es_context = fetch_es_futures(days=30)
            
            if es_context and es_context.get('error') is None:
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric('ES Price', f'${es_context["es_price"]:.0f}' if es_context.get('es_price') else 'N/A')
                
                with col2:
                    trend_arrow = '📈' if es_context.get('es_trend') == 'UP' else '📉' if es_context.get('es_trend') == 'DOWN' else '➡️'
                    momentum_val = es_context.get('es_momentum', 0) * 100
                    st.metric('ES Trend', trend_arrow, 
                              delta=f'{momentum_val:.2f}%' if momentum_val else None)
                
                with col3:
                    volatility_val = es_context.get('es_volatility', 0) * 100
                    st.metric('ES Volatility', f'{volatility_val:.1f}%' if volatility_val else 'N/A')
                
                # Try to get correlation from aligned data
                correlation = None
                try:
                    aligned_data = load_es_and_stock_aligned(symbol, days=252)
                    if aligned_data and aligned_data.get('correlation'):
                        correlation = aligned_data['correlation']
                except Exception:
                    pass
                
                with col4:
                    if correlation is not None:
                        st.metric('Stock-ES Correlation', f'{correlation:.2f}')
                        st.caption('0.6+ = Strong flow-through')
                    else:
                        st.metric('Stock-ES Correlation', 'N/A')
                
                # Show stock vs ES comparison
                if correlation is not None:
                    st.info(f'''
                    **Market Current Analysis:**
                    - ES moving: **{es_context.get('es_trend', 'UNKNOWN')}** {momentum_val:.1f}%
                    - **{correlation*100:.0f}%** of {symbol} moves expected from ES alone
                    - **Alpha opportunity:** Trading the {100-correlation*100:.0f}% that's stock-specific
                    ''')
    except ImportError:
        pass  # ES integration not available, skip silently
    except Exception:
        pass  # Error fetching ES, skip silently
    
    # Compact timestamp
    if st.session_state.last_forecast_time:
        last_update = st.session_state.last_forecast_time.strftime("%H:%M")
        st.caption(f"🕰️ {last_update}")
    
    # Get or generate forecast
    forecast = get_current_forecast()
    
    if forecast and 'error' not in forecast:
        # Main forecast metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Direction",
                forecast['4hr_direction'],
                delta=f"{forecast['4hr_probability']*100:.1f}%"
            )
        
        with col2:
            confidence_color = "normal"
            if forecast['4hr_confidence'] > 70:
                confidence_color = "normal"
            elif forecast['4hr_confidence'] < 50:
                confidence_color = "inverse"
            
            st.metric(
                "Confidence",
                f"{forecast['4hr_confidence']:.1f}%",
                delta=forecast.get('regime', 'UNKNOWN').replace('STREAMLINED_', '')
            )
        
        with col3:
            st.metric(
                "Current Price",
                f"${forecast['current_price']:.2f}",
                delta=f"±{forecast['expected_move_pct']:.2f}%"
            )
        
        with col4:
            # Market status - streamlined format
            market_open = forecast.get('market_open', True)
            last_close_time = forecast.get('last_close_time', forecast.get('last_close_date', ''))
            
            if market_open:
                st.metric(
                    "Market",
                    "🟢 OPEN",
                    delta="Live"
                )
            else:
                st.metric(
                    "Market", 
                    "🔴 CLOSED",
                    delta="Last close"
                )
        
        # Streamlined analysis info
        st.subheader("📊 Analysis")
        col1, col2 = st.columns(2)
        
        with col1:
            data_quality = forecast.get('data_quality', 'UNKNOWN')
            st.info(f"**Data Quality:** {data_quality}")
        with col2:
            processing = forecast.get('processing_time', 'UNKNOWN')
            st.info(f"**Processing:** {processing}")
        
        # Recommendation
        st.subheader("🎯 Trading Recommendation")
        
        recommendation = forecast['recommendation']
        if "HIGH CONFIDENCE" in recommendation:
            st.success(f"✅ {recommendation}")
        elif "LOW CONFIDENCE" in recommendation:
            st.warning(f"⚠️ {recommendation}")
        else:
            st.info(f"ℹ️ {recommendation}")
        
        # Key levels
        st.subheader("📈 Technical Levels")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            sma_short = forecast.get('sma_short', forecast['current_price'])
            st.metric("SMA Short", f"${sma_short:.2f}")
        
        with col2:
            st.metric("Current", f"${forecast['current_price']:.2f}")
        
        with col3:
            rsi = forecast.get('rsi', 50)
            st.metric("RSI", f"{rsi:.0f}")
        
        # Price chart
        render_price_chart(forecast)
        
    elif forecast and 'error' in forecast:
        st.error(f"❌ Forecast Error: {forecast['error']}")
    else:
        st.info("👆 Load model in sidebar, then generate forecast")


def render_forecast_controls():
    """Render forecast control buttons."""
    st.subheader("🎯 Actions")
    
    if st.button("🔄 Generate", type="primary", width="stretch"):
        forecaster = st.session_state.streamlined_forecaster
        if not forecaster.model_loaded:
            st.warning("⚠️ Load model first")
        else:
            with st.spinner("Generating..."):
                forecast = forecaster.generate_simple_forecast(st.session_state.symbol)
                if 'error' not in forecast:
                    st.session_state.forecast_history.append(forecast)
                    st.session_state.last_forecast_time = datetime.now()
                    st.success("✅ Done!")
                    st.rerun()
                else:
                    st.error(f"❌ {forecast['error']}")
    
    # Add refresh now button
    if st.button("⚡ Refresh", width="stretch"):
        forecaster = st.session_state.streamlined_forecaster
        if not forecaster.model_loaded:
            st.warning("⚠️ Load model first")
        else:
            with st.spinner("Refreshing..."):
                # Force refresh data cache
                forecaster.cached_data = None
                forecast = forecaster.generate_simple_forecast(st.session_state.symbol)
                if 'error' not in forecast:
                    st.session_state.forecast_history.append(forecast)
                    st.session_state.last_forecast_time = datetime.now()
                    st.success("✅ Updated!")
                    st.rerun()
                else:
                    st.error(f"❌ {forecast['error']}")
    
    # Compact status
    if hasattr(st.session_state, 'auto_refresh') and st.session_state.auto_refresh:
        st.caption(f"🔄 Auto: {st.session_state.refresh_interval//60}min")
    
    if st.session_state.forecast_history:
        st.caption(f"📊 {len(st.session_state.forecast_history)} forecasts")


def render_price_projections_chart():
    """Render price projections chart."""
    forecast = get_current_forecast()
    
    st.subheader("📈 Projections")
    
    if not forecast or 'error' in forecast:
        st.info("Generate forecast to see projections")
        return
    
    if 'price_projections' not in forecast:
        st.warning("Price projections not available in current forecast.")
        return
    
    projections = forecast['price_projections']
    symbol = forecast.get('symbol', 'Stock')
    
    # Create DataFrame for plotting
    df_proj = pd.DataFrame({
        'Date': pd.to_datetime(projections['dates']),
        'Conservative': projections['conservative'],
        'Expected': projections['expected'],
        'Optimistic': projections['optimistic']
    })
    
    # Create the chart
    fig = go.Figure()
    
    # Add traces
    fig.add_trace(go.Scatter(
        x=df_proj['Date'],
        y=df_proj['Conservative'],
        mode='lines+markers',
        name='Conservative',
        line=dict(color='orange', dash='dash'),
        marker=dict(size=6)
    ))
    
    fig.add_trace(go.Scatter(
        x=df_proj['Date'],
        y=df_proj['Expected'],
        mode='lines+markers',
        name='Expected',
        line=dict(color='#1f77b4', width=3),
        marker=dict(size=8)
    ))
    
    fig.add_trace(go.Scatter(
        x=df_proj['Date'],
        y=df_proj['Optimistic'],
        mode='lines+markers',
        name='Optimistic',
        line=dict(color='green', dash='dash'),
        marker=dict(size=6)
    ))
    
    # Add current price line
    current_price = projections['current_price']
    fig.add_hline(
        y=current_price,
        line_dash="dot",
        line_color="red",
        annotation_text=f"Current: ${current_price:.2f}"
    )
    
    # Calculate expected return
    days_return = (df_proj['Expected'].iloc[-1] - current_price) / current_price * 100
    
    # Update layout
    fig.update_layout(
        title=f"{symbol} 5-Day Price Forecast<br><sub>Direction: {projections['direction']} | Confidence: {projections['confidence']:.1f}% | Expected Return: {days_return:+.2f}%</sub>",
        xaxis_title="Date",
        yaxis_title="Price ($)",
        hovermode='x unified',
        template='plotly_white',
        height=500
    )
    
    # Format x-axis
    fig.update_xaxes(
        tickformat="%b %d",
        tickmode='linear',
        tick0=df_proj['Date'].iloc[0],
        dtick=86400000  # 1 day in milliseconds
    )
    
    # Add grid
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Show projection summary
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Conservative Target",
            f"${df_proj['Conservative'].iloc[-1]:.2f}",
            f"{((df_proj['Conservative'].iloc[-1] - current_price) / current_price * 100):+.2f}%"
        )
    
    with col2:
        st.metric(
            "Expected Target",
            f"${df_proj['Expected'].iloc[-1]:.2f}",
            f"{((df_proj['Expected'].iloc[-1] - current_price) / current_price * 100):+.2f}%"
        )
    
    with col3:
        st.metric(
            "Optimistic Target",
            f"${df_proj['Optimistic'].iloc[-1]:.2f}",
            f"{((df_proj['Optimistic'].iloc[-1] - current_price) / current_price * 100):+.2f}%"
        )


# Removed - moved to sidebar expander for cleaner layout


def render_wave_analogy_breakdown():
    """Render wave analogy breakdown."""
    st.subheader("🌊 Wave Analysis")
    
    forecast = get_current_forecast()
    if not forecast or 'error' in forecast:
        st.info("Generate forecast first")
        return
    
    # Direction from streamlined forecast
    direction = forecast.get('4hr_direction', 'UNKNOWN')
    if direction == 'UP':
        st.success(f"📈 Trend: BULLISH")
    elif direction == 'DOWN':
        st.error(f"📉 Trend: BEARISH")
    else:
        st.info(f"➡️ Trend: {direction}")
    
    # Key metrics only
    direction = forecast.get('4hr_direction', 'UNKNOWN')
    confidence = forecast.get('4hr_confidence', 0)
    expected_move = forecast.get('expected_move_pct', 0)
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Next 4hr", direction, f"{confidence:.0f}% confidence")
    with col2:
        st.metric("Move", f"±{expected_move:.1f}%")


def render_regime_analysis():
    """Render regime analysis."""
    st.subheader("📊 Regime")
    
    forecast = get_current_forecast()
    if not forecast or 'error' in forecast:
        st.info("Generate forecast first")
        return
    
    # Data quality from streamlined forecast
    data_quality = forecast.get('data_quality', 'UNKNOWN')
    processing_time = forecast.get('processing_time', 'UNKNOWN')
    
    # Display analysis quality
    if data_quality == 'GOOD':
        st.success(f"✅ Data Quality: {data_quality}")
    elif data_quality == 'LIMITED':
        st.warning(f"⚠️ Data Quality: {data_quality}")
    else:
        st.info(f"ℹ️ Data Quality: {data_quality}")
    
    # Processing efficiency
    if processing_time == 'FAST':
        st.success("⚡ Fast Processing")
    else:
        st.info(f"⏱️ Processing: {processing_time}")
    
    # Confidence metric
    confidence = forecast.get('4hr_confidence', 0)
    st.metric("Confidence", f"{confidence:.0f}%")


def render_price_chart(forecast):
    """Render price chart with key levels."""
    st.subheader("📈 Price Chart")
    
    # Simplified chart with available data
    current_price = forecast['current_price']
    sma_short = forecast.get('sma_short', current_price)
    sma_long = forecast.get('sma_long', current_price)
    
    # Create sample price data for visualization
    dates = pd.date_range(end=datetime.now(), periods=20, freq='4H')
    prices = np.random.normal(current_price, current_price * 0.02, 20)
    prices[-1] = current_price  # Set last price to current
    
    fig = go.Figure()
    
    # Price line
    fig.add_trace(go.Scatter(
        x=dates,
        y=prices,
        mode='lines',
        name='Price',
        line=dict(color='blue', width=2)
    ))
    
    # SMA Short line
    fig.add_hline(
        y=sma_short,
        line_dash="dash",
        line_color="orange",
        annotation_text=f"SMA Short: ${sma_short:.2f}"
    )
    
    # SMA Long line (if different from short)
    if abs(sma_long - sma_short) > 0.01:
        fig.add_hline(
            y=sma_long,
            line_dash="dash",
            line_color="blue",
            annotation_text=f"SMA Long: ${sma_long:.2f}"
        )
    
    # Current price line
    fig.add_hline(
        y=current_price,
        line_dash="dot",
        line_color="orange",
        annotation_text=f"Current: ${current_price:.2f}"
    )
    
    fig.update_layout(
        title=f"Price Chart - {forecast['symbol']}",
        xaxis_title="Time",
        yaxis_title="Price ($)",
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_forecast_history():
    """Render forecast history."""
    if not st.session_state.forecast_history:
        return
    
    # Convert to DataFrame for display
    history_df = pd.DataFrame(st.session_state.forecast_history)
    
    # Select columns to display
    display_cols = [
        'timestamp', '4hr_direction', '4hr_confidence', 
        'regime', 'current_price', 'expected_accuracy'
    ]
    
    if all(col in history_df.columns for col in display_cols):
        display_df = history_df[display_cols].copy()
        display_df['timestamp'] = pd.to_datetime(display_df['timestamp'])
        display_df = display_df.sort_values('timestamp', ascending=False)
        
        st.dataframe(
            display_df,
            use_container_width=True,
            height=300
        )
        
        # Summary statistics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Forecasts", len(history_df))
        
        with col2:
            up_forecasts = len(history_df[history_df['4hr_direction'] == 'UP'])
            st.metric("UP Forecasts", up_forecasts)
        
        with col3:
            avg_confidence = history_df['4hr_confidence'].mean()
            st.metric("Avg Confidence", f"{avg_confidence:.1f}%")


def get_current_forecast():
    """Get current forecast, generating if needed."""
    if not hasattr(st.session_state, 'streamlined_forecaster'):
        return None
    
    forecaster = st.session_state.streamlined_forecaster
    
    # Check if we need to refresh
    if st.session_state.auto_refresh and st.session_state.last_forecast_time:
        time_since_last = datetime.now() - st.session_state.last_forecast_time
        if time_since_last.total_seconds() > st.session_state.refresh_interval:
            # Auto-refresh
            try:
                forecast = forecaster.generate_simple_forecast(st.session_state.symbol)
                if 'error' not in forecast:
                    st.session_state.forecast_history.append(forecast)
                    st.session_state.last_forecast_time = datetime.now()
                return forecast
            except Exception as e:
                st.error(f"Auto-refresh failed: {e}")
                return None
    
    # Return last forecast if available
    if st.session_state.forecast_history:
        return st.session_state.forecast_history[-1]
    
    return None


# Main function for testing
if __name__ == "__main__":
    st.set_page_config(
        page_title="Live Forecasting",
        page_icon="🌊",
        layout="wide"
    )
    
    render_forecasting_tab()
