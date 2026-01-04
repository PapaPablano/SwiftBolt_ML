"""Unit tests for Forecast-Options Integration."""

import numpy as np
import pandas as pd
import pytest

from src.models.forecast_options_integration import (
    ForecastSignal,
    ForecastOptionsIntegration,
    create_integration_from_manager,
)


@pytest.fixture
def bullish_forecast():
    """Create a bullish forecast dict."""
    return {
        "label": "Bullish",
        "confidence": 0.75,
        "agreement": 0.8,
        "probabilities": {
            "bullish": 0.75,
            "neutral": 0.15,
            "bearish": 0.10,
        },
        "forecast_return": 0.02,
        "forecast_volatility": 0.018,
        "n_models": 4,
        "horizon": "1D",
    }


@pytest.fixture
def bearish_forecast():
    """Create a bearish forecast dict."""
    return {
        "label": "Bearish",
        "confidence": 0.70,
        "agreement": 0.75,
        "probabilities": {
            "bullish": 0.15,
            "neutral": 0.15,
            "bearish": 0.70,
        },
        "forecast_return": -0.015,
        "forecast_volatility": 0.02,
        "n_models": 5,
        "horizon": "1D",
    }


@pytest.fixture
def neutral_forecast():
    """Create a neutral/uncertain forecast dict."""
    return {
        "label": "Neutral",
        "confidence": 0.45,
        "agreement": 0.5,
        "probabilities": {
            "bullish": 0.35,
            "neutral": 0.35,
            "bearish": 0.30,
        },
        "n_models": 3,
    }


@pytest.fixture
def sample_options_df():
    """Create sample options DataFrame."""
    return pd.DataFrame({
        "strike": [95, 100, 105, 110, 95, 100, 105, 110],
        "side": ["call", "call", "call", "call", "put", "put", "put", "put"],
        "expiration": ["2024-01-19"] * 8,
        "bid": [5.5, 2.5, 0.8, 0.2, 0.2, 0.8, 2.5, 5.5],
        "ask": [5.7, 2.7, 1.0, 0.3, 0.3, 1.0, 2.7, 5.7],
    })


@pytest.fixture
def sample_ohlc_df():
    """Create sample OHLC DataFrame."""
    np.random.seed(42)
    n = 50
    prices = 100 * np.exp(np.cumsum(np.random.randn(n) * 0.01))

    return pd.DataFrame({
        "ts": pd.date_range("2024-01-01", periods=n, freq="D"),
        "open": prices * 0.998,
        "high": prices * 1.01,
        "low": prices * 0.99,
        "close": prices,
        "volume": np.random.randint(1e6, 1e7, n).astype(float),
    })


class TestForecastSignalDataclass:
    """Test ForecastSignal dataclass."""

    def test_create_signal(self):
        """Test creating a ForecastSignal."""
        signal = ForecastSignal(
            trend="bullish",
            signal_strength=7.5,
            supertrend_factor=3.0,
            supertrend_performance=0.6,
            confidence=0.75,
            agreement=0.8,
            uncertainty=0.25,
        )

        assert signal.trend == "bullish"
        assert signal.signal_strength == 7.5
        assert signal.confidence == 0.75

    def test_signal_defaults(self):
        """Test ForecastSignal defaults."""
        signal = ForecastSignal(
            trend="neutral",
            signal_strength=5.0,
            supertrend_factor=3.0,
            supertrend_performance=0.5,
            confidence=0.5,
            agreement=0.5,
            uncertainty=0.5,
        )

        assert signal.forecast_return is None
        assert signal.forecast_volatility is None
        assert signal.horizon == "1D"
        assert signal.n_models == 0


