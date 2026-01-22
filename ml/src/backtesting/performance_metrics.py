"""Performance metrics calculation for backtesting.

Calculates key metrics for evaluating trading strategies:
- Total return, CAGR
- Sharpe ratio, Sortino ratio
- Maximum drawdown
- Win rate, profit factor
- Risk-adjusted returns

Usage:
    from src.backtesting.performance_metrics import PerformanceMetrics
    
    metrics = PerformanceMetrics()
    
    # Calculate from equity curve
    results = metrics.calculate_all(equity_curve, risk_free_rate=0.05)
    
    print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
    print(f"Max Drawdown: {results['max_drawdown']:.2%}")

References:
    - Sharpe, W. F. (1966). "Mutual Fund Performance"
    - Sortino, F. A. (1994). "Downside Risk"
"""

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """Calculate performance metrics for trading strategies."""
    
    @staticmethod
    def total_return(equity_curve: pd.Series) -> float:
        """Calculate total return.
        
        Args:
            equity_curve: Series of portfolio values over time
        
        Returns:
            Total return as decimal (e.g., 0.25 for 25%)
        """
        if len(equity_curve) < 2:
            return 0.0
        
        return (equity_curve.iloc[-1] - equity_curve.iloc[0]) / equity_curve.iloc[0]
    
    @staticmethod
    def cagr(equity_curve: pd.Series, periods_per_year: int = 252) -> float:
        """Calculate Compound Annual Growth Rate (CAGR).
        
        Formula: CAGR = (End Value / Start Value)^(1/years) - 1
        
        Args:
            equity_curve: Series of portfolio values over time
            periods_per_year: Number of periods per year (252 for daily, 12 for monthly)
        
        Returns:
            CAGR as decimal
        """
        if len(equity_curve) < 2:
            return 0.0
        
        start_value = equity_curve.iloc[0]
        end_value = equity_curve.iloc[-1]
        num_periods = len(equity_curve)
        
        years = num_periods / periods_per_year
        
        if years <= 0 or start_value <= 0:
            return 0.0
        
        cagr = (end_value / start_value) ** (1 / years) - 1
        
        return float(cagr)
    
    @staticmethod
    def sharpe_ratio(
        returns: pd.Series,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252
    ) -> float:
        """Calculate Sharpe Ratio.
        
        Formula: Sharpe = (Mean Return - Risk Free Rate) / Std Dev of Returns
        
        Args:
            returns: Series of returns
            risk_free_rate: Annual risk-free rate (default: 0)
            periods_per_year: Number of periods per year for annualization
        
        Returns:
            Annualized Sharpe ratio
        """
        if len(returns) < 2:
            return 0.0
        
        # Annualize risk-free rate to match return frequency
        rf_per_period = risk_free_rate / periods_per_year
        
        excess_returns = returns - rf_per_period
        
        if excess_returns.std() == 0:
            return 0.0
        
        # Annualize
        sharpe = (excess_returns.mean() / excess_returns.std()) * np.sqrt(periods_per_year)
        
        return float(sharpe)
    
    @staticmethod
    def sortino_ratio(
        returns: pd.Series,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252
    ) -> float:
        """Calculate Sortino Ratio (Sharpe using only downside deviation).
        
        Formula: Sortino = (Mean Return - Risk Free Rate) / Downside Deviation
        
        Args:
            returns: Series of returns
            risk_free_rate: Annual risk-free rate (default: 0)
            periods_per_year: Number of periods per year for annualization
        
        Returns:
            Annualized Sortino ratio
        """
        if len(returns) < 2:
            return 0.0
        
        # Annualize risk-free rate
        rf_per_period = risk_free_rate / periods_per_year
        
        excess_returns = returns - rf_per_period
        
        # Downside deviation (only negative returns)
        downside_returns = excess_returns[excess_returns < 0]
        
        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return 0.0
        
        # Annualize
        sortino = (excess_returns.mean() / downside_returns.std()) * np.sqrt(periods_per_year)
        
        return float(sortino)
    
    @staticmethod
    def max_drawdown(equity_curve: pd.Series) -> Dict[str, float]:
        """Calculate maximum drawdown and related metrics.
        
        Args:
            equity_curve: Series of portfolio values over time
        
        Returns:
            Dictionary with:
            - max_drawdown: Maximum drawdown (as decimal, e.g., -0.25 for -25%)
            - max_drawdown_duration: Duration of max drawdown (in periods)
            - current_drawdown: Current drawdown from peak
        """
        if len(equity_curve) < 2:
            return {
                'max_drawdown': 0.0,
                'max_drawdown_duration': 0,
                'current_drawdown': 0.0
            }
        
        # Calculate running maximum
        running_max = equity_curve.expanding().max()
        
        # Calculate drawdown at each point
        drawdown = (equity_curve - running_max) / running_max
        
        # Maximum drawdown
        max_dd = float(drawdown.min())
        
        # Find duration of maximum drawdown
        max_dd_end_idx = drawdown.idxmin()
        
        # Find start of max drawdown period (last time equity was at peak before max dd)
        drawdown_period = drawdown.loc[:max_dd_end_idx]
        max_dd_start_idx = drawdown_period[drawdown_period == 0].index[-1] if any(drawdown_period == 0) else drawdown.index[0]
        
        max_dd_duration = len(equity_curve.loc[max_dd_start_idx:max_dd_end_idx])
        
        # Current drawdown
        current_dd = float(drawdown.iloc[-1])
        
        return {
            'max_drawdown': max_dd,
            'max_drawdown_duration': max_dd_duration,
            'current_drawdown': current_dd
        }
    
    @staticmethod
    def win_rate(trade_returns: pd.Series) -> float:
        """Calculate win rate (% of profitable trades).
        
        Args:
            trade_returns: Series of per-trade returns
        
        Returns:
            Win rate as decimal (e.g., 0.60 for 60%)
        """
        if len(trade_returns) == 0:
            return 0.0
        
        winning_trades = (trade_returns > 0).sum()
        
        return float(winning_trades / len(trade_returns))
    
    @staticmethod
    def profit_factor(trade_returns: pd.Series) -> float:
        """Calculate profit factor (gross profit / gross loss).
        
        Args:
            trade_returns: Series of per-trade returns
        
        Returns:
            Profit factor (values > 1.0 indicate profitable strategy)
        """
        if len(trade_returns) == 0:
            return 0.0
        
        gross_profit = trade_returns[trade_returns > 0].sum()
        gross_loss = abs(trade_returns[trade_returns < 0].sum())
        
        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0
        
        return float(gross_profit / gross_loss)
    
    @staticmethod
    def calmar_ratio(equity_curve: pd.Series, periods_per_year: int = 252) -> float:
        """Calculate Calmar Ratio (CAGR / Max Drawdown).
        
        Args:
            equity_curve: Series of portfolio values over time
            periods_per_year: Number of periods per year
        
        Returns:
            Calmar ratio
        """
        cagr_value = PerformanceMetrics.cagr(equity_curve, periods_per_year)
        dd_metrics = PerformanceMetrics.max_drawdown(equity_curve)
        max_dd = abs(dd_metrics['max_drawdown'])
        
        if max_dd == 0:
            return 0.0
        
        return float(cagr_value / max_dd)
    
    @staticmethod
    def volatility(returns: pd.Series, periods_per_year: int = 252) -> float:
        """Calculate annualized volatility.
        
        Args:
            returns: Series of returns
            periods_per_year: Number of periods per year for annualization
        
        Returns:
            Annualized volatility (standard deviation)
        """
        if len(returns) < 2:
            return 0.0
        
        return float(returns.std() * np.sqrt(periods_per_year))
    
    @staticmethod
    def calculate_all(
        equity_curve: pd.Series,
        risk_free_rate: float = 0.05,
        periods_per_year: int = 252,
        trade_returns: Optional[pd.Series] = None
    ) -> Dict[str, float]:
        """Calculate all performance metrics.
        
        Args:
            equity_curve: Series of portfolio values over time
            risk_free_rate: Annual risk-free rate (default: 5%)
            periods_per_year: Number of periods per year (252 for daily)
            trade_returns: Optional series of per-trade returns for win rate, profit factor
        
        Returns:
            Dictionary with all performance metrics
        """
        # Calculate returns from equity curve
        returns = equity_curve.pct_change().dropna()
        
        # Basic metrics
        total_ret = PerformanceMetrics.total_return(equity_curve)
        cagr_val = PerformanceMetrics.cagr(equity_curve, periods_per_year)
        vol = PerformanceMetrics.volatility(returns, periods_per_year)
        
        # Risk-adjusted metrics
        sharpe = PerformanceMetrics.sharpe_ratio(returns, risk_free_rate, periods_per_year)
        sortino = PerformanceMetrics.sortino_ratio(returns, risk_free_rate, periods_per_year)
        calmar = PerformanceMetrics.calmar_ratio(equity_curve, periods_per_year)
        
        # Drawdown metrics
        dd_metrics = PerformanceMetrics.max_drawdown(equity_curve)
        
        # Compile results
        results = {
            'total_return': total_ret,
            'cagr': cagr_val,
            'volatility': vol,
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'calmar_ratio': calmar,
            'max_drawdown': dd_metrics['max_drawdown'],
            'max_drawdown_duration': dd_metrics['max_drawdown_duration'],
            'current_drawdown': dd_metrics['current_drawdown'],
        }
        
        # Add trade-level metrics if provided
        if trade_returns is not None and len(trade_returns) > 0:
            results['win_rate'] = PerformanceMetrics.win_rate(trade_returns)
            results['profit_factor'] = PerformanceMetrics.profit_factor(trade_returns)
            results['avg_trade_return'] = float(trade_returns.mean())
            results['num_trades'] = len(trade_returns)
        
        return results


