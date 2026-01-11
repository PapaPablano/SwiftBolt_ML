"""
SwiftBolt ML Forecast Dashboard
===============================
Streamlit dashboard for visualizing ML forecasts, model performance,
and feature importance.

Run with: streamlit run ml/src/dashboard/forecast_dashboard.py
"""

import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402
from typing import Optional  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

# Page configuration
st.set_page_config(
    page_title="SwiftBolt ML Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for styling
st.markdown(
    """
<style>
    .metric-card {
        background-color: #1e1e1e;
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
    }
    .bullish { color: #00c853; }
    .bearish { color: #ff5252; }
    .neutral { color: #ffc107; }
    .stMetric > div { background-color: #262730; border-radius: 5px; padding: 10px; }
</style>
""",
    unsafe_allow_html=True,
)


def get_db_connection():
    """Get database connection for fetching data."""
    try:
        from src.data.supabase_db import SupabaseDatabase

        return SupabaseDatabase()
    except Exception as e:
        st.warning(f"Could not connect to database: {e}")
        return None


def fetch_forecasts(db) -> pd.DataFrame:
    """Fetch recent forecasts from database."""
    if db is None:
        return get_sample_forecasts()

    try:
        result = (
            db.client.table("ml_forecasts")
            .select("*, symbols(ticker)")
            .order("run_at", desc=True)
            .limit(500)
            .execute()
        )

        if result.data:
            df = pd.DataFrame(result.data)
            df["symbol"] = df["symbols"].apply(lambda x: x.get("ticker") if x else "Unknown")
            # Rename overall_label to label for consistency
            if "overall_label" in df.columns:
                df["label"] = df["overall_label"]
            # Ensure required columns exist with defaults
            if "label" not in df.columns:
                df["label"] = "neutral"
            if "model_agreement" not in df.columns:
                df["model_agreement"] = 0.75
            if "quality_score" not in df.columns:
                df["quality_score"] = 0.70
            return df
    except Exception as e:
        st.warning(f"Error fetching forecasts: {e}")

    return get_sample_forecasts()


def get_sample_forecasts() -> pd.DataFrame:
    """Generate sample forecast data for demo."""
    np.random.seed(42)
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "AMD"]
    horizons = ["1D", "1W"]
    labels = ["bullish", "neutral", "bearish"]

    data = []
    for symbol in symbols:
        for horizon in horizons:
            label = np.random.choice(labels, p=[0.4, 0.35, 0.25])
            data.append(
                {
                    "symbol": symbol,
                    "horizon": horizon,
                    "label": label,
                    "confidence": np.random.uniform(0.55, 0.92),
                    "model_agreement": np.random.uniform(0.65, 0.98),
                    "quality_score": np.random.uniform(0.60, 0.95),
                    "run_at": datetime.now() - timedelta(hours=np.random.randint(1, 48)),
                    "backtest_metrics": {
                        "accuracy": np.random.uniform(0.52, 0.68),
                        "sharpe_ratio": np.random.uniform(0.3, 1.5),
                        "win_rate": np.random.uniform(0.48, 0.62),
                        "max_drawdown": np.random.uniform(-0.25, -0.08),
                        "profit_factor": np.random.uniform(1.0, 2.0),
                    },
                    "training_stats": {
                        "accuracy": np.random.uniform(0.65, 0.85),
                        "precision": np.random.uniform(0.60, 0.80),
                        "recall": np.random.uniform(0.55, 0.75),
                        "f1_score": np.random.uniform(0.58, 0.78),
                        "top_features": [
                            ("rsi_14", np.random.uniform(0.10, 0.20)),
                            ("macd", np.random.uniform(0.08, 0.15)),
                            ("sma_20", np.random.uniform(0.06, 0.12)),
                            ("volume_ratio", np.random.uniform(0.05, 0.10)),
                            ("bb_width", np.random.uniform(0.04, 0.08)),
                        ],
                    },
                }
            )

    return pd.DataFrame(data)