class TestIntegrationInit:
    """Test ForecastOptionsIntegration initialization."""

    def test_default_initialization(self):
        """Test default initialization."""
        integration = ForecastOptionsIntegration()

        assert integration.confidence_weight == 0.3
        assert integration.agreement_weight == 0.2
        assert integration.min_confidence_for_directional == 0.55
        assert integration.uncertainty_discount_factor == 0.5

    def test_custom_initialization(self):
        """Test custom initialization."""
        integration = ForecastOptionsIntegration(
            confidence_weight=0.4,
            agreement_weight=0.3,
            min_confidence_for_directional=0.6,
            uncertainty_discount_factor=0.3,
        )

        assert integration.confidence_weight == 0.4
        assert integration.agreement_weight == 0.3
        assert integration.min_confidence_for_directional == 0.6
        assert integration.uncertainty_discount_factor == 0.3


class TestConvertForecastToSignal:
    """Test convert_forecast_to_signal method."""

    def test_bullish_signal(self, bullish_forecast):
        """Test converting bullish forecast to signal."""
        integration = ForecastOptionsIntegration()
        signal = integration.convert_forecast_to_signal(bullish_forecast)

        assert signal.trend == "bullish"
        assert signal.confidence == 0.75
        assert signal.agreement == 0.8
        assert signal.n_models == 4
        assert signal.horizon == "1D"

    def test_bearish_signal(self, bearish_forecast):
        """Test converting bearish forecast to signal."""
        integration = ForecastOptionsIntegration()
        signal = integration.convert_forecast_to_signal(bearish_forecast)

        assert signal.trend == "bearish"
        assert signal.confidence == 0.70

    def test_neutral_signal_low_confidence(self, neutral_forecast):
        """Test that low confidence results in neutral trend."""
        integration = ForecastOptionsIntegration()
        signal = integration.convert_forecast_to_signal(neutral_forecast)

        # Even if label is something else, low confidence should give neutral
        assert signal.trend == "neutral"

    def test_signal_strength_bounded(self, bullish_forecast):
        """Test that signal strength is bounded 0-10."""
        integration = ForecastOptionsIntegration()
        signal = integration.convert_forecast_to_signal(bullish_forecast)

        assert 0 <= signal.signal_strength <= 10

    def test_uncertainty_bounded(self, bullish_forecast):
        """Test that uncertainty is bounded 0-1."""
        integration = ForecastOptionsIntegration()
        signal = integration.convert_forecast_to_signal(bullish_forecast)

        assert 0 <= signal.uncertainty <= 1

    def test_with_ohlc_data(self, bullish_forecast, sample_ohlc_df):
        """Test signal conversion with OHLC data."""
        integration = ForecastOptionsIntegration()
        signal = integration.convert_forecast_to_signal(
            bullish_forecast, sample_ohlc_df
        )

        # Should use OHLC to estimate supertrend factor
        assert signal.supertrend_factor >= 2.0

    def test_without_ohlc_data(self, bullish_forecast):
        """Test signal conversion without OHLC data."""
        integration = ForecastOptionsIntegration()
        signal = integration.convert_forecast_to_signal(bullish_forecast)

        # Should use forecast volatility if available
        assert signal.supertrend_factor >= 2.0


class TestCreateTrendAnalysisDict:
    """Test create_trend_analysis_dict method."""

    def test_creates_valid_dict(self, bullish_forecast):
        """Test that it creates a valid trend analysis dict."""
        integration = ForecastOptionsIntegration()
        signal = integration.convert_forecast_to_signal(bullish_forecast)
        trend_dict = integration.create_trend_analysis_dict(signal)

        assert "trend" in trend_dict
        assert "signal_strength" in trend_dict
        assert "supertrend_factor" in trend_dict
        assert "supertrend_performance" in trend_dict
        assert trend_dict["source"] == "ensemble_forecast"

    def test_includes_forecast_metadata(self, bullish_forecast):
        """Test that it includes forecast metadata."""
        integration = ForecastOptionsIntegration()
        signal = integration.convert_forecast_to_signal(bullish_forecast)
        trend_dict = integration.create_trend_analysis_dict(signal)

        assert trend_dict["forecast_confidence"] == signal.confidence
        assert trend_dict["forecast_agreement"] == signal.agreement
        assert trend_dict["n_models"] == signal.n_models

    def test_includes_earnings_date(self, bullish_forecast):
        """Test that it includes earnings date."""
        integration = ForecastOptionsIntegration()
        signal = integration.convert_forecast_to_signal(bullish_forecast)
        trend_dict = integration.create_trend_analysis_dict(
            signal, earnings_date="2024-01-25"
        )

        assert trend_dict["earnings_date"] == "2024-01-25"


