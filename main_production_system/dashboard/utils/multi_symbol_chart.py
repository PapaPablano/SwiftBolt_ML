"""
Multi-Symbol Chart Comparison Module

Koyfin-style multi-symbol overlay charts for comparing multiple stocks.
"""

import streamlit as st
import pandas as pd
from typing import Dict, List, Optional
import logging

from main_production_system.dashboard.utils.chart_service import render_multi_symbol_comparison

logger = logging.getLogger(__name__)


def render_multi_symbol_interface(
    available_symbols: Optional[List[str]] = None,
    default_symbols: Optional[List[str]] = None
) -> None:
    """
    Render a user interface for multi-symbol chart comparison.
    
    Args:
        available_symbols: List of available symbols to choose from (if None, uses user input)
        default_symbols: Default symbols to pre-select
    """
    st.subheader("📊 Multi-Symbol Comparison")
    st.markdown("Compare multiple stocks on a single chart (Koyfin-style)")
    
    # Symbol selection
    if available_symbols:
        selected_symbols = st.multiselect(
            "Select Symbols to Compare",
            options=available_symbols,
            default=default_symbols if default_symbols else available_symbols[:3] if len(available_symbols) >= 3 else available_symbols,
            help="Select up to 7 symbols for comparison"
        )
    else:
        # Manual input
        symbol_input = st.text_input(
            "Enter Symbols (comma-separated)",
            value=",".join(default_symbols) if default_symbols else "AAPL,MSFT,GOOGL",
            help="Enter stock symbols separated by commas (e.g., AAPL,MSFT,GOOGL)"
        )
        selected_symbols = [s.strip().upper() for s in symbol_input.split(",") if s.strip()]
    
    # Chart type selection
    col1, col2 = st.columns(2)
    with col1:
        chart_type = st.selectbox(
            "Chart Type",
            ["line", "candlestick", "bar"],
            index=0,
            help="Select visualization type for comparison"
        )
    with col2:
        show_volume = st.checkbox(
            "Show Volume",
            value=False,
            help="Display volume for first symbol"
        )
    
    # Limit to 7 symbols for clarity
    if len(selected_symbols) > 7:
        st.warning("⚠️ Maximum 7 symbols recommended for clarity. Showing first 7.")
        selected_symbols = selected_symbols[:7]
    
    if len(selected_symbols) < 2:
        st.info("ℹ️ Please select at least 2 symbols for comparison")
        return
    
    # Load data for each symbol
    if st.button("📈 Generate Comparison Chart", type="primary"):
        with st.spinner("Loading data for all symbols..."):
            symbol_data = {}
            failed_symbols = []
            
            for symbol in selected_symbols:
                try:
                    # Import data loading function
                    from core.data_pipeline import get_data_and_features
                    
                    # Get data (assuming same timeframe and lookback as session state)
                    timeframe = st.session_state.get("current_timeframe", "1d")
                    days = int(st.session_state.get("lookback_days", 30))
                    use_polygon = st.session_state.get("use_polygon", True)
                    
                    df_raw, _ = get_data_and_features(
                        symbol, timeframe, days,
                        use_polygon=use_polygon,
                        force_refresh=False
                    )
                    
                    if df_raw is not None and not df_raw.empty:
                        symbol_data[symbol] = df_raw
                    else:
                        failed_symbols.append(symbol)
                        
                except Exception as e:
                    logger.warning(f"[MULTI_SYMBOL] Failed to load {symbol}: {e}")
                    failed_symbols.append(symbol)
            
            if failed_symbols:
                st.warning(f"⚠️ Failed to load: {', '.join(failed_symbols)}")
            
            if symbol_data:
                success = render_multi_symbol_comparison(
                    symbol_data=symbol_data,
                    timeframe=st.session_state.get("current_timeframe", "1d"),
                    show_volume=show_volume,
                    chart_type=chart_type
                )
                
                if success:
                    st.success(f"✅ Comparison chart generated for {len(symbol_data)} symbols")
                else:
                    st.error("❌ Failed to generate comparison chart")
            else:
                st.error("❌ No data loaded for comparison")


def render_quick_comparison(
    symbol_data: Dict[str, pd.DataFrame],
    title: str = "Quick Comparison"
) -> None:
    """
    Quick render of multi-symbol comparison without UI controls.
    
    Args:
        symbol_data: Dictionary mapping symbols to DataFrames
        title: Chart title
    """
    if not symbol_data:
        st.warning("⚠️ No symbol data provided")
        return
    
    timeframe = st.session_state.get("current_timeframe", "1d")
    
    success = render_multi_symbol_comparison(
        symbol_data=symbol_data,
        timeframe=timeframe,
        show_volume=False,
        chart_type="line"
    )
    
    if not success:
        st.error("❌ Failed to render comparison chart")

