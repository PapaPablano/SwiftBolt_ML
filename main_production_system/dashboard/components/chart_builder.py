"""
Unified chart builder utilities.

Author: Cursor Agent
Created: 2025-10-31
"""

from __future__ import annotations

# Third-party imports
import plotly.graph_objects as go
import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict


def build_price_chart(df: pd.DataFrame, title: str = "Price") -> None:
    """Render a price chart using Plotly with OHLCV support.

    Args:
        df: DataFrame containing at least 'Close' or 'close' column.
            If OHLCV columns present, renders candlestick chart.
        title: Chart title.
    """
    if df is None or df.empty:
        st.warning(f"No data available for {title}")
        return

    fig = go.Figure()

    # Detect column name variations
    date_col = None
    for col in ["Date", "date", "timestamp", "Timestamp"]:
        if col in df.columns:
            date_col = col
            break

    close_col = None
    for col in ["Close", "close"]:
        if col in df.columns:
            close_col = col
            break

    # Determine if we have OHLCV data
    has_ohlcv = all(
        col in df.columns for col in ["Open", "High", "Low", "Close"]
    ) or all(col in df.columns for col in ["open", "high", "low", "close"])

    if has_ohlcv:
        # Render candlestick chart
        open_col = "Open" if "Open" in df.columns else "open"
        high_col = "High" if "High" in df.columns else "high"
        low_col = "Low" if "Low" in df.columns else "low"
        close_col = "Close" if "Close" in df.columns else "close"

        x_axis = df[date_col] if date_col else df.index
        fig.add_trace(
            go.Candlestick(
                x=x_axis,
                open=df[open_col],
                high=df[high_col],
                low=df[low_col],
                close=df[close_col],
                name="Price",
            )
        )
    elif close_col:
        # Render line chart
        x_axis = df[date_col] if date_col else df.index
        fig.add_trace(
            go.Scatter(x=x_axis, y=df[close_col], mode="lines", name="Close")
        )
    else:
        st.warning(f"Could not find price data columns in DataFrame")
        return

    fig.update_layout(
        title=title,
        template="plotly_white",
        height=500,
        xaxis_rangeslider_visible=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def build_price_chart_figure(df: pd.DataFrame, title: str = "Price") -> go.Figure | None:
    """Build and return a price chart figure (for fallback scenarios).

    Args:
        df: DataFrame containing at least 'Close' or 'close' column.
            If OHLCV columns present, creates candlestick chart.
        title: Chart title.

    Returns:
        Plotly Figure object or None if data is invalid
    """
    if df is None or df.empty:
        return None

    fig = go.Figure()

    # Detect column name variations
    date_col = None
    for col in ["Date", "date", "timestamp", "Timestamp"]:
        if col in df.columns:
            date_col = col
            break

    close_col = None
    for col in ["Close", "close"]:
        if col in df.columns:
            close_col = col
            break

    # Determine if we have OHLCV data
    has_ohlcv = all(
        col in df.columns for col in ["Open", "High", "Low", "Close"]
    ) or all(col in df.columns for col in ["open", "high", "low", "close"])

    if has_ohlcv:
        # Render candlestick chart
        open_col = "Open" if "Open" in df.columns else "open"
        high_col = "High" if "High" in df.columns else "high"
        low_col = "Low" if "Low" in df.columns else "low"
        close_col = "Close" if "Close" in df.columns else "close"

        x_axis = df[date_col] if date_col else df.index
        fig.add_trace(
            go.Candlestick(
                x=x_axis,
                open=df[open_col],
                high=df[high_col],
                low=df[low_col],
                close=df[close_col],
                name="Price",
            )
        )
    elif close_col:
        # Render line chart
        x_axis = df[date_col] if date_col else df.index
        fig.add_trace(
            go.Scatter(x=x_axis, y=df[close_col], mode="lines", name="Close")
        )
    else:
        return None

    fig.update_layout(
        title=title,
        template="plotly_white",
        height=500,
        xaxis_rangeslider_visible=False,
    )
    return fig


def render_predictions_with_confidence(
    df_actual: pd.DataFrame,
    predictions: Dict[str, np.ndarray],
    symbol: str
) -> None:
    """
    Render price chart with prediction confidence bands.
    
    Shows:
    - Historical prices (candlesticks)
    - Point predictions (line)
    - Confidence interval (shaded region)
    
    Args:
        df_actual: DataFrame with historical OHLCV data, must include 'Date' or 'time' column
        predictions: Dictionary with keys:
            - 'predictions': Point predictions array
            - 'lower_bound': Lower confidence bound array
            - 'upper_bound': Upper confidence bound array
            - 'confidence_level': Confidence level (e.g., 0.95)
            - 'method': Method used ('bootstrap' or 'quantile')
        symbol: Stock ticker symbol for display
    """
    if df_actual is None or df_actual.empty:
        st.warning("No historical data available for chart")
        return
    
    # Detect date column
    date_col = None
    for col in ["Date", "date", "timestamp", "Timestamp", "time"]:
        if col in df_actual.columns:
            date_col = col
            break
    
    if date_col is None:
        st.warning("Could not find date column in DataFrame")
        return
    
    # Detect OHLCV columns
    open_col = None
    high_col = None
    low_col = None
    close_col = None
    
    for col in ["Open", "open"]:
        if col in df_actual.columns:
            open_col = col
            break
    
    for col in ["High", "high"]:
        if col in df_actual.columns:
            high_col = col
            break
    
    for col in ["Low", "low"]:
        if col in df_actual.columns:
            low_col = col
            break
    
    for col in ["Close", "close"]:
        if col in df_actual.columns:
            close_col = col
            break
    
    # Create figure
    fig = go.Figure()
    
    # Historical candlesticks (if OHLCV available)
    if all([open_col, high_col, low_col, close_col]):
        fig.add_trace(go.Candlestick(
            x=df_actual[date_col],
            open=df_actual[open_col],
            high=df_actual[high_col],
            low=df_actual[low_col],
            close=df_actual[close_col],
            name='Historical Price',
            increasing_line_color='#10b981',
            decreasing_line_color='#ef5350'
        ))
    elif close_col:
        # Fallback to line chart if no OHLCV
        fig.add_trace(go.Scatter(
            x=df_actual[date_col],
            y=df_actual[close_col],
            mode='lines',
            name='Historical Price',
            line=dict(color='#3b82f6', width=2)
        ))
    else:
        st.warning("Could not find price data columns in DataFrame")
        return
    
    # Prediction data
    pred_values = predictions.get('predictions', np.array([]))
    lower_bound = predictions.get('lower_bound', np.array([]))
    upper_bound = predictions.get('upper_bound', np.array([]))
    confidence_level = predictions.get('confidence_level', 0.95)
    method = predictions.get('method', 'bootstrap')
    
    if len(pred_values) == 0:
        st.warning("No prediction data available")
        st.plotly_chart(fig, use_container_width=True)
        return
    
    # Align predictions with historical data timeline
    # Predictions start from the end of historical data
    n_predictions = len(pred_values)
    n_historical = len(df_actual)
    
    # Get last date from historical data
    last_date = pd.to_datetime(df_actual[date_col].iloc[-1])
    
    # Create date range for predictions
    # If we don't have a clear interval, use daily frequency
    try:
        # Try to infer frequency from historical data
        if n_historical > 1:
            date_diff = pd.to_datetime(df_actual[date_col].iloc[-1]) - pd.to_datetime(df_actual[date_col].iloc[-2])
            freq = date_diff
        else:
            freq = pd.Timedelta(days=1)
    except:
        freq = pd.Timedelta(days=1)
    
    pred_dates = pd.date_range(start=last_date + freq, periods=n_predictions, freq=freq)
    
    # Prediction line
    fig.add_trace(go.Scatter(
        x=pred_dates,
        y=pred_values,
        mode='lines',
        name='Prediction',
        line=dict(color='#00C853', width=3)
    ))
    
    # Confidence interval (shaded region)
    if len(lower_bound) > 0 and len(upper_bound) > 0:
        # Upper bound (invisible line for fill)
        fig.add_trace(go.Scatter(
            x=pred_dates,
            y=upper_bound,
            mode='lines',
            name=f"{confidence_level:.0%} CI Upper",
            line=dict(width=0),
            showlegend=False,
            hoverinfo='skip'
        ))
        
        # Lower bound with fill
        fig.add_trace(go.Scatter(
            x=pred_dates,
            y=lower_bound,
            mode='lines',
            name=f"{confidence_level:.0%} Confidence Interval",
            line=dict(width=0),
            fillcolor='rgba(0, 200, 83, 0.2)',
            fill='tonexty',
            showlegend=True,
            hovertemplate=f'Lower Bound: $%{{y:.2f}}<extra></extra>'
        ))
    
    # Update layout
    confidence_pct = confidence_level * 100
    
    # Detect theme (handle potential errors)
    try:
        theme = st.get_option('theme.base')
        template = 'plotly_dark' if theme == 'dark' else 'plotly_white'
    except:
        template = 'plotly_white'  # Default to white theme
    
    fig.update_layout(
        title=f"{symbol} Price Predictions with {confidence_pct:.0f}% Confidence Interval",
        xaxis_title="Date",
        yaxis_title="Price ($)",
        height=600,
        hovermode='x unified',
        template=template,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Confidence metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if len(upper_bound) > 0 and len(lower_bound) > 0:
            avg_width = np.mean(upper_bound - lower_bound)
            st.metric("Avg CI Width", f"${avg_width:.2f}")
        else:
            st.metric("Avg CI Width", "N/A")
    
    with col2:
        std_values = predictions.get('std', np.array([]))
        if len(std_values) > 0:
            avg_std = np.mean(std_values)
            st.metric("Avg Std Dev", f"${avg_std:.2f}")
        else:
            st.metric("Avg Std Dev", "N/A")
    
    with col3:
        st.metric("Method", method.capitalize())


