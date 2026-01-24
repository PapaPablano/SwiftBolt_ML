"""Factor-based performance attribution."""

import logging
from dataclasses import dataclass
from typing import Dict, List
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression

logger = logging.getLogger(__name__)


@dataclass
class FactorExposure:
    """Factor exposure analysis."""
    factor_exposures: Dict[str, float]
    factor_returns: Dict[str, float]
    alpha: float
    r_squared: float


class FactorAnalyzer:
    """Multi-factor performance attribution."""
    
    COMMON_FACTORS = ['market', 'size', 'value', 'momentum', 'volatility']
    
    def __init__(self, factor_data: pd.DataFrame = None):
        """Initialize with factor returns.
        
        Args:
            factor_data: DataFrame with factors as columns, dates as index
        """
        self.factor_data = factor_data
        logger.info(f"FactorAnalyzer initialized: {factor_data.shape if factor_data is not None else 'no data'}")
    
    def analyze(self, portfolio_returns: pd.Series, factors: List[str] = None) -> FactorExposure:
        """Perform factor regression analysis.
        
        Args:
            portfolio_returns: Series of portfolio returns
            factors: List of factor names to use
        
        Returns:
            FactorExposure
        """
        if self.factor_data is None:
            # Generate synthetic factor data for testing
            logger.warning("No factor data provided, using synthetic data")
            self.factor_data = self._generate_synthetic_factors(len(portfolio_returns))
        
        factors = factors or self.COMMON_FACTORS
        factors = [f for f in factors if f in self.factor_data.columns]
        
        # Align data
        common_index = portfolio_returns.index.intersection(self.factor_data.index)
        y = portfolio_returns.loc[common_index].values
        X = self.factor_data.loc[common_index, factors].values
        
        # Regression
        model = LinearRegression()
        model.fit(X, y)
        
        # Extract results
        factor_exposures = {factor: coef for factor, coef in zip(factors, model.coef_)}
        alpha = float(model.intercept_)
        r_squared = float(model.score(X, y))
        
        # Calculate factor returns contribution
        factor_returns = {}
        for i, factor in enumerate(factors):
            factor_ret = (model.coef_[i] * X[:, i]).mean()
            factor_returns[factor] = float(factor_ret)
        
        return FactorExposure(
            factor_exposures=factor_exposures,
            factor_returns=factor_returns,
            alpha=alpha,
            r_squared=r_squared
        )
    
    def _generate_synthetic_factors(self, n_periods: int) -> pd.DataFrame:
        """Generate synthetic factor data for testing."""
        np.random.seed(42)
        factors = {}
        for factor in self.COMMON_FACTORS:
            factors[factor] = np.random.randn(n_periods) * 0.02
        return pd.DataFrame(factors)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=" * 70)
    print("Factor Analysis - Self Test")
    print("=" * 70)
    
    # Generate test data
    np.random.seed(42)
    n = 252
    portfolio_returns = pd.Series(np.random.randn(n) * 0.02, name='returns')
    
    analyzer = FactorAnalyzer()
    result = analyzer.analyze(portfolio_returns, ['market', 'size', 'value'])
    
    print("\nFactor Exposures:")
    for factor, exposure in result.factor_exposures.items():
        print(f"  {factor}: {exposure:.4f}")
    
    print(f"\nAlpha: {result.alpha:.6f} ({result.alpha*252*100:.2f}% annualized)")
    print(f"R-squared: {result.r_squared:.4f}")
    
    print("\n✅ Factor analysis test complete!")
