# main_production_system/dashboard/components/sidebar_controls.py
import streamlit as st
import logging

logger = logging.getLogger(__name__)


def render_sidebar():
    """
    Render global sidebar controls for symbol, timeframe, and lookback period.
    Updates st.session_state with user selections.
    """

    st.sidebar.markdown("---")
    st.sidebar.subheader("🎛️ Global Controls")

    # Symbol selector (no key needed - Streamlit handles it)
    symbol = st.sidebar.text_input(
        "Symbol",
        value=st.session_state.get('symbol', 'AAPL'),
        help="Stock ticker symbol (e.g., AAPL, SPY, MSFT)",
    )
    st.session_state['symbol'] = symbol.upper()

    # Timeframe selector
    timeframe = st.sidebar.selectbox(
        "Timeframe",
        options=['1m', '5m', '15m', '1h', '4h', '1d', '1w'],
        index=5,  # Default to '1d'
        help="Candlestick interval",
    )
    st.session_state['timeframe'] = timeframe

    # Lookback period
    days = st.sidebar.slider(
        "Lookback (days)",
        min_value=7,
        max_value=365,
        value=st.session_state.get('days', 30),
        step=5,
        help="Number of days of historical data",
    )
    st.session_state['days'] = days
    
    # Data source selector
    st.sidebar.markdown("---")
    st.sidebar.subheader("📡 Data Source")
    data_provider = st.sidebar.selectbox(
        "Primary Provider (Fallback Auto)",
        options=['auto', 'yahoo_finance', 'alpha_vantage', 'polygon'],
        index=0,
        help="Auto prioritizes yfinance, then Alpha Vantage, Polygon as fallback"
    )
    st.session_state['data_provider'] = data_provider
    
    # ML Predictions toggle
    st.sidebar.markdown("---")
    st.sidebar.subheader("🤖 ML Predictions")
    show_predictions = st.sidebar.checkbox(
        "Enable ML Predictions",
        value=st.session_state.get('show_predictions', True),  # Default to True
        help="Show ML price predictions and forecast confidence bands on chart",
    )
    st.session_state['show_predictions'] = show_predictions

    logger.info(f"[SIDEBAR] {symbol} | {timeframe} | {days}d | Predictions: {show_predictions}")

