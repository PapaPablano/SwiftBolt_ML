#!/usr/bin/env python3
"""
Forecast Accuracy Tracker

Tracks and reports forecast accuracy over time by regime and confidence level.

Usage:
    python forecast_accuracy_tracker.py TSM --days 30
"""

import pandas as pd
import numpy as np
import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import json

# Add parent directories to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(parent_dir)
sys.path.insert(0, root_dir)

from multi_timeframe_forecaster import Forecaster


class AccuracyTracker:
    """
    Track forecast accuracy over time.
    """

    def __init__(self, symbol: str, log_file: str = None):
        """
        Initialize tracker.

        Args:
            symbol: Stock symbol
            log_file: Path to forecast log file
        """
        self.symbol = symbol
        self.log_file = log_file or f'forecast_log_{symbol}.jsonl'
        self.forecaster = Forecaster()

    def log_forecast(self, forecast: dict):
        """
        Log a forecast.

        Args:
            forecast: Forecast dictionary
        """
        # Add to log file (one JSON per line)
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(forecast) + '\n')

    def load_forecasts(self) -> pd.DataFrame:
        """Load all logged forecasts."""
        if not Path(self.log_file).exists():
            return pd.DataFrame()

        forecasts = []
        with open(self.log_file, 'r') as f:
            for line in f:
                forecasts.append(json.loads(line))

        return pd.DataFrame(forecasts)

    def verify_forecasts(self, df_forecasts: pd.DataFrame) -> pd.DataFrame:
        """
        Verify forecast accuracy by downloading actual outcomes.

        Args:
            df_forecasts: DataFrame of forecasts

        Returns:
            DataFrame with accuracy results
        """
        # This would download actual price data and compare
        # Simplified for now - would need 4hr+ of delay to verify

        print("Verifying forecasts...")
        print("  (Note: Requires 4hr+ delay to verify 4hr forecasts)")

        # Placeholder - in production, would:
        # 1. For each forecast timestamp
        # 2. Download actual 4hr candle that followed
        # 3. Check if direction matched
        # 4. Return accuracy stats

        return df_forecasts

    def generate_report(self, days: int = 30):
        """
        Generate accuracy report.

        Args:
            days: Number of days to analyze
        """
        df = self.load_forecasts()

        if len(df) == 0:
            print(f"\n❌ No forecast logs found for {self.symbol}")
            print(f"   Start logging: python forecast_dashboard.py {self.symbol}")
            return

        print("\n" + "="*80)
        print(f"📊 FORECAST ACCURACY REPORT - {self.symbol}")
        print("="*80)
        print()

        # Filter to date range
        cutoff = datetime.now() - timedelta(days=days)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df[df['timestamp'] >= cutoff]

        print(f"Analysis Period: Last {days} days")
        print(f"Total Forecasts: {len(df)}")
        print()

        # By Regime
        print("Performance by Regime:")
        print("━" * 80)

        regime_stats = df.groupby('regime').agg({
            '4hr_probability': ['count', 'mean'],
            '4hr_confidence': 'mean'
        }).round(3)

        for regime in df['regime'].unique():
            regime_df = df[df['regime'] == regime]
            count = len(regime_df)
            avg_prob = regime_df['4hr_probability'].mean()
            avg_conf = regime_df['4hr_confidence'].mean()

            print(f"  {regime}:")
            print(f"    Forecasts: {count}")
            print(f"    Avg Probability: {avg_prob*100:.1f}%")
            print(f"    Avg Confidence: {avg_conf:.1f}%")
            print()

        # By Direction
        print("Forecasts by Direction:")
        print("━" * 80)

        direction_counts = df['4hr_direction'].value_counts()
        for direction, count in direction_counts.items():
            pct = count / len(df) * 100
            print(f"  {direction}: {count} ({pct:.1f}%)")
        print()

        # High Confidence Forecasts
        high_conf = df[df['4hr_confidence'] > 70]
        print(f"High Confidence Forecasts (>70%):")
        print("━" * 80)
        print(f"  Count: {len(high_conf)}")
        print(f"  Percentage: {len(high_conf)/len(df)*100:.1f}%")
        print()

        # Expected vs Actual (placeholder)
        print("Expected Accuracy:")
        print("━" * 80)
        for regime in df['regime'].unique():
            regime_df = df[df['regime'] == regime]
            if len(regime_df) > 0:
                expected = regime_df['expected_accuracy'].mean()
                print(f"  {regime}: {expected*100:.0f}%")
        print()

        print("="*80)
        print("\nNote: Actual accuracy verification requires 4hr+ delay")
        print("      to compare forecast vs outcome. Implement with")
        print("      verify_forecasts() method for production use.")
        print("="*80)


def main():
    parser = argparse.ArgumentParser(
        description='Forecast Accuracy Tracker'
    )
    parser.add_argument(
        'symbol', type=str,
        help='Stock symbol'
    )
    parser.add_argument(
        '--days', type=int, default=30,
        help='Number of days to analyze (default: 30)'
    )

    args = parser.parse_args()

    tracker = AccuracyTracker(args.symbol)
    tracker.generate_report(args.days)


if __name__ == "__main__":
    main()
