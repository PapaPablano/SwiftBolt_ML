"""
Logistic Regression Support/Resistance Indicator.

Port of LogisticRegressionIndicator.swift - Flux Charts style ML-based S/R detection
using logistic regression to predict level validity.

Features:
- On-the-fly training using RSI and body size features
- Probability prediction for each S/R level
- Retest and break tracking
- Signal detection

Usage:
    from src.features.logistic_sr_indicator import LogisticSRIndicator

    indicator = LogisticSRIndicator()
    result = indicator.calculate(df)

    print(result["support_levels"])
    print(result["resistance_levels"])
    print(result["signals"])
"""

import logging
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class LogisticSignalType(Enum):
    """Type of signal from logistic regression indicator."""

    SUPPORT_RETEST = "support_retest"
    SUPPORT_BREAK = "support_break"
    RESISTANCE_RETEST = "resistance_retest"
    RESISTANCE_BREAK = "resistance_break"


@dataclass
class LogisticSRLevel:
    """A detected S/R level with ML probability."""

    # Core properties
    is_support: bool
    level: float
    start_index: int
    start_timestamp: Optional[pd.Timestamp] = None

    # Tracking
    end_index: Optional[int] = None
    end_timestamp: Optional[pd.Timestamp] = None
    times_respected: int = 0

    # ML Features (binary: -1 or 1)
    detected_rsi: float = 0.0
    detected_body_size: float = 0.0

    # Prediction
    detected_by_regression: bool = False
    detected_prediction: float = 0.0

    # Retest tracking
    latest_retest_index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "is_support": self.is_support,
            "level": self.level,
            "start_index": self.start_index,
            "end_index": self.end_index,
            "times_respected": self.times_respected,
            "detected_rsi": self.detected_rsi,
            "detected_body_size": self.detected_body_size,
            "detected_by_regression": self.detected_by_regression,
            "probability": self.detected_prediction,
        }


@dataclass
class LogisticSRSettings:
    """Settings for LogisticSRIndicator."""

    pivot_length: int = 14
    target_respects: int = 3
    probability_threshold: float = 0.7
    hide_far_lines: bool = True
    retest_cooldown: int = 3
    learning_rate: float = 0.008


class LogisticRegressionModel:
    """
    Logistic regression model for S/R classification.

    Matches the Flux Charts PineScript implementation.
    Trains on-the-fly using binary RSI and body size features.
    """

    def __init__(self, learning_rate: float = 0.008):
        """
        Initialize the model.

        Args:
            learning_rate: Learning rate for gradient descent
        """
        self.learning_rate = learning_rate

    def predict(
        self,
        is_support: bool,
        rsi: float,
        body_size: float,
        existing_levels: List[LogisticSRLevel],
        target_respects: int,
    ) -> float:
        """
        Predict probability that a level is valid S/R.

        Trains on-the-fly using only pivots of the same type (support or resistance).

        Args:
            is_support: Whether we're predicting for a support or resistance level
            rsi: RSI value (binary: -1 or 1)
            body_size: Body size (binary: -1 or 1)
            existing_levels: All existing levels to train from
            target_respects: Number of respects needed to be "respected"

        Returns:
            Probability (0-1)
        """
        # Filter to only same-type pivots
        same_type_levels = [level for level in existing_levels if level.is_support == is_support]

        if not same_type_levels:
            return 0.0

        # Initialize weights fresh for each prediction (matching PineScript)
        base_bias = 1.0
        rsi_bias = 1.0
        body_size_bias = 1.0

        log_res = 0.0

        # Train on each same-type pivot and update weights
        for level in same_type_levels:
            is_respected = 1.0 if level.times_respected >= target_respects else -1.0

            p = self._logistic(
                level.detected_rsi,
                level.detected_body_size,
                base_bias,
                rsi_bias,
                body_size_bias,
            )

            loss_val = self._loss(is_respected, p)

            # Gradient descent update
            rsi_bias -= self.learning_rate * (p + loss_val) * level.detected_rsi
            body_size_bias -= self.learning_rate * (p + loss_val) * level.detected_body_size

            # Calculate prediction with updated weights
            log_res = self._logistic(
                rsi,
                body_size,
                base_bias,
                rsi_bias,
                body_size_bias,
            )

        return log_res

    def _logistic(
        self,
        x1: float,
        x2: float,
        bias: float,
        rsi_weight: float,
        body_size_weight: float,
    ) -> float:
        """Logistic function."""
        exponent = -(bias + rsi_weight * x1 + body_size_weight * x2)
        # Clip to avoid overflow
        exponent = max(-500, min(500, exponent))
        return 1.0 / (1.0 + math.exp(exponent))

    def _loss(self, y: float, prediction: float) -> float:
        """Binary cross-entropy loss (clipped to avoid log(0))."""
        clipped = max(min(prediction, 0.9999), 0.0001)
        return -y * math.log(clipped) - (1 - y) * math.log(1 - clipped)


