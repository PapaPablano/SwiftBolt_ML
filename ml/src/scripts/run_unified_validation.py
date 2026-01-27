#!/usr/bin/env python3
"""
Unified Validation Script

Runs comprehensive validation including drift detection, confidence reconciliation,
and model health checks using real database scores.

Usage:
    python run_unified_validation.py [--symbols AAPL,NVDA,MSFT]
"""

import argparse
import asyncio
import sys
from typing import List, Dict, Any

# Add src to path for imports
sys.path.insert(0, 'src')

from src.services.validation_service import ValidationService


def get_default_symbols() -> List[str]:
    """Get default symbols for validation."""
    return ['AAPL', 'NVDA', 'MSFT', 'TSLA', 'META', 'AMD', 'CRWD', 'GOOGL', 'AMZN']


async def validate_symbol(symbol: str, service: ValidationService) -> Dict[str, Any]:
    """Validate a single symbol and return results."""
    try:
        # Fetch actual validation from database
        # Use BULLISH as default direction (can be enhanced to fetch actual direction)
        result = await service.get_live_validation(symbol, 'BULLISH')
        
        # Check if using default scores (indicates missing data)
        using_defaults = (
            result.live_score == 0.50 and
            result.backtesting_score == 0.55 and
            result.walkforward_score == 0.60
        )
        
        status = result.get_status_emoji()
        print(f'{status} {symbol}: {result.unified_confidence:.1%} confidence')
        print(f'   Drift: {result.drift_severity} ({result.drift_magnitude:.0%})')
        print(f'   Consensus: {result.consensus_direction}')
        
        if using_defaults:
            print(f'   ℹ️  Using default scores (live_predictions table empty)')
        
        if result.drift_detected:
            print(f'   ⚠️ RETRAINING TRIGGERED: {result.retraining_reason}')
        
        return {
            'symbol': symbol,
            'status': 'success',
            'confidence': result.unified_confidence,
            'drift_detected': result.drift_detected,
            'drift_severity': result.drift_severity,
            'drift_magnitude': result.drift_magnitude,
            'using_defaults': using_defaults,
            'retraining_trigger': result.retraining_trigger,
            'retraining_reason': result.retraining_reason
        }
        
    except Exception as e:
        error_msg = f'{symbol}: {str(e)}'
        print(f'⚠️ {error_msg}')
        return {
            'symbol': symbol,
            'status': 'error',
            'error': str(e)
        }


async def run_all_validations(symbols: List[str]) -> Dict[str, Any]:
    """Run validations for all symbols."""
    service = ValidationService()
    
    print('=' * 60)
    print('UNIFIED VALIDATION REPORT (Real Database Scores)')
    print('=' * 60)
    print('')
    print('Note: If live_predictions table is empty, scores will use conservative defaults.')
    print('      This is expected until predictions are written to the database.')
    print('')
    
    tasks = [validate_symbol(symbol, service) for symbol in symbols]
    results = await asyncio.gather(*tasks)
    
    print('')
    print('=' * 60)
    
    # Analyze results
    validation_errors = []
    missing_live_data = []
    drift_alerts = []
    
    for result in results:
        if result['status'] == 'error':
            validation_errors.append(result['error'])
        elif result.get('using_defaults'):
            missing_live_data.append(result['symbol'])
        elif result.get('drift_detected'):
            drift_alerts.append({
                'symbol': result['symbol'],
                'severity': result['drift_severity'],
                'magnitude': result['drift_magnitude'],
                'reason': result.get('retraining_reason', 'Unknown')
            })
    
    # Print summary
    if validation_errors:
        print(f'⚠️ VALIDATION ERRORS: {len(validation_errors)} symbols')
        for error in validation_errors:
            print(f'   - {error}')
        print('')
    
    if missing_live_data:
        print(f'ℹ️  MISSING LIVE DATA: {len(missing_live_data)} symbols using default scores')
        print(f'   Symbols: {", ".join(missing_live_data)}')
        print('   This is expected until predictions are written to live_predictions table.')
        print('')
    
    if drift_alerts:
        print(f'⚠️ DRIFT ALERTS: {len(drift_alerts)} symbols')
        for alert in drift_alerts:
            print(f'   - {alert["symbol"]}: {alert["severity"]} drift ({alert["magnitude"]:.0%})')
    else:
        print('✅ No drift alerts')
    
    print('=' * 60)
    print('✅ Unified validation complete')
    
    # Return summary for GitHub Actions
    return {
        'total_symbols': len(symbols),
        'validation_errors': len(validation_errors),
        'missing_live_data': len(missing_live_data),
        'drift_alerts': len(drift_alerts),
        'results': results
    }


def main():
    parser = argparse.ArgumentParser(description='Run unified validation')
    parser.add_argument('--symbols', help='Comma-separated list of symbols')
    args = parser.parse_args()
    
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(',') if s.strip()]
    else:
        symbols = get_default_symbols()
    
    print(f'📊 Running unified validation for {len(symbols)} symbols...')
    
    # Run async validation
    summary = asyncio.run(run_all_validations(symbols))
    
    # Export metrics for GitHub Actions
    print(f"::notice::Validated {summary['total_symbols']} symbols")
    print(f"::notice::Validation errors: {summary['validation_errors']}")
    print(f"::notice::Missing live data: {summary['missing_live_data']}")
    print(f"::notice::Drift alerts: {summary['drift_alerts']}")
    
    # Set GitHub Actions outputs
    print(f"total_symbols={summary['total_symbols']}")
    print(f"validation_errors={summary['validation_errors']}")
    print(f"missing_live_data={summary['missing_live_data']}")
    print(f"drift_alerts={summary['drift_alerts']}")
    
    # Exit with error code if there are validation errors
    if summary['validation_errors'] > 0:
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
