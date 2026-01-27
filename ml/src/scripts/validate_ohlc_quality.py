#!/usr/bin/env python3
"""
OHLC Data Quality Validation Script

Validates OHLC data quality for ML training, checking for critical issues
that could affect model reliability. Non-critical issues (outliers, gaps)
are treated as warnings.

Usage:
    python validate_ohlc_quality.py [--symbols AAPL,NVDA,MSFT] [--limit 10]
"""

import argparse
import sys
from typing import List, Tuple

# Add src to path for imports
sys.path.insert(0, 'src')

from src.data.data_validator import OHLCValidator
from src.data.supabase_db import db
from src.scripts.universe_utils import get_symbol_universe


def get_symbols(symbols_arg: str = None, limit: int = 10) -> List[str]:
    """Get symbols to validate, with fallbacks."""
    if symbols_arg:
        return [s.strip() for s in symbols_arg.split(',') if s.strip()]
    
    try:
        universe = get_symbol_universe()
        symbols = universe.get('symbols', []) or ['SPY', 'AAPL', 'NVDA', 'MSFT']
    except Exception as e:
        print(f'⚠️ Unable to fetch watchlist symbols: {e}')
        print('   Using default symbols: SPY, AAPL, NVDA, MSFT')
        symbols = ['SPY', 'AAPL', 'NVDA', 'MSFT']
    
    return symbols[:limit]


def validate_symbol(symbol: str, validator: OHLCValidator) -> Tuple[List[str], List[str]]:
    """Validate a single symbol and return (critical_errors, warnings)."""
    critical_errors = []
    warnings = []
    
    try:
        # Check daily timeframe (used for training)
        df = db.fetch_ohlc_bars(symbol, timeframe='d1', limit=252)
        if df.empty:
            error_msg = f'{symbol}: No data found'
            critical_errors.append(error_msg)
            print(f'⚠️ {error_msg}')
            return critical_errors, warnings
        
        df, result = validator.validate(df, fix_issues=False)
        
        if result.issues:
            # Separate critical issues from warnings
            critical_keywords = [
                'High < max(Open,Close)',
                'Low > min(Open,Close)',
                'Negative volume',
                'Non-positive'
            ]
            
            symbol_critical = []
            symbol_warnings = []
            
            for issue in result.issues:
                is_critical = any(keyword in issue for keyword in critical_keywords)
                if is_critical:
                    symbol_critical.append(issue)
                else:
                    # Outliers and gaps are warnings, not critical
                    symbol_warnings.append(issue)
            
            if symbol_critical:
                error_msg = f'{symbol}: {symbol_critical}'
                critical_errors.append(error_msg)
                print(f'❌ {error_msg}')
            else:
                # Only warnings (outliers/gaps) - acceptable
                print(f'⚠️ {symbol}: {symbol_warnings} (non-critical)')
                warnings.extend([f'{symbol}: {w}' for w in symbol_warnings])
        else:
            print(f'✅ {symbol}: OHLC validation passed ({len(df)} bars)')
            
    except Exception as e:
        error_msg = f'{symbol}: {str(e)}'
        critical_errors.append(error_msg)
        print(f'❌ {error_msg}')
    
    return critical_errors, warnings


def main():
    parser = argparse.ArgumentParser(description='Validate OHLC data quality')
    parser.add_argument('--symbols', help='Comma-separated list of symbols')
    parser.add_argument('--limit', type=int, default=10, help='Limit number of symbols')
    args = parser.parse_args()
    
    validator = OHLCValidator()
    symbols = get_symbols(args.symbols, args.limit)
    
    print(f'📊 Validating OHLC data quality for {len(symbols)} symbols...')
    print('')
    
    all_critical = []
    all_warnings = []
    
    for symbol in symbols:
        critical, warnings = validate_symbol(symbol, validator)
        all_critical.extend(critical)
        all_warnings.extend(warnings)
    
    print('')
    print('=' * 60)
    
    if all_critical:
        print('❌ OHLC validation failed for some symbols (critical issues):')
        for error in all_critical:
            print(f'  - {error}')
        print('')
        print('::error::Critical OHLC data quality issues detected. ML training may produce unreliable results.')
        return 1
    
    if all_warnings:
        print('⚠️ OHLC validation warnings (non-critical):')
        for warning in all_warnings:
            print(f'  - {warning}')
        print('')
        print('::warning::Some OHLC data quality warnings detected (outliers/gaps). These are common in real market data.')
    
    print('')
    print('✅ OHLC validation passed for all checked symbols (critical checks only)')
    print('=' * 60)
    
    # Export metrics
    print(f"::notice::Validated {len(symbols)} symbols with {len(all_warnings)} warnings")
    print(f"symbols_validated={len(symbols)}")
    print(f"warnings_count={len(all_warnings)}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
