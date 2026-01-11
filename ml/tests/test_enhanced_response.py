"""Tests for Enhanced Response API builder."""

import pandas as pd
import pytest
import numpy as np

from src.api.enhanced_response import (
    build_enhanced_response,
    build_minimal_response,
    _build_multi_timeframe_section,
    _build_explanation_section,
    _build_data_quality_section,
)


class TestBuildEnhancedResponse:
    """Tests for the main build_enhanced_response function."""

    @pytest.fixture
    def sample_features_df(self):
        """Create sample features DataFrame."""
        return pd.DataFrame(
            {
                "ts": pd.date_range("2024-01-01", periods=10, freq="D"),
                "close": [100 + i for i in range(10)],
                "rsi_14_d1": [45, 48, 52, 55, 58, 62, 65, 68, 70, 72],
                "rsi_14_h1": [50, 52, 54, 56, 58, 60, 62, 64, 66, 68],
                "macd_d1": [-0.5, -0.3, 0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4],
                "adx_d1": [20, 22, 24, 26, 28, 30, 32, 34, 36, 38],
                "plus_di_d1": [25, 26, 27, 28, 29, 30, 31, 32, 33, 34],
                "minus_di_d1": [20, 19, 18, 17, 16, 15, 14, 13, 12, 11],
            }
        )

    def test_build_enhanced_response_structure(self, sample_features_df):
        """Test that response has all required sections."""
        response = build_enhanced_response(
            symbol="AAPL",
            features_df=sample_features_df,
            prediction="bullish",
            confidence=0.78,
            price_target=150.25,
        )

        assert "symbol" in response
        assert "timestamp" in response
        assert "prediction" in response
        assert "confidence" in response
        assert "price_target" in response
        assert "multi_timeframe" in response
        assert "explanation" in response
        assert "data_quality" in response

    def test_build_enhanced_response_values(self, sample_features_df):
        """Test that response values are correct."""
        response = build_enhanced_response(
            symbol="AAPL",
            features_df=sample_features_df,
            prediction="bullish",
            confidence=0.78,
            price_target=150.25,
        )

        assert response["symbol"] == "AAPL"
        assert response["prediction"] == "bullish"
        assert response["confidence"] == 0.78
        assert response["price_target"] == 150.25

    def test_build_enhanced_response_empty_df(self):
        """Test handling of empty DataFrame."""
        response = build_enhanced_response(
            symbol="AAPL",
            features_df=pd.DataFrame(),
            prediction="neutral",
            confidence=0.5,
        )

        assert response["symbol"] == "AAPL"
        assert response["prediction"] == "neutral"
        # Should handle gracefully, not crash


class TestMultiTimeframeSection:
    """Tests for multi-timeframe section builder."""

    @pytest.fixture
    def sample_features_df(self):
        """Create sample features DataFrame with multi-TF data."""
        return pd.DataFrame(
            {
                "ts": pd.date_range("2024-01-01", periods=5, freq="D"),
                "rsi_14_m15": [55, 58, 60, 62, 65],
                "rsi_14_h1": [52, 55, 58, 60, 63],
                "rsi_14_d1": [48, 50, 52, 55, 58],
                "rsi_14_w1": [45, 47, 49, 51, 53],
                "macd_d1": [0.1, 0.2, 0.3, 0.4, 0.5],
                "adx_d1": [25, 26, 27, 28, 29],
                "plus_di_d1": [30, 31, 32, 33, 34],
                "minus_di_d1": [20, 19, 18, 17, 16],
            }
        )

    def test_multi_timeframe_section_structure(self, sample_features_df):
        """Test multi-timeframe section has required fields."""
        result = _build_multi_timeframe_section(
            sample_features_df,
            timeframes=["m15", "h1", "d1", "w1"],
        )

        assert "signal" in result
        assert "consensus_confidence" in result
        assert "bullish_count" in result
        assert "bearish_count" in result
        assert "timeframe_breakdown" in result

    def test_multi_timeframe_breakdown(self, sample_features_df):
        """Test timeframe breakdown contains expected data."""
        result = _build_multi_timeframe_section(
            sample_features_df,
            timeframes=["m15", "h1", "d1", "w1"],
        )

        breakdown = result["timeframe_breakdown"]
        assert len(breakdown) > 0

        for tf_data in breakdown:
            assert "timeframe" in tf_data
            assert "signal" in tf_data
            assert "rsi" in tf_data


