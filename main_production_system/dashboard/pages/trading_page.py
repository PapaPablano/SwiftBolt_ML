"""
Live Trading Dashboard Page - REDESIGNED FOR USABILITY

Complete rewrite with proper layout, technical indicators, and feature visualization.

Author: Cursor Agent
Created: 2025-10-31
Updated: 2025-11-01 - Complete redesign for production usability
"""

from __future__ import annotations

# ═══════════════════════════════════════════════════════════════════════════
# IMPORTS
# ═══════════════════════════════════════════════════════════════════════════

import sys
from pathlib import Path
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple


PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent  # Adjust to root
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Guard forecast_renderer (missing? Create stub or skip)
try:
    from main_production_system.dashboard.utils.forecast_renderer import (
        add_simple_forecast_dots,
        add_forecast_table,
    )
except ImportError:
    logger.warning("forecast_renderer not found - Skipping forecast features")

    def add_simple_forecast_dots(fig, df):
        pass

    def add_forecast_table(st, df):
        pass


# Guard other utils/charts
try:
    from main_production_system.dashboard.utils.chart_service import (
        create_supertrend_plot,
        create_forecasting_plot,
    )
except ImportError as e:
    logger.warning(f"Chart service partial: {e}")

    def create_supertrend_plot(df, sym, tf):
        st.line_chart(df["Close"])  # Basic fallback

    def create_forecasting_plot(df):
        st.line_chart(df["Close"])


import concurrent.futures
import time

# External providers and feature engine (for multi-symbol batch)
try:
    import yfinance as yf  # Fallback for direct batch fetch
except Exception:
    yf = None  # Guarded usage
from src.option_analysis.data_providers import (
    DataProviderManager,
)  # Auto-fallback manager
from main_production_system.dashboard.core.feature_engine import engineer_features
from main_production_system.core.supertrend_ai import SuperTrendAI

logger = logging.getLogger(__name__)

# ML Prediction imports (lazy loaded when needed)
try:
    from main_production_system.dashboard.core.ml_prediction_service import (
        generate_price_predictions_all_levels,
        prepare_prediction_overlay_data,
    )

    ML_PREDICTIONS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"ML prediction service not available: {e}")
    ML_PREDICTIONS_AVAILABLE = False
    generate_price_predictions_all_levels = None  # type: ignore
    prepare_prediction_overlay_data = None  # type: ignore

# Page config (must be at top level before any other Streamlit commands)
try:
    st.set_page_config(page_title="Trading Dashboard", layout="wide")
except Exception:
    # Already configured by parent or not in Streamlit context
    pass

# ═══════════════════════════════════════════════════════════════════════════
# LAZY IMPORTS
# ═══════════════════════════════════════════════════════════════════════════


def get_data_pipeline():
    """Lazy load data pipeline with error handling."""
    try:
        from main_production_system.dashboard.core.data_pipeline import (
            get_data_and_features_with_friendly_errors,
            get_data_and_features_timescale_market_hours,
            UserFriendlyError,
        )
        from main_production_system.data_infrastructure.market_calendar import (
            get_market_calendar,
        )

        return {
            "get_data_and_features_with_friendly_errors": get_data_and_features_with_friendly_errors,
            "get_data_and_features_timescale_market_hours": get_data_and_features_timescale_market_hours,
            "get_market_calendar": get_market_calendar,
            "UserFriendlyError": UserFriendlyError,
        }
    except Exception as e:
        logger.error(f"Failed to import data pipeline: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ═══════════════════════════════════════════════════════════════════════════


def init_session_state():
    """Initialize session state variables."""
    defaults = {
        "current_symbol": "AAPL",
        "current_timeframe": "1d",
        "lookback_days": 30,
        "use_polygon": True,
        "last_update": datetime.now(),
    }
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value


# ═══════════════════════════════════════════════════════════════════════════
# MULTI-SYMBOL BATCH FETCH + HEATMAP HELPERS (Phase 5)
# ═══════════════════════════════════════════════════════════════════════════


@st.cache_data(ttl=300)
def batch_fetch_data(
    symbols: list[str], timeframes: list[str], days: int = 730, provider: str = "auto"
) -> dict[str, dict[str, pd.DataFrame]]:
    """Parallel fetch for multiple symbols and timeframes.

    Uses DataProviderManager (auto fallback). For explicit non-auto provider,
    falls back to yfinance direct fetch per symbol.
    Returns nested dict: {symbol: {tf: df_ohlcv}}
    """
    results: dict[str, dict[str, pd.DataFrame]] = {}
    manager = DataProviderManager() if provider == "auto" else None

    tf_map = {"1h": "1h", "4h": "1h", "1d": "1d"}  # 4h will be resampled

    def _resample_4h(df_in: pd.DataFrame) -> pd.DataFrame:
        try:
            d = df_in.copy()
            # Normalize column names
            cols = {c: c.lower() for c in d.columns}
            d = d.rename(columns=cols)
            time_col = (
                "date"
                if "date" in d.columns
                else "timestamp" if "timestamp" in d.columns else "time"
            )
            if time_col not in d.columns:
                return pd.DataFrame()
            d[time_col] = pd.to_datetime(d[time_col])
            d = d.set_index(time_col).sort_index()
            d = (
                d.resample("4H")
                .agg(
                    {
                        "open": "first",
                        "high": "max",
                        "low": "min",
                        "close": "last",
                        "volume": "sum",
                    }
                )
                .dropna(how="any")
                .reset_index()
                .rename(
                    columns={
                        time_col: "Date",
                        "open": "Open",
                        "high": "High",
                        "low": "Low",
                        "close": "Close",
                        "volume": "Volume",
                    }
                )
            )
            return d
        except Exception:
            return pd.DataFrame()

    def normalize_df(df_in: pd.DataFrame) -> pd.DataFrame:
        if df_in is None or df_in.empty:
            return pd.DataFrame()
        d = df_in.copy()
        # Support both timestamp/time/date columns
        col_map = {}
        if "timestamp" in d.columns:
            col_map["timestamp"] = "Date"
        elif "time" in d.columns:
            col_map["time"] = "Date"
        elif "date" in d.columns:
            col_map["date"] = "Date"
        # OHLCV
        for a, b in [
            ("open", "Open"),
            ("high", "High"),
            ("low", "Low"),
            ("close", "Close"),
            ("volume", "Volume"),
        ]:
            if a in d.columns:
                col_map[a] = b
            elif a.capitalize() in d.columns:
                col_map[a.capitalize()] = b
        d = d.rename(columns=col_map)
        if "Date" in d.columns:
            d["Date"] = pd.to_datetime(d["Date"])
        # Keep only required
        needed = ["Date", "Open", "High", "Low", "Close", "Volume"]
        missing = [c for c in needed if c not in d.columns]
        if missing:
            return pd.DataFrame()
        d = d[needed].dropna().sort_values("Date").reset_index(drop=True)
        return d

    def fetch_single(sym: str, tf: str) -> pd.DataFrame:
        start = datetime.now() - timedelta(days=days)
        end = datetime.now()
        try:
            if provider == "auto" and manager is not None:
                raw = manager.fetch(sym, start, end, tf_map.get(tf, "1d"))
                df = normalize_df(raw)
                if tf == "4h" and not df.empty:
                    df = _resample_4h(df)
            else:
                if yf is None:
                    raise RuntimeError("yfinance not available for direct fetch")
                interval = {"1h": "60m", "4h": "60m", "1d": "1d"}.get(tf, "1d")
                df = yf.Ticker(sym).history(
                    period=f"{days}d",
                    interval=interval,
                    actions=False,
                    auto_adjust=False,
                )
                df = df.reset_index().rename(
                    columns={
                        "Date": "Date",
                        "Open": "Open",
                        "High": "High",
                        "Low": "Low",
                        "Close": "Close",
                        "Volume": "Volume",
                    }
                )
                if tf == "4h" and not df.empty:
                    df = _resample_4h(df)
            logger.info(f"[BATCH] {sym} {tf}: {len(df)} bars fetched")
            return df
        except Exception as e:
            # Backoff for rate limits
            if "rate limit" in str(e).lower():
                time.sleep(1)
            try:
                # yfinance specific missing error
                if hasattr(yf, "YFPricesMissingError") and isinstance(e, yf.YFPricesMissingError):  # type: ignore
                    logger.warning(f"[BATCH] {sym} {tf}: Data missing (interval limit)")
                    return pd.DataFrame()
            except Exception:
                pass
            logger.warning(f"[BATCH] {sym} {tf} failed: {e}")
            return pd.DataFrame()

    # Parallel fetch
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=min(5, max(1, len(symbols) * len(timeframes)))
    ) as executor:
        futures = {
            executor.submit(fetch_single, sym, tf): (sym, tf)
            for sym in symbols
            for tf in timeframes
        }
        for future in concurrent.futures.as_completed(futures):
            sym, tf = futures[future]
            try:
                df = future.result(timeout=30)
                if sym not in results:
                    results[sym] = {}
                # Engineer features per DF (fast path)
                if df is not None and not df.empty:
                    try:
                        feats = engineer_features(
                            df, cache_params={"symbol": sym, "timeframe": tf}
                        )
                    except Exception:
                        feats = df
                    results[sym][tf] = feats
                else:
                    results[sym][tf] = pd.DataFrame()
            except Exception as e:
                logger.error(f"[BATCH] {sym} {tf} error: {e}")
                if sym not in results:
                    results[sym] = {}
                results[sym][tf] = pd.DataFrame()

    logger.info(
        f"[BATCH] Complete: {len(results)} symbols across {len(timeframes)} TFs"
    )
    return results


