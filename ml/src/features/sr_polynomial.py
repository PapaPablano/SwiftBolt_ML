"""
Polynomial Regression for Dynamic Support/Resistance Levels.

Fits polynomial curves to historical pivot points to identify:
- Rising/falling support trendlines
- Rising/falling resistance trendlines
- Current interpolated S/R levels
- Trend direction (slope) for momentum detection

Phase 3 of the Advanced S/R Integration Strategy.
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class SRPolynomialRegressor:
    """
    Fit polynomial curves to S/R pivot points.

    Captures dynamic/trending support and resistance that static
    horizontal lines miss. Useful for identifying:
    - Rising support in uptrends
    - Falling resistance in downtrends
    - Trend exhaustion (flattening curves)

    Usage:
        regressor = SRPolynomialRegressor(degree=2)
        features = regressor.fit_and_extract(df, zigzag_swings)
        df = regressor.add_polynomial_features(df, sr_levels)
    """

    def __init__(
        self,
        degree: int = 2,
        min_points: int = 4,
    ):
        """
        Initialize the polynomial regressor.

        Args:
            degree: Polynomial degree (1=linear, 2=quadratic, 3=cubic)
            min_points: Minimum pivot points required for fitting
        """
        self.degree = degree
        self.min_points = min_points
        self.support_coeffs: Optional[np.ndarray] = None
        self.resistance_coeffs: Optional[np.ndarray] = None
        self._x_min: float = 0
        self._x_max: float = 1

    def fit_support_curve(
        self,
        pivot_points: List[Dict[str, Any]],
    ) -> Optional[np.ndarray]:
        """
        Fit polynomial to support pivot points (lows).

        Args:
            pivot_points: List of {"index": int, "price": float, "type": str}

        Returns:
            Polynomial coefficients or None if insufficient data
        """
        support_points = [p for p in pivot_points if p.get("type") == "low"]

        if len(support_points) < self.min_points:
            logger.debug(
                f"Insufficient support points for polynomial: "
                f"{len(support_points)} (need {self.min_points})"
            )
            return None

        x = np.array([p["index"] for p in support_points])
        y = np.array([p["price"] for p in support_points])

        # Store normalization params
        self._x_min = float(x.min())
        self._x_max = float(x.max())

        # Normalize x for numerical stability
        x_range = self._x_max - self._x_min
        if x_range == 0:
            x_range = 1
        x_norm = (x - self._x_min) / x_range

        try:
            # Use numpy polyfit (returns coefficients highest degree first)
            coeffs = np.polyfit(x_norm, y, self.degree)
            self.support_coeffs = coeffs
            logger.debug(
                f"Fitted degree-{self.degree} support polynomial "
                f"with {len(support_points)} points"
            )
            return coeffs
        except Exception as e:
            logger.warning(f"Support curve fit failed: {e}")
            return None

    def fit_resistance_curve(
        self,
        pivot_points: List[Dict[str, Any]],
    ) -> Optional[np.ndarray]:
        """
        Fit polynomial to resistance pivot points (highs).

        Args:
            pivot_points: List of {"index": int, "price": float, "type": str}

        Returns:
            Polynomial coefficients or None if insufficient data
        """
        resistance_points = [p for p in pivot_points if p.get("type") == "high"]

        if len(resistance_points) < self.min_points:
            logger.debug(
                f"Insufficient resistance points for polynomial: "
                f"{len(resistance_points)} (need {self.min_points})"
            )
            return None

        x = np.array([p["index"] for p in resistance_points])
        y = np.array([p["price"] for p in resistance_points])

        # Normalize x
        x_range = self._x_max - self._x_min
        if x_range == 0:
            x_range = 1
        x_norm = (x - self._x_min) / x_range

        try:
            coeffs = np.polyfit(x_norm, y, self.degree)
            self.resistance_coeffs = coeffs
            logger.debug(
                f"Fitted degree-{self.degree} resistance polynomial "
                f"with {len(resistance_points)} points"
            )
            return coeffs
        except Exception as e:
            logger.warning(f"Resistance curve fit failed: {e}")
            return None

    def predict_level(
        self,
        coeffs: np.ndarray,
        target_index: int,
    ) -> float:
        """
        Predict S/R level at a specific index using fitted polynomial.

        Args:
            coeffs: Polynomial coefficients
            target_index: Index to predict

        Returns:
            Predicted price level
        """
        # Normalize target index
        x_range = self._x_max - self._x_min
        if x_range == 0:
            x_range = 1
        x_norm = (target_index - self._x_min) / x_range

        # Evaluate polynomial (polyval expects coeffs highest degree first)
        level = np.polyval(coeffs, x_norm)
        return float(level)

    def compute_slope(
        self,
        coeffs: np.ndarray,
        at_x: float = 1.0,
    ) -> float:
        """
        Compute slope (derivative) of polynomial at a point.

        Positive slope = rising level (bullish for support, bearish for resistance)
        Negative slope = falling level

        Args:
            coeffs: Polynomial coefficients
            at_x: Normalized x position (0=start, 1=end of data)

        Returns:
            Slope value
        """
        # Derivative of polynomial: reduce degree by 1, multiply by original power
        deriv_coeffs = np.polyder(coeffs)

        # Evaluate derivative at point
        slope = np.polyval(deriv_coeffs, at_x)
        return float(slope)

    def fit_and_extract(
        self,
        df: pd.DataFrame,
        zigzag_swings: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Fit polynomial curves and extract all features.

        Args:
            df: OHLC DataFrame
            zigzag_swings: List of swing points from SupportResistanceDetector

        Returns:
            Dict with polynomial S/R features:
            - polynomial_support: Interpolated support at current bar
            - polynomial_resistance: Interpolated resistance at current bar
            - support_slope: Trend direction of support
            - resistance_slope: Trend direction of resistance
            - support_curve_valid: Whether support curve was fitted
            - resistance_curve_valid: Whether resistance curve was fitted
        """
        current_idx = len(df) - 1

        result = {
            "polynomial_support": None,
            "polynomial_resistance": None,
            "support_slope": 0.0,
            "resistance_slope": 0.0,
            "support_curve_valid": False,
            "resistance_curve_valid": False,
        }

        if not zigzag_swings:
            return result

        # Fit curves
        support_coeffs = self.fit_support_curve(zigzag_swings)
        resistance_coeffs = self.fit_resistance_curve(zigzag_swings)

        # Extract support features
        if support_coeffs is not None:
            result["polynomial_support"] = self.predict_level(
                support_coeffs, current_idx
            )
            result["support_slope"] = self.compute_slope(support_coeffs, at_x=1.0)
            result["support_curve_valid"] = True

        # Extract resistance features
        if resistance_coeffs is not None:
            result["polynomial_resistance"] = self.predict_level(
                resistance_coeffs, current_idx
            )
            result["resistance_slope"] = self.compute_slope(resistance_coeffs, at_x=1.0)
            result["resistance_curve_valid"] = True

        # Log results
        support_str = (
            f"{result['polynomial_support']:.2f}"
            if result['polynomial_support'] else "N/A"
        )
        resistance_str = (
            f"{result['polynomial_resistance']:.2f}"
            if result['polynomial_resistance'] else "N/A"
        )
        logger.info(
            f"Polynomial S/R: support={support_str}, resistance={resistance_str}, "
            f"slopes=(S:{result['support_slope']:.4f}, R:{result['resistance_slope']:.4f})"
        )

        return result

    def add_polynomial_features(
        self,
        df: pd.DataFrame,
        sr_levels: Dict[str, Any],
    ) -> pd.DataFrame:
        """
        Add polynomial S/R features to DataFrame.

        Adds columns:
        - polynomial_support: Dynamic support level at current bar
        - polynomial_resistance: Dynamic resistance level at current bar
        - support_slope: Trend of support (positive = rising)
        - resistance_slope: Trend of resistance (negative = falling)

        Args:
            df: OHLC DataFrame
            sr_levels: S/R levels from detector (includes zigzag swings)

        Returns:
            DataFrame with polynomial features added
        """
        df = df.copy()

        # Get zigzag swings
        methods = sr_levels.get("methods", {})
        zigzag_data = methods.get("zigzag", {})
        swings = zigzag_data.get("swings", [])

        if not swings:
            # Set defaults if no swings available
            df["polynomial_support"] = np.nan
            df["polynomial_resistance"] = np.nan
            df["support_slope"] = 0.0
            df["resistance_slope"] = 0.0
            return df

        # Fit and extract features
        poly_features = self.fit_and_extract(df, swings)

        # Add features (broadcast to all rows)
        df["polynomial_support"] = poly_features["polynomial_support"]
        df["polynomial_resistance"] = poly_features["polynomial_resistance"]
        df["support_slope"] = poly_features["support_slope"]
        df["resistance_slope"] = poly_features["resistance_slope"]

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
    from src.features.support_resistance_detector import SupportResistanceDetector

    detector = SupportResistanceDetector()
    sr_levels = detector.find_all_levels(df)

    regressor = SRPolynomialRegressor(degree=2, min_points=4)
    return regressor.add_polynomial_features(df, sr_levels)
