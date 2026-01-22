"""Tax-aware portfolio rebalancing."""

import logging
from dataclasses import dataclass
from typing import Dict, List
from datetime import datetime, timedelta
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class RebalanceResult:
    """Rebalancing recommendation."""
    trades: Dict[str, float]  # {symbol: quantity}
    expected_tax: float
    turnover: float
    tracking_error: float


class TaxAwareRebalancer:
    """Tax-aware rebalancing optimizer."""
    
    def __init__(self, short_term_rate: float = 0.37, long_term_rate: float = 0.20):
        """Initialize with tax rates.
        
        Args:
            short_term_rate: Short-term capital gains tax rate
            long_term_rate: Long-term capital gains tax rate (held > 1 year)
        """
        self.short_term_rate = short_term_rate
        self.long_term_rate = long_term_rate
        logger.info(f"TaxAwareRebalancer: ST={short_term_rate:.1%}, LT={long_term_rate:.1%}")
    
    def rebalance(self, current_holdings: Dict[str, float],
                  target_weights: Dict[str, float],
                  prices: Dict[str, float],
                  cost_basis: Dict[str, float],
                  purchase_dates: Dict[str, datetime],
                  tolerance: float = 0.05) -> RebalanceResult:
        """Calculate tax-aware rebalancing trades.
        
        Args:
            current_holdings: {symbol: quantity}
            target_weights: {symbol: target_weight}
            prices: {symbol: current_price}
            cost_basis: {symbol: average_cost_basis}
            purchase_dates: {symbol: purchase_date}
            tolerance: Rebalancing tolerance (5% = don't rebalance if within 5%)
        
        Returns:
            RebalanceResult
        """
        # Calculate current portfolio value
        total_value = sum(current_holdings.get(s, 0) * prices.get(s, 0) 
                         for s in set(current_holdings.keys()) | set(target_weights.keys()))
        
        if total_value == 0:
            return RebalanceResult({}, 0, 0, 0)
        
        # Calculate current weights
        current_weights = {
            symbol: (current_holdings.get(symbol, 0) * prices.get(symbol, 0)) / total_value
            for symbol in set(current_holdings.keys()) | set(target_weights.keys())
        }
        
        # Identify positions needing rebalancing
        trades = {}
        total_tax = 0
        now = datetime.now()
        
        for symbol in set(current_holdings.keys()) | set(target_weights.keys()):
            current_w = current_weights.get(symbol, 0)
            target_w = target_weights.get(symbol, 0)
            
            # Check if rebalancing needed
            if abs(current_w - target_w) < tolerance:
                continue
            
            # Calculate trade
            target_value = target_w * total_value
            current_value = current_w * total_value
            trade_value = target_value - current_value
            trade_quantity = trade_value / prices.get(symbol, 1)
            
            # Calculate tax for sells
            if trade_quantity < 0:
                current_qty = current_holdings.get(symbol, 0)
                sell_qty = min(abs(trade_quantity), current_qty)
                
                # Determine if long-term or short-term
                purchase_date = purchase_dates.get(symbol, now)
                is_long_term = (now - purchase_date) > timedelta(days=365)
                
                # Calculate gain/loss
                basis = cost_basis.get(symbol, prices.get(symbol, 0))
                gain = (prices.get(symbol, 0) - basis) * sell_qty
                
                if gain > 0:
                    tax_rate = self.long_term_rate if is_long_term else self.short_term_rate
                    tax = gain * tax_rate
                    total_tax += tax
            
            trades[symbol] = float(trade_quantity)
        
        # Calculate turnover
        turnover = sum(abs(trades.get(s, 0) * prices.get(s, 0)) for s in trades) / total_value
        
        # Calculate tracking error (simplified)
        tracking_error = np.sqrt(sum((current_weights.get(s, 0) - target_weights.get(s, 0))**2 
                                    for s in set(current_weights.keys()) | set(target_weights.keys())))
        
        return RebalanceResult(
            trades=trades,
            expected_tax=float(total_tax),
            turnover=float(turnover),
            tracking_error=float(tracking_error)
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=" * 70)
    print("Tax-Aware Rebalancer - Self Test")
    print("=" * 70)
    
    # Example portfolio
    current_holdings = {'AAPL': 10, 'GOOGL': 5, 'MSFT': 15}
    target_weights = {'AAPL': 0.40, 'GOOGL': 0.30, 'MSFT': 0.30}
    prices = {'AAPL': 150, 'GOOGL': 2800, 'MSFT': 300}
    cost_basis = {'AAPL': 120, 'GOOGL': 2500, 'MSFT': 280}
    purchase_dates = {
        'AAPL': datetime.now() - timedelta(days=400),  # Long-term
        'GOOGL': datetime.now() - timedelta(days=200),  # Short-term
        'MSFT': datetime.now() - timedelta(days=500)   # Long-term
    }
    
    rebalancer = TaxAwareRebalancer()
    result = rebalancer.rebalance(current_holdings, target_weights, prices, 
                                  cost_basis, purchase_dates, tolerance=0.05)
    
    print("\nRebalancing Trades:")
    for symbol, qty in result.trades.items():
        print(f"  {symbol}: {qty:+.2f}")
    
    print(f"\nExpected Tax: ${result.expected_tax:,.2f}")
    print(f"Turnover: {result.turnover:.2%}")
    print(f"Tracking Error: {result.tracking_error:.4f}")
    
    print("\n✅ Tax-aware rebalancer test complete!")
