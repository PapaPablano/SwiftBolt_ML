#!/usr/bin/env python3
"""
Run Market Regime-Aware Testing for SwiftBolt ML

Tests stocks across different market regimes with regime-specific requirements.
Optimized for Docker/production use with structured output.

Usage:
    # Run all regimes and stocks
    python ml/scripts/run_regime_testing.py
    
    # Run specific regime
    python ml/scripts/run_regime_testing.py --regime crash_2022
    
    # Quick test on single stock
    python ml/scripts/run_regime_testing.py --quick-test AAPL --regime crash_2022
    
    # Output to custom CSV
    python ml/scripts/run_regime_testing.py --output results/regime_tests.csv
"""

import sys
import argparse
import json
import logging
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# Ensure src resolves correctly
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.supabase_db import SupabaseDatabase
from src.data.data_cleaner import DataCleaner
from src.models.xgboost_forecaster import XGBoostForecaster

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# MARKET REGIME DEFINITIONS
# ============================================================================

REGIMES = {
    'crash_2022': {
        'start': '2022-03-01',
        'end': '2022-10-31',
        'type': 'Bear Market Crash',
        'spx_return': -18.1,
        'description': 'High volatility, panic selling, rate hikes',
    },
    'recovery_2023': {
        'start': '2022-11-01',
        'end': '2023-12-31',
        'type': 'Post-Crash Recovery',
        'spx_return': +26.3,
        'description': 'V-shaped recovery, mean reversion',
    },
    'bull_2024': {
        'start': '2024-01-01',
        'end': '2024-12-31',
        'type': 'Mega-Cap Bull',
        'spx_return': +25.0,
        'description': 'AI euphoria, low volatility',
    },
    'rotation_2022': {
        'start': '2021-09-01',
        'end': '2022-06-30',
        'type': 'Growth Rotation',
        'spx_return': -15.5,
        'description': 'First signs of weakness, rate shock',
    },
}

# Stock categories for testing
STOCKS = {
    'defensive': {
        'symbols': ['PG', 'KO', 'JNJ', 'MRK'],
        'horizon': 5,
        'threshold': 0.015,
        'description': 'Low-volatility defensive stocks'
    },
    'quality': {
        'symbols': ['AAPL', 'MSFT', 'AMGN', 'BRK.B'],
        'horizon': 5,
        'threshold': 0.015,
        'description': 'Mid-range quality growth'
    },
    'semis': {
        'symbols': ['NVDA', 'MU', 'ALB'],
        'horizon': 10,
        'threshold': 0.020,
        'description': 'High-volatility semiconductors'
    },
}


def get_regime_requirements(regime_name: str) -> dict:
    """Get minimum requirements per regime.
    
    Growth Rotation: limited data (15/5/1/21)
    Others: full data (55/7/4/75)
    """
    if regime_name == 'rotation_2022':
        return {
            'min_train_size': 15,
            'test_window': 5,
            'min_bars': 21,
            'min_windows': 1,  # ⚠️ Below research-backed 25-75d range - max coverage mode
        }
    return {
        'min_train_size': 55,
        'test_window': 7,
        'min_bars': 75,
        'min_windows': 4,
    }


def fetch_regime_data(db: SupabaseDatabase, symbol: str, regime_config: dict) -> pd.DataFrame:
    """Fetch OHLC data for a specific regime period."""
    try:
        df = db.fetch_ohlc_bars(
            symbol=symbol,
            timeframe='d1',
            start_date=regime_config['start'],
            end_date=regime_config['end'],
            provider='alpaca',
            limit=2000
        )
        
        if df.empty:
            logger.warning(f"No data for {symbol} in regime period")
            return pd.DataFrame()
        
        # Apply data cleaning
        cleaner = DataCleaner()
        df = cleaner.clean_ohlc_data(df)
        
        # Filter to regime period
        df_regime = df[
            (df['ts'] >= pd.to_datetime(regime_config['start'])) &
            (df['ts'] <= pd.to_datetime(regime_config['end']))
        ].copy()
        
        logger.info(f"Fetched {len(df_regime)} bars for {symbol}")
        return df_regime
        
    except Exception as e:
        logger.error(f"Error fetching data for {symbol}: {e}")
        return pd.DataFrame()


