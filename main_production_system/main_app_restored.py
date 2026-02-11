#!/usr/bin/env python3
"""
Simplified ML Trading Platform
Streamlined interface for trading signals with real-time data
"""

import streamlit as st
from datetime import datetime
import pandas as pd
import sys
from pathlib import Path

# Add paths for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir.parent))

# Import core modules
try:
    from main_production_system.dashboard.core.model_manager import load_ml_models, predict_signal
    from main_production_system.dashboard.core.data_pipeline import get_data_and_features
    MODULES_AVAILABLE = True
except ImportError:
    try:
        # Fallback to relative imports
        from dashboard.core.model_manager import load_ml_models, predict_signal
        from dashboard.core.data_pipeline import get_data_and_features
        MODULES_AVAILABLE = True
    except ImportError as e:
        MODULES_AVAILABLE = False
        import_error = str(e)

st.set_page_config(page_title="ML Trading Platform", layout="wide")

# Show import status if needed
if not MODULES_AVAILABLE:
    st.error(f"❌ Import error: {import_error}")
    st.info("💡 Make sure you're running from the project root directory")

# Initialize session state
if 'models_loaded' not in st.session_state:
    st.session_state.models_loaded = False
if 'models_dict' not in st.session_state:
    st.session_state.models_dict = None
if 'last_signal' not in st.session_state:
    st.session_state.last_signal = None

# Title
st.title("🚀 ML Analysis Platform - Trading Signals")

# Sidebar
with st.sidebar:
    st.header("📊 Controls")
    
    ticker = st.selectbox(
        "Select Stock:",
        ["CRWD", "AAPL", "MSFT", "TSLA", "SPY", "QQQ", "NVDA"],
        index=0
    )
    
    timeframe = st.radio(
        "Timeframe:",
        ["1h", "4h", "1d"],
        index=2
    )
    
    days = st.slider(
        "Historical Days:",
        min_value=30,
        max_value=365,
        value=90,
        step=30
    )
    
    st.divider()
    
    if st.button("📥 Load Models", type="primary", use_container_width=True):
        if MODULES_AVAILABLE:
            with st.spinner("Loading models..."):
                try:
                    models_dict = load_ml_models()
                    if models_dict and any(v for k, v in models_dict.items() if k != 'status' and v is not None):
                        st.session_state.models_dict = models_dict
                        st.session_state.models_loaded = True
                        st.success("✅ Models Loaded!")
                    else:
                        st.error("❌ Failed to load models. Check logs for details.")
                except Exception as e:
                    st.error(f"❌ Error loading models: {e}")
                    st.exception(e)
        else:
            st.error("❌ Core modules not available")
    
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()
    
    # Show model status
    if st.session_state.models_loaded:
        st.success("✅ Models Ready")
        if st.session_state.models_dict:
            model_names = [name for name, model in st.session_state.models_dict.items() 
                         if model is not None and name != 'status']
            if model_names:
                st.info(f"📦 Loaded: {', '.join(model_names)}")
    else:
        st.warning("⚠️ Models Not Loaded")

# Main content
if not MODULES_AVAILABLE:
    st.error("❌ Core modules failed to load. Please check the installation.")
    st.stop()

