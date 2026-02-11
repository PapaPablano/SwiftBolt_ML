"""
Unified data loading and feature engineering pipeline.
Used by all tabs—technical analysis, wave detection, etc.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from core.wave_detection.ultimate_feature_engineer import UltimateFeatureEngineer
from core.wave_detection.enhanced_wave_detector import EnhancedWaveDetector


class DataPipeline:
    """Load, engineer, and cache data for dashboard tabs."""

    @staticmethod
    @st.cache_data(ttl=300)
    def load_ohlcv(symbol: str, timeframe: str, days: int) -> Optional[pd.DataFrame]:
        """Load OHLCV data (cached)."""
        try:
            # Prefer test utils loader if available; otherwise expect project loader in PYTHONPATH
            try:
                from tests.utils import load_data as _ld  # type: ignore

                df = _ld(symbol, timeframe, days=days)
            except Exception:
                # Fallback: require a production loader to be available to the environment
                raise RuntimeError("No data loader found. Ensure tests.utils.load_data is available.")

            if df is None or df.empty:
                st.error(f"❌ No data loaded for {symbol} {timeframe}")
                return None

            if "time" not in df.columns and df.index.name == "time":
                df = df.reset_index()

            st.success(f"✅ Loaded {len(df)} bars: {symbol} {timeframe}")
            return df
        except Exception as e:
            st.error(f"❌ Data load error: {str(e)}")
            return None

    @staticmethod
    @st.cache_data(ttl=300)
    def engineer_features(df_ohlcv: pd.DataFrame) -> Optional[pd.DataFrame]:
        """Generate engineered features (cached)."""
        try:
            engineer = UltimateFeatureEngineer()
            df_features = engineer.engineer_features(df_ohlcv)
            st.success(f"✅ Engineered {len(df_features.columns)} features")
            return df_features
        except Exception as e:
            st.error(f"❌ Feature engineering error: {str(e)}")
            return None

    @staticmethod
    @st.cache_data(ttl=300)
    def detect_waves(df_chart: pd.DataFrame, timeframe: str) -> Optional[list]:
        """Detect waves and enrich with features (cached)."""
        try:
            detector = EnhancedWaveDetector()
            waves = detector.detect_waves_enhanced(df_chart, timeframe=timeframe)
            st.success(f"✅ Detected {len(waves)} waves")
            return waves
        except Exception as e:
            st.error(f"❌ Wave detection error: {str(e)}")
            return None

    @staticmethod
    def full_pipeline(symbol: str, timeframe: str, days: int) -> dict:
        """Full pipeline: load → features → waves. Returns status + data."""
        result = {"status": "error", "ohlcv": None, "features": None, "waves": None}

        df_ohlcv = DataPipeline.load_ohlcv(symbol, timeframe, days)
        if df_ohlcv is None:
            return result
        result["ohlcv"] = df_ohlcv

        df_features = DataPipeline.engineer_features(df_ohlcv)
        if df_features is None:
            return result
        result["features"] = df_features

        waves = DataPipeline.detect_waves(df_features, timeframe)
        if waves is None:
            return result
        result["waves"] = waves

        result["status"] = "success"
        return result


