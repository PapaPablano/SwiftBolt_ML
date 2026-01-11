"""Unit tests for Enhanced Options Ranker (Phase 6)."""

import sys
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

# Mock the settings before importing (required for CI without env vars)
mock_settings = MagicMock()
mock_settings.min_bars_for_training = 50
sys.modules["config.settings"] = MagicMock()
sys.modules["config.settings"].settings = mock_settings

from src.models.enhanced_options_ranker import EnhancedOptionsRanker  # noqa: E402


@pytest.fixture
def sample_ohlc_df():
    """Create sample OHLC data for testing."""
    np.random.seed(42)
    n = 200  # Need enough data for SuperTrend AI

    # Generate trending price data
    base_price = 100.0
    trend = np.linspace(0, 0.3, n)  # 30% uptrend
    noise = np.random.randn(n) * 0.01
    prices = base_price * (1 + trend + np.cumsum(noise))

    df = pd.DataFrame(
        {
            "ts": pd.date_range("2024-01-01", periods=n, freq="D"),
            "open": prices * (1 + np.random.randn(n) * 0.005),
            "high": prices * (1 + np.abs(np.random.randn(n) * 0.01)),
            "low": prices * (1 - np.abs(np.random.randn(n) * 0.01)),
            "close": prices,
            "volume": np.random.randint(1000000, 10000000, n).astype(float),
        }
    )

    # Ensure high >= close >= low
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)

    return df


@pytest.fixture
def sample_options_df():
    """Create sample options chain data for testing."""
    # Create a mix of calls and puts at various strikes
    underlying_price = 130.0  # Matches end of trending OHLC data
    strikes = [120, 125, 130, 135, 140]

    contracts = []
    for strike in strikes:
        # Call option
        moneyness = (strike - underlying_price) / underlying_price
        contracts.append(
            {
                "contract_symbol": f"AAPL240315C{strike:05d}000",
                "strike": float(strike),
                "expiration": 1710460800,  # March 15, 2024
                "side": "call",
                "bid": max(0.1, underlying_price - strike + 2),
                "ask": max(0.2, underlying_price - strike + 3),
                "mark": max(0.15, underlying_price - strike + 2.5),
                "last_price": max(0.15, underlying_price - strike + 2.5),
                "volume": np.random.randint(100, 5000),
                "openInterest": np.random.randint(1000, 50000),
                "impliedVolatility": 0.25 + abs(moneyness) * 0.1,
                "delta": max(0.1, min(0.9, 0.5 - moneyness)),
                "gamma": 0.05,
                "theta": -0.05,
                "vega": 0.10,
                "rho": 0.02,
            }
        )

        # Put option
        contracts.append(
            {
                "contract_symbol": f"AAPL240315P{strike:05d}000",
                "strike": float(strike),
                "expiration": 1710460800,
                "side": "put",
                "bid": max(0.1, strike - underlying_price + 2),
                "ask": max(0.2, strike - underlying_price + 3),
                "mark": max(0.15, strike - underlying_price + 2.5),
                "last_price": max(0.15, strike - underlying_price + 2.5),
                "volume": np.random.randint(100, 5000),
                "openInterest": np.random.randint(1000, 50000),
                "impliedVolatility": 0.25 + abs(moneyness) * 0.1,
                "delta": -max(0.1, min(0.9, 0.5 + moneyness)),
                "gamma": 0.05,
                "theta": -0.05,
                "vega": 0.10,
                "rho": -0.02,
            }
        )

    return pd.DataFrame(contracts)


class TestEnhancedOptionsRankerInit:
    """Test EnhancedOptionsRanker initialization."""

    def test_initialization(self):
        """Test default initialization."""
        ranker = EnhancedOptionsRanker()

        assert ranker.weights is not None
        assert "moneyness" in ranker.weights
        assert "supertrend" in ranker.weights
        assert "trend_strength" in ranker.weights

    def test_weights_sum(self):
        """Test that weights sum to approximately 1.0."""
        ranker = EnhancedOptionsRanker()
        total_weight = sum(ranker.weights.values())
        assert 0.95 <= total_weight <= 1.05


