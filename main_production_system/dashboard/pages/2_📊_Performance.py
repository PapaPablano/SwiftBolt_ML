#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Ensure project root is on sys.path
project_root = Path(__file__).resolve().parents[3]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

st.set_page_config(page_title="Performance Analytics", page_icon="📊", layout="wide")
st.sidebar.info("💡 Analyze new symbols in Wave Analysis page")

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

from core.wave_detection.signal_tracker import SignalTracker

st.title("🎯 Wave Detection Performance Analytics")

tracker = SignalTracker()
df_signals = tracker.get_all_signals()

if df_signals.empty:
    st.info("No signals found yet. Start generating signals to see analytics.")
    st.stop()

# Filters and metrics replicate original dashboard
df = df_signals.copy()
if "profit_pct" not in df.columns:
    df["profit_pct"] = np.nan

df["profit_pct"] = pd.to_numeric(df["profit_pct"], errors="coerce")
df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
df.sort_values("timestamp", inplace=True)
df["status"] = df["status"].fillna("open")

with st.sidebar:
    st.header("Filters")
    symbols = ["All"] + sorted(df["symbol"].dropna().unique().tolist())
    sel_symbol = st.selectbox("Symbol", symbols)
    direction = st.multiselect("Direction", ["bullish", "bearish"], default=["bullish", "bearish"])
    status_sel = st.multiselect("Status", ["open", "win", "loss", "expired"], default=["win", "loss", "open", "expired"])
    if st.button("📈 Analyze New Symbol"):
        st.switch_page("pages/1_📈_Wave_Analysis.py")

# Apply filters
df_f = df.copy()
if sel_symbol != "All":
    df_f = df_f[df_f["symbol"] == sel_symbol]
df_f = df_f[df_f["direction"].isin(direction)]
df_f = df_f[df_f["status"].isin(status_sel)]

# Key metrics
col1, col2, col3, col4 = st.columns(4)

total = len(df_f)
wins = int((df_f["status"] == "win").sum())
losses = int((df_f["status"] == "loss").sum())
win_rate = (wins / total * 100.0) if total else 0.0
avg_win = float(df_f.loc[df_f["status"] == "win", "profit_pct"].mean()) if wins else 0.0
avg_loss = float(df_f.loc[df_f["status"] == "loss", "profit_pct"].mean()) if losses else 0.0
expectancy = (win_rate / 100.0 * avg_win) + ((1 - win_rate / 100.0) * avg_loss)

with col1:
    st.metric("Win Rate", f"{win_rate:.1f}%", delta=f"{wins}/{total}")
with col2:
    st.metric("Avg Win", f"{avg_win:+.2f}%")
with col3:
    st.metric("Avg Loss", f"{avg_loss:+.2f}%")
with col4:
    st.metric("Expectancy", f"{expectancy:+.2f}%")

# Charts
fig = make_subplots(
    rows=2,
    cols=2,
    subplot_titles=(
        "Cumulative P&L",
        "Win Rate by Month",
        "Performance by Timeframe",
        "Confidence vs Profit%",
    ),
)

df_f_sorted = df_f.sort_values("timestamp").copy()
df_f_sorted["profit_pct_filled"] = df_f_sorted["profit_pct"].fillna(0.0)
df_f_sorted["cumulative_pl"] = df_f_sorted["profit_pct_filled"].cumsum()

fig.add_trace(
    go.Scatter(x=df_f_sorted["timestamp"], y=df_f_sorted["cumulative_pl"], mode="lines", name="Cumulative P&L", line=dict(color="green", width=2)),
    row=1,
    col=1,
)

monthly = df_f.assign(month=df_f["timestamp"].dt.to_period("M")).groupby("month").apply(lambda x: (x["status"] == "win").sum() / len(x) * 100.0)
fig.add_trace(go.Bar(x=monthly.index.astype(str), y=monthly.values, name="Monthly Win Rate"), row=1, col=2)

if "timeframes" in df_f.columns:
    tf_win = (df_f.assign(win=(df_f["status"] == "win").astype(int)).groupby("timeframes")["win"].mean() * 100.0).sort_values(ascending=False)
else:
    tf_win = pd.Series(dtype=float)
fig.add_trace(go.Bar(x=tf_win.index.astype(str), y=tf_win.values, name="Win Rate by TF"), row=2, col=1)

fig.add_trace(
    go.Scatter(
        x=df_f["confidence"],
        y=df_f["profit_pct"],
        mode="markers",
        name="Signals",
        marker=dict(color=df_f["status"].map({"win": "green", "loss": "red", "open": "gray", "expired": "orange"}), size=8),
    ),
    row=2,
    col=2,
)

