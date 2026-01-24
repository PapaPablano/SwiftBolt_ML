"""Transaction cost optimization for rebalancing."""

import logging
from dataclasses import dataclass
from typing import Dict, List
import numpy as np
from scipy.optimize import minimize

logger = logging.getLogger(__name__)


@dataclass
class TransactionCost:
    """Transaction cost breakdown."""
    commission: float
    spread: float
    market_impact: float
    total: float


class CostOptimizer:
    """Optimize rebalancing to minimize transaction costs."""
    
    def __init__(self, commission_rate: float = 0.001, 
                 spread_bps: float = 5.0,
                 impact_coef: float = 0.1):
        """Initialize with cost parameters.
        
        Args:
            commission_rate: Commission as fraction of trade value
            spread_bps: Bid-ask spread in basis points
            impact_coef: Market impact coefficient
        """
        self.commission_rate = commission_rate
        self.spread_bps = spread_bps / 10000
        self.impact_coef = impact_coef
        logger.info(f"CostOptimizer: commission={commission_rate:.4f}, spread={spread_bps}bps")
    
    def calculate_cost(self, trade_value: float, volume: float) -> TransactionCost:
        """Calculate transaction cost for a trade.
        
        Args:
            trade_value: Dollar value of trade
            volume: Average daily volume
        
        Returns:
            TransactionCost
        """
        # Commission
        commission = abs(trade_value) * self.commission_rate
        
        # Spread cost
        spread = abs(trade_value) * self.spread_bps
        
        # Market impact (simplified model)
        # Impact increases with trade size relative to volume
        participation_rate = abs(trade_value) / max(volume, 1)
        impact = abs(trade_value) * self.impact_coef * (participation_rate ** 0.5)
        
        total = commission + spread + impact
        
        return TransactionCost(
            commission=float(commission),
            spread=float(spread),
            market_impact=float(impact),
            total=float(total)
        )
    
    def optimize_rebalancing(self, proposed_trades: Dict[str, float],
                            prices: Dict[str, float],
                            volumes: Dict[str, float],
                            target_weights: Dict[str, float],
                            max_tracking_error: float = 0.05) -> Dict[str, float]:
        """Optimize trades to minimize cost while staying near target.
        
        Args:
            proposed_trades: {symbol: quantity}
            prices: {symbol: price}
            volumes: {symbol: avg_daily_volume}
            target_weights: {symbol: target_weight}
            max_tracking_error: Maximum allowed tracking error
        
        Returns:
            Optimized trades
        """
        symbols = list(proposed_trades.keys())
        if not symbols:
            return {}
        
        # Initial trade vector
        x0 = np.array([proposed_trades.get(s, 0) for s in symbols])
        
        # Objective: minimize total transaction cost
        def objective(x):
            total_cost = 0
            for i, symbol in enumerate(symbols):
                trade_value = x[i] * prices.get(symbol, 0)
                cost = self.calculate_cost(trade_value, volumes.get(symbol, 1e6))
                total_cost += cost.total
            return total_cost
        
        # Constraint: tracking error
        def tracking_error_constraint(x):
            # Simplified: just ensure we're not too far from proposed trades
            deviation = np.sum((x - x0) ** 2)
            return max_tracking_error - deviation
        
        # Optimize
        result = minimize(
            objective,
            x0,
            method='SLSQP',
            constraints=[{'type': 'ineq', 'fun': tracking_error_constraint}],
            options={'maxiter': 100}
        )
        
        if result.success:
            optimized_trades = {symbol: float(qty) for symbol, qty in zip(symbols, result.x)}
            logger.info(f"Optimization successful: cost reduced by {(objective(x0) - result.fun) / objective(x0):.2%}")
            return optimized_trades
        else:
            logger.warning("Optimization failed, returning original trades")
            return proposed_trades


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=" * 70)
    print("Cost Optimizer - Self Test")
    print("=" * 70)
    
    optimizer = CostOptimizer()
    
    # Calculate cost for a single trade
    cost = optimizer.calculate_cost(trade_value=10000, volume=1000000)
    print(f"\nTransaction Cost for $10,000 trade:")
    print(f"  Commission: ${cost.commission:.2f}")
    print(f"  Spread: ${cost.spread:.2f}")
    print(f"  Market Impact: ${cost.market_impact:.2f}")
    print(f"  Total: ${cost.total:.2f}")
    
    # Optimize rebalancing
    proposed_trades = {'AAPL': 10, 'GOOGL': -2, 'MSFT': 5}
    prices = {'AAPL': 150, 'GOOGL': 2800, 'MSFT': 300}
    volumes = {'AAPL': 100e6, 'GOOGL': 50e6, 'MSFT': 80e6}
    target_weights = {'AAPL': 0.4, 'GOOGL': 0.3, 'MSFT': 0.3}
    
    optimized = optimizer.optimize_rebalancing(proposed_trades, prices, volumes, target_weights)
    
    print("\nOptimized Trades:")
    for symbol, qty in optimized.items():
        original = proposed_trades[symbol]
        print(f"  {symbol}: {qty:+.2f} (original: {original:+.2f})")
    
    print("\n✅ Cost optimizer test complete!")
