"""Unit tests for Weight Optimizer."""

import numpy as np
import pytest

from src.models.weight_optimizer import (
    WeightOptimizer,
    AdaptiveWeightOptimizer,
)


@pytest.fixture
def sample_predictions():
    """Create sample predictions for testing."""
    np.random.seed(42)
    n = 100

    actuals = np.cumsum(np.random.randn(n) * 0.01) + 100

    predictions = {
        "rf": actuals + np.random.randn(n) * 0.5,
        "gb": actuals + np.random.randn(n) * 0.3,
        "arima": actuals + np.random.randn(n) * 0.4,
    }

    return predictions, actuals


@pytest.fixture
def biased_predictions():
    """Create predictions with clear quality differences."""
    np.random.seed(42)
    n = 100

    actuals = np.linspace(100, 110, n)

    # Good model: low error
    good_preds = actuals + np.random.randn(n) * 0.1

    # Medium model: medium error
    medium_preds = actuals + np.random.randn(n) * 0.5

    # Bad model: high error with bias
    bad_preds = actuals + np.random.randn(n) * 1.0 + 2.0

    predictions = {
        "good": good_preds,
        "medium": medium_preds,
        "bad": bad_preds,
    }

    return predictions, actuals


class TestWeightOptimizerInit:
    """Test WeightOptimizer initialization."""

    def test_default_initialization(self):
        """Test default initialization."""
        optimizer = WeightOptimizer()

        assert optimizer.optimization_method == "ridge"
        assert optimizer.alpha == 0.01
        assert optimizer.min_weight == 0.05
        assert optimizer.max_weight == 0.60
        assert optimizer.lookback_window == 50
        assert optimizer.is_fitted is False

    def test_custom_initialization(self):
        """Test custom initialization."""
        optimizer = WeightOptimizer(
            optimization_method="sharpe",
            alpha=0.1,
            min_weight=0.1,
            max_weight=0.5,
            lookback_window=100,
        )

        assert optimizer.optimization_method == "sharpe"
        assert optimizer.alpha == 0.1
        assert optimizer.min_weight == 0.1
        assert optimizer.max_weight == 0.5
        assert optimizer.lookback_window == 100


class TestRidgeOptimization:
    """Test ridge regression optimization."""

    def test_ridge_returns_weights(self, sample_predictions):
        """Test that ridge optimization returns valid weights."""
        predictions, actuals = sample_predictions
        optimizer = WeightOptimizer(optimization_method="ridge")

        weights = optimizer.optimize_weights(predictions, actuals)

        assert len(weights) == 3
        assert all(w >= 0 for w in weights.values())
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_ridge_respects_bounds(self, sample_predictions):
        """Test that ridge respects weight bounds."""
        predictions, actuals = sample_predictions
        optimizer = WeightOptimizer(
            optimization_method="ridge",
            min_weight=0.1,
            max_weight=0.5,
        )

        weights = optimizer.optimize_weights(predictions, actuals)

        for w in weights.values():
            assert w >= 0.1 - 0.01  # Small tolerance
            assert w <= 0.5 + 0.01

    def test_ridge_favors_better_model(self, biased_predictions):
        """Test that ridge gives more weight to better models."""
        predictions, actuals = biased_predictions
        optimizer = WeightOptimizer(
            optimization_method="ridge",
            min_weight=0.01,
            max_weight=0.9,
        )

        weights = optimizer.optimize_weights(predictions, actuals)

        # Good model should have highest weight
        assert weights["good"] >= weights["medium"]


class TestSharpeOptimization:
    """Test Sharpe ratio optimization."""

    def test_sharpe_returns_weights(self, sample_predictions):
        """Test that Sharpe optimization returns valid weights."""
        predictions, actuals = sample_predictions
        optimizer = WeightOptimizer(optimization_method="sharpe")

        weights = optimizer.optimize_weights(predictions, actuals)

        assert len(weights) == 3
        assert all(w >= 0 for w in weights.values())
        assert abs(sum(weights.values()) - 1.0) < 0.01


class TestDirectionalOptimization:
    """Test directional accuracy optimization."""

    def test_directional_returns_weights(self, sample_predictions):
        """Test that directional optimization returns valid weights."""
        predictions, actuals = sample_predictions
        optimizer = WeightOptimizer(optimization_method="directional")

        weights = optimizer.optimize_weights(predictions, actuals)

        assert len(weights) == 3
        assert all(w >= 0 for w in weights.values())
        assert abs(sum(weights.values()) - 1.0) < 0.01


