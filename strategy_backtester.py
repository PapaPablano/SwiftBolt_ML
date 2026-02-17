"""
Strategy Backtester for SwiftBolt Trading System
This module provides tools to backtest trading strategies without ML integration.

Key Features:
- Strategy configuration management
- Backtesting engine with performance metrics
- Visualization of results
- Simulated trading environment
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict

@dataclass
class Trade:
    """Represents a single trade execution"""
    symbol: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    position_size: int
    trade_type: str  # 'BUY' or 'SELL'
    profit_loss: float = 0.0
    profit_loss_pct: float = 0.0

@dataclass
class StrategyConfig:
    """Configuration for a trading strategy"""
    name: str
    description: str
    parameters: Dict[str, Any]
    indicators: List[str]
    signal_filter: str  # 'buy', 'sell', 'both'
    
@dataclass
class BacktestResult:
    """Results of a strategy backtest"""
    strategy_name: str
    start_date: datetime
    end_date: datetime
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_profit: float
    total_return: float
    max_drawdown: float
    sharpe_ratio: float
    trade_details: List[Trade]
    performance_metrics: Dict[str, float]

class MockDataGenerator:
    """Generates mock market data for backtesting without external dependencies"""
    
    @staticmethod
    def generate_mock_data(symbol: str, start_date: datetime, end_date: datetime, 
                          volatility: float = 0.02, trend: float = 0.001) -> pd.DataFrame:
        """Generate mock price data for backtesting"""
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        base_price = 100.0
        
        # Generate random walk with trend and volatility
        returns = np.random.normal(trend, volatility, len(dates))
        prices = [base_price]
        
        for ret in returns[1:]:
            new_price = prices[-1] * (1 + ret)
            prices.append(max(0.01, new_price))  # Ensure positive prices
            
        # Add some technical indicators
        df = pd.DataFrame({
            'date': dates,
            'open': prices[:-1],
            'high': [p * (1 + np.random.uniform(0, 0.03)) for p in prices[:-1]],
            'low': [p * (1 - np.random.uniform(0, 0.03)) for p in prices[:-1]],
            'close': prices[1:],
            'volume': np.random.randint(1000, 100000, len(dates) - 1)
        })
        
        # Add technical indicators
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['ema_12'] = df['close'].ewm(span=12).mean()
        df['ema_26'] = df['close'].ewm(span=26).mean()
        df['rsi'] = MockDataGenerator._calculate_rsi(df['close'])
        df['macd'] = df['ema_12'] - df['ema_26']
        df['signal_line'] = df['macd'].ewm(span=9).mean()
        df['bollinger_upper'] = df['sma_20'] + (df['close'].rolling(window=20).std() * 2)
        df['bollinger_lower'] = df['sma_20'] - (df['close'].rolling(window=20).std() * 2)
        
        return df.dropna()
    
    @staticmethod
    def _calculate_rsi(prices: pd.Series, window: int = 14) -> pd.Series:
        """Calculate RSI (Relative Strength Index)"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

