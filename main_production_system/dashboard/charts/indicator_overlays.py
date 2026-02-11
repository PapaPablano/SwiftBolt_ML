"""
Indicator overlay renderers for KDJ and SuperTrend AI.
Uses data from core feature engineering modules (no reimplementation here).
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

try:
    from lightweight_charts import Chart
except Exception:  # pragma: no cover - import guard for environments without the package
    Chart = object  # type: ignore


class SuperTrendOverlay:
    """
    Render SuperTrend AI indicator on the main price chart.

    Column mapping (must come from existing pipeline):
    - st_band: SuperTrend band value
    - st_trend_dir: +1 for uptrend, -1 for downtrend
    - st_long_entry: bool flag for long entries
    - st_short_entry: bool flag for short entries
    """

    @staticmethod
    def add_to_chart(
        chart: Chart,
        df: pd.DataFrame,
        band_col: str = "st_band",
        trend_col: str = "st_trend_dir",
        long_entry_col: str = "st_long_entry",
        short_entry_col: str = "st_short_entry",
    ) -> Chart:
        """Add SuperTrend bands and entry markers to a chart.

        Args:
            chart: LightweightChart instance
            df: DataFrame with required SuperTrend columns and 'time'
            band_col: Column name for SuperTrend band
            trend_col: Column name for trend direction (+1/-1)
            long_entry_col: Column with long entry booleans
            short_entry_col: Column with short entry booleans
        """
        if df is None or df.empty:
            return chart

        data = df.copy()
        if "time" not in data.columns:
            if data.index.name == "time":
                data = data.reset_index()
            else:
                return chart

        if not pd.api.types.is_datetime64_any_dtype(data["time"]):
            data["time"] = pd.to_datetime(data["time"], errors="coerce")

        # Guard for required columns
        for col in (band_col, trend_col):
            if col not in data.columns:
                return chart

        # Create series split by trend direction
        data["st_band_up"] = np.where(data[trend_col] == 1, data[band_col], np.nan)
        data["st_band_down"] = np.where(data[trend_col] == -1, data[band_col], np.nan)

        # Uptrend band (green)
        try:
            line_up = chart.create_line(
                name="SuperTrend ↑",
                color="rgba(38, 166, 154, 1)",
                width=2,
                price_line=False,
            )
            line_up.set(
                data[["time", "st_band_up"]].rename(columns={"st_band_up": "value"})
            )
        except Exception:
            pass

        # Downtrend band (red)
        try:
            line_down = chart.create_line(
                name="SuperTrend ↓",
                color="rgba(239, 83, 80, 1)",
                width=2,
                price_line=False,
            )
            line_down.set(
                data[["time", "st_band_down"]].rename(columns={"st_band_down": "value"})
            )
        except Exception:
            pass

        # Entry markers
        SuperTrendOverlay._add_entry_markers(chart, data, long_entry_col, short_entry_col)
        return chart

    @staticmethod
    def _add_entry_markers(chart: Chart, df: pd.DataFrame, long_col: str, short_col: str) -> None:
        """Add marker shapes for long/short entry signals."""
        try:
            if long_col in df.columns:
                long_entries = df[df[long_col] == True]  # noqa: E712
                for _, row in long_entries.iterrows():
                    chart.marker(
                        time=row["time"],
                        position="below",
                        shape="arrow_up",
                        color="#26a69a",
                        text="LONG",
                    )

            if short_col in df.columns:
                short_entries = df[df[short_col] == True]  # noqa: E712
                for _, row in short_entries.iterrows():
                    chart.marker(
                        time=row["time"],
                        position="above",
                        shape="arrow_down",
                        color="#ef5350",
                        text="SHORT",
                    )
        except Exception:
            # Markers are non-critical; ignore rendering errors
            pass


class KDJOverlay:
    """
    Render KDJ indicator in a synchronized subchart.

    Columns expected from the feature pipeline:
    - close_kdj_k, close_kdj_d, close_kdj_j
    """

    @staticmethod
    def create_subchart(
        chart: Chart,
        df: pd.DataFrame,
        k_col: str = "close_kdj_k",
        d_col: str = "close_kdj_d",
        j_col: str = "close_kdj_j",
        height_ratio: float = 0.3,
    ) -> Chart:
        """Create and populate a KDJ subchart synchronized with the main chart."""
        if df is None or df.empty:
            return chart

        try:
            kdj_chart = chart.create_subchart(height=height_ratio, sync=True)
        except Exception:
            # If subcharts unsupported, return main chart to keep tests resilient
            return chart

        data = df.copy()
        if "time" not in data.columns:
            if data.index.name == "time":
                data = data.reset_index()
            else:
                return kdj_chart

        if not pd.api.types.is_datetime64_any_dtype(data["time"]):
            data["time"] = pd.to_datetime(data["time"], errors="coerce")

        # %K line (blue)
        if k_col in data.columns:
            try:
                k_line = kdj_chart.create_line(name="%K", color="#2962FF", width=2)
                k_line.set(data[["time", k_col]].rename(columns={k_col: "value"}))
            except Exception:
                pass

        # %D line (orange)
        if d_col in data.columns:
            try:
                d_line = kdj_chart.create_line(name="%D", color="#FF6D00", width=2)
                d_line.set(data[["time", d_col]].rename(columns={d_col: "value"}))
            except Exception:
                pass

        # %J line (purple, dotted)
        if j_col in data.columns:
            try:
                j_line = kdj_chart.create_line(name="%J", color="#AA00FF", width=1, style="dotted")
                j_line.set(data[["time", j_col]].rename(columns={j_col: "value"}))
            except Exception:
                pass

        # Reference levels
        try:
            kdj_chart.horizontal_line(100, color="rgba(255, 0, 0, 0.3)", width=1, style="dashed")
            kdj_chart.horizontal_line(80, color="rgba(255, 152, 0, 0.3)", width=1, style="dashed")
            kdj_chart.horizontal_line(20, color="rgba(76, 175, 80, 0.3)", width=1, style="dashed")
            kdj_chart.horizontal_line(0, color="rgba(0, 255, 0, 0.3)", width=1, style="dashed")
        except Exception:
            pass

        return kdj_chart


