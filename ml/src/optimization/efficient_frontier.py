"""Efficient Frontier calculation and visualization.

The efficient frontier represents the set of optimal portfolios
that offer the highest expected return for a given level of risk.

Usage:
    from src.optimization.efficient_frontier import EfficientFrontier
    
    # Calculate frontier
    ef = EfficientFrontier(returns_data, risk_free_rate=0.02)
    frontier_portfolios = ef.calculate_frontier(n_points=50)
    
    # Plot
    ef.plot()
"""

import logging
from typing import List, Optional

import numpy as np
import pandas as pd

try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    logging.warning("Plotly not available. Install with: pip install plotly")

from .portfolio_optimizer import PortfolioOptimizer, PortfolioAllocation

logger = logging.getLogger(__name__)


class EfficientFrontier:
    """Efficient frontier calculator."""
    
    def __init__(
        self,
        returns: pd.DataFrame,
        risk_free_rate: float = 0.02
    ):
        """Initialize efficient frontier calculator.
        
        Args:
            returns: DataFrame of asset returns
            risk_free_rate: Annual risk-free rate
        """
        self.optimizer = PortfolioOptimizer(returns, risk_free_rate)
        self.risk_free_rate = risk_free_rate
        self.frontier_portfolios: List[PortfolioAllocation] = []
        
        logger.info("EfficientFrontier initialized")
    
    def calculate_frontier(
        self,
        n_points: int = 50,
        constraints: Optional[dict] = None
    ) -> List[PortfolioAllocation]:
        """Calculate efficient frontier.
        
        Args:
            n_points: Number of points on frontier
            constraints: Optional constraints dict
        
        Returns:
            List of PortfolioAllocation objects
        """
        # Get min variance and max return portfolios
        min_var_port = self.optimizer.min_variance_portfolio(constraints)
        
        # Find max return (100% in highest return asset with constraints)
        max_return = self.optimizer.mean_returns.max()
        min_return = min_var_port.expected_return
        
        # Generate target returns
        target_returns = np.linspace(min_return, max_return * 0.95, n_points)
        
        portfolios = []
        for target_return in target_returns:
            try:
                portfolio = self.optimizer.efficient_portfolio(
                    target_return,
                    constraints
                )
                portfolios.append(portfolio)
            except Exception as e:
                logger.debug(f"Could not find portfolio for return {target_return:.4f}: {e}")
                continue
        
        self.frontier_portfolios = portfolios
        logger.info(f"Calculated efficient frontier with {len(portfolios)} points")
        
        return portfolios
    
    def plot(self, show_assets: bool = True, show_special_portfolios: bool = True):
        """Plot efficient frontier.
        
        Args:
            show_assets: Show individual assets
            show_special_portfolios: Show special portfolios (max Sharpe, min var)
        
        Returns:
            Plotly figure (if available)
        """
        if not PLOTLY_AVAILABLE:
            print("Plotly not available. Cannot plot frontier.")
            return None
        
        if not self.frontier_portfolios:
            print("No frontier calculated. Call calculate_frontier() first.")
            return None
        
        fig = go.Figure()
        
        # Plot efficient frontier
        vols = [p.volatility * 100 for p in self.frontier_portfolios]
        rets = [p.expected_return * 100 for p in self.frontier_portfolios]
        
        fig.add_trace(go.Scatter(
            x=vols,
            y=rets,
            mode='lines+markers',
            name='Efficient Frontier',
            line=dict(color='blue', width=2),
            marker=dict(size=4)
        ))
        
        # Plot individual assets
        if show_assets:
            asset_vols = np.sqrt(np.diag(self.optimizer.cov_matrix)) * 100
            asset_rets = self.optimizer.mean_returns.values * 100
            
            fig.add_trace(go.Scatter(
                x=asset_vols,
                y=asset_rets,
                mode='markers+text',
                name='Individual Assets',
                text=self.optimizer.assets,
                textposition='top center',
                marker=dict(size=10, color='red', symbol='star')
            ))
        
        # Plot special portfolios
        if show_special_portfolios:
            # Max Sharpe
            max_sharpe = self.optimizer.max_sharpe_portfolio()
            fig.add_trace(go.Scatter(
                x=[max_sharpe.volatility * 100],
                y=[max_sharpe.expected_return * 100],
                mode='markers+text',
                name='Max Sharpe',
                text=['Max Sharpe'],
                textposition='top center',
                marker=dict(size=15, color='green', symbol='diamond')
            ))
            
            # Min Variance
            min_var = self.optimizer.min_variance_portfolio()
            fig.add_trace(go.Scatter(
                x=[min_var.volatility * 100],
                y=[min_var.expected_return * 100],
                mode='markers+text',
                name='Min Variance',
                text=['Min Var'],
                textposition='bottom center',
                marker=dict(size=15, color='orange', symbol='square')
            ))
        
        # Capital Market Line (CML)
        max_sharpe = self.optimizer.max_sharpe_portfolio()
        cml_x = [0, max_sharpe.volatility * 100 * 1.5]
        cml_y = [
            self.risk_free_rate * 100,
            self.risk_free_rate * 100 + max_sharpe.sharpe_ratio * (cml_x[1])
        ]
        
        fig.add_trace(go.Scatter(
            x=cml_x,
            y=cml_y,
            mode='lines',
            name='Capital Market Line',
            line=dict(color='gray', width=1, dash='dash')
        ))
        
        fig.update_layout(
            title='Efficient Frontier',
            xaxis_title='Volatility (% annual)',
            yaxis_title='Expected Return (% annual)',
            hovermode='closest',
            showlegend=True
        )
        
        return fig


if __name__ == "__main__":
    # Self-test
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("Efficient Frontier - Self Test")
    print("=" * 70)
    
    # Generate synthetic data
    np.random.seed(42)
    n_days = 1000
    
    mean_returns = np.array([0.10, 0.08, 0.12]) / 252
    volatilities = np.array([0.20, 0.15, 0.25]) / np.sqrt(252)
    
    corr = np.array([
        [1.0, 0.6, 0.4],
        [0.6, 1.0, 0.5],
        [0.4, 0.5, 1.0]
    ])
    
    cov_matrix = np.outer(volatilities, volatilities) * corr
    returns = np.random.multivariate_normal(mean_returns, cov_matrix, n_days)
    returns_df = pd.DataFrame(returns, columns=['Stock A', 'Stock B', 'Stock C'])
    
    print(f"\nGenerated {n_days} days of returns for 3 assets")
    
    # Calculate efficient frontier
    ef = EfficientFrontier(returns_df, risk_free_rate=0.02)
    portfolios = ef.calculate_frontier(n_points=30)
    
    print(f"\n📊 Efficient Frontier:")
    print(f"Number of portfolios: {len(portfolios)}")
    
    print(f"\n{'Return':<12} {'Volatility':<12} {'Sharpe':<10}")
    print("-" * 34)
    
    for i, p in enumerate(portfolios[::5]):  # Show every 5th
        print(f"{p.expected_return*100:<12.2f}% {p.volatility*100:<12.2f}% {p.sharpe_ratio:<10.2f}")
    
    # Plot frontier
    if PLOTLY_AVAILABLE:
        print("\n📊 Generating plot...")
        fig = ef.plot()
        print("Plot generated (call fig.show() to display)")
    else:
        print("\n⚠️ Plotly not available, skipping plot")
    
    print("\n" + "=" * 70)
    print("✅ Efficient frontier test complete!")
    print("=" * 70)
