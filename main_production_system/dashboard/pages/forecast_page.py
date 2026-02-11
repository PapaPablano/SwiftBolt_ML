"""
Forecasting tools page.

Author: Cursor Agent
Created: 2025-10-31
"""

from __future__ import annotations

# Third-party imports
import streamlit as st

# Local imports
from core.data_pipeline import load_and_engineer


def render() -> None:
    st.header("Forecast")
    symbol = st.session_state.get("current_symbol", "AAPL")
    timeframe = st.session_state.get("current_timeframe", "1d")
    days = int(st.session_state.get("lookback_days", 365))

    df = load_and_engineer(symbol, timeframe, days, feature_set="all")
    st.write("Prepared features:")
    st.dataframe(df.tail(10))