class TestRankOptionsWithIndicators:
    """Test the main rank_options_with_indicators method."""

    def test_rank_options_with_indicators(self, sample_ohlc_df, sample_options_df):
        """Test full ranking with technical indicators."""
        ranker = EnhancedOptionsRanker()
        underlying_price = sample_ohlc_df["close"].iloc[-1]

        ranked_df = ranker.rank_options_with_indicators(
            sample_options_df,
            sample_ohlc_df,
            underlying_price,
            historical_vol=0.25,
        )

        # Check result structure
        assert "ml_score" in ranked_df.columns
        assert "trend" in ranked_df.columns
        assert "trend_strength" in ranked_df.columns
        assert "supertrend_factor" in ranked_df.columns

        # Check scores are in valid range
        assert (ranked_df["ml_score"] >= 0).all()
        assert (ranked_df["ml_score"] <= 1).all()

        # Check sorted by score descending
        scores = ranked_df["ml_score"].tolist()
        assert scores == sorted(scores, reverse=True)

    def test_rank_options_empty_options(self, sample_ohlc_df):
        """Test handling of empty options DataFrame."""
        ranker = EnhancedOptionsRanker()
        empty_df = pd.DataFrame()

        result = ranker.rank_options_with_indicators(
            empty_df,
            sample_ohlc_df,
            100.0,
        )

        assert result.empty

    def test_rank_options_insufficient_ohlc(self, sample_options_df):
        """Test fallback when OHLC data is insufficient."""
        ranker = EnhancedOptionsRanker()

        # Create minimal OHLC data (less than 50 bars)
        small_ohlc = pd.DataFrame(
            {
                "ts": pd.date_range("2024-01-01", periods=10, freq="D"),
                "open": [100.0] * 10,
                "high": [101.0] * 10,
                "low": [99.0] * 10,
                "close": [100.0] * 10,
                "volume": [1000000.0] * 10,
            }
        )

        # Should fall back to basic ranking
        result = ranker.rank_options_with_indicators(
            sample_options_df,
            small_ohlc,
            100.0,
        )

        assert "ml_score" in result.columns
        assert len(result) == len(sample_options_df)


class TestAnalyzeUnderlying:
    """Test the analyze_underlying method."""

    def test_analyze_underlying(self, sample_ohlc_df):
        """Test underlying analysis."""
        ranker = EnhancedOptionsRanker()
        analysis = ranker.analyze_underlying(sample_ohlc_df)

        # Check result structure
        assert "trend" in analysis
        assert "signal_strength" in analysis
        assert "supertrend_factor" in analysis
        assert "supertrend_performance" in analysis
        assert "confidence" in analysis
        assert "indicators" in analysis

        # Check trend is valid
        assert analysis["trend"] in ["bullish", "bearish", "neutral"]

        # Check signal strength is in range
        assert 0 <= analysis["signal_strength"] <= 10

        # Check indicators dict has expected keys
        indicators = analysis["indicators"]
        assert "rsi_14" in indicators
        assert "adx" in indicators
        assert "macd_hist" in indicators

    def test_analyze_underlying_insufficient_data(self):
        """Test analysis with insufficient data."""
        ranker = EnhancedOptionsRanker()

        small_df = pd.DataFrame(
            {
                "ts": pd.date_range("2024-01-01", periods=10, freq="D"),
                "open": [100.0] * 10,
                "high": [101.0] * 10,
                "low": [99.0] * 10,
                "close": [100.0] * 10,
                "volume": [1000000.0] * 10,
            }
        )

        analysis = ranker.analyze_underlying(small_df)

        # Should return neutral defaults
        assert analysis["trend"] == "neutral"
        assert analysis["confidence"] == 0.0


class TestRankOptionsWithTrend:
    """Test the rank_options_with_trend method."""

    def test_rank_with_bullish_trend(self, sample_options_df):
        """Test ranking with bullish trend analysis."""
        ranker = EnhancedOptionsRanker()

        trend_analysis = {
            "trend": "bullish",
            "signal_strength": 8.0,
            "supertrend_factor": 2.5,
            "supertrend_performance": 0.7,
        }

        ranked_df = ranker.rank_options_with_trend(
            sample_options_df,
            underlying_price=130.0,
            trend_analysis=trend_analysis,
            historical_vol=0.25,
        )

        # Calls should generally score higher in bullish trend
        calls = ranked_df[ranked_df["side"] == "call"]
        puts = ranked_df[ranked_df["side"] == "put"]

        if not calls.empty and not puts.empty:
            avg_call_score = calls["ml_score"].mean()
            avg_put_score = puts["ml_score"].mean()
            # In strong bullish trend, calls should score higher on average
            assert avg_call_score >= avg_put_score * 0.8

    def test_rank_with_bearish_trend(self, sample_options_df):
        """Test ranking with bearish trend analysis."""
        ranker = EnhancedOptionsRanker()

        trend_analysis = {
            "trend": "bearish",
            "signal_strength": 8.0,
            "supertrend_factor": 2.5,
            "supertrend_performance": 0.7,
        }

        ranked_df = ranker.rank_options_with_trend(
            sample_options_df,
            underlying_price=130.0,
            trend_analysis=trend_analysis,
            historical_vol=0.25,
        )

        # Puts should generally score higher in bearish trend
        calls = ranked_df[ranked_df["side"] == "call"]
        puts = ranked_df[ranked_df["side"] == "put"]

        if not calls.empty and not puts.empty:
            avg_call_score = calls["ml_score"].mean()
            avg_put_score = puts["ml_score"].mean()
            # In strong bearish trend, puts should score higher on average
            assert avg_put_score >= avg_call_score * 0.8


