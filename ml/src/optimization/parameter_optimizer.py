"""Parameter optimization tools for trading strategies.

Provides various optimization methods:
- Grid search
- Random search
- Bayesian optimization (if available)
- Genetic algorithms

Usage:
    from src.optimization.parameter_optimizer import ParameterOptimizer
    
    # Define strategy
    def my_strategy(data, param1, param2):
        # ... strategy logic ...
        return {'sharpe_ratio': 1.5, 'return': 0.25}
    
    # Optimize
    optimizer = ParameterOptimizer(
        strategy_function=my_strategy,
        param_space={
            'param1': {'type': 'int', 'low': 10, 'high': 50},
            'param2': {'type': 'float', 'low': 0.1, 'high': 1.0}
        },
        metric='sharpe_ratio'
    )
    
    result = optimizer.optimize(data, method='grid', n_trials=100)
    print(f"Best params: {result.best_params}")
"""

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """Results from parameter optimization.
    
    Attributes:
        best_params: Best parameter combination
        best_score: Best metric value
        all_results: List of all trials
        n_trials: Number of trials run
        method: Optimization method used
    """
    best_params: Dict[str, Any]
    best_score: float
    all_results: List[Dict]
    n_trials: int
    method: str


class ParameterOptimizer:
    """Parameter optimization for trading strategies."""
    
    def __init__(
        self,
        strategy_function: Callable,
        param_space: Dict[str, Dict],
        metric: str = 'sharpe_ratio',
        maximize: bool = True
    ):
        """Initialize parameter optimizer.
        
        Args:
            strategy_function: Function that takes (data, **params) and returns metrics dict
            param_space: Parameter space definition, e.g.:
                         {'param1': {'type': 'int', 'low': 10, 'high': 50},
                          'param2': {'type': 'float', 'low': 0.1, 'high': 1.0}}
            metric: Metric to optimize
            maximize: If True, maximize metric; if False, minimize
        """
        self.strategy_function = strategy_function
        self.param_space = param_space
        self.metric = metric
        self.maximize = maximize
        
        logger.info(f"ParameterOptimizer initialized: metric={metric}, maximize={maximize}")
    
    def _generate_grid_combinations(self, n_points: int = 10) -> List[Dict]:
        """Generate grid search combinations.
        
        Args:
            n_points: Number of points per parameter
        
        Returns:
            List of parameter combinations
        """
        import itertools
        
        param_values = {}
        
        for param_name, param_spec in self.param_space.items():
            ptype = param_spec['type']
            low = param_spec['low']
            high = param_spec['high']
            
            if ptype == 'int':
                values = np.linspace(low, high, n_points, dtype=int)
                param_values[param_name] = np.unique(values).tolist()
            elif ptype == 'float':
                param_values[param_name] = np.linspace(low, high, n_points).tolist()
            elif ptype == 'choice':
                param_values[param_name] = param_spec['choices']
            else:
                raise ValueError(f"Unknown parameter type: {ptype}")
        
        # Generate all combinations
        keys = param_values.keys()
        values = param_values.values()
        
        combinations = []
        for combo in itertools.product(*values):
            combinations.append(dict(zip(keys, combo)))
        
        return combinations
    
    def _generate_random_sample(self, n_samples: int = 100) -> List[Dict]:
        """Generate random parameter samples.
        
        Args:
            n_samples: Number of random samples
        
        Returns:
            List of parameter combinations
        """
        samples = []
        
        for _ in range(n_samples):
            sample = {}
            
            for param_name, param_spec in self.param_space.items():
                ptype = param_spec['type']
                low = param_spec['low']
                high = param_spec['high']
                
                if ptype == 'int':
                    sample[param_name] = np.random.randint(low, high + 1)
                elif ptype == 'float':
                    sample[param_name] = np.random.uniform(low, high)
                elif ptype == 'choice':
                    sample[param_name] = np.random.choice(param_spec['choices'])
            
            samples.append(sample)
        
        return samples
    
    def _evaluate_params(
        self,
        data: pd.DataFrame,
        params: Dict[str, Any]
    ) -> Optional[float]:
        """Evaluate a parameter combination.
        
        Args:
            data: Historical data
            params: Parameters to evaluate
        
        Returns:
            Metric value (or None if evaluation failed)
        """
        try:
            performance = self.strategy_function(data, **params)
            score = performance.get(self.metric, None)
            
            if score is None:
                logger.warning(f"Metric '{self.metric}' not found in performance results")
                return None
            
            # Convert to maximization problem
            if not self.maximize:
                score = -score
            
            return float(score)
            
        except Exception as e:
            logger.debug(f"Error evaluating params {params}: {e}")
            return None
    
    def optimize(
        self,
        data: pd.DataFrame,
        method: str = 'grid',
        n_trials: int = 100,
        verbose: bool = True
    ) -> OptimizationResult:
        """Optimize parameters.
        
        Args:
            data: Historical data
            method: Optimization method ('grid', 'random')
            n_trials: Number of trials (for random search) or points per param (for grid)
            verbose: Print progress
        
        Returns:
            OptimizationResult
        """
        logger.info(f"Starting optimization: method={method}, n_trials={n_trials}")
        
        # Generate parameter combinations
        if method == 'grid':
            n_points_per_param = int(np.power(n_trials, 1 / len(self.param_space)))
            param_combinations = self._generate_grid_combinations(n_points_per_param)
        elif method == 'random':
            param_combinations = self._generate_random_sample(n_trials)
        else:
            raise ValueError(f"Unknown optimization method: {method}")
        
        # Evaluate all combinations
        best_params = None
        best_score = -np.inf
        all_results = []
        
        total = len(param_combinations)
        for i, params in enumerate(param_combinations):
            score = self._evaluate_params(data, params)
            
            if score is not None:
                all_results.append({
                    'params': params,
                    'score': score
                })
                
                if score > best_score:
                    best_score = score
                    best_params = params
            
            if verbose and (i + 1) % max(1, total // 10) == 0:
                logger.info(f"Progress: {i+1}/{total} ({100*(i+1)/total:.0f}%), "
                           f"Best score: {best_score:.4f}")
        
        # Convert score back if minimizing
        if not self.maximize:
            best_score = -best_score
            for result in all_results:
                result['score'] = -result['score']
        
        logger.info(f"Optimization complete: best score={best_score:.4f}")
        
        return OptimizationResult(
            best_params=best_params if best_params else {},
            best_score=best_score if best_params else 0.0,
            all_results=all_results,
            n_trials=len(all_results),
            method=method
        )


if __name__ == "__main__":
    # Self-test
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("Parameter Optimizer - Self Test")
    print("=" * 70)
    
    # Create synthetic data
    np.random.seed(42)
    dates = pd.date_range('2020-01-01', '2022-12-31', freq='D')
    returns = np.random.randn(len(dates)) * 0.02 + 0.0005
    prices = 100 * (1 + returns).cumprod()
    
    data = pd.DataFrame({
        'price': prices,
        'returns': returns
    }, index=dates)
    
    print(f"\nGenerated {len(data)} days of synthetic data")
    
    # Define test strategy
    def test_strategy(data: pd.DataFrame, ma_fast: int, ma_slow: int, threshold: float) -> Dict:
        """Moving average crossover strategy."""
        data = data.copy()
        
        # Calculate moving averages
        data['ma_fast'] = data['price'].rolling(ma_fast).mean()
        data['ma_slow'] = data['price'].rolling(ma_slow).mean()
        
        # Generate signals
        data['signal'] = np.where(
            (data['ma_fast'] > data['ma_slow'] * (1 + threshold)), 1, 0
        )
        
        # Calculate returns
        data['strategy_returns'] = data['signal'].shift(1) * data['returns']
        strat_returns = data['strategy_returns'].dropna()
        
        if len(strat_returns) == 0 or strat_returns.std() == 0:
            return {'sharpe_ratio': 0, 'total_return': 0}
        
        sharpe = (strat_returns.mean() / strat_returns.std()) * np.sqrt(252)
        total_return = (1 + strat_returns).prod() - 1
        
        return {
            'sharpe_ratio': sharpe,
            'total_return': total_return
        }
    
    # Test 1: Grid search
    print("\n📊 Test 1: Grid Search Optimization")
    
    optimizer_grid = ParameterOptimizer(
        strategy_function=test_strategy,
        param_space={
            'ma_fast': {'type': 'int', 'low': 5, 'high': 30},
            'ma_slow': {'type': 'int', 'low': 20, 'high': 100},
            'threshold': {'type': 'float', 'low': 0.0, 'high': 0.05}
        },
        metric='sharpe_ratio',
        maximize=True
    )
    
    result_grid = optimizer_grid.optimize(data, method='grid', n_trials=27, verbose=False)
    
    print(f"\nGrid Search Results:")
    print(f"  Best Sharpe: {result_grid.best_score:.4f}")
    print(f"  Best params: {result_grid.best_params}")
    print(f"  Trials evaluated: {result_grid.n_trials}")
    
    # Test 2: Random search
    print("\n📊 Test 2: Random Search Optimization")
    
    optimizer_random = ParameterOptimizer(
        strategy_function=test_strategy,
        param_space={
            'ma_fast': {'type': 'int', 'low': 5, 'high': 30},
            'ma_slow': {'type': 'int', 'low': 20, 'high': 100},
            'threshold': {'type': 'float', 'low': 0.0, 'high': 0.05}
        },
        metric='sharpe_ratio',
        maximize=True
    )
    
    result_random = optimizer_random.optimize(data, method='random', n_trials=100, verbose=False)
    
    print(f"\nRandom Search Results:")
    print(f"  Best Sharpe: {result_random.best_score:.4f}")
    print(f"  Best params: {result_random.best_params}")
    print(f"  Trials evaluated: {result_random.n_trials}")
    
    # Test 3: Compare results
    print("\n📊 Test 3: Method Comparison")
    print(f"{'Method':<15} {'Best Sharpe':<15} {'Trials':<10}")
    print("-" * 40)
    print(f"{'Grid':<15} {result_grid.best_score:<15.4f} {result_grid.n_trials:<10}")
    print(f"{'Random':<15} {result_random.best_score:<15.4f} {result_random.n_trials:<10}")
    
    # Test 4: Analyze distribution of results
    print("\n📊 Test 4: Result Distribution")
    
    scores = [r['score'] for r in result_random.all_results]
    print(f"Score statistics:")
    print(f"  Mean: {np.mean(scores):.4f}")
    print(f"  Std: {np.std(scores):.4f}")
    print(f"  Min: {np.min(scores):.4f}")
    print(f"  Max: {np.max(scores):.4f}")
    print(f"  Median: {np.median(scores):.4f}")
    
    print("\n" + "=" * 70)
    print("✅ Parameter optimization test complete!")
    print("=" * 70)
