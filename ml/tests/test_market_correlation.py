"""
Unit tests for Market Correlation Features.

Tests:
- SPY correlation calculation
- Beta estimation
- Relative strength
- Momentum spread
- Feature integration
"""

import numpy as np
import pandas as pd
import pytest

from src.features.market_correlation import MarketCorrelationFeatures


class TestMarketCorrelationFeatures:
    """Test suite for MarketCorrelationFeatures."""

    @pytest.fixture
    def spy_data(self):
        """Create synthetic SPY data."""
        np.random.seed(42)
        n = 250
        prices = 100 * np.exp(np.cumsum(np.random.randn(n) * 0.01))

        return pd.DataFrame({
            "ts": pd.date_range("2024-01-01", periods=n, freq="D"),
            "close": prices,
        })

    @pytest.fixture
    def symbol_data(self):
        """Create synthetic symbol data (correlated with SPY)."""
        np.random.seed(42)
        n = 250

        # Start with SPY-like movement
        spy_like = 100 * np.exp(np.cumsum(np.random.randn(n) * 0.01))

        # Add some idiosyncratic movement (0.7 correlation)
        noise = np.random.randn(n) * 0.01
        prices = 50 * np.exp(np.cumsum(
            0.7 * np.diff(np.log(spy_like), prepend=np.log(spy_like[0])) +
            0.3 * noise
        ))

        return pd.DataFrame({
            "ts": pd.date_range("2024-01-01", periods=n, freq="D"),
            "close": prices,
        })

    def test_initialization(self, spy_data):
        """Test calculator initialization."""
        calc = MarketCorrelationFeatures(spy_data=spy_data)

        assert calc.spy_data is not None
        assert calc.spy_returns is not None
        assert len(calc.spy_returns) == len(spy_data)
        print("✓ Initialization successful")

    def test_correlation_features(self, spy_data, symbol_data):
        """Test correlation feature calculation."""
        calc = MarketCorrelationFeatures(spy_data=spy_data)
        result = calc.calculate_features(symbol_data)

        # Check correlation features exist
        assert "spy_correlation_20d" in result.columns
        assert "spy_correlation_60d" in result.columns
        assert "spy_correlation_120d" in result.columns
        assert "spy_correlation_change" in result.columns

        # Check reasonable values
        corr_20d = result["spy_correlation_20d"].dropna()
        assert len(corr_20d) > 0
        assert all(-1 <= c <= 1 for c in corr_20d)
        print(f"✓ Correlation features: 20d avg={corr_20d.mean():.3f}, std={corr_20d.std():.3f}")

    def test_beta_features(self, spy_data, symbol_data):
        """Test beta calculation."""
        calc = MarketCorrelationFeatures(spy_data=spy_data)
        result = calc.calculate_features(symbol_data)

        # Check beta features
        assert "market_beta_20d" in result.columns
        assert "market_beta_60d" in result.columns
        assert "market_beta_momentum" in result.columns
        assert "market_beta_regime" in result.columns

        # Check reasonable values
        beta = result["market_beta_60d"].dropna()
        assert len(beta) > 0
        assert all(b > 0 for b in beta)  # Beta should be positive
        print(f"✓ Beta features: 60d avg={beta.mean():.3f}, range=[{beta.min():.2f}, {beta.max():.2f}]")

    def test_relative_strength(self, spy_data, symbol_data):
        """Test relative strength features."""
        calc = MarketCorrelationFeatures(spy_data=spy_data)
        result = calc.calculate_features(symbol_data)

        # Check RS features
        assert "market_rs_20d" in result.columns
        assert "market_rs_60d" in result.columns
        assert "market_rs_trend" in result.columns
        assert "market_rs_percentile" in result.columns

        rs = result["market_rs_20d"].dropna()
        assert len(rs) > 0
        print(f"✓ Relative strength: 20d avg={rs.mean():.4f}, percentile avg={result['market_rs_percentile'].mean():.2%}")

    def test_momentum_spread(self, spy_data, symbol_data):
        """Test momentum spread features."""
        calc = MarketCorrelationFeatures(spy_data=spy_data)
        result = calc.calculate_features(symbol_data)

        # Check momentum features
        assert "momentum_spread_5d" in result.columns
        assert "momentum_spread_20d" in result.columns
        assert "momentum_alignment" in result.columns

        spread = result["momentum_spread_5d"].dropna()
        alignment = result["momentum_alignment"].dropna()
        assert len(spread) > 0
        assert len(alignment) > 0
        assert all(a in [0, 1] for a in alignment)  # Binary: 0 or 1
        print(f"✓ Momentum spread: 5d avg={spread.mean():.4f}, alignment={alignment.mean():.1%}")

    def test_placeholder_features(self):
        """Test placeholder feature generation when SPY data unavailable."""
        symbol_data = pd.DataFrame({
            "ts": pd.date_range("2024-01-01", periods=100, freq="D"),
            "close": np.linspace(100, 105, 100),
        })

        calc = MarketCorrelationFeatures(spy_data=None)
        result = calc.calculate_features(symbol_data)

        # Should have all features as placeholders
        assert "spy_correlation_20d" in result.columns
        assert "market_beta_20d" in result.columns
        assert "market_rs_20d" in result.columns
        assert "momentum_spread_5d" in result.columns

        # Placeholders should be reasonable
        assert (result["market_beta_20d"] == 1.0).all()  # Market-neutral
        assert (result["momentum_alignment"] == 0.5).all()  # 50% alignment
        print("✓ Placeholder features working")

    def test_feature_count(self, spy_data, symbol_data):
        """Test that correct number of features is added."""
        calc = MarketCorrelationFeatures(spy_data=spy_data)
        original_cols = set(symbol_data.columns)
        result = calc.calculate_features(symbol_data)
        new_cols = set(result.columns) - original_cols

        # Should add 15 features
        expected_features = {
            "spy_correlation_20d", "spy_correlation_60d", "spy_correlation_120d",
            "spy_correlation_change",
            "market_beta_20d", "market_beta_60d", "market_beta_momentum", "market_beta_regime",
            "market_rs_20d", "market_rs_60d", "market_rs_trend", "market_rs_percentile",
            "momentum_spread_5d", "momentum_spread_20d", "momentum_alignment",
        }

        assert expected_features.issubset(new_cols)
        print(f"✓ Added {len(expected_features)} features as expected")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Market Correlation Features")
    print("=" * 60)

    test = TestMarketCorrelationFeatures()
    spy = test.spy_data()
    symbol = test.symbol_data()

    test.test_initialization(spy)
    test.test_correlation_features(spy, symbol)
    test.test_beta_features(spy, symbol)
    test.test_relative_strength(spy, symbol)
    test.test_momentum_spread(spy, symbol)
    test.test_placeholder_features()
    test.test_feature_count(spy, symbol)

    print("\n" + "=" * 60)
    print("All Market Correlation tests passed! ✓")
    print("=" * 60)
