#!/usr/bin/env python3
"""
CLI script to run backtests for trading strategies.
Returns JSON output for use by Edge Functions.

Usage:
    python run_backtest.py --symbol AAPL --strategy supertrend_ai --start 2024-01-01 --end 2024-12-31

Strategies:
    - supertrend_ai: SuperTrend AI with adaptive factor
    - sma_crossover: Simple moving average crossover
    - buy_and_hold: Buy and hold baseline
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.supabase_db import SupabaseDatabase
from src.backtesting.backtest_engine import BacktestEngine
from src.strategies.supertrend_ai import SuperTrendAI

logging.basicConfig(level=logging.WARNING)  # Suppress verbose logs
logger = logging.getLogger(__name__)


def create_supertrend_ai_strategy(df: pd.DataFrame, params: dict):
    """Create SuperTrend AI strategy function."""
    atr_length = params.get("atr_length", 10)
    min_mult = params.get("min_mult", 1.0)
    max_mult = params.get("max_mult", 5.0)
    step = params.get("step", 0.5)
    
    # Calculate SuperTrend AI
    supertrend = SuperTrendAI(
        df=df,
        atr_length=atr_length,
        min_mult=min_mult,
        max_mult=max_mult,
        step=step
    )
    result_df, info = supertrend.calculate()
    
    # Create strategy function
    def strategy(data):
        signals = []
        date = data['date']
        
        # Find matching row in result_df
        if 'ts' in result_df.columns:
            matching = result_df[result_df['ts'] == date]
        else:
            # Try to match by index if ts column doesn't exist
            idx = df.index[df.index == date]
            if len(idx) > 0:
                matching = result_df.iloc[[idx[0]]] if idx[0] < len(result_df) else pd.DataFrame()
            else:
                matching = pd.DataFrame()
        
        if not matching.empty:
            row = matching.iloc[0]
            signal = row.get('signal', 0)
            
            # Generate buy/sell signals based on SuperTrend
            if signal == 1 and data['cash'] >= 1000:  # Buy signal
                signals.append({
                    'symbol': 'STOCK',
                    'action': 'BUY',
                    'quantity': int(data['cash'] / data['ohlc']['close'] * 0.95),  # Use 95% of cash
                    'price': data['ohlc']['close'],
                    'strategy_name': 'SuperTrend AI'
                })
            elif signal == -1:  # Sell signal
                # Close all positions
                positions = data['positions']
                for pos in positions:
                    signals.append({
                        'symbol': pos['symbol'],
                        'action': 'SELL',
                        'quantity': pos['quantity'],
                        'price': data['ohlc']['close'],
                        'strategy_name': 'SuperTrend AI'
                    })
        
        return signals
    
    return strategy


def create_sma_crossover_strategy(df: pd.DataFrame, params: dict):
    """Create SMA crossover strategy function."""
    fast_period = params.get("fast_period", 20)
    slow_period = params.get("slow_period", 50)
    
    # Calculate SMAs
    df['sma_fast'] = df['close'].rolling(window=fast_period).mean()
    df['sma_slow'] = df['close'].rolling(window=slow_period).mean()
    df['signal'] = 0
    df.loc[df['sma_fast'] > df['sma_slow'], 'signal'] = 1
    df.loc[df['sma_fast'] < df['sma_slow'], 'signal'] = -1
    
    def strategy(data):
        signals = []
        date = data['date']
        
        # Find matching row
        matching = df[df.index == date]
        if not matching.empty:
            row = matching.iloc[0]
            signal = row.get('signal', 0)
            
            if signal == 1 and data['cash'] >= 1000:  # Buy
                signals.append({
                    'symbol': 'STOCK',
                    'action': 'BUY',
                    'quantity': int(data['cash'] / data['ohlc']['close'] * 0.95),
                    'price': data['ohlc']['close'],
                    'strategy_name': f'SMA({fast_period}/{slow_period})'
                })
            elif signal == -1:  # Sell
                positions = data['positions']
                for pos in positions:
                    signals.append({
                        'symbol': pos['symbol'],
                        'action': 'SELL',
                        'quantity': pos['quantity'],
                        'price': data['ohlc']['close'],
                        'strategy_name': f'SMA({fast_period}/{slow_period})'
                    })
        
        return signals
    
    return strategy


def create_buy_and_hold_strategy():
    """Create simple buy and hold strategy."""
    bought = False
    
    def strategy(data):
        nonlocal bought
        signals = []
        
        if not bought and data['cash'] >= 1000:
            signals.append({
                'symbol': 'STOCK',
                'action': 'BUY',
                'quantity': int(data['cash'] / data['ohlc']['close'] * 0.95),
                'price': data['ohlc']['close'],
                'strategy_name': 'Buy and Hold'
            })
            bought = True
        
        return signals
    
    return strategy


def run_backtest(
    symbol: str,
    strategy_name: str,
    start_date: str,
    end_date: str,
    timeframe: str = "d1",
    initial_capital: float = 10000,
    strategy_params: dict = None
) -> dict:
    """
    Run backtest for a symbol/strategy.
    
    Args:
        symbol: Stock ticker symbol
        strategy_name: Strategy name (supertrend_ai, sma_crossover, buy_and_hold)
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        timeframe: Timeframe (d1, h1, etc.)
        initial_capital: Starting capital
        strategy_params: Strategy-specific parameters
        
    Returns:
        Dictionary with backtest results
    """
    try:
        # Initialize database
        db = SupabaseDatabase()
        
        # Fetch OHLC bars
        df = db.fetch_ohlc_bars(symbol=symbol, timeframe=timeframe, limit=1000)
        
        if df.empty:
            return {
                "error": f"No OHLC data found for {symbol} ({timeframe})",
                "symbol": symbol,
                "strategy": strategy_name
            }
        
        # Filter by date range
        df['ts'] = pd.to_datetime(df['ts'])
        start = pd.Timestamp(start_date)
        end = pd.Timestamp(end_date)
        df = df[(df['ts'] >= start) & (df['ts'] <= end)].copy()
        
        if df.empty:
            return {
                "error": f"No data in date range {start_date} to {end_date}",
                "symbol": symbol,
                "strategy": strategy_name
            }
        
        # Rename columns for backtest engine (expects 'date' not 'ts')
        df = df.rename(columns={'ts': 'date'})
        df = df.sort_values('date').reset_index(drop=True)
        
        # Create strategy function
        strategy_params = strategy_params or {}
        if strategy_name == "supertrend_ai":
            strategy_func = create_supertrend_ai_strategy(df, strategy_params)
        elif strategy_name == "sma_crossover":
            strategy_func = create_sma_crossover_strategy(df, strategy_params)
        elif strategy_name == "buy_and_hold":
            strategy_func = create_buy_and_hold_strategy()
        else:
            return {
                "error": f"Unknown strategy: {strategy_name}",
                "symbol": symbol,
                "strategy": strategy_name
            }
        
        # Initialize backtest engine
        engine = BacktestEngine(initial_capital=initial_capital)
        engine.load_historical_data(df)
        
        # Run backtest
        results = engine.run(
            strategy=strategy_func,
            start_date=start,
            end_date=end
        )
        
        # Convert results to JSON-serializable format
        equity_curve = []
        for date, value in zip(results['dates'], results['equity_curve']):
            equity_curve.append({
                "date": date.isoformat() if hasattr(date, 'isoformat') else str(date),
                "value": float(value)
            })
        
        trades = []
        if not results['trade_history'].empty:
            for _, trade in results['trade_history'].iterrows():
                trades.append({
                    "date": trade.get('date', '').isoformat() if hasattr(trade.get('date', ''), 'isoformat') else str(trade.get('date', '')),
                    "symbol": str(trade.get('symbol', '')),
                    "action": str(trade.get('action', '')),
                    "quantity": int(trade.get('quantity', 0)),
                    "price": float(trade.get('price', 0)),
                    "pnl": float(trade.get('pnl', 0)) if 'pnl' in trade else None
                })
        
        return {
            "symbol": symbol.upper(),
            "strategy": strategy_name,
            "period": {
                "start": start_date,
                "end": end_date
            },
            "initialCapital": float(initial_capital),
            "finalValue": float(results['final_value']),
            "totalReturn": float(results['total_return']),
            "metrics": {
                "sharpeRatio": float(results.get('sharpe_ratio', 0)) if 'sharpe_ratio' in results else None,
                "maxDrawdown": float(results.get('max_drawdown', 0)) if 'max_drawdown' in results else None,
                "winRate": float(results.get('win_rate', 0)) if 'win_rate' in results else None,
                "totalTrades": int(results['pnl'].get('num_trades', 0)) if 'pnl' in results else 0
            },
            "equityCurve": equity_curve,
            "trades": trades,
            "barsUsed": len(df)
        }
        
    except Exception as e:
        logger.error(f"Error running backtest for {symbol}: {e}", exc_info=True)
        return {
            "error": str(e),
            "symbol": symbol,
            "strategy": strategy_name
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Run backtest for a trading strategy")
    parser.add_argument("--symbol", required=True, help="Stock ticker symbol")
    parser.add_argument("--strategy", required=True, help="Strategy name (supertrend_ai, sma_crossover, buy_and_hold)")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--timeframe", default="d1", help="Timeframe (d1, h1, etc.)")
    parser.add_argument("--capital", type=float, default=10000, help="Initial capital")
    parser.add_argument("--params", help="Strategy parameters as JSON string")
    
    args = parser.parse_args()
    
    # Parse strategy parameters if provided
    strategy_params = {}
    if args.params:
        try:
            strategy_params = json.loads(args.params)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in --params: {args.params}")
    
    result = run_backtest(
        symbol=args.symbol,
        strategy_name=args.strategy,
        start_date=args.start,
        end_date=args.end,
        timeframe=args.timeframe,
        initial_capital=args.capital,
        strategy_params=strategy_params
    )
    
    # Output JSON
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
