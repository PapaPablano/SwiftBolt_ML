"""
Complete Example: Polynomial S/R with Flux Charts Visualization.

Demonstrates:
1. Loading OHLC data from Supabase
2. Detecting pivot points
3. Fitting polynomial regressions
4. Creating TradingView-style charts
5. Generating forecasts

Usage:
    python examples/polynomial_sr_example.py --symbol AAPL --days 30
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.features.sr_polynomial_fixed import SRPolynomialRegressor
from src.visualization.polynomial_sr_chart import (
    FluxChartVisualizer,
    InteractiveFluxChart,
    create_flux_chart
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_ohlc_data(symbol: str, days: int = 30) -> pd.DataFrame:
    """
    Fetch OHLC data from Supabase or use demo data.
    
    Args:
        symbol: Trading symbol
        days: Number of days of history
        
    Returns:
        DataFrame with OHLC data
    """
    try:
        # Try to import Supabase client
        from src.data.supabase_client import get_ohlc_data
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        df = get_ohlc_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval='1h'
        )
        
        logger.info(f"Fetched {len(df)} bars for {symbol}")
        return df
        
    except Exception as e:
        logger.warning(f"Could not fetch real  {e}")
        logger.info("Using synthetic demo data...")
        return generate_demo_data(days * 24)  # hourly bars


def generate_demo_data(n_bars: int = 500) -> pd.DataFrame:
    """
    Generate synthetic OHLC data for demo.
    
    Args:
        n_bars: Number of bars to generate
        
    Returns:
        DataFrame with OHLC data
    """
    np.random.seed(42)
    
    # Generate price trend with mean reversion
    trend = np.linspace(100, 120, n_bars)
    noise = np.cumsum(np.random.randn(n_bars) * 0.5)
    mean_reversion = -0.1 * noise
    price = trend + noise + mean_reversion
    
    # Generate OHLC from price
    df = pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=n_bars, freq='1h'),
        'open': price + np.random.randn(n_bars) * 0.2,
        'high': price + np.abs(np.random.randn(n_bars)) * 0.8,
        'low': price - np.abs(np.random.randn(n_bars)) * 0.8,
        'close': price + np.random.randn(n_bars) * 0.2,
        'volume': np.random.randint(10000, 100000, n_bars)
    })
    
    # Ensure high is highest, low is lowest
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)
    
    return df


def detect_pivots(
    df: pd.DataFrame,
    left_bars: int = 5,
    right_bars: int = 5
) -> List[Dict[str, Any]]:
    """
    Detect pivot highs and lows.
    
    Args:
        df: OHLC DataFrame
        left_bars: Bars to left of pivot
        right_bars: Bars to right of pivot
        
    Returns:
        List of pivot dictionaries
    """
    pivots = []
    
    for i in range(left_bars, len(df) - right_bars):
        # Check for pivot high
        is_pivot_high = True
        for j in range(i - left_bars, i + right_bars + 1):
            if j != i and df.iloc[j]['high'] > df.iloc[i]['high']:
                is_pivot_high = False
                break
        
        if is_pivot_high:
            pivots.append({
                'index': i,
                'price': df.iloc[i]['high'],
                'type': 'high',
                'timestamp': df.iloc[i]['timestamp']
            })
        
        # Check for pivot low
        is_pivot_low = True
        for j in range(i - left_bars, i + right_bars + 1):
            if j != i and df.iloc[j]['low'] < df.iloc[i]['low']:
                is_pivot_low = False
                break
        
        if is_pivot_low:
            pivots.append({
                'index': i,
                'price': df.iloc[i]['low'],
                'type': 'low',
                'timestamp': df.iloc[i]['timestamp']
            })
    
    logger.info(
        f"Detected {len([p for p in pivots if p['type'] == 'high'])} resistance pivots, "
        f"{len([p for p in pivots if p['type'] == 'low'])} support pivots"
    )
    
    return pivots


def analyze_polynomial_sr(
    df: pd.DataFrame,
    pivots: List[Dict[str, Any]],
    degree: int = 2
) -> Tuple[SRPolynomialRegressor, Dict[str, Any]]:
    """
    Fit polynomial regressions and extract features.
    
    Args:
        df: OHLC DataFrame
        pivots: Pivot points
        degree: Polynomial degree
        
    Returns:
        (regressor, features dict)
    """
    regressor = SRPolynomialRegressor(degree=degree, min_points=4)
    
    # Fit curves
    support_coeffs = regressor.fit_support_curve(pivots)
    resistance_coeffs = regressor.fit_resistance_curve(pivots)
    
    # Extract current levels
    current_idx = len(df) - 1
    features = {
        'support_level': None,
        'resistance_level': None,
        'support_slope': 0.0,
        'resistance_slope': 0.0,
        'support_trend': 'N/A',
        'resistance_trend': 'N/A',
    }
    
    if support_coeffs is not None:
        features['support_level'] = regressor.predict_level(
            support_coeffs, current_idx, curve_type='support'
        )
        features['support_slope'] = regressor.compute_slope(
            support_coeffs, at_x=1.0, curve_type='support'
        )
        features['support_trend'] = (
            'Rising' if features['support_slope'] > 0.1 else
            'Falling' if features['support_slope'] < -0.1 else
            'Flat'
        )
    
    if resistance_coeffs is not None:
        features['resistance_level'] = regressor.predict_level(
            resistance_coeffs, current_idx, curve_type='resistance'
        )
        features['resistance_slope'] = regressor.compute_slope(
            resistance_coeffs, at_x=1.0, curve_type='resistance'
        )
        features['resistance_trend'] = (
            'Rising' if features['resistance_slope'] > 0.1 else
            'Falling' if features['resistance_slope'] < -0.1 else
            'Flat'
        )
    
    return regressor, features


def print_analysis_summary(
    df: pd.DataFrame,
    features: Dict[str, Any]
):
    """
    Print analysis summary to console.
    """
    current_price = df.iloc[-1]['close']
    
    print("\n" + "="*60)
    print("POLYNOMIAL SUPPORT & RESISTANCE ANALYSIS")
    print("="*60)
    print(f"\nCurrent Price: ${current_price:.2f}")
    print(f"Latest Bar: {df.iloc[-1]['timestamp']}")
    print(f"Total Bars: {len(df)}")
    
    print("\n" + "-"*60)
    print("SUPPORT")
    print("-"*60)
    if features['support_level']:
        print(f"  Level:     ${features['support_level']:.2f}")
        print(f"  Distance:  ${current_price - features['support_level']:.2f} "
              f"({(current_price - features['support_level'])/current_price*100:.2f}%)")
        print(f"  Slope:     {features['support_slope']:.4f} $/bar")
        print(f"  Trend:     {features['support_trend']}")
    else:
        print("  Not enough pivot points")
    
    print("\n" + "-"*60)
    print("RESISTANCE")
    print("-"*60)
    if features['resistance_level']:
        print(f"  Level:     ${features['resistance_level']:.2f}")
        print(f"  Distance:  ${features['resistance_level'] - current_price:.2f} "
              f"({(features['resistance_level'] - current_price)/current_price*100:.2f}%)")
        print(f"  Slope:     {features['resistance_slope']:.4f} $/bar")
        print(f"  Trend:     {features['resistance_trend']}")
    else:
        print("  Not enough pivot points")
    
    print("\n" + "="*60)


def main():
    parser = argparse.ArgumentParser(
        description='Polynomial S/R Analysis with Flux Charts'
    )
    parser.add_argument(
        '--symbol', '-s',
        default='DEMO',
        help='Trading symbol (default: DEMO for synthetic data)'
    )
    parser.add_argument(
        '--days', '-d',
        type=int,
        default=30,
        help='Days of history (default: 30)'
    )
    parser.add_argument(
        '--degree',
        type=int,
        default=2,
        choices=[1, 2, 3],
        help='Polynomial degree: 1=linear, 2=quadratic, 3=cubic (default: 2)'
    )
    parser.add_argument(
        '--pivot-bars',
        type=int,
        default=5,
        help='Bars on each side for pivot detection (default: 5)'
    )
    parser.add_argument(
        '--style',
        default='dark',
        choices=['dark', 'light'],
        help='Chart style (default: dark)'
    )
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Create interactive Plotly chart instead of static'
    )
    parser.add_argument(
        '--output', '-o',
        default='polynomial_sr_chart',
        help='Output filename (without extension)'
    )
    parser.add_argument(
        '--forecast',
        type=int,
        default=50,
        help='Forecast bars to extend (default: 50)'
    )
    
    args = parser.parse_args()
    
    # Fetch data
    logger.info(f"Loading data for {args.symbol}...")
    df = fetch_ohlc_data(args.symbol, args.days)
    
    # Detect pivots
    logger.info("Detecting pivot points...")
    pivots = detect_pivots(df, args.pivot_bars, args.pivot_bars)
    
    if len(pivots) < 4:
        logger.error("Not enough pivots detected. Try increasing --days or decreasing --pivot-bars")
        return 1
    
    # Analyze
    logger.info("Fitting polynomial regressions...")
    regressor, features = analyze_polynomial_sr(df, pivots, args.degree)
    
    # Print summary
    print_analysis_summary(df, features)
    
    # Create chart
    logger.info("Creating Flux Charts visualization...")
    
    ext = '.html' if args.interactive else '.png'
    output_path = f"{args.output}{ext}"
    
    fig = create_flux_chart(
        df=df,
        regressor=regressor,
        pivots=pivots,
        signals=None,
        style=args.style,
        interactive=args.interactive,
        save_path=output_path
    )
    
    logger.info(f"Chart saved to: {output_path}")
    
    # Generate forecast data
    if regressor.support_coeffs is not None:
        support_forecast = regressor.generate_forecast(
            len(df) - 1,
            args.forecast,
            curve_type='support'
        )
        logger.info(f"Support forecast: {len(support_forecast)} points")
    
    if regressor.resistance_coeffs is not None:
        resistance_forecast = regressor.generate_forecast(
            len(df) - 1,
            args.forecast,
            curve_type='resistance'
        )
        logger.info(f"Resistance forecast: {len(resistance_forecast)} points")
    
    print("\n✓ Analysis complete!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
