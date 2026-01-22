"""Paper trading engine for strategy testing."""

import logging
from dataclasses import dataclass, field
from typing import Dict, List
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class PaperAccount:
    """Paper trading account state."""
    initial_balance: float
    balance: float
    positions: Dict[str, float] = field(default_factory=dict)
    transaction_history: List[dict] = field(default_factory=list)
    
    @property
    def equity(self) -> float:
        """Total account equity."""
        return self.balance + sum(self.positions.values())


class PaperTradingEngine:
    """Simulated trading environment."""
    
    def __init__(self, initial_balance: float = 100000.0):
        self.account = PaperAccount(initial_balance, initial_balance)
        self.current_time = None
        logger.info(f"PaperTradingEngine initialized: balance=${initial_balance:,.2f}")
    
    def execute_order(self, symbol: str, quantity: float, price: float, 
                     order_type: str = 'market') -> bool:
        """Execute paper order.
        
        Args:
            symbol: Ticker symbol
            quantity: Positive for buy, negative for sell
            price: Execution price
            order_type: 'market' or 'limit'
        
        Returns:
            True if executed
        """
        cost = abs(quantity * price)
        
        # Check balance for buys
        if quantity > 0 and cost > self.account.balance:
            logger.warning(f"Insufficient balance: ${cost:.2f} > ${self.account.balance:.2f}")
            return False
        
        # Execute
        if quantity > 0:  # Buy
            self.account.balance -= cost
            self.account.positions[symbol] = self.account.positions.get(symbol, 0) + quantity
        else:  # Sell
            self.account.balance += cost
            self.account.positions[symbol] = self.account.positions.get(symbol, 0) + quantity
            if self.account.positions[symbol] == 0:
                del self.account.positions[symbol]
        
        # Log transaction
        self.account.transaction_history.append({
            'timestamp': self.current_time or datetime.now(),
            'symbol': symbol,
            'quantity': quantity,
            'price': price,
            'type': order_type,
            'balance': self.account.balance
        })
        
        logger.debug(f"Executed: {symbol} {quantity:+.2f} @ ${price:.2f}")
        return True
    
    def get_position(self, symbol: str) -> float:
        """Get current position."""
        return self.account.positions.get(symbol, 0)
    
    def close_position(self, symbol: str, price: float) -> bool:
        """Close position at price."""
        position = self.get_position(symbol)
        if position == 0:
            return False
        return self.execute_order(symbol, -position, price)
    
    def get_performance(self) -> Dict:
        """Calculate performance metrics."""
        total_return = (self.account.equity - self.account.initial_balance) / self.account.initial_balance
        
        # Calculate from transaction history
        transactions_df = pd.DataFrame(self.account.transaction_history) if self.account.transaction_history else pd.DataFrame()
        
        return {
            'initial_balance': self.account.initial_balance,
            'current_balance': self.account.balance,
            'equity': self.account.equity,
            'total_return': total_return,
            'total_trades': len(self.account.transaction_history),
            'positions': dict(self.account.positions)
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=" * 70)
    print("Paper Trading Engine - Self Test")
    print("=" * 70)
    
    engine = PaperTradingEngine(100000)
    
    # Test trades
    engine.execute_order('AAPL', 10, 150.0)
    print(f"Position: {engine.get_position('AAPL')}")
    
    engine.execute_order('AAPL', -5, 155.0)
    print(f"Position after partial sell: {engine.get_position('AAPL')}")
    
    perf = engine.get_performance()
    print(f"\nPerformance: Return={perf['total_return']:.2%}, Trades={perf['total_trades']}")
    print("\n✅ Paper trading engine test complete!")
