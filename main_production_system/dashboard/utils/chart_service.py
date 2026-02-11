"""
Unified Chart Service - Professional TradingView-Style Charts

Handles all trading chart rendering with automatic fallback
Features:
- TradingView-style rendering with streamlit-lightweight-charts-pro
- Multiple Moving Averages (MA20, MA50, MA200)
- Bollinger Bands overlay
- RSI subplot with overbought/oversold zones
- MACD subplot with histogram
- Volume panels, trade signals/flags
- Multi-symbol comparison support
- Robust error handling and data validation
- Uniform theming (backgrounds, grids, colors, fonts)
- Crosshair, zoom, and annotation layers
- Configurable indicator overlays via indicators dict
"""

import streamlit as st
import pandas as pd
import numpy as np
import logging
import traceback
from typing import Tuple, Optional, Dict, List, Any, Union
from datetime import datetime

logger = logging.getLogger(__name__)

# Import chart libraries - try pro version first
try:
    from streamlit_lightweight_charts import renderLightweightCharts

    try:
        # Check if pro version is available (may have additional features)
        LIGHTWEIGHT_AVAILABLE = True
        LIGHTWEIGHT_PRO = False
        logger.info("[CHART_SERVICE] ✅ streamlit-lightweight-charts available")
    except:
        LIGHTWEIGHT_AVAILABLE = False
        LIGHTWEIGHT_PRO = False
        logger.warning("[CHART_SERVICE] ⚠️ streamlit-lightweight-charts not available")
except ImportError:
    LIGHTWEIGHT_AVAILABLE = False
    LIGHTWEIGHT_PRO = False
    logger.warning(
        "[CHART_SERVICE] ⚠️ streamlit-lightweight-charts not available, will use Plotly"
    )

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import plotly.express as px

    PLOTLY_AVAILABLE = True
    logger.info("[CHART_SERVICE] ✅ Plotly available")
except ImportError:
    PLOTLY_AVAILABLE = False
    logger.error("[CHART_SERVICE] ❌ Neither lightweight-charts nor Plotly available!")

# Optional TA-Lib for ATR/SuperTrend
try:
    import talib

    TALIB_AVAILABLE = True
except Exception:
    TALIB_AVAILABLE = False
    logger.warning(
        "[CHART_SERVICE] ⚠️ TA-Lib not available, using numpy fallback for ATR"
    )

# SuperTrend AI with K-Means clustering
try:
    from main_production_system.core.supertrend_ai import SuperTrendAI

    SUPERTREND_AI_AVAILABLE = True
    logger.info("[CHART_SERVICE] ✅ SuperTrend AI available")
except Exception as e:
    SUPERTREND_AI_AVAILABLE = False
    logger.warning(f"[CHART_SERVICE] ⚠️ SuperTrend AI not available: {e}")