class TestScoreOptionWithForecast:
    """Test score_option_with_forecast method."""

    def test_bullish_call_scores_higher(self, bullish_forecast):
        """Test that bullish forecast scores calls higher than puts."""
        integration = ForecastOptionsIntegration()
        signal = integration.convert_forecast_to_signal(bullish_forecast)

        call_option = {"side": "call", "strike": 100}
        put_option = {"side": "put", "strike": 100}

        call_score = integration.score_option_with_forecast(
            call_option, signal, underlying_price=100
        )
        put_score = integration.score_option_with_forecast(
            put_option, signal, underlying_price=100
        )

        assert call_score > put_score

    def test_bearish_put_scores_higher(self, bearish_forecast):
        """Test that bearish forecast scores puts higher than calls."""
        integration = ForecastOptionsIntegration()
        signal = integration.convert_forecast_to_signal(bearish_forecast)

        call_option = {"side": "call", "strike": 100}
        put_option = {"side": "put", "strike": 100}

        call_score = integration.score_option_with_forecast(
            call_option, signal, underlying_price=100
        )
        put_score = integration.score_option_with_forecast(
            put_option, signal, underlying_price=100
        )

        assert put_score > call_score

    def test_neutral_scores_similar(self, neutral_forecast):
        """Test that neutral forecast scores calls and puts similarly."""
        integration = ForecastOptionsIntegration()
        signal = integration.convert_forecast_to_signal(neutral_forecast)

        call_option = {"side": "call", "strike": 100}
        put_option = {"side": "put", "strike": 100}

        call_score = integration.score_option_with_forecast(
            call_option, signal, underlying_price=100
        )
        put_score = integration.score_option_with_forecast(
            put_option, signal, underlying_price=100
        )

        # Scores should be relatively close for neutral
        assert abs(call_score - put_score) < 0.3

    def test_score_bounded_0_to_1(self, bullish_forecast):
        """Test that scores are bounded 0-1."""
        integration = ForecastOptionsIntegration()
        signal = integration.convert_forecast_to_signal(bullish_forecast)

        for strike in [90, 100, 110, 120]:
            for side in ["call", "put"]:
                option = {"side": side, "strike": strike}
                score = integration.score_option_with_forecast(
                    option, signal, underlying_price=100
                )
                assert 0 <= score <= 1

    def test_otm_call_bullish_scores_well(self, bullish_forecast):
        """Test that slightly OTM call scores well in bullish forecast."""
        integration = ForecastOptionsIntegration()
        signal = integration.convert_forecast_to_signal(bullish_forecast)

        # Slightly OTM call (strike > underlying)
        otm_call = {"side": "call", "strike": 103}
        atm_call = {"side": "call", "strike": 100}
        deep_otm_call = {"side": "call", "strike": 115}

        otm_score = integration.score_option_with_forecast(
            otm_call, signal, underlying_price=100
        )
        atm_score = integration.score_option_with_forecast(
            atm_call, signal, underlying_price=100
        )
        deep_otm_score = integration.score_option_with_forecast(
            deep_otm_call, signal, underlying_price=100
        )

        # Slightly OTM should score at least as well as ATM
        assert otm_score >= atm_score * 0.9
        # Should score better than deep OTM
        assert otm_score > deep_otm_score


