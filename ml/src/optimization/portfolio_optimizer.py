"""Portfolio optimization using Modern Portfolio Theory.

Implements:
- Mean-variance optimization (Markowitz)
- Efficient frontier calculation
- Maximum Sharpe ratio portfolio
- Minimum variance portfolio
- Risk parity allocation

Usage:
    from src.optimization.portfolio_optimizer import PortfolioOptimizer
    
    # Initialize
    optimizer = PortfolioOptimizer(returns_data)
    
    # Find optimal portfolio
    weights = optimizer.max_sharpe_portfolio(risk_free_rate=0.02)
    
    # Generate efficient frontier
    frontier = optimizer.efficient_frontier(n_points=50)

References:
    - Markowitz, H. (1952). "Portfolio Selection"
    - Sharpe, W. F. (1964). "Capital Asset Pricing Model"
    - Maillard, S., Roncalli, T., & Teïletche, J. (2010). "Risk Parity"
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import minimize

logger = logging.getLogger(__name__)


@dataclass
class PortfolioAllocation:
    """Portfolio allocation results.
    
    Attributes:
        weights: Asset weights
        expected_return: Expected portfolio return
        volatility: Portfolio volatility
        sharpe_ratio: Sharpe ratio
        assets: Asset names
    """
    weights: np.ndarray
    expected_return: float
    volatility: float
    sharpe_ratio: float
    assets: List[str]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'weights': dict(zip(self.assets, self.weights)),
            'expected_return': self.expected_return,
            'volatility': self.volatility,
            'sharpe_ratio': self.sharpe_ratio
        }


class PortfolioOptimizer:
    """Portfolio optimizer using mean-variance optimization."""
    
    def __init__(
        self,
        returns: pd.DataFrame,
        risk_free_rate: float = 0.02
    ):
        """Initialize portfolio optimizer.
        
        Args:
            returns: DataFrame of asset returns (columns = assets)
            risk_free_rate: Annual risk-free rate
        """
        self.returns = returns
        self.assets = list(returns.columns)
        self.n_assets = len(self.assets)
        self.risk_free_rate = risk_free_rate
        
        # Calculate mean returns and covariance
        self.mean_returns = returns.mean() * 252  # Annualized
        self.cov_matrix = returns.cov() * 252  # Annualized
        
        logger.info(
            f"PortfolioOptimizer initialized: {self.n_assets} assets, "
            f"risk_free_rate={risk_free_rate:.2%}"
        )
    
    def _portfolio_stats(
        self,
        weights: np.ndarray
    ) -> Tuple[float, float, float]:
        """Calculate portfolio statistics.
        
        Args:
            weights: Asset weights
        
        Returns:
            Tuple of (return, volatility, sharpe_ratio)
        """
        # Expected return
        portfolio_return = np.sum(self.mean_returns * weights)
        
        # Volatility
        portfolio_vol = np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))
        
        # Sharpe ratio
        sharpe = (portfolio_return - self.risk_free_rate) / portfolio_vol
        
        return portfolio_return, portfolio_vol, sharpe
    
    def max_sharpe_portfolio(
        self,
        constraints: Optional[Dict] = None
    ) -> PortfolioAllocation:
        """Find portfolio with maximum Sharpe ratio.
        
        Args:
            constraints: Optional constraints dict with:
                        - 'min_weight': minimum weight per asset
                        - 'max_weight': maximum weight per asset
                        - 'target_return': target return
        
        Returns:
            PortfolioAllocation
        """
        constraints = constraints or {}
        
        # Objective: minimize negative Sharpe ratio
        def neg_sharpe(weights):
            _, _, sharpe = self._portfolio_stats(weights)
            return -sharpe
        
        # Constraints
        cons = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]  # Weights sum to 1
        
        if 'target_return' in constraints:
            target = constraints['target_return']
            cons.append({
                'type': 'eq',
                'fun': lambda w: np.sum(self.mean_returns * w) - target
            })
        
        # Bounds
        min_w = constraints.get('min_weight', 0.0)
        max_w = constraints.get('max_weight', 1.0)
        bounds = tuple((min_w, max_w) for _ in range(self.n_assets))
        
        # Initial guess: equal weights
        w0 = np.array([1 / self.n_assets] * self.n_assets)
        
        # Optimize
        result = minimize(
            neg_sharpe,
            w0,
            method='SLSQP',
            bounds=bounds,
            constraints=cons
        )
        
        if not result.success:
            logger.warning(f"Optimization did not converge: {result.message}")
        
        # Calculate stats
        ret, vol, sharpe = self._portfolio_stats(result.x)
        
        return PortfolioAllocation(
            weights=result.x,
            expected_return=ret,
            volatility=vol,
            sharpe_ratio=sharpe,
            assets=self.assets
        )
    
    def min_variance_portfolio(
        self,
        constraints: Optional[Dict] = None
    ) -> PortfolioAllocation:
        """Find minimum variance portfolio.
        
        Args:
            constraints: Optional constraints dict
        
        Returns:
            PortfolioAllocation
        """
        constraints = constraints or {}
        
        # Objective: minimize variance
        def portfolio_variance(weights):
            return np.dot(weights.T, np.dot(self.cov_matrix, weights))
        
        # Constraints
        cons = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
        
        # Bounds
        min_w = constraints.get('min_weight', 0.0)
        max_w = constraints.get('max_weight', 1.0)
        bounds = tuple((min_w, max_w) for _ in range(self.n_assets))
        
        # Initial guess
        w0 = np.array([1 / self.n_assets] * self.n_assets)
        
        # Optimize
        result = minimize(
            portfolio_variance,
            w0,
            method='SLSQP',
            bounds=bounds,
            constraints=cons
        )
        
        # Calculate stats
        ret, vol, sharpe = self._portfolio_stats(result.x)
        
        return PortfolioAllocation(
            weights=result.x,
            expected_return=ret,
            volatility=vol,
            sharpe_ratio=sharpe,
            assets=self.assets
        )
    
    def efficient_portfolio(
        self,
        target_return: float,
        constraints: Optional[Dict] = None
    ) -> PortfolioAllocation:
        """Find efficient portfolio for target return.
        
        Args:
            target_return: Target annual return
            constraints: Optional constraints dict
        
        Returns:
            PortfolioAllocation
        """
        constraints = constraints or {}
        constraints['target_return'] = target_return
        
        # Objective: minimize variance
        def portfolio_variance(weights):
            return np.dot(weights.T, np.dot(self.cov_matrix, weights))
        
        # Constraints
        cons = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1},
            {'type': 'eq', 'fun': lambda w: np.sum(self.mean_returns * w) - target_return}
        ]
        
        # Bounds
        min_w = constraints.get('min_weight', 0.0)
        max_w = constraints.get('max_weight', 1.0)
        bounds = tuple((min_w, max_w) for _ in range(self.n_assets))
        
        # Initial guess
        w0 = np.array([1 / self.n_assets] * self.n_assets)
        
        # Optimize
        result = minimize(
            portfolio_variance,
            w0,
            method='SLSQP',
            bounds=bounds,
            constraints=cons
        )
        
        # Calculate stats
        ret, vol, sharpe = self._portfolio_stats(result.x)
        
        return PortfolioAllocation(
            weights=result.x,
            expected_return=ret,
            volatility=vol,
            sharpe_ratio=sharpe,
            assets=self.assets
        )
    
    def risk_parity_portfolio(self) -> PortfolioAllocation:
        """Calculate risk parity portfolio.
        
        Risk parity allocates capital such that each asset contributes
        equally to total portfolio risk.
        
        Returns:
            PortfolioAllocation
        """
        # Objective: minimize difference in risk contributions
        def risk_parity_objective(weights):
            # Portfolio variance
            port_var = np.dot(weights.T, np.dot(self.cov_matrix, weights))
            
            # Marginal risk contributions
            marginal_contrib = np.dot(self.cov_matrix, weights)
            
            # Risk contributions
            risk_contrib = weights * marginal_contrib
            
            # Target: equal risk contribution
            target_risk = port_var / self.n_assets
            
            # Sum of squared deviations
            return np.sum((risk_contrib - target_risk)**2)
        
        # Constraints
        cons = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
        
        # Bounds: all weights positive
        bounds = tuple((0.001, 1.0) for _ in range(self.n_assets))
        
        # Initial guess
        w0 = np.array([1 / self.n_assets] * self.n_assets)
        
        # Optimize
        result = minimize(
            risk_parity_objective,
            w0,
            method='SLSQP',
            bounds=bounds,
            constraints=cons
        )
        
        # Calculate stats
        ret, vol, sharpe = self._portfolio_stats(result.x)
        
        return PortfolioAllocation(
            weights=result.x,
            expected_return=ret,
            volatility=vol,
            sharpe_ratio=sharpe,
            assets=self.assets
        )


if __name__ == "__main__":
    # Self-test
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("Portfolio Optimizer - Self Test")
    print("=" * 70)
    
    # Generate synthetic returns for multiple assets
    np.random.seed(42)
    n_days = 1000
    
    # Create correlated returns
    mean_returns = np.array([0.10, 0.08, 0.12, 0.06]) / 252  # Daily
    volatilities = np.array([0.20, 0.15, 0.25, 0.10]) / np.sqrt(252)  # Daily
    
    # Correlation matrix
    corr = np.array([
        [1.0, 0.7, 0.5, 0.3],
        [0.7, 1.0, 0.6, 0.4],
        [0.5, 0.6, 1.0, 0.5],
        [0.3, 0.4, 0.5, 1.0]
    ])
    
    # Covariance matrix
    cov_matrix = np.outer(volatilities, volatilities) * corr
    
    # Generate returns
    returns = np.random.multivariate_normal(mean_returns, cov_matrix, n_days)
    returns_df = pd.DataFrame(
        returns,
        columns=['Stock A', 'Stock B', 'Stock C', 'Bond']
    )
    
    print(f"\nGenerated {n_days} days of returns for 4 assets")
    print(f"\nAnnualized Statistics:")
    print(returns_df.mean() * 252)
    
    # Initialize optimizer
    optimizer = PortfolioOptimizer(returns_df, risk_free_rate=0.02)
    
    # Test 1: Max Sharpe portfolio
    print("\n📊 Test 1: Maximum Sharpe Ratio Portfolio")
    max_sharpe = optimizer.max_sharpe_portfolio()
    
    print(f"\nWeights:")
    for asset, weight in zip(max_sharpe.assets, max_sharpe.weights):
        print(f"  {asset}: {weight*100:.2f}%")
    
    print(f"\nPerformance:")
    print(f"  Expected Return: {max_sharpe.expected_return*100:.2f}%")
    print(f"  Volatility: {max_sharpe.volatility*100:.2f}%")
    print(f"  Sharpe Ratio: {max_sharpe.sharpe_ratio:.2f}")
    
    # Test 2: Min variance portfolio
    print("\n📊 Test 2: Minimum Variance Portfolio")
    min_var = optimizer.min_variance_portfolio()
    
    print(f"\nWeights:")
    for asset, weight in zip(min_var.assets, min_var.weights):
        print(f"  {asset}: {weight*100:.2f}%")
    
    print(f"\nPerformance:")
    print(f"  Expected Return: {min_var.expected_return*100:.2f}%")
    print(f"  Volatility: {min_var.volatility*100:.2f}%")
    print(f"  Sharpe Ratio: {min_var.sharpe_ratio:.2f}")
    
    # Test 3: Risk parity portfolio
    print("\n📊 Test 3: Risk Parity Portfolio")
    risk_parity = optimizer.risk_parity_portfolio()
    
    print(f"\nWeights:")
    for asset, weight in zip(risk_parity.assets, risk_parity.weights):
        print(f"  {asset}: {weight*100:.2f}%")
    
    print(f"\nPerformance:")
    print(f"  Expected Return: {risk_parity.expected_return*100:.2f}%")
    print(f"  Volatility: {risk_parity.volatility*100:.2f}%")
    print(f"  Sharpe Ratio: {risk_parity.sharpe_ratio:.2f}")
    
    # Test 4: Comparison
    print("\n📊 Test 4: Strategy Comparison")
    print(f"{'Strategy':<20} {'Return':<12} {'Vol':<12} {'Sharpe':<10}")
    print("-" * 54)
    
    strategies = [
        ("Max Sharpe", max_sharpe),
        ("Min Variance", min_var),
        ("Risk Parity", risk_parity)
    ]
    
    for name, portfolio in strategies:
        print(f"{name:<20} {portfolio.expected_return*100:<12.2f}% "
              f"{portfolio.volatility*100:<12.2f}% {portfolio.sharpe_ratio:<10.2f}")
    
    print("\n" + "=" * 70)
    print("✅ Portfolio optimizer test complete!")
    print("=" * 70)