if st.session_state.get('models_loaded', False):
    # Generate signal
    with st.spinner("Generating trading signal..."):
        try:
            # Get data and features
            df_ohlcv, df_features = get_data_and_features(
                symbol=ticker,
                timeframe=timeframe,
                days=days,
                feature_set='all',
                use_polygon=(timeframe in ['1h', '4h']),
                force_refresh=False
            )
            
            if df_features is None or df_features.empty:
                st.error("❌ Failed to generate features. Check data availability.")
                st.stop()
            
            # Get prediction
            signal_result = predict_signal(
                df_features=df_features,
                models_dict=st.session_state.models_dict,
                df_ohlcv=df_ohlcv
            )
            
            st.session_state.last_signal = signal_result
            
            # Extract metrics
            current_price = None
            if df_ohlcv is not None and 'Close' in df_ohlcv.columns:
                current_price = float(df_ohlcv['Close'].iloc[-1])
                price_change = None
                if len(df_ohlcv) > 1:
                    price_change = ((current_price - df_ohlcv['Close'].iloc[-2]) / df_ohlcv['Close'].iloc[-2]) * 100
            else:
                current_price = 0.0
                price_change = 0.0
            
            signal_text = signal_result.get('signal_text', 'HOLD')
            confidence = signal_result.get('confidence', 0.0) * 100
            model_used = signal_result.get('model', 'Unknown')
            
            # Display metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if current_price and current_price > 0:
                    delta = f"{price_change:+.2f}%" if price_change is not None else None
                    st.metric("Current Price", f"${current_price:.2f}", delta=delta)
                else:
                    st.metric("Current Price", "N/A")
            
            with col2:
                # Color code signal
                signal_color = {
                    'BUY': '🟢',
                    'SELL': '🔴',
                    'HOLD': '🟡'
                }
                signal_emoji = signal_color.get(signal_text, '⚪')
                st.metric("Signal", f"{signal_emoji} {signal_text}", 
                         help="Trading signal: BUY, SELL, or HOLD")
            
            with col3:
                confidence_label = "Strong" if confidence >= 70 else "Moderate" if confidence >= 50 else "Weak"
                st.metric("Confidence", f"{confidence:.1f}%", 
                         delta=confidence_label,
                         help="Model prediction confidence")
            
            with col4:
                st.metric("Model", model_used, 
                         help="Model used for prediction")
            
            # Status indicator
            if signal_result.get('error'):
                st.warning(f"⚠️ {signal_result.get('error')}")
            else:
                st.success("✅ System operational and generating trading signals")
            
            # Show additional details in expander
            with st.expander("📊 Signal Details"):
                st.json(signal_result)
                
                # Show data info
                if df_ohlcv is not None:
                    st.write(f"**Data Points:** {len(df_ohlcv)} candles")
                    st.write(f"**Features:** {len(df_features.columns)} columns")
                    st.write(f"**Date Range:** {df_ohlcv['Date'].min()} to {df_ohlcv['Date'].max()}")
                
                # Show component breakdown if available
                breakdown = signal_result.get('component_breakdown', {})
                if breakdown:
                    st.write("**Component Breakdown:**")
                    st.json(breakdown)
            
            # Quick chart
            if df_ohlcv is not None and 'Close' in df_ohlcv.columns:
                st.subheader("📈 Price Chart")
                chart_data = df_ohlcv[['Date', 'Close']].copy()
                chart_data = chart_data.set_index('Date')
                st.line_chart(chart_data)
                
        except Exception as e:
            st.error(f"❌ Error generating signal: {e}")
            st.exception(e)
else:
    st.warning("⚠️ Click 'Load Models' in the sidebar to start generating trading signals")
    
    # Show instructions
    with st.expander("ℹ️ How to Use"):
        st.markdown("""
        1. **Load Models**: Click the "📥 Load Models" button in the sidebar
        2. **Select Stock**: Choose a stock ticker from the dropdown
        3. **Choose Timeframe**: Select 1h, 4h, or 1d for data granularity
        4. **Set Historical Days**: Adjust how much historical data to use
        5. **View Signals**: The dashboard will automatically generate trading signals
        
        **Signal Meanings:**
        - 🟢 **BUY**: Model predicts upward price movement
        - 🔴 **SELL**: Model predicts downward price movement  
        - 🟡 **HOLD**: Model is neutral or uncertain
        
        **Confidence Levels:**
        - **Strong** (70%+): High model confidence
        - **Moderate** (50-70%): Moderate confidence
        - **Weak** (<50%): Low confidence - use caution
        """)