class TestRankOptionsWithForecast:
    """Test rank_options_with_forecast method."""

    def test_adds_forecast_score_column(
        self, bullish_forecast, sample_options_df
    ):
        """Test that it adds forecast_score column."""
        integration = ForecastOptionsIntegration()
        ranked = integration.rank_options_with_forecast(
            sample_options_df, bullish_forecast, underlying_price=100
        )

        assert "forecast_score" in ranked.columns

    def test_adds_forecast_metadata_columns(
        self, bullish_forecast, sample_options_df
    ):
        """Test that it adds forecast metadata columns."""
        integration = ForecastOptionsIntegration()
        ranked = integration.rank_options_with_forecast(
            sample_options_df, bullish_forecast, underlying_price=100
        )

        assert "forecast_trend" in ranked.columns
        assert "forecast_confidence" in ranked.columns
        assert "forecast_agreement" in ranked.columns

    def test_sorts_by_forecast_score(
        self, bullish_forecast, sample_options_df
    ):
        """Test that results are sorted by forecast score."""
        integration = ForecastOptionsIntegration()
        ranked = integration.rank_options_with_forecast(
            sample_options_df, bullish_forecast, underlying_price=100
        )

        scores = ranked["forecast_score"].values
        assert all(scores[i] >= scores[i+1] for i in range(len(scores)-1))

    def test_bullish_calls_rank_higher(
        self, bullish_forecast, sample_options_df
    ):
        """Test that calls rank higher in bullish forecast."""
        integration = ForecastOptionsIntegration()
        ranked = integration.rank_options_with_forecast(
            sample_options_df, bullish_forecast, underlying_price=100
        )

        # Top ranked should be calls
        top_3 = ranked.head(3)
        call_count = (top_3["side"] == "call").sum()
        assert call_count >= 2

    def test_bearish_puts_rank_higher(
        self, bearish_forecast, sample_options_df
    ):
        """Test that puts rank higher in bearish forecast."""
        integration = ForecastOptionsIntegration()
        ranked = integration.rank_options_with_forecast(
            sample_options_df, bearish_forecast, underlying_price=100
        )

        # Top ranked should be puts
        top_3 = ranked.head(3)
        put_count = (top_3["side"] == "put").sum()
        assert put_count >= 2

    def test_empty_dataframe(self, bullish_forecast):
        """Test with empty DataFrame."""
        integration = ForecastOptionsIntegration()
        empty_df = pd.DataFrame()

        ranked = integration.rank_options_with_forecast(
            empty_df, bullish_forecast, underlying_price=100
        )

        assert ranked.empty


class TestGetPositionSizeRecommendation:
    """Test get_position_size_recommendation method."""

    def test_returns_valid_dict(self, bullish_forecast):
        """Test that it returns a valid dict."""
        integration = ForecastOptionsIntegration()
        signal = integration.convert_forecast_to_signal(bullish_forecast)
        sizing = integration.get_position_size_recommendation(signal)

        assert "recommended_size" in sizing
        assert "size_factor" in sizing
        assert "is_high_conviction" in sizing
        assert "is_low_conviction" in sizing

    def test_high_confidence_larger_size(self):
        """Test that high confidence gives larger position size."""
        integration = ForecastOptionsIntegration()

        high_conf = ForecastSignal(
            trend="bullish",
            signal_strength=8.0,
            supertrend_factor=3.0,
            supertrend_performance=0.8,
            confidence=0.85,
            agreement=0.9,
            uncertainty=0.1,
        )

        low_conf = ForecastSignal(
            trend="bullish",
            signal_strength=4.0,
            supertrend_factor=3.0,
            supertrend_performance=0.3,
            confidence=0.55,
            agreement=0.5,
            uncertainty=0.6,
        )

        high_sizing = integration.get_position_size_recommendation(high_conf)
        low_sizing = integration.get_position_size_recommendation(low_conf)

        assert high_sizing["recommended_size"] > low_sizing["recommended_size"]

    def test_high_conviction_flag(self):
        """Test high conviction flag criteria."""
        integration = ForecastOptionsIntegration()

        high_conv = ForecastSignal(
            trend="bullish",
            signal_strength=9.0,
            supertrend_factor=3.0,
            supertrend_performance=0.9,
            confidence=0.8,
            agreement=0.8,
            uncertainty=0.2,
        )

        sizing = integration.get_position_size_recommendation(high_conv)
        assert sizing["is_high_conviction"]
        assert not sizing["is_low_conviction"]

    def test_low_conviction_flag(self):
        """Test low conviction flag criteria."""
        integration = ForecastOptionsIntegration()

        low_conv = ForecastSignal(
            trend="neutral",
            signal_strength=4.0,
            supertrend_factor=3.0,
            supertrend_performance=0.3,
            confidence=0.5,
            agreement=0.4,
            uncertainty=0.6,
        )

        sizing = integration.get_position_size_recommendation(low_conv)
        assert sizing["is_low_conviction"]
        assert not sizing["is_high_conviction"]

    def test_respects_max_position_size(self, bullish_forecast):
        """Test that it respects max position size."""
        integration = ForecastOptionsIntegration()
        signal = integration.convert_forecast_to_signal(bullish_forecast)

        sizing = integration.get_position_size_recommendation(
            signal, base_position_size=1.0, max_position_size=1.5
        )

        assert sizing["recommended_size"] <= 1.5


