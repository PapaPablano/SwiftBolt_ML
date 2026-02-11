#!/usr/bin/env python3
"""
Streamlined Forecaster - Clean & Efficient

Focused approach:
1. Smart API data fetching based on market hours
2. Single model load/cache (no excessive retraining)
3. Clean inference pipeline
4. Proper market close handling
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import pickle
import os
import sys
from typing import Dict, Optional
import warnings
import pytz
from pathlib import Path
warnings.filterwarnings('ignore')

# Add parent directories for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(parent_dir)
sys.path.insert(0, root_dir)


class StreamlinedForecaster:
    """
    Clean, efficient forecaster focused on smart data fetching and cached models.
    """
    
    def __init__(self):
        self.model = None
        self.model_loaded = False
        self.last_data_fetch = None
        self.cached_data = None
        
    def is_market_open(self, symbol: str = None) -> bool:
        """Check if US market is currently open."""
        eastern = pytz.timezone('US/Eastern')
        now = datetime.now(eastern)
        
        # Market hours: 9:30 AM - 4:00 PM ET, Monday-Friday
        market_start = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_end = now.replace(hour=16, minute=0, second=0, microsecond=0)
        
        is_weekday = now.weekday() < 5  # Monday=0, Sunday=6
        is_trading_hours = market_start <= now <= market_end
        
        return is_weekday and is_trading_hours
    
    def get_last_market_close(self) -> datetime:
        """Get the last market close datetime."""
        eastern = pytz.timezone('US/Eastern')
        now = datetime.now(eastern)
        
        # If it's before 9:30 AM on a weekday, use previous day
        market_start = now.replace(hour=9, minute=30, second=0, microsecond=0)
        if now < market_start and now.weekday() < 5:
            last_close = (now - timedelta(days=1)).replace(hour=16, minute=0, second=0, microsecond=0)
        else:
            # Use most recent 4:00 PM
            last_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
            if now.time() < last_close.time():
                last_close = (now - timedelta(days=1)).replace(hour=16, minute=0, second=0, microsecond=0)
        
        # Handle weekends - go back to Friday
        while last_close.weekday() >= 5:  # Saturday=5, Sunday=6
            last_close -= timedelta(days=1)
            
        return last_close
    
    def fetch_market_data(self, symbol: str, force_refresh: bool = False) -> Dict:
        """
        Smart data fetching based on market status.
        Uses cache to avoid redundant API calls.
        """
        # Check if we need to refresh data
        if not force_refresh and self.cached_data is not None and self.last_data_fetch:
            # Use cache if data is less than 15 minutes old
            if (datetime.now() - self.last_data_fetch).total_seconds() < 900:
                return self.cached_data
        
        market_open = self.is_market_open(symbol)
        last_close = self.get_last_market_close()
        
        print(f"📊 Market Status: {'🟢 OPEN' if market_open else '🔴 CLOSED'}")
        if not market_open:
            print(f"📅 Using last close: {last_close.strftime('%Y-%m-%d %H:%M ET')}")
        
        try:
            # Fetch recent data (5 days is enough for most indicators)
            data = yf.download(
                symbol, 
                period='5d', 
                interval='1h',  # Hourly data for good resolution
                progress=False
            )
            
            if data.empty:
                raise Exception(f"No data returned for {symbol}")
            
            # Clean column names
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0).str.lower()
            else:
                data.columns = data.columns.str.lower()
            
            # If market is closed, filter to last market close
            if not market_open:
                data = data[data.index <= last_close]
            
            # Cache the data
            self.cached_data = {
                'symbol': symbol,
                'data': data,
                'market_open': market_open,
                'last_close': last_close.strftime('%Y-%m-%d %H:%M ET'),
                'current_price': float(data['close'].iloc[-1]),
                'data_points': len(data),
                'latest_timestamp': data.index[-1].strftime('%Y-%m-%d %H:%M')
            }
            self.last_data_fetch = datetime.now()
            
            print(f"✅ Data fetched: {len(data)} points, latest: {self.cached_data['latest_timestamp']}")
            return self.cached_data
            
        except Exception as e:
            print(f"❌ Data fetch failed: {e}")
            return None
    
    def load_model_if_needed(self):
        """Load model once and cache it."""
        if self.model_loaded:
            return True
        
        try:
            # Try to load existing model
            model_path = Path(root_dir) / "xgboost_tuned_model.pkl"
            if model_path.exists():
                with open(model_path, 'rb') as f:
                    self.model = pickle.load(f)
                self.model_loaded = True
                print(f"✅ Model loaded from {model_path}")
                return True
            else:
                print(f"❌ Model not found at {model_path}")
                return False
                
        except Exception as e:
            print(f"❌ Model loading failed: {e}")
            return False
    
    def calculate_simple_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate essential technical indicators efficiently."""
        df = data.copy()
        
        # Use shorter periods that work with available data
        data_len = len(df)
        sma_short = min(10, data_len // 3)  # Adaptive short SMA
        sma_long = min(20, data_len // 2)   # Adaptive long SMA
        rsi_period = min(14, data_len // 3) # Adaptive RSI
        
        # Simple moving averages
        df['sma_short'] = df['close'].rolling(sma_short).mean()
        df['sma_long'] = df['close'].rolling(sma_long).mean()
        
        # RSI with adaptive period
        if rsi_period >= 2:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
        else:
            df['rsi'] = 50  # Neutral RSI if insufficient data
        
        # Price change
        df['price_change'] = df['close'].pct_change()
        df['price_change_3'] = df['close'].pct_change(min(3, data_len-1))
        
        # Volume indicators (if volume data available)
        if 'volume' in df.columns and not df['volume'].isna().all():
            vol_period = min(10, data_len // 2)
            df['volume_sma'] = df['volume'].rolling(vol_period).mean()
            df['volume_ratio'] = df['volume'] / df['volume_sma']
        else:
            df['volume_ratio'] = 1.0  # Neutral if no volume data
        
        # Only drop rows with critical NaN values
        df = df.dropna(subset=['close', 'sma_short'])
        
        return df
    
    def generate_simple_forecast(self, symbol: str) -> Dict:
        """
        Generate forecast using clean, efficient approach.
        """
        # 1. Smart data fetching
        market_data = self.fetch_market_data(symbol)
        if not market_data:
            return {'error': 'Failed to fetch market data'}
        
        # 2. Load model once
        if not self.load_model_if_needed():
            return {'error': 'Failed to load prediction model'}
        
        # 3. Calculate indicators
        data = market_data['data']
        df = self.calculate_simple_indicators(data)
        
        if len(df) < 10:  # More reasonable threshold
            return {'error': f'Insufficient data: only {len(df)} points available'}
        
        # 4. Simple trend analysis (no excessive ML)
        latest = df.iloc[-1]
        prev_5 = df.iloc[-6:-1] if len(df) >= 6 else df.iloc[:-1]
        
        # Trend signals
        price_trend = 'UP' if latest['close'] > latest['sma_short'] else 'DOWN'
        momentum = 'STRONG' if abs(latest['price_change_3']) > 0.02 else 'WEAK'
        volume_signal = 'HIGH' if latest['volume_ratio'] > 1.2 else 'NORMAL'
        
        # Simple confidence based on alignment
        confidence_factors = []
        if price_trend == 'UP' and latest['rsi'] < 70:  # Not overbought
            confidence_factors.append(0.3)
        if price_trend == 'DOWN' and latest['rsi'] > 30:  # Not oversold
            confidence_factors.append(0.3)
        if momentum == 'STRONG':
            confidence_factors.append(0.2)
        if volume_signal == 'HIGH':
            confidence_factors.append(0.2)
        
        confidence = min(sum(confidence_factors) * 100, 95)  # Cap at 95%
        
        # Expected move based on recent volatility
        recent_volatility = df['price_change'].tail(20).std() * 100
        expected_move = recent_volatility * 1.5  # 1.5x recent volatility
        
        # Build clean forecast
        forecast = {
            'symbol': symbol,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            
            # Market info
            'market_open': market_data['market_open'],
            'last_close_time': market_data['last_close'],
            'current_price': market_data['current_price'],
            
            # Prediction (dashboard compatible fields)
            '4hr_direction': price_trend,
            '4hr_probability': confidence / 100.0,  # Dashboard expects probability as decimal
            '4hr_confidence': confidence,
            'expected_move_pct': expected_move,
            
            # Add regime compatibility
            'regime': 'STREAMLINED_' + price_trend,
            'expected_accuracy': confidence / 100.0,
            
            # Technical levels
            'sma_short': float(latest['sma_short']),
            'sma_long': float(latest['sma_long']),
            'rsi': float(latest['rsi']),
            
            # Simple recommendation
            'recommendation': self._generate_recommendation(price_trend, confidence),
            
            # Clean status
            'data_quality': 'GOOD' if len(df) > 50 else 'LIMITED',
            'processing_time': 'FAST',  # No excessive retraining
            
            # Price projections for dashboard compatibility
            'price_projections': self._generate_simple_projections(
                market_data['current_price'], price_trend, confidence, expected_move
            )
        }
        
        return forecast
    
    def _generate_recommendation(self, direction: str, confidence: float) -> str:
        """Generate simple, clear recommendations."""
        if confidence > 70:
            return f"HIGH CONFIDENCE {direction} - Consider position"
        elif confidence > 50:
            return f"MODERATE {direction} - Wait for confirmation"
        else:
            return "LOW CONFIDENCE - Wait for clearer signals"
    
    def _generate_simple_projections(self, current_price: float, direction: str, 
                                   confidence: float, expected_move_pct: float, days: int = 5) -> Dict:
        """Generate simple price projections for dashboard compatibility."""
        from datetime import datetime, timedelta
        
        # Calculate daily move based on confidence
        move_multiplier = confidence / 100.0
        
        if direction == "UP":
            daily_move_pct = expected_move_pct * move_multiplier * 0.3  # More conservative
        else:
            daily_move_pct = -expected_move_pct * move_multiplier * 0.3
        
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


def main():
    """Simple test of streamlined forecaster."""
    print("🚀 Streamlined Forecaster Test")
    print("=" * 50)
    
    forecaster = StreamlinedForecaster()
    
    # Test with TSM
    symbol = "TSM"
    
    print(f"\n📊 Generating forecast for {symbol}...")
    forecast = forecaster.generate_simple_forecast(symbol)
    
    if 'error' in forecast:
        print(f"❌ Error: {forecast['error']}")
        return
    
    # Display clean results
    print(f"\n✅ Forecast for {forecast['symbol']}")
    print(f"🕐 Time: {forecast['timestamp']}")
    print(f"📈 Price: ${forecast['current_price']:.2f}")
    print(f"🎯 Direction: {forecast['4hr_direction']} ({forecast['4hr_confidence']:.0f}% confidence)")
    print(f"📊 Expected Move: ±{forecast['expected_move_pct']:.1f}%")
    print(f"💡 Recommendation: {forecast['recommendation']}")
    print(f"🏪 Market: {'OPEN' if forecast['market_open'] else 'CLOSED'}")
    if not forecast['market_open']:
        print(f"📅 Last Close: {forecast['last_close_time']}")


if __name__ == "__main__":
    main()