class StrategyBacktester:
    """Backtester for trading strategies with simulated trades"""
    
    def __init__(self, data: pd.DataFrame):
        self.data = data
        self.trades = []
        
    def run_simple_strategy(self, buy_signal_func, sell_signal_func, 
                          initial_capital: float = 10000.0, position_size: int = 100) -> BacktestResult:
        """
        Run a simple strategy backtest
        
        Args:
            buy_signal_func: Function that returns True when to buy
            sell_signal_func: Function that returns True when to sell
            initial_capital: Starting capital for backtest
            position_size: Number of shares to trade per signal
        """
        cash = initial_capital
        shares = 0
        portfolio_value_history = []
        
        # Initialize trading state
        buy_signals = []
        sell_signals = []
        trade_history = []
        current_position = None
        
        # Get data for loop
        dates = self.data['date'].tolist()
        closes = self.data['close'].tolist()
        opens = self.data['open'].tolist()
        
        # Track portfolio value over time
        portfolio_value_history.append(cash + shares * closes[0])
        
        for i in range(1, len(dates)):
            current_date = dates[i]
            current_price = closes[i]
            open_price = opens[i]
            prev_price = closes[i-1]
            
            # Check for buy signals
            if buy_signal_func(self.data.iloc[:i+1]) and shares == 0:
                buy_signals.append(current_date)
                trade_size = min(position_size, int(cash / current_price))
                if trade_size > 0:
                    shares += trade_size
                    cash -= trade_size * current_price
                    # Record trade
                    trade = Trade(
                        symbol="TEST",
                        entry_time=current_date,
                        exit_time=None,
                        entry_price=current_price,
                        exit_price=0,
                        position_size=trade_size,
                        trade_type="BUY",
                        profit_loss=0,
                        profit_loss_pct=0,
                    )
                    trade_history.append(trade)
                    current_position = trade
                    
            # Check for sell signals
            elif sell_signal_func(self.data.iloc[:i+1]) and shares > 0 and current_position:
                sell_signals.append(current_date)
                
                # Record trade
                if current_position:
                    current_position.exit_time = current_date
                    current_position.exit_price = current_price
                    profit = (current_position.exit_price - current_position.entry_price) * current_position.position_size
                    current_position.profit_loss = profit
                    current_position.profit_loss_pct = (profit / (current_position.position_size * current_position.entry_price)) * 100
                    
                # Close position
                cash += shares * current_price
                shares = 0
                # Add to trades list if we had current_position
                if current_position:
                    trade_history[-1] = current_position  # Replace last with complete info
            
            # Update portfolio value for current date
            portfolio_value = cash + shares * current_price
            portfolio_value_history.append(portfolio_value)
        
        total_trades = len(buy_signals) + len(sell_signals)
        winning_trades = sum(1 for trade in trade_history if trade.profit_loss > 0)
        losing_trades = total_trades - winning_trades
        
        # Calculate final metrics
        total_return = ((portfolio_value_history[-1] - initial_capital) / initial_capital) * 100
        total_profit = portfolio_value_history[-1] - initial_capital
        max_drawdown = self._calculate_max_drawdown(portfolio_value_history)
        sharpe_ratio = self._calculate_sharpe_ratio(portfolio_value_history, risk_free_rate=0.02)
        
        # Create result
        result = BacktestResult(
            strategy_name="SimpleStrategy",
            start_date=dates[0],
            end_date=dates[-1],
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            total_profit=total_profit,
            total_return=total_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            trade_details=trade_history,
            performance_metrics={
                'win_rate': winning_trades / total_trades if total_trades > 0 else 0,
                'avg_profit': total_profit / total_trades if total_trades > 0 else 0,
                'avg_win': sum(t.profit_loss for t in trade_history if t.profit_loss > 0) / winning_trades if winning_trades > 0 else 0,
                'avg_loss': sum(t.profit_loss for t in trade_history if t.profit_loss < 0) / losing_trades if losing_trades > 0 else 0,
            }
        )
        
        return result
    
    def _calculate_max_drawdown(self, portfolio_values: List[float]) -> float:
        """Calculate maximum drawdown of portfolio"""
        peak = portfolio_values[0]
        max_dd = 0
        
        for value in portfolio_values:
            if value > peak:
                peak = value
            dd = (peak - value) / peak
            if dd > max_dd:
                max_dd = dd
                
        return max_dd
    
    def _calculate_sharpe_ratio(self, portfolio_values: List[float], risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio for portfolio"""
        returns = []
        for i in range(1, len(portfolio_values)):
            returns.append((portfolio_values[i] - portfolio_values[i-1]) / portfolio_values[i-1])
            
        if len(returns) < 2:
            return 0.0
            
        avg_return = np.mean(returns)
        std_dev = np.std(returns)
        
        if std_dev == 0:
            return 0.0
            
        sharpe = (avg_return - risk_free_rate) / std_dev
        return sharpe
    
    def visualize_results(self, result: BacktestResult, data: pd.DataFrame):
        """Visualize backtest results"""
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10))
        
        # Plot price and signals
        ax1.plot(data['date'], data['close'], label='Close Price')
        ax1.set_title('Price with Strategy Signals')
        ax1.set_ylabel('Price')
        ax1.legend()
        
        # Plot portfolio value over time  
        portfolio_values = [10000.0]  # Starting capital
        for i in range(1, len(data)):
            portfolio_values.append(portfolio_values[-1] + (data['close'].iloc[i] - data['close'].iloc[i-1]) * 100)  # Simplified
            
        ax2.plot(data['date'], portfolio_values, label='Portfolio Value')
        ax2.set_title('Portfolio Value Over Time')
        ax2.set_ylabel('Portfolio Value')
        ax2.legend()
        
        # Plot performance metrics
        metrics = ['Win Rate', 'Profit per Trade', 'Max Drawdown']
        values = [
            result.performance_metrics['win_rate'],
            result.performance_metrics['avg_profit'],
            result.max_drawdown
        ]
        ax3.bar(metrics, values)
        ax3.set_title('Performance Metrics')
        ax3.set_ylabel('Values')
        
        plt.tight_layout()
        plt.show()

# Example usage functions
def simple_moving_average_cross_signal(df: pd.DataFrame) -> bool:
    """Simple moving average crossover signal"""
    if len(df) < 30:
        return False
    
    sma_5 = df['close'].tail(5).mean()
    sma_20 = df['close'].tail(20).mean()
    
    # Buy when short SMA crosses above long SMA
    return sma_5 > sma_20

def rsi_overbought_oversold_signal(df: pd.DataFrame) -> bool:
    """RSI overbought/oversold signal"""
    if len(df) < 15:
        return False
    
    rsi = df['rsi'].tail(1).iloc[0]
    
    # Buy when RSI is below 30 (oversold)
    return rsi < 30

def main():
    """Main function to demonstrate backtester usage"""
    print("Initializing Strategy Backtester...")
    
    # Generate mock data for testing
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2023, 12, 31)
    
    data = MockDataGenerator.generate_mock_data("TEST", start_date, end_date)
    print(f"Generated {len(data)} data points")
    
    # Create backtester
    backtester = StrategyBacktester(data)
    
    # Test simple strategy
    result = backtester.run_simple_strategy(
        buy_signal_func=simple_moving_average_cross_signal,
        sell_signal_func=lambda df: False,  # Don't sell in this example
        initial_capital=10000.0,
        position_size=100
    )
    
    print("=== BACKTEST RESULTS ===")
    print(f"Strategy: {result.strategy_name}")
    print(f"Period: {result.start_date} to {result.end_date}")
    print(f"Total Trades: {result.total_trades}")
    print(f"Winning Trades: {result.winning_trades}")
    print(f"Losing Trades: {result.losing_trades}")
    print(f"Total Profit: ${result.total_profit:.2f}")
    print(f"Total Return: {result.total_return:.2f}%")
    print(f"Max Drawdown: {result.max_drawdown:.2f}")
    print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
    print(f"Win Rate: {result.performance_metrics['win_rate']:.2f}")
    
    # Visualize results
    backtester.visualize_results(result, data)

if __name__ == "__main__":
    main()