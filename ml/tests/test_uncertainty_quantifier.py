"""Unit tests for Uncertainty Quantifier."""

import numpy as np
import pytest

from src.models.uncertainty_quantifier import (
    UncertaintyQuantifier,
    DirectionalUncertaintyQuantifier,
    ModelForecast,
)


@pytest.fixture
def sample_forecasts():
    """Create sample model forecasts."""
    return [
        ModelForecast(
            model_name="rf",
            forecast_value=0.015,
            forecast_volatility=0.02,
            confidence_interval_lower=-0.025,
            confidence_interval_upper=0.055,
        ),
        ModelForecast(
            model_name="gb",
            forecast_value=0.012,
            forecast_volatility=0.018,
            confidence_interval_lower=-0.022,
            confidence_interval_upper=0.046,
        ),
        ModelForecast(
            model_name="arima",
            forecast_value=0.010,
            forecast_volatility=0.025,
            confidence_interval_lower=-0.040,
            confidence_interval_upper=0.060,
        ),
    ]


@pytest.fixture
def equal_weights():
    """Equal weights for 3 models."""
    return {"rf": 1/3, "gb": 1/3, "arima": 1/3}


@pytest.fixture
def sample_predictions():
    """Sample predictions dict for directional testing."""
    return {
        "rf": {
            "label": "Bullish",
            "confidence": 0.7,
            "probabilities": {"bullish": 0.7, "neutral": 0.2, "bearish": 0.1},
            "forecast_return": 0.02,
            "forecast_volatility": 0.015,
        },
        "gb": {
            "label": "Bullish",
            "confidence": 0.6,
            "probabilities": {"bullish": 0.6, "neutral": 0.25, "bearish": 0.15},
            "forecast_return": 0.015,
            "forecast_volatility": 0.018,
        },
        "arima": {
            "label": "Neutral",
            "confidence": 0.5,
            "probabilities": {"bullish": 0.35, "neutral": 0.5, "bearish": 0.15},
            "forecast_return": 0.005,
            "forecast_volatility": 0.02,
        },
    }


class TestUncertaintyQuantifierInit:
    """Test initialization."""

    def test_default_initialization(self):
        """Test default initialization."""
        uq = UncertaintyQuantifier()

        assert uq.confidence_level == 0.95
        assert uq.z_score > 1.9  # ~1.96 for 95%
        assert uq.z_score < 2.0
        assert uq.min_samples_for_calibration == 30

    def test_custom_confidence_level(self):
        """Test custom confidence level."""
        uq = UncertaintyQuantifier(confidence_level=0.99)

        assert uq.confidence_level == 0.99
        assert uq.z_score > 2.5  # ~2.576 for 99%


class TestForecastAggregation:
    """Test forecast aggregation."""

    def test_aggregate_returns_valid_dict(self, sample_forecasts, equal_weights):
        """Test that aggregation returns valid dict."""
        uq = UncertaintyQuantifier()
        result = uq.aggregate_forecasts(sample_forecasts, equal_weights)

        assert "forecast" in result
        assert "volatility" in result
        assert "ci_lower" in result
        assert "ci_upper" in result
        assert "model_agreement" in result

    def test_weighted_average_forecast(self, sample_forecasts, equal_weights):
        """Test that forecast is weighted average."""
        uq = UncertaintyQuantifier()
        result = uq.aggregate_forecasts(sample_forecasts, equal_weights)

        expected = np.mean([f.forecast_value for f in sample_forecasts])
        assert abs(result["forecast"] - expected) < 0.001

    def test_ci_contains_forecast(self, sample_forecasts, equal_weights):
        """Test that CI contains forecast."""
        uq = UncertaintyQuantifier()
        result = uq.aggregate_forecasts(sample_forecasts, equal_weights)

        assert result["ci_lower"] <= result["forecast"]
        assert result["forecast"] <= result["ci_upper"]

    def test_volatility_positive(self, sample_forecasts, equal_weights):
        """Test that volatility is positive."""
        uq = UncertaintyQuantifier()
        result = uq.aggregate_forecasts(sample_forecasts, equal_weights)

        assert result["volatility"] > 0

    def test_model_agreement_bounded(self, sample_forecasts, equal_weights):
        """Test that model agreement is between 0 and 1."""
        uq = UncertaintyQuantifier()
        result = uq.aggregate_forecasts(sample_forecasts, equal_weights)

        assert 0 <= result["model_agreement"] <= 1

    def test_weighted_aggregation(self, sample_forecasts):
        """Test that weights affect aggregation."""
        uq = UncertaintyQuantifier()

        # Heavy weight on first model
        weights1 = {"rf": 0.8, "gb": 0.1, "arima": 0.1}
        result1 = uq.aggregate_forecasts(sample_forecasts, weights1)

        # Heavy weight on last model
        weights2 = {"rf": 0.1, "gb": 0.1, "arima": 0.8}
        result2 = uq.aggregate_forecasts(sample_forecasts, weights2)

        # Results should be different
        assert result1["forecast"] != result2["forecast"]

        # First should be closer to rf forecast
        rf_forecast = sample_forecasts[0].forecast_value
        arima_forecast = sample_forecasts[2].forecast_value

        assert abs(result1["forecast"] - rf_forecast) < abs(
            result1["forecast"] - arima_forecast
        )

    def test_handles_nan_forecasts(self, equal_weights):
        """Test handling of NaN forecasts."""
        forecasts = [
            ModelForecast("rf", 0.01, 0.02, -0.03, 0.05),
            ModelForecast("gb", np.nan, 0.02, np.nan, np.nan),
            ModelForecast("arima", 0.02, 0.02, 0.00, 0.04),
        ]

        uq = UncertaintyQuantifier()
        result = uq.aggregate_forecasts(forecasts, equal_weights)

        assert not np.isnan(result["forecast"])
        assert result["n_valid_models"] == 2

    def test_empty_forecasts(self, equal_weights):
        """Test with empty forecast list."""
        uq = UncertaintyQuantifier()
        result = uq.aggregate_forecasts([], equal_weights)

        assert "error" in result
        assert np.isnan(result["forecast"])