class LogisticSRIndicator:
    """
    Flux Charts style logistic regression S/R indicator.

    Processes bars sequentially to match PineScript streaming behavior.
    Uses on-the-fly logistic regression to predict which S/R levels
    are most likely to hold.
    """

    def __init__(self, settings: Optional[LogisticSRSettings] = None):
        """
        Initialize the indicator.

        Args:
            settings: Configuration settings (uses defaults if not provided)
        """
        self.settings = settings or LogisticSRSettings()
        self._all_levels: List[LogisticSRLevel] = []
        self._regression_levels: List[LogisticSRLevel] = []
        self._signals: List[LogisticSignalType] = []
        self._rsi_values: List[float] = []
        self._body_size_values: List[float] = []
        self._atr_values: List[float] = []
        self._model = LogisticRegressionModel(self.settings.learning_rate)

    def calculate(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate logistic regression S/R levels.

        Processes bars sequentially to match PineScript streaming behavior.

        Args:
            df: DataFrame with 'open', 'high', 'low', 'close' columns

        Returns:
            Dict with:
            - support_levels: List of support levels with probabilities
            - resistance_levels: List of resistance levels with probabilities
            - signals: Current signals on last bar
            - all_levels: All detected levels (before filtering)
            - respected_levels: Levels with enough respects
        """
        # Reset state
        self._all_levels = []
        self._regression_levels = []
        self._signals = []

        if df.empty:
            return self._empty_result()

        # Pre-calculate indicators for all bars
        self._calculate_rsi(df)
        self._calculate_body_size(df)
        self._calculate_atr(df)

        # Process bars sequentially (streaming approach like PineScript)
        self._process_sequentially(df)

        # Detect signals on the last bar
        self._detect_signals(df)

        # Filter levels for display
        self._filter_levels(df)

        # Separate support and resistance levels
        support_levels = [level for level in self._regression_levels if level.is_support]
        resistance_levels = [level for level in self._regression_levels if not level.is_support]
        respected_levels = [
            level
            for level in self._all_levels
            if level.times_respected >= self.settings.target_respects
        ]

        # Find nearest support and resistance
        current_price = df["close"].iloc[-1]
        nearest_support = None
        nearest_resistance = None

        active_supports = [
            level.level
            for level in support_levels
            if level.end_index is None and level.level < current_price
        ]
        active_resistances = [
            level.level
            for level in resistance_levels
            if level.end_index is None and level.level > current_price
        ]

        if active_supports:
            nearest_support = max(active_supports)
        if active_resistances:
            nearest_resistance = min(active_resistances)

        # Calculate distances
        support_distance_pct = None
        resistance_distance_pct = None

        if nearest_support:
            support_distance_pct = (current_price - nearest_support) / current_price * 100

        if nearest_resistance:
            resistance_distance_pct = (nearest_resistance - current_price) / current_price * 100

        logger.info(
            f"LogisticSR: {len(support_levels)} support, {len(resistance_levels)} resistance, "
            f"{len(self._signals)} signals, {len(respected_levels)} respected"
        )

        return {
            "support_levels": [level.to_dict() for level in support_levels],
            "resistance_levels": [level.to_dict() for level in resistance_levels],
            "nearest_support": nearest_support,
            "nearest_resistance": nearest_resistance,
            "support_distance_pct": (
                round(support_distance_pct, 2) if support_distance_pct else None
            ),
            "resistance_distance_pct": (
                round(resistance_distance_pct, 2) if resistance_distance_pct else None
            ),
            "signals": [s.value for s in self._signals],
            "all_levels_count": len(self._all_levels),
            "respected_levels_count": len(respected_levels),
            "current_price": float(current_price),
        }

    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure."""
        return {
            "support_levels": [],
            "resistance_levels": [],
            "nearest_support": None,
            "nearest_resistance": None,
            "support_distance_pct": None,
            "resistance_distance_pct": None,
            "signals": [],
            "all_levels_count": 0,
            "respected_levels_count": 0,
            "current_price": None,
        }

    def _calculate_rsi(self, df: pd.DataFrame) -> None:
        """Calculate RSI for all bars."""
        n = len(df)
        self._rsi_values = [50.0] * n  # Default value

        if n <= self.settings.pivot_length:
            return

        closes = df["close"].values

        # Calculate price changes
        gains = [0.0]
        losses = [0.0]

        for i in range(1, n):
            change = closes[i] - closes[i - 1]
            gains.append(max(change, 0))
            losses.append(max(-change, 0))

        # Initial averages
        period = self.settings.pivot_length
        avg_gain = sum(gains[: period + 1]) / period
        avg_loss = sum(losses[: period + 1]) / period

        for i in range(period, n):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

            if avg_loss == 0:
                rs = 100
            else:
                rs = avg_gain / avg_loss

            self._rsi_values[i] = 100 - (100 / (1 + rs))

    def _calculate_body_size(self, df: pd.DataFrame) -> None:
        """Calculate candle body size for all bars."""
        self._body_size_values = [
            abs(float(row["close"]) - float(row["open"])) for _, row in df.iterrows()
        ]

    def _calculate_atr(self, df: pd.DataFrame) -> None:
        """Calculate ATR for all bars."""
        n = len(df)
        self._atr_values = [0.0] * n

        if n <= self.settings.pivot_length:
            return

        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values

        # Calculate true ranges
        true_ranges = []
        for i in range(n):
            if i == 0:
                true_ranges.append(highs[i] - lows[i])
            else:
                prev_close = closes[i - 1]
                tr = max(highs[i] - lows[i], abs(highs[i] - prev_close), abs(lows[i] - prev_close))
                true_ranges.append(tr)

        # Calculate ATR using Wilder's smoothing
        period = self.settings.pivot_length
        atr = sum(true_ranges[:period]) / period

        for i in range(period, n):
            atr = (atr * (period - 1) + true_ranges[i]) / period
            self._atr_values[i] = atr

    def _process_sequentially(self, df: pd.DataFrame) -> None:
        """
        Process bars sequentially to match PineScript streaming behavior.

        Order: 1) Update existing levels, 2) Detect new pivots, 3) Predict for new pivots
        """
        n = len(df)

        if n <= self.settings.pivot_length * 2:
            return

        # Process each bar sequentially
        for current_bar_index in range(self.settings.pivot_length * 2, n):
            current_bar = df.iloc[current_bar_index]

            # Step 1: Update all existing levels with current bar (retests/breaks)
            self._update_existing_levels(current_bar, current_bar_index)

            # Step 2: Check if there's a pivot at (current_bar_index - pivot_length)
            pivot_index = current_bar_index - self.settings.pivot_length

            if pivot_index >= self.settings.pivot_length:
                self._detect_and_predict_pivot(pivot_index, df)

    def _update_existing_levels(
        self,
        current_bar: pd.Series,
        current_index: int,
    ) -> None:
        """Update existing levels with current bar data (retests and breaks)."""
        for i, level in enumerate(self._all_levels):
            # Skip if already ended (broken)
            if level.end_index is not None:
                continue

            # Skip if current bar is before/at the level's start
            if current_index <= level.start_index + self.settings.pivot_length:
                continue

            if level.is_support:
                # Support level logic
                if current_bar["low"] < level.level:
                    # Price touched below support
                    if current_bar["close"] > level.level:
                        # Bounced back above - this is a retest
                        level.times_respected += 1

                        # Only update latest_retest_index if cooldown passed
                        if (
                            current_index
                            > level.latest_retest_index + self.settings.retest_cooldown
                        ):
                            level.latest_retest_index = current_index
                    else:
                        # Closed below support - BREAK
                        level.end_index = current_index
            else:
                # Resistance level logic
                if current_bar["high"] > level.level:
                    # Price touched above resistance
                    if current_bar["close"] < level.level:
                        # Bounced back below - this is a retest
                        level.times_respected += 1

                        if (
                            current_index
                            > level.latest_retest_index + self.settings.retest_cooldown
                        ):
                            level.latest_retest_index = current_index
                    else:
                        # Closed above resistance - BREAK
                        level.end_index = current_index

            self._all_levels[i] = level

    def _detect_and_predict_pivot(self, pivot_index: int, df: pd.DataFrame) -> None:
        """Detect pivot at a specific index and run prediction."""
        bar = df.iloc[pivot_index]
        highs = df["high"].values
        lows = df["low"].values
        n = len(df)

        # Check pivot high (resistance)
        is_high = True
        for offset in range(1, self.settings.pivot_length + 1):
            left_idx = pivot_index - offset
            right_idx = pivot_index + offset

            if left_idx >= 0 and highs[left_idx] > bar["high"]:
                is_high = False
                break
            if right_idx < n and highs[right_idx] > bar["high"]:
                is_high = False
                break

        if is_high:
            self._create_and_predict_level(
                is_support=False,
                level=float(bar["high"]),
                pivot_index=pivot_index,
                bar=bar,
            )

        # Check pivot low (support)
        is_low = True
        for offset in range(1, self.settings.pivot_length + 1):
            left_idx = pivot_index - offset
            right_idx = pivot_index + offset

            if left_idx >= 0 and lows[left_idx] < bar["low"]:
                is_low = False
                break
            if right_idx < n and lows[right_idx] < bar["low"]:
                is_low = False
                break

        if is_low:
            self._create_and_predict_level(
                is_support=True,
                level=float(bar["low"]),
                pivot_index=pivot_index,
                bar=bar,
            )

    def _create_and_predict_level(
        self,
        is_support: bool,
        level: float,
        pivot_index: int,
        bar: pd.Series,
    ) -> None:
        """Create a new level and run prediction using existing levels."""
        rsi = self._rsi_values[pivot_index]
        body_size = self._body_size_values[pivot_index]
        atr = self._atr_values[pivot_index]

        rsi_signed = 1.0 if rsi > 50 else -1.0
        body_size_signed = 1.0 if (atr > 0 and body_size > atr) else -1.0

        has_ts = "ts" in bar.index

        # Create new level (initially not detected by regression)
        new_level = LogisticSRLevel(
            is_support=is_support,
            level=level,
            start_index=pivot_index,
            start_timestamp=bar["ts"] if has_ts else None,
            detected_rsi=rsi_signed,
            detected_body_size=body_size_signed,
            detected_by_regression=False,
            detected_prediction=0.0,
        )

        # Add to all_levels first (PineScript adds before predict)
        self._all_levels.append(new_level)

        # Run prediction using ALL existing levels (including the one just added)
        prediction = self._model.predict(
            is_support=is_support,
            rsi=rsi_signed,
            body_size=body_size_signed,
            existing_levels=self._all_levels,
            target_respects=self.settings.target_respects,
        )

        # Update the level if prediction meets threshold
        if prediction >= self.settings.probability_threshold:
            new_level.detected_by_regression = True
            new_level.detected_prediction = prediction
            self._all_levels[-1] = new_level

    def _detect_signals(self, df: pd.DataFrame) -> None:
        """Detect signals on the current (last) bar."""
        if len(df) < 2:
            return

        current_bar = df.iloc[-1]
        current_index = len(df) - 1

        for level in self._all_levels:
            # Only check regression-detected levels
            if not level.detected_by_regression:
                continue
            # Skip broken levels
            if level.end_index is not None:
                continue

            if level.is_support:
                # Must touch the level first (low < level)
                if current_bar["low"] < level.level:
                    if current_bar["close"] > level.level:
                        # Retest signal (only with cooldown)
                        if (
                            current_index
                            > level.latest_retest_index + self.settings.retest_cooldown
                        ):
                            self._signals.append(LogisticSignalType.SUPPORT_RETEST)
                    else:
                        # Break signal
                        self._signals.append(LogisticSignalType.SUPPORT_BREAK)
            else:
                # Must touch the level first (high > level)
                if current_bar["high"] > level.level:
                    if current_bar["close"] < level.level:
                        # Retest signal (only with cooldown)
                        if (
                            current_index
                            > level.latest_retest_index + self.settings.retest_cooldown
                        ):
                            self._signals.append(LogisticSignalType.RESISTANCE_RETEST)
                    else:
                        # Break signal
                        self._signals.append(LogisticSignalType.RESISTANCE_BREAK)

    def _filter_levels(self, df: pd.DataFrame) -> None:
        """Filter levels for display based on settings."""
        # Filter by regression prediction
        self._regression_levels = [
            level for level in self._all_levels if level.detected_by_regression
        ]

        # Filter far lines if enabled
        if self.settings.hide_far_lines and len(df) > 0:
            last_close = df["close"].iloc[-1]
            atr = self._atr_values[-1] if self._atr_values else 0

            if atr > 0:
                self._regression_levels = [
                    level
                    for level in self._regression_levels
                    if level.end_index is not None or abs(last_close - level.level) <= atr * 7
                ]

    def add_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add logistic S/R features to DataFrame for ML.

        Adds columns:
        - logistic_nearest_support: Nearest logistic support level
        - logistic_nearest_resistance: Nearest logistic resistance level
        - logistic_support_prob: Probability of nearest support
        - logistic_resistance_prob: Probability of nearest resistance
        - logistic_support_distance_pct: Distance to support
        - logistic_resistance_distance_pct: Distance to resistance

        Args:
            df: DataFrame with OHLC data

        Returns:
            DataFrame with logistic features added
        """
        df = df.copy()

        result = self.calculate(df)

        df["logistic_nearest_support"] = result["nearest_support"]
        df["logistic_nearest_resistance"] = result["nearest_resistance"]
        df["logistic_support_distance_pct"] = result["support_distance_pct"]
        df["logistic_resistance_distance_pct"] = result["resistance_distance_pct"]

        # Get probabilities for nearest levels
        support_levels = result["support_levels"]
        resistance_levels = result["resistance_levels"]

        if result["nearest_support"] and support_levels:
            nearest_support_level = next(
                (level for level in support_levels if level["level"] == result["nearest_support"]),
                None,
            )
            df["logistic_support_prob"] = (
                nearest_support_level["probability"] if nearest_support_level else None
            )
        else:
            df["logistic_support_prob"] = None

        if result["nearest_resistance"] and resistance_levels:
            nearest_resistance_level = next(
                (
                    level
                    for level in resistance_levels
                    if level["level"] == result["nearest_resistance"]
                ),
                None,
            )
            df["logistic_resistance_prob"] = (
                nearest_resistance_level["probability"] if nearest_resistance_level else None
            )
        else:
            df["logistic_resistance_prob"] = None

        return df


def add_logistic_sr_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convenience function to add logistic S/R features.

    Args:
        df: DataFrame with OHLC data

    Returns:
        DataFrame with logistic S/R features added
    """
    indicator = LogisticSRIndicator()
    return indicator.add_features(df)
