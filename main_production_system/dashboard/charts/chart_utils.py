"""
Utility functions for preparing data from our feature engineering pipeline
for TradingView Lightweight Charts.
"""

from __future__ import annotations

import pandas as pd

from core.wave_detection.ultimate_feature_engineer import UltimateFeatureEngineer


def prepare_chart_data(symbol: str, timeframe: str, df_ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Prepare OHLCV data with engineered features for charting.

    Args:
        symbol: Ticker symbol (e.g., "SPY")
        timeframe: Timeframe string (e.g., "1h", "10min", "4h")
        df_ohlcv: Raw OHLCV DataFrame with columns [time, open, high, low, close, volume]

    Returns:
        DataFrame with OHLCV + engineered features used by overlays.
    """
    if df_ohlcv is None or df_ohlcv.empty:
        raise ValueError("prepare_chart_data received empty OHLCV data")

    # Ensure 'time' is a regular column
    if "time" not in df_ohlcv.columns and df_ohlcv.index.name == "time":
        df_ohlcv = df_ohlcv.reset_index()

    # Feature engineering via existing pipeline (no reimplementation)
    engineer = UltimateFeatureEngineer()
    df_features = engineer.engineer_features(df_ohlcv)

    # Align indices and merge
    df_features = df_features.reset_index(drop=True)
    df_ohlcv = df_ohlcv.reset_index(drop=True)
    df_chart = pd.concat([df_ohlcv, df_features], axis=1)

    return df_chart


def add_wave_overlays(chart, waves: list) -> None:
    """Add detected wave regions as background shading on the chart.

    Args:
        chart: LightweightChart instance
        waves: List of wave dicts from EnhancedWaveDetector.detect_waves_enhanced()
    """
    if not waves:
        return

    for wave in waves:
        start_time = wave.get("start_time")
        end_time = wave.get("end_time")
        if start_time is None or end_time is None:
            continue

        trend = 0
        features = wave.get("features") or {}
        try:
            trend = int(features.get("eng_st_trend_dir", 0))
        except Exception:
            trend = 0

        color = "rgba(38, 166, 154, 0.1)" if trend > 0 else "rgba(239, 83, 80, 0.1)"

        try:
            chart.box(start_time=start_time, end_time=end_time, color=color, text=f"Wave {wave.get('wave_id', '')}")
        except Exception:
            # Shading is optional; ignore if unsupported
            pass


