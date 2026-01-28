"""
Test suite for polynomial regression fixes.

Verifies:
1. Separate normalization ranges for support and resistance
2. Curve-type-aware prediction using correct coordinate systems
3. Slope calculation properly scaled to bar-index space
4. Data-point translation matches TradingView design
"""

import numpy as np
import pytest
from src.features.sr_polynomial import SRPolynomialRegressor


class TestSeparateNormalization:
    """Test that support and resistance have independent normalization."""

    def test_support_normalization_stored(self):
        """Support fit should store _support_x_min and _support_x_max."""
        regressor = SRPolynomialRegressor(degree=2, min_points=3)

        # Create support pivots at different indices
        support_pivots = [
            {"index": 0, "price": 100.0, "type": "low"},
            {"index": 50, "price": 102.0, "type": "low"},
            {"index": 100, "price": 101.0, "type": "low"},
        ]

        regressor.fit_support_curve(support_pivots)

        assert regressor._support_x_min == 0.0
        assert regressor._support_x_max == 100.0
        assert regressor.support_coeffs is not None

    def test_resistance_normalization_stored(self):
        """Resistance fit should store _resistance_x_min and _resistance_x_max."""
        regressor = SRPolynomialRegressor(degree=2, min_points=3)

        # Create resistance pivots at different indices
        resistance_pivots = [
            {"index": 10, "price": 110.0, "type": "high"},
            {"index": 60, "price": 112.0, "type": "high"},
            {"index": 90, "price": 111.0, "type": "high"},
        ]

        regressor.fit_resistance_curve(resistance_pivots)

        assert regressor._resistance_x_min == 10.0
        assert regressor._resistance_x_max == 90.0
        assert regressor.resistance_coeffs is not None

    def test_support_and_resistance_independent(self):
        """Support and resistance should have independent x ranges."""
        regressor = SRPolynomialRegressor(degree=2, min_points=3)

        # Support pivots span 0-100
        support_pivots = [
            {"index": 0, "price": 100.0, "type": "low"},
            {"index": 50, "price": 102.0, "type": "low"},
            {"index": 100, "price": 101.0, "type": "low"},
        ]

        # Resistance pivots span 20-80
        resistance_pivots = [
            {"index": 20, "price": 110.0, "type": "high"},
            {"index": 50, "price": 112.0, "type": "high"},
            {"index": 80, "price": 111.0, "type": "high"},
        ]

        regressor.fit_support_curve(support_pivots)
        regressor.fit_resistance_curve(resistance_pivots)

        # Support range should be 100
        support_range = regressor._support_x_max - regressor._support_x_min
        assert support_range == 100.0

        # Resistance range should be 60
        resistance_range = regressor._resistance_x_max - regressor._resistance_x_min
        assert resistance_range == 60.0

        # Ranges are different
        assert support_range != resistance_range


class TestCurveTypeAwarePrediction:
    """Test that predictions use the correct coordinate system for each curve."""

    def test_predict_support_uses_support_normalization(self):
        """Prediction for support should use _support_x_min/max."""
        regressor = SRPolynomialRegressor(degree=1, min_points=2)

        # Linear support: y = 100 + 0.1*x
        support_pivots = [
            {"index": 0, "price": 100.0, "type": "low"},
            {"index": 100, "price": 110.0, "type": "low"},
        ]

        regressor.fit_support_curve(support_pivots)

        # Predict at index 50 (middle of support range)
        pred = regressor.predict_level(regressor.support_coeffs, 50, curve_type="support")

        # Should be approximately 105 (linear interpolation)
        assert 104.5 < pred < 105.5

    def test_predict_resistance_uses_resistance_normalization(self):
        """Prediction for resistance should use _resistance_x_min/max."""
        regressor = SRPolynomialRegressor(degree=1, min_points=2)

        # Linear resistance: y = 110 + 0.1*x
        resistance_pivots = [
            {"index": 0, "price": 110.0, "type": "high"},
            {"index": 100, "price": 120.0, "type": "high"},
        ]

        regressor.fit_resistance_curve(resistance_pivots)

        # Predict at index 50 (middle of resistance range)
        pred = regressor.predict_level(regressor.resistance_coeffs, 50, curve_type="resistance")

        # Should be approximately 115 (linear interpolation)
        assert 114.5 < pred < 115.5

    def test_different_ranges_different_predictions(self):
        """
        When support and resistance have different index ranges,
        predictions should reflect their different normalization.
        """
        regressor = SRPolynomialRegressor(degree=1, min_points=2)

        # Support: indices 0-100, prices 100-110
        support_pivots = [
            {"index": 0, "price": 100.0, "type": "low"},
            {"index": 100, "price": 110.0, "type": "low"},
        ]

        # Resistance: indices 0-50, prices 120-130 (steeper in price space)
        resistance_pivots = [
            {"index": 0, "price": 120.0, "type": "high"},
            {"index": 50, "price": 130.0, "type": "high"},
        ]

        regressor.fit_support_curve(support_pivots)
        regressor.fit_resistance_curve(resistance_pivots)

        # At index 25:
        # Support: 25/100 = 0.25 through range, so 100 + 0.25*10 = 102.5
        sup_pred = regressor.predict_level(regressor.support_coeffs, 25, curve_type="support")

        # Resistance: 25/50 = 0.5 through range, so 120 + 0.5*10 = 125
        res_pred = regressor.predict_level(regressor.resistance_coeffs, 25, curve_type="resistance")

        assert 102.0 < sup_pred < 103.0
        assert 124.5 < res_pred < 125.5