class TestFromPredictions:
    """Test aggregate_from_predictions method."""

    def test_aggregate_from_predictions(self, sample_predictions, equal_weights):
        """Test aggregation from prediction dicts."""
        uq = UncertaintyQuantifier()
        result = uq.aggregate_from_predictions(sample_predictions, equal_weights)

        assert "forecast" in result
        assert "volatility" in result
        assert result["n_valid_models"] == 3


class TestCalibration:
    """Test uncertainty calibration."""

    def test_calibrate_perfect_coverage(self):
        """Test calibration with perfect coverage."""
        uq = UncertaintyQuantifier(confidence_level=0.95)

        n = 100
        # Generate intervals that cover 95% of actuals
        actuals = np.random.randn(n) * 0.02
        ci_lower = actuals - 0.04
        ci_upper = actuals + 0.04

        result = uq.calibrate_uncertainty(ci_lower, ci_upper, actuals)

        # Should have coverage close to 1.0 (since all are in bounds)
        assert result["empirical_coverage"] == 1.0
        assert result["calibration_ratio"] > 1.0  # Over-coverage

    def test_calibrate_under_coverage(self):
        """Test calibration with under-coverage."""
        uq = UncertaintyQuantifier(confidence_level=0.95)

        np.random.seed(42)
        n = 100
        # Actuals spread wider than intervals
        actuals = np.random.randn(n) * 0.5
        # Intervals centered at 0 with narrow width
        ci_lower = np.zeros(n) - 0.1
        ci_upper = np.zeros(n) + 0.1

        result = uq.calibrate_uncertainty(ci_lower, ci_upper, actuals)

        assert result["empirical_coverage"] < 0.95
        assert result["needs_widening"]

    def test_calibrate_stores_ratio(self):
        """Test that calibration stores ratio."""
        uq = UncertaintyQuantifier()

        n = 50
        actuals = np.random.randn(n)
        ci_lower = actuals - 2
        ci_upper = actuals + 2

        uq.calibrate_uncertainty(ci_lower, ci_upper, actuals, "test_model")

        assert "test_model" in uq.calibration_ratios

    def test_calibrate_insufficient_samples(self):
        """Test calibration with insufficient samples."""
        uq = UncertaintyQuantifier(min_samples_for_calibration=50)

        actuals = np.random.randn(20)
        ci_lower = actuals - 1
        ci_upper = actuals + 1

        result = uq.calibrate_uncertainty(ci_lower, ci_upper, actuals)

        assert "error" in result


class TestApplyCalibration:
    """Test calibration application."""

    def test_apply_calibration(self, sample_forecasts, equal_weights):
        """Test applying calibration to forecast."""
        uq = UncertaintyQuantifier()

        # Set up calibration ratio (under-coverage scenario)
        uq.calibration_ratios["ensemble"] = 0.8

        result = uq.aggregate_forecasts(sample_forecasts, equal_weights)
        calibrated = uq.apply_calibration(result, "ensemble")

        assert calibrated["calibration_applied"]
        # Under-coverage should widen intervals
        assert calibrated["volatility"] > result["volatility"]

    def test_apply_calibration_over_coverage(self, sample_forecasts, equal_weights):
        """Test applying calibration for over-coverage."""
        uq = UncertaintyQuantifier()

        # Over-coverage scenario
        uq.calibration_ratios["ensemble"] = 1.2

        result = uq.aggregate_forecasts(sample_forecasts, equal_weights)
        calibrated = uq.apply_calibration(result, "ensemble")

        # Over-coverage should narrow intervals
        assert calibrated["volatility"] < result["volatility"]

    def test_no_calibration_available(self, sample_forecasts, equal_weights):
        """Test when no calibration is available."""
        uq = UncertaintyQuantifier()

        result = uq.aggregate_forecasts(sample_forecasts, equal_weights)
        not_calibrated = uq.apply_calibration(result)

        assert not not_calibrated["calibration_applied"]


