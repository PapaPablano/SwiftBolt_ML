"""Position sizing strategies for trading.

Implements various position sizing methods:
- Fixed fractional
- Kelly criterion
- Optimal f
- Risk-based sizing
- Volatility-adjusted sizing

Usage:
    from src.optimization.position_sizing import PositionSizer
    
    sizer = PositionSizer(account_size=100000, risk_per_trade=0.02)
    
    # Calculate position size
    size = sizer.kelly_criterion(win_rate=0.55, avg_win=1.5, avg_loss=1.0)
"""

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class PositionSizer:
    """Position sizing calculator."""
    
    def __init__(
        self,
        account_size: float,
        risk_per_trade: float = 0.02,
        max_position_size: float = 0.20
    ):
        """Initialize position sizer.
        
        Args:
            account_size: Total account size
            risk_per_trade: Maximum risk per trade (as fraction of account)
            max_position_size: Maximum position size (as fraction of account)
        """
        self.account_size = account_size
        self.risk_per_trade = risk_per_trade
        self.max_position_size = max_position_size
        
        logger.info(
            f"PositionSizer initialized: account=${account_size:,.0f}, "
            f"risk_per_trade={risk_per_trade:.2%}"
        )
    
    def fixed_fractional(
        self,
        entry_price: float,
        stop_loss: float,
        fraction: Optional[float] = None
    ) -> int:
        """Calculate position size using fixed fractional method.
        
        Args:
            entry_price: Entry price per unit
            stop_loss: Stop loss price
            fraction: Fraction of account to risk (defaults to risk_per_trade)
        
        Returns:
            Number of units to trade
        """
        if fraction is None:
            fraction = self.risk_per_trade
        
        # Risk per unit
        risk_per_unit = abs(entry_price - stop_loss)
        
        if risk_per_unit == 0:
            return 0
        
        # Maximum amount to risk
        max_risk_amount = self.account_size * fraction
        
        # Position size
        position_size = int(max_risk_amount / risk_per_unit)
        
        # Apply max position size limit
        max_units = int((self.account_size * self.max_position_size) / entry_price)
        
        return min(position_size, max_units)
    
    def kelly_criterion(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        fraction: float = 0.5
    ) -> float:
        """Calculate optimal position size using Kelly criterion.
        
        Kelly formula: f* = (p*b - q) / b
        where:
            f* = fraction of capital to bet
            p = win probability
            q = loss probability (1-p)
            b = win/loss ratio
        
        Args:
            win_rate: Historical win rate (0 to 1)
            avg_win: Average win amount
            avg_loss: Average loss amount (positive)
            fraction: Kelly fraction (0.5 = half Kelly, more conservative)
        
        Returns:
            Optimal fraction of capital to allocate
        """
        if avg_loss == 0:
            return 0
        
        # Win/loss ratio
        b = avg_win / avg_loss
        
        # Probabilities
        p = win_rate
        q = 1 - win_rate
        
        # Kelly percentage
        kelly_pct = (p * b - q) / b
        
        # Apply Kelly fraction for conservatism
        kelly_pct *= fraction
        
        # Ensure non-negative and capped
        kelly_pct = np.clip(kelly_pct, 0, self.max_position_size)
        
        return kelly_pct
    
    def kelly_position_size(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        entry_price: float,
        fraction: float = 0.5
    ) -> int:
        """Calculate position size in units using Kelly criterion.
        
        Args:
            win_rate: Historical win rate
            avg_win: Average win amount
            avg_loss: Average loss amount
            entry_price: Entry price per unit
            fraction: Kelly fraction
        
        Returns:
            Number of units to trade
        """
        kelly_pct = self.kelly_criterion(win_rate, avg_win, avg_loss, fraction)
        
        # Convert to position size
        capital_to_allocate = self.account_size * kelly_pct
        position_size = int(capital_to_allocate / entry_price)
        
        return position_size
    
    def volatility_adjusted(
        self,
        entry_price: float,
        volatility: float,
        target_volatility: float = 0.10
    ) -> int:
        """Calculate position size based on volatility targeting.
        
        Args:
            entry_price: Entry price per unit
            volatility: Asset volatility (annualized)
            target_volatility: Target portfolio volatility
        
        Returns:
            Number of units to trade
        """
        if volatility == 0:
            return 0
        
        # Scale position to achieve target volatility
        position_value = (self.account_size * target_volatility) / volatility
        
        # Convert to units
        position_size = int(position_value / entry_price)
        
        # Apply max position size limit
        max_units = int((self.account_size * self.max_position_size) / entry_price)
        
        return min(position_size, max_units)
    
    def optimal_f(
        self,
        trade_results: list,
        entry_price: float
    ) -> int:
        """Calculate position size using Optimal f (Ralph Vince).
        
        Optimal f finds the fixed fraction that maximizes geometric growth.
        
        Args:
            trade_results: List of historical trade P&Ls
            entry_price: Entry price per unit
        
        Returns:
            Number of units to trade
        """
        if not trade_results:
            return 0
        
        # Find largest loss
        largest_loss = abs(min(trade_results))
        
        if largest_loss == 0:
            return 0
        
        # Search for optimal f
        def terminal_wealth(f, results, largest_loss):
            """Calculate terminal wealth for given f."""
            wealth = 1.0
            for result in results:
                hpr = 1 + (f * result / largest_loss)
                wealth *= hpr
            return wealth
        
        # Grid search for optimal f
        best_f = 0
        best_wealth = 0
        
        for f in np.linspace(0.01, 0.30, 30):
            wealth = terminal_wealth(f, trade_results, largest_loss)
            if wealth > best_wealth:
                best_wealth = wealth
                best_f = f
        
        # Apply conservatism
        optimal_f_conservative = best_f * 0.5
        
        # Convert to position size
        capital_to_allocate = self.account_size * optimal_f_conservative
        position_size = int(capital_to_allocate / entry_price)
        
        # Apply max position size limit
        max_units = int((self.account_size * self.max_position_size) / entry_price)
        
        return min(position_size, max_units)


