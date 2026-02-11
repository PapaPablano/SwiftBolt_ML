#!/usr/bin/env python3
"""
Multi-Timeframe Forecaster - Core Engine

Generates directional forecasts using your wave analogy strategy with
regime-aware confidence scoring.

Usage:
    from main_production_system.forecasting_platform.multi_timeframe_forecaster import Forecaster

    forecaster = Forecaster()
    forecast = forecaster.forecast('TSM')
    print(forecast)
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import pickle
import os
import sys
from typing import Dict, List, Tuple
import warnings
import pytz
warnings.filterwarnings('ignore')

# Add parent directories to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(parent_dir)  # This should be the project root
sys.path.insert(0, root_dir)

# Also add the current directory to path for relative imports
sys.path.insert(0, current_dir)

from custom_trading_features import create_custom_trading_features
from custom_trading_ensemble import CustomTradingEnsemble
from regime_adaptive_validator import MarketRegimeDetector


class Forecaster:
    """
    Multi-timeframe directional forecaster with regime awareness.
    """

    def __init__(self, model_dir: str = None):
        """
        Initialize forecaster.

        Args:
            model_dir: Directory containing trained models
        """
        if model_dir is None:
            # Use main production system models directory
            self.model_dir = os.path.join(parent_dir, 'models')
        else:
            self.model_dir = model_dir
            
        self.regime_detector = MarketRegimeDetector()
        self.ensemble = None
        self.trained = False

    def is_market_hours(self, symbol: str = None) -> bool:
        """
        Check if current time is during market hours.
        
        Args:
            symbol: Stock symbol (for exchange-specific hours)
            
        Returns:
            True if market is open, False otherwise
        """
        # Get current time in Eastern timezone (US market)
        eastern = pytz.timezone('US/Eastern')
        now = datetime.now(eastern)
        
        # Market hours: 9:30 AM - 4:00 PM ET, Monday-Friday
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        
        # Check if it's a weekday (Monday=0, Sunday=6)
        is_weekday = now.weekday() < 5
        
        # Check if current time is within market hours
        is_market_time = market_open <= now <= market_close
        
        return is_weekday and is_market_time

    def get_last_market_close_date(self) -> str:
        """
        Get the date string for the most recent market close.
        
        Returns:
            Date string in YYYY-MM-DD format
        """
        eastern = pytz.timezone('US/Eastern')
        now = datetime.now(eastern)
        
        # If it's weekend, go back to Friday
        if now.weekday() == 5:  # Saturday
            days_back = 1
        elif now.weekday() == 6:  # Sunday
            days_back = 2
        else:
            # Weekday - if before market open, use previous day
            market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
            if now < market_open:
                days_back = 1
            else:
                days_back = 0
        
        last_close = now - timedelta(days=days_back)
        return last_close.strftime('%Y-%m-%d')

    def download_live_data(self, symbol: str, period: str = '5d') -> Dict:
        """
        Download recent data for forecasting.
        Handles market hours - defaults to most recent close when outside market hours.

        Args:
            symbol: Stock symbol
            period: Recent data period (5d = enough for features)

        Returns:
            Dictionary with multi-timeframe data
        """
        data = {}
        
        # Check if market is open
        market_open = self.is_market_hours(symbol)
        last_close_date = self.get_last_market_close_date()
        
        print(f"Market Status: {'OPEN' if market_open else 'CLOSED'}")
        if not market_open:
            print(f"Using most recent market close: {last_close_date}")

        timeframes = {
            '10min': None,
            '1hr': '1h',
            '4hr': None,
            'daily': '1d',
            'weekly': '1wk'
        }

        # Download base timeframes
        for name, interval in timeframes.items():
            if interval is not None:
                try:
                    df = yf.download(symbol, period=period, interval=interval, progress=False)
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0).str.lower()
                    else:
                        df.columns = df.columns.str.lower()
                    
                    # If market is closed, ensure we have data up to last close
                    if not market_open and not df.empty:
                        # Filter to include only data up to last market close
                        df = df[df.index.date <= pd.to_datetime(last_close_date).date()]
                    
                    data[name] = df
                except Exception as e:
                    print(f"Error downloading {name}: {e}")
                    return None

        # Resample to create missing timeframes
        try:
            df_1hr = data['1hr']

            # 15min (simulates 10min)
            df_10min = pd.DataFrame()
            df_10min['open'] = df_1hr['open'].resample('15min').first()
            df_10min['high'] = df_1hr['high'].resample('15min').max()
            df_10min['low'] = df_1hr['low'].resample('15min').min()
            df_10min['close'] = df_1hr['close'].resample('15min').last()
            df_10min['volume'] = df_1hr['volume'].resample('15min').sum()
            data['10min'] = df_10min.dropna()

            # 4hr
            df_4hr = pd.DataFrame()
            df_4hr['open'] = df_1hr['open'].resample('4h').first()
            df_4hr['high'] = df_1hr['high'].resample('4h').max()
            df_4hr['low'] = df_1hr['low'].resample('4h').min()
            df_4hr['close'] = df_1hr['close'].resample('4h').last()
            df_4hr['volume'] = df_1hr['volume'].resample('4h').sum()
            data['4hr'] = df_4hr.dropna()
        except Exception as e:
            print(f"Error resampling: {e}")
            return None

        return data

    def train_on_recent_data(self, symbol: str, period: str = '2y'):
        """
        Train ensemble on recent historical data.

        Args:
            symbol: Stock symbol
            period: Training data period
        """
        print(f"Training forecaster on {symbol} ({period} data)...")

        # Download training data
        print("  Downloading data...")
        data = {}

        timeframes = {
            '10min': None,
            '1hr': '1h',
            '4hr': None,
            'daily': '1d',
            'weekly': '1wk'
        }

        for name, interval in timeframes.items():
            if interval is not None:
                df = yf.download(symbol, period=period, interval=interval, progress=False)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0).str.lower()
                else:
                    df.columns = df.columns.str.lower()
                data[name] = df

        # Resample
        df_1hr = data['1hr']

        df_10min = pd.DataFrame()
        df_10min['open'] = df_1hr['open'].resample('15min').first()
        df_10min['high'] = df_1hr['high'].resample('15min').max()
        df_10min['low'] = df_1hr['low'].resample('15min').min()
        df_10min['close'] = df_1hr['close'].resample('15min').last()
        df_10min['volume'] = df_1hr['volume'].resample('15min').sum()
        data['10min'] = df_10min.dropna()

        df_4hr = pd.DataFrame()
        df_4hr['open'] = df_1hr['open'].resample('4h').first()
        df_4hr['high'] = df_1hr['high'].resample('4h').max()
        df_4hr['low'] = df_1hr['low'].resample('4h').min()
        df_4hr['close'] = df_1hr['close'].resample('4h').last()
        df_4hr['volume'] = df_1hr['volume'].resample('4h').sum()
        data['4hr'] = df_4hr.dropna()

        # Detect regime for parameter selection
        regime = self.regime_detector.detect_regime(data['4hr'])
        regime_params = self.regime_detector.get_regime_params(regime)

        print(f"  Detected regime: {regime}")
        print(f"  Using regime-specific parameters")

        # Initialize and train ensemble
        self.ensemble = CustomTradingEnsemble(xgb_params=regime_params)

        print("  Training ensemble...")
        self.ensemble.train(
            df_10min=data['10min'],
            df_1hr=data['1hr'],
            df_4hr=data['4hr'],
            df_daily=data['daily'],
            df_weekly=data['weekly']
        )

        self.trained = True
        print("  ✅ Training complete!")

    def forecast(self, symbol: str, live_period: str = '5d') -> Dict:
        """
        Generate multi-horizon forecast.

        Args:
            symbol: Stock symbol
            live_period: Recent data period for forecasting (default: '5d')

        Returns:
            Dictionary with forecast details
        """
        if not self.trained:
            print("Model not trained. Training now...")
            self.train_on_recent_data(symbol)

        # Download recent data
        data = self.download_live_data(symbol, live_period)
        if data is None:
            return {'error': 'Failed to download data'}

        # Check market status
        market_open = self.is_market_hours(symbol)
        last_close_date = self.get_last_market_close_date()

        # Detect current regime
        regime = self.regime_detector.detect_regime(data['4hr'])

        # Generate predictions
        try:
            predictions = self.ensemble.predict(
                df_10min=data['10min'],
                df_1hr=data['1hr'],
                df_4hr=data['4hr'],
                df_daily=data['daily'],
                df_weekly=data['weekly']
            )

            # Get latest prediction
            latest = predictions.iloc[-1]

            # Calculate confidence
            base_prob = latest['probability']

            # Adjust confidence based on regime
            if regime in ['TRENDING_UP', 'TRENDING_DOWN']:
                regime_boost = 0.15  # High confidence in trending
                expected_accuracy = 0.54
            elif regime == 'RANGING':
                regime_boost = -0.10  # Lower confidence in ranging
                expected_accuracy = 0.44
            else:  # HIGH_VOL
                regime_boost = -0.20  # Very low confidence
                expected_accuracy = 0.40

            # Check timeframe alignment
            # (This is simplified - could enhance)
            alignment_boost = 0.10 if base_prob > 0.60 or base_prob < 0.40 else 0

            confidence = min(100, max(0, 
                (base_prob * 100) + (regime_boost * 100) + (alignment_boost * 100)
            ))

            # Get current price and calculate key levels
            current_price = data['4hr']['close'].iloc[-1]

            # SuperTrend support (simplified - using recent low)
            support = data['4hr']['low'].iloc[-20:].min()

            # Resistance (simplified - using recent high)
            resistance = data['4hr']['high'].iloc[-20:].max()

            # Expected move (based on average true range)
            atr = (data['4hr']['high'] - data['4hr']['low']).iloc[-14:].mean()
            expected_move_pct = (atr / current_price) * 100

            # Build forecast dictionary
            forecast = {
                'symbol': symbol,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'regime': regime,
                'expected_accuracy': expected_accuracy,

                # 4hr forecast (primary)
                '4hr_direction': 'UP' if latest['prediction'] == 1 else 'DOWN',
                '4hr_probability': base_prob,
                '4hr_confidence': confidence,

                # Current levels
                'current_price': current_price,
                'support': support,
                'resistance': resistance,
                'expected_move_pct': expected_move_pct,

                # Regime info
                'regime_confidence': 'HIGH' if regime in ['TRENDING_UP', 'TRENDING_DOWN'] else 'LOW',
                'recommendation': self._generate_recommendation(regime, latest['prediction'], confidence),
                
                # Market status
                'market_open': market_open,
                'last_close_date': last_close_date,
                
                # Price projections for visualization
                'price_projections': self._generate_price_projections(
                    current_price, 'UP' if latest['prediction'] == 1 else 'DOWN', confidence, expected_move_pct
                )
            }

            return forecast

        except Exception as e:
            return {'error': f'Forecasting failed: {str(e)}'}

    def _generate_recommendation(self, regime: str, prediction: int, confidence: float) -> str:
        """Generate trading recommendation."""
        if regime in ['TRENDING_UP', 'TRENDING_DOWN'] and confidence > 70:
            if prediction == 1:
                return "HIGH CONFIDENCE - Consider long position"
            else:
                return "HIGH CONFIDENCE - Consider short/exit"
        elif regime == 'RANGING':
            return "LOW CONFIDENCE - Wait for clearer trend"
        else:
            return "VERY LOW CONFIDENCE - Sit out or reduce exposure"

    def _generate_price_projections(self, current_price: float, direction: str, 
                                  confidence: float, expected_move_pct: float, days: int = 5) -> Dict:
        """Generate price projections for visualization."""
        # Calculate daily move based on confidence
        move_multiplier = confidence / 100.0
        
        if direction == "UP":
            daily_move_pct = expected_move_pct * move_multiplier * 1.5
        else:
            daily_move_pct = -expected_move_pct * move_multiplier * 1.5
        
        projections = {
            'dates': [],
            'conservative': [],
            'expected': [],
            'optimistic': [],
            'current_price': current_price,
            'direction': direction,
            'confidence': confidence
        }
        
        start_date = datetime.now()
        
        for day in range(days + 1):
            future_date = start_date + timedelta(days=day)
            projections['dates'].append(future_date.isoformat())
            
            # Expected case
            expected_price = current_price * (1 + daily_move_pct/100) ** day
            projections['expected'].append(expected_price)
            
            # Optimistic case (1.5x move)
            optimistic_price = current_price * (1 + (daily_move_pct * 1.5)/100) ** day
            projections['optimistic'].append(optimistic_price)
            
            # Conservative case (0.5x move)
            conservative_price = current_price * (1 + (daily_move_pct * 0.5)/100) ** day
            projections['conservative'].append(conservative_price)
        
        return projections


if __name__ == "__main__":
    # Example usage
    forecaster = Forecaster()

    print("Generating forecast for TSM...")
    forecast = forecaster.forecast('TSM')

    if 'error' not in forecast:
        print("\nForecast generated successfully!")
        print(f"Direction: {forecast['4hr_direction']}")
        print(f"Confidence: {forecast['4hr_confidence']:.1f}%")
        print(f"Regime: {forecast['regime']}")
    else:
        print(f"Error: {forecast['error']}")