fig.update_layout(height=800, showlegend=False)
st.plotly_chart(fig, use_container_width=True)

# Tables and additional views as in original page
st.subheader("🔍 Signal Quality Breakdown")
col1, col2 = st.columns(2)
with col1:
    st.markdown("**Best Signals:**")
    best = df_f[df_f["status"] == "win"].nlargest(10, "profit_pct")
    st.dataframe(best[["timestamp", "symbol", "direction", "confidence", "profit_pct"]])
with col2:
    st.markdown("**Worst Signals:**")
    worst = df_f[df_f["status"] == "loss"].nsmallest(10, "profit_pct")
    st.dataframe(worst[["timestamp", "symbol", "direction", "confidence", "profit_pct"]])

st.subheader("📈 Additional Performance Views")
colA, colB = st.columns(2)
with colA:
    st.markdown("**Equity Curve and Drawdown**")
    curve = df_f_sorted[["timestamp", "cumulative_pl"]].set_index("timestamp")
    roll_max = curve["cumulative_pl"].cummax()
    drawdown = curve["cumulative_pl"] - roll_max
    fig_dd = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05)
    fig_dd.add_trace(go.Scatter(x=curve.index, y=curve["cumulative_pl"], name="Equity", line=dict(color="green")), row=1, col=1)
    fig_dd.add_trace(go.Bar(x=curve.index, y=drawdown, name="Drawdown", marker_color="crimson"), row=2, col=1)
    fig_dd.update_layout(height=500, showlegend=False)
    st.plotly_chart(fig_dd, use_container_width=True)
with colB:
    st.markdown("**Profit/Loss Distribution**")
    closed = df_f[df_f["status"].isin(["win", "loss", "expired"])]
    fig_hist = go.Figure()
    fig_hist.add_trace(go.Histogram(x=closed["profit_pct"], nbinsx=40, marker_color="#4e79a7"))
    fig_hist.update_layout(height=500, xaxis_title="Profit %", yaxis_title="Count")
    st.plotly_chart(fig_hist, use_container_width=True)

st.subheader("🔥 Win Rate by Confidence Band")

def confidence_band(c: float) -> str:
    if pd.isna(c):
        return "Unknown"
    if c >= 0.8:
        return "80-100%"
    if c >= 0.6:
        return "60-80%"
    return "<60%"

df_f["conf_band"] = df_f["confidence"].apply(confidence_band)
heat = df_f.groupby(["conf_band"]).apply(lambda x: (x["status"] == "win").sum() / len(x) * 100.0).reindex(["80-100%", "60-80%", "<60%", "Unknown"])  # type: ignore
st.dataframe(heat.rename("Win Rate %").to_frame().round(1))

st.subheader("🕒 Time-of-Day Performance")
df_f["hour"] = df_f["timestamp"].dt.hour
by_hour = df_f.groupby("hour").apply(lambda x: (x["status"] == "win").sum() / len(x) * 100.0)
fig_hour = go.Figure()
fig_hour.add_trace(go.Bar(x=by_hour.index.astype(str), y=by_hour.values, marker_color="#59a14f"))
fig_hour.update_layout(height=400, xaxis_title="Hour", yaxis_title="Win Rate %")
st.plotly_chart(fig_hour, use_container_width=True)

st.subheader("📊 Market Condition Performance (Simple)")
closed2 = df_f.sort_values("timestamp").copy()
if "profit_pct" in closed2.columns:
    ret = closed2["profit_pct"].fillna(0.0)
elif "profit_loss" in closed2.columns and "entry_price" in closed2.columns:
    ret = (closed2["profit_loss"] / closed2["entry_price"] * 100).fillna(0.0)
else:
    ret = pd.Series([0.0])
closed2["rolling_ret"] = ret.rolling(24, min_periods=5).sum()
threshold = st.slider("Trend threshold (profit% over 24 signals)", min_value=2.0, max_value=50.0, value=10.0, step=1.0)
closed2["market_condition"] = np.where(closed2["rolling_ret"].abs() >= threshold, "Trending", "Ranging")
mc = closed2.groupby("market_condition").apply(lambda x: (x["status"] == "win").sum() / len(x) * 100.0)
fig_mc = go.Figure()
fig_mc.add_trace(go.Bar(x=mc.index, y=mc.values, marker_color=["#f28e2c", "#e15759"]))
fig_mc.update_layout(height=400, yaxis_title="Win Rate %")
st.plotly_chart(fig_mc, use_container_width=True)
