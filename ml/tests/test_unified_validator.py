"""
Unit tests for the Unified Validation Framework.

Tests cover:
- Unified confidence calculation
- Drift detection thresholds
- Multi-timeframe reconciliation
- Retraining triggers
- Edge cases
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Add ml directory to path for proper package imports
ml_dir = Path(__file__).parent.parent
sys.path.insert(0, str(ml_dir))

from src.validation.unified_framework import (
    UnifiedPrediction,
    UnifiedValidator,
    ValidationScores,
    validate_prediction,
)


class TestUnifiedConfidenceCalculation:
    """Test the weighted average confidence calculation."""

    def setup_method(self):
        self.validator = UnifiedValidator()

    def test_basic_weighted_average(self):
        """Test standard weighted average calculation."""
        scores = ValidationScores(
            backtesting_score=0.988,
            walkforward_score=0.78,
            live_score=0.40,
            multi_tf_scores={},
        )

        result = self.validator.validate("AAPL", "BULLISH", scores)

        # Expected: 0.40*0.988 + 0.35*0.78 + 0.25*0.40 = 0.768 (before adjustments)
        # With drift penalty and no TF conflict, result will be lower
        assert 0.5 < result.unified_confidence < 0.8

    def test_perfect_scores(self):
        """Test with all perfect scores."""
        scores = ValidationScores(
            backtesting_score=1.0,
            walkforward_score=1.0,
            live_score=1.0,
            multi_tf_scores={"D1": 0.5, "W1": 0.6},
        )

        result = self.validator.validate("AAPL", "BULLISH", scores)

        # Perfect scores should give high confidence (with consensus bonus)
        assert result.unified_confidence >= 0.95

    def test_zero_scores(self):
        """Test with zero scores."""
        scores = ValidationScores(
            backtesting_score=0.0,
            walkforward_score=0.0,
            live_score=0.0,
            multi_tf_scores={},
        )

        result = self.validator.validate("AAPL", "BULLISH", scores)

        assert result.unified_confidence == 0.0

    def test_custom_weights(self):
        """Test with custom weight configuration."""
        # Heavy emphasis on live score
        validator = UnifiedValidator(
            backtest_weight=0.20,
            walkforward_weight=0.20,
            live_weight=0.60,
        )

        scores = ValidationScores(
            backtesting_score=0.90,
            walkforward_score=0.80,
            live_score=0.90,
            multi_tf_scores={"D1": 0.5},
        )

        result = validator.validate("AAPL", "BULLISH", scores)

        # Should be close to 0.88 (weighted by live)
        assert result.unified_confidence > 0.85


class TestDriftDetection:
    """Test model drift detection logic."""

    def setup_method(self):
        self.validator = UnifiedValidator()

    def test_no_drift(self):
        """Test when backtesting and live scores are similar."""
        scores = ValidationScores(
            backtesting_score=0.75,
            walkforward_score=0.72,
            live_score=0.70,
            multi_tf_scores={},
        )

        result = self.validator.validate("AAPL", "BULLISH", scores)

        assert result.drift_detected is False
        assert result.drift_severity in ("none", "minor")
        assert result.drift_magnitude < 0.25

    def test_moderate_drift(self):
        """Test moderate drift detection (25-50% divergence)."""
        scores = ValidationScores(
            backtesting_score=0.80,
            walkforward_score=0.65,
            live_score=0.55,  # 31% drift from backtesting
            multi_tf_scores={},
        )

        result = self.validator.validate("AAPL", "BULLISH", scores)

        assert result.drift_detected is True
        assert result.drift_severity == "moderate"
        assert 0.25 <= result.drift_magnitude < 0.50

    def test_severe_drift(self):
        """Test severe drift detection (50-75% divergence)."""
        scores = ValidationScores(
            backtesting_score=0.988,
            walkforward_score=0.78,
            live_score=0.40,  # ~60% drift
            multi_tf_scores={},
        )

        result = self.validator.validate("AAPL", "BULLISH", scores)

        assert result.drift_detected is True
        assert result.drift_severity == "severe"
        assert 0.50 <= result.drift_magnitude < 0.75

    def test_critical_drift(self):
        """Test critical drift detection (>75% divergence)."""
        scores = ValidationScores(
            backtesting_score=0.90,
            walkforward_score=0.50,
            live_score=0.10,  # ~89% drift
            multi_tf_scores={},
        )

        result = self.validator.validate("AAPL", "BULLISH", scores)

        assert result.drift_detected is True
        assert result.drift_severity == "critical"
        assert result.drift_magnitude > 0.75
        assert result.retraining_trigger is True

    def test_drift_with_zero_backtesting(self):
        """Test drift detection when backtesting score is zero."""
        scores = ValidationScores(
            backtesting_score=0.0,
            walkforward_score=0.50,
            live_score=0.40,
            multi_tf_scores={},
        )

        result = self.validator.validate("AAPL", "BULLISH", scores)

        # Should not crash, drift should be marked as not detected
        assert result.drift_detected is False
        assert "No historical data" in result.drift_explanation


class TestMultiTimeframeReconciliation:
    """Test multi-timeframe prediction reconciliation."""

    def setup_method(self):
        self.validator = UnifiedValidator()

    def test_all_bullish_consensus(self):
        """Test when all timeframes agree on bullish."""
        scores = ValidationScores(
            backtesting_score=0.80,
            walkforward_score=0.75,
            live_score=0.75,
            multi_tf_scores={
                "M15": 0.40,
                "H1": 0.45,
                "H4": 0.50,
                "D1": 0.55,
                "W1": 0.60,
            },
        )

        result = self.validator.validate("AAPL", "BULLISH", scores)

        assert result.timeframe_conflict is False
        assert result.consensus_direction == "BULLISH"

    def test_all_bearish_consensus(self):
        """Test when all timeframes agree on bearish."""
        scores = ValidationScores(
            backtesting_score=0.80,
            walkforward_score=0.75,
            live_score=0.75,
            multi_tf_scores={
                "M15": -0.40,
                "H1": -0.45,
                "H4": -0.50,
                "D1": -0.55,
                "W1": -0.60,
            },
        )

        result = self.validator.validate("AAPL", "BEARISH", scores)

        assert result.timeframe_conflict is False
        assert result.consensus_direction == "BEARISH"

    def test_conflict_short_vs_long_tf(self):
        """Test conflict when short TFs bearish, long TFs bullish."""
        scores = ValidationScores(
            backtesting_score=0.80,
            walkforward_score=0.75,
            live_score=0.70,
            multi_tf_scores={
                "M15": -0.48,  # BEARISH (weight 0.05)
                "H1": -0.40,  # BEARISH (weight 0.10)
                "H4": -0.35,  # BEARISH (weight 0.20)
                "D1": 0.60,  # BULLISH (weight 0.30)
                "W1": 0.70,  # BULLISH (weight 0.35)
            },
        )

        result = self.validator.validate("AAPL", "BULLISH", scores)

        # W1 + D1 (0.65) > M15 + H1 + H4 (0.35), so consensus should be BULLISH
        # But there is still conflict since both directions have weight
        assert result.consensus_direction == "BULLISH"

    def test_conflict_with_neutral_mixed(self):
        """Test with neutral and conflicting directions."""
        scores = ValidationScores(
            backtesting_score=0.80,
            walkforward_score=0.75,
            live_score=0.70,
            multi_tf_scores={
                "M15": 0.10,  # NEUTRAL
                "H1": 0.15,  # NEUTRAL
                "H4": -0.40,  # BEARISH
                "D1": 0.40,  # BULLISH
                "W1": 0.05,  # NEUTRAL
            },
        )

        result = self.validator.validate("AAPL", "BULLISH", scores)

        # Mixed signals should show conflict
        # D1 bullish (0.30) vs H4 bearish (0.20) - close margin
        assert result.timeframe_conflict is True

    def test_empty_multi_tf_scores(self):
        """Test with no multi-TF data."""
        scores = ValidationScores(
            backtesting_score=0.80,
            walkforward_score=0.75,
            live_score=0.70,
            multi_tf_scores={},
        )

        result = self.validator.validate("AAPL", "BULLISH", scores)

        assert result.consensus_direction == "UNKNOWN"
        assert "No multi-TF data" in result.conflict_explanation

    def test_consensus_alignment_bonus(self):
        """Test that consensus alignment gives confidence bonus."""
        scores_aligned = ValidationScores(
            backtesting_score=0.80,
            walkforward_score=0.75,
            live_score=0.75,
            multi_tf_scores={"D1": 0.50, "W1": 0.60},
        )

        scores_misaligned = ValidationScores(
            backtesting_score=0.80,
            walkforward_score=0.75,
            live_score=0.75,
            multi_tf_scores={"D1": -0.50, "W1": -0.60},
        )

        result_aligned = self.validator.validate("AAPL", "BULLISH", scores_aligned)
        result_misaligned = self.validator.validate("AAPL", "BULLISH", scores_misaligned)

        # Aligned should have higher confidence
        assert result_aligned.unified_confidence > result_misaligned.unified_confidence


class TestRetrainingTrigger:
    """Test retraining trigger logic."""

    def setup_method(self):
        # Set last retraining to 10 days ago
        self.validator = UnifiedValidator(last_retraining_date=datetime.now() - timedelta(days=10))

    def test_no_retrain_within_schedule(self):
        """Test no retraining trigger when within schedule."""
        scores = ValidationScores(
            backtesting_score=0.80,
            walkforward_score=0.75,
            live_score=0.70,
            multi_tf_scores={},
        )

        result = self.validator.validate("AAPL", "BULLISH", scores)

        assert result.retraining_trigger is False

    def test_retrain_on_critical_drift(self):
        """Test retraining triggered on critical drift."""
        scores = ValidationScores(
            backtesting_score=0.90,
            walkforward_score=0.50,
            live_score=0.10,  # >75% drift
            multi_tf_scores={},
        )

        result = self.validator.validate("AAPL", "BULLISH", scores)

        assert result.retraining_trigger is True
        assert "Critical drift" in result.retraining_reason

    def test_retrain_on_schedule(self):
        """Test retraining triggered on 30-day schedule."""
        validator = UnifiedValidator(last_retraining_date=datetime.now() - timedelta(days=35))

        scores = ValidationScores(
            backtesting_score=0.80,
            walkforward_score=0.75,
            live_score=0.70,  # No significant drift
            multi_tf_scores={},
        )

        result = validator.validate("AAPL", "BULLISH", scores)

        assert result.retraining_trigger is True
        assert "30-day" in result.retraining_reason or "Scheduled" in result.retraining_reason


class TestUnifiedPredictionOutput:
    """Test the UnifiedPrediction output format."""

    def setup_method(self):
        self.validator = UnifiedValidator()

    def test_to_dict_serialization(self):
        """Test that to_dict produces valid serializable output."""
        scores = ValidationScores(
            backtesting_score=0.80,
            walkforward_score=0.75,
            live_score=0.70,
            multi_tf_scores={"D1": 0.50},
        )

        result = self.validator.validate("AAPL", "BULLISH", scores)
        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict["symbol"] == "AAPL"
        assert result_dict["direction"] == "BULLISH"
        assert 0 <= result_dict["unified_confidence"] <= 1
        assert isinstance(result_dict["timestamp"], str)

    def test_status_emoji(self):
        """Test status emoji based on confidence levels."""
        scores_high = ValidationScores(
            backtesting_score=0.95,
            walkforward_score=0.90,
            live_score=0.90,
            multi_tf_scores={"D1": 0.5},
        )

        scores_low = ValidationScores(
            backtesting_score=0.40,
            walkforward_score=0.35,
            live_score=0.30,
            multi_tf_scores={},
        )

        result_high = self.validator.validate("AAPL", "BULLISH", scores_high)
        result_low = self.validator.validate("AAPL", "BULLISH", scores_low)

        # High confidence should be green or yellow
        assert result_high.get_status_emoji() in ("🟢", "🟡")
        # Low confidence should be orange or red
        assert result_low.get_status_emoji() in ("🟠", "🔴")


class TestConvenienceFunction:
    """Test the validate_prediction convenience function."""

    def test_basic_usage(self):
        """Test basic convenience function usage."""
        result = validate_prediction(
            symbol="AAPL",
            direction="BULLISH",
            backtesting_score=0.80,
            walkforward_score=0.75,
            live_score=0.70,
        )

        assert isinstance(result, UnifiedPrediction)
        assert result.symbol == "AAPL"
        assert result.direction == "BULLISH"

    def test_with_multi_tf(self):
        """Test convenience function with multi-TF scores."""
        result = validate_prediction(
            symbol="NVDA",
            direction="BEARISH",
            backtesting_score=0.85,
            walkforward_score=0.80,
            live_score=0.75,
            multi_tf_scores={"D1": -0.50, "W1": -0.55},
        )

        assert result.consensus_direction == "BEARISH"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def setup_method(self):
        self.validator = UnifiedValidator()

    def test_scores_at_boundaries(self):
        """Test with scores at 0 and 1 boundaries."""
        scores = ValidationScores(
            backtesting_score=1.0,
            walkforward_score=0.0,
            live_score=0.5,
            multi_tf_scores={},
        )

        result = self.validator.validate("AAPL", "BULLISH", scores)

        # Should not crash and should produce valid output
        assert 0 <= result.unified_confidence <= 1

    def test_negative_multi_tf_scores(self):
        """Test with strongly negative multi-TF scores."""
        scores = ValidationScores(
            backtesting_score=0.80,
            walkforward_score=0.75,
            live_score=0.70,
            multi_tf_scores={
                "M15": -0.99,
                "H1": -0.98,
                "D1": -0.95,
                "W1": -0.90,
            },
        )

        result = self.validator.validate("AAPL", "BULLISH", scores)

        # Consensus should be BEARISH
        assert result.consensus_direction == "BEARISH"
        # Conflict with BULLISH prediction should reduce confidence
        assert result.unified_confidence < 0.80

    def test_unknown_timeframes(self):
        """Test with non-standard timeframe keys."""
        scores = ValidationScores(
            backtesting_score=0.80,
            walkforward_score=0.75,
            live_score=0.70,
            multi_tf_scores={
                "5m": 0.40,  # Non-standard
                "2H": 0.45,  # Non-standard
            },
        )

        result = self.validator.validate("AAPL", "BULLISH", scores)

        # Should not crash, should use default weight for unknown TFs
        assert isinstance(result, UnifiedPrediction)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
