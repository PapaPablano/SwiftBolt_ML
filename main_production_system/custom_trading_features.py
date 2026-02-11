"""
Custom Trading Features Module
Provides advanced technical indicators and feature engineering for trading signals
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

class CustomTradingFeatures:
    """Custom trading features calculator"""
    
    def __init__(self):
        self.features = {}
    
    def calculate_all_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all custom trading features for a given DataFrame
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with additional feature columns
        """
        df_features = df.copy()
        
        # Ensure required columns exist
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in required_cols:
            if col not in df_features.columns:
                df_features[col] = df_features.get('close', df_features.get('Close', 100))
        
        try:
            # Basic technical indicators
            df_features = self._add_moving_averages(df_features)
            df_features = self._add_rsi(df_features)
            df_features = self._add_macd(df_features)
            df_features = self._add_bollinger_bands(df_features)
            df_features = self._add_volatility_features(df_features)
            df_features = self._add_momentum_features(df_features)
            df_features = self._add_volume_features(df_features)
            df_features = self._add_pattern_features(df_features)
            
        except Exception as e:
            print(f"Warning: Error calculating custom features: {e}")
            # Add minimal fallback features
            df_features = self._add_fallback_features(df_features)
        
        return df_features
    
    def _add_moving_averages(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add various moving averages"""
        df['SMA_5'] = df['Close'].rolling(window=5).mean()
        df['SMA_10'] = df['Close'].rolling(window=10).mean()
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        
        df['EMA_5'] = df['Close'].ewm(span=5).mean()
        df['EMA_10'] = df['Close'].ewm(span=10).mean()
        df['EMA_20'] = df['Close'].ewm(span=20).mean()
        
        # Price relative to moving averages
        df['Price_vs_SMA20'] = df['Close'] / df['SMA_20'] - 1
        df['Price_vs_SMA50'] = df['Close'] / df['SMA_50'] - 1
        
        return df
    
    def _add_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """Add RSI indicator"""
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        df['RSI_Overbought'] = (df['RSI'] > 70).astype(int)
        df['RSI_Oversold'] = (df['RSI'] < 30).astype(int)
        return df
    
    def _add_macd(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add MACD indicator"""
        ema_12 = df['Close'].ewm(span=12).mean()
        ema_26 = df['Close'].ewm(span=26).mean()
        df['MACD'] = ema_12 - ema_26
        df['MACD_Signal'] = df['MACD'].ewm(span=9).mean()
        df['MACD_Histogram'] = df['MACD'] - df['MACD_Signal']
        df['MACD_Bullish'] = (df['MACD'] > df['MACD_Signal']).astype(int)
        return df
    
    def _add_bollinger_bands(self, df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
        """Add Bollinger Bands"""
        sma = df['Close'].rolling(window=period).mean()
        std = df['Close'].rolling(window=period).std()
        df['BB_Upper'] = sma + (std * 2)
        df['BB_Lower'] = sma - (std * 2)
        df['BB_Middle'] = sma
        df['BB_Width'] = df['BB_Upper'] - df['BB_Lower']
        df['BB_Position'] = (df['Close'] - df['BB_Lower']) / (df['BB_Upper'] - df['BB_Lower'])
        return df
    
    def _add_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add volatility-based features"""
        df['True_Range'] = np.maximum(
            df['High'] - df['Low'],
            np.maximum(
                abs(df['High'] - df['Close'].shift(1)),
                abs(df['Low'] - df['Close'].shift(1))
            )
        )
        df['ATR'] = df['True_Range'].rolling(window=14).mean()
        df['Volatility_5'] = df['Close'].rolling(window=5).std()
        df['Volatility_20'] = df['Close'].rolling(window=20).std()
        df['Volatility_Ratio'] = df['Volatility_5'] / df['Volatility_20']
        return df
    
    def _add_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add momentum indicators"""
        # Rate of Change
        df['ROC_5'] = (df['Close'] / df['Close'].shift(5) - 1) * 100
        df['ROC_10'] = (df['Close'] / df['Close'].shift(10) - 1) * 100
        
        # Momentum
        df['Momentum_5'] = df['Close'] - df['Close'].shift(5)
        df['Momentum_10'] = df['Close'] - df['Close'].shift(10)
        
        # Williams %R
        high_14 = df['High'].rolling(window=14).max()
        low_14 = df['Low'].rolling(window=14).min()
        df['Williams_R'] = -100 * (high_14 - df['Close']) / (high_14 - low_14)
        
        return df
    
    def _add_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add volume-based features"""
        df['Volume_SMA'] = df['Volume'].rolling(window=20).mean()
        df['Volume_Ratio'] = df['Volume'] / df['Volume_SMA']
        df['Price_Volume'] = df['Close'] * df['Volume']
        df['OBV'] = (df['Volume'] * np.sign(df['Close'].diff())).cumsum()
        return df
    
    def _add_pattern_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add candlestick pattern features"""
        # Doji pattern
        body_size = abs(df['Close'] - df['Open'])
        candle_range = df['High'] - df['Low']
        df['Doji'] = (body_size / candle_range < 0.1).astype(int)
        
        # Hammer pattern
        lower_shadow = df[['Open', 'Close']].min(axis=1) - df['Low']
        upper_shadow = df['High'] - df[['Open', 'Close']].max(axis=1)
        df['Hammer'] = ((lower_shadow > 2 * body_size) & (upper_shadow < body_size)).astype(int)
        
        # Engulfing patterns
        df['Bullish_Engulfing'] = (
            (df['Close'] > df['Open']) &  # Current candle is bullish
            (df['Close'].shift(1) < df['Open'].shift(1)) &  # Previous candle is bearish
            (df['Open'] < df['Close'].shift(1)) &  # Current open below previous close
            (df['Close'] > df['Open'].shift(1))  # Current close above previous open
        ).astype(int)
        
        return df
    
    def _add_fallback_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add minimal fallback features if main calculation fails"""
        df['Returns'] = df['Close'].pct_change()
        df['Log_Returns'] = np.log(df['Close'] / df['Close'].shift(1))
        df['Price_Change'] = df['Close'].diff()
        df['High_Low_Ratio'] = df['High'] / df['Low']
        df['OHLC_Avg'] = (df['Open'] + df['High'] + df['Low'] + df['Close']) / 4
        return df
    
    def get_feature_importance(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate feature importance scores
        
        Args:
            df: DataFrame with features
            
        Returns:
            Dictionary of feature importance scores
        """
        feature_cols = [col for col in df.columns if col not in ['Open', 'High', 'Low', 'Close', 'Volume', 'Date', 'Timestamp']]
        
        importance = {}
        for col in feature_cols:
            if col in df.columns:
                # Simple correlation with price changes as importance metric
                try:
                    corr = abs(df[col].corr(df['Close'].pct_change()))
                    importance[col] = corr if not np.isnan(corr) else 0.0
                except:
                    importance[col] = 0.0
        
        return importance
    
    def select_top_features(self, df: pd.DataFrame, n_features: int = 20) -> List[str]:
        """
        Select top N most important features
        
        Args:
            df: DataFrame with features
            n_features: Number of top features to select
            
        Returns:
            List of top feature names
        """
        importance = self.get_feature_importance(df)
        sorted_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)
        return [feature[0] for feature in sorted_features[:n_features]]

# Global instance for easy access
custom_features = CustomTradingFeatures()

# Convenience functions
def add_custom_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add all custom trading features to a DataFrame
    
    Args:
        df: DataFrame with OHLCV data
        
    Returns:
        DataFrame with additional features
    """
    return custom_features.calculate_all_features(df)

def get_feature_importance(df: pd.DataFrame) -> Dict[str, float]:
    """Get feature importance scores"""
    return custom_features.get_feature_importance(df)

def select_features(df: pd.DataFrame, n_features: int = 20) -> List[str]:
    """Select top N features"""
    return custom_features.select_top_features(df, n_features)