"""
Enhanced Forecaster with full technical indicator integration.

This module combines:
- All technical indicators (momentum, volume, volatility)
- SuperTrend AI adaptive signals
- LightGBM with linear_tree for extrapolation
- Multi-indicator signal generation

Phase 3 implementation from technicals_and_ml_improvement.md
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

from ..features.technical_indicators import add_all_technical_features
from ..features.multi_timeframe import (
    MultiTimeframeFeatures,
    fetch_multi_timeframe_data,
)
from ..strategies.supertrend_ai import SuperTrendAI
from ..strategies.multi_indicator_signals import MultiIndicatorSignalGenerator

# Try to import LightGBM, fall back to sklearn if not available
try:
    from .lightgbm_forecaster import LightGBMForecaster, LIGHTGBM_AVAILABLE
except ImportError:
    LIGHTGBM_AVAILABLE = False
    LightGBMForecaster = None

logger = logging.getLogger(__name__)


# Enhanced feature list including all new indicators
ENHANCED_FEATURES = [
    # Basic returns
    "returns_1d",
    "returns_5d",
    "returns_20d",
    # Moving averages
    "sma_5",
    "sma_20",
    "sma_50",
    "ema_12",
    "ema_26",
    # MACD
    "macd",
    "macd_signal",
    "macd_hist",
    # RSI
    "rsi_14",
    # Bollinger Bands
    "bb_upper",
    "bb_middle",
    "bb_lower",
    "bb_width",
    # ATR
    "atr_14",
    # Volume
    "volume_ratio",
    # Volatility
    "volatility_20d",
    # Price position
    "price_vs_sma20",
    "price_vs_sma50",
    # NEW: Momentum indicators
    "stoch_k",
    "stoch_d",
    "kdj_k",
    "kdj_d",
    "kdj_j",
    "kdj_j_minus_d",
    "adx",
    "plus_di",
    "minus_di",
    # NEW: Volume indicators
    "obv",
    "obv_sma",
    "mfi",
    "vroc",
    # NEW: Volatility indicators
    "keltner_upper",
    "keltner_middle",
    "keltner_lower",
    # NEW: SuperTrend
    "supertrend",
    "supertrend_trend",
    # Phase 1: Volume-based S/R Strength (6 features)
    "support_volume_strength",
    "resistance_volume_strength",
    "support_touches_count",
    "resistance_touches_count",
    "support_strength_score",
    "resistance_strength_score",
    # Phase 2: S/R Hold Probabilities (2 features)
    "support_hold_probability",
    "resistance_hold_probability",
    # Phase 3: Polynomial S/R (4 features)
    "polynomial_support",
    "polynomial_resistance",
    "support_slope",
    "resistance_slope",
]


class EnhancedForecaster:
    """
    Enhanced forecaster combining all technical indicators with ML.

    Features:
    - Comprehensive technical indicator suite (25+ indicators)
    - SuperTrend AI with adaptive factor selection
    - Multi-indicator signal generation
    - LightGBM with linear_tree for extrapolation
    - Classification (Bullish/Neutral/Bearish) and regression modes

    Usage:
        forecaster = EnhancedForecaster()
        result = forecaster.generate_forecast(df, horizon="1W")
        # Returns: {
        #     'label': 'bullish',
        #     'confidence': 0.75,
        #     'trend_analysis': {...},
        #     'supertrend_info': {...},
        #     'points': [...]
        # }
    """

    def __init__(
        self,
        use_lightgbm: bool = True,
        use_multi_timeframe: bool = False,
        timeframes: List[str] = None,
        classification_thresholds: Tuple[float, float] = (-0.02, 0.02),
        min_training_samples: int = 100,
    ):
        """
        Initialize the enhanced forecaster.

        Args:
            use_lightgbm: Use LightGBM if available (else RandomForest)
            use_multi_timeframe: Enable multi-timeframe feature engineering
            timeframes: Timeframes to use (default: ["h1", "d1", "w1"])
            classification_thresholds: (bearish, bullish) return thresholds
            min_training_samples: Minimum samples required for training
        """
        self.use_lightgbm = use_lightgbm and LIGHTGBM_AVAILABLE
        self.use_multi_timeframe = use_multi_timeframe
        self.timeframes = timeframes or ["h1", "d1", "w1"]
        self.classification_thresholds = classification_thresholds
        self.min_training_samples = min_training_samples

        # Models
        self.classifier = None
        self.regressor = None
        self.scaler = StandardScaler()

        # Components
        self.signal_generator = MultiIndicatorSignalGenerator()
        self.supertrend_info: Dict[str, Any] = {}
        self.mtf_features: MultiTimeframeFeatures = None
        if self.use_multi_timeframe:
            self.mtf_features = MultiTimeframeFeatures(timeframes=self.timeframes)

        # State
        self.feature_columns: List[str] = []
        self.is_trained = False

        logger.info(
            f"EnhancedForecaster initialized: "
            f"lightgbm={self.use_lightgbm}, "
            f"multi_timeframe={self.use_multi_timeframe}, "
            f"thresholds={classification_thresholds}"
        )

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare comprehensive feature set from OHLCV data.

        Adds all technical indicators and SuperTrend AI signals.

        Args:
            df: DataFrame with columns [ts, open, high, low, close, volume]

        Returns:
            DataFrame with all features added
        """
        # Add all technical indicators
        df = add_all_technical_features(df)

        # Add SuperTrend AI
        if len(df) >= 50:  # Need enough data for SuperTrend
            try:
                supertrend = SuperTrendAI(df)
                df, self.supertrend_info = supertrend.calculate()
                factor = self.supertrend_info.get("target_factor", 0)
                perf = self.supertrend_info.get("performance_index", 0)
                logger.info(f"SuperTrend: factor={factor:.2f}, perf={perf:.3f}")
            except Exception as e:
                logger.warning(f"SuperTrend AI failed: {e}")
                # Add placeholder columns
                df["supertrend"] = df["close"]
                df["supertrend_trend"] = 0
                df["supertrend_signal"] = 0

        return df

    def prepare_training_data(
        self,
        df: pd.DataFrame,
        horizon_days: int = 5,
        mode: str = "classification",
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prepare training data with features and labels.

        Args:
            df: DataFrame with technical indicators
            horizon_days: Number of days ahead to predict
            mode: 'classification' or 'regression'

        Returns:
            Tuple of (features_df, labels_series)
        """
        df = df.copy()

        # Calculate forward returns
        fwd_ret = df["close"].pct_change(periods=horizon_days)
        df["forward_return"] = fwd_ret.shift(-horizon_days)

        if mode == "classification":
            # Create labels: bullish (1), neutral (0), bearish (-1)
            low_thresh, high_thresh = self.classification_thresholds
            df["label"] = pd.cut(
                df["forward_return"],
                bins=[-np.inf, low_thresh, high_thresh, np.inf],
                labels=["bearish", "neutral", "bullish"],
            )
        else:
            df["label"] = df["forward_return"]

        # Drop rows with NaN labels
        df_clean = df.dropna(subset=["label"])

        # Select feature columns
        exclude_cols = [
            "ts",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "forward_return",
            "label",
        ]
        feature_cols = [
            col for col in df_clean.columns if col not in exclude_cols and not col.startswith("_")
        ]

        # Filter to available features
        available_features = [col for col in feature_cols if col in df_clean.columns]
        self.feature_columns = available_features

        X = df_clean[available_features].copy()
        y = df_clean["label"]

        # Handle any remaining NaN values
        X = X.ffill().fillna(0)

        n_samples = len(X)
        n_features = len(available_features)
        logger.info(f"Prepared {n_samples} samples with {n_features} features")
        if mode == "classification":
            logger.info(f"Label distribution: {y.value_counts().to_dict()}")

        return X, y

    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        mode: str = "classification",
    ) -> Dict[str, Any]:
        """
        Train the forecaster model.

        Args:
            X: Feature DataFrame
            y: Label series
            mode: 'classification' or 'regression'

        Returns:
            Dict with training metrics
        """
        if len(X) < self.min_training_samples:
            msg = f"Insufficient data: {len(X)} < {self.min_training_samples}"
            raise ValueError(msg)

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        if mode == "classification":
            self.classifier = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                random_state=42,
            )
            self.classifier.fit(X_scaled, y)
            train_score = self.classifier.score(X_scaled, y)
            logger.info(f"Classification training accuracy: {train_score:.3f}")

        else:  # regression
            if self.use_lightgbm and LightGBMForecaster is not None:
                self.regressor = LightGBMForecaster()
                X_df = pd.DataFrame(X_scaled, columns=X.columns)
                self.regressor.train(X_df, y)
            else:
                from sklearn.ensemble import RandomForestRegressor

                self.regressor = RandomForestRegressor(
                    n_estimators=100, max_depth=10, random_state=42
                )
                self.regressor.fit(X_scaled, y)

            train_score = 0.0  # Regression doesn't have simple accuracy

        self.is_trained = True

        return {
            "n_samples": len(X),
            "n_features": len(self.feature_columns),
            "train_score": train_score,
            "mode": mode,
        }

    def predict(
        self,
        X: pd.DataFrame,
        mode: str = "classification",
    ) -> Tuple[Any, float, np.ndarray]:
        """
        Make a prediction on new data.

        Args:
            X: Feature DataFrame
            mode: 'classification' or 'regression'

        Returns:
            Tuple of (prediction, confidence, probabilities/values)
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")

        # Ensure features match training
        X = X[self.feature_columns].copy()
        X = X.ffill().fillna(0)

        # Scale features
        X_scaled = self.scaler.transform(X)

        if mode == "classification":
            predictions = self.classifier.predict(X_scaled)
            probabilities = self.classifier.predict_proba(X_scaled)

            label = predictions[-1]
            proba = probabilities[-1]
            confidence = float(proba.max())

            return label, confidence, probabilities

        else:  # regression
            if self.use_lightgbm and hasattr(self.regressor, "predict"):
                predictions = self.regressor.predict(
                    pd.DataFrame(X_scaled, columns=self.feature_columns)
                )
            else:
                predictions = self.regressor.predict(X_scaled)

            prediction = predictions[-1]
            confidence = 1.0 - min(abs(prediction) * 10, 0.5)  # Heuristic

            return prediction, confidence, predictions

    def generate_forecast(
        self,
        df: pd.DataFrame,
        horizon: str = "1W",
    ) -> Dict[str, Any]:
        """
        Generate a complete forecast with all enhancements.

        Args:
            df: DataFrame with OHLC data (indicators will be added)
            horizon: Forecast horizon ("1D", "1W", "1M")

        Returns:
            Comprehensive forecast dictionary
        """
        # Parse horizon
        horizon_days = self._parse_horizon(horizon)

        # Prepare features (adds all indicators + SuperTrend)
        df = self.prepare_features(df)

        # Get trend analysis from multi-indicator signals
        trend_analysis = self.signal_generator.get_trend_analysis(df)

        # Prepare training data
        X, y = self.prepare_training_data(df, horizon_days=horizon_days)

        # Train model
        train_metrics = self.train(X, y)

        # Get last row features for prediction
        last_features = X.tail(1)
        last_close = df["close"].iloc[-1]
        last_ts = df["ts"].iloc[-1]

        # Predict
        label, confidence, probabilities = self.predict(last_features)

        # Generate forecast points
        points = self._generate_forecast_points(
            last_ts, last_close, label, confidence, horizon_days
        )

        return {
            "label": label,
            "confidence": confidence,
            "horizon": horizon,
            "points": points,
            "trend_analysis": trend_analysis,
            "supertrend_info": {
                "target_factor": self.supertrend_info.get("target_factor", 3.0),
                "performance_index": self.supertrend_info.get("performance_index", 0.0),
                "signal_strength": self.supertrend_info.get("signal_strength", 5),
            },
            "train_metrics": train_metrics,
            "feature_count": len(self.feature_columns),
        }

    def _parse_horizon(self, horizon: str) -> int:
        """Parse horizon string to number of days."""
        horizon_map = {
            "1D": 1,
            "1W": 5,  # 5 trading days
            "2W": 10,
            "1M": 20,  # ~20 trading days
        }
        if horizon not in horizon_map:
            valid = list(horizon_map.keys())
            raise ValueError(f"Unknown horizon: {horizon}. Use: {valid}")
        return horizon_map[horizon]

    def _generate_forecast_points(
        self,
        last_ts: datetime,
        last_close: float,
        label: str,
        confidence: float,
        horizon_days: int,
    ) -> List[Dict[str, Any]]:
        """
        Generate forecast points for visualization.

        Creates a projection with confidence bands based on
        prediction and SuperTrend performance.
        """
        points = []

        # Determine expected return based on label
        return_map = {
            "bullish": 0.03,
            "bearish": -0.03,
            "neutral": 0.0,
        }
        expected_return = return_map.get(label, 0.0)

        # Scale by confidence and SuperTrend performance
        supertrend_perf = self.supertrend_info.get("performance_index", 0.5)
        expected_return *= confidence * (0.5 + 0.5 * supertrend_perf)

        # Generate daily points
        for i in range(1, horizon_days + 1):
            forecast_ts = last_ts + timedelta(days=i)
            progress = i / horizon_days

            # Linear interpolation of price movement
            forecast_value = last_close * (1 + expected_return * progress)

            # Confidence bands (wider for less confident predictions)
            uncertainty = (1 - confidence) * 0.05
            uncertainty += (1 - supertrend_perf) * 0.02
            lower_bound = forecast_value * (1 - uncertainty)
            upper_bound = forecast_value * (1 + uncertainty)

            if hasattr(forecast_ts, "timestamp"):
                ts_val = int(forecast_ts.timestamp())
            else:
                ts_val = forecast_ts

            points.append(
                {
                    "ts": ts_val,
                    "value": round(forecast_value, 2),
                    "lower": round(lower_bound, 2),
                    "upper": round(upper_bound, 2),
                }
            )

        return points

    def get_feature_importance(self) -> Dict[str, float]:
        """
        Get feature importance scores from the trained model.

        Returns:
            Dict mapping feature names to importance scores
        """
        if not self.is_trained:
            return {}

        if self.classifier is not None:
            importance = self.classifier.feature_importances_
        elif self.regressor is not None:
            if hasattr(self.regressor, "get_feature_importance"):
                return self.regressor.get_feature_importance()
            elif hasattr(self.regressor, "feature_importances_"):
                importance = self.regressor.feature_importances_
            else:
                return {}
        else:
            return {}

        return dict(zip(self.feature_columns, importance))

    def get_top_features(self, n: int = 10) -> List[Tuple[str, float]]:
        """
        Get top N most important features.

        Returns:
            List of (feature_name, importance) tuples, sorted by importance
        """
        importance = self.get_feature_importance()
        sorted_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)
        return sorted_features[:n]

    def generate_forecast_multi_timeframe(
        self,
        symbol: str,
        horizon: str = "1W",
    ) -> Dict[str, Any]:
        """
        Generate forecast using multi-timeframe features.

        Fetches data for multiple timeframes from the database and
        computes cross-timeframe features for enhanced prediction.

        Args:
            symbol: Stock ticker symbol
            horizon: Forecast horizon ("1D", "1W", "1M")

        Returns:
            Comprehensive forecast with multi-timeframe analysis
        """
        if not self.use_multi_timeframe or self.mtf_features is None:
            raise ValueError(
                "Multi-timeframe not enabled. " "Initialize with use_multi_timeframe=True"
            )

        # Fetch data for all timeframes
        data_dict = fetch_multi_timeframe_data(symbol, timeframes=self.timeframes)

        if not data_dict:
            raise ValueError(f"No data available for {symbol}")

        # Compute multi-timeframe features
        features_df = self.mtf_features.compute_all_timeframes(data_dict, align_to="d1")

        if features_df.empty:
            raise ValueError(f"Could not compute features for {symbol}")

        # Add alignment and trend scores
        features_df["tf_alignment"] = self.mtf_features.compute_alignment_score(features_df)
        features_df["tf_trend_strength"] = self.mtf_features.compute_trend_strength(features_df)

        # Parse horizon
        horizon_days = self._parse_horizon(horizon)

        # Prepare training data from multi-timeframe features
        X, y = self._prepare_mtf_training_data(features_df, horizon_days)

        # Train model
        train_metrics = self.train(X, y)

        # Get last row for prediction
        last_features = X.tail(1)
        last_close = features_df["close"].iloc[-1]
        last_ts = features_df["ts"].iloc[-1]

        # Predict
        label, confidence, probabilities = self.predict(last_features)

        # Generate forecast points
        points = self._generate_forecast_points(
            last_ts, last_close, label, confidence, horizon_days
        )

        # Get alignment info
        last_alignment = features_df["tf_alignment"].iloc[-1]
        last_strength = features_df["tf_trend_strength"].iloc[-1]

        return {
            "label": label,
            "confidence": confidence,
            "horizon": horizon,
            "points": points,
            "multi_timeframe_info": {
                "timeframes": self.timeframes,
                "alignment_score": float(last_alignment),
                "trend_strength": float(last_strength),
                "feature_count": len(self.feature_columns),
            },
            "train_metrics": train_metrics,
        }

    def _prepare_mtf_training_data(
        self,
        features_df: pd.DataFrame,
        horizon_days: int,
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prepare training data from multi-timeframe features.

        Args:
            features_df: DataFrame with multi-timeframe features
            horizon_days: Number of days ahead to predict

        Returns:
            Tuple of (features_df, labels_series)
        """
        df = features_df.copy()

        # Calculate forward returns
        df["forward_return"] = df["close"].pct_change(periods=horizon_days).shift(-horizon_days)

        # Create labels
        low_thresh, high_thresh = self.classification_thresholds
        df["label"] = pd.cut(
            df["forward_return"],
            bins=[-np.inf, low_thresh, high_thresh, np.inf],
            labels=["bearish", "neutral", "bullish"],
        )

        # Drop rows with NaN labels
        df_clean = df.dropna(subset=["label"])

        # Get feature columns (exclude metadata)
        feature_cols = self.mtf_features.get_feature_columns(df_clean)

        # Also include alignment and strength scores
        extra_cols = ["tf_alignment", "tf_trend_strength"]
        feature_cols = [c for c in feature_cols if c in df_clean.columns]
        feature_cols.extend([c for c in extra_cols if c in df_clean.columns])

        self.feature_columns = feature_cols

        X = df_clean[feature_cols].copy()
        y = df_clean["label"]

        # Handle NaN values
        X = X.ffill().fillna(0)

        logger.info(
            f"Prepared MTF training data: " f"{len(X)} samples, {len(feature_cols)} features"
        )

        return X, y