if __name__ == "__main__":
    # Example usage and self-test
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("Performance Metrics - Self Test")
    print("=" * 70)
    
    # Create sample equity curve
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', '2024-01-01', freq='D')
    
    # Simulated equity curve with some volatility
    returns = np.random.randn(len(dates)) * 0.01 + 0.0005  # Mean positive return
    equity = 10000 * (1 + returns).cumprod()
    equity_curve = pd.Series(equity, index=dates)
    
    # Calculate metrics
    metrics = PerformanceMetrics()
    results = metrics.calculate_all(equity_curve, risk_free_rate=0.05)
    
    # Display results
    print("\n📊 Performance Metrics:")
    print(f"Total Return: {results['total_return']:.2%}")
    print(f"CAGR: {results['cagr']:.2%}")
    print(f"Volatility: {results['volatility']:.2%}")
    print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
    print(f"Sortino Ratio: {results['sortino_ratio']:.2f}")
    print(f"Calmar Ratio: {results['calmar_ratio']:.2f}")
    print(f"Max Drawdown: {results['max_drawdown']:.2%}")
    print(f"Max DD Duration: {results['max_drawdown_duration']} days")
    print(f"Current Drawdown: {results['current_drawdown']:.2%}")
    
    # Test with trade returns
    print("\n📊 Trade-Level Metrics:")
    trade_returns = pd.Series([0.05, -0.02, 0.03, -0.01, 0.04, -0.03, 0.06])
    
    trade_metrics = {
        'win_rate': metrics.win_rate(trade_returns),
        'profit_factor': metrics.profit_factor(trade_returns),
        'avg_return': trade_returns.mean()
    }
    
    print(f"Win Rate: {trade_metrics['win_rate']:.2%}")
    print(f"Profit Factor: {trade_metrics['profit_factor']:.2f}")
    print(f"Avg Trade Return: {trade_metrics['avg_return']:.2%}")
    
    # Interpretation
    print("\n📈 Interpretation:")
    if results['sharpe_ratio'] > 1.0:
        print("✅ Sharpe Ratio > 1.0: Good risk-adjusted returns")
    else:
        print("⚠️ Sharpe Ratio < 1.0: Consider improving strategy")
    
    if trade_metrics['profit_factor'] > 1.5:
        print("✅ Profit Factor > 1.5: Strong profitability")
    elif trade_metrics['profit_factor'] > 1.0:
        print("✅ Profit Factor > 1.0: Profitable strategy")
    else:
        print("❌ Profit Factor < 1.0: Losing strategy")
    
    if results['max_drawdown'] > -0.20:
        print("✅ Max Drawdown < 20%: Good risk control")
    else:
        print("⚠️ Max Drawdown > 20%: High risk")
    
    print("\n" + "=" * 70)
    print("✅ All tests completed!")
    print("=" * 70)
