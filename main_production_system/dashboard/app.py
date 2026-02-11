#!/usr/bin/env python3
"""
Wave Trading System - Unified Dashboard

Main entry point for the trading system dashboard.

Launch:
    cd /Users/ericpeterson/Attention-Based\ Multi-Timeframe-Transformer
    export PYTHONPATH="$(pwd):$PYTHONPATH"
    streamlit run main_production_system/dashboard/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st

st.set_page_config(
    page_title="Wave Trading System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Main header
st.markdown("<h1>🌊 Wave Trading System</h1>", unsafe_allow_html=True)
st.markdown("Multi-Timeframe Wave Confluence Analysis")

# Sidebar navigation (Streamlit multipage uses st.switch_page to pages/*.py)
with st.sidebar:
    st.header("Navigation")
    if st.button("📈 Wave Analysis", use_container_width=True):
        st.switch_page("pages/1_📈_Wave_Analysis.py")
    if st.button("📊 Performance", use_container_width=True):
        st.switch_page("pages/2_📊_Performance.py")

# Welcome section
col1, col2 = st.columns(2)
with col1:
    st.markdown(
        """
        ### 📈 Wave Analysis
        Detect and analyze price waves across multiple timeframes:
        - **10-minute waves** - Short-term moves
        - **1-hour waves** - Intraday trends
        - **4-hour waves** - Swing trade setups
        **Features:**
        - Multi-timeframe wave detection
        - Confluence signal identification
        - Quality scoring (A/B/C grades)
        - Auto signal tracking
        """
    )
    if st.button("🚀 Start Wave Analysis", key="goto_analysis"):
        st.switch_page("pages/1_📈_Wave_Analysis.py")

with col2:
    st.markdown(
        """
        ### 📊 Performance Analytics
        Track and analyze your trading performance:
        - **Win Rate** - Track success percentage
        - **Expectancy** - Calculate edge
        - **Equity Curve** - Visualize growth
        **Features:**
        - Real-time performance metrics
        - Historical signal analysis
        - Time-based patterns
        - Best/worst signal review
        """
    )
    if st.button("📊 View Performance", key="goto_performance"):
        st.switch_page("pages/2_📊_Performance.py")

# Quick stats
st.markdown("---")
st.subheader("🎯 Quick Stats")

from core.wave_detection.signal_tracker import SignalTracker  # noqa: E402

tracker = SignalTracker()
_df = tracker.get_all_signals()
col1, col2, col3, col4 = st.columns(4)

with col1:
    total_signals = len(_df)
    st.metric("Total Signals", total_signals)

with col2:
    open_signals = len(_df[_df["status"] == "open"]) if not _df.empty and "status" in _df.columns else 0
    st.metric("Open Signals", open_signals)

with col3:
    if not _df.empty and "status" in _df.columns:
        closed = _df[_df["status"].isin(["win", "loss"])]
        wins = len(closed[closed["status"] == "win"]) if not closed.empty else 0
        denom = len(closed) if not closed.empty else 0
        win_rate = (wins / denom * 100.0) if denom else 0.0
        st.metric("Win Rate", f"{win_rate:.1f}%")
    else:
        st.metric("Win Rate", "0.0%")

with col4:
    if not _df.empty and "symbol" in _df.columns:
        recent = _df.tail(1)
        last_symbol = recent.iloc[0]["symbol"] if len(recent) > 0 else "None"
        st.metric("Last Signal", last_symbol)
    else:
        st.metric("Last Signal", "None")

# Getting started
st.markdown("---")
st.subheader("🚀 Getting Started")

st.markdown(
    """
    1. Analyze Waves - Go to Wave Analysis page and enter a symbol
    2. Review Signals - System automatically detects confluence signals
    3. Track Performance - Signals are saved and monitored automatically
    4. View Analytics - Check Performance page to see results

    Navigation: Use the sidebar on the left to switch between pages.
    """
)
