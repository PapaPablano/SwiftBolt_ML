"""
System configuration page.

Author: Cursor Agent
Created: 2025-10-31
"""

from __future__ import annotations

# Third-party imports
import streamlit as st


def render() -> None:
    st.header("Config")
    st.json({
        "symbol": st.session_state.get("current_symbol", "AAPL"),
        "timeframe": st.session_state.get("current_timeframe", "1d"),
        "lookback_days": int(st.session_state.get("lookback_days", 365)),
    })