class TestScipyOptimization:
    """Test scipy-based optimization."""

    def test_scipy_returns_weights(self, sample_predictions):
        """Test that scipy optimization returns valid weights."""
        predictions, actuals = sample_predictions
        optimizer = WeightOptimizer(optimization_method="scipy")

        weights = optimizer.optimize_weights(predictions, actuals)

        assert len(weights) == 3
        assert all(w >= 0 for w in weights.values())
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_scipy_respects_bounds(self, sample_predictions):
        """Test that scipy respects weight bounds."""
        predictions, actuals = sample_predictions
        optimizer = WeightOptimizer(
            optimization_method="scipy",
            min_weight=0.15,
            max_weight=0.45,
        )

        weights = optimizer.optimize_weights(predictions, actuals)

        for w in weights.values():
            assert w >= 0.15 - 0.02  # Small tolerance
            assert w <= 0.45 + 0.02


class TestEqualWeights:
    """Test equal weights fallback."""

    def test_equal_weights(self, sample_predictions):
        """Test equal weights."""
        predictions, actuals = sample_predictions
        optimizer = WeightOptimizer(optimization_method="equal")

        weights = optimizer.optimize_weights(predictions, actuals)

        assert len(weights) == 3
        for w in weights.values():
            assert abs(w - 1/3) < 0.01


class TestEdgeCases:
    """Test edge cases."""

    def test_single_model(self):
        """Test with single model."""
        np.random.seed(42)
        predictions = {"single": np.random.randn(50)}
        actuals = np.random.randn(50)

        optimizer = WeightOptimizer()
        weights = optimizer.optimize_weights(predictions, actuals)

        assert weights == {"single": 1.0}

    def test_empty_predictions(self):
        """Test with empty predictions."""
        optimizer = WeightOptimizer()
        weights = optimizer.optimize_weights({}, np.array([]))

        assert weights == {}

    def test_short_data(self):
        """Test with very short data."""
        np.random.seed(42)
        predictions = {
            "a": np.array([1, 2]),
            "b": np.array([1.5, 2.5]),
        }
        actuals = np.array([1, 2])

        optimizer = WeightOptimizer()
        weights = optimizer.optimize_weights(predictions, actuals)

        assert len(weights) == 2
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_lookback_window(self):
        """Test lookback window truncation."""
        np.random.seed(42)
        n = 200
        predictions = {
            "a": np.random.randn(n),
            "b": np.random.randn(n),
        }
        actuals = np.random.randn(n)

        optimizer = WeightOptimizer(lookback_window=50)
        weights = optimizer.optimize_weights(predictions, actuals)

        # Should still work
        assert len(weights) == 2


class TestStateManagement:
    """Test state management."""

    def test_weights_stored(self, sample_predictions):
        """Test that weights are stored after optimization."""
        predictions, actuals = sample_predictions
        optimizer = WeightOptimizer()

        optimizer.optimize_weights(predictions, actuals)

        assert optimizer.is_fitted
        assert optimizer.weights is not None
        assert optimizer.get_weights() == optimizer.weights

    def test_optimization_history(self, sample_predictions):
        """Test optimization history tracking."""
        predictions, actuals = sample_predictions
        optimizer = WeightOptimizer()

        # Multiple optimizations
        optimizer.optimize_weights(predictions, actuals, optimize_for="ridge")
        optimizer.optimize_weights(predictions, actuals, optimize_for="sharpe")

        assert len(optimizer.optimization_history) == 2

        history_df = optimizer.get_optimization_history()
        assert len(history_df) == 2
        assert "method" in history_df.columns

    def test_get_info(self, sample_predictions):
        """Test get_info method."""
        predictions, actuals = sample_predictions
        optimizer = WeightOptimizer()
        optimizer.optimize_weights(predictions, actuals)

        info = optimizer.get_info()

        assert info["optimization_method"] == "ridge"
        assert info["is_fitted"] is True
        assert info["current_weights"] is not None


