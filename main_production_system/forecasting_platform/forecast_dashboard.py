#!/usr/bin/env python3
"""
Forecast Dashboard - Beautiful Terminal Display

Real-time forecasting dashboard showing your wave analogy predictions with
confidence scores, regime detection, and trading recommendations.

Usage:
    python forecast_dashboard.py TSM
    python forecast_dashboard.py SPY --refresh 60
"""

import argparse
import time
import os
import sys
from datetime import datetime

# Add parent directories to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(parent_dir)
sys.path.insert(0, root_dir)

from multi_timeframe_forecaster import Forecaster


def print_header():
    """Print dashboard header."""
    print("\n" + "="*80)
    print("🌊 WAVE ANALOGY FORECAST DASHBOARD")
    print("="*80)


def print_forecast(forecast: dict):
    """Display formatted forecast."""
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
    print("Current \"Water Current\" (Long-term):")
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

    # Detailed Forecast Section
    print("📊 DETAILED FORECAST")
    print("━" * 80)
    print()

    print("Next 4hr Candle:")
    if direction == "UP":
        print(f"  UP Probability: {probability*100:.1f}%")
        print(f"  DOWN Probability: {(1-probability)*100:.1f}%")
    else:
        print(f"  DOWN Probability: {probability*100:.1f}%")
        print(f"  UP Probability: {(1-probability)*100:.1f}%")

    print(f"  Forecast Accuracy (backtested): {forecast['expected_accuracy']*100:.0f}% in {regime}")
    print()

    # Key Levels
    current = forecast['current_price']
    support = forecast['support']
    resistance = forecast['resistance']

    print("Key Levels:")
    print(f"  Resistance: ${resistance:.2f}")
    print(f"  Current:    ${current:.2f}")
    print(f"  Support:    ${support:.2f}")
    print()

    # Risk Factors
    print("⚠️  RISK FACTORS")
    print("━" * 80)
    print()

    print("Confidence Factors:")
    if regime in ['TRENDING_UP', 'TRENDING_DOWN']:
        print("  ✅ Regime: TRENDING (+15% confidence)")
    else:
        print("  ⚠️  Regime: NOT TRENDING (-10% confidence)")

    print(f"  ✅ Historical: {forecast['expected_accuracy']*100:.0f}% accuracy in this regime")
    print()

    # Recommendation
    print("🎯 TRADING RECOMMENDATION")
    print("━" * 80)
    print()

    print(forecast['recommendation'])
    print()

    if direction == "UP" and confidence > 70:
        target = current * (1 + forecast['expected_move_pct']/100)
        stop = support
        print(f"\nFor Manual Trading:")
        print(f"  Entry: Current levels (${current:.2f})")
        print(f"  Target: ${target:.2f} ({forecast['expected_move_pct']:.1f}% move)")
        print(f"  Stop: ${stop:.2f} (support level)")
        print(f"  Position Size: Full (high confidence)")
        print(f"  Time Horizon: 4-8 hours")
    elif direction == "DOWN" and confidence > 70:
        target = current * (1 - forecast['expected_move_pct']/100)
        stop = resistance
        print(f"\nFor Manual Trading:")
        print(f"  Entry: Current levels (${current:.2f})")
        print(f"  Target: ${target:.2f} ({forecast['expected_move_pct']:.1f}% move)")
        print(f"  Stop: ${stop:.2f} (resistance level)")
        print(f"  Position Size: Full (high confidence)")
        print(f"  Time Horizon: 4-8 hours")
    else:
        print("\nFor Manual Trading:")
        print("  Recommendation: WAIT for higher confidence setup")

    # Price Projections
    if 'price_projections' in forecast:
        print_price_projections(forecast['price_projections'], symbol)

    print()
    print("="*80)


def print_price_projections(projections: dict, symbol: str):
    """Print price projections summary."""
    print("\n📈 PRICE PROJECTIONS")
    print("━" * 80)
    
    current_price = projections['current_price']
    direction = projections['direction']
    confidence = projections['confidence']
    
    print(f"Current Price: ${current_price:.2f}")
    print(f"Direction: {direction} | Confidence: {confidence:.1f}%")
    print()
    
    print("5-Day Price Targets:")
    print("-" * 80)
    
    for i in range(len(projections['dates'])):
        if i == 0:
            continue  # Skip current day
        
        date_str = projections['dates'][i][:10]  # Extract date part
        day_num = i
        
        conservative = projections['conservative'][i]
        expected = projections['expected'][i]
        optimistic = projections['optimistic'][i]
        
        print(f"Day {day_num} ({date_str}):")
        print(f"  Conservative: ${conservative:.2f}")
        print(f"  Expected:     ${expected:.2f}")
        print(f"  Optimistic:   ${optimistic:.2f}")
        print()
    
    # Calculate returns
    final_day = len(projections['dates']) - 1
    cons_return = (projections['conservative'][final_day] - current_price) / current_price * 100
    exp_return = (projections['expected'][final_day] - current_price) / current_price * 100
    opt_return = (projections['optimistic'][final_day] - current_price) / current_price * 100
    
    print("Expected Returns:")
    print(f"  Conservative: {cons_return:+.2f}%")
    print(f"  Expected:     {exp_return:+.2f}%")
    print(f"  Optimistic:   {opt_return:+.2f}%")


def run_dashboard(symbol: str, refresh_seconds: int = 0):
    """
    Run forecast dashboard.

    Args:
        symbol: Stock symbol
        refresh_seconds: Auto-refresh interval (0 = no refresh)
    """
    forecaster = Forecaster()

    # Train on first run
    print(f"\nInitializing forecaster for {symbol}...")
    forecaster.train_on_recent_data(symbol)

    while True:
        print_header()

        # Generate forecast
        forecast = forecaster.forecast(symbol)

        # Display
        print_forecast(forecast)

        if refresh_seconds == 0:
            break

        print(f"\n⏱️ Refreshing in {refresh_seconds} seconds... (Ctrl+C to exit)")
        time.sleep(refresh_seconds)


def main():
    parser = argparse.ArgumentParser(
        description='Wave Analogy Forecast Dashboard'
    )
    parser.add_argument(
        'symbol', type=str,
        help='Stock symbol (e.g., TSM, SPY)'
    )
    parser.add_argument(
        '--refresh', type=int, default=0,
        help='Auto-refresh interval in seconds (0 = no refresh)'
    )

    args = parser.parse_args()

    try:
        run_dashboard(args.symbol, args.refresh)
    except KeyboardInterrupt:
        print("\n\n👋 Dashboard closed.")
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()
