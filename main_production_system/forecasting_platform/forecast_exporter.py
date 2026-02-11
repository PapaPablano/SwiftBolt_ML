#!/usr/bin/env python3
"""
Forecast Export Bridge Tool

Exports forecasts from the ML platform in formats compatible with external tools,
including the visualization script format.

Usage:
    python forecast_exporter.py TSM --format visualization
    python forecast_exporter.py TSM --format dashboard --days 10
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import argparse
from pathlib import Path
import json
import os
import sys

# Add parent directories to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(parent_dir)
sys.path.insert(0, root_dir)

from multi_timeframe_forecaster import Forecaster


class ForecastExporter:
    """
    Export forecasts in various formats for external tools and analysis.
    """
    
    def __init__(self):
        self.forecaster = Forecaster()
    
    def export_for_visualization_script(self, symbol: str, training_period: str = '2y', 
                                      live_period: str = '5d', output_file: str = None) -> str:
        """
        Export forecast data compatible with the visualization script.
        
        Args:
            symbol: Stock symbol
            training_period: Training data period (1y, 2y, 3y)
            live_period: Live data period (1d, 3d, 5d, 7d)
            output_file: Output CSV file path
            
        Returns:
            Path to created CSV file
        """
        print(f"🔄 Training model for {symbol} ({training_period} training, {live_period} live)...")
        
        # Train model
        self.forecaster.train_on_recent_data(symbol, training_period)
        
        # Generate forecast
        forecast = self.forecaster.forecast(symbol, live_period)
        
        if 'error' in forecast:
            raise Exception(f"Forecast failed: {forecast['error']}")
        
        # Convert to visualization script format
        export_data = {
            'symbol': forecast['symbol'],
            'timestamp': forecast['timestamp'],
            'current_price': forecast['current_price'],
            '4hr_direction': forecast['4hr_direction'],
            '4hr_confidence': forecast['4hr_confidence'],
            'expected_move_pct': forecast['expected_move_pct'],
            'regime': forecast['regime'],
            'expected_accuracy': forecast['expected_accuracy'],
            'support': forecast['support'],
            'resistance': forecast['resistance'],
            'market_open': forecast.get('market_open', True),
            'last_close_date': forecast.get('last_close_date', ''),
            'recommendation': forecast['recommendation']
        }
        
        # Create DataFrame
        df = pd.DataFrame([export_data])
        
        # Set output file
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f'forecast_{symbol}_{timestamp}.csv'
        
        # Save to CSV
        df.to_csv(output_file, index=False)
        
        print(f"✅ Forecast exported to: {output_file}")
        return output_file
    
    def export_price_projections(self, symbol: str, days: int = 5, 
                               output_file: str = None) -> str:
        """
        Export price projections in CSV format.
        
        Args:
            symbol: Stock symbol
            days: Number of days to project
            output_file: Output CSV file path
            
        Returns:
            Path to created CSV file
        """
        # Generate forecast (reuse if already trained)
        forecast = self.forecaster.forecast(symbol)
        
        if 'error' in forecast:
            raise Exception(f"Forecast failed: {forecast['error']}")
        
        if 'price_projections' not in forecast:
            raise Exception("Price projections not available in forecast")
        
        projections = forecast['price_projections']
        
        # Convert to DataFrame
        df = pd.DataFrame({
            'Date': pd.to_datetime(projections['dates']),
            'Conservative': projections['conservative'],
            'Expected': projections['expected'],
            'Optimistic': projections['optimistic'],
            'Current_Price': projections['current_price'],
            'Direction': projections['direction'],
            'Confidence': projections['confidence']
        })
        
        # Set output file
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f'projections_{symbol}_{days}d_{timestamp}.csv'
        
        # Save to CSV
        df.to_csv(output_file, index=False)
        
        print(f"✅ Price projections exported to: {output_file}")
        return output_file
    
    def export_full_forecast_json(self, symbol: str, output_file: str = None) -> str:
        """
        Export complete forecast data in JSON format.
        
        Args:
            symbol: Stock symbol
            output_file: Output JSON file path
            
        Returns:
            Path to created JSON file
        """
        # Generate forecast
        forecast = self.forecaster.forecast(symbol)
        
        if 'error' in forecast:
            raise Exception(f"Forecast failed: {forecast['error']}")
        
        # Set output file
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f'forecast_full_{symbol}_{timestamp}.json'
        
        # Save to JSON
        with open(output_file, 'w') as f:
            json.dump(forecast, f, indent=2, default=str)
        
        print(f"✅ Full forecast exported to: {output_file}")
        return output_file
    
    def batch_export_multiple_symbols(self, symbols: list, export_format: str = 'visualization',
                                    output_dir: str = 'exports') -> list:
        """
        Export forecasts for multiple symbols.
        
        Args:
            symbols: List of stock symbols
            export_format: Export format ('visualization', 'projections', 'json')
            output_dir: Output directory
            
        Returns:
            List of created file paths
        """
        # Create output directory
        Path(output_dir).mkdir(exist_ok=True)
        
        exported_files = []
        
        for symbol in symbols:
            try:
                print(f"\n📊 Processing {symbol}...")
                
                if export_format == 'visualization':
                    output_file = f"{output_dir}/forecast_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                    file_path = self.export_for_visualization_script(symbol, output_file=output_file)
                elif export_format == 'projections':
                    output_file = f"{output_dir}/projections_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                    file_path = self.export_price_projections(symbol, output_file=output_file)
                elif export_format == 'json':
                    output_file = f"{output_dir}/forecast_full_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    file_path = self.export_full_forecast_json(symbol, output_file=output_file)
                else:
                    raise ValueError(f"Unknown export format: {export_format}")
                
                exported_files.append(file_path)
                print(f"✅ {symbol} completed")
                
            except Exception as e:
                print(f"❌ {symbol} failed: {e}")
                continue
        
        print(f"\n🎉 Batch export completed! {len(exported_files)} files created in {output_dir}/")
        return exported_files


def main():
    parser = argparse.ArgumentParser(
        description='Export forecasts from ML platform for external tools'
    )
    parser.add_argument(
        'symbol', type=str,
        help='Stock symbol (e.g., TSM, SPY, QQQ)'
    )
    parser.add_argument(
        '--format', type=str, choices=['visualization', 'projections', 'json'], 
        default='visualization',
        help='Export format (default: visualization)'
    )
    parser.add_argument(
        '--days', type=int, default=5,
        help='Number of days to project for projections format (default: 5)'
    )
    parser.add_argument(
        '--output', type=str, default=None,
        help='Output file path (auto-generated if not specified)'
    )
    parser.add_argument(
        '--training-period', type=str, choices=['1y', '2y', '3y'], 
        default='2y',
        help='Training period (default: 2y)'
    )
    parser.add_argument(
        '--live-period', type=str, choices=['1d', '3d', '5d', '7d'], 
        default='5d',
        help='Live data period (default: 5d)'
    )
    parser.add_argument(
        '--batch', type=str, nargs='+', default=None,
        help='Batch export multiple symbols'
    )
    
    args = parser.parse_args()
    
    try:
        exporter = ForecastExporter()
        
        if args.batch:
            # Batch export
            print(f"🔄 Starting batch export for {len(args.batch)} symbols...")
            exported_files = exporter.batch_export_multiple_symbols(
                args.batch, args.format
            )
            print(f"\n📁 Files created:")
            for file_path in exported_files:
                print(f"  • {file_path}")
        else:
            # Single export
            print(f"🔄 Exporting forecast for {args.symbol} in {args.format} format...")
            
            if args.format == 'visualization':
                file_path = exporter.export_for_visualization_script(
                    args.symbol, args.training_period, args.live_period, args.output
                )
            elif args.format == 'projections':
                file_path = exporter.export_price_projections(
                    args.symbol, args.days, args.output
                )
            elif args.format == 'json':
                file_path = exporter.export_full_forecast_json(
                    args.symbol, args.output
                )
            
            print(f"\n🎉 Export completed!")
            print(f"📁 File: {file_path}")
            
            # Show next steps
            if args.format == 'visualization':
                print(f"\n💡 Next steps:")
                print(f"   python visualize_forecast.py {file_path} --symbol {args.symbol}")
                print(f"   python visualize_forecast.py {file_path} --days {args.days} --symbol {args.symbol}")
    
    except Exception as e:
        print(f"❌ Export failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
