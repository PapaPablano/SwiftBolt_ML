"""
Direct comparison: TabPFN vs XGBoost on same symbols and horizons.

Usage:
    python experiments/tabpfn_vs_xgboost.py
    python experiments/tabpfn_vs_xgboost.py --symbols AAPL,MSFT,NVDA
    python experiments/tabpfn_vs_xgboost.py --live  # Pull from DB instead of generating
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "ml"))

from src.data.supabase_db import db
from src.models.baseline_forecaster import BaselineForecaster
from src.models.tabpfn_forecaster import TabPFNForecaster, is_tabpfn_available


# Test configuration
DEFAULT_SYMBOLS = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META']
HORIZONS = [1, 5, 10, 20]  # Days


def fetch_ohlc_data(symbol: str, limit: int = 500) -> pd.DataFrame:
    """Fetch OHLC data for a symbol."""
    try:
        symbol_id = db.get_symbol_id(symbol)
        if not symbol_id:
            print(f"  ❌ Symbol {symbol} not found in database")
            return pd.DataFrame()

        # Fetch OHLC data
        query = f"""
            SELECT ts, open, high, low, close, volume
            FROM ohlc_data
            WHERE symbol_id = '{symbol_id}' AND timeframe = 'd1'
            ORDER BY ts DESC
            LIMIT {limit}
        """
        result = db.execute_query(query)

        if not result:
            print(f"  ❌ No OHLC data found for {symbol}")
            return pd.DataFrame()

        df = pd.DataFrame(result)
        df = df.sort_values('ts').reset_index(drop=True)
        df['ts'] = pd.to_datetime(df['ts'])

        print(f"  ✓ Fetched {len(df)} bars for {symbol}")
        return df

    except Exception as e:
        print(f"  ❌ Error fetching data for {symbol}: {e}")
        return pd.DataFrame()


def compare_models_live(symbols: list, horizons: list) -> pd.DataFrame:
    """
    Compare models by pulling recent forecasts from database.

    Args:
        symbols: List of symbol tickers
        horizons: List of horizon days

    Returns:
        DataFrame with comparison results
    """
    print("\n" + "=" * 80)
    print("LIVE COMPARISON: Fetching forecasts from database")
    print("=" * 80)

    results = []

    for symbol in symbols:
        try:
            symbol_id = db.get_symbol_id(symbol)
            if not symbol_id:
                continue

            for horizon_days in horizons:
                horizon_str = f"{horizon_days}D"

                # Get latest forecasts for each model type
                query = f"""
                    SELECT
                        model_type,
                        overall_label as direction,
                        confidence,
                        forecast_return,
                        quality_score,
                        synthesis_data,
                        created_at
                    FROM ml_forecasts
                    WHERE symbol_id = '{symbol_id}'
                      AND horizon = '{horizon_str}'
                      AND created_at > NOW() - INTERVAL '24 hours'
                    ORDER BY model_type, created_at DESC
                """
                forecasts = db.execute_query(query)

                if not forecasts:
                    continue

                # Get latest for each model type
                model_forecasts = {}
                for fc in forecasts:
                    model_type = fc['model_type']
                    if model_type not in model_forecasts:
                        model_forecasts[model_type] = fc

                # Compare if we have both
                if 'xgboost' in model_forecasts and 'tabpfn' in model_forecasts:
                    xgb = model_forecasts['xgboost']
                    tabpfn = model_forecasts['tabpfn']

                    # Extract training time from synthesis_data if available
                    xgb_time = None
                    tabpfn_time = None
                    if xgb.get('synthesis_data'):
                        xgb_time = xgb['synthesis_data'].get('train_time_sec')
                    if tabpfn.get('synthesis_data'):
                        tabpfn_time = tabpfn['synthesis_data'].get('train_time_sec')

                    results.append({
                        'symbol': symbol,
                        'horizon': horizon_str,
                        'xgb_direction': xgb['direction'],
                        'xgb_confidence': float(xgb['confidence']),
                        'xgb_return': float(xgb.get('forecast_return') or 0),
                        'xgb_quality': float(xgb.get('quality_score') or 0),
                        'xgb_train_time': xgb_time,
                        'tabpfn_direction': tabpfn['direction'],
                        'tabpfn_confidence': float(tabpfn['confidence']),
                        'tabpfn_return': float(tabpfn.get('forecast_return') or 0),
                        'tabpfn_quality': float(tabpfn.get('quality_score') or 0),
                        'tabpfn_train_time': tabpfn_time,
                        'agreement': xgb['direction'] == tabpfn['direction'],
                        'xgb_created': xgb['created_at'],
                        'tabpfn_created': tabpfn['created_at'],
                    })

                    print(
                        f"{symbol:6} {horizon_str:4} | "
                        f"XGB: {xgb['direction']:8} ({xgb['confidence']:.1%}) | "
                        f"TabPFN: {tabpfn['direction']:8} ({tabpfn['confidence']:.1%}) | "
                        f"{'✓ AGREE' if results[-1]['agreement'] else '✗ DISAGREE'}"
                    )

        except Exception as e:
            print(f"Error processing {symbol}: {e}")
            continue

    if not results:
        print("\n⚠️  No comparison data found. Run with --generate to create forecasts first.")
        return pd.DataFrame()

    return pd.DataFrame(results)


def compare_models_generate(symbols: list, horizons: list) -> pd.DataFrame:
    """
    Compare models by generating fresh forecasts for all symbols.

    Args:
        symbols: List of symbol tickers
        horizons: List of horizon days

    Returns:
        DataFrame with comparison results
    """
    if not is_tabpfn_available():
        print("\n❌ TabPFN not available. Install with: pip install tabpfn torch")
        return pd.DataFrame()

    print("\n" + "=" * 80)
    print("GENERATE COMPARISON: Running both models on same data")
    print("=" * 80)

    results = []

    for symbol in symbols:
        print(f"\n{'=' * 80}")
        print(f"Testing: {symbol}")
        print(f"{'=' * 80}")

        # Fetch data
        df = fetch_ohlc_data(symbol, limit=500)
        if df.empty:
            continue

        for horizon_days in horizons:
            print(f"\n  Horizon: {horizon_days}D")

            try:
                # XGBoost
                print(f"    Running XGBoost...")
                start_time = datetime.now()
                xgb_forecaster = BaselineForecaster()
                xgb_forecaster.fit(df, horizon_days=horizon_days)
                pred_xgb = xgb_forecaster.predict(df, horizon_days=horizon_days)
                xgb_time = (datetime.now() - start_time).total_seconds()

                # TabPFN
                print(f"    Running TabPFN...")
                start_time = datetime.now()
                tabpfn_forecaster = TabPFNForecaster(device='cpu')
                tabpfn_forecaster.fit(df, horizon_days=horizon_days)
                pred_tabpfn = tabpfn_forecaster.predict(df, horizon_days=horizon_days)
                tabpfn_time = (datetime.now() - start_time).total_seconds()

                # Compare
                agreement = pred_xgb['label'] == pred_tabpfn['label']

                results.append({
                    'symbol': symbol,
                    'horizon': f'{horizon_days}D',
                    'xgb_direction': pred_xgb['label'],
                    'xgb_confidence': pred_xgb['confidence'],
                    'xgb_return': pred_xgb.get('forecast_return', 0),
                    'xgb_train_time': xgb_time,
                    'tabpfn_direction': pred_tabpfn['label'],
                    'tabpfn_confidence': pred_tabpfn['confidence'],
                    'tabpfn_return': pred_tabpfn.get('forecast_return', 0),
                    'tabpfn_train_time': tabpfn_time,
                    'tabpfn_interval_width': pred_tabpfn.get('intervals', {}).get('width', 0),
                    'agreement': agreement,
                })

                print(
                    f"    XGB: {pred_xgb['label']:8} ({pred_xgb['confidence']:.1%}, {xgb_time:.2f}s) | "
                    f"TabPFN: {pred_tabpfn['label']:8} ({pred_tabpfn['confidence']:.1%}, {tabpfn_time:.2f}s) | "
                    f"{'✓ AGREE' if agreement else '✗ DISAGREE'}"
                )

            except Exception as e:
                print(f"    ❌ Error: {e}")
                continue

    if not results:
        print("\n⚠️  No results generated")
        return pd.DataFrame()

    return pd.DataFrame(results)


def print_summary(df: pd.DataFrame):
    """Print summary statistics."""
    if df.empty:
        return

    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")

    print(f"\nTotal comparisons: {len(df)}")
    print(f"Agreement rate: {df['agreement'].mean():.1%}")

    print(f"\n{'─' * 80}")
    print("Confidence Comparison:")
    print(f"{'─' * 80}")
    print(f"{'':20} {'XGBoost':>15} {'TabPFN':>15} {'Difference':>15}")
    print(f"{'─' * 80}")
    print(f"{'Mean':20} {df['xgb_confidence'].mean():>14.1%} {df['tabpfn_confidence'].mean():>14.1%} {(df['tabpfn_confidence'] - df['xgb_confidence']).mean():>14.1%}")
    print(f"{'Std Dev':20} {df['xgb_confidence'].std():>14.1%} {df['tabpfn_confidence'].std():>14.1%}")
    print(f"{'Min':20} {df['xgb_confidence'].min():>14.1%} {df['tabpfn_confidence'].min():>14.1%}")
    print(f"{'Max':20} {df['xgb_confidence'].max():>14.1%} {df['tabpfn_confidence'].max():>14.1%}")

    print(f"\n{'─' * 80}")
    print("Agreement by Horizon:")
    print(f"{'─' * 80}")
    for horizon in sorted(df['horizon'].unique()):
        subset = df[df['horizon'] == horizon]
        print(f"{horizon:10} {subset['agreement'].mean():>10.1%} ({len(subset)} forecasts)")

    print(f"\n{'─' * 80}")
    print("Direction Distribution:")
    print(f"{'─' * 80}")
    xgb_dist = df['xgb_direction'].value_counts()
    tabpfn_dist = df['tabpfn_direction'].value_counts()
    print(f"{'Direction':15} {'XGBoost':>12} {'TabPFN':>12}")
    print(f"{'─' * 80}")
    for direction in ['bullish', 'neutral', 'bearish']:
        xgb_count = xgb_dist.get(direction, 0)
        tabpfn_count = tabpfn_dist.get(direction, 0)
        print(f"{direction:15} {xgb_count:>12} {tabpfn_count:>12}")

    # Training time comparison (if available)
    if 'xgb_train_time' in df.columns and df['xgb_train_time'].notna().any():
        print(f"\n{'─' * 80}")
        print("Training Time (seconds):")
        print(f"{'─' * 80}")
        print(f"{'XGBoost mean':20} {df['xgb_train_time'].mean():>14.2f}s")
        print(f"{'TabPFN mean':20} {df['tabpfn_train_time'].mean():>14.2f}s")
        print(f"{'Speedup':20} {df['xgb_train_time'].mean() / df['tabpfn_train_time'].mean():>14.2f}x")


def main():
    parser = argparse.ArgumentParser(description='Compare TabPFN vs XGBoost forecasters')
    parser.add_argument('--symbols', help='Comma-separated list of symbols', default=','.join(DEFAULT_SYMBOLS))
    parser.add_argument('--horizons', help='Comma-separated list of horizons (days)', default=','.join(map(str, HORIZONS)))
    parser.add_argument('--live', action='store_true', help='Pull from database instead of generating')
    parser.add_argument('--generate', action='store_true', help='Generate fresh forecasts')
    parser.add_argument('--output', help='Output CSV file', default='tabpfn_vs_xgboost_results.csv')
    parser.add_argument('--output-json', help='Output JSON file')

    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(',')]
    horizons = [int(h.strip()) for h in args.horizons.split(',')]

    print(f"Comparing models on {len(symbols)} symbols × {len(horizons)} horizons")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Horizons: {', '.join(f'{h}D' for h in horizons)}")

    # Run comparison
    if args.live:
        df_results = compare_models_live(symbols, horizons)
    else:
        df_results = compare_models_generate(symbols, horizons)

    if df_results.empty:
        print("\n⚠️  No results to display")
        return

    # Print summary
    print_summary(df_results)

    # Save results
    df_results.to_csv(args.output, index=False)
    print(f"\n✓ Results saved to: {args.output}")

    if args.output_json:
        df_results.to_json(args.output_json, orient='records', indent=2)
        print(f"✓ Results saved to: {args.output_json}")


if __name__ == '__main__':
    main()
