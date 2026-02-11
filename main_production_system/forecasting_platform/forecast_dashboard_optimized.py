#!/usr/bin/env python3
"""
Optimized Forecast Dashboard with Efficient Data Flow

Enhanced version with:
- Centralized data I/O (DataIO)
- Configuration management (ConfigLoader)
- Resilient data provider
- Streamlit caching best practices
- Improved performance

Usage:
    python forecast_dashboard_optimized.py TSM
    python forecast_dashboard_optimized.py SPY --refresh 60

Author: ML Analysis Platform Team
Date: October 28, 2025
"""

import argparse
import time
import os
import sys
from datetime import datetime
from pathlib import Path
import logging

# Add parent directories to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(parent_dir)
sys.path.insert(0, root_dir)

# Import optimization components
from src.option_analysis.data_io import get_data_io
from src.option_analysis.data_provider import DataProviderManager
from main_production_system.core.config_loader import get_config
from multi_timeframe_forecaster import Forecaster

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize global components
config = get_config()
data_io = get_data_io(base=Path(root_dir))
data_provider = DataProviderManager(config=config.get_all())


def print_header():
    """Print dashboard header."""
    print("\n" + "="*80)
    print("🌊 WAVE ANALOGY FORECAST DASHBOARD (OPTIMIZED)")
    print("="*80)
    print("\n🚀 Using: DataIO caching, Config management, Resilient provider")


def load_data_efficient(symbol: str, use_live: bool = False) -> dict:
    """
    Load data efficiently with caching and fallback.
    
    Args:
        symbol: Stock symbol
        use_live: Whether to fetch live data
        
    Returns:
        Dictionary with data and metadata
    """
    start_time = time.time()
    
    # Get paths from config
    raw_path = config.get_path('paths.raw')
    
    if use_live:
        logger.info(f"Fetching live data for {symbol}...")
        try:
            # Fetch from provider (with caching and rate limiting)
            df = data_provider.fetch_daily(symbol, provider='alpha_vantage')
            
            # Save to local cache
            local_file = raw_path / f"{symbol}_daily.parquet"
            data_io.write_parquet(df, local_file)
            
            logger.info(f"Fetched {len(df)} rows (live)")
            
        except Exception as e:
            logger.warning(f"Live fetch failed: {e}. Falling back to local data.")
            use_live = False
    
    if not use_live:
        # Try Parquet first, then CSV
        parquet_file = raw_path / f"{symbol}_daily.parquet"
        csv_file = raw_path / f"data_NYSE_{symbol}_2y_1h.csv"
        
        if parquet_file.exists():
            logger.info(f"Loading from cached Parquet: {parquet_file.name}")
            df = data_io.read_auto(parquet_file)
        elif csv_file.exists():
            logger.info(f"Loading from CSV (will cache): {csv_file.name}")
            df = data_io.read_auto(csv_file)  # Auto-caches to Parquet
        else:
            raise FileNotFoundError(f"No data found for {symbol}")
    
    load_time = time.time() - start_time
    
    return {
        'data': df,
        'symbol': symbol,
        'source': 'live' if use_live else 'cached',
        'load_time_sec': load_time,
        'num_rows': len(df)
    }