def render_sidebar():
    """Render sidebar with filters and controls."""
    st.sidebar.title("📈 SwiftBolt ML")
    st.sidebar.markdown("---")

    # View selection
    view = st.sidebar.radio(
        "Select View",
        [
            "Overview",
            "Forecast Details",
            "Model Performance",
            "Feature Importance",
            "Support & Resistance",
        ],
        index=0,
    )

    st.sidebar.markdown("---")

    # Filters
    st.sidebar.subheader("Filters")

    horizon_filter = st.sidebar.multiselect(
        "Horizon",
        ["1D", "1W"],
        default=["1D", "1W"],
    )

    label_filter = st.sidebar.multiselect(
        "Signal",
        ["bullish", "neutral", "bearish"],
        default=["bullish", "neutral", "bearish"],
    )

    min_confidence = st.sidebar.slider(
        "Min Confidence",
        min_value=0.0,
        max_value=1.0,
        value=0.5,
        step=0.05,
    )

    st.sidebar.markdown("---")

    # Refresh button
    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    return view, horizon_filter, label_filter, min_confidence


def render_overview(df: pd.DataFrame):
    """Render overview dashboard."""
    st.title("ML Forecast Overview")

    # Top metrics row
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Total Forecasts", len(df))

    with col2:
        bullish_pct = (df["label"] == "bullish").mean() * 100
        st.metric("Bullish %", f"{bullish_pct:.1f}%")

    with col3:
        avg_confidence = df["confidence"].mean() * 100
        st.metric("Avg Confidence", f"{avg_confidence:.1f}%")

    with col4:
        avg_quality = df["quality_score"].mean() * 100 if "quality_score" in df else 0
        st.metric("Avg Quality", f"{avg_quality:.1f}%")

    with col5:
        unique_symbols = df["symbol"].nunique()
        st.metric("Symbols", unique_symbols)

    st.markdown("---")

    # Charts row
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Signal Distribution")

        # Pie chart of signals
        signal_counts = df["label"].value_counts()
        colors = {"bullish": "#00c853", "neutral": "#ffc107", "bearish": "#ff5252"}

        fig = px.pie(
            values=signal_counts.values,
            names=signal_counts.index,
            color=signal_counts.index,
            color_discrete_map=colors,
            hole=0.4,
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="white",
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Confidence Distribution")

        fig = px.histogram(
            df,
            x="confidence",
            nbins=20,
            color="label",
            color_discrete_map=colors,
            opacity=0.7,
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="white",
            xaxis_title="Confidence",
            yaxis_title="Count",
            bargap=0.1,
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Forecast table
    st.subheader("Recent Forecasts")

    display_df = df[
        ["symbol", "horizon", "label", "confidence", "model_agreement", "quality_score", "run_at"]
    ].copy()
    display_df["confidence"] = (display_df["confidence"] * 100).round(1).astype(str) + "%"
    display_df["model_agreement"] = (
        (display_df["model_agreement"] * 100).round(1).astype(str) + "%"
        if "model_agreement" in display_df
        else "N/A"
    )
    display_df["quality_score"] = (
        (display_df["quality_score"] * 100).round(1).astype(str) + "%"
        if "quality_score" in display_df
        else "N/A"
    )

    # Color the label column
    def highlight_label(val):
        if val == "bullish":
            return "background-color: #00c85320; color: #00c853"
        elif val == "bearish":
            return "background-color: #ff525220; color: #ff5252"
        else:
            return "background-color: #ffc10720; color: #ffc107"

    st.dataframe(
        display_df.head(20).style.applymap(highlight_label, subset=["label"]),
        use_container_width=True,
        height=400,
    )


def render_forecast_details(df: pd.DataFrame):
    """Render detailed forecast view."""
    st.title("Forecast Details")

    # Symbol selector
    symbols = sorted(df["symbol"].unique())
    selected_symbol = st.selectbox("Select Symbol", symbols)

    symbol_df = df[df["symbol"] == selected_symbol]

    if symbol_df.empty:
        st.warning(f"No forecasts found for {selected_symbol}")
        return

    # Latest forecast for each horizon
    st.subheader(f"Latest Forecasts for {selected_symbol}")

    for horizon in ["1D", "1W"]:
        horizon_df = symbol_df[symbol_df["horizon"] == horizon]
        if horizon_df.empty:
            continue

        latest = horizon_df.iloc[0]

        with st.container():
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                label = latest["label"]
                color = (
                    "#00c853"
                    if label == "bullish"
                    else "#ff5252" if label == "bearish" else "#ffc107"
                )
                st.markdown(f"### {horizon}")
                st.markdown(
                    f"<h2 style='color: {color}'>{label.upper()}</h2>", unsafe_allow_html=True
                )

            with col2:
                st.metric("Confidence", f"{latest['confidence']*100:.1f}%")

            with col3:
                agreement = latest.get("model_agreement", 0.75)
                st.metric("Model Agreement", f"{agreement*100:.1f}%")

            with col4:
                quality = latest.get("quality_score", 0.70)
                st.metric("Quality Score", f"{quality*100:.1f}%")

        st.markdown("---")

    # Probability distribution chart
    st.subheader("Confidence Over Time")

    if len(symbol_df) > 1:
        fig = px.line(
            symbol_df.sort_values("run_at"),
            x="run_at",
            y="confidence",
            color="horizon",
            markers=True,
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="white",
            xaxis_title="Time",
            yaxis_title="Confidence",
            yaxis_range=[0, 1],
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Not enough data points to show trend")


def render_model_performance(df: pd.DataFrame):
    """Render model performance metrics."""
    st.title("Model Performance")

    # Extract backtest metrics
    metrics_data = []
    for _, row in df.iterrows():
        bt = row.get("backtest_metrics", {})
        if isinstance(bt, str):
            try:
                bt = json.loads(bt)
            except Exception:
                bt = {}
        if bt:
            metrics_data.append(
                {
                    "symbol": row["symbol"],
                    "horizon": row["horizon"],
                    "accuracy": bt.get("accuracy", 0),
                    "sharpe_ratio": bt.get("sharpe_ratio", 0),
                    "win_rate": bt.get("win_rate", 0),
                    "max_drawdown": bt.get("max_drawdown", 0),
                    "profit_factor": bt.get("profit_factor", 1),
                }
            )

    if not metrics_data:
        st.warning("No backtest metrics available. Showing sample data.")
        metrics_data = [
            {
                "symbol": s,
                "horizon": h,
                "accuracy": np.random.uniform(0.52, 0.68),
                "sharpe_ratio": np.random.uniform(0.3, 1.5),
                "win_rate": np.random.uniform(0.48, 0.62),
                "max_drawdown": np.random.uniform(-0.25, -0.08),
                "profit_factor": np.random.uniform(1.0, 2.0),
            }
            for s in df["symbol"].unique()[:5]
            for h in ["1D", "1W"]
        ]

    metrics_df = pd.DataFrame(metrics_data)

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        avg_accuracy = metrics_df["accuracy"].mean() * 100
        st.metric(
            "Avg Accuracy",
            f"{avg_accuracy:.1f}%",
            delta=f"+{(avg_accuracy-50):.1f}% vs random" if avg_accuracy > 50 else None,
        )

    with col2:
        avg_sharpe = metrics_df["sharpe_ratio"].mean()
        st.metric("Avg Sharpe", f"{avg_sharpe:.2f}")

    with col3:
        avg_win_rate = metrics_df["win_rate"].mean() * 100
        st.metric("Avg Win Rate", f"{avg_win_rate:.1f}%")

    with col4:
        avg_pf = metrics_df["profit_factor"].mean()
        st.metric("Avg Profit Factor", f"{avg_pf:.2f}")

    st.markdown("---")

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Accuracy by Symbol")

        symbol_accuracy = (
            metrics_df.groupby("symbol")["accuracy"].mean().sort_values(ascending=True)
        )

        fig = px.bar(
            x=symbol_accuracy.values * 100,
            y=symbol_accuracy.index,
            orientation="h",
            color=symbol_accuracy.values,
            color_continuous_scale=["#ff5252", "#ffc107", "#00c853"],
        )
        fig.add_vline(x=50, line_dash="dash", line_color="white", opacity=0.5)
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="white",
            xaxis_title="Accuracy %",
            yaxis_title="",
            showlegend=False,
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Sharpe Ratio by Symbol")

        symbol_sharpe = (
            metrics_df.groupby("symbol")["sharpe_ratio"].mean().sort_values(ascending=True)
        )

        fig = px.bar(
            x=symbol_sharpe.values,
            y=symbol_sharpe.index,
            orientation="h",
            color=symbol_sharpe.values,
            color_continuous_scale=["#ff5252", "#ffc107", "#00c853"],
        )
        fig.add_vline(x=0, line_dash="dash", line_color="white", opacity=0.5)
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="white",
            xaxis_title="Sharpe Ratio",
            yaxis_title="",
            showlegend=False,
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Detailed metrics table
    st.subheader("Detailed Backtest Metrics")

    display_metrics = metrics_df.copy()
    display_metrics["accuracy"] = (display_metrics["accuracy"] * 100).round(1).astype(str) + "%"
    display_metrics["sharpe_ratio"] = display_metrics["sharpe_ratio"].round(2)
    display_metrics["win_rate"] = (display_metrics["win_rate"] * 100).round(1).astype(str) + "%"
    display_metrics["max_drawdown"] = (display_metrics["max_drawdown"] * 100).round(1).astype(
        str
    ) + "%"
    display_metrics["profit_factor"] = display_metrics["profit_factor"].round(2)

    st.dataframe(display_metrics, use_container_width=True)


def render_feature_importance(df: pd.DataFrame):
    """Render feature importance visualization."""
    st.title("Feature Importance")

    # Extract feature importance from training stats
    all_features = {}
    feature_by_symbol = {}

    for _, row in df.iterrows():
        ts = row.get("training_stats", {})
        if isinstance(ts, str):
            try:
                ts = json.loads(ts)
            except Exception:
                ts = {}

        top_features = ts.get("top_features", [])
        symbol = row["symbol"]

        if symbol not in feature_by_symbol:
            feature_by_symbol[symbol] = {}

        for feat in top_features:
            if isinstance(feat, (list, tuple)) and len(feat) >= 2:
                name, importance = feat[0], feat[1]
                all_features[name] = all_features.get(name, 0) + importance
                feature_by_symbol[symbol][name] = importance

    # If no real data, generate sample
    if not all_features:
        st.info("Using sample feature importance data")
        sample_features = [
            ("rsi_14", 0.18),
            ("macd", 0.15),
            ("sma_20", 0.12),
            ("volume_ratio", 0.10),
            ("bb_width", 0.08),
            ("ema_12", 0.07),
            ("returns_5d", 0.06),
            ("volatility_20d", 0.05),
            ("price_vs_sma20", 0.04),
            ("atr_14", 0.03),
        ]
        all_features = dict(sample_features)
        for symbol in df["symbol"].unique()[:5]:
            feature_by_symbol[symbol] = {
                k: v * np.random.uniform(0.8, 1.2) for k, v in sample_features
            }

    # Top features chart
    st.subheader("Top Features (Aggregated)")

    sorted_features = sorted(all_features.items(), key=lambda x: x[1], reverse=True)[:15]
    feature_names = [f[0] for f in sorted_features]
    feature_values = [f[1] for f in sorted_features]

    # Normalize
    total = sum(feature_values)
    feature_values = [v / total for v in feature_values]

    fig = px.bar(
        x=feature_values,
        y=feature_names,
        orientation="h",
        color=feature_values,
        color_continuous_scale="Viridis",
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="white",
        xaxis_title="Relative Importance",
        yaxis_title="",
        yaxis=dict(autorange="reversed"),
        showlegend=False,
        coloraxis_showscale=False,
        height=500,
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Feature importance by symbol heatmap
    st.subheader("Feature Importance by Symbol")

    # Create matrix
    symbols = list(feature_by_symbol.keys())[:10]
    features = feature_names[:10]

    matrix = []
    for symbol in symbols:
        row = []
        for feat in features:
            row.append(feature_by_symbol.get(symbol, {}).get(feat, 0))
        # Normalize row
        row_sum = sum(row) if sum(row) > 0 else 1
        row = [v / row_sum for v in row]
        matrix.append(row)

    fig = px.imshow(
        matrix,
        x=features,
        y=symbols,
        color_continuous_scale="Viridis",
        aspect="auto",
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="white",
        xaxis_title="Feature",
        yaxis_title="Symbol",
        height=400,
    )
    fig.update_xaxes(tickangle=45)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Feature categories
    st.subheader("Feature Categories")

    categories = {
        "Momentum": ["rsi_14", "macd", "macd_signal", "macd_hist", "stoch_k", "stoch_d"],
        "Trend": [
            "sma_5",
            "sma_20",
            "sma_50",
            "ema_12",
            "ema_26",
            "price_vs_sma20",
            "price_vs_sma50",
        ],
        "Volatility": ["bb_width", "atr_14", "volatility_20d", "keltner_upper", "keltner_lower"],
        "Volume": ["volume_ratio", "volume_sma_20", "obv", "mfi", "vroc"],
        "Returns": ["returns_1d", "returns_5d", "returns_20d"],
    }

    category_importance = {}
    for cat, feats in categories.items():
        cat_sum = sum(all_features.get(f, 0) for f in feats)
        category_importance[cat] = cat_sum

    # Normalize
    cat_total = sum(category_importance.values()) if sum(category_importance.values()) > 0 else 1
    category_importance = {k: v / cat_total for k, v in category_importance.items()}

    col1, col2 = st.columns(2)

    with col1:
        fig = px.pie(
            values=list(category_importance.values()),
            names=list(category_importance.keys()),
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="white",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("### Category Breakdown")
        for cat, importance in sorted(
            category_importance.items(), key=lambda x: x[1], reverse=True
        ):
            st.progress(importance, text=f"{cat}: {importance*100:.1f}%")


def fetch_sr_levels_from_db(db, symbol: str) -> dict:
    """Fetch S/R levels from database for a symbol."""
    if db is None:
        return None

    try:
        result = (
            db.client.table("sr_levels")
            .select("*, symbols(ticker)")
            .eq("symbols.ticker", symbol)
            .order("computed_at", desc=True)
            .limit(1)
            .execute()
        )

        if result.data and len(result.data) > 0:
            return result.data[0]
    except Exception as e:
        st.warning(f"Could not fetch S/R data: {e}")

    return None


def fetch_ohlc_for_sr(db, symbol: str, lookback: int = 252) -> Optional[pd.DataFrame]:
    """Fetch OHLC data for S/R calculation."""
    if db is None:
        return None

    try:
        # Get symbol ID first
        sym_result = db.client.table("symbols").select("id").eq("ticker", symbol).single().execute()

        if not sym_result.data:
            return None

        symbol_id = sym_result.data["id"]

        # Fetch OHLC data from v2 (real Alpaca data only)
        ohlc_result = (
            db.client.table("ohlc_bars_v2")
            .select("ts, open, high, low, close, volume")
            .eq("symbol_id", symbol_id)
            .eq("timeframe", "d1")
            .eq("provider", "alpaca")
            .eq("is_forecast", False)
            .order("ts", desc=True)
            .limit(lookback)
            .execute()
        )

        if ohlc_result.data:
            # Reverse to get chronological order (oldest to newest)
            return pd.DataFrame(ohlc_result.data[::-1])
    except Exception as e:
        st.warning(f"Could not fetch OHLC data: {e}")

    return None


def render_support_resistance(df: pd.DataFrame):
    """Render support and resistance levels visualization."""
    st.title("Support & Resistance Levels")

    # Symbol selector
    symbols = sorted(df["symbol"].unique())
    selected_symbol = st.selectbox("Select Symbol for S/R Analysis", symbols)

    st.markdown("---")

    # Try to fetch real data from database
    db = get_db_connection()
    ohlc_df = fetch_ohlc_for_sr(db, selected_symbol, lookback=252)

    # Check if we have real data
    use_real_data = ohlc_df is not None and len(ohlc_df) >= 20

    if use_real_data:
        st.success(f"📊 Using real market data ({len(ohlc_df)} bars)")

        # Use the SupportResistanceDetector for real calculations
        try:
            from src.features.support_resistance_detector import SupportResistanceDetector

            sr_detector = SupportResistanceDetector()

            # Ensure proper column names
            ohlc_df.columns = [c.lower() for c in ohlc_df.columns]

            # Calculate S/R levels
            sr_result = sr_detector.find_all_levels(ohlc_df)

            current_price = sr_result["current_price"]
            nearest_support = sr_result["nearest_support"]
            nearest_resistance = sr_result["nearest_resistance"]

            pivot_points = sr_result["methods"]["pivot_points"]
            fib_data = sr_result["methods"]["fibonacci"]
            trend = fib_data["trend"]

            # Build fib_levels dict for display
            fib_levels = {f"{k}%": v for k, v in fib_data["levels"].items()}

            # Get price series for chart
            close_prices = ohlc_df["close"].values
            n_bars = len(close_prices)

        except Exception as e:
            st.warning(f"S/R calculation error: {e}. Using simulated data.")
            use_real_data = False

    if not use_real_data:
        st.info("📈 Using simulated data (connect to database for real data)")

        # Fallback to simulated data
        np.random.seed(hash(selected_symbol) % 2**32)
        base_price = 100 + np.random.uniform(0, 200)

        n_bars = 100
        returns = np.random.normal(0.0005, 0.02, n_bars)
        close_prices = base_price * np.cumprod(1 + returns)
        current_price = close_prices[-1]

        high = close_prices.max() * 1.01
        low = close_prices.min() * 0.99
        close = current_price

        pp = (high + low + close) / 3
        r1 = 2 * pp - low
        r2 = pp + (high - low)
        r3 = high + 2 * (pp - low)
        s1 = 2 * pp - high
        s2 = pp - (high - low)
        s3 = low - 2 * (high - pp)

        pivot_points = {
            "PP": round(pp, 2),
            "R1": round(r1, 2),
            "R2": round(r2, 2),
            "R3": round(r3, 2),
            "S1": round(s1, 2),
            "S2": round(s2, 2),
            "S3": round(s3, 2),
        }

        range_high = max(close_prices[-50:])
        range_low = min(close_prices[-50:])
        diff = range_high - range_low
        trend = "uptrend" if close_prices[-1] > close_prices[-50] else "downtrend"

        if trend == "uptrend":
            fib_levels = {
                "0.0%": round(range_high, 2),
                "23.6%": round(range_high - diff * 0.236, 2),
                "38.2%": round(range_high - diff * 0.382, 2),
                "50.0%": round(range_high - diff * 0.5, 2),
                "61.8%": round(range_high - diff * 0.618, 2),
                "78.6%": round(range_high - diff * 0.786, 2),
                "100.0%": round(range_low, 2),
            }
        else:
            fib_levels = {
                "0.0%": round(range_low, 2),
                "23.6%": round(range_low + diff * 0.236, 2),
                "38.2%": round(range_low + diff * 0.382, 2),
                "50.0%": round(range_low + diff * 0.5, 2),
                "61.8%": round(range_low + diff * 0.618, 2),
                "78.6%": round(range_low + diff * 0.786, 2),
                "100.0%": round(range_high, 2),
            }

        all_levels = list(pivot_points.values()) + list(fib_levels.values())
        supports = sorted([lv for lv in all_levels if lv < current_price], reverse=True)
        resistances = sorted([lv for lv in all_levels if lv > current_price])

        nearest_support = supports[0] if supports else None
        nearest_resistance = resistances[0] if resistances else None

    # Top metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Current Price", f"${current_price:.2f}")

    with col2:
        if nearest_support:
            dist = (current_price - nearest_support) / current_price * 100
            st.metric(
                "Nearest Support",
                f"${nearest_support:.2f}",
                delta=f"-{dist:.1f}%",
                delta_color="normal",
            )
        else:
            st.metric("Nearest Support", "N/A")

    with col3:
        if nearest_resistance:
            dist = (nearest_resistance - current_price) / current_price * 100
            st.metric(
                "Nearest Resistance",
                f"${nearest_resistance:.2f}",
                delta=f"+{dist:.1f}%",
                delta_color="normal",
            )
        else:
            st.metric("Nearest Resistance", "N/A")

    with col4:
        st.metric("Trend", trend.upper(), delta="↑" if trend == "uptrend" else "↓")

    st.markdown("---")

    # Price chart with S/R levels
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Price Chart with S/R Levels")

        # Create price chart
        dates = pd.date_range(end=datetime.now(), periods=n_bars, freq="D")
        price_df = pd.DataFrame({"Date": dates, "Price": close_prices})

        fig = px.line(
            price_df, x="Date", y="Price", title=f"{selected_symbol} Price with Support/Resistance"
        )

        # Add horizontal lines for key levels
        colors = {
            "R3": "#ff1744",
            "R2": "#ff5252",
            "R1": "#ff8a80",
            "PP": "#ffc107",
            "S1": "#69f0ae",
            "S2": "#00e676",
            "S3": "#00c853",
        }

        for level_name, level_price in pivot_points.items():
            fig.add_hline(
                y=level_price,
                line_dash="dash",
                line_color=colors.get(level_name, "gray"),
                annotation_text=f"{level_name}: ${level_price:.2f}",
                annotation_position="right",
            )

        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="white",
            height=500,
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Pivot Points")

        # Display pivot points as a table
        pivot_df = pd.DataFrame(
            [
                {"Level": "R3", "Price": f"${pivot_points['R3']:.2f}", "Type": "🔴 Resistance"},
                {"Level": "R2", "Price": f"${pivot_points['R2']:.2f}", "Type": "🔴 Resistance"},
                {"Level": "R1", "Price": f"${pivot_points['R1']:.2f}", "Type": "🔴 Resistance"},
                {"Level": "PP", "Price": f"${pivot_points['PP']:.2f}", "Type": "🟡 Pivot"},
                {"Level": "S1", "Price": f"${pivot_points['S1']:.2f}", "Type": "🟢 Support"},
                {"Level": "S2", "Price": f"${pivot_points['S2']:.2f}", "Type": "🟢 Support"},
                {"Level": "S3", "Price": f"${pivot_points['S3']:.2f}", "Type": "🟢 Support"},
            ]
        )
        st.dataframe(pivot_df, use_container_width=True, hide_index=True)

        st.subheader("Fibonacci Levels")
        fib_df = pd.DataFrame([{"Level": k, "Price": f"${v:.2f}"} for k, v in fib_levels.items()])
        st.dataframe(fib_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # S/R Level Gauge
    st.subheader("Price Position Analysis")

    col1, col2, col3 = st.columns(3)

    with col1:
        # Distance to support gauge
        if nearest_support:
            support_dist_pct = (current_price - nearest_support) / current_price * 100
            st.markdown("### Distance to Support")
            st.progress(
                min(support_dist_pct / 10, 1.0), text=f"{support_dist_pct:.2f}% above support"
            )
            if support_dist_pct < 2:
                st.warning("⚠️ Price near support level")
            elif support_dist_pct < 5:
                st.info("ℹ️ Price moderately above support")
            else:
                st.success("✅ Price well above support")

    with col2:
        # Distance to resistance gauge
        if nearest_resistance:
            resistance_dist_pct = (nearest_resistance - current_price) / current_price * 100
            st.markdown("### Distance to Resistance")
            st.progress(
                min(resistance_dist_pct / 10, 1.0),
                text=f"{resistance_dist_pct:.2f}% below resistance",
            )
            if resistance_dist_pct < 2:
                st.warning("⚠️ Price near resistance level")
            elif resistance_dist_pct < 5:
                st.info("ℹ️ Price moderately below resistance")
            else:
                st.success("✅ Price well below resistance")

    with col3:
        # S/R Ratio
        if nearest_support and nearest_resistance:
            support_dist = current_price - nearest_support
            resistance_dist = nearest_resistance - current_price
            sr_ratio = resistance_dist / support_dist if support_dist > 0 else 0

            st.markdown("### S/R Ratio")
            if sr_ratio > 1.5:
                st.success(f"📈 Bullish bias (ratio: {sr_ratio:.2f})")
                st.caption("More room to upside than downside")
            elif sr_ratio < 0.67:
                st.error(f"📉 Bearish bias (ratio: {sr_ratio:.2f})")
                st.caption("More room to downside than upside")
            else:
                st.info(f"➡️ Neutral (ratio: {sr_ratio:.2f})")
                st.caption("Balanced risk/reward")

    st.markdown("---")

    # Method comparison
    st.subheader("S/R Detection Methods Comparison")

    methods_data = {
        "Method": ["ZigZag", "Pivot Points", "Fibonacci", "Local Extrema", "K-Means"],
        "Accuracy": [9, 8, 7, 8, 8],
        "Speed": [8, 10, 10, 9, 6],
        "Best For": [
            "Swing trading, trend reversals",
            "Daily levels, day trading",
            "Retracement targets",
            "Peak/trough detection",
            "Statistical zones",
        ],
        "Complexity": ["Medium", "Low", "Low", "Low", "High"],
    }

    methods_df = pd.DataFrame(methods_data)
    st.dataframe(methods_df, use_container_width=True, hide_index=True)

    # Radar chart for method comparison
    fig = go.Figure()

    categories = ["Accuracy", "Speed", "Simplicity", "Real-time", "Reliability"]

    fig.add_trace(
        go.Scatterpolar(r=[9, 8, 7, 9, 8], theta=categories, fill="toself", name="ZigZag")
    )
    fig.add_trace(
        go.Scatterpolar(r=[8, 10, 10, 10, 8], theta=categories, fill="toself", name="Pivot Points")
    )
    fig.add_trace(
        go.Scatterpolar(r=[7, 10, 9, 8, 7], theta=categories, fill="toself", name="Fibonacci")
    )

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 10])),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="white",
        showlegend=True,
        title="Method Comparison",
    )
    st.plotly_chart(fig, use_container_width=True)


def main():
    """Main dashboard entry point."""
    # Sidebar
    view, horizon_filter, label_filter, min_confidence = render_sidebar()

    # Fetch data
    db = get_db_connection()
    df = fetch_forecasts(db)

    # Debug: show columns if there's an issue
    if df.empty:
        st.warning("No forecast data available.")
        return

    # Ensure required columns exist
    required_cols = ["symbol", "horizon", "label", "confidence"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        st.error(f"Missing required columns: {missing_cols}")
        st.write("Available columns:", list(df.columns))
        return

    # Apply filters safely
    try:
        if horizon_filter and "horizon" in df.columns:
            df = df[df["horizon"].isin(horizon_filter)]
        if label_filter and "label" in df.columns:
            df = df[df["label"].isin(label_filter)]
        if "confidence" in df.columns:
            df = df[df["confidence"] >= min_confidence]
    except Exception as e:
        st.error(f"Error applying filters: {e}")
        return

    if df.empty:
        st.warning("No forecasts match the current filters.")
        return

    # Render selected view
    if view == "Overview":
        render_overview(df)
    elif view == "Forecast Details":
        render_forecast_details(df)
    elif view == "Model Performance":
        render_model_performance(df)
    elif view == "Feature Importance":
        render_feature_importance(df)
    elif view == "Support & Resistance":
        render_support_resistance(df)


if __name__ == "__main__":
    main()