class TestPredictionHistory:
    """Test prediction history tracking."""

    def test_record_prediction(self, sample_forecasts, equal_weights):
        """Test recording predictions."""
        uq = UncertaintyQuantifier()

        result = uq.aggregate_forecasts(sample_forecasts, equal_weights)
        uq.record_prediction(result, actual=0.01)

        assert len(uq.prediction_history) == 1
        assert uq.prediction_history[0]["actual"] == 0.01

    def test_update_calibration_from_history(self):
        """Test updating calibration from history."""
        uq = UncertaintyQuantifier(min_samples_for_calibration=10)

        # Record enough predictions
        for i in range(20):
            actual = np.random.randn() * 0.02
            uq.record_prediction({
                "forecast": actual + 0.001,
                "ci_lower": actual - 0.05,
                "ci_upper": actual + 0.05,
            }, actual=actual)

        result = uq.update_calibration_from_history()

        assert result is not None
        assert "empirical_coverage" in result


class TestCalibrationStatus:
    """Test calibration status reporting."""

    def test_get_calibration_status(self):
        """Test getting calibration status."""
        uq = UncertaintyQuantifier()

        status = uq.get_calibration_status()

        assert "confidence_level" in status
        assert "z_score" in status
        assert "calibration_ratios" in status

    def test_get_calibration_history(self):
        """Test getting calibration history."""
        uq = UncertaintyQuantifier()

        # Perform calibration
        n = 50
        actuals = np.random.randn(n)
        uq.calibrate_uncertainty(actuals - 1, actuals + 1, actuals)

        history = uq.get_calibration_history()

        assert len(history) == 1


class TestDirectionalQuantifier:
    """Test DirectionalUncertaintyQuantifier."""

    def test_aggregate_probabilities(self, sample_predictions, equal_weights):
        """Test probability aggregation."""
        duq = DirectionalUncertaintyQuantifier()
        result = duq.aggregate_probabilities(sample_predictions, equal_weights)

        assert "label" in result
        assert "confidence" in result
        assert "probabilities" in result
        assert "entropy" in result

    def test_probabilities_sum_to_one(self, sample_predictions, equal_weights):
        """Test that aggregated probabilities sum to 1."""
        duq = DirectionalUncertaintyQuantifier()
        result = duq.aggregate_probabilities(sample_predictions, equal_weights)

        total = sum(result["probabilities"].values())
        assert abs(total - 1.0) < 0.01

    def test_confidence_equals_max_prob(self, sample_predictions, equal_weights):
        """Test that confidence equals max probability."""
        duq = DirectionalUncertaintyQuantifier()
        result = duq.aggregate_probabilities(sample_predictions, equal_weights)

        max_prob = max(result["probabilities"].values())
        assert abs(result["confidence"] - max_prob) < 0.01

    def test_entropy_bounded(self, sample_predictions, equal_weights):
        """Test that entropy is bounded."""
        duq = DirectionalUncertaintyQuantifier()
        result = duq.aggregate_probabilities(sample_predictions, equal_weights)

        assert result["entropy"] >= 0
        assert result["normalized_entropy"] >= 0
        assert result["normalized_entropy"] <= 1

    def test_high_agreement_low_entropy(self):
        """Test that high agreement gives low entropy."""
        duq = DirectionalUncertaintyQuantifier()

        # All models agree strongly
        predictions = {
            "rf": {"probabilities": {"bullish": 0.9, "neutral": 0.08, "bearish": 0.02}},
            "gb": {"probabilities": {"bullish": 0.85, "neutral": 0.1, "bearish": 0.05}},
        }

        result = duq.aggregate_probabilities(predictions, {"rf": 0.5, "gb": 0.5})

        # Should have low entropy (high confidence)
        assert result["normalized_entropy"] < 0.5

    def test_disagreement_high_entropy(self):
        """Test that disagreement gives high entropy."""
        duq = DirectionalUncertaintyQuantifier()

        # Models disagree (uniform probabilities)
        predictions = {
            "rf": {"probabilities": {"bullish": 0.33, "neutral": 0.34, "bearish": 0.33}},
            "gb": {"probabilities": {"bullish": 0.33, "neutral": 0.34, "bearish": 0.33}},
        }

        result = duq.aggregate_probabilities(predictions, {"rf": 0.5, "gb": 0.5})

        # Should have high entropy
        assert result["normalized_entropy"] > 0.9


class TestIntegration:
    """Integration tests."""

    def test_full_workflow(self, sample_forecasts, equal_weights):
        """Test complete workflow."""
        uq = UncertaintyQuantifier(confidence_level=0.95)

        # 1. Aggregate forecasts
        result = uq.aggregate_forecasts(sample_forecasts, equal_weights)
        assert not np.isnan(result["forecast"])

        # 2. Record predictions with actuals
        for _ in range(50):
            actual = result["forecast"] + np.random.randn() * 0.02
            uq.record_prediction(result, actual=actual)

        # 3. Update calibration
        cal_result = uq.update_calibration_from_history()
        assert cal_result is not None

        # 4. Apply calibration
        calibrated = uq.apply_calibration(result)
        assert calibrated["calibration_applied"]

        # 5. Get status
        status = uq.get_calibration_status()
        assert len(status["calibration_ratios"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