class TestSlopeScaling:
    """Test that slopes are properly scaled from normalized to bar-index space."""

    def test_slope_scaling_support(self):
        """Support slope should be scaled by 1/support_x_range."""
        regressor = SRPolynomialRegressor(degree=1, min_points=2)

        # Linear support: indices 0-100, prices 100-110
        # True slope per bar: (110-100)/(100-0) = 0.1
        support_pivots = [
            {"index": 0, "price": 100.0, "type": "low"},
            {"index": 100, "price": 110.0, "type": "low"},
        ]

        regressor.fit_support_curve(support_pivots)
        slope = regressor.compute_slope(regressor.support_coeffs, at_x=1.0, curve_type="support")

        # Should be 0.1 (price per bar)
        assert 0.09 < slope < 0.11

    def test_slope_scaling_resistance(self):
        """Resistance slope should be scaled by 1/resistance_x_range."""
        regressor = SRPolynomialRegressor(degree=1, min_points=2)

        # Linear resistance: indices 0-50, prices 120-130
        # True slope per bar: (130-120)/(50-0) = 0.2
        resistance_pivots = [
            {"index": 0, "price": 120.0, "type": "high"},
            {"index": 50, "price": 130.0, "type": "high"},
        ]

        regressor.fit_resistance_curve(resistance_pivots)
        slope = regressor.compute_slope(regressor.resistance_coeffs, at_x=1.0, curve_type="resistance")

        # Should be 0.2 (price per bar)
        assert 0.19 < slope < 0.21

    def test_slope_magnitude_matches_real_slope(self):
        """
        Slope should represent the actual per-bar change,
        not the normalized space change.
        """
        regressor = SRPolynomialRegressor(degree=1, min_points=2)

        # Create two identical lines with different index ranges
        # Both go from 100 to 105 in price

        # Support: 0-10 indices
        support_pivots = [
            {"index": 0, "price": 100.0, "type": "low"},
            {"index": 10, "price": 105.0, "type": "low"},
        ]

        # Resistance: 0-100 indices
        resistance_pivots = [
            {"index": 0, "price": 100.0, "type": "high"},
            {"index": 100, "price": 105.0, "type": "high"},
        ]

        regressor.fit_support_curve(support_pivots)
        regressor.fit_resistance_curve(resistance_pivots)

        support_slope = regressor.compute_slope(regressor.support_coeffs, at_x=1.0, curve_type="support")
        resistance_slope = regressor.compute_slope(regressor.resistance_coeffs, at_x=1.0, curve_type="resistance")

        # Both slopes should be 0.5 (5 price units / 10 bars)
        # NOT different values due to normalization
        assert 0.49 < support_slope < 0.51
        assert 0.049 < resistance_slope < 0.051


