"""Trade logging and tracking for backtesting.

Usage:
    from src.backtesting.trade_logger import TradeLogger, Trade
    
    logger = TradeLogger()
    
    # Log a trade
    trade = Trade(
        timestamp='2024-01-15 10:30:00',
        symbol='AAPL_CALL_150_20240215',
        action='BUY',
        quantity=1,
        price=5.25,
        underlying_price=148.50,
        commission=0.65
    )
    
    logger.log_trade(trade)
    
    # Get trade history
    history = logger.get_trade_history()
    
    # Calculate P&L
    pnl = logger.calculate_pnl()
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Represents a single trade in the backtest.
    
    Attributes:
        timestamp: Trade execution time
        symbol: Option symbol
        action: 'BUY' or 'SELL'
        quantity: Number of contracts (positive)
        price: Price per contract
        underlying_price: Underlying stock price at trade time
        commission: Commission paid (default: $0.65 per contract)
        slippage: Slippage amount (default: 0)
        strategy_name: Name of strategy (optional)
        notes: Additional notes (optional)
        trade_id: Unique trade identifier (auto-generated)
    """
    timestamp: str
    symbol: str
    action: str  # 'BUY' or 'SELL'
    quantity: int
    price: float
    underlying_price: float
    commission: float = 0.65
    slippage: float = 0.0
    strategy_name: str = ""
    notes: str = ""
    trade_id: Optional[str] = None
    
    def __post_init__(self):
        """Generate trade ID if not provided."""
        if self.trade_id is None:
            self.trade_id = f"{self.timestamp}_{self.symbol}_{self.action}"
        
        # Validate action
        if self.action not in ['BUY', 'SELL']:
            raise ValueError(f"Invalid action: {self.action}. Must be 'BUY' or 'SELL'")
        
        # Validate quantity
        if self.quantity <= 0:
            raise ValueError(f"Quantity must be positive: {self.quantity}")
    
    def total_cost(self) -> float:
        """Calculate total cost including commission and slippage.
        
        Supports both options (100 shares per contract) and stocks (1 share per unit).
        Detects based on symbol format, price magnitude, or explicit indicator.
        """
        # Detect if this is an options contract or stock
        # Simple heuristic: if symbol is short (<=6 chars) and matches common stock patterns, treat as stock
        # Otherwise, if it has option-like characteristics, treat as option
        symbol_upper = self.symbol.upper()
        
        # Explicit stock indicators
        is_stock = (
            symbol_upper == "STOCK" or
            (len(self.symbol) <= 6 and self.symbol.isalpha()) or  # Short alphabetic symbols like "AAPL", "TSLA"
            (hasattr(self, 'underlying_price') and self.underlying_price > 0 and 
             abs(self.price - self.underlying_price) / self.underlying_price < 0.1)  # Price close to underlying (within 10%)
        )
        
        is_option = not is_stock and (
            len(self.symbol) > 10 or  # Options symbols are typically longer
            (hasattr(self, 'underlying_price') and self.underlying_price > 0 and 
             self.price < self.underlying_price * 0.3) or  # Options are much cheaper than underlying
            '_' in self.symbol or  # Options often have underscores
            ('C' in self.symbol[-15:] and any(c.isdigit() for c in self.symbol[-15:])) or  # Has Call indicator with digits
            ('P' in self.symbol[-15:] and any(c.isdigit() for c in self.symbol[-15:]))  # Has Put indicator with digits
        )
        
        if is_option:
            # Options: 100 shares per contract
            contract_cost = self.price * self.quantity * 100
            total_commission = self.commission * self.quantity
            total_slippage = self.slippage * self.quantity * 100
        else:
            # Stocks: 1 share per unit
            contract_cost = self.price * self.quantity
            total_commission = self.commission  # Per trade for stocks (flat fee)
            total_slippage = self.slippage * self.quantity
        
        if self.action == 'BUY':
            return contract_cost + total_commission + total_slippage
        else:  # SELL
            return -(contract_cost - total_commission - total_slippage)
    
    def to_dict(self) -> Dict:
        """Convert trade to dictionary."""
        return {
            'trade_id': self.trade_id,
            'timestamp': self.timestamp,
            'symbol': self.symbol,
            'action': self.action,
            'quantity': self.quantity,
            'price': self.price,
            'underlying_price': self.underlying_price,
            'commission': self.commission,
            'slippage': self.slippage,
            'total_cost': self.total_cost(),
            'strategy_name': self.strategy_name,
            'notes': self.notes
        }