def print_data_info(data_info: dict):
    """
    Print data loading information.
    
    Args:
        data_info: Dictionary from load_data_efficient
    """
    print(f"\n📊 DATA LOADED")
    print("─" * 80)
    print(f"  Symbol: {data_info['symbol']}")
    print(f"  Source: {data_info['source'].upper()}")
    print(f"  Rows: {data_info['num_rows']:,}")
    print(f"  Load Time: {data_info['load_time_sec']:.3f}s")
    
    # Show data quality metrics
    df = data_info['data']
    if 'timestamp' in df.columns:
        print(f"  Date Range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    if 'close' in df.columns:
        print(f"  Price Range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
    print()


def print_forecast(forecast: dict):
    """
    Display formatted forecast.
    
    Args:
        forecast: Forecast dictionary from Forecaster
    """
    if 'error' in forecast:
        print(f"\n❌ Error: {forecast['error']}")
        return

    symbol = forecast['symbol']
    timestamp = forecast['timestamp']

    print(f"\nSYMBOL: {symbol}")
    print(f"TIME: {timestamp}")
    
    # Market status
    market_open = forecast.get('market_open', True)
    last_close_date = forecast.get('last_close_date', '')
    if market_open:
        print(f"MARKET: OPEN")
    else:
        print(f"MARKET: CLOSED (Using {last_close_date} close)")
    print()

    # Wave Analogy Section
    print("🌊 WAVE ANALOGY FORECAST")
    print("━" * 80)
    print()

    # Current "Water Current"
    print('Current "Water Current" (Long-term):')
    regime = forecast['regime']
    if 'UP' in regime:
        print("  Weekly/Daily: BULLISH (↑)")
    elif 'DOWN' in regime:
        print("  Weekly/Daily: BEARISH (↓)")
    else:
        print("  Weekly/Daily: NEUTRAL (→)")

    print(f"  Regime: {regime}", end="")
    if regime in ['TRENDING_UP', 'TRENDING_DOWN']:
        print(" ✅")
    else:
        print(" ⚠️ ")
    print()

    # 4hr Forecast (The Wave)
    direction = forecast['4hr_direction']
    probability = forecast['4hr_probability']
    confidence = forecast['4hr_confidence']

    print("4hr Forecast (Next Wave):")
    print(f"  Direction: {direction}", "↑" if direction == "UP" else "↓")
    print(f"  Probability: {probability*100:.1f}%")
    print(f"  Confidence: {confidence:.1f}%", end="")
    if confidence > 70:
        print(" (HIGH)")
    elif confidence > 50:
        print(" (MODERATE)")
    else:
        print(" (LOW)")
    print(f"  Expected Move: ±{forecast['expected_move_pct']:.2f}%")
    print()

    # Trading Recommendation
    print("💼 TRADING RECOMMENDATION")
    print("━" * 80)
    recommendation = forecast.get('recommendation', 'HOLD')
    position_size = forecast.get('position_size', 0)
    
    print(f"  Action: {recommendation}")
    print(f"  Position Size: {position_size:.1%}")
    
    if 'stop_loss' in forecast:
        print(f"  Stop Loss: ${forecast['stop_loss']:.2f}")
    if 'take_profit' in forecast:
        print(f"  Take Profit: ${forecast['take_profit']:.2f}")
    print()


def print_performance_stats(stats: dict):
    """
    Print performance statistics.
    
    Args:
        stats: Performance statistics dictionary
    """
    print("⏱️  PERFORMANCE STATS")
    print("─" * 80)
    print(f"  Data Load: {stats.get('data_load_time', 0):.3f}s")
    print(f"  Feature Engineering: {stats.get('feature_time', 0):.3f}s")
    print(f"  Model Prediction: {stats.get('predict_time', 0):.3f}s")
    print(f"  Total Pipeline: {stats.get('total_time', 0):.3f}s")
    print()


def run_dashboard(symbol: str, refresh_sec: int = 0, use_live: bool = False):
    """
    Run the forecast dashboard.
    
    Args:
        symbol: Stock symbol
        refresh_sec: Refresh interval (0 = run once)
        use_live: Whether to fetch live data
    """
    print_header()
    
    # Show cache info
    cache_info = data_io.get_cache_info()
    print(f"💾 CACHE STATUS")
    print("─" * 80)
    print(f"  Cache Directory: {cache_info['cache_dir']}")
    print(f"  Cached Files: {cache_info['num_files']}")
    print(f"  Total Size: {cache_info['total_size_mb']:.2f}MB")
    
    iteration = 0
    
    try:
        while True:
            iteration += 1
            
            print(f"\n{'='*80}")
            print(f"ITERATION {iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*80)
            
            # Track timing
            start_time = time.time()
            
            # Load data efficiently
            data_info = load_data_efficient(symbol, use_live=use_live)
            print_data_info(data_info)
            data_load_time = time.time() - start_time
            
            # Generate forecast
            forecaster = Forecaster(symbol=symbol)
            
            feature_start = time.time()
            forecast = forecaster.forecast(data_info['data'])
            feature_time = time.time() - feature_start
            
            # Display forecast
            print_forecast(forecast)
            
            total_time = time.time() - start_time
            
            # Performance stats
            stats = {
                'data_load_time': data_load_time,
                'feature_time': feature_time,
                'predict_time': 0,  # Included in feature_time
                'total_time': total_time
            }
            print_performance_stats(stats)
            
            # Check if refresh needed
            if refresh_sec == 0:
                break
            
            print(f"\n🔄 Next refresh in {refresh_sec} seconds...")
            print("Press Ctrl+C to stop")
            time.sleep(refresh_sec)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Dashboard stopped by user")
    except Exception as e:
        logger.error(f"Dashboard error: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Wave Analogy Forecast Dashboard (Optimized)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single forecast
  python forecast_dashboard_optimized.py TSM

  # Auto-refresh every 60 seconds
  python forecast_dashboard_optimized.py SPY --refresh 60

  # Use live data from Alpha Vantage
  python forecast_dashboard_optimized.py AAPL --live

  # Live data with auto-refresh
  python forecast_dashboard_optimized.py CRWD --live --refresh 300
        """
    )
    
    parser.add_argument('symbol', help='Stock symbol (e.g., TSM, SPY, AAPL)')
    parser.add_argument('--refresh', type=int, default=0,
                       help='Auto-refresh interval in seconds (default: 0 = run once)')
    parser.add_argument('--live', action='store_true',
                       help='Fetch live data from Alpha Vantage')
    parser.add_argument('--clear-cache', action='store_true',
                       help='Clear data cache before running')
    
    args = parser.parse_args()
    
    # Clear cache if requested
    if args.clear_cache:
        logger.info("Clearing data cache...")
        data_io.clear_cache()
        if hasattr(data_provider.providers.get('alpha_vantage'), 'clear_cache'):
            data_provider.providers['alpha_vantage'].clear_cache(args.symbol)
    
    # Run dashboard
    run_dashboard(
        symbol=args.symbol.upper(),
        refresh_sec=args.refresh,
        use_live=args.live
    )


if __name__ == '__main__':
    main()
