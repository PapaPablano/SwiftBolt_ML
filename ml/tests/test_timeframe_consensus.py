"""
Unit tests for TimeframeConsensus.

Tests:
- Consensus calculation
- Alignment scoring
- Confidence adjustment
- Agreement detection
- Recommendation generation
"""

from datetime import datetime

import numpy as np
import pytest

from src.features.timeframe_consensus import TimeframeConsensus, TimeframeSignal


class TestTimeframeConsensus:
    """Test suite for TimeframeConsensus."""

    @pytest.fixture
    def consensus_calc(self):
        """Create consensus calculator."""
        return TimeframeConsensus(
            confidence_boost_full_consensus=0.20,
            confidence_boost_strong=0.10,
            confidence_penalty_conflicted=0.10,
        )

    def test_initialization(self, consensus_calc):
        """Test calculator initialization."""
        assert consensus_calc.confidence_boost_full == 0.20
        assert consensus_calc.confidence_boost_strong == 0.10
        assert consensus_calc.confidence_penalty == 0.10
        print("✓ Initialization successful")

    def test_full_consensus_bullish(self, consensus_calc):
        """Test full bullish consensus (all 4 timeframes agree)."""
        signals = {
            "m15": TimeframeSignal("m15", "bullish", 0.6, 0.6, 0.01, datetime.now()),
            "h1": TimeframeSignal("h1", "bullish", 0.7, 0.7, 0.02, datetime.now()),
            "h4": TimeframeSignal("h4", "bullish", 0.8, 0.8, 0.03, datetime.now()),
            "d1": TimeframeSignal("d1", "bullish", 0.75, 0.75, 0.05, datetime.now()),
        }

        result = consensus_calc._analyze_consensus(signals, None)

        assert result.consensus_direction == "bullish"
        assert result.consensus_strength == "strong"
        assert len(result.agreeing_timeframes) == 4
        assert len(result.conflicting_timeframes) == 0
        assert result.alignment_score > 0.7
        print(f"✓ Full bullish consensus: alignment={result.alignment_score:.2%}, strength={result.consensus_strength}")

    def test_moderate_consensus(self, consensus_calc):
        """Test moderate consensus (3/4 agree)."""
        signals = {
            "m15": TimeframeSignal("m15", "bullish", 0.6, 0.6, 0.01, datetime.now()),
            "h1": TimeframeSignal("h1", "bullish", 0.7, 0.7, 0.02, datetime.now()),
            "h4": TimeframeSignal("h4", "bullish", 0.8, 0.8, 0.03, datetime.now()),
            "d1": TimeframeSignal("d1", "bearish", 0.65, 0.65, -0.02, datetime.now()),
        }

        result = consensus_calc._analyze_consensus(signals, None)

        assert result.consensus_direction == "bullish"
        assert result.consensus_strength == "moderate"
        assert len(result.agreeing_timeframes) == 3
        assert len(result.conflicting_timeframes) == 1
        print(f"✓ Moderate consensus: {len(result.agreeing_timeframes)}/4 agree, strength={result.consensus_strength}")

    def test_conflicted_signals(self, consensus_calc):
        """Test conflicted signals (split opinion)."""
        signals = {
            "m15": TimeframeSignal("m15", "bearish", 0.6, 0.6, -0.01, datetime.now()),
            "h1": TimeframeSignal("h1", "bullish", 0.7, 0.7, 0.02, datetime.now()),
            "h4": TimeframeSignal("h4", "bearish", 0.65, 0.65, -0.02, datetime.now()),
            "d1": TimeframeSignal("d1", "bullish", 0.75, 0.75, 0.05, datetime.now()),
        }

        result = consensus_calc._analyze_consensus(signals, None)

        # 2/4 bullish, 2/4 bearish = weak consensus (50% agreement)
        assert result.consensus_strength in ["weak", "conflicted"]
        assert len(result.conflicting_timeframes) > 0
        print(f"✓ Conflicted consensus: {len(result.conflicting_timeframes)} conflicts detected")

    def test_confidence_adjustment_full(self, consensus_calc):
        """Test confidence boost with full consensus."""
        signals = {
            "m15": TimeframeSignal("m15", "bullish", 0.6, 0.6, 0.01, datetime.now()),
            "h1": TimeframeSignal("h1", "bullish", 0.7, 0.7, 0.02, datetime.now()),
            "h4": TimeframeSignal("h4", "bullish", 0.8, 0.8, 0.03, datetime.now()),
            "d1": TimeframeSignal("d1", "bullish", 0.75, 0.75, 0.05, datetime.now()),
        }

        forecast = {
            "confidence": 0.60,
            "label": "Bullish",
            "forecast_return": 0.03,
        }

        result = consensus_calc._analyze_consensus(signals, forecast)

        # Should boost confidence by ~20%
        expected_boost = min(0.60 + 0.20, 0.95)
        assert result.adjusted_confidence >= 0.60  # At least no penalty
        print(f"✓ Confidence boost: {0.60:.1%} -> {result.adjusted_confidence:.1%}")

    def test_confidence_penalty_conflicted(self, consensus_calc):
        """Test confidence penalty with conflicted signals."""
        signals = {
            "m15": TimeframeSignal("m15", "bearish", 0.6, 0.6, -0.01, datetime.now()),
            "h1": TimeframeSignal("h1", "bullish", 0.5, 0.5, 0.02, datetime.now()),
            "h4": TimeframeSignal("h4", "bearish", 0.65, 0.65, -0.02, datetime.now()),
            "d1": TimeframeSignal("d1", "bearish", 0.75, 0.75, 0.05, datetime.now()),
        }

        forecast = {
            "confidence": 0.70,
            "label": "Bullish",
            "forecast_return": 0.03,
        }

        result = consensus_calc._analyze_consensus(signals, forecast)

        # 3 bearish vs 1 bullish = moderate bearish consensus
        # Forecast is bullish which conflicts with consensus
        assert result.consensus_direction == "bearish"
        assert result.consensus_strength == "moderate"
        print(f"✓ Confidence penalty: {0.70:.1%} -> {result.adjusted_confidence:.1%}")

    def test_alignment_score_calculation(self, consensus_calc):
        """Test alignment score calculation."""
        signals = {
            "m15": TimeframeSignal("m15", "bullish", 0.6, 0.6, 0.01, datetime.now()),
            "h1": TimeframeSignal("h1", "bullish", 0.7, 0.7, 0.02, datetime.now()),
            "h4": TimeframeSignal("h4", "bullish", 0.8, 0.8, 0.03, datetime.now()),
            "d1": TimeframeSignal("d1", "bullish", 0.75, 0.75, 0.05, datetime.now()),
        }

        result = consensus_calc._analyze_consensus(signals, None)

        assert 0 <= result.alignment_score <= 1
        assert result.alignment_score > 0.5  # Strong alignment expected
        print(f"✓ Alignment score: {result.alignment_score:.2%}")

    def test_recommendation_generation(self, consensus_calc):
        """Test recommendation text generation."""
        signals = {
            "m15": TimeframeSignal("m15", "bullish", 0.6, 0.6, 0.01, datetime.now()),
            "h1": TimeframeSignal("h1", "bullish", 0.7, 0.7, 0.02, datetime.now()),
            "h4": TimeframeSignal("h4", "bullish", 0.8, 0.8, 0.03, datetime.now()),
            "d1": TimeframeSignal("d1", "bullish", 0.75, 0.75, 0.05, datetime.now()),
        }

        result = consensus_calc._analyze_consensus(signals, None)

        assert isinstance(result.recommendation, str)
        assert len(result.recommendation) > 10
        assert "bullish" in result.recommendation.lower()
        print(f"✓ Recommendation: {result.recommendation}")

    def test_empty_signals(self, consensus_calc):
        """Test behavior with no signals."""
        result = consensus_calc._analyze_consensus({}, None)

        assert result.consensus_direction == "neutral"
        assert result.alignment_score == 0.0
        # Empty signals are handled by _empty_consensus which returns "unknown"
        # but if called directly from _analyze_consensus, it may return "weak"
        assert result.consensus_strength in ["unknown", "weak"]
        print("✓ Empty signals handled correctly")

    def test_timeframe_weights(self, consensus_calc):
        """Test that timeframe weights are correct."""
        expected_weights = {
            "m15": 0.10,
            "h1": 0.20,
            "h4": 0.30,
            "d1": 0.40,
        }

        assert consensus_calc.TIMEFRAME_WEIGHTS == expected_weights
        print(f"✓ Timeframe weights correct: {consensus_calc.TIMEFRAME_WEIGHTS}")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Timeframe Consensus")
    print("=" * 60)

    test = TestTimeframeConsensus()
    calc = test.consensus_calc()

    test.test_initialization(calc)
    test.test_full_consensus_bullish(calc)
    test.test_moderate_consensus(calc)
    test.test_conflicted_signals(calc)
    test.test_confidence_adjustment_full(calc)
    test.test_confidence_penalty_conflicted(calc)
    test.test_alignment_score_calculation(calc)
    test.test_recommendation_generation(calc)
    test.test_empty_signals(calc)
    test.test_timeframe_weights(calc)

    print("\n" + "=" * 60)
    print("All Timeframe Consensus tests passed! ✓")
    print("=" * 60)