class TestFilterOptionsByForecast:
    """Test filter_options_by_forecast method."""

    def test_filters_by_score(self, bullish_forecast, sample_options_df):
        """Test filtering by forecast score."""
        integration = ForecastOptionsIntegration()
        signal = integration.convert_forecast_to_signal(bullish_forecast)

        # First rank to get scores
        ranked = integration.rank_options_with_forecast(
            sample_options_df, bullish_forecast, underlying_price=100
        )

        # Filter
        filtered = integration.filter_options_by_forecast(
            ranked, signal, min_forecast_score=0.6
        )

        assert len(filtered) <= len(ranked)
        assert all(filtered["forecast_score"] >= 0.6)

    def test_filters_by_side_for_strong_signal(
        self, bullish_forecast, sample_options_df
    ):
        """Test filtering by side for strong directional signals."""
        integration = ForecastOptionsIntegration()

        # Create strong bullish signal
        strong_bullish = bullish_forecast.copy()
        strong_bullish["confidence"] = 0.85

        signal = integration.convert_forecast_to_signal(strong_bullish)

        ranked = integration.rank_options_with_forecast(
            sample_options_df, strong_bullish, underlying_price=100
        )

        filtered = integration.filter_options_by_forecast(
            ranked, signal, min_forecast_score=0.4
        )

        # Should only have calls for strong bullish
        assert all(filtered["side"] == "call")

    def test_keeps_both_sides_for_neutral(
        self, neutral_forecast, sample_options_df
    ):
        """Test keeping both sides for neutral forecast."""
        integration = ForecastOptionsIntegration()
        signal = integration.convert_forecast_to_signal(neutral_forecast)

        ranked = integration.rank_options_with_forecast(
            sample_options_df, neutral_forecast, underlying_price=100
        )

        # Use a very low threshold to keep options
        filtered = integration.filter_options_by_forecast(
            ranked, signal, min_forecast_score=0.0
        )

        # Should have both calls and puts for neutral (no side filtering)
        sides = filtered["side"].unique()
        assert len(sides) == 2

    def test_returns_all_without_score_column(
        self, bullish_forecast, sample_options_df
    ):
        """Test returning all options when no score column."""
        integration = ForecastOptionsIntegration()
        signal = integration.convert_forecast_to_signal(bullish_forecast)

        # No score column
        result = integration.filter_options_by_forecast(
            sample_options_df, signal, min_forecast_score=0.5
        )

        assert len(result) == len(sample_options_df)


class TestLabelToTrend:
    """Test _label_to_trend method."""

    def test_bullish_high_confidence(self):
        """Test bullish label with high confidence."""
        integration = ForecastOptionsIntegration()
        trend = integration._label_to_trend("Bullish", 0.7)
        assert trend == "bullish"

    def test_bearish_high_confidence(self):
        """Test bearish label with high confidence."""
        integration = ForecastOptionsIntegration()
        trend = integration._label_to_trend("Bearish", 0.7)
        assert trend == "bearish"

    def test_neutral_label(self):
        """Test neutral label."""
        integration = ForecastOptionsIntegration()
        trend = integration._label_to_trend("Neutral", 0.7)
        assert trend == "neutral"

    def test_low_confidence_is_neutral(self):
        """Test that low confidence gives neutral regardless of label."""
        integration = ForecastOptionsIntegration()

        trend = integration._label_to_trend("Bullish", 0.5)
        assert trend == "neutral"

        trend = integration._label_to_trend("Bearish", 0.4)
        assert trend == "neutral"


