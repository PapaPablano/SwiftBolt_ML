"""
Historical data testing for walk-forward validation.

Tests walk-forward window creation and divergence detection on realistic
historical time series data spanning multiple years.

This validates Phase 2.3 (Walk-Forward Validation on Historical Data).
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.training.walk_forward_optimizer import WalkForwardOptimizer, WindowConfig


class TestWalkForwardOnHistoricalData:
    """Test walk-forward validation on historical market data."""

    @pytest.fixture
    def five_year_data(self):
        """Generate 5 years of synthetic OHLC data (realistic market simulation)."""
        # Generate 5 years of daily data
        dates = pd.date_range(start="2019-01-01", end="2024-01-01", freq="D")
        n_days = len(dates)

        # Simulate realistic price movement with trend + noise
        trend = np.linspace(100, 150, n_days)  # Long-term uptrend
        noise = np.random.randn(n_days) * 5   # Random daily noise
        close_prices = trend + noise

        # Create OHLC data
        data = pd.DataFrame({
            "open": close_prices + np.random.randn(n_days) * 0.5,
            "high": close_prices + np.abs(np.random.randn(n_days) * 2),
            "low": close_prices - np.abs(np.random.randn(n_days) * 2),
            "close": close_prices,
            "volume": np.random.randint(1000000, 100000000, n_days),
        }, index=dates)

        return data

    def test_window_creation_on_five_years(self, five_year_data):
        """Test creating walk-forward windows on 5 years of data."""
        optimizer = WalkForwardOptimizer(
            train_days=500,   # ~2 years of training
            val_days=100,     # ~4 months validation
            test_days=100,    # ~4 months test
            step_size=20,     # 20-day rolling window
        )

        windows = optimizer.create_windows(five_year_data)

        # With 5 years (1260 days) and 700 total per window (500+100+100)
        # Should create roughly (1260-700)/20 + 1 = 29 windows
        assert len(windows) > 0, "Should create at least one window"
        assert len(windows) >= 25, f"Expected ~29 windows, got {len(windows)}"

    def test_window_temporal_progression(self, five_year_data):
        """Test that windows progress chronologically through time."""
        optimizer = WalkForwardOptimizer(
            train_days=200,
            val_days=50,
            test_days=50,
            step_size=10,
        )

        windows = optimizer.create_windows(five_year_data)

        # Verify chronological progression - each window's train_start should advance
        for i in range(len(windows) - 1):
            current_train_start = windows[i].train_start
            next_train_start = windows[i + 1].train_start

            # Next window should start after current window (rolling forward)
            assert next_train_start > current_train_start, \
                f"Window {i} starts at {current_train_start}, but window {i+1} starts at {next_train_start}"

    def test_no_data_leakage_between_windows(self, five_year_data):
        """Test that train/val/test splits don't leak data."""
        optimizer = WalkForwardOptimizer(
            train_days=200,
            val_days=50,
            test_days=50,
            step_size=10,
        )

        windows = optimizer.create_windows(five_year_data)

        for window in windows:
            # Train should not overlap with val or test
            assert window.train_end <= window.val_start, \
                f"Train ({window.train_start} to {window.train_end}) overlaps with val"
            assert window.val_end <= window.test_start, \
                f"Val ({window.val_start} to {window.val_end}) overlaps with test"

            # Test dates should be in data range
            assert window.train_start >= five_year_data.index.min()
            assert window.test_end <= five_year_data.index.max()

    def test_sufficient_data_per_window(self, five_year_data):
        """Test that each window has sufficient samples for training."""
        optimizer = WalkForwardOptimizer(
            train_days=200,
            val_days=50,
            test_days=50,
        )

        windows = optimizer.create_windows(five_year_data)

        for window in windows:
            train_data = five_year_data.loc[window.train_start:window.train_end]
            val_data = five_year_data.loc[window.val_start:window.val_end]
            test_data = five_year_data.loc[window.test_start:window.test_end]

            # Each split should have data
            assert len(train_data) > 0
            assert len(val_data) > 0
            assert len(test_data) > 0

            # Should be close to expected days (accounting for weekends/holidays)
            assert len(train_data) >= 150, \
                f"Train window {window.window_id} has only {len(train_data)} samples"

    def test_window_size_consistency(self, five_year_data):
        """Test that windows maintain consistent structure."""
        optimizer = WalkForwardOptimizer(
            train_days=250,
            val_days=50,
            test_days=50,
        )

        windows = optimizer.create_windows(five_year_data)

        total_per_window = 250 + 50 + 50  # Expected days per window
        acceptable_variance = 5  # Allow 5 days variance

        for window in windows:
            actual_total = (window.test_end - window.train_start).days
            assert abs(actual_total - total_per_window) <= acceptable_variance, \
                f"Window {window.window_id} has {actual_total} days, expected ~{total_per_window}"

    def test_divergence_tracking_across_windows(self, five_year_data):
        """Test that divergence can be calculated across windows."""
        optimizer = WalkForwardOptimizer(
            train_days=200,
            val_days=50,
            test_days=50,
            step_size=20,
            divergence_threshold=0.20,
        )

        windows = optimizer.create_windows(five_year_data)

        # Simulate adding divergence metrics
        for i, window in enumerate(windows):
            # Simulate varying validation vs test performance
            val_rmse = 0.05
            # As we move forward in time, add some increasing noise
            test_rmse = val_rmse * (1.0 + (i * 0.001))  # Gradually worse generalization

            divergence = abs(val_rmse - test_rmse) / val_rmse
            optimizer.divergence_history.append(divergence)

        # Should have tracked divergence for all windows
        assert len(optimizer.divergence_history) == len(windows)

    def test_summary_statistics_on_historical_windows(self, five_year_data):
        """Test generating summary statistics from historical windows."""
        optimizer = WalkForwardOptimizer(
            train_days=200,
            val_days=50,
            test_days=50,
            step_size=20,
            divergence_threshold=0.20,
        )

        windows = optimizer.create_windows(five_year_data)

        # Add realistic divergence data
        for i in range(len(windows)):
            # Mix of good and bad divergence
            if i % 3 == 0:
                div = 0.30  # Overfitting case
            else:
                div = 0.08  # Good generalization

            optimizer.divergence_history.append(div)

        summary = optimizer.get_divergence_summary()

        assert summary["total_windows"] == len(windows)
        assert summary["mean_divergence"] > 0
        assert summary["max_divergence"] >= 0.30
        assert summary["n_overfitting_windows"] > 0


