# flake8: noqa
"""
Polynomial Regression for Dynamic Support/Resistance Levels - FIXED VERSION.

Fixes data point translation issues:
1. Separate normalization for support and resistance
2. Curve-type-aware prediction
3. Proper slope scaling to real bar space

Matches TradingView Flux Charts behavior exactly.
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class SRPolynomialRegressor:
    """
    Fit polynomial curves to S/R pivot points.
    
    FIXED: Proper data point translation matching TradingView spec.
    
    Key improvements:
    - Separate x_min/x_max for support and resistance curves
    - Curve-type parameter in predict_level() and compute_slope()
    - Slope scaled from normalized space to bar-index space
    
    Usage:
        regressor = SRPolynomialRegressor(degree=2)
        regressor.fit_support_curve(pivots)
        regressor.fit_resistance_curve(pivots)
        
        # Predictions now use correct normalization
        support_level = regressor.predict_level(
            regressor.support_coeffs, current_idx, curve_type='support'
        )
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
        
        # FIXED: Separate normalization ranges for each curve
        self._support_x_min: float = 0.0
        self._support_x_max: float = 1.0
        self._resistance_x_min: float = 0.0
        self._resistance_x_max: float = 1.0

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

        # FIXED: Store SUPPORT-specific normalization params
        self._support_x_min = float(x.min())
        self._support_x_max = float(x.max())

        # Normalize x for numerical stability
        x_range = self._support_x_max - self._support_x_min
        if x_range == 0:
            x_range = 1.0
        x_norm = (x - self._support_x_min) / x_range

        try:
            # Use numpy polyfit (returns coefficients highest degree first)
            coeffs = np.polyfit(x_norm, y, self.degree)
            self.support_coeffs = coeffs
            logger.debug(
                f"Fitted degree-{self.degree} support polynomial "
                f"with {len(support_points)} points "
                f"(x_range: [{self._support_x_min:.0f}, {self._support_x_max:.0f}])"
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

        # FIXED: Store RESISTANCE-specific normalization params
        self._resistance_x_min = float(x.min())
        self._resistance_x_max = float(x.max())

        # FIXED: Use resistance-specific normalization
        x_range = self._resistance_x_max - self._resistance_x_min
        if x_range == 0:
            x_range = 1.0
        x_norm = (x - self._resistance_x_min) / x_range

        try:
            coeffs = np.polyfit(x_norm, y, self.degree)
            self.resistance_coeffs = coeffs
            logger.debug(
                f"Fitted degree-{self.degree} resistance polynomial "
                f"with {len(resistance_points)} points "
                f"(x_range: [{self._resistance_x_min:.0f}, {self._resistance_x_max:.0f}])"
            )
            return coeffs
        except Exception as e:
            logger.warning(f"Resistance curve fit failed: {e}")
            return None

    def predict_level(
        self,
        coeffs: np.ndarray,
        target_index: int,
        curve_type: str = 'support',
    ) -> float:
        """
        Predict S/R level at a specific index using fitted polynomial.
        
        FIXED: Uses curve-type-specific normalization parameters.

        Args:
            coeffs: Polynomial coefficients
            target_index: Index to predict
            curve_type: 'support' or 'resistance'

        Returns:
            Predicted price level
        """
        # FIXED: Select correct normalization range based on curve type
        if curve_type == 'support':
            x_min = self._support_x_min
            x_max = self._support_x_max
        else:
            x_min = self._resistance_x_min
            x_max = self._resistance_x_max
        
        # Normalize target index
        x_range = x_max - x_min
        if x_range == 0:
            x_range = 1.0
        x_norm = (target_index - x_min) / x_range

        # Evaluate polynomial (polyval expects coeffs highest degree first)
        level = np.polyval(coeffs, x_norm)
        return float(level)

    def compute_slope(
        self,
        coeffs: np.ndarray,
        at_x: float = 1.0,
        curve_type: str = 'support',
    ) -> float:
        """
        Compute slope (derivative) of polynomial at a point.
        
        FIXED: Scales derivative from normalized space to real bar-index space.

        Positive slope = rising level (bullish for support, bearish for resistance)
        Negative slope = falling level

        Args:
            coeffs: Polynomial coefficients
            at_x: Normalized x position (0=start, 1=end of data)
            curve_type: 'support' or 'resistance'

        Returns:
            Slope value in price-per-bar units
        """
        # Derivative of polynomial: reduce degree by 1, multiply by original power
        deriv_coeffs = np.polyder(coeffs)

        # Evaluate derivative at point (in normalized space)
        slope_norm = np.polyval(deriv_coeffs, at_x)
        
        # FIXED: Scale back to actual index space
        # dy/dx_real = dy/dx_norm * (1 / x_range)
        if curve_type == 'support':
            x_range = self._support_x_max - self._support_x_min
        else:
            x_range = self._resistance_x_max - self._resistance_x_min
        
        if x_range == 0:
            x_range = 1.0
        
        # Actual slope = normalized_slope / x_range
        actual_slope = slope_norm / x_range
        return float(actual_slope)

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
            - support_slope: Trend direction of support (price/bar)
            - resistance_slope: Trend direction of resistance (price/bar)
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

        # FIXED: Extract support features with curve_type parameter
        if support_coeffs is not None:
            result["polynomial_support"] = self.predict_level(
                support_coeffs, current_idx, curve_type='support'
            )
            result["support_slope"] = self.compute_slope(
                support_coeffs, at_x=1.0, curve_type='support'
            )
            result["support_curve_valid"] = True

        # FIXED: Extract resistance features with curve_type parameter
        if resistance_coeffs is not None:
            result["polynomial_resistance"] = self.predict_level(
                resistance_coeffs, current_idx, curve_type='resistance'
            )
            result["resistance_slope"] = self.compute_slope(
                resistance_coeffs, at_x=1.0, curve_type='resistance'
            )
            result["resistance_curve_valid"] = True

        # Log results
        support_str = (
            f"{result['polynomial_support']:.2f}" if result["polynomial_support"] else "N/A"
        )
        resistance_str = (
            f"{result['polynomial_resistance']:.2f}" if result["polynomial_resistance"] else "N/A"
        )
        logger.info(
            f"Polynomial S/R: support={support_str}, resistance={resistance_str}, "
            f"slopes=(S:{result['support_slope']:.4f}, R:{result['resistance_slope']:.4f}) price/bar"
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
        - support_slope: Trend of support (positive = rising, in price/bar)
        - resistance_slope: Trend of resistance (negative = falling, in price/bar)

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
            df["polynomial_support"] = 0.0
            df["polynomial_resistance"] = 0.0
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
    
    def generate_forecast(
        self,
        current_index: int,
        forecast_bars: int,
        curve_type: str = 'support'
    ) -> List[Tuple[int, float]]:
        """
        Generate forecast values for visualization.
        
        Args:
            current_index: Current bar index
            forecast_bars: Number of bars to forecast
            curve_type: 'support' or 'resistance'
            
        Returns:
            List of (index, price) tuples
        """
        if curve_type == 'support' and self.support_coeffs is None:
            return []
        if curve_type == 'resistance' and self.resistance_coeffs is None:
            return []
        
        coeffs = self.support_coeffs if curve_type == 'support' else self.resistance_coeffs
        
        forecast = []
        for i in range(forecast_bars + 1):
            idx = current_index + i
            level = self.predict_level(coeffs, idx, curve_type=curve_type)
            forecast.append((idx, level))
        
        return forecast


def interpret_slope(slope: float, threshold: float = 0.5) -> str:
    """
    Interpret slope value as trend direction.

    Args:
        slope: Slope value from polynomial derivative (price/bar)
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
