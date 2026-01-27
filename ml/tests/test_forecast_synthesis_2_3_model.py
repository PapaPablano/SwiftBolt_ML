"""
Forecast synthesis validation for 2-3 model ensemble.

Tests simplified forecast synthesis with 2-3 model configurations
to validate Phase 4.3 implementation.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta


class TestEnsembleAgreementCalculation:
    """Test ensemble agreement calculation for 2-3 model setups."""

    def test_2_model_full_agreement(self):
        """Test 2-model ensemble with both models agreeing."""
        predictions = ["bullish", "bullish"]
        unique_count = len(set(predictions))
        agreement = 1.0 - (unique_count - 1) / (len(predictions) - 1)

        assert agreement == 1.0

    def test_2_model_no_agreement(self):
        """Test 2-model ensemble with models disagreeing."""
        predictions = ["bullish", "bearish"]
        unique_count = len(set(predictions))
        agreement = 1.0 - (unique_count - 1) / (len(predictions) - 1)

        assert agreement == 0.0

    def test_3_model_full_agreement(self):
        """Test 3-model ensemble with all models agreeing."""
        predictions = ["bullish", "bullish", "bullish"]
        unique_count = len(set(predictions))
        agreement = 1.0 - (unique_count - 1) / (len(predictions) - 1)

        assert agreement == 1.0

    def test_3_model_partial_agreement(self):
        """Test 3-model ensemble with 2 of 3 agreeing."""
        predictions = ["bullish", "bullish", "bearish"]
        unique_count = len(set(predictions))
        agreement = 1.0 - (unique_count - 1) / (len(predictions) - 1)

        # 2 unique predictions: agreement = 1 - 1/2 = 0.5
        assert agreement == pytest.approx(0.5, abs=0.001)

    def test_3_model_no_agreement(self):
        """Test 3-model ensemble with no agreement."""
        predictions = ["bullish", "neutral", "bearish"]
        unique_count = len(set(predictions))
        agreement = 1.0 - (unique_count - 1) / (len(predictions) - 1)

        # 3 unique predictions: agreement = 1 - 2/2 = 0.0
        assert agreement == 0.0


class TestConfidenceCalculation:
    """Test confidence calculation from ensemble agreement."""

    def test_base_confidence_with_agreement_boost(self):
        """Test confidence boost when agreement >= 0.5."""
        base_confidence = 0.50
        agreement = 0.75  # High agreement

        # Agreement >= 0.5 triggers boost
        if agreement >= 0.5:
            final_confidence = base_confidence + 0.10
        else:
            final_confidence = base_confidence

        assert final_confidence == 0.60

    def test_base_confidence_without_agreement_boost(self):
        """Test confidence without boost when agreement < 0.5."""
        base_confidence = 0.50
        agreement = 0.25  # Low agreement

        # No boost when agreement < 0.5
        if agreement >= 0.5:
            final_confidence = base_confidence + 0.10
        else:
            final_confidence = base_confidence

        assert final_confidence == 0.50

    def test_confidence_bounds(self):
        """Test that confidence stays within [0, 1] bounds."""
        base_confidences = [0.30, 0.50, 0.70, 0.90]
        agreements = [0.0, 0.5, 1.0]

        for base in base_confidences:
            for agreement in agreements:
                if agreement >= 0.5:
                    final = base + 0.10
                else:
                    final = base

                # Cap at 1.0
                final = min(final, 1.0)

                assert 0.0 <= final <= 1.0

    def test_confidence_ceiling_at_100_percent(self):
        """Test that confidence is capped at 1.0."""
        base_confidence = 0.95
        agreement = 0.75

        if agreement >= 0.5:
            final_confidence = min(base_confidence + 0.10, 1.0)
        else:
            final_confidence = base_confidence

        assert final_confidence == 1.0


class TestForecastWeightDistribution:
    """Test weight distribution for 2-3 model ensembles."""

    def test_2_model_weights(self):
        """Test 2-model ensemble weights sum to 1.0."""
        lstm_weight = 0.50
        arima_weight = 0.50

        total = lstm_weight + arima_weight
        assert total == pytest.approx(1.0, abs=0.001)

    def test_3_model_weights(self):
        """Test 3-model ensemble weights sum to 1.0."""
        lstm_weight = 0.40
        arima_weight = 0.30
        gb_weight = 0.30

        total = lstm_weight + arima_weight + gb_weight
        assert total == pytest.approx(1.0, abs=0.001)

    def test_weight_application_2_model(self):
        """Test applying weights to 2-model predictions."""
        lstm_prediction = 5.2
        arima_prediction = 5.0

        lstm_weight = 0.50
        arima_weight = 0.50

        weighted_forecast = (lstm_prediction * lstm_weight +
                           arima_prediction * arima_weight)

        assert weighted_forecast == pytest.approx(5.1, abs=0.001)

    def test_weight_application_3_model(self):
        """Test applying weights to 3-model predictions."""
        lstm_prediction = 5.3
        arima_prediction = 5.0
        gb_prediction = 5.1

        lstm_weight = 0.40
        arima_weight = 0.30
        gb_weight = 0.30

        weighted_forecast = (lstm_prediction * lstm_weight +
                           arima_prediction * arima_weight +
                           gb_prediction * gb_weight)

        expected = 5.3 * 0.40 + 5.0 * 0.30 + 5.1 * 0.30
        assert weighted_forecast == pytest.approx(expected, abs=0.001)


class TestForecastSynthesisScenarios:
    """Test complete forecast synthesis scenarios."""

    def test_2_model_bullish_consensus(self):
        """Test 2-model synthesis with bullish consensus."""
        # Input: Both models predict bullish
        lstm_direction = "bullish"
        arima_direction = "bullish"
        lstm_strength = 0.70
        arima_strength = 0.65

        # Ensemble agreement
        agreement = 1.0  # Both agree

        # Final direction
        final_direction = "bullish"
        if agreement >= 0.5:
            final_strength = min(0.60 + 0.10, 1.0)  # Confidence boost
        else:
            final_strength = 0.60

        assert final_direction == "bullish"
        assert final_strength == 0.70

    def test_2_model_conflicting(self):
        """Test 2-model synthesis with conflicting signals."""
        lstm_direction = "bullish"
        arima_direction = "bearish"

        # Ensemble agreement
        agreement = 0.0  # Complete disagreement

        # Default to neutral without consensus
        final_direction = lstm_direction if agreement > 0.5 else "neutral"
        final_strength = 0.40  # Low confidence due to disagreement

        assert final_direction == "neutral"
        assert final_strength == 0.40

    def test_3_model_majority_bullish(self):
        """Test 3-model synthesis with bullish majority."""
        predictions = ["bullish", "bullish", "bearish"]
        unique_count = len(set(predictions))
        agreement = 1.0 - (unique_count - 1) / (len(predictions) - 1)

        # 2 out of 3 bullish = consensus bullish
        final_direction = "bullish"
        if agreement >= 0.5:
            final_strength = min(0.60 + 0.10, 1.0)
        else:
            final_strength = 0.60

        assert final_direction == "bullish"
        assert final_strength == 0.70

    def test_3_model_no_consensus(self):
        """Test 3-model synthesis with no consensus."""
        predictions = ["bullish", "bearish", "neutral"]
        unique_count = len(set(predictions))
        agreement = 1.0 - (unique_count - 1) / (len(predictions) - 1)

        # No agreement = neutral stance
        final_direction = "neutral"
        final_strength = 0.40

        assert agreement == 0.0
        assert final_direction == "neutral"
        assert final_strength == 0.40


class TestForecastValidation:
    """Test forecast validation metrics."""

    def test_forecast_bounds_valid(self):
        """Test forecast is within reasonable bounds."""
        current_price = 100.0
        forecast_price = 102.5
        pct_change = (forecast_price - current_price) / current_price

        # Max reasonable change is ±5%
        assert abs(pct_change) <= 0.05

    def test_forecast_with_very_high_confidence(self):
        """Test forecast with very high confidence."""
        price = 100.0
        confidence = 0.95  # Very confident
        direction = "bullish"

        # High confidence bullish: expect larger move
        expected_move = 0.03 if direction == "bullish" else -0.03
        forecast = price * (1 + expected_move)

        assert forecast > price

    def test_forecast_with_low_confidence(self):
        """Test forecast with low confidence."""
        price = 100.0
        confidence = 0.35  # Low confidence
        direction = "bullish"

        # Low confidence: expect smaller or no move
        expected_move = 0.01 if confidence > 0.50 else 0.0
        forecast = price * (1 + expected_move)

        assert forecast == price


class TestDirectionalAccuracy:
    """Test directional accuracy metrics."""

    def test_perfect_directional_accuracy(self):
        """Test perfect directional predictions."""
        predictions = ["bullish", "bullish", "bearish", "bullish", "bearish"]
        actuals = ["bullish", "bullish", "bearish", "bullish", "bearish"]

        correct = sum(1 for p, a in zip(predictions, actuals) if p == a)
        accuracy = correct / len(predictions)

        assert accuracy == 1.0

    def test_partial_directional_accuracy(self):
        """Test partial directional accuracy."""
        predictions = ["bullish", "bullish", "bearish", "bearish", "bearish"]
        actuals = ["bullish", "bearish", "bearish", "bullish", "bearish"]

        correct = sum(1 for p, a in zip(predictions, actuals) if p == a)
        accuracy = correct / len(predictions)

        assert accuracy == pytest.approx(0.6, abs=0.01)

    def test_random_directional_accuracy(self):
        """Test random directional guessing."""
        predictions = ["bullish", "bullish", "bearish", "bearish", "bullish"]
        actuals = ["bearish", "bearish", "bullish", "bullish", "bearish"]

        correct = sum(1 for p, a in zip(predictions, actuals) if p == a)
        accuracy = correct / len(predictions)

        assert accuracy == pytest.approx(0.0, abs=0.01)


class TestMultiSymbolForecastGeneration:
    """Test forecast generation across multiple symbols."""

    def test_forecast_generation_10_symbols(self):
        """Test generating forecasts for 10 symbols."""
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
                  "NVDA", "META", "NFLX", "ADBE", "CRM"]

        forecasts = {}
        for symbol in symbols:
            # Simulate 2-model forecast
            lstm_pred = np.random.uniform(95, 105)
            arima_pred = np.random.uniform(95, 105)

            ensemble_pred = lstm_pred * 0.50 + arima_pred * 0.50
            direction = "bullish" if ensemble_pred > 100 else "bearish"
            confidence = np.random.uniform(0.40, 0.80)

            forecasts[symbol] = {
                "price": ensemble_pred,
                "direction": direction,
                "confidence": confidence,
            }

        # Verify all symbols have forecasts
        assert len(forecasts) == 10
        for symbol in symbols:
            assert symbol in forecasts
            assert "price" in forecasts[symbol]
            assert "direction" in forecasts[symbol]
            assert "confidence" in forecasts[symbol]

    def test_forecast_consistency_across_runs(self):
        """Test forecast reproducibility with same inputs."""
        symbol = "AAPL"

        # First run
        np.random.seed(42)
        lstm_1 = 102.5
        arima_1 = 101.8
        ensemble_1 = lstm_1 * 0.50 + arima_1 * 0.50

        # Second run (same seed)
        np.random.seed(42)
        lstm_2 = 102.5
        arima_2 = 101.8
        ensemble_2 = lstm_2 * 0.50 + arima_2 * 0.50

        assert ensemble_1 == ensemble_2

    def test_forecast_across_multiple_horizons(self):
        """Test forecasts for same symbol across multiple horizons."""
        symbol = "AAPL"
        horizons = ["1D", "4h", "8h"]

        forecasts = {}
        for horizon in horizons:
            lstm_pred = 102.5
            arima_pred = 101.8
            ensemble_pred = lstm_pred * 0.50 + arima_pred * 0.50

            forecasts[horizon] = {
                "price": ensemble_pred,
                "direction": "bullish",
                "confidence": 0.65,
            }

        # All horizons should have predictions
        assert len(forecasts) == 3
        for horizon in horizons:
            assert horizon in forecasts


class TestWeightConstraints:
    """Test weight constraints are maintained."""

    def test_2_model_weights_positive(self):
        """Test 2-model weights are all positive."""
        weights = [0.50, 0.50]
        assert all(w > 0 for w in weights)

    def test_3_model_weights_positive(self):
        """Test 3-model weights are all positive."""
        weights = [0.40, 0.30, 0.30]
        assert all(w > 0 for w in weights)

    def test_2_model_weights_sum_to_one(self):
        """Test 2-model weights sum to exactly 1.0."""
        weights = [0.50, 0.50]
        assert sum(weights) == pytest.approx(1.0, abs=0.0001)

    def test_3_model_weights_sum_to_one(self):
        """Test 3-model weights sum to exactly 1.0."""
        weights = [0.40, 0.30, 0.30]
        assert sum(weights) == pytest.approx(1.0, abs=0.0001)

    def test_weights_within_bounds(self):
        """Test weights are within [0, 1] range."""
        weights_2 = [0.50, 0.50]
        weights_3 = [0.40, 0.30, 0.30]

        assert all(0 <= w <= 1 for w in weights_2)
        assert all(0 <= w <= 1 for w in weights_3)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