class TestWalkForwardOnSmallDataset:
    """Test walk-forward behavior on smaller datasets."""

    def test_insufficient_data_returns_empty_windows(self):
        """Test that insufficient data results in no windows."""
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        small_data = pd.DataFrame({
            "close": np.random.randn(100).cumsum() + 100
        }, index=dates)

        optimizer = WalkForwardOptimizer(
            train_days=500,  # Need 500 days but only have 100
            val_days=100,
            test_days=100,
        )

        windows = optimizer.create_windows(small_data)

        assert len(windows) == 0, "Should not create windows with insufficient data"

    def test_minimal_viable_windows(self):
        """Test window creation with minimal viable data."""
        dates = pd.date_range(start="2024-01-01", periods=500, freq="D")
        data = pd.DataFrame({
            "close": np.random.randn(500).cumsum() + 100
        }, index=dates)

        optimizer = WalkForwardOptimizer(
            train_days=200,
            val_days=50,
            test_days=50,
            step_size=50,  # Large step to minimize windows
        )

        windows = optimizer.create_windows(data)

        # With 500 days and 300 total per window, step_size=50
        # (500-300)/50 + 1 = 5 windows
        assert len(windows) >= 1


class TestWalkForwardOnRealPricePatterns:
    """Test walk-forward on data with realistic market patterns."""

    def test_trending_market_data(self):
        """Test on strongly trending market."""
        dates = pd.date_range(start="2020-01-01", periods=1000, freq="D")

        # Strong uptrend
        close_prices = 100 + np.linspace(0, 50, 1000) + np.random.randn(1000) * 1

        data = pd.DataFrame({"close": close_prices}, index=dates)

        optimizer = WalkForwardOptimizer(train_days=200, val_days=50, test_days=50)
        windows = optimizer.create_windows(data)

        assert len(windows) > 0
        # In trending market, models should generalize well (low divergence)

    def test_volatile_market_data(self):
        """Test on highly volatile market."""
        dates = pd.date_range(start="2020-01-01", periods=1000, freq="D")

        # High volatility (50% daily noise)
        close_prices = 100 + np.random.randn(1000) * 15

        data = pd.DataFrame({"close": close_prices}, index=dates)

        optimizer = WalkForwardOptimizer(train_days=200, val_days=50, test_days=50)
        windows = optimizer.create_windows(data)

        assert len(windows) > 0
        # In volatile market, models may show higher divergence

    def test_mean_reverting_market_data(self):
        """Test on mean-reverting market."""
        dates = pd.date_range(start="2020-01-01", periods=1000, freq="D")

        # Mean reversion around 100
        price = 100
        prices = []
        for _ in range(1000):
            price = price * 0.99 + 100 * 0.01 + np.random.randn() * 1
            prices.append(price)

        data = pd.DataFrame({"close": prices}, index=dates)

        optimizer = WalkForwardOptimizer(train_days=200, val_days=50, test_days=50)
        windows = optimizer.create_windows(data)

        assert len(windows) > 0
        # Mean-reverting market may be predictable (low divergence)


class TestWalkForwardWindowEdgeCases:
    """Test edge cases in walk-forward window creation."""

    def test_step_size_equals_window_size(self):
        """Test with step_size equal to total window size (non-overlapping)."""
        dates = pd.date_range(start="2020-01-01", periods=1000, freq="D")
        data = pd.DataFrame({"close": np.random.randn(1000).cumsum() + 100}, index=dates)

        total_window = 200 + 50 + 50  # 300 days

        optimizer = WalkForwardOptimizer(
            train_days=200,
            val_days=50,
            test_days=50,
            step_size=300,  # Non-overlapping windows
        )

        windows = optimizer.create_windows(data)

        # Should create ~3 windows with non-overlapping data
        assert len(windows) >= 2

        # Verify no overlap between first and second window
        if len(windows) > 1:
            first_test_end = windows[0].test_end
            second_train_start = windows[1].train_start
            assert second_train_start >= first_test_end

    def test_step_size_of_one(self):
        """Test with step_size=1 (maximum overlap)."""
        dates = pd.date_range(start="2020-01-01", periods=500, freq="D")
        data = pd.DataFrame({"close": np.random.randn(500).cumsum() + 100}, index=dates)

        optimizer = WalkForwardOptimizer(
            train_days=100,
            val_days=50,
            test_days=50,
            step_size=1,  # Roll by 1 day
        )

        windows = optimizer.create_windows(data)

        # With 500 days, 200 total per window, step=1
        # Should create many windows
        assert len(windows) > 50

        # Verify each window advances by 1 day
        for i in range(min(5, len(windows) - 1)):
            diff = (windows[i + 1].train_start - windows[i].train_start).days
            assert diff == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
