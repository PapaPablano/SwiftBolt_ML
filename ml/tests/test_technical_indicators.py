"""Unit tests for technical indicators."""

import numpy as np
import pandas as pd
import pytest

from src.features.technical_indicators import (
    add_all_technical_features,
    add_technical_features,
    calculate_adx,
    calculate_atr,
    calculate_kdj,
    calculate_keltner_channel,
    calculate_mfi,
    calculate_obv,
    calculate_rsi,
    calculate_stochastic,
    calculate_vroc,
)


@pytest.fixture
def sample_ohlc_df():
    """Create sample OHLC data for testing."""
    np.random.seed(42)
    n = 100

    # Generate realistic price data
    base_price = 100.0
    returns = np.random.randn(n) * 0.02  # 2% daily volatility
    prices = base_price * np.cumprod(1 + returns)

    # Generate OHLC from close prices
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


class TestBasicIndicators:
    """Test basic technical indicators."""

    def test_add_technical_features_columns(self, sample_ohlc_df):
        """Test that add_technical_features adds expected columns."""
        df = add_technical_features(sample_ohlc_df)

        expected_cols = [
            "returns_1d",
            "returns_5d",
            "returns_20d",
            "sma_5",
            "sma_20",
            "sma_50",
            "ema_12",
            "ema_26",
            "macd",
            "macd_signal",
            "macd_hist",
            "rsi_14",
            "bb_upper",
            "bb_middle",
            "bb_lower",
            "bb_width",
            "atr_14",
            "volume_sma_20",
            "volume_ratio",
            "volatility_20d",
            "price_vs_sma20",
            "price_vs_sma50",
        ]

        for col in expected_cols:
            assert col in df.columns, f"Missing column: {col}"

    def test_rsi_range(self, sample_ohlc_df):
        """Test that RSI is within 0-100 range."""
        rsi = calculate_rsi(sample_ohlc_df["close"], period=14)

        # Skip NaN values from warmup period
        valid_rsi = rsi.dropna()

        assert (valid_rsi >= 0).all(), "RSI should be >= 0"
        assert (valid_rsi <= 100).all(), "RSI should be <= 100"

    def test_atr_positive(self, sample_ohlc_df):
        """Test that ATR is always positive."""
        atr = calculate_atr(sample_ohlc_df, period=14)
        valid_atr = atr.dropna()

        assert (valid_atr >= 0).all(), "ATR should be >= 0"


class TestMomentumIndicators:
    """Test momentum indicators (Stochastic, KDJ, ADX)."""

    def test_stochastic_range(self, sample_ohlc_df):
        """Test that Stochastic K and D are within 0-100."""
        df = calculate_stochastic(sample_ohlc_df, k_period=14, d_period=3)

        stoch_k = df["stoch_k"].dropna()
        stoch_d = df["stoch_d"].dropna()

        assert (stoch_k >= 0).all(), "Stochastic K should be >= 0"
        assert (stoch_k <= 100).all(), "Stochastic K should be <= 100"
        assert (stoch_d >= 0).all(), "Stochastic D should be >= 0"
        assert (stoch_d <= 100).all(), "Stochastic D should be <= 100"

    def test_kdj_columns_exist(self, sample_ohlc_df):
        """Test that KDJ adds expected columns."""
        df = calculate_kdj(sample_ohlc_df)

        assert "kdj_k" in df.columns
        assert "kdj_d" in df.columns
        assert "kdj_j" in df.columns
        assert "kdj_j_minus_d" in df.columns

    def test_kdj_j_formula(self, sample_ohlc_df):
        """Test that J = 3*K - 2*D."""
        df = calculate_kdj(sample_ohlc_df)

        # Get valid values
        mask = df["kdj_k"].notna() & df["kdj_d"].notna() & df["kdj_j"].notna()
        valid_df = df[mask]

        expected_j = 3 * valid_df["kdj_k"] - 2 * valid_df["kdj_d"]
        np.testing.assert_array_almost_equal(
            valid_df["kdj_j"].values, expected_j.values, decimal=10
        )

    def test_adx_range(self, sample_ohlc_df):
        """Test that ADX is within 0-100."""
        df = calculate_adx(sample_ohlc_df)

        adx = df["adx"].dropna()
        plus_di = df["plus_di"].dropna()
        minus_di = df["minus_di"].dropna()

        assert (adx >= 0).all(), "ADX should be >= 0"
        assert (adx <= 100).all(), "ADX should be <= 100"
        assert (plus_di >= 0).all(), "+DI should be >= 0"
        assert (minus_di >= 0).all(), "-DI should be >= 0"


