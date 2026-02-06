"""Baseline ML forecaster using XGBoost for price movement prediction."""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler
from xgboost import XGBClassifier

from config.settings import settings
from src.data.data_validator import OHLCValidator, ValidationResult
from src.features.adaptive_thresholds import AdaptiveThresholds
from src.features.lookahead_checks import LookaheadViolation, assert_label_gap
from src.features.temporal_indicators import (
    SIMPLIFIED_FEATURES,
    TemporalFeatureEngineer,
    compute_simplified_features,
)
from src.monitoring.confidence_calibrator import ConfidenceCalibrator

logger = logging.getLogger(__name__)


# Default label encoding (3-class); binary uses dynamic 0/1 from unique y
LABEL_DECODE = {0: "bearish", 1: "neutral", 2: "bullish"}


class BaselineForecaster:
    """
    Baseline forecaster using XGBoost to predict price direction.

    Predicts: Bullish (up >2%), Neutral (-2% to 2%), Bearish (down >2%)
    """

    def __init__(self) -> None:
        """Initialize the forecaster."""
        self.scaler = RobustScaler()
        self.model = XGBClassifier(
            n_estimators=500,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=3,
            gamma=0.1,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=42,
            n_jobs=-1,
            eval_metric="mlogloss",
        )
        self.feature_columns: list[str] = []
        self.is_trained = False
        self._last_df: Optional[pd.DataFrame] = None  # Cache for predict method
        self._label_decode: dict[int, str] = {}  # 0/1/2 -> bearish/neutral/bullish (set at train)

    def prepare_training_data(
        self,
        df: pd.DataFrame,
        horizon_days: int = 1,
        sentiment_series: pd.Series | None = None,
    ) -> tuple[pd.DataFrame, pd.Series]:
        """
        Prepare training data with adaptive thresholds and temporal features.
        Uses simplified feature set (compute_simplified_features) and start_idx=50 (min lookback for lags).
        sentiment_series: optional daily sentiment (index=date) to merge; if None, sentiment_score=0.
        """
        df = df.copy()
        df = compute_simplified_features(df, sentiment_series=sentiment_series)

        bearish_thresh, bullish_thresh = AdaptiveThresholds.compute_thresholds_horizon(
            df, horizon_days=horizon_days
        )
        logger.info(
            "Adaptive thresholds (%.0fD): bearish=%.4f, bullish=%.4f",
            horizon_days,
            bearish_thresh,
            bullish_thresh,
        )

        horizon_days_int = max(1, int(np.ceil(horizon_days)))
        forward_returns = (
            df["close"].pct_change(periods=horizon_days_int).shift(-horizon_days_int).copy()
        )
        if horizon_days_int > 0:
            forward_returns.iloc[-horizon_days_int:] = np.nan

        engineer = TemporalFeatureEngineer()
        X_list: list[dict[str, Any]] = []
        y_list: list[str] = []

        valid_samples = 0
        nan_returns = 0

        # Min lookback 50 bars (lags/supertrend); sma_200 uses min_periods=1 so valid from row 0
        start_idx = 50
        end_idx = len(df) - horizon_days_int
        
        logger.debug(
            "Training data range: start_idx=%d, end_idx=%d, df_len=%d, horizon=%.3f (int=%d)",
            start_idx,
            end_idx,
            len(df),
            horizon_days,
            horizon_days_int,
        )
        
        for idx in range(start_idx, end_idx):
            features = engineer.add_features_to_point(df, idx)
            try:
                assert_label_gap(df, idx, horizon_days_int)
            except LookaheadViolation as exc:
                logger.error(
                    "Lookahead violation detected (idx=%s, horizon=%s): %s",
                    idx,
                    horizon_days_int,
                    exc,
                )
                raise
            actual_return = forward_returns.iloc[idx]

            if pd.notna(actual_return):
                X_list.append(features)
                if actual_return > bullish_thresh:
                    label = "bullish"
                elif actual_return < bearish_thresh:
                    label = "bearish"
                else:
                    label = "neutral"
                y_list.append(label)
                valid_samples += 1
            else:
                nan_returns += 1

        X = pd.DataFrame(X_list)
        y = pd.Series(y_list)

        logger.info(
            "Training data prepared: %s samples (valid: %s, NaN returns: %s, df_len: %s, range: %s-%s)",
            len(X),
            valid_samples,
            nan_returns,
            len(df),
            start_idx,
            end_idx,
        )
        if len(y) > 0:
            logger.info("Label distribution: %s", y.value_counts().to_dict())
        else:
            logger.warning("No valid training samples generated!")

        return X, y

    def prepare_training_data_binary(
        self,
        df: pd.DataFrame,
        horizon_days: int = 1,
        sentiment_series: pd.Series | None = None,
        threshold_pct: float = 0.005,
        add_simple_regime: bool = False,
    ) -> tuple[pd.DataFrame, pd.Series]:
        """
        Binary classification: bullish vs bearish only.
        Drops small moves (|return| < threshold_pct) as too noisy.
        Uses same feature pipeline as prepare_training_data; only labels and filter differ.
        When add_simple_regime=True, adds stock-only trend/momentum regime (no VIX/SPY).
        """
        df = df.copy()
        df = compute_simplified_features(df, sentiment_series=sentiment_series, add_volatility=True)
        if add_simple_regime:
            from src.features.regime_features_simple import add_all_simple_regime_features
            df = add_all_simple_regime_features(df)

        horizon_days_int = max(1, int(np.ceil(horizon_days)))
        forward_returns = (
            df["close"]
            .pct_change(periods=horizon_days_int)
            .shift(-horizon_days_int)
            .copy()
        )
        if horizon_days_int > 0:
            forward_returns.iloc[-horizon_days_int:] = np.nan

        engineer = TemporalFeatureEngineer()
        X_list: list[dict[str, Any]] = []
        y_list: list[str] = []

        # Min lookback 50 bars (lags/supertrend); sma_200 uses min_periods=1 so valid from row 0
        start_idx = 50
        end_idx = len(df) - horizon_days_int
        filtered_out = 0

        date_list: list[pd.Timestamp] = []
        ts_col = df["ts"] if "ts" in df.columns else df.index
        for idx in range(start_idx, end_idx):
            actual_return = forward_returns.iloc[idx]
            if not pd.notna(actual_return):
                continue
            if abs(actual_return) <= threshold_pct:
                filtered_out += 1
                continue
            try:
                assert_label_gap(df, idx, horizon_days_int)
            except LookaheadViolation as exc:
                logger.error(
                    "Lookahead violation detected (binary idx=%s, horizon=%s): %s",
                    idx,
                    horizon_days_int,
                    exc,
                )
                raise
            features = engineer.add_features_to_point(df, idx)
            X_list.append(features)
            y_list.append("bullish" if actual_return > 0 else "bearish")
            date_list.append(pd.to_datetime(ts_col.iloc[idx]))

        X = pd.DataFrame(X_list)
        y = pd.Series(y_list)
        dates = pd.Series(date_list) if date_list else pd.Series(dtype="datetime64[ns]")

        logger.info(
            "Binary training data: %s samples (filtered out %s moves < %.2f%%), "
            "bullish=%.1f%%, bearish=%.1f%%",
            len(X),
            filtered_out,
            threshold_pct * 100,
            (y == "bullish").mean() * 100 if len(y) > 0 else 0,
            (y == "bearish").mean() * 100 if len(y) > 0 else 0,
        )
        return X, y, dates

    def train(self, X: pd.DataFrame, y: pd.Series, min_samples: Optional[int] = None) -> None:
        """
        Train the forecaster model with enhanced metrics logging.
        
        Args:
            X: Feature DataFrame
            y: Label Series
            min_samples: Minimum samples required (defaults to settings.min_bars_for_training)
                        Use lower value for walk-forward scenarios with smaller windows
        """
        min_required = min_samples if min_samples is not None else settings.min_bars_for_training
        if len(X) < min_required:
            raise ValueError(
                f"Insufficient training data: {len(X)} < {min_required}"
            )

        # Exclude non-numeric columns (e.g., timestamps)
        numeric_cols = X.select_dtypes(include=["number"]).columns.tolist()
        X = X[numeric_cols]
        self.feature_columns = numeric_cols
        X_scaled = self.scaler.fit_transform(X)

        # XGBoost expects contiguous 0, 1, ..., k-1; encode from unique labels
        unique_labels = sorted(set(str(l).lower() for l in y))
        label_encode = {lbl: i for i, lbl in enumerate(unique_labels)}
        self._label_decode = {i: lbl for lbl, i in label_encode.items()}
        y_encoded = np.array([label_encode.get(str(l).lower(), 0) for l in y])

        logger.info("Training XGBoost model...")
        self.model.fit(X_scaled, y_encoded)

        from sklearn.metrics import (
            accuracy_score,
            confusion_matrix,
            f1_score,
            precision_score,
            recall_score,
        )

        predictions = self.model.predict(X_scaled)
        accuracy = accuracy_score(y_encoded, predictions)
        precision = precision_score(
            y_encoded,
            predictions,
            average="weighted",
            zero_division=0,
        )
        recall = recall_score(
            y_encoded,
            predictions,
            average="weighted",
            zero_division=0,
        )
        f1 = f1_score(y_encoded, predictions, average="weighted", zero_division=0)
        cm = confusion_matrix(y_encoded, predictions)
        # Feature importances (RF supports this attribute)
        importances = getattr(self.model, "feature_importances_", None)
        if importances is not None and len(importances) == len(self.feature_columns):
            importance_pairs = sorted(
                zip(self.feature_columns, importances),
                key=lambda kv: kv[1],
                reverse=True,
            )
            top_features = importance_pairs[:10]
        else:
            top_features = []

        self.training_stats = {
            "timestamp": datetime.now().isoformat(),
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "confusion_matrix": cm.tolist(),
            "n_samples": len(X),
            "n_features": len(self.feature_columns),
            "class_distribution": y.value_counts().to_dict(),
            "top_features": top_features,
        }

        logger.info(
            "Training metrics - acc=%.3f, prec=%.3f, rec=%.3f, f1=%.3f",
            accuracy,
            precision,
            recall,
            f1,
        )
        logger.info("Confusion matrix:\n%s", cm)
        if top_features:
            logger.info(
                "Top features: %s",
                ", ".join(f"{name}={score:.3f}" for name, score in top_features),
            )

        self.is_trained = True

    def fit(self, df: pd.DataFrame, horizon_days: int = 1) -> "BaselineForecaster":
        """
        Fit the model on OHLC dataframe (compatible with ensemble interface).
        
        This method provides compatibility with EnsembleForecaster interface.
        It prepares features and trains the model in one step.
        
        Args:
            df: DataFrame with OHLC + technical indicators
            horizon_days: Forecast horizon in days (1, 5, 20, etc.)
        
        Returns:
            self (for method chaining)
        """
        # Store df for later predict calls
        self._last_df = df.copy()
        
        # Prepare training data
        X, y = self.prepare_training_data(df, horizon_days=horizon_days)
        
        # Train model
        if len(X) >= settings.min_bars_for_training:
            self.train(X, y)
        else:
            logger.warning(
                f"Insufficient data for training: {len(X)} < {settings.min_bars_for_training}"
            )
        
        return self

    def predict(self, X: pd.DataFrame | None = None, horizon_days: int = 1) -> dict[str, Any]:
        """
        Make a prediction on new data.

        This method has dual interfaces:
        1. Called with X (features DataFrame) - original interface for internal use
        2. Called with df (OHLC DataFrame) - ensemble-compatible interface
        
        Args:
            X: Feature DataFrame (single row or multiple rows) OR OHLC DataFrame
            horizon_days: Forecast horizon (used if X is OHLC data)

        Returns:
            Dict with label, confidence, probabilities (ensemble-compatible)
            OR Tuple (label, confidence, probabilities) for internal use
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")

        # Check if X is OHLC data (has 'close' column) or features
        if X is not None and 'close' in X.columns:
            # OHLC data - run same pipeline as training so feature columns match
            df = compute_simplified_features(X.copy(), sentiment_series=None)
            engineer = TemporalFeatureEngineer()
            last_idx = len(df) - 1
            features = engineer.add_features_to_point(df, last_idx)
            X_features = pd.DataFrame([features])
        else:
            # Already feature data
            X_features = X if X is not None else self._last_df
            if X_features is None:
                raise ValueError("No features provided and no cached dataframe available")

        # Ensure features match training
        X_features = X_features[self.feature_columns]

        # Scale features
        X_scaled = self.scaler.transform(X_features)

        # Predict (XGBoost returns 0/1/2; decode to bearish/neutral/bullish)
        predictions_encoded = self.model.predict(X_scaled)
        probabilities = self.model.predict_proba(X_scaled)

        # Get most recent prediction (last row)
        label_encoded = int(predictions_encoded[-1])
        label = self._label_decode.get(label_encoded, LABEL_DECODE.get(label_encoded, "neutral"))
        proba = probabilities[-1]
        confidence = float(proba.max())

        # proba order follows _label_decode (0,1,...,k-1)
        proba_dict = {
            self._label_decode.get(i, LABEL_DECODE.get(i, "neutral")): float(proba[i])
            for i in range(min(len(proba), len(self._label_decode) or 3))
        }

        logger.info(f"Prediction: {label} (confidence: {confidence:.3f})")
        logger.info(f"Probabilities: {proba_dict}")

        return {
            "label": label,
            "confidence": confidence,
            "probabilities": proba_dict,
            "raw_probabilities": probabilities,
        }

    def generate_forecast(
        self,
        df: pd.DataFrame,
        horizon: str,
        calibrator: Optional[ConfidenceCalibrator] = None,
        validate_data: bool = True,
    ) -> dict[str, Any]:
        """
        Generate a complete forecast with label, confidence, and future points.

        Args:
            df: DataFrame with OHLC + technical indicators
            horizon: Forecast horizon ("1D", "1W", etc.)
            calibrator: Optional confidence calibrator for adjusting scores
            validate_data: Whether to validate OHLC data before processing

        Returns:
            Forecast dictionary with label, confidence, and points
        """
        # Validate data if requested
        data_quality_multiplier = 1.0
        validation_result: Optional[ValidationResult] = None

        if validate_data:
            validator = OHLCValidator()
            df, validation_result = validator.validate(df, fix_issues=True)

            if validation_result and not validation_result.is_valid:
                logger.warning(f"Data quality issues detected: {validation_result.issues}")
                # Apply slight confidence penalty for data with issues
                data_quality_multiplier = max(
                    0.9, 1.0 - (validation_result.rows_flagged / len(df) * 0.2)
                )

        # Parse horizon
        horizon_days = self._parse_horizon(horizon)

        # Prepare training data
        X, y = self.prepare_training_data(df, horizon_days=horizon_days)

        # Calculate data quality multiplier based on sample size
        # Less data = lower confidence (per improvement plan 1.1)
        sample_size_multiplier = min(1.0, len(X) / settings.min_bars_for_high_confidence)

        # Train model
        self.train(X, y)

        # Get last row features for prediction
        last_features = X.tail(1)
        last_close = df["close"].iloc[-1]
        last_ts = pd.to_datetime(df["ts"].iloc[-1]).to_pydatetime()

        # Predict
        pred_result = self.predict(last_features)
        label = pred_result["label"]
        raw_confidence = pred_result["confidence"]
        probabilities = pred_result["raw_probabilities"]
        proba_dict = pred_result["probabilities"]

        # Apply confidence adjustments
        adjusted_confidence = raw_confidence

        # 1. Apply calibration if calibrator is provided
        if calibrator and calibrator.is_fitted:
            adjusted_confidence = calibrator.calibrate(adjusted_confidence)
            logger.info(f"Calibration: {raw_confidence:.3f} -> {adjusted_confidence:.3f}")

        # 2. Apply data quality multiplier
        adjusted_confidence *= data_quality_multiplier

        # 3. Apply sample size multiplier
        adjusted_confidence *= sample_size_multiplier

        # Ensure confidence stays in valid range
        adjusted_confidence = float(np.clip(adjusted_confidence, 0.40, 0.95))

        if adjusted_confidence != raw_confidence:
            logger.info(
                f"Final confidence: {raw_confidence:.3f} -> {adjusted_confidence:.3f} "
                f"(data_qual={data_quality_multiplier:.2f}, "
                f"sample_size={sample_size_multiplier:.2f})"
            )

        # Generate forecast points with probability-based directional estimates
        points = self._generate_forecast_points(
            last_ts, last_close, label, adjusted_confidence, horizon_days, proba_dict
        )

        return {
            "label": label,
            "confidence": adjusted_confidence,
            "raw_confidence": raw_confidence,
            "horizon": horizon,
            "points": points,
            "probabilities": probabilities,
            "data_quality": {
                "validation_issues": (validation_result.issues if validation_result else []),
                "quality_multiplier": data_quality_multiplier,
                "sample_size_multiplier": sample_size_multiplier,
                "n_training_samples": len(X),
            },
        }

    def _parse_horizon(self, horizon: str) -> int:
        """Parse horizon string to number of days."""
        if horizon == "1D":
            return 1
        elif horizon == "1W":
            return 5  # 5 trading days
        elif horizon == "1M":
            return 20  # ~20 trading days
        else:
            raise ValueError(f"Unknown horizon: {horizon}")

    def _generate_forecast_points(
        self,
        last_ts: datetime,
        last_close: float,
        label: str,
        confidence: float,
        horizon_days: int,
        probabilities: dict[str, float] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Generate forecast points for visualization.

        Creates directional projections based on the full probability distribution,
        ensuring forecasts always show meaningful price movement.
        """
        points = []

        # Calculate directional expected return from probability distribution
        if probabilities:
            # Use weighted probabilities for more nuanced predictions
            # Convert numpy types to float to avoid calculation issues
            bull_prob = float(probabilities.get("bullish", 0.0))
            bear_prob = float(probabilities.get("bearish", 0.0))

            # Net directional signal: positive = bullish bias, negative = bearish bias
            directional_bias = bull_prob - bear_prob

            # Base expected return scaled by directional strength
            # Maximum move is 5% for 100% directional confidence
            expected_return = directional_bias * 0.05

            logger.info(
                f"Directional: bull={bull_prob:.3f}, bear={bear_prob:.3f}, "
                f"bias={directional_bias:.3f}, return={expected_return:.4f}"
            )
        else:
            # Fallback to label-based approach
            if label == "bullish":
                expected_return = 0.03 * confidence
            elif label == "bearish":
                expected_return = -0.03 * confidence
            else:
                expected_return = 0.0

        # Ensure minimum visible movement for 1-week+ horizons
        # Even "neutral" should show slight directional tendency
        min_move = 0.005 * (horizon_days / 5)  # 0.5% per week minimum
        if abs(expected_return) < min_move and probabilities:
            # Use sign of directional bias or default to slight bullish
            sign = 1 if (probabilities.get("bullish", 0) >= probabilities.get("bearish", 0)) else -1
            expected_return = sign * min_move

        # Scale expected return by horizon (longer = more movement)
        # 1D = base, 1W = 1.5x, 1M = 2x
        horizon_multiplier = 1.0 + (horizon_days - 1) * 0.1
        expected_return *= min(horizon_multiplier, 2.0)

        logger.info(
            f"Forecast: close={last_close:.2f}, return={expected_return:.4f}, "
            f"horizon={horizon_days}d"
        )

        # Generate daily points
        for i in range(1, horizon_days + 1):
            forecast_ts = last_ts + timedelta(days=i)
            progress = i / horizon_days

            # Linear interpolation of price movement
            forecast_value = float(last_close) * (1 + expected_return * progress)

            # Confidence bands (wider for less confident, more for longer horizons)
            base_uncertainty = (1 - confidence) * 0.03  # 3% max base uncertainty
            time_uncertainty = progress * 0.02  # +2% uncertainty over time
            total_uncertainty = base_uncertainty + time_uncertainty

            lower_bound = forecast_value * (1 - total_uncertainty)
            upper_bound = forecast_value * (1 + total_uncertainty)

            if i == 1:
                logger.info(
                    f"  Day {i}: val={forecast_value:.2f}, "
                    f"low={lower_bound:.2f}, up={upper_bound:.2f}"
                )

            points.append(
                {
                    "ts": int(forecast_ts.timestamp()),
                    "value": round(forecast_value, 2),
                    "lower": round(lower_bound, 2),
                    "upper": round(upper_bound, 2),
                }
            )

        return points
