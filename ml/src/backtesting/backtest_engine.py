"""Backtest engine for options trading strategies.

Runs historical simulations of trading strategies with realistic
transaction costs, slippage, and position tracking.

Usage:
    from src.backtesting import BacktestEngine
    from src.models.options_pricing import BlackScholesModel
    
    # Initialize
    engine = BacktestEngine(
        initial_capital=10000,
        commission=0.65,
        slippage=0.01
    )
    
    # Load data
    engine.load_historical_data(ohlc_df, options_df)
    
    # Define strategy
    def simple_strategy(date, data, portfolio):
        # Your strategy logic
        return signals
    
    # Run backtest
    results = engine.run(simple_strategy)
    
    # Analyze
    print(f"Total Return: {results['total_return']:.2%}")
    print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")

References:
    - Pardo, R. (2008). "The Evaluation and Optimization of Trading Strategies"
"""

import logging
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..models.options_pricing import BlackScholesModel
from .performance_metrics import PerformanceMetrics
from .trade_logger import Trade, TradeLogger

logger = logging.getLogger(__name__)


class BacktestEngine:
    """Engine for backtesting options trading strategies.
    
    Features:
    - Historical data replay
    - Realistic transaction costs
    - Position tracking
    - Performance analytics
    - Risk management hooks
    """
    
    def __init__(
        self,
        initial_capital: float = 10000,
        commission_per_contract: float = 0.65,
        slippage_pct: float = 0.01,
        risk_free_rate: float = 0.05
    ):
        """Initialize backtest engine.
        
        Args:
            initial_capital: Starting portfolio value
            commission_per_contract: Commission per contract (default: $0.65)
            slippage_pct: Slippage as % of price (default: 1%)
            risk_free_rate: Annual risk-free rate for Sharpe calculation
        """
        self.initial_capital = initial_capital
        self.commission = commission_per_contract
        self.slippage_pct = slippage_pct
        self.risk_free_rate = risk_free_rate
        
        # Components
        self.trade_logger = TradeLogger()
        self.metrics = PerformanceMetrics()
        self.bs_model = BlackScholesModel(risk_free_rate=risk_free_rate)
        
        # State
        self.cash = initial_capital
        self.equity_curve = []
        self.dates = []
        
        # Data
        self.ohlc_data: Optional[pd.DataFrame] = None
        self.options_data: Optional[pd.DataFrame] = None
        
        logger.info(
            f"Initialized backtest engine: ${initial_capital:.2f} capital, "
            f"${commission:.2f} commission, {slippage_pct:.1%} slippage"
        )
    
    def load_historical_data(
        self,
        ohlc_data: pd.DataFrame,
        options_data: Optional[pd.DataFrame] = None
    ):
        """Load historical data for backtesting.
        
        Args:
            ohlc_data: OHLC data with columns: date, open, high, low, close, volume
            options_data: Options data with columns: date, symbol, strike, expiry,
                         option_type, bid, ask, volume, open_interest, iv
        """
        # Validate OHLC data
        required_cols = ['date', 'open', 'high', 'low', 'close']
        if not all(col in ohlc_data.columns for col in required_cols):
            raise ValueError(f"OHLC data must have columns: {required_cols}")
        
        self.ohlc_data = ohlc_data.copy()
        self.ohlc_data['date'] = pd.to_datetime(self.ohlc_data['date'])
        self.ohlc_data = self.ohlc_data.sort_values('date').reset_index(drop=True)
        
        if options_data is not None:
            self.options_data = options_data.copy()
            self.options_data['date'] = pd.to_datetime(self.options_data['date'])
            self.options_data = self.options_data.sort_values('date').reset_index(drop=True)
        
        logger.info(
            f"Loaded {len(self.ohlc_data)} days of OHLC data "
            f"({self.ohlc_data['date'].min()} to {self.ohlc_data['date'].max()})"
        )
        
        if self.options_data is not None:
            logger.info(f"Loaded {len(self.options_data)} options data points")
    
    def get_current_prices(self, date: pd.Timestamp) -> Dict[str, float]:
        """Get current prices for open positions.
        
        Args:
            date: Current date
        
        Returns:
            Dictionary of symbol -> current_price
        """
        prices = {}
        
        # Get underlying price from OHLC
        if self.ohlc_data is not None:
            ohlc_row = self.ohlc_data[self.ohlc_data['date'] == date]
            if not ohlc_row.empty:
                underlying_price = float(ohlc_row['close'].iloc[0])
            else:
                underlying_price = None
        else:
            underlying_price = None
        
        # Get options prices
        if self.options_data is not None and underlying_price is not None:
            options_today = self.options_data[self.options_data['date'] == date]
            
            for _, opt in options_today.iterrows():
                symbol = opt['symbol']
                
                # Use mid price (bid-ask midpoint)
                if 'bid' in opt and 'ask' in opt:
                    mid_price = (opt['bid'] + opt['ask']) / 2
                elif 'price' in opt:
                    mid_price = opt['price']
                else:
                    # Fallback: Calculate theoretical price
                    strike = opt['strike']
                    expiry = pd.to_datetime(opt['expiry'])
                    dte = (expiry - date).days
                    iv = opt.get('iv', 0.30)
                    option_type = opt.get('option_type', 'call')
                    
                    pricing = self.bs_model.calculate_greeks(
                        S=underlying_price,
                        K=strike,
                        T=dte/365,
                        sigma=iv,
                        option_type=option_type
                    )
                    mid_price = pricing.theoretical_price
                
                prices[symbol] = mid_price
        
        return prices
    
    def calculate_portfolio_value(self, date: pd.Timestamp) -> float:
        """Calculate current portfolio value.
        
        Args:
            date: Current date
        
        Returns:
            Total portfolio value (cash + positions)
        """
        # Start with cash
        portfolio_value = self.cash
        
        # Add value of open positions
        current_prices = self.get_current_prices(date)
        
        for symbol, position in self.trade_logger.positions.items():
            if symbol in current_prices:
                position_value = position.current_value(current_prices[symbol])
                portfolio_value += position_value
        
        return portfolio_value
    
    def execute_trade(
        self,
        date: pd.Timestamp,
        symbol: str,
        action: str,
        quantity: int,
        price: Optional[float] = None,
        strategy_name: str = ""
    ) -> bool:
        """Execute a trade with realistic costs.
        
        Args:
            date: Trade date
            symbol: Option symbol
            action: 'BUY' or 'SELL'
            quantity: Number of contracts
            price: Price per contract (if None, uses market price)
            strategy_name: Name of strategy
        
        Returns:
            True if trade executed successfully, False otherwise
        """
        # Get underlying price
        ohlc_row = self.ohlc_data[self.ohlc_data['date'] == date]
        if ohlc_row.empty:
            logger.warning(f"No OHLC data for {date}")
            return False
        
        underlying_price = float(ohlc_row['close'].iloc[0])
        
        # Get option price
        if price is None:
            current_prices = self.get_current_prices(date)
            if symbol not in current_prices:
                logger.warning(f"No price available for {symbol} on {date}")
                return False
            price = current_prices[symbol]
        
        # Apply slippage
        slippage = self.slippage_pct * price
        
        # Create trade
        trade = Trade(
            timestamp=str(date),
            symbol=symbol,
            action=action,
            quantity=quantity,
            price=price,
            underlying_price=underlying_price,
            commission=self.commission,
            slippage=slippage,
            strategy_name=strategy_name
        )
        
        # Check if we have enough cash for BUY orders
        if action == 'BUY':
            required_cash = trade.total_cost()
            if required_cash > self.cash:
                logger.warning(
                    f"Insufficient cash for trade: need ${required_cash:.2f}, "
                    f"have ${self.cash:.2f}"
                )
                return False
            
            self.cash -= required_cash
        else:  # SELL
            self.cash -= trade.total_cost()  # total_cost() is negative for SELL
        
        # Log trade
        self.trade_logger.log_trade(trade)
        
        logger.debug(
            f"{action} {quantity} {symbol} @ ${price:.2f} "
            f"(cost: ${trade.total_cost():.2f}, cash: ${self.cash:.2f})"
        )
        
        return True
    
    def run(
        self,
        strategy: Callable,
        start_date: Optional[pd.Timestamp] = None,
        end_date: Optional[pd.Timestamp] = None,
        rebalance_freq: str = 'daily'
    ) -> Dict:
        """Run backtest with given strategy.
        
        Args:
            strategy: Callable that takes (date, data, portfolio) and returns signals
            start_date: Start date for backtest (None = first date in data)
            end_date: End date for backtest (None = last date in data)
            rebalance_freq: Rebalancing frequency ('daily', 'weekly', 'monthly')
        
        Returns:
            Dictionary with backtest results including metrics and equity curve
        """
        if self.ohlc_data is None:
            raise ValueError("Must load historical data before running backtest")
        
        # Reset state
        self.cash = self.initial_capital
        self.equity_curve = []
        self.dates = []
        self.trade_logger.reset()
        
        # Filter data by date range
        if start_date:
            mask = self.ohlc_data['date'] >= start_date
            data = self.ohlc_data[mask].copy()
        else:
            data = self.ohlc_data.copy()
        
        if end_date:
            mask = data['date'] <= end_date
            data = data[mask].copy()
        
        logger.info(
            f"Running backtest from {data['date'].min()} to {data['date'].max()} "
            f"({len(data)} days)"
        )
        
        # Main backtest loop
        for idx, row in data.iterrows():
            date = row['date']
            
            # Calculate portfolio value
            portfolio_value = self.calculate_portfolio_value(date)
            self.equity_curve.append(portfolio_value)
            self.dates.append(date)
            
            # Get data for strategy
            strategy_data = {
                'date': date,
                'ohlc': row,
                'positions': self.trade_logger.get_positions(),
                'cash': self.cash,
                'portfolio_value': portfolio_value
            }
            
            if self.options_data is not None:
                strategy_data['options'] = self.options_data[
                    self.options_data['date'] == date
                ]
            
            # Run strategy
            try:
                signals = strategy(strategy_data)
                
                # Execute signals
                if signals:
                    for signal in signals:
                        self.execute_trade(
                            date=date,
                            symbol=signal.get('symbol'),
                            action=signal.get('action'),
                            quantity=signal.get('quantity', 1),
                            price=signal.get('price'),
                            strategy_name=signal.get('strategy_name', '')
                        )
            except Exception as e:
                logger.error(f"Strategy error on {date}: {e}")
                continue
        
        # Final portfolio value
        final_value = self.calculate_portfolio_value(self.dates[-1])
        self.equity_curve[-1] = final_value
        
        # Calculate performance metrics
        equity_series = pd.Series(self.equity_curve, index=self.dates)
        
        # Get trade returns
        trade_history = self.trade_logger.get_trade_history()
        if not trade_history.empty:
            # Calculate per-trade returns (simplified)
            trade_returns = pd.Series()
        else:
            trade_returns = None
        
        metrics = self.metrics.calculate_all(
            equity_curve=equity_series,
            risk_free_rate=self.risk_free_rate,
            trade_returns=trade_returns
        )
        
        # Get P&L
        current_prices = self.get_current_prices(self.dates[-1])
        pnl = self.trade_logger.calculate_pnl(current_prices)
        
        # Compile results
        results = {
            'equity_curve': equity_series,
            'dates': self.dates,
            'final_value': final_value,
            'total_return': (final_value - self.initial_capital) / self.initial_capital,
            'trade_history': trade_history,
            'positions': self.trade_logger.get_positions(),
            'pnl': pnl,
            **metrics
        }
        
        logger.info(
            f"Backtest complete: ${self.initial_capital:.2f} → ${final_value:.2f} "
            f"({results['total_return']:.2%} return, {pnl['num_trades']} trades)"
        )
        
        return results


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("Backtest Engine - Self Test")
    print("=" * 70)
    
    # Create sample data
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
    
    # OHLC data
    close_prices = 100 * (1 + np.random.randn(len(dates)).cumsum() * 0.01)
    ohlc_data = pd.DataFrame({
        'date': dates,
        'open': close_prices * 0.99,
        'high': close_prices * 1.01,
        'low': close_prices * 0.98,
        'close': close_prices,
        'volume': np.random.randint(1000000, 10000000, len(dates))
    })
    
    # Initialize engine
    engine = BacktestEngine(initial_capital=10000)
    engine.load_historical_data(ohlc_data)
    
    # Simple buy-and-hold strategy (for testing)
    bought = False
    
    def simple_strategy(data):
        global bought
        signals = []
        
        # Buy on first day
        if not bought and data['cash'] >= 1000:
            signals.append({
                'symbol': 'TEST_CALL',
                'action': 'BUY',
                'quantity': 1,
                'price': 10.0,
                'strategy_name': 'Buy and Hold'
            })
            bought = True
        
        return signals
    
    # Run backtest
    print("\n🔄 Running backtest...")
    results = engine.run(simple_strategy)
    
    # Display results
    print("\n📊 Backtest Results:")
    print(f"Initial Capital: ${engine.initial_capital:.2f}")
    print(f"Final Value: ${results['final_value']:.2f}")
    print(f"Total Return: {results['total_return']:.2%}")
    print(f"Total Trades: {results['pnl']['num_trades']}")
    
    if 'sharpe_ratio' in results:
        print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
    if 'max_drawdown' in results:
        print(f"Max Drawdown: {results['max_drawdown']:.2%}")
    
    print("\n" + "=" * 70)
    print("✅ Backtest engine test complete!")
    print("=" * 70)
