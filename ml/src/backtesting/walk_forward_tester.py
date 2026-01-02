"""
Walk-Forward Backtest Engine
============================
Implements proper time-series backtesting with no lookahead bias.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class BacktestMetrics:
    """Container for backtest results."""

    total_trades: int
    winning_trades: int
    losing_trades: int
    accuracy: float
    precision: float
    recall: float
    f1_score: float

    # Financial metrics
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    avg_win_size: float
    avg_loss_size: float
    profit_factor: float

    # Metadata
    start_date: datetime
    end_date: datetime
    test_periods: int

    def __str__(self) -> str:
        return f"""
        Backtest Results
        ================
        Accuracy: {self.accuracy:.2%}
        Precision: {self.precision:.2%}
        Recall: {self.recall:.2%}
        F1 Score: {self.f1_score:.2f}

        Win Rate: {self.win_rate:.2%}
        Sharpe: {self.sharpe_ratio:.2f}
        Sortino: {self.sortino_ratio:.2f}
        Max Drawdown: {self.max_drawdown:.2%}
        Profit Factor: {self.profit_factor:.2f}

        Period: {self.start_date.date()} to {self.end_date.date()}
        Test Periods: {self.test_periods}
        """


class WalkForwardBacktester:
    """
    Implements walk-forward analysis for time-series ML models.

    Parameters:
    -----------
    train_window: int (default: 252)
        Number of bars for training (1 year of daily bars)
    test_window: int (default: 21)
        Number of bars for testing (1 month of daily bars)
    step_size: int (default: 5)
        Number of bars to roll forward (weekly retraining)
    horizon: str (optional)
        Forecast horizon for auto-configured windows
    """

    # Horizon-specific window configuration
    # Longer horizons need more training data and longer test windows
    HORIZON_WINDOWS = {
        "1D": {"train": 126, "test": 10, "step": 2},   # 6mo train, 2wk test
        "1W": {"train": 252, "test": 25, "step": 5},   # 1yr train, 5wk test
        "1M": {"train": 504, "test": 60, "step": 20},  # 2yr train, 3mo test
        "2M": {"train": 504, "test": 90, "step": 30},  # 2yr train, 4.5mo test
        "3M": {"train": 756, "test": 120, "step": 40}, # 3yr train, 6mo test
        "4M": {"train": 756, "test": 150, "step": 50}, # 3yr train, 7.5mo test
        "5M": {"train": 756, "test": 165, "step": 55}, # 3yr train, 8mo test
        "6M": {"train": 756, "test": 180, "step": 60}, # 3yr train, 9mo test
    }

    def __init__(
        self,
        train_window: int = 252,
        test_window: int = 21,
        step_size: int = 5,
        horizon: str | None = None,
    ) -> None:
        # Use horizon-optimized windows if provided
        if horizon and horizon in self.HORIZON_WINDOWS:
            config = self.HORIZON_WINDOWS[horizon]
            self.train_window = config["train"]
            self.test_window = config["test"]
            self.step_size = config["step"]
            logger.info(f"Using horizon-optimized windows for {horizon}: {config}")
        else:
            self.train_window = train_window
            self.test_window = test_window
            self.step_size = step_size

    def backtest(
        self,
        df: pd.DataFrame,
        forecaster: Any,
        horizons: List[str] | None = None,
    ) -> BacktestMetrics:
        """
        Run walk-forward backtest.

        Args:
            df: DataFrame with OHLCV + technical indicators
            forecaster: Trained forecaster with predict() method
            horizons: Forecast horizons to test

        Returns:
            BacktestMetrics with aggregated results
        """

        if horizons is None:
            horizons = ["1D"]

        all_predictions: List[str] = []
        all_actuals: List[str] = []
        all_returns: List[float] = []

        min_data_required = self.train_window + self.test_window
        if len(df) < min_data_required:
            raise ValueError(
                f"Insufficient data: {len(df)} bars "
                f"(need {min_data_required})"
            )

        # Walk forward through time
        n_windows = (len(df) - self.train_window) // self.step_size

        for window_idx in range(n_windows):
            start_train = window_idx * self.step_size
            end_train = start_train + self.train_window
            end_test = min(end_train + self.test_window, len(df))

            if end_test - end_train < 1:
                break

            train_df = df.iloc[start_train:end_train].copy()
            test_df = df.iloc[end_train:end_test].copy()

            # Train model
            try:
                X_train, y_train = forecaster.prepare_training_data(
                    train_df,
                    horizon_days=self._get_horizon_days(horizons[0]),
                )
                forecaster.train(X_train, y_train)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Training failed in window %s: %s",
                    window_idx,
                    exc,
                )
                continue

            # Test on test window
            for test_idx in range(len(test_df)):
                test_point = test_df.iloc[test_idx:test_idx + 1]

                try:
                    label, confidence, proba = forecaster.predict(test_point)

                    if test_idx + 1 < len(test_df):
                        current_price = test_point["close"].iloc[0]
                        next_price = test_df["close"].iloc[test_idx + 1]
                        actual_return = (
                            (next_price - current_price) / current_price
                        )

                        actual_label = self._return_to_label(actual_return)

                        all_predictions.append(label)
                        all_actuals.append(actual_label)
                        all_returns.append(actual_return)
                except Exception as exc:  # noqa: BLE001
                    logger.debug(f"Prediction failed: {exc}")
                    continue

        if not all_predictions:
            raise ValueError("No valid predictions generated")

        return self._compute_metrics(
            all_predictions,
            all_actuals,
            all_returns,
            df["ts"].iloc[0],
            df["ts"].iloc[-1],
            n_windows,
        )

    def _get_horizon_days(self, horizon: str) -> int:
        if horizon == "1D":
            return 1
        if horizon == "1W":
            return 5
        if horizon == "1M":
            return 20
        return 1

    def _return_to_label(self, ret: float) -> str:
        if ret > 0.02:
            return "bullish"
        if ret < -0.02:
            return "bearish"
        return "neutral"

    def _compute_metrics(
        self,
        predictions: List[str],
        actuals: List[str],
        returns: List[float],
        start_date: datetime,
        end_date: datetime,
        n_windows: int,
    ) -> BacktestMetrics:
        from sklearn.metrics import (
            accuracy_score,
            f1_score,
            precision_score,
            recall_score,
        )

        accuracy = accuracy_score(actuals, predictions)
        precision = precision_score(
            actuals,
            predictions,
            labels=["bullish", "neutral", "bearish"],
            average="weighted",
            zero_division=0,
        )
        recall = recall_score(
            actuals,
            predictions,
            labels=["bullish", "neutral", "bearish"],
            average="weighted",
            zero_division=0,
        )
        f1 = f1_score(
            actuals,
            predictions,
            labels=["bullish", "neutral", "bearish"],
            average="weighted",
            zero_division=0,
        )

        returns_array = np.array(returns)
        winning_returns = returns_array[returns_array > 0]
        losing_returns = np.abs(returns_array[returns_array < 0])

        total_trades = len(returns)
        winning_trades = len(winning_returns)
        losing_trades = len(losing_returns)
        win_rate = (
            winning_trades / total_trades
            if total_trades > 0
            else 0
        )

        excess_returns = returns_array
        std_excess = np.std(excess_returns)
        sharpe_ratio = (
            np.mean(excess_returns) / std_excess * np.sqrt(252)
            if std_excess > 0
            else 0
        )

        downside_returns = excess_returns[excess_returns < 0]
        downside_std = (
            np.std(downside_returns)
            if len(downside_returns) > 0
            else 0
        )
        sortino_ratio = (
            np.mean(excess_returns) / downside_std * np.sqrt(252)
            if downside_std > 0
            else 0
        )

        cumulative_returns = np.cumprod(1 + returns_array) - 1
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdown = cumulative_returns - running_max
        max_drawdown = np.min(drawdown) if len(drawdown) else 0

        avg_win = np.mean(winning_returns) if len(winning_returns) > 0 else 0
        avg_loss = np.mean(losing_returns) if len(losing_returns) > 0 else 1
        profit_factor = (
            (avg_win * winning_trades) / (avg_loss * losing_trades)
            if losing_trades > 0
            else 1
        )

        return BacktestMetrics(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1_score=f1,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            avg_win_size=avg_win,
            avg_loss_size=avg_loss,
            profit_factor=profit_factor,
            start_date=start_date,
            end_date=end_date,
            test_periods=n_windows,
        )