class TestExplanationSection:
    """Tests for explanation section builder."""

    @pytest.fixture
    def sample_features_df(self):
        """Create sample features DataFrame."""
        return pd.DataFrame(
            {
                "ts": pd.date_range("2024-01-01", periods=3, freq="D"),
                "rsi_14_d1": [65, 68, 72],
                "macd_d1": [0.5, 0.8, 1.2],
                "adx_d1": [28, 30, 32],
            }
        )

    def test_explanation_section_structure(self, sample_features_df):
        """Test explanation section has required fields."""
        result = _build_explanation_section(
            symbol="AAPL",
            features_df=sample_features_df,
            prediction="bullish",
            confidence=0.75,
            price_target=150.0,
            feature_importance=None,
        )

        assert "summary" in result
        assert "top_features" in result
        assert "signal_breakdown" in result
        assert "risk_factors" in result
        assert "recommendation" in result

    def test_explanation_has_summary(self, sample_features_df):
        """Test that summary is generated."""
        result = _build_explanation_section(
            symbol="AAPL",
            features_df=sample_features_df,
            prediction="bullish",
            confidence=0.75,
            price_target=None,
            feature_importance=None,
        )

        assert len(result["summary"]) > 0
        assert "AAPL" in result["summary"]


class TestDataQualitySection:
    """Tests for data quality section builder."""

    @pytest.fixture
    def clean_df(self):
        """Create clean DataFrame with no NaNs."""
        return pd.DataFrame(
            {
                "a": [1.0, 2.0, 3.0, 4.0, 5.0],
                "b": [1.0, 2.0, 3.0, 4.0, 5.0],
            }
        )

    @pytest.fixture
    def dirty_df(self):
        """Create DataFrame with NaNs."""
        return pd.DataFrame(
            {
                "a": [1.0, np.nan, 3.0, np.nan, 5.0],
                "b": [1.0, 2.0, np.nan, 4.0, 5.0],
            }
        )

    def test_data_quality_clean(self, clean_df):
        """Test data quality for clean DataFrame."""
        result = _build_data_quality_section(clean_df)

        assert result["health_score"] == 1.0
        assert result["total_nans"] == 0
        assert result["is_clean"] == True  # noqa: E712
        assert len(result["warnings"]) == 0

    def test_data_quality_dirty(self, dirty_df):
        """Test data quality for dirty DataFrame."""
        result = _build_data_quality_section(dirty_df)

        assert result["health_score"] < 1.0
        assert result["total_nans"] == 3
        assert result["is_clean"] == False  # noqa: E712
        assert result["columns_with_issues"] == 2

    def test_data_quality_structure(self, clean_df):
        """Test data quality section has required fields."""
        result = _build_data_quality_section(clean_df)

        assert "health_score" in result
        assert "total_rows" in result
        assert "total_columns" in result
        assert "total_nans" in result
        assert "severity" in result
        assert "warnings" in result
        assert "is_clean" in result


class TestMinimalResponse:
    """Tests for minimal response builder."""

    def test_minimal_response_structure(self):
        """Test minimal response has required fields."""
        response = build_minimal_response(
            symbol="AAPL",
            prediction="bullish",
            confidence=0.78,
            price_target=150.25,
        )

        assert response["symbol"] == "AAPL"
        assert response["prediction"] == "bullish"
        assert response["confidence"] == 0.78
        assert response["price_target"] == 150.25
        assert "timestamp" in response

    def test_minimal_response_no_extras(self):
        """Test minimal response doesn't have enhanced sections."""
        response = build_minimal_response(
            symbol="AAPL",
            prediction="bullish",
            confidence=0.78,
        )

        assert "multi_timeframe" not in response
        assert "explanation" not in response
        assert "data_quality" not in response
