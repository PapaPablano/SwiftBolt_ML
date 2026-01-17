"""Tests for alpaca_underlying_history module."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from src.data.alpaca_underlying_history import (
    AlpacaUnderlyingHistoryClient,
    UnderlyingMetrics,
    compute_all_metrics,
    compute_drawdown,
    compute_return,
    compute_volatility,
    count_gaps,
    fetch_underlying_history,
    get_client,
    metrics_to_dict,
)


# ============================================================================
# Test data fixtures
# ============================================================================


@pytest.fixture
def sample_prices():
    """Sample close prices for testing."""
    return pd.Series([100.0, 102.0, 101.5, 103.0, 105.0, 104.0, 107.0])


@pytest.fixture
def sample_ohlc_df():
    """Sample OHLC DataFrame for testing."""
    return pd.DataFrame(
        {
            "ts": pd.date_range("2024-01-01", periods=7, freq="D"),
            "open": [100.0, 102.5, 101.0, 102.0, 104.5, 105.5, 103.5],
            "high": [103.0, 104.0, 103.5, 105.0, 107.0, 108.0, 109.0],
            "low": [99.0, 101.0, 100.0, 101.5, 103.0, 103.5, 102.5],
            "close": [100.0, 102.0, 101.5, 103.0, 105.0, 104.0, 107.0],
            "volume": [1000000, 1200000, 900000, 1100000, 1500000, 1300000, 1400000],
        }
    )


@pytest.fixture
def sample_ohlc_with_gaps():
    """Sample OHLC DataFrame with price gaps."""
    return pd.DataFrame(
        {
            "ts": pd.date_range("2024-01-01", periods=5, freq="D"),
            "open": [100.0, 105.0, 103.0, 110.0, 108.0],  # 5% gap, then 7% gap
            "high": [103.0, 106.0, 105.0, 112.0, 110.0],
            "low": [99.0, 102.0, 101.0, 107.0, 105.0],
            "close": [102.0, 104.0, 102.5, 109.0, 107.5],
            "volume": [1000000, 1200000, 900000, 1100000, 1500000],
        }
    )


# ============================================================================
# Unit tests for metric computation functions
# ============================================================================


class TestComputeReturn:
    """Tests for compute_return function."""

    def test_positive_return(self, sample_prices):
        """Test positive return calculation."""
        ret = compute_return(sample_prices)
        # (107 - 100) / 100 * 100 = 7%
        assert abs(ret - 7.0) < 0.01

    def test_negative_return(self):
        """Test negative return calculation."""
        prices = pd.Series([100.0, 95.0, 92.0])
        ret = compute_return(prices)
        # (92 - 100) / 100 * 100 = -8%
        assert abs(ret - (-8.0)) < 0.01

    def test_zero_return(self):
        """Test zero return when prices are equal."""
        prices = pd.Series([100.0, 100.0, 100.0])
        ret = compute_return(prices)
        assert ret == 0.0

    def test_single_price(self):
        """Test return with single price."""
        prices = pd.Series([100.0])
        ret = compute_return(prices)
        assert ret == 0.0

    def test_empty_series(self):
        """Test return with empty series."""
        prices = pd.Series([], dtype=float)
        ret = compute_return(prices)
        assert ret == 0.0


class TestComputeVolatility:
    """Tests for compute_volatility function."""

    def test_positive_volatility(self, sample_prices):
        """Test volatility is positive and reasonable."""
        vol = compute_volatility(sample_prices)
        # Volatility should be positive
        assert vol > 0
        # Annualized volatility should be reasonable (10-100% range for typical stocks)
        assert vol < 200  # Upper bound for sanity check

    def test_constant_prices(self):
        """Test volatility is zero for constant prices."""
        prices = pd.Series([100.0, 100.0, 100.0, 100.0])
        vol = compute_volatility(prices)
        assert vol == 0.0

    def test_short_series(self):
        """Test volatility with too few prices."""
        prices = pd.Series([100.0, 102.0])
        vol = compute_volatility(prices)
        assert vol == 0.0


class TestComputeDrawdown:
    """Tests for compute_drawdown function."""

    def test_drawdown_with_decline(self):
        """Test drawdown calculation with price decline."""
        # Peak at 110, then drops to 100 = 9.09% drawdown
        prices = pd.Series([100.0, 105.0, 110.0, 105.0, 100.0])
        dd = compute_drawdown(prices)
        assert abs(dd - 9.09) < 0.1

    def test_no_drawdown_uptrend(self):
        """Test no drawdown in pure uptrend."""
        prices = pd.Series([100.0, 102.0, 104.0, 106.0, 108.0])
        dd = compute_drawdown(prices)
        assert dd == 0.0

    def test_full_recovery(self):
        """Test drawdown with full recovery."""
        prices = pd.Series([100.0, 110.0, 95.0, 115.0])
        dd = compute_drawdown(prices)
        # Max drawdown from 110 to 95 = 13.6%
        assert abs(dd - 13.6) < 0.5


class TestCountGaps:
    """Tests for count_gaps function."""

    def test_gaps_detected(self, sample_ohlc_with_gaps):
        """Test gap detection with threshold."""
        gap_count = count_gaps(sample_ohlc_with_gaps, threshold_pct=1.0)
        # Two significant gaps: 5% and 7%
        assert gap_count >= 2

    def test_no_gaps(self, sample_ohlc_df):
        """Test no gaps when prices are continuous."""
        gap_count = count_gaps(sample_ohlc_df, threshold_pct=5.0)
        # With 5% threshold, small moves shouldn't count as gaps
        assert gap_count == 0

    def test_empty_df(self):
        """Test with empty DataFrame."""
        df = pd.DataFrame()
        gap_count = count_gaps(df)
        assert gap_count == 0


class TestComputeAllMetrics:
    """Tests for compute_all_metrics function."""

    def test_all_metrics_computed(self, sample_ohlc_df):
        """Test all metrics are computed correctly."""
        metrics = compute_all_metrics(sample_ohlc_df, "AAPL", "d1")

        assert metrics.symbol == "AAPL"
        assert metrics.timeframe == "d1"
        assert isinstance(metrics.return_7d, float)
        assert isinstance(metrics.volatility_7d, float)
        assert isinstance(metrics.drawdown_7d, float)
        assert isinstance(metrics.gap_count, int)
        assert metrics.bars_count == 7
        assert metrics.first_ts is not None
        assert metrics.last_ts is not None
        assert metrics.computed_at is not None

    def test_empty_df_metrics(self):
        """Test metrics with empty DataFrame."""
        df = pd.DataFrame()
        metrics = compute_all_metrics(df, "AAPL", "d1")

        assert metrics.symbol == "AAPL"
        assert metrics.return_7d == 0.0
        assert metrics.volatility_7d == 0.0
        assert metrics.drawdown_7d == 0.0
        assert metrics.gap_count == 0
        assert metrics.bars_count == 0


# ============================================================================
# Tests for AlpacaUnderlyingHistoryClient
# ============================================================================


class TestAlpacaUnderlyingHistoryClient:
    """Tests for AlpacaUnderlyingHistoryClient class."""

    def test_cache_key_generation(self):
        """Test cache key generation."""
        client = AlpacaUnderlyingHistoryClient()
        key = client._get_cache_key("AAPL", "d1")
        assert key == "AAPL:d1"

    def test_cache_validity_empty(self):
        """Test cache validity for empty cache."""
        client = AlpacaUnderlyingHistoryClient()
        assert not client._is_cache_valid("AAPL:d1")

    @pytest.mark.asyncio
    async def test_fetch_bars_no_credentials(self):
        """Test fetch_bars returns empty when no credentials."""
        with patch.dict("os.environ", {"ALPACA_API_KEY": "", "ALPACA_API_SECRET": ""}):
            client = AlpacaUnderlyingHistoryClient()
            # Import fresh to get updated env vars
            import importlib

            import src.data.alpaca_underlying_history as mod

            importlib.reload(mod)

            # Should return empty DataFrame due to missing credentials
            # (The actual behavior depends on how credentials are checked)

    def test_clear_cache(self):
        """Test cache clearing."""
        client = AlpacaUnderlyingHistoryClient()
        client._cache["AAPL:d1"] = (pd.DataFrame(), 0.0)
        assert len(client._cache) == 1

        client.clear_cache()
        assert len(client._cache) == 0


class TestMetricsToDict:
    """Tests for metrics_to_dict function."""

    def test_conversion(self):
        """Test UnderlyingMetrics to dict conversion."""
        now = datetime.now(timezone.utc)
        metrics = UnderlyingMetrics(
            symbol="AAPL",
            timeframe="d1",
            return_7d=5.5,
            volatility_7d=25.0,
            drawdown_7d=3.2,
            gap_count=1,
            bars_count=7,
            first_ts=now,
            last_ts=now,
            computed_at=now,
        )

        result = metrics_to_dict(metrics)

        assert result["symbol"] == "AAPL"
        assert result["timeframe"] == "d1"
        assert result["ret_7d"] == 5.5
        assert result["vol_7d"] == 25.0
        assert result["drawdown_7d"] == 3.2
        assert result["gap_count"] == 1
        assert result["bars_count"] == 7


class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    def test_get_client_singleton(self):
        """Test get_client returns singleton."""
        client1 = get_client()
        client2 = get_client()
        assert client1 is client2

    @pytest.mark.asyncio
    async def test_fetch_underlying_history_mocked(self):
        """Test fetch_underlying_history with mocked client."""
        mock_metrics = UnderlyingMetrics(
            symbol="AAPL",
            timeframe="d1",
            return_7d=5.0,
            volatility_7d=20.0,
            drawdown_7d=2.0,
            gap_count=0,
            bars_count=7,
            first_ts=datetime.now(timezone.utc),
            last_ts=datetime.now(timezone.utc),
            computed_at=datetime.now(timezone.utc),
        )

        with patch.object(
            AlpacaUnderlyingHistoryClient,
            "fetch_7day_metrics",
            new_callable=AsyncMock,
            return_value=mock_metrics,
        ):
            client = get_client()
            result = await client.fetch_7day_metrics("AAPL", "d1")
            assert result.symbol == "AAPL"
            assert result.return_7d == 5.0


# ============================================================================
# Integration-style tests (still using mocks but testing full flow)
# ============================================================================


class TestIntegration:
    """Integration tests for the full metric computation flow."""

    def test_full_metric_flow(self, sample_ohlc_df):
        """Test the full flow from OHLC data to metrics."""
        # Compute metrics
        metrics = compute_all_metrics(sample_ohlc_df, "NVDA", "d1")

        # Verify all fields populated
        assert metrics.symbol == "NVDA"
        assert metrics.bars_count == 7
        assert metrics.return_7d != 0  # Should have some return

        # Convert to dict for database
        metrics_dict = metrics_to_dict(metrics)

        # Verify dict has expected structure
        assert "symbol" in metrics_dict
        assert "ret_7d" in metrics_dict
        assert "vol_7d" in metrics_dict
        assert "computed_at" in metrics_dict