class TestCalculateSignalStrength:
    """Test _calculate_signal_strength method."""

    def test_high_confidence_high_strength(self):
        """Test that high confidence gives high strength."""
        integration = ForecastOptionsIntegration()

        strength = integration._calculate_signal_strength(
            confidence=0.9,
            agreement=0.9,
            probabilities={"bullish": 0.9, "neutral": 0.05, "bearish": 0.05},
        )

        assert strength >= 7

    def test_low_confidence_low_strength(self):
        """Test that low confidence gives low strength."""
        integration = ForecastOptionsIntegration()

        strength = integration._calculate_signal_strength(
            confidence=0.4,
            agreement=0.4,
            probabilities={"bullish": 0.35, "neutral": 0.35, "bearish": 0.30},
        )

        assert strength < 5

    def test_strength_bounded_0_10(self):
        """Test that strength is bounded 0-10."""
        integration = ForecastOptionsIntegration()

        # Test extreme cases
        probs = {"bullish": 0.8, "neutral": 0.1, "bearish": 0.1}
        for conf in [0, 0.5, 1.0]:
            for agree in [0, 0.5, 1.0]:
                strength = integration._calculate_signal_strength(
                    confidence=conf,
                    agreement=agree,
                    probabilities=probs,
                )
                assert 0 <= strength <= 10


class TestCalculateUncertainty:
    """Test _calculate_uncertainty method."""

    def test_high_certainty_low_uncertainty(self):
        """Test that concentrated probabilities give low uncertainty."""
        integration = ForecastOptionsIntegration()

        uncertainty = integration._calculate_uncertainty({
            "bullish": 0.9,
            "neutral": 0.05,
            "bearish": 0.05,
        })

        assert uncertainty < 0.5

    def test_uniform_high_uncertainty(self):
        """Test that uniform probabilities give high uncertainty."""
        integration = ForecastOptionsIntegration()

        uncertainty = integration._calculate_uncertainty({
            "bullish": 0.333,
            "neutral": 0.334,
            "bearish": 0.333,
        })

        assert uncertainty > 0.9

    def test_empty_probabilities(self):
        """Test with empty probabilities."""
        integration = ForecastOptionsIntegration()

        uncertainty = integration._calculate_uncertainty({})
        assert uncertainty == 0.5


class TestCalculateATR:
    """Test _calculate_atr method."""

    def test_calculates_atr(self, sample_ohlc_df):
        """Test ATR calculation."""
        integration = ForecastOptionsIntegration()
        atr = integration._calculate_atr(sample_ohlc_df)

        assert atr > 0

    def test_atr_with_short_data(self):
        """Test ATR with short data."""
        integration = ForecastOptionsIntegration()

        short_df = pd.DataFrame({
            "high": [101, 102, 103, 104, 105],
            "low": [99, 100, 101, 102, 103],
            "close": [100, 101, 102, 103, 104],
        })

        atr = integration._calculate_atr(short_df, period=3)
        assert atr >= 0


class TestScoreDirectionalAlignment:
    """Test _score_directional_alignment method."""

    def test_bullish_call_aligned(self):
        """Test bullish trend with call is aligned."""
        integration = ForecastOptionsIntegration()

        score = integration._score_directional_alignment(
            trend="bullish", side="call", confidence=0.8
        )

        assert score > 0.5

    def test_bullish_put_misaligned(self):
        """Test bullish trend with put is misaligned."""
        integration = ForecastOptionsIntegration()

        score = integration._score_directional_alignment(
            trend="bullish", side="put", confidence=0.8
        )

        assert score < 0.5

    def test_neutral_both_ok(self):
        """Test neutral trend gives 0.5 for both sides."""
        integration = ForecastOptionsIntegration()

        call_score = integration._score_directional_alignment(
            trend="neutral", side="call", confidence=0.5
        )
        put_score = integration._score_directional_alignment(
            trend="neutral", side="put", confidence=0.5
        )

        assert call_score == 0.5
        assert put_score == 0.5


