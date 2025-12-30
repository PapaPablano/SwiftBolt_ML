"""
Polynomial Regression Support/Resistance Indicator.

Port of PolynomialRegressionIndicator.swift - fits polynomial curves to pivot points
to identify dynamic/trending support and resistance levels.

Features:
- Linear, quadratic, or cubic polynomial regression
- Separate support and resistance curves
- Forecast capability (project levels into future)
- Slope calculation for trend direction
- Signal detection (tests and breaks)

Usage:
    from src.features.polynomial_sr_indicator import PolynomialSRIndicator

    indicator = PolynomialSRIndicator()
    result = indicator.calculate(df)

    print(result["current_support"])
    print(result["current_resistance"])
    print(result["support_slope"])
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class RegressionType(Enum):
    """Type of polynomial regression."""
    LINEAR = "linear"
    QUADRATIC = "quadratic"
    CUBIC = "cubic"

    @property
    def degree(self) -> int:
        """Get polynomial degree for this type."""
        if self == RegressionType.LINEAR:
            return 1
        elif self == RegressionType.QUADRATIC:
            return 2
        else:
            return 3


class SignalType(Enum):
    """Type of signal detected."""
    RESISTANCE_BREAK = "resistance_break"
    RESISTANCE_TEST = "resistance_test"
    SUPPORT_BREAK = "support_break"
    SUPPORT_TEST = "support_test"


@dataclass
class RegressionCoefficients:
    """Polynomial coefficients with normalization parameters."""
    values: List[float]  # Coefficients, lowest degree first [a0, a1, a2, ...]
    x_min: float = 0.0
    x_max: float = 1.0

    def normalize_x(self, x: float) -> float:
        """Normalize x value to [0, 1] range."""
        x_range = self.x_max - self.x_min
        if x_range <= 0:
            return 0.5
        return (x - self.x_min) / x_range

    def predict(self, x: float) -> float:
        """Predict Y value for given X."""
        x_norm = self.normalize_x(x)
        result = 0.0
        for i, coeff in enumerate(self.values):
            result += coeff * (x_norm ** i)
        return result


@dataclass
class DetectedPivot:
    """A detected pivot point."""
    index: int
    price: float
    timestamp: Optional[pd.Timestamp] = None
    is_high: bool = True


@dataclass
class RegressionSignal:
    """A detected signal from regression analysis."""
    type: SignalType
    price: float
    index: int
    timestamp: Optional[pd.Timestamp] = None


@dataclass
class PolynomialSRSettings:
    """Settings for PolynomialSRIndicator."""
    # Resistance settings
    resistance_enabled: bool = True
    resistance_type: RegressionType = RegressionType.LINEAR
    resistance_pivot_size_l: int = 5  # Bars to the left
    resistance_pivot_size_r: int = 5  # Bars to the right
    resistance_y_offset: float = 0.0

    # Support settings
    support_enabled: bool = True
    support_type: RegressionType = RegressionType.LINEAR
    support_pivot_size_l: int = 5
    support_pivot_size_r: int = 5
    support_y_offset: float = 0.0

    # General settings
    extend_future: int = 20  # Bars to extend into future
    lookback_bars: Optional[int] = 150  # Only use pivots from last N bars
    show_tests: bool = True
    show_breaks: bool = True


class PolynomialRegression:
    """
    Polynomial regression calculator for curve fitting.

    Uses normalized X values for numerical stability.
    """

    @staticmethod
    def fit(
        x_values: List[float],
        y_values: List[float],
        degree: int,
    ) -> Optional[RegressionCoefficients]:
        """
        Fit polynomial regression to data points.

        Args:
            x_values: X coordinates (bar offsets, 0 = current bar, positive = past)
            y_values: Y coordinates (prices)
            degree: Polynomial degree (1=linear, 2=quadratic, 3=cubic)

        Returns:
            Coefficients with normalization parameters, or None if fitting fails
        """
        if len(x_values) != len(y_values) or len(x_values) < 2:
            return None

        if degree + 1 > len(x_values):
            # Not enough points for this degree, fall back to lower
            degree = len(x_values) - 1
            if degree < 1:
                return None

        x = np.array(x_values)
        y = np.array(y_values)

        # Normalize X values to [0, 1] for numerical stability
        x_min = float(x.min())
        x_max = float(x.max())
        x_range = x_max - x_min

        if x_range > 0:
            x_norm = (x - x_min) / x_range
        else:
            x_norm = np.full_like(x, 0.5)

        try:
            # polyfit returns coefficients highest degree first
            # We reverse to get lowest degree first
            coeffs = np.polyfit(x_norm, y, degree)
            coeffs_list = list(reversed(coeffs))

            return RegressionCoefficients(
                values=coeffs_list,
                x_min=x_min,
                x_max=x_max,
            )
        except (np.linalg.LinAlgError, ValueError) as e:
            logger.warning(f"Polynomial fit failed: {e}")
            return None

    @staticmethod
    def compute_slope(coeffs: RegressionCoefficients, at_x: float = 1.0) -> float:
        """
        Compute slope (derivative) of polynomial at a point.

        Positive slope = rising level
        Negative slope = falling level

        Args:
            coeffs: Polynomial coefficients
            at_x: Normalized x position (0=start, 1=end of data)

        Returns:
            Slope value
        """
        # Derivative of polynomial: reduce degree by 1, multiply by original power
        # For coeffs [a0, a1, a2, a3], derivative is [a1, 2*a2, 3*a3]
        if len(coeffs.values) < 2:
            return 0.0

        deriv_coeffs = []
        for i in range(1, len(coeffs.values)):
            deriv_coeffs.append(i * coeffs.values[i])

        # Evaluate derivative at point
        slope = 0.0
        for i, coeff in enumerate(deriv_coeffs):
            slope += coeff * (at_x ** i)

        return float(slope)


class PolynomialSRIndicator:
    """
    Polynomial regression-based support and resistance indicator.

    Fits polynomial curves to pivot points to identify dynamic S/R levels
    that capture trending support and resistance.
    """

    def __init__(self, settings: Optional[PolynomialSRSettings] = None):
        """
        Initialize the indicator.

        Args:
            settings: Configuration settings (uses defaults if not provided)
        """
        self.settings = settings or PolynomialSRSettings()
        self._support_coeffs: Optional[RegressionCoefficients] = None
        self._resistance_coeffs: Optional[RegressionCoefficients] = None
        self._support_pivots: List[DetectedPivot] = []
        self._resistance_pivots: List[DetectedPivot] = []
        self._signals: List[RegressionSignal] = []

    def calculate(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate polynomial regression S/R for given bars.

        Args:
            df: DataFrame with 'high', 'low', 'close' columns

        Returns:
            Dict with:
            - current_support: Support level at current bar
            - current_resistance: Resistance level at current bar
            - support_slope: Trend direction of support
            - resistance_slope: Trend direction of resistance
            - forecast_support: List of forecast support values
            - forecast_resistance: List of forecast resistance values
            - signals: List of detected signals
            - support_pivots: Pivots used for support regression
            - resistance_pivots: Pivots used for resistance regression
        """
        # Reset state
        self._support_coeffs = None
        self._resistance_coeffs = None
        self._support_pivots = []
        self._resistance_pivots = []
        self._signals = []

        if df.empty:
            return self._empty_result()

        last_index = len(df) - 1
        has_ts = "ts" in df.columns

        # Detect pivots
        if self.settings.resistance_enabled:
            self._resistance_pivots = self._detect_pivots(
                df,
                self.settings.resistance_pivot_size_l,
                self.settings.resistance_pivot_size_r,
                is_high=True,
            )

        if self.settings.support_enabled:
            self._support_pivots = self._detect_pivots(
                df,
                self.settings.support_pivot_size_l,
                self.settings.support_pivot_size_r,
                is_high=False,
            )

        # Filter by lookback window
        if self.settings.lookback_bars:
            min_index = max(0, last_index - self.settings.lookback_bars)
            self._resistance_pivots = [
                p for p in self._resistance_pivots if p.index >= min_index
            ]
            self._support_pivots = [
                p for p in self._support_pivots if p.index >= min_index
            ]

        # Calculate regressions
        current_resistance = None
        resistance_slope = 0.0
        if self._resistance_pivots:
            self._resistance_coeffs = self._fit_regression(
                self._resistance_pivots,
                last_index,
                self.settings.resistance_type,
                self.settings.resistance_y_offset,
            )
            if self._resistance_coeffs:
                current_resistance = self._resistance_coeffs.predict(0)
                resistance_slope = PolynomialRegression.compute_slope(
                    self._resistance_coeffs, at_x=1.0
                )

        current_support = None
        support_slope = 0.0
        if self._support_pivots:
            self._support_coeffs = self._fit_regression(
                self._support_pivots,
                last_index,
                self.settings.support_type,
                self.settings.support_y_offset,
            )
            if self._support_coeffs:
                current_support = self._support_coeffs.predict(0)
                support_slope = PolynomialRegression.compute_slope(
                    self._support_coeffs, at_x=1.0
                )

        # Generate forecasts
        forecast_resistance = self._generate_forecasts(
            self._resistance_coeffs, self.settings.extend_future
        )
        forecast_support = self._generate_forecasts(
            self._support_coeffs, self.settings.extend_future
        )

        # Detect signals
        if self.settings.show_tests or self.settings.show_breaks:
            self._detect_signals(df)

        # Calculate distances
        current_price = df["close"].iloc[-1]
        support_distance_pct = None
        resistance_distance_pct = None

        if current_support and current_support < current_price:
            support_distance_pct = (current_price - current_support) / current_price * 100

        if current_resistance and current_resistance > current_price:
            resistance_distance_pct = (current_resistance - current_price) / current_price * 100

        logger.info(
            f"PolynomialSR: support={current_support}, resistance={current_resistance}, "
            f"slopes=(S:{support_slope:.4f}, R:{resistance_slope:.4f}), "
            f"pivots=(S:{len(self._support_pivots)}, R:{len(self._resistance_pivots)})"
        )

        return {
            "current_support": current_support,
            "current_resistance": current_resistance,
            "support_slope": support_slope,
            "resistance_slope": resistance_slope,
            "support_distance_pct": round(support_distance_pct, 2) if support_distance_pct else None,
            "resistance_distance_pct": round(resistance_distance_pct, 2) if resistance_distance_pct else None,
            "forecast_support": forecast_support,
            "forecast_resistance": forecast_resistance,
            "signals": [
                {"type": s.type.value, "price": s.price, "index": s.index}
                for s in self._signals
            ],
            "support_pivots": [
                {"index": p.index, "price": p.price} for p in self._support_pivots
            ],
            "resistance_pivots": [
                {"index": p.index, "price": p.price} for p in self._resistance_pivots
            ],
            "current_price": float(current_price),
        }

    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure."""
        return {
            "current_support": None,
            "current_resistance": None,
            "support_slope": 0.0,
            "resistance_slope": 0.0,
            "support_distance_pct": None,
            "resistance_distance_pct": None,
            "forecast_support": [],
            "forecast_resistance": [],
            "signals": [],
            "support_pivots": [],
            "resistance_pivots": [],
            "current_price": None,
        }

    def _detect_pivots(
        self,
        df: pd.DataFrame,
        left_size: int,
        right_size: int,
        is_high: bool,
    ) -> List[DetectedPivot]:
        """Detect pivots with separate left and right lookback periods."""
        pivots = []
        n = len(df)

        if n <= left_size + right_size:
            return []

        highs = df["high"].values
        lows = df["low"].values
        has_ts = "ts" in df.columns

        for i in range(left_size, n - right_size):
            if is_high:
                bar_val = highs[i]
                # Check left side
                is_pivot = True
                for j in range(i - left_size, i):
                    if highs[j] > bar_val:
                        is_pivot = False
                        break
                # Check right side
                if is_pivot:
                    for j in range(i + 1, i + right_size + 1):
                        if highs[j] > bar_val:
                            is_pivot = False
                            break
            else:
                bar_val = lows[i]
                # Check left side
                is_pivot = True
                for j in range(i - left_size, i):
                    if lows[j] < bar_val:
                        is_pivot = False
                        break
                # Check right side
                if is_pivot:
                    for j in range(i + 1, i + right_size + 1):
                        if lows[j] < bar_val:
                            is_pivot = False
                            break

            if is_pivot:
                ts = df["ts"].iloc[i] if has_ts else None
                pivots.append(DetectedPivot(
                    index=i,
                    price=float(bar_val),
                    timestamp=ts,
                    is_high=is_high,
                ))

        return pivots

    def _fit_regression(
        self,
        pivots: List[DetectedPivot],
        last_index: int,
        reg_type: RegressionType,
        y_offset: float,
    ) -> Optional[RegressionCoefficients]:
        """Fit polynomial regression to pivots."""
        if not pivots:
            return None

        # X convention: 0 = current bar, positive = past
        x_values = [float(last_index - p.index) for p in pivots]
        y_values = [p.price for p in pivots]

        coeffs = PolynomialRegression.fit(x_values, y_values, reg_type.degree)

        if coeffs and y_offset != 0:
            # Apply Y offset to constant term
            coeffs.values[0] += y_offset

        return coeffs

    def _generate_forecasts(
        self,
        coeffs: Optional[RegressionCoefficients],
        n_bars: int,
    ) -> List[float]:
        """Generate forecast values for N bars into the future."""
        if not coeffs:
            return []

        # Future = negative x values (0 = current, negative = future)
        forecasts = []
        for i in range(1, n_bars + 1):
            val = coeffs.predict(-i)
            forecasts.append(round(val, 4))

        return forecasts

    def _detect_signals(self, df: pd.DataFrame) -> None:
        """Detect test and break signals on the last bar."""
        if len(df) < 2:
            return

        last_bar = df.iloc[-1]
        prev_bar = df.iloc[-2]
        last_index = len(df) - 1
        has_ts = "ts" in df.columns

        # Check resistance signals
        if self._resistance_coeffs and self.settings.resistance_enabled:
            current_res = self._resistance_coeffs.predict(0)
            prev_res = self._resistance_coeffs.predict(1)

            # Test: high touched resistance from below
            if last_bar["high"] >= current_res and prev_bar["high"] < prev_res:
                if self.settings.show_tests:
                    self._signals.append(RegressionSignal(
                        type=SignalType.RESISTANCE_TEST,
                        price=float(last_bar["high"]),
                        index=last_index,
                        timestamp=last_bar["ts"] if has_ts else None,
                    ))

            # Break: close crossed above resistance
            if last_bar["close"] > current_res and prev_bar["close"] <= prev_res:
                if self.settings.show_breaks:
                    self._signals.append(RegressionSignal(
                        type=SignalType.RESISTANCE_BREAK,
                        price=float(last_bar["close"]),
                        index=last_index,
                        timestamp=last_bar["ts"] if has_ts else None,
                    ))

        # Check support signals
        if self._support_coeffs and self.settings.support_enabled:
            current_sup = self._support_coeffs.predict(0)
            prev_sup = self._support_coeffs.predict(1)

            # Test: low touched support from above
            if last_bar["low"] <= current_sup and prev_bar["low"] > prev_sup:
                if self.settings.show_tests:
                    self._signals.append(RegressionSignal(
                        type=SignalType.SUPPORT_TEST,
                        price=float(last_bar["low"]),
                        index=last_index,
                        timestamp=last_bar["ts"] if has_ts else None,
                    ))

            # Break: close crossed below support
            if last_bar["close"] < current_sup and prev_bar["close"] >= prev_sup:
                if self.settings.show_breaks:
                    self._signals.append(RegressionSignal(
                        type=SignalType.SUPPORT_BREAK,
                        price=float(last_bar["close"]),
                        index=last_index,
                        timestamp=last_bar["ts"] if has_ts else None,
                    ))

    def forecast_resistance(self, bars_ahead: int) -> Optional[float]:
        """Get forecasted resistance at N bars into the future."""
        if not self._resistance_coeffs:
            return None
        return self._resistance_coeffs.predict(-bars_ahead)

    def forecast_support(self, bars_ahead: int) -> Optional[float]:
        """Get forecasted support at N bars into the future."""
        if not self._support_coeffs:
            return None
        return self._support_coeffs.predict(-bars_ahead)

    def add_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add polynomial S/R features to DataFrame for ML.

        Adds columns:
        - poly_support: Current polynomial support level
        - poly_resistance: Current polynomial resistance level
        - poly_support_slope: Trend of support (positive = rising)
        - poly_resistance_slope: Trend of resistance
        - poly_support_distance_pct: Distance to support
        - poly_resistance_distance_pct: Distance to resistance

        Args:
            df: DataFrame with OHLC data

        Returns:
            DataFrame with polynomial features added
        """
        df = df.copy()

        result = self.calculate(df)

        df["poly_support"] = result["current_support"]
        df["poly_resistance"] = result["current_resistance"]
        df["poly_support_slope"] = result["support_slope"]
        df["poly_resistance_slope"] = result["resistance_slope"]
        df["poly_support_distance_pct"] = result["support_distance_pct"]
        df["poly_resistance_distance_pct"] = result["resistance_distance_pct"]

        return df


def interpret_slope(slope: float, threshold: float = 0.5) -> str:
    """
    Interpret slope value as trend direction.

    Args:
        slope: Slope value from polynomial derivative
        threshold: Minimum absolute value for significant trend

    Returns:
        Trend label: "rising", "falling", or "flat"
    """
    if slope > threshold:
        return "rising"
    elif slope < -threshold:
        return "falling"
    else:
        return "flat"


def add_polynomial_sr_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convenience function to add polynomial S/R features.

    Args:
        df: DataFrame with OHLC data

    Returns:
        DataFrame with polynomial S/R features added
    """
    indicator = PolynomialSRIndicator()
    return indicator.add_features(df)
