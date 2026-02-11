"""
Technical Analysis Tab - TradingView Lightweight Charts Integration
Integrated with unified sidebar controls and data pipeline.
"""

from __future__ import annotations

import streamlit as st

from main_production_system.dashboard.sidebar_controls import DashboardControls
from main_production_system.dashboard.data_pipeline import DataPipeline
from main_production_system.dashboard.charts.lightweight_chart_builder import (
    LightweightChartBuilder,
)
from main_production_system.dashboard.charts.indicator_overlays import (
    KDJOverlay,
    SuperTrendOverlay,
)
from main_production_system.dashboard.charts.chart_utils import add_wave_overlays


def render_technical_analysis() -> None:
    """Main Technical Analysis tab."""
    st.title("🚀 Technical Analysis")
    st.subheader("SuperTrend AI + KDJ with Wave Detection")

    # Use unified sidebar controls
    symbol, timeframe, days = DashboardControls.get_controls()

    # Unified pipeline
    st.write("Loading data and engineering features...")
    pipeline_result = DataPipeline.full_pipeline(symbol, timeframe, days)
    if pipeline_result["status"] != "success":
        st.error("❌ Pipeline failed. Check errors above.")
        return

    df_features = pipeline_result["features"]
    waves = pipeline_result["waves"]

    st.markdown("---")
    st.subheader(f"📈 {symbol} - {timeframe} Chart")

    try:
        builder = LightweightChartBuilder(height=600, width=1400)
        chart = builder.set_ohlcv_data(df_features).get_chart()
        SuperTrendOverlay.add_to_chart(chart, df_features)
        KDJOverlay.create_subchart(chart, df_features)
        if waves:
            add_wave_overlays(chart, waves)
        st.components.v1.html(chart.get_html(), height=900, scrolling=False)
    except Exception as exc:
        st.error(f"Chart rendering error: {exc}")

    st.markdown("---")
    st.subheader("🌊 Wave Detection Summary")
    if waves:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Waves Detected", len(waves))
        with col2:
            avg_duration = (
                sum(w.get("end_idx", 0) - w.get("start_idx", 0) for w in waves) / len(waves)
            )
            st.metric("Avg Wave Duration", f"{avg_duration:.0f} bars")
        with col3:
            uptrends = sum(1 for w in waves if w["features"].get("eng_st_trend_dir", 0) > 0)
            st.metric("Uptrends", uptrends)

        st.subheader("Wave Details")
        wave_data = []
        for i, w in enumerate(waves):
            wave_data.append(
                {
                    "Wave": i + 1,
                    "Start": w.get("start_idx"),
                    "End": w.get("end_idx"),
                    "Trend": "📈 UP"
                    if w["features"].get("eng_st_trend_dir", 0) > 0
                    else "📉 DOWN",
                    "ST_ATR": round(w["features"].get("eng_st_atr", 0), 2),
                    "Multiplier": round(w["features"].get("eng_st_best_multiplier", 0), 2),
                    "KDJ_K": round(w["features"].get("eng_close_kdj_k", 0), 1),
                }
            )
        st.dataframe(wave_data, use_container_width=True)
    else:
        st.info("No waves detected in current data window.")

    if st.checkbox("Show All 39 Features", value=False):
        st.subheader("Engineered Features")
        st.dataframe(df_features.tail(20), use_container_width=True)


if __name__ == "__main__":
    # Allow running the page standalone for quick checks
    DashboardControls.render_sidebar()
    render_technical_analysis()


