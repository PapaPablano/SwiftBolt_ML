#!/usr/bin/env python3
"""
CLI script to optimize portfolio allocation.
Returns JSON output for use by Edge Functions.

Usage:
    python optimize_portfolio.py --symbols AAPL,MSFT,GOOGL --method max_sharpe --risk-free-rate 0.02

Methods:
    - max_sharpe: Maximum Sharpe ratio portfolio
    - min_variance: Minimum variance portfolio
    - risk_parity: Risk parity portfolio
    - efficient: Efficient portfolio for target return
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.supabase_db import SupabaseDatabase
from src.optimization.portfolio_optimizer import PortfolioOptimizer

logging.basicConfig(level=logging.WARNING)  # Suppress verbose logs
logger = logging.getLogger(__name__)


def optimize_portfolio(
    symbols: List[str],
    method: str = "max_sharpe",
    timeframe: str = "d1",
    lookback_days: int = 252,
    risk_free_rate: float = 0.02,
    target_return: Optional[float] = None,
    min_weight: float = 0.0,
    max_weight: float = 1.0
) -> dict:
    """
    Optimize portfolio allocation.
    
    Args:
        symbols: List of stock ticker symbols
        method: Optimization method (max_sharpe, min_variance, risk_parity, efficient)
        timeframe: Timeframe (d1, h1, etc.)
        lookback_days: Number of days to look back for returns
        risk_free_rate: Annual risk-free rate
        target_return: Target return for efficient portfolio
        min_weight: Minimum weight per asset
        max_weight: Maximum weight per asset
        
    Returns:
        Dictionary with optimization results
    """
    try:
        # Initialize database
        db = SupabaseDatabase()
        
        # Fetch returns for all symbols
        returns_data = {}
        for symbol in symbols:
            df = db.fetch_ohlc_bars(symbol=symbol, timeframe=timeframe, limit=lookback_days + 50)
            
            if df.empty:
                logger.warning(f"No data for {symbol}")
                continue
            
            # Calculate daily returns
            df = df.sort_values('ts')
            df['return'] = df['close'].pct_change()
            returns_data[symbol] = df['return'].dropna()
        
        if not returns_data:
            return {
                "error": f"No data found for symbols: {', '.join(symbols)}",
                "symbols": symbols,
                "method": method
            }
        
        # Align returns by date
        returns_df = pd.DataFrame(returns_data)
        returns_df = returns_df.dropna()
        
        if len(returns_df) < 50:
            return {
                "error": f"Insufficient overlapping data: {len(returns_df)} days",
                "symbols": symbols,
                "method": method
            }
        
        # Initialize optimizer
        optimizer = PortfolioOptimizer(returns_df, risk_free_rate=risk_free_rate)
        
        # Build constraints
        constraints = {
            "min_weight": min_weight,
            "max_weight": max_weight
        }
        if target_return is not None:
            constraints["target_return"] = target_return
        
        # Run optimization
        if method == "max_sharpe":
            result = optimizer.max_sharpe_portfolio(constraints=constraints)
        elif method == "min_variance":
            result = optimizer.min_variance_portfolio(constraints=constraints)
        elif method == "risk_parity":
            result = optimizer.risk_parity_portfolio()
        elif method == "efficient":
            if target_return is None:
                return {
                    "error": "target_return required for efficient portfolio",
                    "symbols": symbols,
                    "method": method
                }
            result = optimizer.efficient_portfolio(target_return=target_return, constraints=constraints)
        else:
            return {
                "error": f"Unknown method: {method}",
                "symbols": symbols,
                "method": method
            }
        
        # Convert to JSON-serializable format
        weights_dict = {}
        for asset, weight in zip(result.assets, result.weights):
            weights_dict[asset] = float(weight)
        
        return {
            "symbols": [s.upper() for s in symbols],
            "method": method,
            "timeframe": timeframe,
            "lookbackDays": len(returns_df),
            "allocation": {
                "weights": weights_dict,
                "expectedReturn": float(result.expected_return),
                "volatility": float(result.volatility),
                "sharpeRatio": float(result.sharpe_ratio)
            },
            "parameters": {
                "riskFreeRate": float(risk_free_rate),
                "minWeight": float(min_weight),
                "maxWeight": float(max_weight),
                "targetReturn": float(target_return) if target_return else None
            }
        }
        
    except Exception as e:
        logger.error(f"Error optimizing portfolio: {e}", exc_info=True)
        return {
            "error": str(e),
            "symbols": symbols,
            "method": method
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Optimize portfolio allocation")
    parser.add_argument("--symbols", required=True, help="Comma-separated list of symbols")
    parser.add_argument("--method", default="max_sharpe", 
                       help="Optimization method (max_sharpe, min_variance, risk_parity, efficient)")
    parser.add_argument("--timeframe", default="d1", help="Timeframe (d1, h1, etc.)")
    parser.add_argument("--lookback-days", type=int, default=252, help="Lookback period in days")
    parser.add_argument("--risk-free-rate", type=float, default=0.02, help="Annual risk-free rate")
    parser.add_argument("--target-return", type=float, help="Target return for efficient portfolio")
    parser.add_argument("--min-weight", type=float, default=0.0, help="Minimum weight per asset")
    parser.add_argument("--max-weight", type=float, default=1.0, help="Maximum weight per asset")
    
    args = parser.parse_args()
    
    symbols = [s.strip().upper() for s in args.symbols.split(",")]
    
    result = optimize_portfolio(
        symbols=symbols,
        method=args.method,
        timeframe=args.timeframe,
        lookback_days=args.lookback_days,
        risk_free_rate=args.risk_free_rate,
        target_return=args.target_return,
        min_weight=args.min_weight,
        max_weight=args.max_weight
    )
    
    # Output JSON
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
