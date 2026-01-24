"""Fitness evaluation for strategy discovery."""

import logging
from dataclasses import dataclass
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class FitnessMetrics:
    """Fitness evaluation metrics."""
    sharpe_ratio: float
    total_return: float
    max_drawdown: float
    win_rate: float
    fitness_score: float


class FitnessEvaluator:
    """Evaluate strategy fitness."""
    
    def __init__(self, data: pd.DataFrame, risk_free_rate: float = 0.02):
        self.data = data
        self.risk_free_rate = risk_free_rate
        logger.info(f"FitnessEvaluator initialized with {len(data)} samples")
    
    def evaluate(self, strategy_func: callable, params: dict) -> FitnessMetrics:
        """Evaluate strategy fitness.
        
        Args:
            strategy_func: Function(data, **params) -> returns
            params: Strategy parameters
        
        Returns:
            FitnessMetrics
        """
        try:
            # Run strategy
            returns = strategy_func(self.data, **params)
            
            if len(returns) == 0 or returns.std() == 0:
                return FitnessMetrics(0, 0, -1, 0, 0)
            
            # Calculate metrics
            sharpe = (returns.mean() - self.risk_free_rate/252) / returns.std() * np.sqrt(252)
            total_return = (1 + returns).prod() - 1
            
            # Drawdown
            cum_returns = (1 + returns).cumprod()
            running_max = cum_returns.expanding().max()
            drawdown = (cum_returns - running_max) / running_max
            max_dd = drawdown.min()
            
            # Win rate
            win_rate = (returns > 0).mean()
            
            # Combined fitness score
            fitness = sharpe * 0.5 + total_return * 0.3 - abs(max_dd) * 0.2
            
            return FitnessMetrics(
                sharpe_ratio=float(sharpe),
                total_return=float(total_return),
                max_drawdown=float(max_dd),
                win_rate=float(win_rate),
                fitness_score=float(fitness)
            )
        except Exception as e:
            logger.debug(f"Strategy evaluation failed: {e}")
            return FitnessMetrics(0, 0, -1, 0, 0)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Generate test data
    np.random.seed(42)
    data = pd.DataFrame({'returns': np.random.randn(252) * 0.02})
    
    def test_strategy(data, position_size=0.1):
        return data['returns'] * position_size
    
    evaluator = FitnessEvaluator(data)
    metrics = evaluator.evaluate(test_strategy, {'position_size': 0.1})
    print(f"Fitness: {metrics.fitness_score:.4f}, Sharpe: {metrics.sharpe_ratio:.2f}")
    print("✅ Fitness evaluator ready")