class TestGetTopRecommendations:
    """Test the get_top_recommendations method."""

    def test_get_top_recommendations(self, sample_options_df):
        """Test getting top recommendations."""
        ranker = EnhancedOptionsRanker()

        trend_analysis = {
            "trend": "neutral",
            "signal_strength": 5.0,
            "supertrend_factor": 3.0,
            "supertrend_performance": 0.5,
        }

        ranked_df = ranker.rank_options_with_trend(
            sample_options_df,
            underlying_price=130.0,
            trend_analysis=trend_analysis,
        )

        recs = ranker.get_top_recommendations(ranked_df, n_calls=2, n_puts=2)

        assert "calls" in recs
        assert "puts" in recs
        assert "top_call" in recs
        assert "top_put" in recs

        assert len(recs["calls"]) <= 2
        assert len(recs["puts"]) <= 2


class TestGenerateRankingSummary:
    """Test the generate_ranking_summary method."""

    def test_generate_summary(self, sample_options_df):
        """Test summary generation."""
        ranker = EnhancedOptionsRanker()

        trend_analysis = {
            "trend": "bullish",
            "signal_strength": 7.5,
            "supertrend_factor": 2.8,
            "supertrend_performance": 0.65,
        }

        ranked_df = ranker.rank_options_with_trend(
            sample_options_df,
            underlying_price=130.0,
            trend_analysis=trend_analysis,
        )

        summary = ranker.generate_ranking_summary(ranked_df, trend_analysis)

        assert "OPTIONS RANKING SUMMARY" in summary
        assert "BULLISH" in summary
        assert "7.5" in summary
        assert "TOP CALL" in summary
        assert "TOP PUT" in summary


class TestIntegration:
    """Integration tests for EnhancedOptionsRanker."""

    def test_full_pipeline(self, sample_ohlc_df, sample_options_df):
        """Test full pipeline: OHLC -> indicators -> ranking."""
        ranker = EnhancedOptionsRanker()
        underlying_price = sample_ohlc_df["close"].iloc[-1]

        # Step 1: Analyze underlying
        analysis = ranker.analyze_underlying(sample_ohlc_df)

        # Step 2: Rank options with indicators
        ranked_df = ranker.rank_options_with_indicators(
            sample_options_df,
            sample_ohlc_df,
            underlying_price,
        )

        # Step 3: Get recommendations
        recs = ranker.get_top_recommendations(ranked_df)

        # Step 4: Generate summary
        summary = ranker.generate_ranking_summary(ranked_df, analysis)

        # Verify all steps completed successfully
        assert analysis["trend"] in ["bullish", "bearish", "neutral"]
        assert len(ranked_df) == len(sample_options_df)
        assert recs["top_call"] is not None or recs["top_put"] is not None
        assert len(summary) > 0

    def test_consistency_across_runs(self, sample_ohlc_df, sample_options_df):
        """Test that results are consistent with same data."""
        ranker1 = EnhancedOptionsRanker()
        ranker2 = EnhancedOptionsRanker()

        underlying_price = sample_ohlc_df["close"].iloc[-1]

        result1 = ranker1.rank_options_with_indicators(
            sample_options_df,
            sample_ohlc_df,
            underlying_price,
        )

        result2 = ranker2.rank_options_with_indicators(
            sample_options_df,
            sample_ohlc_df,
            underlying_price,
        )

        # Scores should be identical
        pd.testing.assert_series_equal(
            result1["ml_score"].reset_index(drop=True),
            result2["ml_score"].reset_index(drop=True),
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