def generate_stylized_predictions(
    df_raw: pd.DataFrame,
    features: pd.DataFrame,
    predictions: Union[pd.Series, np.ndarray, List[float]],
    ignored_rows: int = 50,
    actuals: Optional[Union[pd.Series, np.ndarray]] = None,
    bootstrap_ci: bool = True,
    n_bootstrap: int = 100,
    confidence_level: float = 0.95,
) -> "go.Figure":
    """
    Create a two-row Plotly figure with bootstrap confidence intervals:
    - Row 1: Actual close vs predictions, with shaded warm-up period and empirical confidence band
    - Row 2: Feature NaN heatmap overview (loads latest report if available)

    Args:
        df_raw: Original OHLCV with a 'close' column and datetime index
        features: Engineered features DataFrame (for optional context)
        predictions: Array-like predictions aligned to df_raw.index[ignored_rows:]
        ignored_rows: Warm-up rows ignored for rolling features
        actuals: Actual values for residual-based bootstrap (if None, uses df_raw['close'])
        bootstrap_ci: Use bootstrap for empirical confidence intervals (default: True)
        n_bootstrap: Number of bootstrap samples (default: 100)
        confidence_level: Confidence level for intervals (default: 0.95)
    """
    if not PLOTLY_AVAILABLE:
        raise RuntimeError("Plotly is required for generate_stylized_predictions")

    # Normalize inputs
    d = df_raw.copy()
    if "close" not in d.columns:
        # try lower-case conversion
        d.columns = [str(c).lower() for c in d.columns]
    if "close" not in d.columns:
        raise ValueError("df_raw must contain a 'close' column")

    x_all = d.index
    x_use = x_all[ignored_rows:]
    preds = np.asarray(predictions, dtype=float)
    if len(preds) != len(x_use):
        # Best effort: align to min length
        n = min(len(preds), len(x_use))
        preds = preds[-n:]
        x_use = x_use[-n:]

    # Get actuals for residual calculation
    if actuals is None:
        actuals_array = d["close"].iloc[ignored_rows:].values[: len(preds)]
    else:
        actuals_array = np.asarray(actuals, dtype=float)[: len(preds)]

    # === BOOTSTRAP CONFIDENCE INTERVALS ===
    if bootstrap_ci and len(actuals_array) == len(preds):
        residuals = actuals_array - preds

        # Resample residuals and compute percentiles
        bootstrap_preds = []
        rng = np.random.RandomState(42)

        for _ in range(n_bootstrap):
            # Bootstrap: resample residuals with replacement
            resampled_residuals = rng.choice(
                residuals, size=len(residuals), replace=True
            )
            bootstrap_pred = preds + resampled_residuals
            bootstrap_preds.append(bootstrap_pred)

        bootstrap_preds = np.array(bootstrap_preds)

        # Compute empirical percentiles (e.g., 2.5% and 97.5% for 95% CI)
        alpha = 1 - confidence_level
        lower_percentile = (alpha / 2) * 100
        upper_percentile = (1 - alpha / 2) * 100

        lower = np.percentile(bootstrap_preds, lower_percentile, axis=0)
        upper = np.percentile(bootstrap_preds, upper_percentile, axis=0)

        logger.info(
            f"[CHART] Bootstrap CI computed: {n_bootstrap} samples, "
            f"{confidence_level:.0%} interval (percentiles: {lower_percentile:.1f}-{upper_percentile:.1f})"
        )
    else:
        # Fallback: simple heuristic based on prediction variability
        pred_std = float(np.std(preds)) if len(preds) > 1 else 0.0
        band = max(1e-8, pred_std * 0.5)
        lower = preds - band
        upper = preds + band
        logger.debug(
            "[CHART] Using simple confidence band (bootstrap disabled or data mismatch)"
        )

    # Build subplots
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        subplot_titles=(
            "Price & Predictions (Bootstrap 95% CI)",
            "NaN Report Overview",
        ),
        vertical_spacing=0.06,
        row_heights=[0.7, 0.3],
    )

    # Row 1: Actual price
    fig.add_trace(
        go.Scatter(
            x=x_all[ignored_rows:][: len(preds)],
            y=actuals_array,
            name="Actual Close",
            line=dict(color="blue", width=2),
        ),
        row=1,
        col=1,
    )

    # Row 1: Predictions
    fig.add_trace(
        go.Scatter(
            x=x_use,
            y=preds,
            name="Predictions",
            line=dict(color="red", dash="dash", width=2),
        ),
        row=1,
        col=1,
    )

    # Row 1: Confidence band as filled region (bootstrap or fallback)
    fig.add_trace(
        go.Scatter(
            x=np.concatenate([x_use, x_use[::-1]]),
            y=np.concatenate([upper, lower[::-1]]),
            fill="toself",
            fillcolor="rgba(255,0,0,0.15)",
            line=dict(color="rgba(255,0,0,0)"),
            name=(
                f"{confidence_level:.0%} CI (Bootstrap)"
                if bootstrap_ci
                else "Confidence Band"
            ),
        ),
        row=1,
        col=1,
    )

    # Shade ignored warm-up period (vertical rectangle)
    try:
        fig.add_vrect(
            x0=x_all[0],
            x1=x_all[min(ignored_rows, len(x_all) - 1)],
            fillcolor="lightgray",
            opacity=0.3,
            line_width=0,
        )
        fig.add_annotation(
            text="Warm-up (Ignored)",
            x=x_all[min(ignored_rows // 2, len(x_all) - 1)],
            y=float(np.nanmax(d["close"])),
            showarrow=False,
        )
    except Exception:
        pass

    # Row 2: NaN report heatmap based on latest CSV summary (percentages)
    try:
        from pathlib import Path
        import pandas as pd

        report_dir = Path("outputs/nan_reports")
        latest_csv = None
        if report_dir.exists():
            csvs = sorted(report_dir.glob("nan_summary_*.csv"))
            if csvs:
                latest_csv = csvs[-1]
        if latest_csv:
            rep = pd.read_csv(latest_csv, index_col=0)
            # Extract numeric percent values
            pct = rep["NaN %"].str.replace("%", "", regex=False).astype(float)
            heat_df = pd.DataFrame({"feature": rep.index, "nan_pct": pct}).sort_values(
                "nan_pct", ascending=False
            )
            fig.add_trace(
                go.Bar(
                    x=heat_df["feature"],
                    y=heat_df["nan_pct"],
                    name="NaN % by feature",
                    marker_color="orange",
                ),
                row=2,
                col=1,
            )
            fig.update_yaxes(title_text="NaN %", row=2, col=1)
    except Exception as e:
        logger.debug(f"[CHART_SERVICE] NaN report subplot skipped: {e}")

    fig.update_layout(
        title="Prediction Accuracy Review - Maximized Data Usage",
        height=800,
        template="plotly_dark",
    )
    return fig


def normalize_ohlcv_data(df: pd.DataFrame) -> Tuple[pd.DataFrame, bool]:
    """
    ENHANCED: Normalize OHLCV data with robust datetime handling.

    NEW FEATURES:
    - Unix timestamp detection and conversion
    - Timezone-aware datetime handling
    - Intraday vs daily format detection
    - Data type validation with coercion

    Returns:
        (normalized_df, is_valid)
    """
    try:
        df_norm = df.copy()

        if df_norm.empty:
            logger.error("[NORMALIZE] Empty DataFrame")
            return df_norm, False

        # === STEP 1: Standardize column names ===
        df_norm.columns = df_norm.columns.str.lower()

        # === STEP 2: Handle time column (critical fix) ===
        time_cols = [
            col
            for col in df_norm.columns
            if col in ["date", "timestamp", "datetime", "time"]
        ]

        if time_cols:
            df_norm = df_norm.rename(columns={time_cols[0]: "time"})
        elif "time" not in df_norm.columns:
            # Check if index is datetime
            if pd.api.types.is_datetime64_any_dtype(df_norm.index):
                df_norm["time"] = df_norm.index
                logger.debug("[NORMALIZE] Extracted time from index")
            else:
                logger.error("[NORMALIZE] No time column found")
                return df_norm, False

        # === STEP 3: Validate required OHLCV columns ===
        required = ["time", "open", "high", "low", "close", "volume"]
        missing = [col for col in required if col not in df_norm.columns]

        if missing:
            logger.error(f"[NORMALIZE] Missing columns: {missing}")
            return df_norm, False

        # === STEP 4: Convert OHLCV to numeric (coerce errors) ===
        for col in ["open", "high", "low", "close", "volume"]:
            df_norm[col] = pd.to_numeric(df_norm[col], errors="coerce")

        # === STEP 5: ROBUST DATETIME CONVERSION ===
        try:
            # Check if already datetime
            if pd.api.types.is_datetime64_any_dtype(df_norm["time"]):
                logger.debug("[NORMALIZE] Time already datetime format")

            # Check if Unix timestamp (seconds or milliseconds)
            elif pd.api.types.is_numeric_dtype(df_norm["time"]):
                sample_val = df_norm["time"].iloc[0]

                # If value > 1e10, likely milliseconds
                if sample_val > 1e10:
                    df_norm["time"] = pd.to_datetime(df_norm["time"], unit="ms")
                    logger.debug("[NORMALIZE] Converted from Unix milliseconds")
                else:
                    df_norm["time"] = pd.to_datetime(df_norm["time"], unit="s")
                    logger.debug("[NORMALIZE] Converted from Unix seconds")

            # String format - let pandas infer
            else:
                df_norm["time"] = pd.to_datetime(df_norm["time"], errors="coerce")
                logger.debug("[NORMALIZE] Converted from string format")

            # Check for NaT (Not a Time) values
            if df_norm["time"].isna().any():
                nat_count = df_norm["time"].isna().sum()
                logger.warning(
                    f"[NORMALIZE] {nat_count} NaT values in time column - dropping"
                )
                df_norm = df_norm.dropna(subset=["time"])

        except Exception as e:
            logger.error(f"[NORMALIZE] Datetime conversion failed: {e}")
            return df_norm, False

        # === STEP 6: Check for NaN in critical OHLCV columns ===
        nan_rows = df_norm[required].isna().any(axis=1).sum()

        if nan_rows > 0:
            logger.warning(
                f"[NORMALIZE] Dropping {nan_rows} rows with NaN in OHLCV columns"
            )
            df_norm = df_norm.dropna(subset=["open", "high", "low", "close"])

        # === STEP 7: Sort by time ===
        df_norm = df_norm.sort_values("time").reset_index(drop=True)

        logger.info(f"[NORMALIZE] ✅ Normalized {len(df_norm)} rows")
        return df_norm, True

    except Exception as e:
        logger.error(f"[NORMALIZE] Fatal error: {e}\n{traceback.format_exc()}")
        return df, False


def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    ENHANCED: Calculate technical indicators for chart overlays.

    Adds:
    - MA20, MA50, MA200 (Moving Averages)
    - Bollinger Bands (upper, middle, lower)
    - RSI (14-period)
    - MACD (12, 26, 9)

    Args:
        df: Normalized DataFrame with OHLCV data

    Returns:
        DataFrame with additional indicator columns
    """
    try:
        df_ind = df.copy()

        # Ensure we have close prices
        if "close" not in df_ind.columns:
            logger.error("[INDICATORS] Missing 'close' column")
            return df_ind
        # Cast to numeric to avoid dtype object comparisons
        df_ind["close"] = pd.to_numeric(df_ind["close"], errors="coerce")

        # === MOVING AVERAGES ===
        df_ind["ma20"] = df_ind["close"].rolling(window=20, min_periods=1).mean()
        df_ind["ma50"] = df_ind["close"].rolling(window=50, min_periods=1).mean()
        df_ind["ma200"] = df_ind["close"].rolling(window=200, min_periods=1).mean()

        # === BOLLINGER BANDS ===
        bb_period = 20
        bb_std = 2.0
        df_ind["bb_middle"] = (
            df_ind["close"].rolling(window=bb_period, min_periods=1).mean()
        )
        df_ind["bb_std"] = (
            df_ind["close"].rolling(window=bb_period, min_periods=1).std()
        )
        df_ind["bb_upper"] = df_ind["bb_middle"] + (df_ind["bb_std"] * bb_std)
        df_ind["bb_lower"] = df_ind["bb_middle"] - (df_ind["bb_std"] * bb_std)

        # === RSI (14-period) ===
        delta = df_ind["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
        rs = gain / loss
        df_ind["rsi_14"] = 100 - (100 / (1 + rs))

        # === MACD (12, 26, 9) ===
        ema12 = df_ind["close"].ewm(span=12, adjust=False).mean()
        ema26 = df_ind["close"].ewm(span=26, adjust=False).mean()
        df_ind["macd"] = ema12 - ema26
        df_ind["macd_signal"] = df_ind["macd"].ewm(span=9, adjust=False).mean()
        df_ind["macd_hist"] = df_ind["macd"] - df_ind["macd_signal"]

        # Fill NaN values with forward/backward fill for better visualization
        for col in ["ma20", "ma50", "ma200", "bb_upper", "bb_lower", "bb_middle"]:
            df_ind[col] = df_ind[col].bfill().ffill().fillna(df_ind["close"])

        for col in ["rsi_14"]:
            df_ind[col] = df_ind[col].bfill().ffill().fillna(50.0)

        for col in ["macd", "macd_signal", "macd_hist"]:
            df_ind[col] = df_ind[col].bfill().ffill().fillna(0.0)

        logger.info(
            "[INDICATORS] ✅ Enhanced technical indicators calculated (MA20/50/200, BB, RSI, MACD)"
        )
        return df_ind

    except Exception as e:
        logger.error(f"[INDICATORS] Failed: {e}\n{traceback.format_exc()}")
        return df


def render_lightweight_chart(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    show_volume: bool = True,
    show_indicators: bool = True,
    show_signals: bool = False,
    indicators: Optional[Dict] = None,
) -> bool:
    """
    ENHANCED: Render professional TradingView-style chart using streamlit-lightweight-charts.

    NEW FEATURES:
    - TradingView-style chart with configurable indicators
    - Bollinger Bands overlay
    - Multiple MA overlays (20, 50, 200)
    - RSI subplot with overbought/oversold zones
    - MACD subplot with histogram
    - Volume profile
    - Trade signals (buy/sell flags)

    Args:
        df: DataFrame with OHLCV data
        symbol: Stock symbol
        timeframe: Time interval (e.g., '1d', '4h')
        show_volume: Show volume panel
        show_indicators: Calculate and show indicators
        show_signals: Show trade signals
        indicators: Dict of indicator configs (e.g., {'bollinger_bands': True, 'rsi': True})
    """

    if not LIGHTWEIGHT_AVAILABLE:
        logger.warning("[LIGHTWEIGHT] Library not available")
        return False

    # Default indicators config
    if indicators is None:
        indicators = {}

    try:
        logger.info(
            f"[LIGHTWEIGHT] Rendering {symbol} {timeframe} with indicators={show_indicators}"
        )

        df_chart = df.copy()

        # Calculate technical indicators if requested
        if show_indicators:
            df_chart = calculate_technical_indicators(df_chart)

        # Convert time to string format (YYYY-MM-DD for daily, with time for intraday)
        # Check if intraday data (has time component) or daily (date only)
        if (
            df_chart["time"].dt.hour.max() == 0
            and df_chart["time"].dt.minute.max() == 0
        ):
            # Daily data - format as YYYY-MM-DD
            df_chart["time"] = df_chart["time"].dt.strftime("%Y-%m-%d")
        else:
            # Intraday data - format as YYYY-MM-DD HH:MM:SS then truncate to date for compatibility
            df_chart["time"] = df_chart["time"].dt.strftime("%Y-%m-%d")

        # Color candles based on price direction
        df_chart["color"] = np.where(
            df_chart["close"] >= df_chart["open"],
            "rgba(38,166,154,0.9)",  # Green for up candles
            "rgba(239,83,80,0.9)",  # Red for down candles
        )

        # Create candles data
        candles = []
        for _, row in df_chart.iterrows():
            candle = {
                "time": row["time"],
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "color": row["color"],
            }
            candles.append(candle)

        # Professional chart configuration with uniform theming
        chart_options = {
            "height": 600,
            "layout": {
                "background": {"type": "solid", "color": "#131722"},  # Dark background
                "textColor": "#d1d4dc",  # Light text
            },
            "grid": {
                "vertLines": {"color": "rgba(42, 46, 57, 0.5)", "style": 0},
                "horzLines": {"color": "rgba(42, 46, 57, 0.5)", "style": 0},
            },
            "crosshair": {
                "mode": 1,  # Normal crosshair
                "vertLine": {
                    "color": "#758696",
                    "width": 1,
                    "style": 2,  # Dashed
                    "labelBackgroundColor": "#131722",
                },
                "horzLine": {
                    "color": "#758696",
                    "width": 1,
                    "style": 2,  # Dashed
                    "labelBackgroundColor": "#131722",
                },
            },
            "watermark": {
                "visible": True,
                "fontSize": 48,
                "horzAlign": "center",
                "vertAlign": "center",
                "color": "rgba(255, 255, 255, 0.08)",
                "text": f"{symbol} • {timeframe.upper()}",
            },
            "timeScale": {
                "timeVisible": True,
                "secondsVisible": False,
                "rightOffset": 12,
                "barSpacing": 6,
                "fixLeftEdge": False,
                "lockVisibleTimeRangeOnResize": False,
                "rightBarStaysOnScroll": False,
                "borderVisible": True,
                "borderColor": "rgba(42, 46, 57, 0.8)",
                "visible": True,
                "ticksVisible": True,
            },
            "rightPriceScale": {
                "visible": True,
                "borderColor": "rgba(42, 46, 57, 0.8)",
                "scaleMargins": {"top": 0.1, "bottom": 0.2},
            },
        }

        # Price series - candlestick
        series = [
            {
                "type": "Candlestick",
                "data": candles,
                "options": {
                    "upColor": "rgba(38,166,154,0.9)",  # Green
                    "downColor": "rgba(239,83,80,0.9)",  # Red
                    "borderUpColor": "rgba(38,166,154,1.0)",
                    "borderDownColor": "rgba(239,83,80,1.0)",
                    "wickUpColor": "rgba(38,166,154,0.9)",
                    "wickDownColor": "rgba(239,83,80,0.9)",
                    "borderVisible": True,
                },
                "name": "Price",
            }
        ]

        # Add technical indicator overlays
        if show_indicators:
            # MA20 - Simple Moving Average 20
            if "ma20" in df_chart.columns:
                ma20_data = [
                    {
                        "time": row["time"],
                        "value": (
                            float(row["ma20"]) if not pd.isna(row["ma20"]) else None
                        ),
                    }
                    for _, row in df_chart.iterrows()
                    if not pd.isna(row["ma20"])
                ]

                if ma20_data:
                    series.append(
                        {
                            "type": "Line",
                            "data": ma20_data,
                            "options": {
                                "color": "#ff9800",  # Orange
                                "lineWidth": 2,
                                "priceLineVisible": False,
                                "lastValueVisible": True,
                                "crosshairMarkerVisible": True,
                                "crosshairMarkerRadius": 4,
                            },
                            "name": "MA20",
                        }
                    )

            # MA50 - Simple Moving Average 50
            if "ma50" in df_chart.columns:
                ma50_data = [
                    {
                        "time": row["time"],
                        "value": (
                            float(row["ma50"]) if not pd.isna(row["ma50"]) else None
                        ),
                    }
                    for _, row in df_chart.iterrows()
                    if not pd.isna(row["ma50"])
                ]

                if ma50_data:
                    series.append(
                        {
                            "type": "Line",
                            "data": ma50_data,
                            "options": {
                                "color": "#2196f3",  # Blue
                                "lineWidth": 2,
                                "priceLineVisible": False,
                                "lastValueVisible": True,
                                "crosshairMarkerVisible": True,
                                "crosshairMarkerRadius": 4,
                            },
                            "name": "MA50",
                        }
                    )

            # MA200 - Simple Moving Average 200
            if "ma200" in df_chart.columns:
                ma200_data = [
                    {
                        "time": row["time"],
                        "value": (
                            float(row["ma200"]) if not pd.isna(row["ma200"]) else None
                        ),
                    }
                    for _, row in df_chart.iterrows()
                    if not pd.isna(row["ma200"])
                ]

                if ma200_data:
                    series.append(
                        {
                            "type": "Line",
                            "data": ma200_data,
                            "options": {
                                "color": "rgba(233, 30, 99, 0.8)",  # Pink
                                "lineWidth": 2,
                                "priceLineVisible": False,
                                "lastValueVisible": True,
                                "crosshairMarkerVisible": True,
                                "crosshairMarkerRadius": 4,
                            },
                            "name": "MA200",
                        }
                    )

            # Bollinger Bands
            if all(
                col in df_chart.columns for col in ["bb_upper", "bb_lower", "bb_middle"]
            ):
                # Upper band
                bb_upper_data = [
                    {
                        "time": row["time"],
                        "value": (
                            float(row["bb_upper"])
                            if not pd.isna(row["bb_upper"])
                            else None
                        ),
                    }
                    for _, row in df_chart.iterrows()
                    if not pd.isna(row["bb_upper"])
                ]

                # Lower band
                bb_lower_data = [
                    {
                        "time": row["time"],
                        "value": (
                            float(row["bb_lower"])
                            if not pd.isna(row["bb_lower"])
                            else None
                        ),
                    }
                    for _, row in df_chart.iterrows()
                    if not pd.isna(row["bb_lower"])
                ]

                # Middle band (SMA)
                bb_middle_data = [
                    {
                        "time": row["time"],
                        "value": (
                            float(row["bb_middle"])
                            if not pd.isna(row["bb_middle"])
                            else None
                        ),
                    }
                    for _, row in df_chart.iterrows()
                    if not pd.isna(row["bb_middle"])
                ]

                if bb_upper_data and bb_lower_data:
                    # Upper band line
                    series.append(
                        {
                            "type": "Line",
                            "data": bb_upper_data,
                            "options": {
                                "color": "rgba(156, 39, 176, 0.6)",  # Purple
                                "lineWidth": 1,
                                "lineStyle": 2,  # Dashed
                                "priceLineVisible": False,
                            },
                            "name": "BB Upper",
                        }
                    )

                    # Lower band line
                    series.append(
                        {
                            "type": "Line",
                            "data": bb_lower_data,
                            "options": {
                                "color": "rgba(156, 39, 176, 0.6)",  # Purple
                                "lineWidth": 1,
                                "lineStyle": 2,  # Dashed
                                "priceLineVisible": False,
                            },
                            "name": "BB Lower",
                        }
                    )

                    # Middle band line
                    if bb_middle_data:
                        series.append(
                            {
                                "type": "Line",
                                "data": bb_middle_data,
                                "options": {
                                    "color": "rgba(156, 39, 176, 0.4)",  # Lighter purple
                                    "lineWidth": 1,
                                    "lineStyle": 1,  # Solid
                                    "priceLineVisible": False,
                                },
                                "name": "BB Middle",
                            }
                        )

        # === TRADE SIGNALS (Buy/Sell Flags) ===
        if show_signals and "signal" in df_chart.columns:
            buy_signals = []
            sell_signals = []

            for _, row in df_chart.iterrows():
                signal = row.get("signal", 0)
                if signal == 1:  # Buy signal
                    buy_signals.append(
                        {
                            "time": row["time"],
                            "position": "belowBar",
                            "color": "#00C853",
                            "shape": "arrowUp",
                            "text": "BUY",
                        }
                    )
                elif signal == -1:  # Sell signal
                    sell_signals.append(
                        {
                            "time": row["time"],
                            "position": "aboveBar",
                            "color": "#FF1744",
                            "shape": "arrowDown",
                            "text": "SELL",
                        }
                    )

            # Add markers to candlestick series
            if buy_signals or sell_signals:
                series[0]["markers"] = buy_signals + sell_signals

        configs = [{"chart": chart_options, "series": series}]

        # Volume series (if requested) - Mini volume panel
        if show_volume and "volume" in df_chart.columns:
            volume_data = []
            for _, row in df_chart.iterrows():
                if not pd.isna(row["volume"]):
                    volume_data.append(
                        {
                            "time": row["time"],
                            "value": float(row["volume"]),
                            "color": row["color"],  # Use same color as candles
                        }
                    )

            if volume_data:
                vol_config = {
                    "height": 120,  # Mini volume panel
                    "layout": {
                        "background": {
                            "type": "solid",
                            "color": "#0a0e27",
                        },  # Darker background
                        "textColor": "#d1d4dc",
                    },
                    "grid": {
                        "vertLines": {"visible": False},
                        "horzLines": {"visible": False},
                    },
                    "timeScale": {
                        "visible": False,  # Hide time scale on volume panel
                        "timeVisible": False,
                    },
                    "rightPriceScale": {"visible": False},  # Hide price scale on volume
                }

                vol_series = [
                    {
                        "type": "Histogram",
                        "data": volume_data,
                        "options": {
                            "color": "rgba(38,166,154,0.6)",  # Semi-transparent green
                            "priceFormat": {"type": "volume"},
                            "priceScaleId": "",  # Use separate scale
                            "scaleMargins": {"top": 0.8, "bottom": 0},
                        },
                        "name": "Volume",
                    }
                ]

                configs.append({"chart": vol_config, "series": vol_series})

        # === RSI SUBPLOT ===
        if indicators and indicators.get("rsi", False) and "rsi_14" in df_chart.columns:
            rsi_data = [
                {
                    "time": row["time"],
                    "value": (
                        float(row["rsi_14"]) if not pd.isna(row["rsi_14"]) else None
                    ),
                }
                for _, row in df_chart.iterrows()
                if not pd.isna(row["rsi_14"])
            ]

            if rsi_data:
                rsi_config = {
                    "height": 100,
                    "layout": {
                        "background": {"type": "solid", "color": "#0a0e27"},
                        "textColor": "#d1d4dc",
                    },
                    "grid": {
                        "vertLines": {"visible": False},
                        "horzLines": {"visible": False},
                    },
                    "timeScale": {"visible": False},
                    "rightPriceScale": {
                        "visible": True,
                        "scaleMargins": {"top": 0.1, "bottom": 0.1},
                    },
                }

                rsi_series = [
                    {
                        "type": "Line",
                        "data": rsi_data,
                        "options": {"color": "rgba(255, 235, 59, 0.9)", "lineWidth": 2},
                        "name": "RSI",
                    },
                    # Overbought line (70)
                    {
                        "type": "Line",
                        "data": [
                            {"time": row["time"], "value": 70}
                            for _, row in df_chart.iterrows()
                        ],
                        "options": {
                            "color": "rgba(255, 82, 82, 0.3)",
                            "lineWidth": 1,
                            "lineStyle": 2,
                        },
                        "name": "Overbought",
                    },
                    # Oversold line (30)
                    {
                        "type": "Line",
                        "data": [
                            {"time": row["time"], "value": 30}
                            for _, row in df_chart.iterrows()
                        ],
                        "options": {
                            "color": "rgba(76, 175, 80, 0.3)",
                            "lineWidth": 1,
                            "lineStyle": 2,
                        },
                        "name": "Oversold",
                    },
                ]

                configs.append({"chart": rsi_config, "series": rsi_series})

        # === MACD SUBPLOT ===
        if (
            indicators
            and indicators.get("macd", False)
            and all(
                col in df_chart.columns for col in ["macd", "macd_signal", "macd_hist"]
            )
        ):
            macd_data = [
                {
                    "time": row["time"],
                    "value": float(row["macd"]) if not pd.isna(row["macd"]) else None,
                }
                for _, row in df_chart.iterrows()
                if not pd.isna(row["macd"])
            ]

            macd_signal_data = [
                {
                    "time": row["time"],
                    "value": (
                        float(row["macd_signal"])
                        if not pd.isna(row["macd_signal"])
                        else None
                    ),
                }
                for _, row in df_chart.iterrows()
                if not pd.isna(row["macd_signal"])
            ]

            macd_hist_data = []
            for _, row in df_chart.iterrows():
                if not pd.isna(row["macd_hist"]):
                    macd_hist_data.append(
                        {
                            "time": row["time"],
                            "value": float(row["macd_hist"]),
                            "color": (
                                "rgba(38,166,154,0.6)"
                                if row["macd_hist"] >= 0
                                else "rgba(239,83,80,0.6)"
                            ),
                        }
                    )

            if macd_data and macd_signal_data:
                macd_config = {
                    "height": 100,
                    "layout": {
                        "background": {"type": "solid", "color": "#0a0e27"},
                        "textColor": "#d1d4dc",
                    },
                    "grid": {
                        "vertLines": {"visible": False},
                        "horzLines": {"visible": False},
                    },
                    "timeScale": {"visible": False},
                    "rightPriceScale": {
                        "visible": True,
                        "scaleMargins": {"top": 0.1, "bottom": 0.1},
                    },
                }

                macd_series = [
                    {
                        "type": "Line",
                        "data": macd_data,
                        "options": {"color": "rgba(33, 150, 243, 0.9)", "lineWidth": 2},
                        "name": "MACD",
                    },
                    {
                        "type": "Line",
                        "data": macd_signal_data,
                        "options": {"color": "rgba(255, 152, 0, 0.9)", "lineWidth": 1},
                        "name": "Signal",
                    },
                ]

                if macd_hist_data:
                    macd_series.append(
                        {
                            "type": "Histogram",
                            "data": macd_hist_data,
                            "options": {"color": "rgba(38,166,154,0.6)"},
                            "name": "Histogram",
                        }
                    )

                configs.append({"chart": macd_config, "series": macd_series})

        # Render
        renderLightweightCharts(configs, f"chart_{symbol}_{timeframe}")
        logger.info(
            f"[LIGHTWEIGHT] ✅ Chart rendered with {len(series)} series, {len(configs)} panels"
        )
        return True

    except Exception as e:
        logger.error(f"[LIGHTWEIGHT] Render failed: {e}\n{traceback.format_exc()}")
        return False


def render_plotly_chart(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    show_volume: bool = True,
    show_indicators: bool = True,
    show_signals: bool = False,
) -> bool:
    """
    Render professional TradingView-style chart using Plotly (fallback).

    Features:
    - Robust error handling for missing columns and NaN values
    - MA20/MA50 overlays
    - Bollinger Bands overlay
    - Volume subplot
    - Trade signals/flags
    - Uniform theming
    """

    if not PLOTLY_AVAILABLE:
        logger.error("[PLOTLY] Plotly not available")
        return False

    try:
        logger.info(
            f"[PLOTLY] Rendering {symbol} {timeframe} (fallback) with indicators={show_indicators}"
        )

        df_chart = df.copy()

        # Validate required columns with error handling
        required_cols = ["time", "open", "high", "low", "close"]
        missing_cols = [col for col in required_cols if col not in df_chart.columns]
        if missing_cols:
            logger.error(f"[PLOTLY] Missing required columns: {missing_cols}")
            st.error(f"❌ Missing required columns: {', '.join(missing_cols)}")
            return False

        # Check for NaN values and handle them
        nan_counts = df_chart[required_cols].isna().sum()
        if nan_counts.any():
            logger.warning(f"[PLOTLY] Found NaN values: {nan_counts.to_dict()}")
            # Drop rows with NaN in critical OHLC columns
            initial_len = len(df_chart)
            df_chart = df_chart.dropna(subset=required_cols)
            dropped = initial_len - len(df_chart)
            if dropped > 0:
                logger.info(f"[PLOTLY] Dropped {dropped} rows with NaN values")

        if df_chart.empty:
            logger.error("[PLOTLY] DataFrame is empty after cleaning")
            st.error("❌ No valid data to display")
            return False

        # Calculate technical indicators if requested
        if show_indicators:
            df_chart = calculate_technical_indicators(df_chart)

        # Determine subplot configuration
        rows = 1
        row_heights = [1.0]
        subplot_titles = [f"{symbol} - {timeframe.upper()}"]

        if show_volume and "volume" in df_chart.columns:
            rows = 2
            row_heights = [0.7, 0.3]  # 70% price, 30% volume
            subplot_titles = [f"{symbol} - {timeframe.upper()}", "Volume"]

        # Create subplots
        fig = make_subplots(
            rows=rows,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=row_heights,
            subplot_titles=subplot_titles,
        )

        # 1. Main candlestick chart
        try:
            fig.add_trace(
                go.Candlestick(
                    x=df_chart["time"],
                    open=df_chart["open"],
                    high=df_chart["high"],
                    low=df_chart["low"],
                    close=df_chart["close"],
                    name="Price",
                    increasing_line_color="rgba(38,166,154,0.9)",  # Green
                    decreasing_line_color="rgba(239,83,80,0.9)",  # Red
                    increasing_fillcolor="rgba(38,166,154,0.9)",
                    decreasing_fillcolor="rgba(239,83,80,0.9)",
                    increasing_line=dict(width=1),
                    decreasing_line=dict(width=1),
                ),
                row=1,
                col=1,
            )
        except Exception as e:
            logger.error(f"[PLOTLY] Failed to add candlestick: {e}")
            st.error(f"❌ Error rendering candlestick: {str(e)}")
            return False

        # 2. Add technical indicator overlays
        if show_indicators:
            # MA20
            if "ma20" in df_chart.columns:
                try:
                    ma20_clean = df_chart["ma20"].dropna()
                    if not ma20_clean.empty:
                        fig.add_trace(
                            go.Scatter(
                                x=df_chart.loc[ma20_clean.index, "time"],
                                y=ma20_clean,
                                mode="lines",
                                name="MA20",
                                line=dict(color="#ff9800", width=2),  # Orange
                                hovertemplate="<b>%{x|%Y-%m-%d}</b><br>MA20: $%{y:.2f}<extra></extra>",
                            ),
                            row=1,
                            col=1,
                        )
                except Exception as e:
                    logger.warning(f"[PLOTLY] Failed to add MA20: {e}")

            # MA50
            if "ma50" in df_chart.columns:
                try:
                    ma50_clean = df_chart["ma50"].dropna()
                    if not ma50_clean.empty:
                        fig.add_trace(
                            go.Scatter(
                                x=df_chart.loc[ma50_clean.index, "time"],
                                y=ma50_clean,
                                mode="lines",
                                name="MA50",
                                line=dict(color="#2196f3", width=2),  # Blue
                                hovertemplate="<b>%{x|%Y-%m-%d}</b><br>MA50: $%{y:.2f}<extra></extra>",
                            ),
                            row=1,
                            col=1,
                        )
                except Exception as e:
                    logger.warning(f"[PLOTLY] Failed to add MA50: {e}")

            # Bollinger Bands
            if all(
                col in df_chart.columns for col in ["bb_upper", "bb_lower", "bb_middle"]
            ):
                try:
                    # Filter valid BB data (where all three bands exist)
                    bb_valid = (
                        df_chart[["bb_upper", "bb_lower", "bb_middle"]]
                        .notna()
                        .all(axis=1)
                    )
                    if bb_valid.any():
                        bb_df = df_chart[bb_valid]

                        # Upper band
                        fig.add_trace(
                            go.Scatter(
                                x=bb_df["time"],
                                y=bb_df["bb_upper"],
                                mode="lines",
                                name="BB Upper",
                                line=dict(
                                    color="rgba(156, 39, 176, 0.6)",
                                    width=1,
                                    dash="dash",
                                ),  # Purple dashed
                                hovertemplate="<b>%{x|%Y-%m-%d}</b><br>BB Upper: $%{y:.2f}<extra></extra>",
                                legendgroup="bollinger",
                                showlegend=True,
                            ),
                            row=1,
                            col=1,
                        )

                        # Lower band (with fill to upper)
                        fig.add_trace(
                            go.Scatter(
                                x=bb_df["time"],
                                y=bb_df["bb_lower"],
                                mode="lines",
                                name="BB Lower",
                                line=dict(
                                    color="rgba(156, 39, 176, 0.6)",
                                    width=1,
                                    dash="dash",
                                ),  # Purple dashed
                                fill="tonexty",
                                fillcolor="rgba(156, 39, 176, 0.1)",  # Light purple fill
                                hovertemplate="<b>%{x|%Y-%m-%d}</b><br>BB Lower: $%{y:.2f}<extra></extra>",
                                legendgroup="bollinger",
                                showlegend=True,
                            ),
                            row=1,
                            col=1,
                        )

                        # Middle band (SMA)
                        fig.add_trace(
                            go.Scatter(
                                x=bb_df["time"],
                                y=bb_df["bb_middle"],
                                mode="lines",
                                name="BB Middle",
                                line=dict(
                                    color="rgba(156, 39, 176, 0.4)", width=1
                                ),  # Lighter purple solid
                                hovertemplate="<b>%{x|%Y-%m-%d}</b><br>BB Middle: $%{y:.2f}<extra></extra>",
                                legendgroup="bollinger",
                                showlegend=True,
                            ),
                            row=1,
                            col=1,
                        )
                except Exception as e:
                    logger.warning(f"[PLOTLY] Failed to add Bollinger Bands: {e}")

        # 3. Volume subplot (if requested)
        if show_volume and "volume" in df_chart.columns:
            try:
                vol_clean = df_chart[["time", "volume", "close", "open"]].dropna(
                    subset=["volume"]
                )
                if not vol_clean.empty:
                    # Color volume bars based on price direction
                    vol_colors = [
                        (
                            "rgba(38,166,154,0.6)"
                            if row["close"] >= row["open"]
                            else "rgba(239,83,80,0.6)"
                        )
                        for _, row in vol_clean.iterrows()
                    ]

                    fig.add_trace(
                        go.Bar(
                            x=vol_clean["time"],
                            y=vol_clean["volume"],
                            name="Volume",
                            marker=dict(color=vol_colors),
                            hovertemplate="<b>%{x|%Y-%m-%d}</b><br>Volume: %{y:,.0f}<extra></extra>",
                            showlegend=False,
                        ),
                        row=2,
                        col=1,
                    )
            except Exception as e:
                logger.warning(f"[PLOTLY] Failed to add volume: {e}")

        # Update layout with professional theming
        fig.update_layout(
            title=dict(
                text=f"{symbol} - {timeframe.upper()}",
                font=dict(size=18, color="#d1d4dc"),
                x=0.5,
            ),
            template="plotly_dark",
            height=700 if show_volume else 600,
            xaxis_rangeslider_visible=False,
            hovermode="x unified",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                bgcolor="rgba(0,0,0,0)",
                bordercolor="rgba(255,255,255,0.2)",
                borderwidth=1,
                font=dict(color="#d1d4dc"),
            ),
            plot_bgcolor="#131722",
            paper_bgcolor="#131722",
            font=dict(color="#d1d4dc", size=12),
            margin=dict(l=60, r=60, t=80, b=40),
        )

        # Update axes styling
        fig.update_xaxes(
            gridcolor="rgba(42, 46, 57, 0.5)",
            showgrid=True,
            zeroline=False,
            color="#d1d4dc",
        )
        fig.update_yaxes(
            gridcolor="rgba(42, 46, 57, 0.5)",
            showgrid=True,
            zeroline=False,
            color="#d1d4dc",
            title_text="Price ($)" if rows == 1 else "Price ($)",
        )

        if show_volume:
            fig.update_yaxes(
                title_text="Volume",
                row=2,
                col=1,
                gridcolor="rgba(42, 46, 57, 0.3)",
                showgrid=True,
            )

        st.plotly_chart(
            fig,
            use_container_width=True,
            config={
                "displayModeBar": True,
                "displaylogo": False,
                "modeBarButtonsToAdd": [
                    "pan2d",
                    "zoom2d",
                    "select2d",
                    "lasso2d",
                    "autoScale2d",
                    "resetScale2d",
                ],
                "toImageButtonOptions": {
                    "format": "png",
                    "filename": f"{symbol}_{timeframe}",
                    "height": 600,
                    "width": 1200,
                    "scale": 2,
                },
            },
        )
        logger.info(f"[PLOTLY] ✅ Chart rendered successfully")
        return True

    except Exception as e:
        logger.error(f"[PLOTLY] Render failed: {e}\n{traceback.format_exc()}")
        st.error(f"❌ Chart rendering error: {str(e)}")
        return False


def render_trading_chart(
    df: pd.DataFrame,
    symbol: str = "AAPL",
    timeframe: str = "1d",
    show_volume: bool = True,
    show_indicators: bool = True,
    show_signals: bool = False,
    chart_type: str = "candlestick",
    indicators: Optional[Dict] = None,
) -> bool:
    """
    ENHANCED: Unified chart rendering with automatic fallback and professional features.

    Features:
    - TradingView-style rendering
    - Technical indicators (MA20, MA50, MA200, Bollinger Bands, RSI, MACD)
    - Volume panel
    - Trade signals/flags
    - Chart type selection (candlestick, line, bar)
    - Uniform theming
    - Configurable indicator overlays via indicators dict

    PRIMARY: streamlit-lightweight-charts
    FALLBACK: Plotly

    Args:
        df: DataFrame with OHLCV data
        symbol: Stock symbol for display
        timeframe: Time interval (e.g., '1d', '4h')
        show_volume: Whether to display volume panel
        show_indicators: Whether to show technical indicators
        show_signals: Whether to show trade signals/flags
        chart_type: Chart type ('candlestick', 'line', 'bar')
        indicators: Dict of indicator configs (e.g., {'bollinger_bands': True, 'rsi': True})

    Returns:
        True if successful, False if all methods failed
    """

    # Default indicators config
    if indicators is None:
        indicators = {}

    try:
        # 1. Normalize data
        df_norm, is_valid = normalize_ohlcv_data(df)
        if not is_valid:
            st.error("❌ Data validation failed. Check logs for details.")
            logger.error("[CHART] Data normalization failed")
            return False

        logger.info(
            f"[CHART] Starting render for {symbol} {timeframe} (type={chart_type})"
        )

        # 2. Try lightweight-charts first
        if LIGHTWEIGHT_AVAILABLE:
            success = render_lightweight_chart(
                df_norm,
                symbol,
                timeframe,
                show_volume=show_volume,
                show_indicators=show_indicators,
                show_signals=show_signals,
                indicators=indicators,
            )
            if success:
                return True
            logger.warning("[CHART] Lightweight-charts failed, trying Plotly fallback")

        # 3. Fall back to Plotly
        if PLOTLY_AVAILABLE:
            success = render_plotly_chart(
                df_norm,
                symbol,
                timeframe,
                show_volume=show_volume,
                show_indicators=show_indicators,
                show_signals=show_signals,
            )
            if success:
                st.info("📊 Using Plotly (lightweight-charts unavailable)")
                return True

        # 4. Both failed
        st.error("❌ All charting methods failed. Check logs for details.")
        logger.error("[CHART] All charting methods failed")
        return False

    except Exception as e:
        logger.error(f"[CHART] Fatal error: {e}\n{traceback.format_exc()}")
        st.error(f"❌ Chart rendering error: {str(e)}")
        return False


def render_multi_symbol_comparison(
    symbol_data: Dict[str, pd.DataFrame],
    timeframe: str = "1d",
    show_volume: bool = False,
    chart_type: str = "line",
) -> bool:
    """
    Render multiple stock symbols on the same chart for comparison (Koyfin-style).

    Args:
        symbol_data: Dictionary mapping symbol names to DataFrames with OHLCV data
        timeframe: Time interval (e.g., '1d', '4h')
        show_volume: Whether to show volume (only for first symbol)
        chart_type: Chart type ('line', 'candlestick', 'bar')

    Returns:
        True if successful, False otherwise
    """

    if not PLOTLY_AVAILABLE:
        st.error("❌ Plotly required for multi-symbol comparison")
        return False

    try:
        if not symbol_data:
            st.error("❌ No symbol data provided")
            return False

        logger.info(f"[MULTI_CHART] Rendering {len(symbol_data)} symbols")

        # Determine subplot configuration
        rows = 1
        row_heights = [1.0]
        subplot_titles = ["Multi-Symbol Comparison"]

        if show_volume and len(symbol_data) > 0:
            # Use first symbol's volume
            first_symbol = list(symbol_data.keys())[0]
            first_df = symbol_data[first_symbol]
            if "volume" in first_df.columns:
                rows = 2
                row_heights = [0.7, 0.3]
                subplot_titles = ["Multi-Symbol Comparison", "Volume"]

        fig = make_subplots(
            rows=rows,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=row_heights,
            subplot_titles=subplot_titles,
        )

        # Color palette for multiple symbols
        colors = [
            "#10b981",
            "#3b82f6",
            "#f59e0b",
            "#ef4444",
            "#8b5cf6",
            "#06b6d4",
            "#ec4899",
        ]

        # Normalize all dataframes and plot them
        symbol_colors = {}
        for idx, (symbol, df_raw) in enumerate(symbol_data.items()):
            df_norm, is_valid = normalize_ohlcv_data(df_raw)
            if not is_valid:
                logger.warning(f"[MULTI_CHART] Skipping {symbol} - invalid data")
                continue

            color = colors[idx % len(colors)]
            symbol_colors[symbol] = color

            # Plot based on chart type
            if chart_type == "line":
                fig.add_trace(
                    go.Scatter(
                        x=df_norm["time"],
                        y=df_norm["close"],
                        mode="lines",
                        name=symbol,
                        line=dict(color=color, width=2),
                        hovertemplate=f"<b>{symbol}</b><br>%{{x|%Y-%m-%d}}<br>Close: $%{{y:.2f}}<extra></extra>",
                    ),
                    row=1,
                    col=1,
                )
            elif chart_type == "candlestick":
                # For candlestick, only show first symbol clearly, others as lines
                if idx == 0:
                    fig.add_trace(
                        go.Candlestick(
                            x=df_norm["time"],
                            open=df_norm["open"],
                            high=df_norm["high"],
                            low=df_norm["low"],
                            close=df_norm["close"],
                            name=symbol,
                            increasing_line_color=color,
                            decreasing_line_color=color,
                        ),
                        row=1,
                        col=1,
                    )
                else:
                    # Other symbols as lines
                    fig.add_trace(
                        go.Scatter(
                            x=df_norm["time"],
                            y=df_norm["close"],
                            mode="lines",
                            name=symbol,
                            line=dict(color=color, width=2),
                            hovertemplate=f"<b>{symbol}</b><br>%{{x|%Y-%m-%d}}<br>Close: $%{{y:.2f}}<extra></extra>",
                        ),
                        row=1,
                        col=1,
                    )
            else:  # bar
                fig.add_trace(
                    go.Bar(
                        x=df_norm["time"],
                        y=df_norm["close"],
                        name=symbol,
                        marker=dict(color=color),
                        hovertemplate=f"<b>{symbol}</b><br>%{{x|%Y-%m-%d}}<br>Close: $%{{y:.2f}}<extra></extra>",
                    ),
                    row=1,
                    col=1,
                )

        # Add volume for first symbol if requested
        if show_volume and len(symbol_data) > 0:
            first_symbol = list(symbol_data.keys())[0]
            first_df_norm, is_valid = normalize_ohlcv_data(symbol_data[first_symbol])
            if is_valid and "volume" in first_df_norm.columns:
                vol_clean = first_df_norm[["time", "volume", "close", "open"]].dropna(
                    subset=["volume"]
                )
                if not vol_clean.empty:
                    vol_colors = [
                        (
                            "rgba(38,166,154,0.6)"
                            if row["close"] >= row["open"]
                            else "rgba(239,83,80,0.6)"
                        )
                        for _, row in vol_clean.iterrows()
                    ]

                    fig.add_trace(
                        go.Bar(
                            x=vol_clean["time"],
                            y=vol_clean["volume"],
                            name=f"{first_symbol} Volume",
                            marker=dict(color=vol_colors),
                            showlegend=False,
                            hovertemplate=f"<b>{first_symbol} Volume</b><br>%{{x|%Y-%m-%d}}<br>Volume: %{{y:,.0f}}<extra></extra>",
                        ),
                        row=2,
                        col=1,
                    )

        # Update layout
        fig.update_layout(
            title=dict(
                text="Multi-Symbol Comparison",
                font=dict(size=18, color="#d1d4dc"),
                x=0.5,
            ),
            template="plotly_dark",
            height=700 if show_volume else 600,
            xaxis_rangeslider_visible=False,
            hovermode="x unified",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                bgcolor="rgba(0,0,0,0)",
                bordercolor="rgba(255,255,255,0.2)",
                borderwidth=1,
                font=dict(color="#d1d4dc"),
            ),
            plot_bgcolor="#131722",
            paper_bgcolor="#131722",
            font=dict(color="#d1d4dc", size=12),
            margin=dict(l=60, r=60, t=80, b=40),
        )

        # Update axes
        fig.update_xaxes(
            gridcolor="rgba(42, 46, 57, 0.5)",
            showgrid=True,
            zeroline=False,
            color="#d1d4dc",
        )
        fig.update_yaxes(
            gridcolor="rgba(42, 46, 57, 0.5)",
            showgrid=True,
            zeroline=False,
            color="#d1d4dc",
            title_text="Price ($)",
            row=1,
            col=1,
        )

        if show_volume:
            fig.update_yaxes(
                title_text="Volume",
                row=2,
                col=1,
                gridcolor="rgba(42, 46, 57, 0.3)",
                showgrid=True,
            )

        st.plotly_chart(fig, use_container_width=True)
        logger.info(f"[MULTI_CHART] ✅ Comparison chart rendered")
        return True

    except Exception as e:
        logger.error(f"[MULTI_CHART] Failed: {e}\n{traceback.format_exc()}")
        st.error(f"❌ Multi-symbol comparison error: {str(e)}")
        return False


# ──────────────────────────────────────────────────────────────────────────────
# NEW: Dedicated SuperTrend and Forecasting plots (Phase 4 plotting adjustments)
# ──────────────────────────────────────────────────────────────────────────────


def _ensure_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names to Title Case OHLCV and ensure datetime index."""
    if df is None or df.empty:
        return pd.DataFrame()
    d = df.copy()
    # Normalize column names
    rename_map = {}
    for c in d.columns:
        cl = c.lower()
        if cl in {"date", "time", "timestamp", "datetime"}:
            rename_map[c] = "Time"
        elif cl == "open":
            rename_map[c] = "Open"
        elif cl == "high":
            rename_map[c] = "High"
        elif cl == "low":
            rename_map[c] = "Low"
        elif cl == "close":
            rename_map[c] = "Close"
        elif cl == "volume":
            rename_map[c] = "Volume"
    if rename_map:
        d = d.rename(columns=rename_map)
    # Build Time column if missing
    if "Time" not in d.columns:
        if not d.index.empty:
            d["Time"] = d.index
        else:
            d["Time"] = pd.Timestamp.utcnow()
    # Ensure datetime
    try:
        d["Time"] = pd.to_datetime(d["Time"], errors="coerce")
    except Exception:
        pass
    d = d.dropna(subset=["Time"]).sort_values("Time")
    return d


def _atr_numpy(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    """ATR fallback implementation if TA-Lib is unavailable."""
    high = pd.to_numeric(high, errors="coerce")
    low = pd.to_numeric(low, errors="coerce")
    close = pd.to_numeric(close, errors="coerce")
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    return atr


def create_supertrend_plot(
    df: pd.DataFrame,
    df_historical: Optional[pd.DataFrame] = None,
    symbol: str = "SYMBOL",
    timeframe: str = "1d",
    atr_length: int = 10,
    min_mult: float = 1,
    max_mult: float = 5,
    step: float = 0.5,
    perf_alpha: int = 10,
    from_cluster: str = "Best",
) -> "go.Figure":
    """
    SuperTrend AI: K-Means Adaptive Factor with conditional plotting (Pine Script match)
    - Uses full historical data for K-Means stability (df_historical if provided)
    - Displays recent window (df) for chart visualization
    - Gaps at trend reversals (os != os[1] ? na logic)
    - Perf AMA support/resistance line (cyan dashed)
    - Score labels 0-10 at signals (performance index strength)
    - Green/red segments based on trend

    Args:
        df: Display window DataFrame (e.g., last 365 days for chart)
        df_historical: Full historical DataFrame for K-Means calculation (optional, uses df if None)
        symbol: Stock ticker
        timeframe: Timeframe string (e.g., '1d', '1h')
        atr_length: ATR period
        min_mult/max_mult: Factor range for K-Means (1-5 default)
        step: Factor step size (0.5 = 9 factors)
        perf_alpha: Performance memory parameter
        from_cluster: Which cluster to use ('Best', 'Average', 'Worst')
    """
    if not PLOTLY_AVAILABLE:
        raise RuntimeError("Plotly required for create_supertrend_plot")

    if not SUPERTREND_AI_AVAILABLE:
        logger.error("[SUPERTR AI] SuperTrendAI class not available - using fallback")
        fig = go.Figure()
        fig.update_layout(
            title="SuperTrend AI Unavailable - Module Not Loaded",
            template="plotly_dark",
        )
        return fig

    # Use historical for calculation, display for chart
    df_calc = (
        df_historical
        if df_historical is not None and len(df_historical) > len(df)
        else df
    )
    df_plot = df  # Display window

    d_calc = _ensure_ohlcv(df_calc)
    d_plot = _ensure_ohlcv(df_plot)
    needed = {"Open", "High", "Low", "Close"}

    if d_calc.empty or not needed.issubset(set(d_calc.columns)) or len(d_calc) < 100:
        fig = go.Figure()
        fig.update_layout(
            title=f"SuperTrend AI: Need 100+ bars for K-Means (got {len(d_calc)})",
            template="plotly_dark",
        )
        logger.warning(
            f"[SUPERTR AI] {symbol}: Need 100+ bars for stable K-Means (got {len(d_calc)})"
        )
        return fig

    try:
        # Prepare historical df (full, for clustering stability)
        df_ai_full = d_calc.copy()
        df_ai_full.columns = df_ai_full.columns.str.lower()

        # SuperTrend AI on full history (K-Means has max data, stable factors)
        st_ai = SuperTrendAI(
            df=df_ai_full,
            atr_length=atr_length,
            min_mult=min_mult,
            max_mult=max_mult,
            step=step,
            perf_alpha=perf_alpha,
            from_cluster=from_cluster,
            max_iter=1000,
            max_data=len(df_ai_full),
        )  # Use actual data length
        result_df_full, info = st_ai.calculate()

        # Slice result to display window (align with d_plot indices)
        try:
            # Try to align by index intersection
            common_idx = d_plot.index.intersection(result_df_full.index)
            if len(common_idx) > 0:
                result_df = result_df_full.loc[common_idx]
            else:
                # Fallback: just use last N rows matching display window
                result_df = result_df_full.tail(len(d_plot))
        except Exception:
            # If alignment fails, use last N rows
            result_df = result_df_full.tail(len(d_plot))

        logger.info(
            f"[SUPERTR AI] {symbol}: Full history {len(df_ai_full)} bars → display {len(result_df)} bars, "
            f"target_factor={info['target_factor']:.2f} (K-Means stable)"
        )

        # Extract signals (flips only)
        buy_signals = result_df[result_df["signal"] == 1].index
        sell_signals = result_df[result_df["signal"] == -1].index

        # Conditional plot data (plot line when trend unchanged, na at flips)
        # Pine: os != os[1] ? na → Python: gaps where trend.diff() != 0
        result_df["trend_prev"] = result_df["trend"].shift(1).fillna(0)
        result_df["plot_st"] = np.where(
            result_df["trend"] == result_df["trend_prev"],
            result_df["supertrend"],
            np.nan,
        )
        result_df["plot_ama"] = result_df["perf_ama"].copy()

        # Subplots (main 2x price/ST+AMA, aux volume/RSI)
        fig = make_subplots(
            rows=2,
            cols=1,
            row_heights=[0.7, 0.3],
            vertical_spacing=0.05,
            subplot_titles=[
                f"SuperTrend AI: {symbol} {timeframe} (Adaptive Factor={info['target_factor']:.2f})",
                "Volume & RSI",
            ],
            specs=[[{"secondary_y": False}], [{"secondary_y": True}]],
        )

        # Main: Candles (gradient via perf_idx if available)
        perf_idx_norm = info.get("performance_index", 0.5)  # 0-1
        opacity = 0.5 + perf_idx_norm * 0.3  # 0.5-0.8
        fig.add_trace(
            go.Candlestick(
                x=d_plot["Time"],
                open=d_plot["Open"],
                high=d_plot["High"],
                low=d_plot["Low"],
                close=d_plot["Close"],
                name="Price",
                increasing_line_color="white",
                decreasing_line_color="gray",
                increasing_fillcolor=f"rgba(0,255,0,{opacity})",
                decreasing_fillcolor=f"rgba(255,0,0,{opacity})",
            ),
            row=1,
            col=1,
        )

        # SuperTrend AI line (conditional, gaps at flips)
        # Split by trend for color (green up/red down segments)
        up_mask = result_df["trend"] == 1
        down_mask = result_df["trend"] == 0

        if up_mask.any():
            fig.add_trace(
                go.Scatter(
                    x=d_plot["Time"][up_mask],
                    y=result_df.loc[up_mask, "plot_st"],
                    mode="lines",
                    line=dict(color="green", width=2.5),
                    name="ST Up",
                    hovertemplate="ST Up: %{y:.2f}<extra></extra>",
                ),
                row=1,
                col=1,
            )
        if down_mask.any():
            fig.add_trace(
                go.Scatter(
                    x=d_plot["Time"][down_mask],
                    y=result_df.loc[down_mask, "plot_st"],
                    mode="lines",
                    line=dict(color="red", width=2.5),
                    name="ST Down",
                ),
                row=1,
                col=1,
            )

        # Perf AMA (cyan dash, support/resistance)
        fig.add_trace(
            go.Scatter(
                x=d_plot["Time"],
                y=result_df["plot_ama"],
                mode="lines",
                line=dict(color="cyan", width=1.5, dash="dash"),
                name="Perf AMA",
                hovertemplate="AMA: %{y:.2f}<extra></extra>",
            ),
            row=1,
            col=1,
        )

        # Signal labels (tiny text at flips with perf_idx score 0-10)
        score = int(perf_idx_norm * 10)  # 0-10 e.g., 7
        for bs in buy_signals:
            if bs in d_plot.index:
                bs_idx = d_plot.index.get_loc(bs)
                fig.add_annotation(
                    x=d_plot["Time"].iloc[bs_idx],
                    y=result_df.loc[bs, "supertrend"],
                    text=str(score),
                    showarrow=True,
                    arrowhead=2,
                    arrowcolor="green",
                    arrowsize=1,
                    ax=0,
                    ay=-20,
                    font=dict(size=8, color="white"),
                    bgcolor="green",
                    bordercolor="white",
                    row=1,
                    col=1,
                )
        for ss in sell_signals:
            if ss in d_plot.index:
                ss_idx = d_plot.index.get_loc(ss)
                fig.add_annotation(
                    x=d_plot["Time"].iloc[ss_idx],
                    y=result_df.loc[ss, "supertrend"],
                    text=str(score),
                    showarrow=True,
                    arrowhead=2,
                    arrowcolor="red",
                    arrowsize=1,
                    ax=0,
                    ay=20,
                    font=dict(size=8, color="white"),
                    bgcolor="red",
                    bordercolor="white",
                    row=1,
                    col=1,
                )

        # Aux: Volume (bars green/red match candles)
        if "Volume" in d_plot.columns:
            vol_colors = [
                "rgba(0,255,0,0.7)" if c > o else "rgba(255,0,0,0.7)"
                for o, c in zip(d_plot["Open"], d_plot["Close"])
            ]
            fig.add_trace(
                go.Bar(
                    x=d_plot["Time"],
                    y=d_plot.get("Volume", np.zeros(len(d_plot))),
                    marker_color=vol_colors,
                    name="Volume",
                    opacity=0.7,
                ),
                row=2,
                col=1,
                secondary_y=False,
            )

        # RSI (orange line 14-period, 70/30 hlines)
        delta = d_plot["Close"].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        fig.add_trace(
            go.Scatter(
                x=d_plot["Time"],
                y=rsi,
                mode="lines",
                line=dict(color="orange", width=1.5),
                name="RSI (14)",
            ),
            row=2,
            col=1,
            secondary_y=True,
        )
        fig.add_hline(
            y=70, line_dash="dash", line_color="red", annotation_text="70", row=2, col=1
        )
        fig.add_hline(
            y=30,
            line_dash="dash",
            line_color="green",
            annotation_text="30",
            row=2,
            col=1,
        )

        # Layout (black bg, shared x, height 700)
        fig.update_layout(
            title="🟢 SuperTrend AI: K-Means Adaptive",
            xaxis_title="Date",
            yaxis_title="Price",
            plot_bgcolor="black",
            paper_bgcolor="black",
            font_color="white",
            height=700,
            showlegend=True,
            template="plotly_dark",
            hovermode="x unified",
        )
        fig.update_xaxes(showgrid=True, gridcolor="gray", row=1, col=1)
        fig.update_yaxes(showgrid=True, gridcolor="gray", row=1, col=1)
        fig.update_yaxes(title="Volume", secondary_y=False, row=2, col=1)
        fig.update_yaxes(title="RSI", secondary_y=True, row=2, col=1, range=[0, 100])

        logger.info(
            f"[SUPERTR AI] {symbol}: {len(buy_signals)} buys/{len(sell_signals)} sells, "
            f"target_factor={info['target_factor']:.2f} (K-Means {from_cluster}), score={score}/10"
        )
        return fig

    except Exception as e:
        logger.error(f"[SUPERTR AI] {symbol} failed: {e}")
        logger.error(traceback.format_exc())
        fig = go.Figure()
        fig.update_layout(
            title=f"SuperTrend AI Error: {str(e)[:50]}", template="plotly_dark"
        )
        return fig


def create_forecasting_plot(
    df: pd.DataFrame, predictions: Dict, garch_vol: float = 0.015
) -> "go.Figure":
    """
    Forecasting overlay: Prophet (blue dashed) + XGBoost (orange markers) + Blend (purple) with vol bands.
    - Two rows: main (price/forecasts), aux (volume/confidence)
    """
    if not PLOTLY_AVAILABLE:
        raise RuntimeError("Plotly required for create_forecasting_plot")

    d = _ensure_ohlcv(df)
    if d.empty or not {"Close", "Time"}.issubset(d.columns):
        fig = go.Figure()
        fig.update_layout(
            title="Forecast Unavailable - Invalid Data", template="plotly_dark"
        )
        return fig

    signal = float(predictions.get("signal", 0.0) or 0.0)
    confidence = float(predictions.get("confidence", 0.5) or 0.5)
    # Construct simple 30-step daily horizon
    last_time = pd.to_datetime(d["Time"].iloc[-1])
    future_dates = pd.date_range(
        start=last_time + pd.Timedelta(days=1), periods=30, freq="D"
    )

    # Basic synthetic components if not provided
    last_price = float(d["Close"].iloc[-1])
    prophet_trend = np.full(len(future_dates), last_price * (1 + signal * 0.02)).astype(
        float
    )
    if "prophet_trend" in predictions and isinstance(
        predictions["prophet_trend"], (list, np.ndarray, pd.Series)
    ):
        pt = (
            pd.to_numeric(pd.Series(predictions["prophet_trend"]), errors="coerce")
            .ffill()
            .fillna(last_price)
        )
        if len(pt) >= len(future_dates):
            prophet_trend = pt.values[: len(future_dates)]

    xgb_component = np.full(len(future_dates), last_price).astype(float)
    if "xgboost_pred" in predictions and isinstance(
        predictions["xgboost_pred"], (list, np.ndarray)
    ):
        xp = pd.to_numeric(
            pd.Series(predictions["xgboost_pred"]), errors="coerce"
        ).fillna(last_price)
        if len(xp) >= len(future_dates):
            xgb_component = xp.values[: len(future_dates)]

    # Ensure arrays are numeric ndarrays to avoid ExtensionArray type issues
    pt_arr = np.asarray(prophet_trend, dtype=float)
    xp_arr = np.asarray(xgb_component, dtype=float)
    blend = (pt_arr + xp_arr) / 2.0
    blend = blend * max(0.5, confidence)  # dampen/amplify by confidence

    # Volatility bands ±1σ cumulative using GARCH vol (sqrt time)
    sigma = float(garch_vol or 0.015)
    steps = np.sqrt(np.arange(1, len(future_dates) + 1))
    upper = blend * (1 + sigma * steps)
    lower = blend * (1 - sigma * steps)

    fig = make_subplots(
        rows=2,
        cols=1,
        row_heights=[0.7, 0.3],
        vertical_spacing=0.05,
        shared_xaxes=True,
        subplot_titles=["Forecast Overlay", "Volume & Confidence"],
    )

    # Historical price
    fig.add_trace(
        go.Scatter(
            x=d["Time"],
            y=d["Close"],
            mode="lines",
            name="Historical Price",
            line=dict(color="white", width=1.5),
        ),
        row=1,
        col=1,
    )
    # Prophet (dashed) + connect from last close
    fig.add_trace(
        go.Scatter(
            x=[d["Time"].iloc[-1], future_dates[0]],
            y=[last_price, pt_arr[0]],
            mode="lines",
            line=dict(color="blue", dash="dash", width=2),
            name="Prophet (conn)",
            showlegend=False,
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=future_dates,
            y=pt_arr,
            mode="lines",
            name="Prophet",
            line=dict(color="blue", dash="dash", width=2),
        ),
        row=1,
        col=1,
    )
    # XGBoost points
    fig.add_trace(
        go.Scatter(
            x=future_dates,
            y=xgb_component,
            mode="markers",
            name="XGBoost",
            marker=dict(color="orange", size=6),
        ),
        row=1,
        col=1,
    )
    # Blend line + connect from last close
    fig.add_trace(
        go.Scatter(
            x=[d["Time"].iloc[-1], future_dates[0]],
            y=[last_price, blend[0]],
            mode="lines",
            line=dict(color="purple", width=3),
            name="Blend (conn)",
            showlegend=False,
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=future_dates,
            y=blend,
            mode="lines",
            name="Blend Signal",
            line=dict(color="purple", width=3),
        ),
        row=1,
        col=1,
    )

    # Vol shading + ribbon
    if sigma > 0.015:
        fig.add_hrect(
            y0=float(lower.min()),
            y1=float(upper.max()),
            fillcolor="rgba(255,165,0,0.18)",
            line_width=0,
            annotation_text=f"High Vol Alert ({sigma:.1%})",
            annotation_font_size=10,
        )
    fig.add_trace(
        go.Scatter(
            x=list(future_dates) + list(future_dates[::-1]),
            y=list(upper) + list(lower[::-1]),
            fill="toself",
            fillcolor="rgba(128,128,128,0.15)",
            line=dict(color="gray"),
            name="Vol Bands (±σ)",
            showlegend=True,
        ),
        row=1,
        col=1,
    )

    # Aux: recent 60-volume + flat confidence line
    if "Volume" in d.columns:
        d_tail = d.tail(60)
        fig.add_trace(
            go.Bar(
                x=d_tail["Time"],
                y=d_tail["Volume"],
                name="Volume",
                marker_color="lightblue",
                opacity=0.6,
            ),
            row=2,
            col=1,
        )
    conf_line = np.full(len(future_dates), confidence)
    fig.add_trace(
        go.Scatter(
            x=future_dates,
            y=conf_line,
            mode="lines",
            name="Confidence",
            line=dict(color="green", width=2),
        ),
        row=2,
        col=1,
    )

    fig.update_layout(
        title="🔮 Forecasting: Ensemble Blend + Vol Bands",
        xaxis_title="Date",
        yaxis_title="Price",
        height=700,
        showlegend=True,
        template="plotly_dark",
        plot_bgcolor="black",
        paper_bgcolor="black",
    )
    fig.update_xaxes(showgrid=True, gridcolor="gray", rangeslider_visible=False)
    fig.update_yaxes(showgrid=True, gridcolor="gray")
    logger.info(
        f"[PLOT] ✅ Forecasting plotted: signal={signal:.2f}, conf={confidence:.2f}, vol={sigma:.2%}"
    )
    return fig
