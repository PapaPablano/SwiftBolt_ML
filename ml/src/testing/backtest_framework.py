"""
Production-grade backtesting framework with walk-forward validation.

Key Features:
- Walk-forward optimization (prevents overfitting)
- Transaction cost modeling
- Slippage simulation
- Position sizing rules
- Risk metrics (Sharpe, Sortino, Max DD, Calmar)
"""

import pandas as pd
import numpy as np
from typing import Callable, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for backtest execution."""

    initial_capital: float = 100_000.0
    commission_rate: float = 0.001  # 0.1% per trade
    slippage_bps: float = 5.0  # 5 basis points
    max_position_pct: float = 0.10  # Max 10% per position
    risk_free_rate: float = 0.05  # 5% annual risk-free rate
    trading_days_per_year: int = 252


@dataclass
class BacktestResult:
    """Results from a single backtest run."""

    start_date: datetime
    end_date: datetime
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    calmar_ratio: float
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_trade_return: float
    avg_trade_duration_days: float
    equity_curve: pd.Series = field(repr=False)
    trades: pd.DataFrame = field(repr=False)
    daily_returns: pd.Series = field(repr=False)

    def summary(self) -> str:
        """Return formatted summary string."""
        return f"""
Backtest Results ({self.start_date.date()} to {self.end_date.date()})
{'='*60}
Total Return:       {self.total_return:>10.2%}
Annualized Return:  {self.annualized_return:>10.2%}
Sharpe Ratio:       {self.sharpe_ratio:>10.2f}
Sortino Ratio:      {self.sortino_ratio:>10.2f}
Max Drawdown:       {self.max_drawdown:>10.2%}
Calmar Ratio:       {self.calmar_ratio:>10.2f}
Win Rate:           {self.win_rate:>10.2%}
Profit Factor:      {self.profit_factor:>10.2f}
Total Trades:       {self.total_trades:>10d}
Avg Trade Return:   {self.avg_trade_return:>10.2%}
Avg Duration:       {self.avg_trade_duration_days:>10.1f} days
"""


class BacktestFramework:
    """
    Production-grade backtesting with walk-forward validation.

    Example usage:
        ```python
        framework = BacktestFramework()

        def my_signal_generator(data: pd.DataFrame) -> pd.Series:
            # Return series of signals: 1 = buy, -1 = sell, 0 = hold
            signals = pd.Series(0, index=data.index)
            signals[data['rsi'] < 30] = 1
            signals[data['rsi'] > 70] = -1
            return signals

        result = framework.run_backtest(data, my_signal_generator)
        print(result.summary())
        ```
    """

    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()

    def run_backtest(
        self,
        data: pd.DataFrame,
        signal_generator: Callable[[pd.DataFrame], pd.Series],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> BacktestResult:
        """
        Run backtest with realistic execution simulation.

        Args:
            data: OHLCV DataFrame with DatetimeIndex
            signal_generator: Function that returns signals (-1, 0, 1)
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)

        Returns:
            BacktestResult with comprehensive metrics
        """
        # Ensure DatetimeIndex
        if not isinstance(data.index, pd.DatetimeIndex):
            data = data.copy()
            data.index = pd.to_datetime(data.index)

        # Filter date range
        if start_date:
            data = data[data.index >= start_date]
        if end_date:
            data = data[data.index <= end_date]

        if len(data) < 2:
            raise ValueError("Insufficient data for backtest")

        # Generate signals
        signals = signal_generator(data)

        # Run simulation
        equity_curve, trades = self._simulate_trading(data, signals)

        # Calculate metrics
        return self._calculate_metrics(equity_curve, trades, data)

    def walk_forward_backtest(
        self,
        data: pd.DataFrame,
        model_trainer: Callable[[pd.DataFrame], Callable[[pd.DataFrame], pd.Series]],
        n_splits: int = 5,
        train_pct: float = 0.7,
    ) -> list[BacktestResult]:
        """
        Walk-forward optimization backtest.

        For each period:
        1. Train model on in-sample data
        2. Generate signals on out-of-sample data
        3. Backtest out-of-sample period

        This prevents overfitting by ensuring model never sees future data.

        Args:
            data: OHLCV DataFrame with DatetimeIndex
            model_trainer: Function that takes training data and returns
                a signal generator
            n_splits: Number of walk-forward splits
            train_pct: Percentage of each split used for training

        Returns:
            List of BacktestResult for each out-of-sample period
        """
        results = []
        n = len(data)
        split_size = n // n_splits

        for i in range(n_splits):
            # Define windows
            train_start = 0
            train_end = int((i + 1) * split_size * train_pct)
            test_start = train_end
            test_end = min((i + 1) * split_size, n)

            if test_start >= test_end:
                continue

            train_data = data.iloc[train_start:train_end]
            test_data = data.iloc[test_start:test_end]

            if len(train_data) < 20 or len(test_data) < 5:
                msg = f"Fold {i+1}/{n_splits}: Insufficient data, skipping"
                logger.warning(msg)
                continue

            # Train model on in-sample
            try:
                signal_generator = model_trainer(train_data)
            except Exception as e:
                logger.error(f"Fold {i+1}/{n_splits}: Training failed: {e}")
                continue

            # Backtest on out-of-sample
            try:
                result = self.run_backtest(test_data, signal_generator)
                results.append(result)

                logger.info(
                    f"Fold {i+1}/{n_splits}: "
                    f"Return={result.total_return:.2%}, "
                    f"Sharpe={result.sharpe_ratio:.2f}, "
                    f"MaxDD={result.max_drawdown:.2%}"
                )
            except Exception as e:
                msg = f"Fold {i+1}/{n_splits}: Backtest failed: {e}"
                logger.error(msg)
                continue

        return results

    def _simulate_trading(
        self,
        data: pd.DataFrame,
        signals: pd.Series,
    ) -> tuple[pd.Series, pd.DataFrame]:
        """Simulate trading with transaction costs and slippage."""
        capital = self.config.initial_capital
        position = 0
        entry_price = 0.0
        entry_date = None

        equity_curve = []
        trades = []

        for i, (idx, row) in enumerate(data.iterrows()):
            signal = signals.iloc[i] if i < len(signals) else 0
            price = row["close"]

            # Apply slippage
            if signal > 0:
                exec_price = price * (1 + self.config.slippage_bps / 10000)
            elif signal < 0:
                exec_price = price * (1 - self.config.slippage_bps / 10000)
            else:
                exec_price = price

            # Position sizing
            if exec_price > 0:
                pct = self.config.max_position_pct
                max_shares = int(capital * pct / exec_price)
            else:
                max_shares = 0

            # Execute trades
            if signal > 0 and position <= 0:  # Buy signal
                shares = max_shares
                if shares > 0:
                    commission = self.config.commission_rate
                    cost = shares * exec_price * (1 + commission)
                    if cost <= capital:
                        capital -= cost
                        position = shares
                        entry_price = exec_price
                        entry_date = idx
                        trades.append(
                            {
                                "entry_date": idx,
                                "entry_price": exec_price,
                                "shares": shares,
                                "type": "LONG",
                            }
                        )

            elif signal < 0 and position > 0:  # Sell signal
                commission = self.config.commission_rate
                proceeds = position * exec_price * (1 - commission)
                capital += proceeds

                # Complete the trade record
                if trades and "exit_date" not in trades[-1]:
                    trades[-1]["exit_date"] = idx
                    trades[-1]["exit_price"] = exec_price
                    trades[-1]["proceeds"] = proceeds
                    entry_cost = position * entry_price * (1 + commission)
                    trades[-1]["pnl"] = proceeds - entry_cost
                    trades[-1]["return"] = (exec_price / entry_price) - 1
                    duration = (idx - entry_date).days if entry_date else 0
                    trades[-1]["duration_days"] = duration

                position = 0
                entry_price = 0.0
                entry_date = None

            # Track equity
            equity = capital + (position * price)
            equity_curve.append({"date": idx, "equity": equity})

        # Close any open position at end
        if position > 0:
            final_price = data["close"].iloc[-1]
            commission = self.config.commission_rate
            proceeds = position * final_price * (1 - commission)
            capital += proceeds

            if trades and "exit_date" not in trades[-1]:
                trades[-1]["exit_date"] = data.index[-1]
                trades[-1]["exit_price"] = final_price
                trades[-1]["proceeds"] = proceeds
                entry_cost = position * entry_price * (1 + commission)
                trades[-1]["pnl"] = proceeds - entry_cost
                trades[-1]["return"] = (final_price / entry_price) - 1
                duration = (data.index[-1] - entry_date).days if entry_date else 0
                trades[-1]["duration_days"] = duration

            equity_curve[-1]["equity"] = capital

        equity_df = pd.DataFrame(equity_curve).set_index("date")
        if trades:
            trades_df = pd.DataFrame(trades)
        else:
            trades_df = pd.DataFrame()

        return equity_df["equity"], trades_df

    def _calculate_metrics(
        self,
        equity_curve: pd.Series,
        trades_df: pd.DataFrame,
        data: pd.DataFrame,
    ) -> BacktestResult:
        """Calculate comprehensive backtest metrics."""
        # Daily returns
        daily_returns = equity_curve.pct_change().dropna()

        # Total return
        final_equity = equity_curve.iloc[-1]
        total_return = (final_equity / self.config.initial_capital) - 1

        # Annualized return
        n_days = (data.index[-1] - data.index[0]).days
        n_years = n_days / 365.25
        if n_years > 0:
            annualized_return = (1 + total_return) ** (1 / n_years) - 1
        else:
            annualized_return = 0

        # Sharpe ratio (annualized)
        trading_days = self.config.trading_days_per_year
        rf_daily = self.config.risk_free_rate / trading_days
        excess_returns = daily_returns - rf_daily
        sharpe = (
            (excess_returns.mean() / excess_returns.std())
            * np.sqrt(self.config.trading_days_per_year)
            if excess_returns.std() > 0
            else 0
        )

        # Sortino ratio (downside deviation only)
        downside_returns = daily_returns[daily_returns < 0]
        if len(downside_returns) > 0:
            downside_std = downside_returns.std()
        else:
            downside_std = 0
        sortino = (
            (daily_returns.mean() / downside_std) * np.sqrt(self.config.trading_days_per_year)
            if downside_std > 0
            else 0
        )

        # Max drawdown
        rolling_max = equity_curve.expanding().max()
        drawdown = (equity_curve - rolling_max) / rolling_max
        max_drawdown = drawdown.min()

        # Calmar ratio
        calmar = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0

        # Trade statistics
        if len(trades_df) > 0 and "pnl" in trades_df.columns:
            completed_trades = trades_df[trades_df["pnl"].notna()]
            n_trades = len(completed_trades)

            if n_trades > 0:
                winning_trades = completed_trades[completed_trades["pnl"] > 0]
                losing_trades = completed_trades[completed_trades["pnl"] < 0]

                win_rate = len(winning_trades) / n_trades
                if len(winning_trades) > 0:
                    gross_profit = winning_trades["pnl"].sum()
                else:
                    gross_profit = 0
                if len(losing_trades) > 0:
                    gross_loss = abs(losing_trades["pnl"].sum())
                else:
                    gross_loss = 0
                if gross_loss > 0:
                    profit_factor = gross_profit / gross_loss
                else:
                    profit_factor = float("inf")
                avg_trade_return = completed_trades["return"].mean()
                avg_duration = completed_trades["duration_days"].mean()
            else:
                win_rate = 0
                profit_factor = 0
                avg_trade_return = 0
                avg_duration = 0
        else:
            n_trades = 0
            win_rate = 0
            profit_factor = 0
            avg_trade_return = 0
            avg_duration = 0

        return BacktestResult(
            start_date=data.index[0].to_pydatetime(),
            end_date=data.index[-1].to_pydatetime(),
            total_return=total_return,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_drawdown,
            calmar_ratio=calmar,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=n_trades,
            avg_trade_return=avg_trade_return,
            avg_trade_duration_days=avg_duration,
            equity_curve=equity_curve,
            trades=trades_df,
            daily_returns=daily_returns,
        )

    def aggregate_walk_forward_results(
        self,
        results: list[BacktestResult],
    ) -> dict:
        """Aggregate metrics across walk-forward folds."""
        if not results:
            return {}

        return {
            "n_folds": len(results),
            "total_return_mean": np.mean([r.total_return for r in results]),
            "total_return_std": np.std([r.total_return for r in results]),
            "sharpe_mean": np.mean([r.sharpe_ratio for r in results]),
            "sharpe_std": np.std([r.sharpe_ratio for r in results]),
            "max_drawdown_mean": np.mean([r.max_drawdown for r in results]),
            "max_drawdown_worst": min([r.max_drawdown for r in results]),
            "win_rate_mean": np.mean([r.win_rate for r in results]),
            "total_trades": sum([r.total_trades for r in results]),
        }
