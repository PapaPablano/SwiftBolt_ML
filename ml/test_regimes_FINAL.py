#!/usr/bin/env python3
"""
Market Regime-Aware Testing for SwiftBolt ML - FINAL VERSION
Tests stocks across different market regimes with regime-specific requirements

Growth Rotation (Limited Data):
  train_size: 15 bars, test_window: 5, min_windows: 1, min_bars: 21
  Minimum needed: 15 + 5 + 1 = 21 samples (⚠️ Below research sweet spot, for max coverage only)

Other Regimes (Full Data):
  train_size: 55 bars, test_window: 7, min_windows: 4, min_bars: 75
  Minimum needed: 55 + 7 + 1 = 63 samples

Usage (from ml/):
    cd /Users/ericpeterson/SwiftBolt_ML/ml
    python test_regimes_FINAL.py
    python test_regimes_FINAL.py --test-data
    python test_regimes_FINAL.py --quick-test AAPL --regime crash_2022
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime
import logging
import warnings
warnings.filterwarnings('ignore')

# Run from ml/: ensure src resolves to ml/src
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.data.supabase_db import SupabaseDatabase
from src.data.data_cleaner import DataCleaner
from src.models.xgboost_forecaster import XGBoostForecaster

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# MARKET REGIME DEFINITIONS - IMPROVED
# ============================================================================

# No threshold_override: each stock category uses its own threshold (defensive 1.5%,
# quality 1.5%, growth 2.0%). Regime volatility != stock volatility.
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

# Walk-forward validation settings - IMPROVED (BALANCED)
WF_MIN_TRAIN_SIZE = 55   # CHANGED: Was 50, moderate increase for stability
WF_TEST_WINDOW = 7       # CHANGED: Was 5, balanced increase for reliability
WF_EMBARGO_BARS = 1      # Kept at 1 (sufficient for daily data)

# Stock categories for testing (AAPL included for --quick-test AAPL)
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
    'growth': {
        'symbols': ['NVDA', 'MU', 'ALB'],
        'horizon': 10,
        'threshold': 0.02,
        'description': 'High-volatility semiconductors'
    },
}


# ============================================================================
# DATA LOADING WITH PROPER CLEANING
# ============================================================================

def load_stock_data(symbol: str, limit: int = 2000) -> pd.DataFrame:
    """
    Load and clean stock data with proper error handling

    Args:
        symbol: Stock symbol
        limit: Number of bars to fetch

    Returns:
        Cleaned DataFrame with OHLCV data
    """
    try:
        db = SupabaseDatabase()
        df = db.fetch_ohlc_bars(symbol, timeframe='d1', limit=limit)

        if df is None or len(df) == 0:
            logger.error(f"  ❌ {symbol}: No data returned from Supabase")
            return None

        # Clean data
        df = DataCleaner.clean_all(df, verbose=False)

        # Ensure timestamp is datetime
        if 'ts' in df.columns:
            df['ts'] = pd.to_datetime(df['ts'])
        elif 'timestamp' in df.columns:
            df['ts'] = pd.to_datetime(df['timestamp'])
        else:
            logger.error(f"  ❌ {symbol}: No timestamp column found")
            return None

        # Sort by date
        df = df.sort_values('ts').reset_index(drop=True)

        # Validate critical columns
        required_cols = ['ts', 'open', 'high', 'low', 'close', 'volume']
        missing_cols = [col for col in required_cols if col not in df.columns]

        if missing_cols:
            logger.error(f"  ❌ {symbol}: Missing columns: {missing_cols}")
            return None

        # Remove rows with NaN in critical columns
        df = df.dropna(subset=['close', 'open', 'high', 'low'])

        return df

    except Exception as e:
        logger.error(f"  ❌ {symbol}: Data loading failed - {str(e)[:100]}")
        return None


def filter_by_regime(df: pd.DataFrame, regime: dict) -> pd.DataFrame:
    """
    Filter dataframe to specific regime period

    Args:
        df: Full dataframe
        regime: Regime dictionary with start/end dates

    Returns:
        Filtered dataframe for regime period
    """
    start = pd.to_datetime(regime['start'])
    end = pd.to_datetime(regime['end'])

    df_regime = df[(df['ts'] >= start) & (df['ts'] <= end)].copy()

    return df_regime


def get_regime_requirements(regime_name: str) -> dict:
    """Get minimum requirements per regime. Growth Rotation: limited data (15/5/1/21); others: full (55/7/4/75)."""
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


# ============================================================================
# MODEL EVALUATION
# ============================================================================

def evaluate_stock_in_regime(
    symbol: str,
    regime_name: str,
    regime: dict,
    category_config: dict,
    df_full: pd.DataFrame = None
) -> dict:
    """
    Evaluate a single stock in a single regime

    Args:
        symbol: Stock symbol
        regime_name: Name of regime
        regime: Regime configuration
        category_config: Stock category configuration (horizon, threshold)
        df_full: Pre-loaded full dataframe (optional)

    Returns:
        Dictionary with results or None if failed
    """

    horizon = category_config['horizon']
    # Regime-specific threshold overrides (e.g. wider in crash, tighter in bull)
    threshold = regime.get('threshold_override', category_config['threshold'])

    # Load data if not provided
    if df_full is None:
        df_full = load_stock_data(symbol, limit=2000)

    if df_full is None:
        return None

    # Filter to regime period
    df = filter_by_regime(df_full, regime)

    req = get_regime_requirements(regime_name)
    min_bars = req['min_bars']
    if len(df) < min_bars:
        logger.warning(f"    ⚠️  Insufficient data: {len(df)} bars (need {min_bars}+)")
        return None

    try:
        # Prepare features
        forecaster = XGBoostForecaster()

        X, y = forecaster.prepare_training_data_binary(
            df,
            horizon_days=horizon,
            threshold_pct=threshold,
        )

        min_samples = 25 if regime_name == 'rotation_2022' else 30
        if X is None or y is None or len(X) < min_samples:
            logger.warning(f"    ⚠️  Insufficient features: {len(X) if X is not None else 0} samples (need {min_samples}+)")
            return None

        # Replace Inf first (do not fill NaNs globally to avoid leakage)
        X_raw = X.replace([np.inf, -np.inf], np.nan)

        # Walk-forward: regime-specific min_train_size, test_window, min_windows; embargo from global
        min_train_size = req['min_train_size']
        test_window = req['test_window']
        min_windows = req['min_windows']
        embargo = WF_EMBARGO_BARS
        step = embargo + test_window
        n_windows = (len(X_raw) - min_train_size - embargo - test_window) // step + 1
        n_windows = max(0, n_windows)

        if n_windows < min_windows:
            logger.warning(f"    ⚠️  Insufficient windows: {n_windows} (need {min_windows}+)")
            return None

        all_predictions = []
        all_actuals = []
        window_accuracies = []
        nan_threshold = 0.5

        for i in range(n_windows):
            train_end = min_train_size + i * step
            test_start = train_end + embargo
            test_end = min(test_start + test_window, len(X_raw))

            X_train_raw = X_raw.iloc[:train_end]
            y_train = y.iloc[:train_end]
            X_test_raw = X_raw.iloc[test_start:test_end]
            y_test = y.iloc[test_start:test_end]

            # NaN handling order (per window, train-only derived): drop bad cols, fill with train median
            train_clean = X_train_raw.replace([np.inf, -np.inf], np.nan)
            nan_pct = train_clean.isna().mean()
            valid_cols = nan_pct[nan_pct < nan_threshold].index.tolist()
            if len(valid_cols) == 0:
                continue
            train_medians = train_clean[valid_cols].median()
            X_train = train_clean[valid_cols].fillna(train_medians).fillna(0)
            X_test = X_test_raw[valid_cols].replace([np.inf, -np.inf], np.nan)
            X_test = X_test.fillna(train_medians).fillna(0)

            if len(X_test) == 0:
                continue

            model = XGBoostForecaster()
            model.train(X_train, y_train)

            y_pred_proba = model.predict_proba(X_test)
            if y_pred_proba is None or len(y_pred_proba) == 0:
                continue
            p_bull = y_pred_proba[:, 1] if getattr(y_pred_proba, 'ndim', 0) == 2 else np.asarray(y_pred_proba)
            y_pred = (p_bull > 0.5).astype(int)
            y_test_bin = np.where(np.asarray([str(v).lower() for v in y_test.values]) == "bullish", 1, 0)

            all_predictions.extend(y_pred)
            all_actuals.extend(y_test_bin)
            window_acc = (y_pred == y_test_bin).mean()
            window_accuracies.append(window_acc)

        if len(all_predictions) == 0:
            logger.warning(f"    ⚠️  No predictions from walk-forward")
            return None

        accuracy = (np.array(all_predictions) == np.array(all_actuals)).mean()
        accuracy_std = float(np.std(window_accuracies)) if len(window_accuracies) > 1 else 0.0
        positive_rate = (y == "bullish").mean()
        feature_count = X_raw.shape[1]

        return {
            'accuracy': accuracy,
            'accuracy_std': accuracy_std,
            'samples': len(X_raw),
            'features': feature_count,
            'test_samples': len(all_predictions),
            'n_windows': n_windows,
            'positive_rate': positive_rate,
            'bars': len(df)
        }

    except Exception as e:
        logger.error(f"    ❌ Evaluation failed: {str(e)[:100]}")
        import traceback
        logger.debug(traceback.format_exc())
        return None


# ============================================================================
# MAIN TESTING LOOP
# ============================================================================

def run_regime_tests():
    """Run complete regime testing across all stocks and periods"""

    print("="*100)
    print("MARKET REGIME-AWARE BACKTESTING - FINAL VERSION")
    print("Testing 10 stocks across 4 market regimes")
    print("Parameters: rotation_2022: train=15, test=5, min_bars=21, min_windows=1; others: 55/7/75/4")
    print("="*100)

    all_results = {}

    # Test each regime
    for regime_name, regime in REGIMES.items():
        print(f"\n{'─'*100}")
        print(f"REGIME: {regime['type']}")
        print(f"Period: {regime['start']} to {regime['end']} | S&P 500: {regime['spx_return']:+.1f}%")
        print(f"Description: {regime['description']}")
        if 'threshold_override' in regime:
            print(f"Threshold: {regime['threshold_override']:.1%} (regime-adjusted)")
        print(f"{'─'*100}")

        regime_results = {}

        # Test each category
        for category, config in STOCKS.items():
            print(f"\n{config['description'].upper()} (horizon={config['horizon']}d, threshold={config['threshold']:.1%}):")

            for symbol in config['symbols']:
                print(f"\n  {symbol:6s} | ", end='', flush=True)

                result = evaluate_stock_in_regime(
                    symbol=symbol,
                    regime_name=regime_name,
                    regime=regime,
                    category_config=config
                )

                if result:
                    print(f"✅ Accuracy: {result['accuracy']:.1%} ± {result['accuracy_std']:.1%} | "
                          f"Test: {result['test_samples']:2d} bars | "
                          f"Windows: {result['n_windows']}")

                    regime_results[symbol] = result
                else:
                    print(f"❌ Failed")

        all_results[regime_name] = regime_results

    # Generate summary
    generate_summary_report(all_results)

    return all_results


def generate_summary_report(results: dict):
    """Generate comprehensive summary report"""

    print("\n\n" + "="*100)
    print("SUMMARY REPORT")
    print("="*100)

    # Collect all accuracies by stock and regime
    summary_data = []

    for regime_name, regime_results in results.items():
        for symbol, result in regime_results.items():
            summary_data.append({
                'Stock': symbol,
                'Regime': REGIMES[regime_name]['type'],
                'Accuracy': result['accuracy'],
                'Accuracy_Std': result['accuracy_std'],
                'Samples': result['samples'],
                'Bars': result['bars'],
                'Windows': result['n_windows']
            })

    if not summary_data:
        print("\n❌ No results to summarize")
        return

    df_summary = pd.DataFrame(summary_data)

    # Pivot table: Stock x Regime
    print("\nAccuracy by Stock and Regime:")
    print("─"*100)

    pivot = df_summary.pivot_table(
        index='Stock',
        columns='Regime',
        values='Accuracy',
        aggfunc='mean'
    )

    # Add average column
    pivot['Average'] = pivot.mean(axis=1)

    # Format as percentages
    pivot_formatted = pivot.applymap(lambda x: f"{x:.1%}" if pd.notna(x) else "N/A")
    print(pivot_formatted.to_string())

    # Regime-level insights
    print("\n\nKey Insights by Regime:")
    print("─"*100)

    for regime_name, regime in REGIMES.items():
        regime_type = regime['type']
        regime_data = df_summary[df_summary['Regime'] == regime_type]

        if len(regime_data) > 0:
            avg_acc = regime_data['Accuracy'].mean()
            avg_std = regime_data['Accuracy_Std'].mean()
            best_stock = regime_data.loc[regime_data['Accuracy'].idxmax(), 'Stock']
            best_acc = regime_data['Accuracy'].max()

            print(f"\n{regime_type} ({regime['start']} to {regime['end']}):")
            print(f"  Average accuracy: {avg_acc:.1%} ± {avg_std:.1%}")
            print(f"  Best performer: {best_stock} at {best_acc:.1%}")
            print(f"  Stocks tested: {len(regime_data)}")
            print(f"  Average windows per test: {regime_data['Windows'].mean():.1f}")

    # Category insights
    print("\n\nInsights by Stock Category:")
    print("─"*100)

    for category, config in STOCKS.items():
        category_stocks = config['symbols']
        category_data = df_summary[df_summary['Stock'].isin(category_stocks)]

        if len(category_data) > 0:
            avg_acc = category_data['Accuracy'].mean()
            avg_std = category_data['Accuracy_Std'].mean()
            best_regime = category_data.loc[category_data['Accuracy'].idxmax(), 'Regime']
            best_acc = category_data['Accuracy'].max()

            print(f"\n{config['description']}:")
            print(f"  Average accuracy: {avg_acc:.1%} ± {avg_std:.1%}")
            print(f"  Best regime: {best_regime} ({best_acc:.1%})")

    # Overall statistics
    print("\n\nOverall Statistics:")
    print("─"*100)
    print(f"Total tests completed: {len(df_summary)}")
    print(f"Average accuracy: {df_summary['Accuracy'].mean():.1%} ± {df_summary['Accuracy'].std():.1%}")
    print(f"Best result: {df_summary['Accuracy'].max():.1%}")
    print(f"Worst result: {df_summary['Accuracy'].min():.1%}")
    print(f"Median accuracy: {df_summary['Accuracy'].median():.1%}")
    print(f"Accuracy range: {df_summary['Accuracy'].max() - df_summary['Accuracy'].min():.1%}")

    # Accuracy distribution
    print(f"\nAccuracy distribution:")
    print(f"  >60%: {(df_summary['Accuracy'] > 0.60).sum()} tests")
    print(f"  55-60%: {((df_summary['Accuracy'] >= 0.55) & (df_summary['Accuracy'] <= 0.60)).sum()} tests")
    print(f"  50-55%: {((df_summary['Accuracy'] >= 0.50) & (df_summary['Accuracy'] < 0.55)).sum()} tests")
    print(f"  45-50%: {((df_summary['Accuracy'] >= 0.45) & (df_summary['Accuracy'] < 0.50)).sum()} tests")
    print(f"  <45%: {(df_summary['Accuracy'] < 0.45).sum()} tests")

    # Save to CSV
    output_path = 'regime_test_results_final.csv'
    df_summary.to_csv(output_path, index=False)
    print(f"\n📊 Results saved to: {output_path}")


# ============================================================================
# QUICK TEST FUNCTIONS
# ============================================================================

def quick_test_single_stock(symbol: str, regime_name: str = 'crash_2022'):
    """Quick test of a single stock in one regime"""
    regime_name = (regime_name or "crash_2022").strip().rstrip(":")
    if regime_name not in REGIMES:
        logger.error(f"Unknown regime: {regime_name!r}. Valid: {list(REGIMES.keys())}")
        return
    print(f"\n{'='*80}")
    print(f"QUICK TEST: {symbol} in {REGIMES[regime_name]['type']}")
    print(f"{'='*80}\n")

    # Determine category (default quality for e.g. AAPL)
    category = None
    for cat, config in STOCKS.items():
        if symbol in config['symbols']:
            category = cat
            break

    if category is None:
        category = 'quality'

    result = evaluate_stock_in_regime(
        symbol=symbol,
        regime_name=regime_name,
        regime=REGIMES[regime_name],
        category_config=STOCKS[category]
    )

    if result:
        print(f"\n✅ Results:")
        print(f"   Accuracy: {result['accuracy']:.1%} ± {result['accuracy_std']:.1%}")
        print(f"   Samples: {result['samples']}")
        print(f"   Features: {result['features']}")
        print(f"   Test: {result['test_samples']} bars | Windows: {result['n_windows']}")
        print(f"   Positive rate: {result['positive_rate']:.1%}")
    else:
        print(f"\n❌ Test failed")


def test_data_availability():
    """Test data availability for all stocks and regimes"""

    print(f"\n{'='*80}")
    print(f"DATA AVAILABILITY TEST")
    print(f"{'='*80}\n")

    for category, config in STOCKS.items():
        print(f"\n{config['description']}:")

        for symbol in config['symbols']:
            print(f"\n  {symbol}:")

            df = load_stock_data(symbol, limit=2000)

            if df is None:
                print(f"    ❌ No data")
                continue

            print(f"    ✅ Total bars: {len(df)}")
            print(f"    Date range: {df['ts'].min().date()} to {df['ts'].max().date()}")

            for rname, regime in REGIMES.items():
                df_regime = filter_by_regime(df, regime)
                min_bars = get_regime_requirements(rname)['min_bars']
                meets_min = "✅" if len(df_regime) >= min_bars else "⚠️"
                print(f"    {regime['type']:25s}: {len(df_regime):3d} bars {meets_min}")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function"""

    import argparse

    parser = argparse.ArgumentParser(description='Market Regime-Aware Testing (Final)')
    parser.add_argument('--test-data', action='store_true',
                       help='Test data availability only')
    parser.add_argument('--quick-test', type=str,
                       help='Quick test single stock (e.g., AAPL)')
    parser.add_argument('--regime', type=str, default='crash_2022',
                       help='Regime for quick test (default: crash_2022)')

    args = parser.parse_args()

    if args.test_data:
        test_data_availability()
    elif args.quick_test:
        regime_key = (args.regime or "").strip().rstrip(":")
        quick_test_single_stock(args.quick_test, regime_key or "crash_2022")
    else:
        run_regime_tests()


if __name__ == '__main__':
    main()
