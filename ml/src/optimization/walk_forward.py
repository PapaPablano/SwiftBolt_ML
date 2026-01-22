"""Walk-forward optimization for robust strategy validation.

Walk-forward analysis prevents overfitting by:
1. Optimizing parameters on in-sample (IS) data
2. Testing on out-of-sample (OOS) data
3. Rolling the window forward through time
4. Aggregating results across all OOS periods

This provides a realistic estimate of strategy performance
without lookahead bias.

Usage:
    from src.optimization.walk_forward import WalkForwardOptimizer
    
    # Initialize
    wfo = WalkForwardOptimizer(
        strategy_function=my_strategy,
        param_grid={'lookback': [10, 20, 30], 'threshold': [0.5, 1.0]},
        is_period_days=252,  # 1 year training
        oos_period_days=63,  # 3 months testing
        metric='sharpe_ratio'
    )
    
    # Run walk-forward
    results = wfo.run(data)
    
    # Analyze
    print(f"OOS Sharpe: {results.oos_sharpe:.2f}")
    results.plot_equity_curve()

References:
    - Pardo, R. (2008). "The Evaluation and Optimization of Trading Strategies"
    - Aronson, D. (2006). "Evidence-Based Technical Analysis"
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class WindowResult:
    """Results for a single walk-forward window.
    
    Attributes:
        window_id: Window identifier
        is_start: In-sample start date
        is_end: In-sample end date
        oos_start: Out-of-sample start date
        oos_end: Out-of-sample end date
        best_params: Optimal parameters from IS optimization
        is_performance: In-sample performance metrics
        oos_performance: Out-of-sample performance metrics
    """
    window_id: int
    is_start: datetime
    is_end: datetime
    oos_start: datetime
    oos_end: datetime
    best_params: Dict[str, Any]
    is_performance: Dict[str, float]
    oos_performance: Dict[str, float]


@dataclass
class WalkForwardResults:
    """Complete walk-forward optimization results.
    
    Attributes:
        window_results: List of results for each window
        oos_equity_curve: Combined OOS equity curve
        efficiency_ratio: OOS/IS performance ratio
        parameter_stability: Stability metrics for parameters
    """
    window_results: List[WindowResult] = field(default_factory=list)
    oos_equity_curve: pd.Series = field(default_factory=pd.Series)
    efficiency_ratio: float = 0.0
    parameter_stability: Dict[str, float] = field(default_factory=dict)
    
    def get_oos_sharpe(self) -> float:
        """Get average OOS Sharpe ratio."""
        if not self.window_results:
            return 0.0
        sharpes = [w.oos_performance.get('sharpe_ratio', 0) for w in self.window_results]
        return np.mean(sharpes)
    
    def get_oos_total_return(self) -> float:
        """Get total OOS return."""
        if self.oos_equity_curve.empty:
            return 0.0
        return (self.oos_equity_curve.iloc[-1] / self.oos_equity_curve.iloc[0]) - 1
    
    def summary(self) -> Dict:
        """Get summary statistics."""
        return {
            'num_windows': len(self.window_results),
            'oos_sharpe': self.get_oos_sharpe(),
            'oos_total_return': self.get_oos_total_return(),
            'efficiency_ratio': self.efficiency_ratio,
            'parameter_stability': self.parameter_stability
        }


class WalkForwardOptimizer:
    """Walk-forward optimization framework."""
    
    def __init__(
        self,
        strategy_function: Callable,
        param_grid: Dict[str, List[Any]],
        is_period_days: int = 252,
        oos_period_days: int = 63,
        metric: str = 'sharpe_ratio',
        anchored: bool = False
    ):
        """Initialize walk-forward optimizer.
        
        Args:
            strategy_function: Trading strategy function that takes (data, **params)
                               and returns performance metrics dict
            param_grid: Dictionary of parameter names to lists of values
            is_period_days: In-sample training period (days)
            oos_period_days: Out-of-sample testing period (days)
            metric: Optimization metric ('sharpe_ratio', 'total_return', etc.)
            anchored: If True, IS period starts from beginning (anchored);
                      if False, IS period slides (rolling)
        """
        self.strategy_function = strategy_function
        self.param_grid = param_grid
        self.is_period_days = is_period_days
        self.oos_period_days = oos_period_days
        self.metric = metric
        self.anchored = anchored
        
        logger.info(
            f"WalkForwardOptimizer initialized: IS={is_period_days}d, "
            f"OOS={oos_period_days}d, metric={metric}, anchored={anchored}"
        )
    
    def _generate_param_combinations(self) -> List[Dict[str, Any]]:
        """Generate all parameter combinations from grid."""
        import itertools
        
        keys = self.param_grid.keys()
        values = self.param_grid.values()
        
        combinations = []
        for combo in itertools.product(*values):
            combinations.append(dict(zip(keys, combo)))
        
        return combinations
    
    def _optimize_window(
        self,
        data: pd.DataFrame,
        start_date: datetime,
        end_date: datetime
    ) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """Optimize parameters for a single window.
        
        Args:
            data: Historical data
            start_date: Window start date
            end_date: Window end date
        
        Returns:
            Tuple of (best_params, best_performance)
        """
        # Filter data for this window
        window_data = data[(data.index >= start_date) & (data.index <= end_date)]
        
        if window_data.empty:
            logger.warning(f"No data in window {start_date} to {end_date}")
            return {}, {}
        
        # Generate all parameter combinations
        param_combinations = self._generate_param_combinations()
        
        # Evaluate each combination
        best_params = None
        best_metric_value = -np.inf
        best_performance = None
        
        for params in param_combinations:
            try:
                # Run strategy with these parameters
                performance = self.strategy_function(window_data, **params)
                
                # Check if this is the best so far
                metric_value = performance.get(self.metric, -np.inf)
                
                if metric_value > best_metric_value:
                    best_metric_value = metric_value
                    best_params = params
                    best_performance = performance
                    
            except Exception as e:
                logger.debug(f"Error evaluating params {params}: {e}")
                continue
        
        if best_params is None:
            logger.warning(f"No valid parameters found for window {start_date} to {end_date}")
            return {}, {}
        
        return best_params, best_performance
    
    def _test_window(
        self,
        data: pd.DataFrame,
        start_date: datetime,
        end_date: datetime,
        params: Dict[str, Any]
    ) -> Dict[str, float]:
        """Test parameters on out-of-sample window.
        
        Args:
            data: Historical data
            start_date: Window start date
            end_date: Window end date
            params: Parameters to test
        
        Returns:
            Performance metrics
        """
        # Filter data for this window
        window_data = data[(data.index >= start_date) & (data.index <= end_date)]
        
        if window_data.empty or not params:
            return {}
        
        try:
            performance = self.strategy_function(window_data, **params)
            return performance
        except Exception as e:
            logger.error(f"Error testing params on OOS window: {e}")
            return {}
    
    def run(self, data: pd.DataFrame) -> WalkForwardResults:
        """Run walk-forward optimization.
        
        Args:
            data: Historical data with DatetimeIndex
        
        Returns:
            WalkForwardResults object
        """
        if not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError("Data must have DatetimeIndex")
        
        results = WalkForwardResults()
        
        # Ensure data is sorted
        data = data.sort_index()
        
        # Calculate window boundaries
        start_date = data.index.min()
        end_date = data.index.max()
        
        window_id = 0
        current_date = start_date
        
        # Collect all OOS equity values
        oos_equity_series = []
        
        # Walk forward through time
        while current_date < end_date:
            # Define IS period
            if self.anchored:
                is_start = start_date
            else:
                is_start = current_date
            
            is_end = current_date + timedelta(days=self.is_period_days)
            
            # Define OOS period
            oos_start = is_end + timedelta(days=1)
            oos_end = oos_start + timedelta(days=self.oos_period_days)
            
            # Check if we have enough data
            if oos_end > end_date:
                logger.info(f"Stopping: OOS end ({oos_end}) exceeds data end ({end_date})")
                break
            
            logger.info(f"Window {window_id}: IS {is_start.date()} to {is_end.date()}, "
                       f"OOS {oos_start.date()} to {oos_end.date()}")
            
            # Optimize on IS period
            best_params, is_performance = self._optimize_window(data, is_start, is_end)
            
            if not best_params:
                logger.warning(f"Skipping window {window_id}: no valid parameters")
                current_date = oos_start
                window_id += 1
                continue
            
            # Test on OOS period
            oos_performance = self._test_window(data, oos_start, oos_end, best_params)
            
            if not oos_performance:
                logger.warning(f"Skipping window {window_id}: OOS test failed")
                current_date = oos_start
                window_id += 1
                continue
            
            # Store window result
            window_result = WindowResult(
                window_id=window_id,
                is_start=is_start,
                is_end=is_end,
                oos_start=oos_start,
                oos_end=oos_end,
                best_params=best_params,
                is_performance=is_performance,
                oos_performance=oos_performance
            )
            results.window_results.append(window_result)
            
            # Move to next window
            current_date = oos_start
            window_id += 1
        
        # Calculate aggregate statistics
        self._calculate_aggregate_stats(results)
        
        logger.info(f"Walk-forward complete: {len(results.window_results)} windows")
        
        return results
    
    def _calculate_aggregate_stats(self, results: WalkForwardResults):
        """Calculate aggregate statistics across all windows."""
        if not results.window_results:
            return
        
        # Calculate efficiency ratio (OOS/IS performance)
        is_metrics = [w.is_performance.get(self.metric, 0) for w in results.window_results]
        oos_metrics = [w.oos_performance.get(self.metric, 0) for w in results.window_results]
        
        avg_is = np.mean([m for m in is_metrics if m != 0])
        avg_oos = np.mean([m for m in oos_metrics if m != 0])
        
        if avg_is != 0:
            results.efficiency_ratio = avg_oos / avg_is
        
        # Calculate parameter stability (coefficient of variation)
        param_stability = {}
        
        for param_name in self.param_grid.keys():
            param_values = [
                w.best_params.get(param_name, 0) 
                for w in results.window_results
            ]
            
            # Convert to numeric if possible
            try:
                param_values = [float(v) for v in param_values]
                mean_val = np.mean(param_values)
                std_val = np.std(param_values)
                
                if mean_val != 0:
                    # Lower CV = more stable
                    cv = std_val / abs(mean_val)
                    param_stability[param_name] = 1 / (1 + cv)  # Normalize to [0, 1]
                else:
                    param_stability[param_name] = 0
            except:
                # Non-numeric parameter
                unique_values = len(set(param_values))
                total_values = len(param_values)
                param_stability[param_name] = 1 - (unique_values / total_values)
        
        results.parameter_stability = param_stability


if __name__ == "__main__":
    # Self-test
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("Walk-Forward Optimizer - Self Test")
    print("=" * 70)
    
    # Create synthetic data
    np.random.seed(42)
    dates = pd.date_range('2020-01-01', '2023-12-31', freq='D')
    returns = np.random.randn(len(dates)) * 0.02 + 0.0005
    prices = 100 * (1 + returns).cumprod()
    
    data = pd.DataFrame({
        'price': prices,
        'returns': returns
    }, index=dates)
    
    print(f"\nGenerated {len(data)} days of synthetic data")
    print(f"Date range: {data.index.min().date()} to {data.index.max().date()}")
    
    # Define a simple momentum strategy
    def momentum_strategy(data: pd.DataFrame, lookback: int = 20, threshold: float = 0.0) -> Dict[str, float]:
        """Simple momentum strategy for testing."""
        # Calculate momentum
        data['momentum'] = data['price'].pct_change(lookback)
        
        # Generate signals
        data['signal'] = np.where(data['momentum'] > threshold, 1, 0)
        
        # Calculate strategy returns
        data['strategy_returns'] = data['signal'].shift(1) * data['returns']
        
        # Calculate performance metrics
        strat_returns = data['strategy_returns'].dropna()
        
        if len(strat_returns) == 0 or strat_returns.std() == 0:
            return {'sharpe_ratio': 0, 'total_return': 0, 'volatility': 0}
        
        sharpe = (strat_returns.mean() / strat_returns.std()) * np.sqrt(252)
        total_return = (1 + strat_returns).prod() - 1
        volatility = strat_returns.std() * np.sqrt(252)
        
        return {
            'sharpe_ratio': sharpe,
            'total_return': total_return,
            'volatility': volatility
        }
    
    # Test walk-forward optimization
    print("\n📊 Running Walk-Forward Optimization...")
    
    wfo = WalkForwardOptimizer(
        strategy_function=momentum_strategy,
        param_grid={
            'lookback': [10, 20, 30],
            'threshold': [0.0, 0.01, 0.02]
        },
        is_period_days=252,  # 1 year training
        oos_period_days=63,  # 3 months testing
        metric='sharpe_ratio',
        anchored=False  # Rolling window
    )
    
    results = wfo.run(data)
    
    # Display results
    print(f"\n📊 Walk-Forward Results:")
    print(f"Number of windows: {len(results.window_results)}")
    print(f"OOS Sharpe ratio: {results.get_oos_sharpe():.2f}")
    print(f"Efficiency ratio: {results.efficiency_ratio:.2f}")
    
    print(f"\n📊 Parameter Stability:")
    for param, stability in results.parameter_stability.items():
        print(f"  {param}: {stability:.2%}")
    
    print(f"\n📊 Window-by-Window Results:")
    print(f"{'Window':<8} {'IS Sharpe':<12} {'OOS Sharpe':<12} {'Best Params'}")
    print("-" * 60)
    
    for w in results.window_results:
        is_sharpe = w.is_performance.get('sharpe_ratio', 0)
        oos_sharpe = w.oos_performance.get('sharpe_ratio', 0)
        params_str = f"LB={w.best_params.get('lookback', 'N/A')}, TH={w.best_params.get('threshold', 'N/A')}"
        print(f"{w.window_id:<8} {is_sharpe:<12.2f} {oos_sharpe:<12.2f} {params_str}")
    
    # Summary
    summary = results.summary()
    print(f"\n📊 Summary:")
    for key, value in summary.items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for k, v in value.items():
                print(f"    {k}: {v:.4f}")
        else:
            print(f"  {key}: {value:.4f}" if isinstance(value, float) else f"  {key}: {value}")
    
    print("\n" + "=" * 70)
    print("✅ Walk-forward optimization test complete!")
    print("=" * 70)
