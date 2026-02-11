"""
Technical analysis page.

Author: Cursor Agent
Created: 2025-10-31
"""

from __future__ import annotations

# Third-party imports
import streamlit as st

# Local imports
from core.feature_engine import engineer_features
from core.data_pipeline import load_market_data, get_data_and_features
from components.chart_builder import build_price_chart
from components.indicator_overlays import add_simple_moving_average


def render() -> None:
    st.header("Analysis")
    symbol = st.session_state.get("current_symbol", "AAPL")
    timeframe = st.session_state.get("current_timeframe", "1d")
    days = int(st.session_state.get("lookback_days", 365))

    df = load_market_data(symbol, timeframe, days)
    df = engineer_features(df, feature_set="all")

    build_price_chart(df, title=f"{symbol} ({timeframe})")

    sma = add_simple_moving_average(df, window=20)
    if sma is not None and not sma.empty:
        st.line_chart(sma.rename("SMA 20"))