class TestVolumeIndicators:
    """Test volume indicators (OBV, MFI, VROC)."""

    def test_obv_columns_exist(self, sample_ohlc_df):
        """Test that OBV adds expected columns."""
        df = calculate_obv(sample_ohlc_df)

        assert "obv" in df.columns
        assert "obv_sma" in df.columns

    def test_obv_cumulative(self, sample_ohlc_df):
        """Test that OBV is cumulative."""
        df = calculate_obv(sample_ohlc_df)

        # OBV should change direction based on price change
        # Just verify it's not constant
        obv = df["obv"].dropna()
        assert obv.nunique() > 1, "OBV should not be constant"

    def test_mfi_range(self, sample_ohlc_df):
        """Test that MFI is within 0-100."""
        df = calculate_mfi(sample_ohlc_df)

        mfi = df["mfi"].dropna()

        assert (mfi >= 0).all(), "MFI should be >= 0"
        assert (mfi <= 100).all(), "MFI should be <= 100"

    def test_vroc_exists(self, sample_ohlc_df):
        """Test that VROC is calculated."""
        df = calculate_vroc(sample_ohlc_df)

        assert "vroc" in df.columns
        vroc = df["vroc"].dropna()
        assert len(vroc) > 0, "VROC should have values"


class TestVolatilityIndicators:
    """Test volatility indicators (Keltner Channel)."""

    def test_keltner_channel_columns(self, sample_ohlc_df):
        """Test that Keltner Channel adds expected columns."""
        df = calculate_keltner_channel(sample_ohlc_df)

        assert "keltner_upper" in df.columns
        assert "keltner_middle" in df.columns
        assert "keltner_lower" in df.columns

    def test_keltner_channel_order(self, sample_ohlc_df):
        """Test that upper > middle > lower."""
        df = calculate_keltner_channel(sample_ohlc_df)

        # Get valid values
        mask = (
            df["keltner_upper"].notna() & df["keltner_middle"].notna() & df["keltner_lower"].notna()
        )
        valid_df = df[mask]

        assert (
            valid_df["keltner_upper"] >= valid_df["keltner_middle"]
        ).all(), "Upper should be >= middle"
        assert (
            valid_df["keltner_middle"] >= valid_df["keltner_lower"]
        ).all(), "Middle should be >= lower"


class TestComprehensiveFeatures:
    """Test the comprehensive feature function."""

    def test_add_all_technical_features(self, sample_ohlc_df):
        """Test that add_all_technical_features adds all indicator columns."""
        df = add_all_technical_features(sample_ohlc_df)

        # Check for momentum indicators
        momentum_cols = ["stoch_k", "stoch_d", "kdj_k", "kdj_d", "kdj_j", "adx"]
        for col in momentum_cols:
            assert col in df.columns, f"Missing momentum indicator: {col}"

        # Check for volume indicators
        volume_cols = ["obv", "mfi", "vroc"]
        for col in volume_cols:
            assert col in df.columns, f"Missing volume indicator: {col}"

        # Check for volatility indicators
        volatility_cols = ["keltner_upper", "keltner_middle", "keltner_lower"]
        for col in volatility_cols:
            assert col in df.columns, f"Missing volatility indicator: {col}"

    def test_no_all_nan_columns(self, sample_ohlc_df):
        """Test that no indicator column is entirely NaN."""
        df = add_all_technical_features(sample_ohlc_df)

        # Exclude original OHLCV columns
        indicator_cols = [
            col for col in df.columns if col not in ["ts", "open", "high", "low", "close", "volume"]
        ]

        for col in indicator_cols:
            assert not df[col].isna().all(), f"Column {col} is entirely NaN"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_dataframe(self):
        """Test handling of empty DataFrame."""
        df = pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])
        result = add_technical_features(df)
        assert len(result) == 0

    def test_single_row(self):
        """Test handling of single row DataFrame."""
        df = pd.DataFrame(
            {
                "ts": [pd.Timestamp("2024-01-01")],
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.5],
                "volume": [1000000.0],
            }
        )
        # Should not raise an error
        result = add_technical_features(df)
        assert len(result) == 1

    def test_constant_prices(self):
        """Test handling of constant prices (no volatility)."""
        n = 50
        df = pd.DataFrame(
            {
                "ts": pd.date_range("2024-01-01", periods=n, freq="D"),
                "open": [100.0] * n,
                "high": [100.0] * n,
                "low": [100.0] * n,
                "close": [100.0] * n,
                "volume": [1000000.0] * n,
            }
        )

        # Should handle division by zero gracefully
        result = add_all_technical_features(df)

        # Some indicators may be NaN due to zero range, but shouldn't crash
        assert len(result) == n


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