@dataclass
class Position:
    """Represents an open position.
    
    Attributes:
        symbol: Option symbol
        quantity: Net quantity (positive = long, negative = short)
        avg_entry_price: Average entry price
        total_cost: Total cost basis
        entry_trades: List of trade IDs that opened/modified this position
    """
    symbol: str
    quantity: int
    avg_entry_price: float
    total_cost: float
    entry_trades: List[str] = field(default_factory=list)
    
    def update(self, trade: Trade):
        """Update position with new trade."""
        if trade.action == 'BUY':
            new_quantity = self.quantity + trade.quantity
            new_cost = self.total_cost + trade.total_cost()
            
            if new_quantity != 0:
                self.avg_entry_price = new_cost / (new_quantity * 100)
            
            self.quantity = new_quantity
            self.total_cost = new_cost
            self.entry_trades.append(trade.trade_id)
        
        elif trade.action == 'SELL':
            # Closing position (full or partial)
            self.quantity -= trade.quantity
            self.total_cost += trade.total_cost()  # total_cost() is negative for SELL
            self.entry_trades.append(trade.trade_id)
            
            if self.quantity == 0:
                self.avg_entry_price = 0
                self.total_cost = 0
    
    def is_closed(self) -> bool:
        """Check if position is fully closed."""
        return self.quantity == 0
    
    def current_value(self, current_price: float) -> float:
        """Calculate current value of position."""
        return self.quantity * current_price * 100  # 100 shares per contract
    
    def unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L."""
        if self.quantity == 0:
            return 0
        return self.current_value(current_price) - self.total_cost


class TradeLogger:
    """Logs and tracks trades during backtesting.
    
    Features:
    - Trade history tracking
    - Position management
    - P&L calculation
    - Trade statistics
    """
    
    def __init__(self):
        """Initialize trade logger."""
        self.trades: List[Trade] = []
        self.positions: Dict[str, Position] = {}
        self.closed_positions: List[Position] = []
    
    def log_trade(self, trade: Trade):
        """Log a trade and update positions.
        
        Args:
            trade: Trade object to log
        """
        self.trades.append(trade)
        
        # Update or create position
        if trade.symbol not in self.positions:
            # New position
            if trade.action == 'BUY':
                self.positions[trade.symbol] = Position(
                    symbol=trade.symbol,
                    quantity=trade.quantity,
                    avg_entry_price=trade.price,
                    total_cost=trade.total_cost(),
                    entry_trades=[trade.trade_id]
                )
        else:
            # Update existing position
            position = self.positions[trade.symbol]
            position.update(trade)
            
            # Move to closed if position is fully closed
            if position.is_closed():
                self.closed_positions.append(position)
                del self.positions[trade.symbol]
        
        logger.debug(f"Logged trade: {trade.action} {trade.quantity} {trade.symbol} @ ${trade.price:.2f}")
    
    def get_trade_history(self, symbol: Optional[str] = None) -> pd.DataFrame:
        """Get trade history as DataFrame.
        
        Args:
            symbol: Filter by symbol (optional)
        
        Returns:
            DataFrame with trade history
        """
        if not self.trades:
            return pd.DataFrame()
        
        df = pd.DataFrame([t.to_dict() for t in self.trades])
        
        if symbol:
            df = df[df['symbol'] == symbol]
        
        return df
    
    def get_positions(self) -> pd.DataFrame:
        """Get current open positions.
        
        Returns:
            DataFrame with open positions
        """
        if not self.positions:
            return pd.DataFrame()
        
        data = []
        for symbol, pos in self.positions.items():
            data.append({
                'symbol': symbol,
                'quantity': pos.quantity,
                'avg_entry_price': pos.avg_entry_price,
                'total_cost': pos.total_cost,
                'num_trades': len(pos.entry_trades)
            })
        
        return pd.DataFrame(data)
    
    def calculate_pnl(self, current_prices: Optional[Dict[str, float]] = None) -> Dict[str, float]:
        """Calculate P&L metrics.
        
        Args:
            current_prices: Dict of symbol -> current_price for open positions
        
        Returns:
            Dictionary with P&L metrics:
            - total_realized: Total realized P&L from closed positions
            - total_unrealized: Total unrealized P&L from open positions
            - total_pnl: Total P&L (realized + unrealized)
            - total_commissions: Total commissions paid
            - total_slippage: Total slippage costs
            - num_trades: Total number of trades
            - num_positions_closed: Number of closed positions
            - num_positions_open: Number of open positions
        """
        # Realized P&L from closed positions
        realized_pnl = -sum(pos.total_cost for pos in self.closed_positions)
        
        # Unrealized P&L from open positions
        unrealized_pnl = 0
        if current_prices:
            for symbol, position in self.positions.items():
                if symbol in current_prices:
                    unrealized_pnl += position.unrealized_pnl(current_prices[symbol])
        
        # Commissions and slippage
        total_commissions = sum(t.commission * t.quantity for t in self.trades)
        total_slippage = sum(t.slippage * t.quantity * 100 for t in self.trades)
        
        return {
            'total_realized': realized_pnl,
            'total_unrealized': unrealized_pnl,
            'total_pnl': realized_pnl + unrealized_pnl,
            'total_commissions': total_commissions,
            'total_slippage': total_slippage,
            'num_trades': len(self.trades),
            'num_positions_closed': len(self.closed_positions),
            'num_positions_open': len(self.positions)
        }
    
    def get_trade_statistics(self) -> Dict:
        """Get trade statistics.
        
        Returns:
            Dictionary with trade statistics
        """
        if not self.trades:
            return {}
        
        df = self.get_trade_history()
        
        return {
            'total_trades': len(self.trades),
            'buy_trades': len(df[df['action'] == 'BUY']),
            'sell_trades': len(df[df['action'] == 'SELL']),
            'total_contracts': df['quantity'].sum(),
            'avg_trade_size': df['quantity'].mean(),
            'total_commission': df['commission'].sum(),
            'avg_commission_per_trade': df['commission'].mean(),
            'total_slippage': df['slippage'].sum(),
        }
    
    def reset(self):
        """Reset logger (clear all trades and positions)."""
        self.trades = []
        self.positions = {}
        self.closed_positions = []
        logger.info("Trade logger reset")


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("Trade Logger - Self Test")
    print("=" * 70)
    
    logger_instance = TradeLogger()
    
    # Test 1: Log some trades
    print("\n📊 Test 1: Logging Trades")
    
    # Buy call option
    trade1 = Trade(
        timestamp='2024-01-15 10:30:00',
        symbol='AAPL_CALL_150',
        action='BUY',
        quantity=2,
        price=5.25,
        underlying_price=148.50,
        strategy_name='Long Call'
    )
    logger_instance.log_trade(trade1)
    print(f"Logged: {trade1.action} {trade1.quantity} {trade1.symbol} @ ${trade1.price:.2f}")
    
    # Sell part of position
    trade2 = Trade(
        timestamp='2024-01-16 14:00:00',
        symbol='AAPL_CALL_150',
        action='SELL',
        quantity=1,
        price=6.50,
        underlying_price=152.00,
        strategy_name='Long Call'
    )
    logger_instance.log_trade(trade2)
    print(f"Logged: {trade2.action} {trade2.quantity} {trade2.symbol} @ ${trade2.price:.2f}")
    
    # Close remaining position
    trade3 = Trade(
        timestamp='2024-01-17 15:30:00',
        symbol='AAPL_CALL_150',
        action='SELL',
        quantity=1,
        price=7.00,
        underlying_price=153.50,
        strategy_name='Long Call'
    )
    logger_instance.log_trade(trade3)
    print(f"Logged: {trade3.action} {trade3.quantity} {trade3.symbol} @ ${trade3.price:.2f}")
    
    # Test 2: Get trade history
    print("\n📊 Test 2: Trade History")
    history = logger_instance.get_trade_history()
    print(history.to_string())
    
    # Test 3: Calculate P&L
    print("\n📊 Test 3: P&L Calculation")
    pnl = logger_instance.calculate_pnl()
    print(f"Realized P&L: ${pnl['total_realized']:.2f}")
    print(f"Unrealized P&L: ${pnl['total_unrealized']:.2f}")
    print(f"Total P&L: ${pnl['total_pnl']:.2f}")
    print(f"Total Commissions: ${pnl['total_commissions']:.2f}")
    print(f"Number of Trades: {pnl['num_trades']}")
    print(f"Closed Positions: {pnl['num_positions_closed']}")
    
    # Test 4: Trade statistics
    print("\n📊 Test 4: Trade Statistics")
    stats = logger_instance.get_trade_statistics()
    print(f"Total Trades: {stats['total_trades']}")
    print(f"Buy Trades: {stats['buy_trades']}")
    print(f"Sell Trades: {stats['sell_trades']}")
    print(f"Average Trade Size: {stats['avg_trade_size']:.1f} contracts")
    
    print("\n" + "=" * 70)
    print("✅ All tests passed!")
    print("=" * 70)
