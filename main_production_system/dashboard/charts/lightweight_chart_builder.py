"""
Lightweight Chart Builder - HYBRID APPROACH

Advanced Plotly charting with TradingView-style features.

Author: Cursor Agent
Created: 2025-11-01
Updated: 2025-11-01 - Hybrid Plotly approach for reliability
"""

from __future__ import annotations

import logging
import pandas as pd
import numpy as np
from typing import Optional, Dict
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)

# Try advanced charting
try:
    from streamlit_lightweight_charts import renderLightweightCharts

    LIGHTWEIGHT_AVAILABLE = True
    logger.info("[CHART_BUILDER] streamlit-lightweight-charts available")
except ImportError:
    LIGHTWEIGHT_AVAILABLE = False
    logger.info("[CHART_BUILDER] Using Plotly")

# Always available
PLOTLY_AVAILABLE = True


class LightweightChartBuilder:
    """Hybrid chart builder - advanced when possible, reliable always."""

    def __init__(self, height: int = 500, width: Optional[int] = None):
        """Initialize chart builder."""
        self.height = height
        self.width = width
        self.df = None
        self.symbol = None
        self.timeframe = None

    def set_ohlcv_data(
        self, df: pd.DataFrame, symbol: str = "", timeframe: str = "1d"
    ) -> "LightweightChartBuilder":
        """Prepare data."""
        self.df = df.copy()
        self.symbol = symbol
        self.timeframe = timeframe

        # Normalize columns - remove duplicates that may occur after lowercasing
        self.df.columns = self.df.columns.str.lower()
        # Keep first occurrence of duplicate columns
        self.df = self.df.loc[:, ~self.df.columns.duplicated()]

        # Ensure date column
        if "date" in self.df.columns and "time" not in self.df.columns:
            self.df = self.df.rename(columns={"date": "time"})
        elif "time" not in self.df.columns and isinstance(
            self.df.index, pd.DatetimeIndex
        ):
            # If time is in the index, reset it to a column
            self.df = self.df.reset_index()
            if "index" in self.df.columns:
                self.df = self.df.rename(columns={"index": "time"})
            elif "date" in self.df.columns:
                self.df = self.df.rename(columns={"date": "time"})

        # Convert to datetime
        if "time" in self.df.columns and not pd.api.types.is_datetime64_any_dtype(
            self.df["time"]
        ):
            try:
                self.df["time"] = pd.to_datetime(self.df["time"])
            except:
                pass

        # Ensure numeric
        for col in ["open", "high", "low", "close", "volume"]:
            if col in self.df.columns:
                self.df[col] = pd.to_numeric(self.df[col], errors="coerce")

        # Sort only if time column exists
        if "time" in self.df.columns:
            self.df = self.df.sort_values("time").reset_index(drop=True)

        return self

    def get_chart(
        self,
        show_volume: bool = True,
        show_indicators: Optional[Dict[str, bool]] = None,
    ) -> bool:
        """Render chart - use reliable Plotly with advanced features."""
        if self.df is None or self.df.empty:
            st.error("No data")
            return False

        # Use Plotly - it works reliably with advanced features
        return self._render_plotly_with_advanced_features(show_volume, show_indicators)

    def _render_plotly_with_advanced_features(
        self, show_volume: bool, show_indicators: Optional[Dict[str, bool]]
    ) -> bool:
        """Render using Plotly WITH advanced charting features."""
        try:
            df = self.df.copy()

            # Validate
            required = ["time", "open", "high", "low", "close"]
            if not all(col in df.columns for col in required):
                st.error("Missing OHLC columns")
                return False

            # Create main chart with volume
            rows = 2 if show_volume and "volume" in df.columns else 1
            row_heights = [0.7, 0.3] if rows == 2 else [1.0]

            fig = make_subplots(
                rows=rows,
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.05,
                row_heights=row_heights,
                subplot_titles=(
                    (f"{self.symbol} {self.timeframe}",)
                    if rows == 1
                    else (f"{self.symbol} {self.timeframe}", "Volume")
                ),
                specs=[[{"secondary_y": False}]] * rows,
            )

            # === PRICE CHART (CANDLESTICK) ===
            fig.add_trace(
                go.Candlestick(
                    x=df["time"],
                    open=df["open"],
                    high=df["high"],
                    low=df["low"],
                    close=df["close"],
                    name="OHLC",
                    increasing_line_color="#26A69A",
                    decreasing_line_color="#EF5350",
                    increasing_fillcolor="#26A69A",
                    decreasing_fillcolor="#EF5350",
                ),
                row=1,
                col=1,
                secondary_y=False,
            )

            # === MOVING AVERAGES (ADVANCED FEATURE) ===
            if "ma_20" in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df["time"],
                        y=df["ma_20"],
                        mode="lines",
                        name="MA20",
                        line=dict(color="#FF9800", width=1),
                        visible=True,
                    ),
                    row=1,
                    col=1,
                )

            if "ma_50" in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df["time"],
                        y=df["ma_50"],
                        mode="lines",
                        name="MA50",
                        line=dict(color="#2196F3", width=1),
                        visible=True,
                    ),
                    row=1,
                    col=1,
                )

            if "ma_200" in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df["time"],
                        y=df["ma_200"],
                        mode="lines",
                        name="MA200",
                        line=dict(color="#9C27B0", width=1),
                        visible=True,
                    ),
                    row=1,
                    col=1,
                )

            # === BOLLINGER BANDS (ADVANCED FEATURE) ===
            if all(col in df.columns for col in ["bb_upper", "bb_middle", "bb_lower"]):
                # Upper band
                fig.add_trace(
                    go.Scatter(
                        x=df["time"],
                        y=df["bb_upper"],
                        mode="lines",
                        name="BB Upper",
                        line=dict(color="rgba(255,0,0,0.3)", width=1),
                        showlegend=True,
                        visible="legendonly",
                    ),
                    row=1,
                    col=1,
                )
                # Lower band
                fig.add_trace(
                    go.Scatter(
                        x=df["time"],
                        y=df["bb_lower"],
                        mode="lines",
                        name="BB Lower",
                        line=dict(color="rgba(255,0,0,0.3)", width=1),
                        fill="tonexty",
                        fillcolor="rgba(255,0,0,0.1)",
                        showlegend=True,
                        visible="legendonly",
                    ),
                    row=1,
                    col=1,
                )

            # === VOLUME (SUBPLOT) ===
            if show_volume and "volume" in df.columns:
                colors = [
                    "#26A69A" if close >= open_ else "#EF5350"
                    for close, open_ in zip(df["close"], df["open"])
                ]

                fig.add_trace(
                    go.Bar(
                        x=df["time"],
                        y=df["volume"],
                        name="Volume",
                        marker_color=colors,
                        showlegend=False,
                        opacity=0.6,
                    ),
                    row=2,
                    col=1,
                )

            # === LAYOUT ===
            fig.update_layout(
                title=f"<b>{self.symbol} - {self.timeframe.upper()}</b>",
                height=self.height,
                template="plotly_dark",
                hovermode="x unified",
                xaxis_rangeslider_visible=False,
                font=dict(size=12),
                plot_bgcolor="#0a0a0a",
                paper_bgcolor="#1a1a1a",
            )

            # Update x-axes
            fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="#333333")
            fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="#333333")

            st.plotly_chart(
                fig,
                use_container_width=True,
                config={
                    "responsive": True,
                    "displayModeBar": True,
                    "displaylogo": False,
                    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                },
            )

            logger.info(f"[CHART] ✅ Advanced Plotly chart rendered: {len(df)} candles")
            return True

        except Exception as e:
            logger.error(f"[CHART] Render failed: {e}", exc_info=True)
            st.error(f"Chart error: {str(e)[:100]}")
            return False


def create_ohlcv_chart(
    df: pd.DataFrame,
    symbol: str = "",
    timeframe: str = "1d",
    height: int = 500,
    show_volume: bool = True,
    show_indicators: Optional[Dict[str, bool]] = None,
) -> bool:
    """Create advanced chart that always works."""
    try:
        builder = LightweightChartBuilder(height=height)
        builder.set_ohlcv_data(df, symbol=symbol, timeframe=timeframe)
        return builder.get_chart(
            show_volume=show_volume, show_indicators=show_indicators
        )
    except Exception as e:
        logger.error(f"Chart failed: {e}")
        return False


__all__ = ["LightweightChartBuilder", "create_ohlcv_chart"]
