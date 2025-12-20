"""Tests for the backtesting framework."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from src.testing.backtest_framework import (
    BacktestFramework,
    BacktestConfig,
    BacktestResult,
)


@pytest.fixture
def sample_ohlcv_data():
    """Generate sample OHLCV data for testing."""
    np.random.seed(42)
    dates = pd.date_range(start='2023-01-01', periods=252, freq='D')

    # Generate random walk price data
    returns = np.random.normal(0.0005, 0.02, len(dates))
    prices = 100 * np.cumprod(1 + returns)

    df = pd.DataFrame({
        'open': prices * (1 + np.random.uniform(-0.01, 0.01, len(dates))),
        'high': prices * (1 + np.random.uniform(0, 0.02, len(dates))),
        'low': prices * (1 - np.random.uniform(0, 0.02, len(dates))),
        'close': prices,
        'volume': np.random.randint(1000000, 10000000, len(dates)),
    }, index=dates)

    return df


@pytest.fixture
def simple_signal_generator():
    """Simple RSI-based signal generator for testing."""
    def generator(data: pd.DataFrame) -> pd.Series:
        # Calculate simple RSI
        delta = data['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        # Generate signals
        signals = pd.Series(0, index=data.index)
        signals[rsi < 30] = 1   # Buy when oversold
        signals[rsi > 70] = -1  # Sell when overbought

        return signals

    return generator


class TestBacktestConfig:
    """Tests for BacktestConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = BacktestConfig()

        assert config.initial_capital == 100_000.0
        assert config.commission_rate == 0.001
        assert config.slippage_bps == 5.0
        assert config.max_position_pct == 0.10
        assert config.risk_free_rate == 0.05
        assert config.trading_days_per_year == 252

    def test_custom_config(self):
        """Test custom configuration."""
        config = BacktestConfig(
            initial_capital=50_000,
            commission_rate=0.002,
            slippage_bps=10,
        )

        assert config.initial_capital == 50_000
        assert config.commission_rate == 0.002
        assert config.slippage_bps == 10


class TestBacktestFramework:
    """Tests for BacktestFramework."""

    def test_run_backtest_basic(
        self, sample_ohlcv_data, simple_signal_generator
    ):
        """Test basic backtest execution."""
        framework = BacktestFramework()
        result = framework.run_backtest(
            sample_ohlcv_data,
            simple_signal_generator,
        )

        assert isinstance(result, BacktestResult)
        assert result.start_date is not None
        assert result.end_date is not None
        assert isinstance(result.total_return, float)
        assert isinstance(result.sharpe_ratio, float)
        assert isinstance(result.max_drawdown, float)
        assert result.max_drawdown <= 0  # Drawdown is negative

    def test_run_backtest_with_date_filter(
        self, sample_ohlcv_data, simple_signal_generator
    ):
        """Test backtest with date filtering."""
        framework = BacktestFramework()
        result = framework.run_backtest(
            sample_ohlcv_data,
            simple_signal_generator,
            start_date='2023-03-01',
            end_date='2023-09-01',
        )

        assert result.start_date >= datetime(2023, 3, 1)
        assert result.end_date <= datetime(2023, 9, 2)

    def test_equity_curve_generated(
        self, sample_ohlcv_data, simple_signal_generator
    ):
        """Test that equity curve is generated."""
        framework = BacktestFramework()
        result = framework.run_backtest(
            sample_ohlcv_data,
            simple_signal_generator,
        )

        assert len(result.equity_curve) > 0
        assert result.equity_curve.iloc[0] > 0

    def test_trades_recorded(
        self, sample_ohlcv_data, simple_signal_generator
    ):
        """Test that trades are recorded."""
        framework = BacktestFramework()
        result = framework.run_backtest(
            sample_ohlcv_data,
            simple_signal_generator,
        )

        # Should have some trades with RSI strategy
        assert isinstance(result.trades, pd.DataFrame)

    def test_walk_forward_backtest(
        self, sample_ohlcv_data
    ):
        """Test walk-forward backtest."""
        framework = BacktestFramework()

        def model_trainer(train_data):
            # Simple moving average crossover
            def signal_gen(data):
                sma_fast = data['close'].rolling(10).mean()
                sma_slow = data['close'].rolling(30).mean()
                signals = pd.Series(0, index=data.index)
                signals[sma_fast > sma_slow] = 1
                signals[sma_fast < sma_slow] = -1
                return signals
            return signal_gen

        results = framework.walk_forward_backtest(
            sample_ohlcv_data,
            model_trainer,
            n_splits=3,
            train_pct=0.7,
        )

        assert len(results) > 0
        for result in results:
            assert isinstance(result, BacktestResult)

    def test_aggregate_results(self, sample_ohlcv_data):
        """Test aggregation of walk-forward results."""
        framework = BacktestFramework()

        def model_trainer(train_data):
            def signal_gen(data):
                signals = pd.Series(0, index=data.index)
                signals.iloc[::10] = 1
                signals.iloc[5::10] = -1
                return signals
            return signal_gen

        results = framework.walk_forward_backtest(
            sample_ohlcv_data,
            model_trainer,
            n_splits=3,
        )

        aggregated = framework.aggregate_walk_forward_results(results)

        assert 'n_folds' in aggregated
        assert 'total_return_mean' in aggregated
        assert 'sharpe_mean' in aggregated
        assert 'max_drawdown_mean' in aggregated

    def test_custom_config(self, sample_ohlcv_data, simple_signal_generator):
        """Test backtest with custom configuration."""
        config = BacktestConfig(
            initial_capital=50_000,
            commission_rate=0.002,
            max_position_pct=0.20,
        )
        framework = BacktestFramework(config)

        result = framework.run_backtest(
            sample_ohlcv_data,
            simple_signal_generator,
        )

        assert isinstance(result, BacktestResult)


class TestBacktestResult:
    """Tests for BacktestResult."""

    def test_summary_output(self, sample_ohlcv_data, simple_signal_generator):
        """Test summary string generation."""
        framework = BacktestFramework()
        result = framework.run_backtest(
            sample_ohlcv_data,
            simple_signal_generator,
        )

        summary = result.summary()

        assert 'Total Return' in summary
        assert 'Sharpe Ratio' in summary
        assert 'Max Drawdown' in summary
        assert 'Win Rate' in summary


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_insufficient_data(self):
        """Test handling of insufficient data."""
        framework = BacktestFramework()

        # Only 1 row of data
        data = pd.DataFrame({
            'open': [100],
            'high': [101],
            'low': [99],
            'close': [100],
            'volume': [1000000],
        }, index=pd.date_range('2023-01-01', periods=1))

        def signal_gen(d):
            return pd.Series(0, index=d.index)

        with pytest.raises(ValueError, match="Insufficient data"):
            framework.run_backtest(data, signal_gen)

    def test_no_trades_generated(self, sample_ohlcv_data):
        """Test handling when no trades are generated."""
        framework = BacktestFramework()

        # Signal generator that never trades
        def no_trade_signal(data):
            return pd.Series(0, index=data.index)

        result = framework.run_backtest(sample_ohlcv_data, no_trade_signal)

        assert result.total_trades == 0
        assert result.win_rate == 0
        assert result.profit_factor == 0