def run_regime_test(
    symbol: str,
    regime_name: str,
    regime_config: dict,
    category_config: dict
) -> dict:
    """Run regime test for a single stock."""
    
    result = {
        'symbol': symbol,
        'regime': regime_name,
        'regime_type': regime_config['type'],
        'category': None,
        'horizon': category_config['horizon'],
        'threshold': category_config['threshold'],
        'status': 'PENDING',
        'accuracy': None,
        'accuracy_std': None,
        'test_bars': None,
        'windows': None,
        'training_samples': None,
        'error': None,
        'timestamp': datetime.now().isoformat()
    }
    
    # Determine category
    for cat, config in STOCKS.items():
        if symbol in config['symbols']:
            result['category'] = cat
            break
    
    try:
        # Get regime requirements
        req = get_regime_requirements(regime_name)
        
        # Fetch data
        db = SupabaseDatabase()
        df = fetch_regime_data(db, symbol, regime_config)
        
        if df.empty:
            result['status'] = 'FAILED'
            result['error'] = 'No data available'
            return result
        
        # Check minimum bars
        if len(df) < req['min_bars']:
            result['status'] = 'FAILED'
            result['error'] = f"Insufficient bars: {len(df)} < {req['min_bars']}"
            return result
        
        # Initialize forecaster
        forecaster = XGBoostForecaster(
            horizon_days=category_config['horizon'],
            threshold_pct=category_config['threshold']
        )
        
        # Prepare data
        X, y = forecaster.prepare_data(df)
        
        if X is None or y is None or len(X) < req['min_bars']:
            result['status'] = 'FAILED'
            result['error'] = f"Insufficient training samples after cleaning"
            return result
        
        result['training_samples'] = len(X)
        
        # Run walk-forward validation
        accuracies = []
        total_test_bars = 0
        num_windows = 0
        
        train_size = req['min_train_size']
        test_size = req['test_window']
        embargo = 1
        
        for start_idx in range(0, len(X) - train_size - test_size - embargo + 1, test_size):
            train_end = start_idx + train_size
            test_start = train_end + embargo
            test_end = test_start + test_size
            
            if test_end > len(X):
                break
            
            # Split data
            X_train = X.iloc[start_idx:train_end]
            y_train = y.iloc[start_idx:train_end]
            X_test = X.iloc[test_start:test_end]
            y_test = y.iloc[test_start:test_end]
            
            # Train and predict
            forecaster.fit(X_train, y_train)
            predictions = forecaster.predict(X_test)
            
            # Calculate accuracy
            accuracy = np.mean(predictions == y_test)
            accuracies.append(accuracy)
            total_test_bars += len(y_test)
            num_windows += 1
        
        # Check minimum windows
        if num_windows < req['min_windows']:
            result['status'] = 'FAILED'
            result['error'] = f"Insufficient windows: {num_windows} < {req['min_windows']}"
            return result
        
        # Calculate metrics
        result['accuracy'] = float(np.mean(accuracies))
        result['accuracy_std'] = float(np.std(accuracies))
        result['test_bars'] = total_test_bars
        result['windows'] = num_windows
        result['status'] = 'PASSED'
        
        logger.info(
            f"✅ {symbol}: {result['accuracy']:.1%} ± {result['accuracy_std']:.1%} "
            f"| {total_test_bars} bars | {num_windows} windows"
        )
        
    except Exception as e:
        result['status'] = 'FAILED'
        result['error'] = str(e)
        logger.error(f"❌ {symbol}: {e}")
    
    return result


def run_all_regime_tests(
    regimes_to_test: list = None,
    symbols_to_test: list = None,
    output_path: str = None
) -> pd.DataFrame:
    """Run regime tests across all configurations."""
    
    if regimes_to_test is None:
        regimes_to_test = list(REGIMES.keys())
    
    all_results = []
    
    for regime_name in regimes_to_test:
        regime_config = REGIMES[regime_name]
        
        logger.info("="*100)
        logger.info(f"REGIME: {regime_config['type']}")
        logger.info(f"Period: {regime_config['start']} to {regime_config['end']} | "
                   f"S&P 500: {regime_config['spx_return']:+.1f}%")
        logger.info(f"Description: {regime_config['description']}")
        logger.info("="*100)
        
        for category, config in STOCKS.items():
            logger.info(f"\n{config['description'].upper()} "
                       f"(horizon={config['horizon']}d, threshold={config['threshold']:.1%}):")
            
            for symbol in config['symbols']:
                # Skip if specific symbols requested
                if symbols_to_test and symbol not in symbols_to_test:
                    continue
                
                result = run_regime_test(symbol, regime_name, regime_config, config)
                all_results.append(result)
    
    # Convert to DataFrame
    df_results = pd.DataFrame(all_results)
    
    # Save to CSV if path provided
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        df_results.to_csv(output_file, index=False)
        logger.info(f"\n✅ Results saved to: {output_file}")
    
    # Print summary
    logger.info("\n" + "="*100)
    logger.info("SUMMARY")
    logger.info("="*100)
    
    summary = df_results.groupby(['regime', 'status']).size().unstack(fill_value=0)
    logger.info(f"\n{summary}")
    
    passed = df_results[df_results['status'] == 'PASSED']
    if len(passed) > 0:
        logger.info(f"\nAverage Accuracy: {passed['accuracy'].mean():.1%} ± {passed['accuracy_std'].mean():.1%}")
        logger.info(f"Best: {passed.loc[passed['accuracy'].idxmax(), 'symbol']} "
                   f"({passed['accuracy'].max():.1%})")
        logger.info(f"Worst: {passed.loc[passed['accuracy'].idxmin(), 'symbol']} "
                   f"({passed['accuracy'].min():.1%})")
    
    return df_results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Run market regime-aware testing')
    parser.add_argument('--regime', type=str, help='Specific regime to test')
    parser.add_argument('--symbol', type=str, help='Specific symbol to test')
    parser.add_argument('--quick-test', type=str, help='Quick test on single symbol')
    parser.add_argument('--output', type=str, default='regime_test_results.csv',
                       help='Output CSV path (default: regime_test_results.csv)')
    
    args = parser.parse_args()
    
    # Determine what to test
    regimes_to_test = [args.regime] if args.regime else None
    symbols_to_test = [args.symbol] if args.symbol else None
    symbols_to_test = [args.quick_test] if args.quick_test else symbols_to_test
    
    # Run tests
    logger.info("Starting Market Regime-Aware Testing...")
    df_results = run_all_regime_tests(
        regimes_to_test=regimes_to_test,
        symbols_to_test=symbols_to_test,
        output_path=args.output
    )
    
    return df_results


if __name__ == '__main__':
    main()
