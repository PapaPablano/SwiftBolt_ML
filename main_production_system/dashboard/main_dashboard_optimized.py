#!/usr/bin/env python3
"""
Main Streamlit Dashboard (Optimized)

- Uses centralized configuration (ConfigLoader)
- Fast data I/O with CSV→Parquet caching (DataIO)
- Multi-provider live data with priority (DataProviderManager)
- Streamlit caching for responsiveness

Launch:
  cd main_production_system
  streamlit run dashboard/main_dashboard_optimized.py

Author: ML Analysis Platform Team
Date: October 28, 2025
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
import time
import pandas as pd
import numpy as np
import streamlit as st

# Project root resolution
HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
import sys
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "main_production_system"))
sys.path.insert(0, str(ROOT / "src"))

# Local imports
# Config
from main_production_system.core.config_loader import get_config
# Data I/O
from src.option_analysis.data_io import get_data_io
# Providers (your existing multi-provider manager)
from src.option_analysis.data_providers import DataProviderManager

# -----------------------------------------------------------------------------
# Streamlit Setup
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Wave Analogy Forecasting Dashboard (Optimized)",
    page_icon="🌊",
    layout="wide"
)

st.title("🌊 Wave Analogy Forecasting Dashboard (Optimized)")

# -----------------------------------------------------------------------------
# Helpers & Cache
# -----------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def get_resources():
    cfg = get_config()
    dio = get_data_io(base=ROOT)
    provider_mgr = DataProviderManager(cfg.get_all())
    return cfg, dio, provider_mgr

@st.cache_data(ttl=300, show_spinner=False)
def load_local_prices(path: str, usecols=None):
    cfg, dio, _ = get_resources()
    return dio.read_auto(path, usecols=usecols)

@st.cache_data(ttl=300, show_spinner=False)
def fetch_live_prices(symbol: str, interval: str, start: datetime, end: datetime, provider: str|None):
    cfg, dio, provider_mgr = get_resources()
    df = provider_mgr.fetch(symbol, start, end, interval, provider=provider)
    return df

# Utility
INTERVAL_ALIASES = {
    "4h": ["4h", "240"],
    "1h": ["1h", "60min", "60"],
    "1d": ["1d", "daily", "1day"],
}

def normalize_interval(i: str) -> str:
    i = (i or "").lower().strip()
    for key, vals in INTERVAL_ALIASES.items():
        if i in vals:
            return key
    return "1d"

# -----------------------------------------------------------------------------
# Sidebar Controls
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("Controls")
    symbol = st.text_input("Symbol", value="TSM").upper().strip()
    interval = st.selectbox("Interval", ["4h", "1h", "1d"], index=0)
    live_mode = st.toggle("Use live data (via providers)", value=True, help="When OFF, loads from local data/raw cache")
    provider_choice = st.selectbox(
        "Provider", ["auto", "finnhub", "polygon", "yahoo", "alpha_vantage"], index=0,
        help="auto = Finnhub → Polygon → Yahoo → Alpha Vantage"
    )
    horizon_days = st.slider("History Window (days)", min_value=7, max_value=365, value=90, step=1)
    run_btn = st.button("Run", type="primary", use_container_width=True)

# -----------------------------------------------------------------------------
# Data Load & Display
# -----------------------------------------------------------------------------
placeholder = st.empty()

if run_btn:
    provider_arg = None if provider_choice == "auto" else provider_choice
    norm_interval = normalize_interval(interval)

    # Compute start/end based on interval/horizon
    end_dt = datetime.utcnow()
    # For intraday, ensure enough density
    if norm_interval == "4h":
        start_dt = end_dt - timedelta(days=max(horizon_days, 30))
    elif norm_interval == "1h":
        start_dt = end_dt - timedelta(days=horizon_days)
    else:
        start_dt = end_dt - timedelta(days=horizon_days)

    with st.spinner("Loading data..."):
        t0 = time.time()
        cfg, dio, provider_mgr = get_resources()

        if live_mode:
            # Live via provider manager (with priority + fallback)
            df = fetch_live_prices(symbol, norm_interval, start_dt, end_dt, provider_arg)
            source = f"live:{provider_choice}"
            # Write-through cache to Parquet for future speedups
            raw_dir = cfg.get_path('paths.raw', base_path=ROOT)
            out_name = f"{symbol}_{norm_interval}_latest.parquet"
            dio.write_parquet(df, raw_dir / out_name)
        else:
            # Local load - try Parquet first then CSV patterns
            raw_dir = cfg.get_path('paths.raw', base_path=ROOT)
            parquet_try = [
                raw_dir / f"{symbol}_{norm_interval}_latest.parquet",
                raw_dir / f"data_NYSE_{symbol}_2y_1h.parquet",
            ]
            csv_try = [
                raw_dir / f"data_NYSE_{symbol}_2y_1h.csv",
                raw_dir / f"data_NASDAQ_{symbol}_2y_1h.csv",
                raw_dir / f"data_NYSE_{symbol}_1y_1h.csv",
                raw_dir / f"data_NASDAQ_{symbol}_1y_1h.csv",
            ]
            df = None
            for p in parquet_try:
                if p.exists():
                    df = load_local_prices(str(p))
                    source = f"local:{p.name}"
                    break
            if df is None:
                for p in csv_try:
                    if p.exists():
                        df = load_local_prices(str(p))
                        source = f"local:{p.name} (csv→parquet cached)"
                        break
            if df is None:
                st.error("No local files found. Enable live mode or add CSVs to data/raw/")
                st.stop()

        load_sec = time.time() - t0

    # Basic sanity/formatting
    if 'timestamp' not in df.columns:
        if df.index.name and 'timestamp' in df.index.name.lower():
            df = df.reset_index()
        else:
            # Attempt to infer
            df = df.rename(columns={c: 'timestamp' for c in df.columns if c.lower() in ('date','time','datetime')})
            if 'timestamp' not in df.columns:
                st.error("Could not locate timestamp column in loaded data")
                st.stop()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)

    # Show metrics
    st.subheader("Data Summary")
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Symbol", symbol)
    with c2: st.metric("Interval", norm_interval)
    with c3: st.metric("Rows", f"{len(df):,}")
    with c4: st.metric("Load Time", f"{load_sec:.3f}s")

    st.caption(f"Source: {source}")

    # Charts
    st.subheader("Price Chart")
    price_col = None
    for c in ['close','Close','adj_close','Adj Close']:
        if c in df.columns:
            price_col = c
            break
    if price_col is None:
        st.warning("No close column found; showing first numeric column")
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        price_col = num_cols[0] if num_cols else None
    if price_col:
        st.line_chart(df.set_index('timestamp')[price_col])
    else:
        st.warning("No numeric columns to chart")

    # Display raw snapshot
    with st.expander("Show data sample", expanded=False):
        st.dataframe(df.tail(200), use_container_width=True)

    # Provider diagnostics
    st.subheader("Provider Diagnostics")
    cache_info = get_data_io(base=ROOT).get_cache_info()
    d1, d2, d3 = st.columns(3)
    with d1: st.metric("Cache Files", cache_info['num_files'])
    with d2: st.metric("Cache Size (MB)", f"{cache_info['total_size_mb']:.2f}")
    with d3:
        _, _, mgr = get_resources()
        try:
            status = getattr(mgr, 'get_provider_status', lambda: {'current':'auto','available_providers': list(mgr.providers.keys())})()
        except Exception:
            status = {'current':'auto','available_providers': list(mgr.providers.keys())}
        st.json(status)

    st.success("Done. Data flow using optimized caching and provider priority is active.")

else:
    st.info("Set your parameters in the sidebar and click Run.")