def compute_supertrend_factor_score(df: pd.DataFrame) -> tuple[float, int]:
    """Compute SuperTrend AI factor and score (0-10) for a given engineered DF.
    Returns (factor, score). On failure returns (nan, -1).
    """
    try:
        # Normalize columns for SuperTrendAI
        needed = ["Open", "High", "Low", "Close"]
        if not all(c in df.columns for c in needed):
            # Try lowercase
            d = df.rename(columns={c: c.title() for c in df.columns})
        else:
            d = df
        d_ai = d.rename(
            columns={"Open": "open", "High": "high", "Low": "low", "Close": "close"}
        )
        st_ai = SuperTrendAI(
            d_ai,
            atr_length=10,
            min_mult=1,
            max_mult=5,
            step=0.5,
            perf_alpha=10,
            from_cluster="Best",
        )
        result_df, info = st_ai.calculate()
        factor = float(info.get("target_factor", np.nan))
        perf_idx = float(info.get("performance_index", 0.0))
        score = int(max(0.0, min(1.0, perf_idx)) * 10)
        return factor, score
    except Exception:
        return float("nan"), -1


# ═══════════════════════════════════════════════════════════════════════════
# RENDER ENHANCED TECHNICAL INDICATORS
# ═══════════════════════════════════════════════════════════════════════════


def render_technical_indicators(df_features: pd.DataFrame) -> None:
    """Display all engineered technical indicators."""
    st.subheader("📊 Technical Indicators & Features")

    # Group indicators by type
    indicator_groups = {
        "Moving Averages": [
            col
            for col in df_features.columns
            if "ma_" in col.lower() or "sma" in col.lower()
        ],
        "Momentum": [
            col
            for col in df_features.columns
            if any(x in col.lower() for x in ["rsi", "macd", "stoch", "kdj"])
        ],
        "Volatility": [
            col
            for col in df_features.columns
            if any(x in col.lower() for x in ["bb_", "atr", "std", "volatility"])
        ],
        "Volume": [col for col in df_features.columns if "volume" in col.lower()],
        "Price Patterns": [
            col
            for col in df_features.columns
            if any(x in col.lower() for x in ["supertrend", "pivot", "pattern"])
        ],
    }

    # Create tabs for each group
    tabs = st.tabs(list(indicator_groups.keys()))

    for tab, (group_name, indicators) in zip(tabs, indicator_groups.items()):
        with tab:
            if indicators:
                # Show latest values in columns
                cols = st.columns(min(3, len(indicators)))

                for i, indicator in enumerate(indicators[:9]):  # Show max 9 per group
                    with cols[i % 3]:
                        if indicator in df_features.columns:
                            value = df_features[indicator].iloc[-1]

                            # Format based on type
                            if isinstance(value, (int, np.integer)):
                                formatted = f"{value:,.0f}"
                            elif isinstance(value, (float, np.floating)):
                                if abs(value) > 1000:
                                    formatted = f"{value:,.0f}"
                                else:
                                    formatted = f"{value:.4f}"
                            else:
                                formatted = str(value)

                            st.metric(
                                label=indicator.replace("_", " ").title(),
                                value=formatted,
                                delta=None,
                            )
            else:
                st.info(f"No {group_name} indicators in this dataset")


# ═══════════════════════════════════════════════════════════════════════════
# RENDER FEATURE HEATMAP
# ═══════════════════════════════════════════════════════════════════════════


def render_feature_heatmap(df_features: pd.DataFrame) -> None:
    """Display normalized feature values as heatmap."""
    st.subheader("🔥 Feature Correlation Heatmap (Last 50 candles)")

    try:
        # Select last 50 rows and numeric columns only
        df_numeric = df_features.select_dtypes(include=[np.number]).iloc[-50:]

        if len(df_numeric.columns) > 5:
            # Show only top 20 features by variance
            top_features = df_numeric.var().nlargest(20).index.tolist()
            df_display = df_numeric[top_features]
        else:
            df_display = df_numeric

        # Create correlation matrix
        corr_matrix = df_display.corr()

        # Heatmap using Plotly
        fig = go.Figure(
            data=go.Heatmap(
                z=corr_matrix.values,
                x=corr_matrix.columns,
                y=corr_matrix.columns,
                colorscale="RdBu",
                zmid=0,
                colorbar=dict(title="Correlation"),
            )
        )

        fig.update_layout(title="Feature Correlation Matrix", height=500, width=700)

        st.plotly_chart(fig, width="stretch")

    except Exception as e:
        logger.warning(f"Could not render heatmap: {e}")
        st.warning("Heatmap unavailable")


# ═══════════════════════════════════════════════════════════════════════════
# MARKET HOURS FILTER
# ═══════════════════════════════════════════════════════════════════════════