class TestScoreMoneynessAlignment:
    """Test _score_moneyness_alignment method."""

    def test_bullish_otm_call(self):
        """Test slightly OTM call scores well for bullish."""
        integration = ForecastOptionsIntegration()

        score = integration._score_moneyness_alignment(
            strike=103,  # Slightly OTM
            underlying=100,
            trend="bullish",
            side="call",
        )

        assert score >= 0.8

    def test_bearish_otm_put(self):
        """Test slightly OTM put scores well for bearish."""
        integration = ForecastOptionsIntegration()

        score = integration._score_moneyness_alignment(
            strike=97,  # Slightly OTM put
            underlying=100,
            trend="bearish",
            side="put",
        )

        assert score >= 0.8

    def test_neutral_atm(self):
        """Test ATM scores well for neutral."""
        integration = ForecastOptionsIntegration()

        score = integration._score_moneyness_alignment(
            strike=100,
            underlying=100,
            trend="neutral",
            side="call",
        )

        assert score >= 0.7


class TestCreateIntegrationFromManager:
    """Test create_integration_from_manager function."""

    def test_with_no_history(self):
        """Test with manager that has no history."""

        class MockManager:
            forecast_history = []

        integration, signal = create_integration_from_manager(MockManager())

        assert isinstance(integration, ForecastOptionsIntegration)
        assert signal.trend == "neutral"
        assert signal.confidence == 0.5

    def test_with_history(self):
        """Test with manager that has history."""

        class MockForecastResult:
            label = "Bullish"
            confidence = 0.8
            probabilities = {"bullish": 0.8, "neutral": 0.1, "bearish": 0.1}
            agreement = 0.85
            forecast_return = 0.02
            forecast_volatility = 0.015
            n_models = 5

        class MockManager:
            forecast_history = [MockForecastResult()]

        integration, signal = create_integration_from_manager(MockManager())

        assert signal.trend == "bullish"
        assert signal.confidence == 0.8


class TestIntegration:
    """Integration tests."""

    def test_full_workflow(
        self, bullish_forecast, sample_options_df, sample_ohlc_df
    ):
        """Test complete workflow."""
        integration = ForecastOptionsIntegration()

        # 1. Convert forecast to signal
        signal = integration.convert_forecast_to_signal(
            bullish_forecast, sample_ohlc_df
        )
        assert signal.trend == "bullish"

        # 2. Create trend analysis dict
        trend_dict = integration.create_trend_analysis_dict(signal)
        assert trend_dict["source"] == "ensemble_forecast"

        # 3. Rank options
        ranked = integration.rank_options_with_forecast(
            sample_options_df, bullish_forecast, underlying_price=100
        )
        assert "forecast_score" in ranked.columns

        # 4. Filter options
        filtered = integration.filter_options_by_forecast(
            ranked, signal, min_forecast_score=0.5
        )
        assert len(filtered) <= len(ranked)

        # 5. Get position sizing
        sizing = integration.get_position_size_recommendation(signal)
        assert sizing["recommended_size"] > 0

    def test_bearish_workflow(
        self, bearish_forecast, sample_options_df
    ):
        """Test workflow with bearish forecast."""
        integration = ForecastOptionsIntegration()

        signal = integration.convert_forecast_to_signal(bearish_forecast)
        assert signal.trend == "bearish"

        ranked = integration.rank_options_with_forecast(
            sample_options_df, bearish_forecast, underlying_price=100
        )

        # Top options should be puts
        top_side = ranked.iloc[0]["side"]
        assert top_side == "put"

    def test_neutral_workflow(
        self, neutral_forecast, sample_options_df
    ):
        """Test workflow with neutral forecast."""
        integration = ForecastOptionsIntegration()

        signal = integration.convert_forecast_to_signal(neutral_forecast)
        assert signal.trend == "neutral"

        sizing = integration.get_position_size_recommendation(signal)
        # Should recommend smaller position for uncertain forecast
        assert sizing["is_low_conviction"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