class TestDataPointTranslation:
    """Test that data-point translation matches TradingView design."""

    def test_trivial_line_translation(self):
        """A horizontal line should predict the same price everywhere."""
        regressor = SRPolynomialRegressor(degree=1, min_points=2)

        support_pivots = [
            {"index": 0, "price": 100.0, "type": "low"},
            {"index": 100, "price": 100.0, "type": "low"},
        ]

        regressor.fit_support_curve(support_pivots)

        # Predict at various indices
        pred_0 = regressor.predict_level(regressor.support_coeffs, 0, curve_type="support")
        pred_50 = regressor.predict_level(regressor.support_coeffs, 50, curve_type="support")
        pred_100 = regressor.predict_level(regressor.support_coeffs, 100, curve_type="support")

        # All should be ~100
        assert 99.9 < pred_0 < 100.1
        assert 99.9 < pred_50 < 100.1
        assert 99.9 < pred_100 < 100.1

    def test_end_point_extrapolation(self):
        """Prediction at the endpoints should match the fitted points."""
        regressor = SRPolynomialRegressor(degree=1, min_points=2)

        support_pivots = [
            {"index": 10, "price": 100.0, "type": "low"},
            {"index": 90, "price": 110.0, "type": "low"},
        ]

        regressor.fit_support_curve(support_pivots)

        # Predict at endpoints
        pred_10 = regressor.predict_level(regressor.support_coeffs, 10, curve_type="support")
        pred_90 = regressor.predict_level(regressor.support_coeffs, 90, curve_type="support")

        # Should match original values
        assert 99.5 < pred_10 < 100.5
        assert 109.5 < pred_90 < 110.5

    def test_fit_and_extract_consistency(self):
        """fit_and_extract should produce consistent results with direct calls."""
        regressor = SRPolynomialRegressor(degree=2, min_points=3)

        pivots = [
            {"index": 0, "price": 100.0, "type": "low"},
            {"index": 50, "price": 102.0, "type": "low"},
            {"index": 100, "price": 101.0, "type": "low"},
            {"index": 10, "price": 110.0, "type": "high"},
            {"index": 60, "price": 112.0, "type": "high"},
            {"index": 90, "price": 111.0, "type": "high"},
        ]

        # Create minimal DataFrame
        import pandas as pd
        df = pd.DataFrame({
            'open': [100] * 101,
            'high': [110] * 101,
            'low': [100] * 101,
            'close': [105] * 101,
        })

        result = regressor.fit_and_extract(df, pivots)

        # Check that we got results
        assert result["polynomial_support"] is not None
        assert result["polynomial_resistance"] is not None
        assert result["support_slope"] != 0
        assert result["resistance_slope"] != 0
        assert result["support_curve_valid"]
        assert result["resistance_curve_valid"]


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_insufficient_support_points(self):
        """Should return None if not enough support points."""
        regressor = SRPolynomialRegressor(degree=2, min_points=4)

        support_pivots = [
            {"index": 0, "price": 100.0, "type": "low"},
            {"index": 50, "price": 102.0, "type": "low"},
        ]

        result = regressor.fit_support_curve(support_pivots)
        assert result is None

    def test_insufficient_resistance_points(self):
        """Should return None if not enough resistance points."""
        regressor = SRPolynomialRegressor(degree=2, min_points=4)

        resistance_pivots = [
            {"index": 0, "price": 110.0, "type": "high"},
            {"index": 50, "price": 112.0, "type": "high"},
        ]

        result = regressor.fit_resistance_curve(resistance_pivots)
        assert result is None

    def test_zero_x_range_normalization(self):
        """Should handle zero x_range gracefully by returning None."""
        regressor = SRPolynomialRegressor(degree=1, min_points=2)

        # Both pivots at same index means zero x_range
        # After normalization, all x values become 0.5 (or any constant)
        # This makes polynomial fitting impossible (singular matrix)
        support_pivots = [
            {"index": 50, "price": 100.0, "type": "low"},
            {"index": 50, "price": 102.0, "type": "low"},  # Same index, different price
        ]

        # This correctly returns None since polyfit fails with constant x
        result = regressor.fit_support_curve(support_pivots)
        assert result is None

    def test_fit_and_extract_no_pivots(self):
        """Should handle empty pivot list gracefully."""
        regressor = SRPolynomialRegressor(degree=2, min_points=3)

        import pandas as pd
        df = pd.DataFrame({
            'open': [100] * 101,
            'high': [110] * 101,
            'low': [100] * 101,
            'close': [105] * 101,
        })

        result = regressor.fit_and_extract(df, [])

        # Should return a valid result structure with no valid curves
        assert result["polynomial_support"] is None
        assert result["polynomial_resistance"] is None
        assert not result["support_curve_valid"]
        assert not result["resistance_curve_valid"]


class TestSlopeSignInterpretation:
    """Test that slope signs are correct for trend interpretation."""

    def test_rising_support_positive_slope(self):
        """Rising support should have positive slope."""
        regressor = SRPolynomialRegressor(degree=1, min_points=2)

        # Prices increase: 100 -> 110
        support_pivots = [
            {"index": 0, "price": 100.0, "type": "low"},
            {"index": 100, "price": 110.0, "type": "low"},
        ]

        regressor.fit_support_curve(support_pivots)
        slope = regressor.compute_slope(regressor.support_coeffs, at_x=1.0, curve_type="support")

        assert slope > 0

    def test_falling_resistance_negative_slope(self):
        """Falling resistance should have negative slope."""
        regressor = SRPolynomialRegressor(degree=1, min_points=2)

        # Prices decrease: 120 -> 110
        resistance_pivots = [
            {"index": 0, "price": 120.0, "type": "high"},
            {"index": 100, "price": 110.0, "type": "high"},
        ]

        regressor.fit_resistance_curve(resistance_pivots)
        slope = regressor.compute_slope(regressor.resistance_coeffs, at_x=1.0, curve_type="resistance")

        assert slope < 0

    def test_flat_line_zero_slope(self):
        """Flat line should have near-zero slope."""
        regressor = SRPolynomialRegressor(degree=1, min_points=2)

        # Constant price
        support_pivots = [
            {"index": 0, "price": 100.0, "type": "low"},
            {"index": 100, "price": 100.0, "type": "low"},
        ]

        regressor.fit_support_curve(support_pivots)
        slope = regressor.compute_slope(regressor.support_coeffs, at_x=1.0, curve_type="support")

        assert abs(slope) < 0.001


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