def filter_to_market_hours_cst(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter to US market hours (CST timezone): 8:30 AM - 3:00 PM.

    Handles timezone conversion if data is in UTC or other timezone.
    Removes pre-market, after-hours, and weekend data.
    """
    if "Date" not in df.columns and "time" not in df.columns:
        logger.warning("[FILTER] No date/time column found, skipping filter")
        return df

    df_filtered = df.copy()
    time_col = "Date" if "Date" in df_filtered.columns else "time"

    # Ensure datetime
    if not pd.api.types.is_datetime64_any_dtype(df_filtered[time_col]):
        df_filtered[time_col] = pd.to_datetime(df_filtered[time_col])

    # Handle timezone conversion
    if df_filtered[time_col].dt.tz is not None:
        # Data has timezone - convert to CST
        logger.info(
            f"[FILTER] Converting from {df_filtered[time_col].dt.tz} to US/Central"
        )
        df_filtered[time_col] = df_filtered[time_col].dt.tz_convert("US/Central")
    else:
        # No timezone - try to infer
        try:
            # Assume UTC and convert to CST
            df_filtered[time_col] = (
                df_filtered[time_col].dt.tz_localize("UTC").dt.tz_convert("US/Central")
            )
            logger.info("[FILTER] Assumed UTC timezone, converted to US/Central")
        except Exception:
            # Already timezone-naive, assume it's in CST
            logger.info("[FILTER] Using timezone-naive data, assuming CST")
            pass

    # Remove timezone info for simpler comparison
    df_filtered[time_col] = df_filtered[time_col].dt.tz_localize(None)

    hour = df_filtered[time_col].dt.hour
    minute = df_filtered[time_col].dt.minute

    # Market hours: 8:30 AM - 3:00 PM CST
    market_hours = (
        # 9:00 AM - 2:59 PM (full hours)
        ((hour >= 9) & (hour < 15))
        |
        # 8:30 AM - 8:59 AM (partial hour at open)
        ((hour == 8) & (minute >= 30))
        |
        # Exactly 3:00 PM (market close)
        ((hour == 15) & (minute == 0))
    )

    df_filtered = df_filtered[market_hours]

    # Remove weekends (Monday=0, Sunday=6)
    df_filtered = df_filtered[df_filtered[time_col].dt.dayofweek < 5]

    # IMPORTANT: Sort by time (ascending) so most recent is LAST
    df_filtered = df_filtered.sort_values(time_col, ascending=True).reset_index(
        drop=True
    )

    rows_removed = len(df) - len(df_filtered)
    logger.info(
        f"[MARKET_HOURS] CST filter: {len(df)} → {len(df_filtered)} rows (removed {rows_removed} candles)"
    )

    return df_filtered


# ═══════════════════════════════════════════════════════════════════════════
# DEBUG DATA ISSUES
# ═══════════════════════════════════════════════════════════════════════════


def debug_data_issues(
    df_raw: pd.DataFrame, df_features: pd.DataFrame, symbol: str
) -> None:
    """Debug data loading issues."""
    with st.expander("🔧 DEBUG: Data Diagnostics", expanded=False):
        st.markdown("### Raw Data Info")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Rows", len(df_raw))
        with col2:
            st.metric("Columns", len(df_raw.columns))
        with col3:
            st.metric("Date Column", "Date" in df_raw.columns)
        with col4:
            st.metric("Has NaN", df_raw.isna().sum().sum())

        st.markdown("### Column Info")
        col_info = pd.DataFrame(
            {
                "Column": df_raw.columns,
                "Type": [str(df_raw[col].dtype) for col in df_raw.columns],
                "First Value": [str(df_raw[col].iloc[0]) for col in df_raw.columns],
                "Last Value": [str(df_raw[col].iloc[-1]) for col in df_raw.columns],
            }
        )
        st.dataframe(col_info, width="stretch")

        st.markdown("### Date Column Analysis")
        if "Date" in df_raw.columns:
            st.write(f"**Type**: {df_raw['Date'].dtype}")
            st.write(f"**First**: {df_raw['Date'].iloc[0]}")
            st.write(f"**Last**: {df_raw['Date'].iloc[-1]}")
            st.write(f"**Min**: {df_raw['Date'].min()}")
            st.write(f"**Max**: {df_raw['Date'].max()}")
        else:
            st.error("❌ No 'Date' column!")

        st.markdown("### First/Last Rows")
        st.write("**First 3 rows:**")
        st.dataframe(df_raw.head(3), width="stretch")
        st.write("**Last 3 rows:**")
        st.dataframe(df_raw.tail(3), width="stretch")


# ═══════════════════════════════════════════════════════════════════════════
# FALLBACK CHART RENDERER
# ═══════════════════════════════════════════════════════════════════════════


def render_plotly_chart(
    df_raw: pd.DataFrame,
    symbol: str,
    timeframe: str,
    predictions_all_levels: Optional[Dict] = None,
) -> bool:
    """
    Render Plotly chart with all confidence level overlays.

    Args:
        df_raw: OHLCV dataframe
        symbol: Stock symbol
        timeframe: Timeframe string
        predictions_all_levels: Optional dict with structure {'0.90': {...}, '0.95': {...}, '0.99': {...}}
    """
    try:
        logger.info(f"[CHART] Rendering chart for {symbol} {timeframe}")

        # Ensure date column
        if "Date" not in df_raw.columns:
            if "date" in df_raw.columns:
                df_raw = df_raw.rename(columns={"date": "Date"})
            else:
                return False

        # Create subplot with price and volume
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.7, 0.3],
            subplot_titles=(f"{symbol} {timeframe} (with ML Predictions)", "Volume"),
        )

        # Candlestick chart
        fig.add_trace(
            go.Candlestick(
                x=pd.to_datetime(df_raw["Date"]),
                open=df_raw["open"],
                high=df_raw["high"],
                low=df_raw["low"],
                close=df_raw["close"],
                name="OHLC",
            ),
            row=1,
            col=1,
        )

        # === ADD ALL CONFIDENCE LEVEL OVERLAYS ===
        confidence_colors = {
            "0.90": "rgba(255, 193, 7, 0.3)",  # Yellow (light)
            "0.95": "rgba(33, 150, 243, 0.3)",  # Blue (light)
            "0.99": "rgba(76, 175, 80, 0.3)",  # Green (light)
        }

        line_colors = {
            "0.90": "rgb(255, 193, 7)",  # Yellow (solid)
            "0.95": "rgb(33, 150, 243)",  # Blue (solid)
            "0.99": "rgb(76, 175, 80)",  # Green (solid)
        }

        if predictions_all_levels is not None:
            # Convert to DataFrame-per-confidence structure expected by renderer
            try:
                converted: Dict[str, pd.DataFrame] = {}
                for conf_key, pred_data in predictions_all_levels.items():
                    if pred_data is None:
                        continue
                    timestamps = pred_data.get("timestamps")
                    predictions = pred_data.get("predictions")
                    if timestamps is None or predictions is None:
                        continue
                    df_preds = pd.DataFrame(
                        {
                            "time": pd.to_datetime(timestamps),
                            "predicted_price": pd.to_numeric(
                                predictions, errors="coerce"
                            ),
                        }
                    )
                    # Drop NaNs and keep chronological order
                    df_preds = (
                        df_preds.dropna().sort_values("time").reset_index(drop=True)
                    )
                    converted[conf_key] = df_preds

                if converted:
                    fig = add_simple_forecast_dots(fig, converted, df_ohlcv=df_raw)
            except Exception as e:
                logger.warning(f"[CHART] Could not overlay simple forecast dots: {e}")

        # Volume bars
        colors = [
            "#26a69a" if c >= o else "#ef5350"
            for c, o in zip(df_raw["close"], df_raw["open"])
        ]
        fig.add_trace(
            go.Bar(
                x=pd.to_datetime(df_raw["Date"]),
                y=df_raw["volume"],
                name="Volume",
                marker_color=colors,
                showlegend=False,
            ),
            row=2,
            col=1,
        )

        # Extend x-axis to show prediction horizon
        if predictions_all_levels:
            max_pred_time = max(
                [pred["timestamps"].max() for pred in predictions_all_levels.values()]
            )
            xaxis_range = [
                pd.to_datetime(df_raw["Date"]).min(),
                max_pred_time + pd.Timedelta(days=1),
            ]
        else:
            xaxis_range = None

        fig.update_layout(
            title=f"{symbol} - {timeframe} (📊 ML Predictions Enabled)",
            height=600,
            xaxis_rangeslider_visible=False,
            template="plotly_dark",
            hovermode="x unified",
            xaxis=dict(range=xaxis_range) if xaxis_range else {},
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
            config={"responsive": True, "displayModeBar": True},
        )

        logger.info("[CHART] ✅ Chart rendered with all confidence levels")
        return True

    except Exception as e:
        logger.error(f"[CHART] Error: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════
# MAIN RENDER FUNCTION
# ═══════════════════════════════════════════════════════════════════════════


def render():
    """Main trading dashboard render function."""

    # Header
    st.title("🔥 Live Trading Dashboard")
    st.markdown("**Real-time stock analysis with ML-engineered features**")
    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 5: MULTI-SYMBOL BATCH + SUPERTREND HEATMAP
    # ═══════════════════════════════════════════════════════════════════
    with st.expander("🧪 Multi-Symbol Batch (Phase 5)", expanded=False):
        symbols_input = st.multiselect(
            "Select Symbols", ["CRWD", "NVDA", "TSLA", "AAPL"], default=["CRWD", "NVDA"]
        )
        timeframes_multi = st.multiselect(
            "Timeframes", ["1h", "4h", "1d"], default=["1h", "4h", "1d"]
        )
        if symbols_input and timeframes_multi:
            with st.spinner("Batch fetching and engineering features..."):
                batch_data = batch_fetch_data(symbols_input, timeframes_multi, days=730)

            # Build SuperTrend Heatmap data
            heatmap_rows = []
            columns = (
                ["Symbol"]
                + [f"{tf} Factor" for tf in timeframes_multi]
                + [f"{tf} Score" for tf in timeframes_multi]
            )
            for sym in symbols_input:
                row_vals = [sym]
                # First all factors, then all scores to keep table compact
                factors_tmp = []
                scores_tmp = []
                for tf in timeframes_multi:
                    df_tf = batch_data.get(sym, {}).get(tf, pd.DataFrame())
                    if not df_tf.empty:
                        fct, scr = compute_supertrend_factor_score(df_tf)
                        factors_tmp.append(None if np.isnan(fct) else round(fct, 2))
                        scores_tmp.append("N/A" if scr < 0 else f"{scr}/10")
                    else:
                        factors_tmp.append(None)
                        scores_tmp.append("N/A")
                row_vals.extend(factors_tmp + scores_tmp)
                heatmap_rows.append(row_vals)

            try:
                st.subheader("SuperTrend Heatmap: Factor & Score per Symbol/TF")
                df_heat = pd.DataFrame(heatmap_rows, columns=columns)
                st.dataframe(df_heat, use_container_width=True)
            except Exception as e:
                st.warning(f"Heatmap unavailable: {e}")

            # Per-symbol charts (side-by-side per TF)
            for sym in symbols_input:
                st.subheader(f"{sym} Analysis")
                cols_multi = st.columns(len(timeframes_multi))
                for i, tf in enumerate(timeframes_multi):
                    with cols_multi[i]:
                        df_tf = batch_data.get(sym, {}).get(tf, pd.DataFrame())
                        if df_tf is not None and not df_tf.empty:
                            try:
                                df_chart = df_tf.rename(
                                    columns={
                                        "Date": "time",
                                        "Open": "open",
                                        "High": "high",
                                        "Low": "low",
                                        "Close": "close",
                                        "Volume": "volume",
                                    }
                                )
                                fig_st = create_supertrend_plot(
                                    df_chart,
                                    df_historical=None,
                                    symbol=sym,
                                    timeframe=tf,
                                )
                                st.plotly_chart(fig_st, use_container_width=True)
                            except Exception:
                                st.caption("Chart unavailable")
                        else:
                            st.caption("No data")

            # SageMaker cloud predictions (optional)
            try:
                from core.sagemaker_client import (
                    predict_multi_symbol,
                )  # root-level core/

                if st.button("Get Cloud Predictions (SageMaker)"):
                    with st.spinner("Contacting SageMaker endpoint..."):
                        cloud_preds = predict_multi_symbol(
                            symbols_input, timeframes_multi
                        )
                    if cloud_preds:
                        st.json(cloud_preds)
                        st.success("Cloud predictions received")
                    else:
                        st.warning("SageMaker unavailable—using local SuperTrend")
            except Exception as e:
                st.caption(f"Cloud prediction client unavailable: {str(e)[:60]}")

            # Local FastAPI mock test
            if st.button("Test Local Mock Endpoint"):
                try:
                    import requests

                    resp = requests.post(
                        "http://localhost:8000/predict",
                        json={"symbols": symbols_input, "timeframes": timeframes_multi},
                    )
                    st.write(resp.status_code)
                    if resp.status_code == 200:
                        st.json(resp.json())
                    else:
                        st.warning("Mock server did not respond 200")
                except Exception as e:
                    st.warning(f"Mock test failed: {e}")

    # Initialize session state
    init_session_state()

    # ═══════════════════════════════════════════════════════════════════
    # SIDEBAR - CONTROLS
    # ═══════════════════════════════════════════════════════════════════

    with st.sidebar:
        st.header("⚙️ Controls")

        # Symbol input (TEXT, not dropdown)
        symbol_col1, symbol_col2 = st.columns([3, 1])

        with symbol_col1:
            symbol_raw = st.text_input(
                "🔍 Stock Symbol",
                value=st.session_state.get("current_symbol", "AAPL"),
                placeholder="e.g., AAPL, MSFT, SPY",
                help="Enter any valid stock ticker",
            )
            # Harden against None and whitespace
            symbol_input = (
                symbol_raw
                if symbol_raw is not None
                else st.session_state.get("current_symbol", "AAPL")
            )
            symbol = (
                str(symbol_input).upper().strip()
                if str(symbol_input).strip()
                else st.session_state.get("current_symbol", "AAPL")
            )
            st.session_state["current_symbol"] = symbol

        with symbol_col2:
            st.write("")  # Spacing
            if st.button("✨", help="Random from preset"):
                st.session_state["current_symbol"] = np.random.choice(
                    ["AAPL", "MSFT", "GOOGL", "TSLA", "SPY"]
                )
                st.rerun()

        # Quick presets
        st.markdown("**Quick Access:**")
        preset_cols = st.columns(4)
        presets = ["AAPL", "MSFT", "SPY", "QQQ"]
        for i, preset in enumerate(presets):
            with preset_cols[i]:
                if st.button(preset, use_container_width=True, key=f"preset_{preset}"):
                    st.session_state["current_symbol"] = preset
                    st.rerun()

        st.markdown("---")

        # Timeframe selection
        timeframe = st.selectbox(
            "📊 Timeframe",
            options=["1h", "4h", "1d"],
            index=2,
            help="1h: Intraday, 4h: Medium-term, 1d: Daily",
        )
        st.session_state["current_timeframe"] = timeframe

        # Load lookback config
        import yaml
        from pathlib import Path

        config_path = Path("main_production_system/config/lookback_config.yaml")
        if config_path.exists():
            with open(config_path, "r") as f:
                lookback_config = yaml.safe_load(f)
        else:
            # Fallback defaults
            lookback_config = {
                "lookback_windows": {
                    "1h": {"optimal_candles": 504},
                    "4h": {"optimal_candles": 126},
                    "1d": {"optimal_candles": 252},
                },
                "prediction_horizons": {"1h": 24, "4h": 30, "1d": 60},
                "confidence_levels": [0.90, 0.95, 0.99],
            }

        # Display current settings (read-only)
        st.markdown("---")
        st.subheader("⚙️ Data Configuration")
        st.info(
            f"**Current Settings:**\n\n"
            f"🕐 Timeframe: {timeframe}\n"
            f"📊 Optimal Lookback: {lookback_config['lookback_windows'][timeframe]['optimal_candles']} candles\n"
            f"📈 Prediction Horizon: {lookback_config['prediction_horizons'][timeframe]} steps\n"
            f"🎯 Confidence Levels: 90% (Yellow), 95% (Blue), 99% (Green)"
        )
        st.caption(
            "💡 Tip: Data and predictions auto-adjust based on timeframe selection"
        )

        # Set days based on timeframe (do NOT expose to slider)
        lookback_candles = lookback_config["lookback_windows"][timeframe][
            "optimal_candles"
        ]
        # Convert candles to approximate days
        if timeframe == "1h":
            days = max(21, int(lookback_candles / 24))  # ~21 days
        elif timeframe == "4h":
            days = max(21, int(lookback_candles / 6))  # ~21 days
        else:  # 1d
            days = lookback_config["lookback_windows"][timeframe][
                "optimal_candles"
            ]  # 252 days

        # Store in session state
        st.session_state["days"] = days
        st.session_state["lookback_days"] = days

        # Data source selection
        st.markdown("---")
        st.subheader("📡 Data Source")
        data_provider = st.selectbox(
            "Primary Provider (Fallback Auto)",
            options=["auto", "yahoo_finance", "alpha_vantage", "polygon"],
            index=0,
            help="Auto: yfinance first (unlimited), then Alpha Vantage; Polygon as fallback",
        )
        st.session_state["data_provider"] = data_provider

        # Polygon toggle (derived if provider explicitly chosen)
        default_use_polygon = timeframe in ["1h", "4h"]
        derived_use_polygon = (
            True
            if data_provider == "polygon"
            else (
                False
                if data_provider in ["yahoo_finance", "alpha_vantage"]
                else default_use_polygon
            )
        )
        use_polygon = st.checkbox(
            "🌐 Use Polygon.io",
            value=derived_use_polygon,
            help="Enable for intraday if you prefer Polygon over yfinance",
        )
        st.session_state["use_polygon"] = use_polygon

        st.markdown("---")

        # Refresh buttons
        col1, col2 = st.columns([2, 1])
        with col1:
            if st.button("🔄 Refresh Data", use_container_width=True):
                st.session_state["last_update"] = datetime.now()
                st.rerun()
        with col2:
            if st.button("⚡", help="Force reload"):
                st.cache_data.clear()
                st.rerun()

        st.markdown("---")

        # Model Status and Reload
        st.subheader("🤖 ML Models")
        models = st.session_state.get("models", {})

        # Check model availability
        from main_production_system.dashboard.core.model_manager import get_model_status

        model_status = (
            get_model_status(models)
            if models
            else {"models_loaded": 0, "message": "No models available"}
        )
        models_loaded = model_status.get("models_loaded", 0)

        if models_loaded == 0:
            st.warning("⚠️ ML Model unavailable - predictions disabled")
            st.caption("Expected path: `./xgboost_tuned_model.pkl`")
            st.caption("Or set `MODEL_PATH` environment variable")
        else:
            st.success(f"✅ {models_loaded} model(s) ready")

        # Reload models button
        if st.button(
            "🔄 Reload ML Models",
            use_container_width=True,
            help="Reload models without restarting app",
        ):
            try:
                with st.spinner("Reloading models..."):
                    # Clear cache
                    from main_production_system.dashboard.core.cache_manager import (
                        initialize_models_in_session,
                    )

                    st.cache_resource.clear()
                    st.session_state["models"] = {}
                    # Reload
                    new_models = initialize_models_in_session()
                    st.session_state["models"] = new_models
                    st.session_state["last_model_reload"] = datetime.now()
                    st.success("✅ Models reloaded!")
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Reload failed: {str(e)[:100]}")
                logger.error(f"Model reload failed: {e}", exc_info=True)

        # Show last reload time if available
        if "last_model_reload" in st.session_state:
            st.caption(
                f"Last reload: {st.session_state['last_model_reload'].strftime('%H:%M:%S')}"
            )

        # Store prediction settings (always enabled, using config)
        st.session_state["show_predictions"] = True  # Always show predictions
        if config_path.exists():
            st.session_state["prediction_horizons"] = lookback_config[
                "prediction_horizons"
            ][timeframe]
            st.session_state["confidence_levels"] = lookback_config["confidence_levels"]

        st.markdown("---")
        st.caption(
            f"Last update: {st.session_state['last_update'].strftime('%H:%M:%S')}"
        )

    # ═══════════════════════════════════════════════════════════════════
    # MAIN CONTENT
    # ═══════════════════════════════════════════════════════════════════

    data_pipeline = get_data_pipeline()
    if data_pipeline is None:
        st.error("❌ Data pipeline unavailable")
        return

    # Load data with market hours enforcement
    try:
        with st.spinner("📊 Loading market hours data from TimescaleDB..."):
            # Show market status
            get_calendar = data_pipeline.get("get_market_calendar")
            if get_calendar:
                calendar_instance = get_calendar()
                market_status = calendar_instance.format_trading_status()
                st.info(f"Market Status: {market_status}")

            # Determine candle count
            candle_config = {"1h": 1000, "4h": 500, "1d": 1000}
            candle_count = candle_config.get(timeframe, 252)

            # Session type selector
            col1, col2 = st.columns(2)
            with col1:
                session_type = st.radio(
                    "Session Type",
                    ["regular", "extended", "full"],
                    index=0,
                    help="Regular: 9:30-4:00 ET | Extended: 4:00 AM-4:00 PM | Full: 4:00 AM-8:00 PM",
                )

            # Try TimescaleDB market hours first
            try:
                get_timescale_market_hours = data_pipeline.get(
                    "get_data_and_features_timescale_market_hours"
                )
                if get_timescale_market_hours:
                    df_raw, df_features = get_timescale_market_hours(
                        symbol=symbol,
                        timeframe=timeframe,
                        candle_count=candle_count,
                        session_type=session_type,
                    )
                    st.success(
                        f"✅ Loaded {len(df_raw)} market-hours candles for {symbol}"
                    )
                else:
                    # Fallback to standard pipeline
                    raise AttributeError("TimescaleDB not available")
            except (AttributeError, RuntimeError, Exception) as e:
                # Fallback to standard pipeline
                logger.warning(f"TimescaleDB unavailable, using standard pipeline: {e}")
                df_raw, df_features = data_pipeline[
                    "get_data_and_features_with_friendly_errors"
                ](
                    symbol=symbol,
                    timeframe=timeframe,
                    days=days,
                    use_polygon=use_polygon,
                )

                # Apply market hours filter for intraday data
                if timeframe in ["1h", "4h"]:
                    df_raw_original = df_raw.copy()
                    df_raw = filter_to_market_hours_cst(df_raw)

                    # Debug output
                    with st.expander("📊 Market Hours Filtering", expanded=False):
                        st.markdown("**Before filtering:**")
                        st.write(f"- Total rows: {len(df_raw_original)}")
                        if (
                            "Date" in df_raw_original.columns
                            and len(df_raw_original) > 0
                        ):
                            st.write(
                                f"- Last timestamp: {df_raw_original['Date'].iloc[-1]}"
                            )
                            st.write(
                                f"- Last close: ${df_raw_original['close'].iloc[-1]:.2f}"
                            )

                        st.markdown("**After filtering (market hours only):**")
                        st.write(f"- Total rows: {len(df_raw)}")
                        if "Date" in df_raw.columns and len(df_raw) > 0:
                            st.write(f"- Last timestamp: {df_raw['Date'].iloc[-1]}")
                            st.write(f"- Last close: ${df_raw['close'].iloc[-1]:.2f}")

                        st.info(
                            f"📊 Filtered to market hours: {len(df_raw_original)} → {len(df_raw)} candles "
                            f"(removed {len(df_raw_original) - len(df_raw)} after-hours candles)"
                        )

                    logger.info(
                        f"[FILTER] Market hours filter: {len(df_raw_original)} → {len(df_raw)} rows"
                    )
    except data_pipeline["UserFriendlyError"] as e:
        e.display_in_streamlit()
        return
    except Exception as e:
        st.error(f"❌ Error loading data: {str(e)[:100]}")
        logger.error(f"Data load failed: {e}")
        return

    if df_raw is None or df_raw.empty:
        st.error(f"❌ No data for {symbol}")
        return

    # ═══════════════════════════════════════════════════════════════════
    # DEBUG DATA ISSUES (TEMPORARY)
    # ═══════════════════════════════════════════════════════════════════

    debug_data_issues(df_raw, df_features, symbol)

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 1: KEY METRICS (TOP)
    # ═══════════════════════════════════════════════════════════════════

    metric_cols = st.columns(5)

    with metric_cols[0]:
        latest_close = df_raw["close"].iloc[-1] if "close" in df_raw.columns else 0
        st.metric("Latest Close", f"${latest_close:.2f}")

    with metric_cols[1]:
        latest_high = df_raw["high"].iloc[-1] if "high" in df_raw.columns else 0
        st.metric("High", f"${latest_high:.2f}")

    with metric_cols[2]:
        latest_low = df_raw["low"].iloc[-1] if "low" in df_raw.columns else 0
        st.metric("Low", f"${latest_low:.2f}")

    with metric_cols[3]:
        if latest_close and len(df_raw) > 1:
            prev_close = df_raw["close"].iloc[-2]
            change = latest_close - prev_close
            change_pct = (change / prev_close) * 100 if prev_close != 0 else 0
            st.metric("Change", f"{change_pct:+.2f}%", f"${change:+.2f}")

    with metric_cols[4]:
        st.metric("Candles", len(df_raw))

    # ═══════════════════════════════════════════════════════════════════
    # DATA FRESHNESS INDICATOR
    # ═══════════════════════════════════════════════════════════════════

    if "Date" in df_raw.columns and len(df_raw) > 0:
        try:
            last_timestamp = pd.to_datetime(df_raw["Date"].iloc[-1])
            now_cst = datetime.now()

            # Calculate age in minutes
            if pd.notna(last_timestamp):
                # Ensure both are timezone-naive for comparison
                if (
                    hasattr(last_timestamp, "tzinfo")
                    and last_timestamp.tzinfo is not None
                ):
                    last_timestamp = last_timestamp.tz_localize(None)

                time_diff = now_cst - last_timestamp
                minutes_old = time_diff.total_seconds() / 60

                # Color-code freshness
                if minutes_old < 5:
                    color = "🟢"
                    status = "LIVE"
                elif minutes_old < 60:
                    color = "🟡"
                    status = "RECENT"
                else:
                    color = "🔴"
                    status = "DELAYED"

                st.info(
                    f"{color} **Data Status: {status}**  \n"
                    f"Last updated: {last_timestamp.strftime('%b %d, %I:%M %p')} CST  \n"
                    f"({int(minutes_old)} minutes ago)"
                )
        except Exception as e:
            logger.warning(f"Could not calculate data freshness: {e}")
            st.caption("⚠️ Data timestamp unavailable")

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════════
    # SECTION: SUPERTrend AI (FIRST) - K-Means Adaptive Factor
    # ═══════════════════════════════════════════════════════════════════
    try:
        st.subheader("🟢 SuperTrend AI: K-Means Adaptive")
        st.caption(
            "Adaptive factor via K-Means clustering (1-5x ATR, Best cluster); Perf AMA support/resistance; Score 0-10 signal strength"
        )

        # Fetch extended historical data for stable K-Means clustering (10K bars target)
        df_historical = None
        try:
            df_historical, _ = data_pipeline[
                "get_data_and_features_with_friendly_errors"
            ](
                symbol=symbol,
                timeframe=timeframe,
                historical_days=None,  # Auto-calculate for 10K bars
                use_polygon=use_polygon,
            )
            logger.info(
                f"[SUPERTR AI] Loaded {len(df_historical)} historical bars for K-Means (vs {len(df_raw)} display bars)"
            )
        except Exception as e:
            logger.warning(
                f"[SUPERTR AI] Could not load historical data, using display window: {e}"
            )
            df_historical = df_raw

        supertrend_ai_fig = create_supertrend_plot(
            df_raw,
            df_historical=df_historical,
            symbol=symbol,
            timeframe=timeframe,
            atr_length=10,
            min_mult=1,
            max_mult=5,
            step=0.5,
            perf_alpha=10,
            from_cluster="Best",
        )
        st.plotly_chart(supertrend_ai_fig, use_container_width=True)
    except Exception as e:
        logger.error(f"SuperTrend AI plot failed: {e}")
        import traceback

        logger.error(traceback.format_exc())
        st.warning(f"SuperTrend AI unavailable: {str(e)[:100]}")

    # ═══════════════════════════════════════════════════════════════════
    # GENERATE ML PREDICTIONS (ALL CONFIDENCE LEVELS)
    # ═══════════════════════════════════════════════════════════════════

    predictions_all_levels = None
    prediction_result = None  # For ensemble breakdown

    if st.session_state.get("show_predictions", False) and ML_PREDICTIONS_AVAILABLE:
        try:
            models = st.session_state.get("models", {})
            if models:
                logger.info(f"[RENDER] Generating predictions for {timeframe}...")
                with st.spinner(
                    "Generating ML predictions for all confidence levels..."
                ):
                    # Generate price predictions for all confidence levels (guard callable)
                    func = generate_price_predictions_all_levels
                    predictions_all_levels = None
                    if callable(func):
                        predictions_all_levels = func(
                            df_features=df_features,
                            _models=models,
                            _symbol=symbol,
                            _timeframe=timeframe,
                        )

                    # Also generate prediction result for ensemble breakdown
                    try:
                        from main_production_system.dashboard.core.model_manager import (
                            predict_signal,
                        )

                        prediction_result = predict_signal(
                            df_features=df_features,
                            models_dict=models,
                            df_ohlcv=df_raw,
                            symbol=symbol,  # Add symbol for Perplexity enrichment
                        )
                    except Exception as e:
                        logger.warning(
                            f"Could not generate prediction result for breakdown: {e}"
                        )
                        prediction_result = None

                if predictions_all_levels:
                    # Persist for downstream renderers (e.g., simple forecast dots/table)
                    st.session_state["predictions_all_levels"] = predictions_all_levels
                    st.success(
                        f"✅ ML Predictions generated for {len(predictions_all_levels)} confidence levels"
                    )
                else:
                    st.warning("⚠️ Prediction generation failed")
            else:
                st.info("ℹ️ Models not loaded - predictions unavailable")
        except Exception as e:
            logger.error(f"Prediction generation failed: {e}", exc_info=True)
            st.error(f"Prediction error: {str(e)[:100]}")

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 2: PRICE CHART (FULL WIDTH)
    # ═══════════════════════════════════════════════════════════════════

    st.subheader("📈 Price Chart")

    try:
        from main_production_system.dashboard.charts.lightweight_chart_builder import (
            create_ohlcv_chart,
        )

        chart_success = create_ohlcv_chart(
            df_raw, symbol=symbol, timeframe=timeframe, height=600
        )

        if not chart_success:
            st.warning("⚠️ Chart rendering failed - showing Plotly fallback")

            # Plotly fallback with ML predictions support
            render_plotly_chart(
                df_raw, symbol, timeframe, predictions_all_levels=predictions_all_levels
            )

        # Debug overlay: optional Plotly figure with forecast dots
        with st.expander("🔧 DEBUG: Forecast Dots Overlay", expanded=False):
            if "predictions_all_levels" in st.session_state:
                preds = st.session_state["predictions_all_levels"]
                if preds:
                    # Show quick counts per confidence level
                    try:
                        counts = {}
                        for k, v in preds.items():
                            if isinstance(v, dict):
                                plist = v.get("predictions") or []
                                try:
                                    counts[k] = len(plist)
                                except Exception:
                                    counts[k] = 0
                    except Exception:
                        counts = {}
                    st.write("Predictions loaded:", counts)

                    try:
                        # Convert to DataFrame-per-confidence
                        converted: Dict[str, pd.DataFrame] = {}
                        for conf_key in ["0.99", "0.95", "0.90"]:
                            pred_data = preds.get(conf_key)
                            if not isinstance(pred_data, dict):
                                continue
                            timestamps = pred_data.get("timestamps")
                            predictions_vals = pred_data.get("predictions")
                            if timestamps is None or predictions_vals is None:
                                continue
                            df_preds = pd.DataFrame(
                                {
                                    "time": pd.to_datetime(timestamps),
                                    "predicted_price": pd.to_numeric(
                                        predictions_vals, errors="coerce"
                                    ),
                                }
                            ).dropna()
                            if not df_preds.empty:
                                converted[conf_key] = df_preds

                        # Build a fresh Plotly figure with candles
                        fig = go.Figure()
                        if all(
                            col in df_raw.columns
                            for col in ["Date", "open", "high", "low", "close"]
                        ):
                            fig.add_trace(
                                go.Candlestick(
                                    x=pd.to_datetime(df_raw["Date"]),
                                    open=df_raw["open"],
                                    high=df_raw["high"],
                                    low=df_raw["low"],
                                    close=df_raw["close"],
                                    name="OHLC",
                                )
                            )

                        # Add forecast dots
                        fig = add_simple_forecast_dots(fig, converted, df_raw)
                        st.success("✅ Forecast dots added to chart")

                        fig.update_layout(
                            template="plotly_dark",
                            height=600,
                            xaxis_rangeslider_visible=False,
                        )
                        st.plotly_chart(fig, use_container_width=True)

                        # Forecast details table
                        forecast_df = add_forecast_table(converted if converted else {})
                        if len(forecast_df) > 0:
                            for col in ["90% Forecast", "95% Forecast", "99% Forecast"]:
                                if col in forecast_df.columns:
                                    forecast_df[col] = forecast_df[col].apply(
                                        lambda x: f"${x:.2f}" if pd.notna(x) else "N/A"
                                    )
                            st.dataframe(forecast_df, use_container_width=True)
                        else:
                            st.info("No forecast data in table")
                    except Exception as e:
                        st.error(f"Error adding dots: {e}")
                else:
                    st.info("No predictions in session state")

    except Exception as e:
        st.error(f"Chart error: {str(e)[:100]}")
        logger.error(f"Chart failed: {e}", exc_info=True)
        # Final fallback
        render_plotly_chart(
            df_raw, symbol, timeframe, predictions_all_levels=predictions_all_levels
        )

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════════
    # SECTION: OPTIMIZED MODEL TRAINING
    # ═══════════════════════════════════════════════════════════════════
    with st.expander("🔬 Train Optimized Model (XGBoost + Optuna)", expanded=False):
        st.markdown("### Advanced Model Training")
        st.caption(
            "Train XGBoost with holdout validation, optional Optuna tuning, PCA, and GPU acceleration"
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            train_max_window = st.number_input(
                "Warm-up Window",
                min_value=20,
                max_value=100,
                value=45,
                help="Number of initial rows to exclude (feature warm-up period)",
            )

        with col2:
            train_tune = st.checkbox(
                "Enable Optuna Tuning",
                value=False,
                help="Hyperparameter optimization (50 trials, ~5min runtime)",
            )

        with col3:
            train_pca = st.checkbox(
                "Enable PCA",
                value=False,
                help="Dimensionality reduction (95% variance)",
            )

        if st.button("🚀 Train Optimized Model", use_container_width=True):
            try:
                with st.spinner(f"Training model on {symbol} ({timeframe})..."):
                    from scripts.train_with_optimizations import run_optimized_training

                    # Run training
                    results = run_optimized_training(
                        symbol=symbol,
                        max_window=train_max_window,
                        tune_hyperparams=train_tune,
                        n_trials=50,
                        period="3mo",
                        interval=timeframe,
                        use_pca=train_pca,
                        use_gpu=False,  # Auto-detect CUDA
                    )

                    # Display results
                    st.success("✅ Training Complete!")

                    # Metrics
                    metric_cols = st.columns(4)
                    with metric_cols[0]:
                        st.metric("Test MSE", f"{results['test_mse']:.6f}")
                    with metric_cols[1]:
                        st.metric("Test RMSE", f"{results['test_rmse']:.6f}")
                    with metric_cols[2]:
                        st.metric(
                            "CV MSE",
                            f"{results['cv_mse']:.6f}" if results["cv_mse"] else "N/A",
                        )
                    with metric_cols[3]:
                        train_total = results["train_rows"] + results["test_rows"]
                        st.metric("Data Usage", f"{train_total} rows")

                    # Performance assessment
                    test_mse = results["test_mse"]
                    if test_mse < 0.0001:
                        st.success("🎯 EXCELLENT: Test MSE < 0.0001 (well-generalized)")
                    elif test_mse < 0.0005:
                        st.info("✅ GOOD: Test MSE < 0.0005")
                    elif test_mse < 0.001:
                        st.warning("⚠️ FAIR: Test MSE < 0.001 (consider tuning)")
                    else:
                        st.error("❌ POOR: Test MSE >= 0.001 (enable Optuna tuning)")

                    # Display chart
                    st.plotly_chart(results["fig"], use_container_width=True)

                    # Show best params if tuning was enabled
                    if train_tune and results.get("best_params"):
                        with st.expander(
                            "📊 Optimized Hyperparameters", expanded=False
                        ):
                            st.json(results["best_params"])

                    # PCA info
                    if train_pca and results.get("pca"):
                        st.info(
                            f"📉 PCA: Reduced to {results['pca'].n_components_} components (95% variance)"
                        )

                    st.caption(f"Model saved to: {results['output_path']}")

            except Exception as e:
                st.error(f"❌ Training failed: {str(e)[:200]}")
                logger.error(f"Model training failed: {e}", exc_info=True)

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════════
    # SECTION (LAST): FORECASTING OVERLAY (Prophet/XGB/Blend + Vol bands)
    # ═══════════════════════════════════════════════════════════════════
    try:
        st.subheader("� Forecasting (Ensemble Blend)")
        preds_dict: Dict = (
            prediction_result if isinstance(prediction_result, dict) else {}
        )
        vol_val = preds_dict.get("vol_forecast", None)
        fig_fc = create_forecasting_plot(
            df_raw,
            preds_dict,
            garch_vol=float(vol_val) if vol_val is not None else 0.015,
        )
        st.plotly_chart(fig_fc, use_container_width=True)
        st.caption(
            "Order: SuperTrend → Price → Forecasting (aligned on time axis); vol bands reflect GARCH blend"
        )
    except Exception as e:
        logger.debug(f"Forecasting plot failed: {e}")
        st.info("Forecast plot unavailable")

    # ═══════════════════════════════════════════════════════════════════
    # ENSEMBLE BREAKDOWN (if predictions enabled)
    # ═══════════════════════════════════════════════════════════════════

    if (
        st.session_state.get("show_predictions", False)
        and prediction_result is not None
        and ML_PREDICTIONS_AVAILABLE
    ):
        try:
            from main_production_system.dashboard.components.ensemble_breakdown import (
                render_ensemble_breakdown,
            )

            models = st.session_state.get("models", {})
            render_ensemble_breakdown(prediction_result, models)
            st.markdown("---")
        except Exception as e:
            logger.warning(f"Could not render ensemble breakdown: {e}")

    # ═══════════════════════════════════════════════════════════════════
    # GARCH VOLATILITY BLEND (ES + Stock)
    # ═══════════════════════════════════════════════════════════════════
    if (
        prediction_result
        and isinstance(prediction_result, dict)
        and "vol_forecast" in prediction_result
    ):
        try:
            st.subheader("📈 GARCH Volatility Blend (ES Futures)")
            vol_forecast = prediction_result.get("vol_forecast")
            es_vol = prediction_result.get("es_vol")
            stock_vol = prediction_result.get("stock_vol")
            vol_factor = prediction_result.get("vol_factor")
            confidence = prediction_result.get("confidence")

            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("Blended Vol", f"{vol_forecast:.2%}")
            with m2:
                st.metric(
                    "ES Market Vol", f"{es_vol:.2%}" if es_vol is not None else "—"
                )
            with m3:
                st.metric(
                    "Stock Vol", f"{stock_vol:.2%}" if stock_vol is not None else "—"
                )
            with m4:
                st.metric(
                    "Confidence Adj.",
                    f"{(confidence if confidence is not None else 0):.1%}",
                    delta=(
                        f"Vol factor {vol_factor:.0%}"
                        if vol_factor is not None
                        else None
                    ),
                )

            with st.expander("🔍 GARCH Params (ω, α, β)"):
                params = prediction_result.get("garch_params", {})
                try:
                    st.json(params)
                except Exception:
                    st.write(params)
            st.caption(
                "• 70% ES (market risk) + 30% stock (idiosyncratic)\n• High vol dampens signals for better risk mgmt"
            )
        except Exception as e:
            logger.debug(f"[UI] GARCH section failed: {e}")

    # ═══════════════════════════════════════════════════════════════════
    # DEBUG: Feature & Model Status (NEW)
    # ═══════════════════════════════════════════════════════════════════
    with st.expander("🔧 Debug: Features & Models Status"):
        # Feature count validation
        if df_features is not None:
            feature_cols = [
                col
                for col in df_features.columns
                if col not in ["Date", "Open", "High", "Low", "Close", "Volume"]
            ]
            total_features = len(feature_cols)
            expected_features = 66  # Baseline expectation

            col1, col2, col3 = st.columns(3)
            with col1:
                status_emoji = "✅" if 60 <= total_features <= 100 else "⚠️"
                st.metric("Total Features", f"{total_features} {status_emoji}")
            with col2:
                match_status = "Match" if 60 <= total_features <= 100 else "Mismatch"
                st.metric("Status", match_status)
            with col3:
                st.metric("Expected Range", "66-100")

            # Critical features check
            critical_features = [
                "RSI",
                "MACD",
                "MACD_Signal",
                "MACD_Histogram",
                "KDJ_K",
                "KDJ_D",
                "SuperTrend",
                "Volume_SMA",
                "BB_Upper",
                "BB_Lower",
                "BB_Middle",
            ]
            available_critical = [
                f for f in critical_features if f in df_features.columns
            ]
            missing_critical = [
                f for f in critical_features if f not in df_features.columns
            ]

            st.write("**Critical Features:**")
            if missing_critical:
                st.warning(
                    f"⚠️ Missing {len(missing_critical)}: {', '.join(missing_critical)}"
                )
            else:
                st.success(f"✅ All {len(critical_features)} critical features present")

            if available_critical:
                st.write(
                    f"Available ({len(available_critical)}): {', '.join(available_critical[:8])}"
                )
                if len(available_critical) > 8:
                    st.caption(f"...and {len(available_critical) - 8} more")
        else:
            st.warning("⚠️ No engineered features available (data loading issue)")

        # Model status
        st.write("**Model Status:**")
        models = st.session_state.get("models", {})

        if models:
            model_status = []
            for model_name, model_obj in models.items():
                is_loaded = model_obj is not None
                expected_features = getattr(model_obj, "n_features_in_", "Unknown")
                status_icon = "✅" if is_loaded else "❌"
                model_status.append(
                    {
                        "Model": model_name.capitalize(),
                        "Status": f"{status_icon} {'Loaded' if is_loaded else 'Missing'}",
                        "Expected Features": str(expected_features),
                    }
                )

            st.dataframe(
                pd.DataFrame(model_status), use_container_width=True, hide_index=True
            )
        else:
            st.info("ℹ️ Models not loaded yet (run prediction to load)")

        # Ensemble components
        if prediction_result and prediction_result.get("component_breakdown"):
            st.write("**Ensemble Components:**")
            breakdown = prediction_result["component_breakdown"]
            components = []
            for comp_name, comp_data in breakdown.items():
                if isinstance(comp_data, dict):
                    signal = comp_data.get("signal", "N/A")
                    confidence = comp_data.get("confidence", 0.0)
                    components.append(
                        {
                            "Component": comp_name,
                            "Signal": signal,
                            "Confidence": f"{confidence:.2%}",
                        }
                    )

            if components:
                st.dataframe(
                    pd.DataFrame(components), use_container_width=True, hide_index=True
                )

        # System info
        try:
            from main_production_system import __version__

            version_str = __version__
        except ImportError:
            version_str = "2.0.0"
        st.caption(
            f"System Version: {version_str} | Feature Pipeline: v2.0 (66+ features)"
        )
        st.caption(f"Data: {len(df_raw)} rows, {timeframe} timeframe, Symbol: {symbol}")

    # ═══════════════════════════════════════════════════════════════════
    # ARIMA-GARCH & ES MARKET REGIME DISPLAY
    # ═══════════════════════════════════════════════════════════════════

    if prediction_result is not None:
        # Market Regime Section (ES Futures)
        st.subheader("🌍 Market Regime (ES Futures)")
        if prediction_result.get("es_market_vol") is not None:
            col1, col2 = st.columns(2)
            with col1:
                es_vol = prediction_result.get("es_market_vol", 0)
                st.metric(
                    "ES Volatility",
                    f"{es_vol:.2%}",
                    help="Expected volatility from ES futures market regime model",
                )
            with col2:
                market_adjust = prediction_result.get("market_adjust", 0)
                st.metric(
                    "Market Adjustment",
                    f"{market_adjust:+.2f}",
                    help="Market regime adjustment applied to ensemble (high vol = penalty, low vol = boost)",
                )

            # Market regime interpretation
            if es_vol > 0.02:
                st.warning(
                    "⚠️ High market volatility detected - market adjustment applied"
                )
            elif es_vol < 0.01:
                st.success("✅ Low market volatility - favorable conditions")
            else:
                st.info("ℹ️ Moderate market volatility")
        else:
            st.info("ES market model not available - market regime adjustment disabled")

        st.markdown("---")

        # ARIMA-GARCH Volatility Forecast Section
        st.subheader("📊 Volatility Forecast (ARIMA-GARCH)")
        if prediction_result.get("arima_volatility") is not None:
            col1, col2, col3 = st.columns(3)
            with col1:
                arima_vol = prediction_result.get("arima_volatility", 0)
                st.metric(
                    "Predicted Volatility",
                    f"{arima_vol:.2%}",
                    help="ARIMA-GARCH forecast for next period volatility",
                )
            with col2:
                garch_signal = prediction_result.get("garch_signal", 0)
                signal_text = (
                    "BUY"
                    if garch_signal == 1
                    else "SELL" if garch_signal == -1 else "HOLD"
                )
                st.metric(
                    "GARCH Signal",
                    signal_text,
                    help="Volatility-based signal (high vol = bearish, low vol = bullish)",
                )
            with col3:
                arima_forecast = prediction_result.get("arima_forecast")
                if arima_forecast is not None:
                    st.metric(
                        "ARIMA Forecast",
                        f"{arima_forecast:.4f}",
                        help="ARIMA-GARCH predicted return for next period",
                    )
                else:
                    st.metric("ARIMA Forecast", "N/A")

            # Volatility regime classification
            if arima_vol > 0.025:
                st.error("🔴 HIGH VOLATILITY REGIME - Increased risk")
            elif arima_vol > 0.015:
                st.warning("🟡 MEDIUM VOLATILITY REGIME - Moderate risk")
            else:
                st.success("🟢 LOW VOLATILITY REGIME - Stable conditions")
        else:
            st.info(
                "ARIMA-GARCH model not available for this symbol - train model first"
            )

        st.markdown("---")

        # Ensemble Breakdown Display
        if prediction_result.get("ensemble_ready"):
            st.subheader("🎯 Ensemble Breakdown")
            xgb_signal = prediction_result.get("xgboost_signal", 0)
            garch_signal = prediction_result.get("garch_signal", 0)
            market_adjust = prediction_result.get("market_adjust", 0)
            sentiment_score = prediction_result.get("sentiment_score", 0.0)
            final_signal = prediction_result.get("signal", 0)

            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("XGBoost", f"{xgb_signal:+d}", "Weight: 45%")
            with col2:
                st.metric("GARCH", f"{garch_signal:+d}", "Weight: 30%")
            with col3:
                st.metric("ES Market", f"{market_adjust:+.2f}", "Weight: 15%")
            with col4:
                sentiment_emoji = (
                    "🟢"
                    if sentiment_score > 0.2
                    else "🔴" if sentiment_score < -0.2 else "🟡"
                )
                st.metric(
                    "Sentiment",
                    f"{sentiment_score:+.2f}",
                    f"Weight: 10% {sentiment_emoji}",
                )
            with col5:
                signal_text = (
                    "BUY"
                    if final_signal == 1
                    else "SELL" if final_signal == -1 else "HOLD"
                )
                st.metric("Final Signal", signal_text, "Ensemble")

            # Weight visualization
            weights_df = pd.DataFrame(
                {
                    "Component": ["XGBoost", "ARIMA-GARCH", "ES Market", "Perplexity"],
                    "Weight": [0.45, 0.30, 0.15, 0.10],
                    "Value": [xgb_signal, garch_signal, market_adjust, sentiment_score],
                }
            )
            st.bar_chart(weights_df.set_index("Component")["Weight"])

            st.caption(
                "Enhanced Ensemble: 45% XGBoost + 30% ARIMA-GARCH + 15% ES Market + 10% Perplexity Sentiment"
            )

            # Perplexity Market Intelligence Section
            st.subheader("📰 Market Intelligence (Perplexity)")

            # Check if Perplexity data is available in prediction_result
            if (
                prediction_result.get("perplexity_sentiment")
                and prediction_result.get("perplexity_sentiment") != "unavailable"
            ):
                col1, col2, col3 = st.columns(3)

                with col1:
                    perplexity_sentiment = prediction_result.get(
                        "perplexity_sentiment", "neutral"
                    )
                    sentiment_emoji_large = (
                        "🟢"
                        if perplexity_sentiment == "positive"
                        else "🔴" if perplexity_sentiment == "negative" else "🟡"
                    )
                    st.metric(
                        "Market Sentiment",
                        perplexity_sentiment.title(),
                        delta=sentiment_emoji_large,
                    )

                with col2:
                    perplexity_score = prediction_result.get(
                        "perplexity_sentiment_score", 0.0
                    )
                    st.metric(
                        "Sentiment Score",
                        f"{perplexity_score:+.2f}",
                        help="Perplexity sentiment score (-1 to +1)",
                    )

                with col3:
                    perplexity_confidence = prediction_result.get(
                        "perplexity_confidence", 0.0
                    )
                    st.metric(
                        "Confidence",
                        f"{perplexity_confidence:.2%}",
                        help="Perplexity analysis confidence",
                    )

                # Display analysis/news summary
                news_summary = prediction_result.get(
                    "news_summary", "No analysis available"
                )
                st.info(f"**Market Analysis:** {news_summary}")

                # Optional: Fetch full news articles if connector is available
                try:
                    from main_production_system.connectors.perplexity_connector import (
                        PerplexityConnector,
                    )

                    if st.button("📄 Fetch Latest News Articles"):
                        with st.spinner("Fetching news..."):
                            connector = PerplexityConnector()
                            news_df = connector.search_news(symbol, max_results=3)

                            if news_df is not None and not news_df.empty:
                                st.write("**Latest News & Analysis:**")
                                for idx, row in news_df.iterrows():
                                    with st.expander(
                                        f"📄 {row.get('title', 'News Article')}"
                                    ):
                                        st.write(
                                            f"**Source:** {row.get('source', 'Unknown')}"
                                        )
                                        st.write(
                                            f"**Published:** {row.get('published_date', 'N/A')}"
                                        )
                                        if "url" in row and row["url"]:
                                            st.write(
                                                f"[Read Full Article]({row['url']})"
                                            )
                                        if "summary" in row and row["summary"]:
                                            st.write(row["summary"])
                            else:
                                st.info(f"No recent news found for {symbol}")
                except Exception as e:
                    logger.debug(f"News fetch failed: {e}")
            else:
                st.info(
                    "💡 Perplexity market intelligence not available. Configure API key in environment variables (PERPLEXITY_API_KEY)."
                )

        st.markdown("---")

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 3: TECHNICAL INDICATORS (TABS)
    # ═══════════════════════════════════════════════════════════════════

    render_technical_indicators(df_features)

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 4: FEATURE HEATMAP
    # ═══════════════════════════════════════════════════════════════════

    render_feature_heatmap(df_features)

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════════
    # SECTION 5: DATA QUALITY & RECENT CANDLES
    # ═══════════════════════════════════════════════════════════════════

    tab1, tab2, tab3 = st.tabs(
        ["📊 Data Quality", "📋 Recent Candles", "🔧 Raw Features"]
    )

    with tab1:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            ohlcv_cols = [
                c
                for c in df_raw.columns
                if c.lower() in ["open", "high", "low", "close", "volume"]
            ]
            nan_count = df_raw[ohlcv_cols].isna().sum().sum()
            st.metric(
                "Data Integrity", "✅ Clean" if nan_count == 0 else f"⚠️ {nan_count} NaN"
            )
        with col2:
            st.metric("Features Engineered", len(df_features.columns))
        with col3:
            st.metric("Feature Rows", len(df_features))
        with col4:
            st.metric("Data Source", "Polygon.io" if use_polygon else "yfinance")

    with tab2:
        display_cols = [
            col
            for col in ["Date", "open", "high", "low", "close", "volume"]
            if col in df_raw.columns
        ]
        display_df = df_raw[display_cols].tail(20).copy()
        if "Date" in display_df.columns:
            display_df["Date"] = pd.to_datetime(display_df["Date"]).dt.strftime(
                "%Y-%m-%d %H:%M"
            )
        st.dataframe(display_df, width="stretch", height=400)

    with tab3:
        # Remove non-numeric columns before describe()
        df_numeric = df_features.select_dtypes(include=[np.number])
        feature_stats = df_numeric.describe().T
        st.dataframe(feature_stats, width="stretch")

    st.markdown("---")
    st.caption(
        f"🟢 Dashboard | {symbol} {timeframe} | {len(df_raw)} candles | {len(df_features.columns)} features"
    )


# ═══════════════════════════════════════════════════════════════════════════
# PAGE ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logger.info("[TRADING] Starting trading_page.py")
    render()