class TestIncrementalUpdate:
    """Test incremental weight updates."""

    def test_update_from_performance(self, sample_predictions):
        """Test incremental weight update."""
        predictions, actuals = sample_predictions
        optimizer = WeightOptimizer()
        optimizer.optimize_weights(predictions, actuals)

        original_weight = optimizer.weights["rf"]

        # Update with good performance
        optimizer.update_from_performance("rf", accuracy=0.7, recent_error=0.1)

        # Weight should increase slightly
        assert optimizer.weights["rf"] != original_weight

        # Weights should still sum to 1
        assert abs(sum(optimizer.weights.values()) - 1.0) < 0.01


class TestAdaptiveOptimizer:
    """Test AdaptiveWeightOptimizer."""

    def test_init(self):
        """Test initialization."""
        optimizer = AdaptiveWeightOptimizer()

        assert optimizer.default_method == "ridge"
        assert optimizer.volatility_threshold == 0.02
        assert optimizer.trend_threshold == 0.01

    def test_regime_detection_normal(self):
        """Test normal regime detection."""
        optimizer = AdaptiveWeightOptimizer()

        normal_returns = np.random.randn(50) * 0.005
        regime = optimizer.detect_regime(normal_returns)

        assert regime == "normal"

    def test_regime_detection_high_vol(self):
        """Test high volatility regime detection."""
        optimizer = AdaptiveWeightOptimizer(volatility_threshold=0.02)

        high_vol_returns = np.random.randn(50) * 0.05
        regime = optimizer.detect_regime(high_vol_returns)

        assert regime == "high_vol"

    def test_regime_detection_trending(self):
        """Test trending regime detection."""
        optimizer = AdaptiveWeightOptimizer(trend_threshold=0.01)

        # Strong upward trend
        trending_returns = np.ones(50) * 0.02
        regime = optimizer.detect_regime(trending_returns)

        assert regime == "trending"

    def test_adaptive_optimization(self, sample_predictions):
        """Test adaptive weight optimization."""
        predictions, actuals = sample_predictions
        optimizer = AdaptiveWeightOptimizer()

        # With normal returns
        normal_returns = np.random.randn(50) * 0.005
        weights = optimizer.optimize_weights_adaptive(
            predictions, actuals, returns=normal_returns
        )

        assert len(weights) == 3
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_method_selection_by_regime(self, sample_predictions):
        """Test that method changes based on regime."""
        predictions, actuals = sample_predictions
        optimizer = AdaptiveWeightOptimizer()

        # High vol -> directional
        high_vol_returns = np.random.randn(50) * 0.05
        optimizer.optimize_weights_adaptive(
            predictions, actuals, returns=high_vol_returns
        )
        assert optimizer.current_regime == "high_vol"

        # Trending -> sharpe
        trending_returns = np.ones(50) * 0.02
        optimizer.optimize_weights_adaptive(
            predictions, actuals, returns=trending_returns
        )
        assert optimizer.current_regime == "trending"


class TestIntegration:
    """Integration tests."""

    def test_full_workflow(self):
        """Test full optimization workflow."""
        np.random.seed(42)
        n = 100

        # Generate data
        actuals = np.cumsum(np.random.randn(n) * 0.01) + 100

        predictions = {
            "rf": actuals + np.random.randn(n) * 0.3,
            "gb": actuals + np.random.randn(n) * 0.4,
            "arima": actuals + np.random.randn(n) * 0.5,
            "prophet": actuals + np.random.randn(n) * 0.35,
            "lstm": actuals + np.random.randn(n) * 0.25,
        }

        optimizer = WeightOptimizer(
            optimization_method="ridge",
            min_weight=0.1,
            max_weight=0.4,
        )

        weights = optimizer.optimize_weights(predictions, actuals)

        # Verify all models have weights
        assert len(weights) == 5
        assert set(weights.keys()) == set(predictions.keys())

        # Verify bounds (with small tolerance for normalization)
        for w in weights.values():
            assert 0.1 - 0.02 <= w <= 0.4 + 0.02

        # Verify sum
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_multiple_optimizations(self, sample_predictions):
        """Test multiple consecutive optimizations."""
        predictions, actuals = sample_predictions
        optimizer = WeightOptimizer()

        methods = ["ridge", "sharpe", "directional", "scipy"]
        all_weights = []

        for method in methods:
            weights = optimizer.optimize_weights(
                predictions, actuals, optimize_for=method
            )
            all_weights.append(weights)

        # All should be valid
        for weights in all_weights:
            assert len(weights) == 3
            assert abs(sum(weights.values()) - 1.0) < 0.01


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