if __name__ == "__main__":
    # Self-test
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("Position Sizing - Self Test")
    print("=" * 70)
    
    # Initialize
    sizer = PositionSizer(
        account_size=100000,
        risk_per_trade=0.02,
        max_position_size=0.20
    )
    
    # Test parameters
    entry_price = 50
    stop_loss = 48
    current_vol = 0.30
    
    # Test 1: Fixed fractional
    print("\n📊 Test 1: Fixed Fractional Sizing")
    size1 = sizer.fixed_fractional(entry_price, stop_loss)
    
    print(f"Entry: ${entry_price}, Stop: ${stop_loss}")
    print(f"Risk per unit: ${entry_price - stop_loss}")
    print(f"Position size: {size1} units")
    print(f"Position value: ${size1 * entry_price:,.0f}")
    print(f"Max risk: ${size1 * (entry_price - stop_loss):,.0f}")
    
    # Test 2: Kelly criterion
    print("\n📊 Test 2: Kelly Criterion")
    
    # Simulate strategy statistics
    win_rate = 0.55
    avg_win = 150
    avg_loss = 100
    
    kelly_pct = sizer.kelly_criterion(win_rate, avg_win, avg_loss, fraction=0.5)
    size2 = sizer.kelly_position_size(win_rate, avg_win, avg_loss, entry_price, fraction=0.5)
    
    print(f"Win rate: {win_rate:.0%}")
    print(f"Avg win: ${avg_win}, Avg loss: ${avg_loss}")
    print(f"Kelly %: {kelly_pct:.2%}")
    print(f"Position size: {size2} units")
    print(f"Position value: ${size2 * entry_price:,.0f}")
    
    # Test 3: Volatility adjusted
    print("\n📊 Test 3: Volatility-Adjusted Sizing")
    size3 = sizer.volatility_adjusted(entry_price, current_vol, target_volatility=0.10)
    
    print(f"Asset volatility: {current_vol:.0%}")
    print(f"Target volatility: {0.10:.0%}")
    print(f"Position size: {size3} units")
    print(f"Position value: ${size3 * entry_price:,.0f}")
    
    # Test 4: Optimal f
    print("\n📊 Test 4: Optimal f")
    
    # Simulate trade results
    np.random.seed(42)
    trade_results = []
    for _ in range(100):
        if np.random.rand() < win_rate:
            trade_results.append(np.random.uniform(50, 200))
        else:
            trade_results.append(-np.random.uniform(50, 150))
    
    size4 = sizer.optimal_f(trade_results, entry_price)
    
    print(f"Historical trades: {len(trade_results)}")
    print(f"Position size: {size4} units")
    print(f"Position value: ${size4 * entry_price:,.0f}")
    
    # Test 5: Comparison
    print("\n📊 Test 5: Method Comparison")
    print(f"{'Method':<25} {'Units':<10} {'Value':<15} {'% of Account':<15}")
    print("-" * 65)
    
    methods = [
        ("Fixed Fractional", size1),
        ("Kelly Criterion", size2),
        ("Volatility Adjusted", size3),
        ("Optimal f", size4)
    ]
    
    for name, size in methods:
        value = size * entry_price
        pct = (value / sizer.account_size) * 100
        print(f"{name:<25} {size:<10} ${value:<14,.0f} {pct:<15.2f}%")
    
    print("\n" + "=" * 70)
    print("✅ Position sizing test complete!")
    print("=" * 70)
