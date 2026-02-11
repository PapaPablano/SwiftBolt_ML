#!/usr/bin/env python3
"""
Legacy Feature Engineer - Production System
Handles feature engineering to match the trained XGBoost model.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging

class LegacyFeatureEngineer:
    """
    Feature engineer that matches the trained XGBoost model expectations.
    Creates features with the exact names expected by the trained model.
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {
            'kdj_period': 9,
            'k_smooth': 3,
            'd_smooth': 3,
            'rsi_period': 14,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'bollinger_period': 20,
            'bollinger_std': 2
        }
        self.logger = logging.getLogger(__name__)
    
    def create_features(self, df: pd.DataFrame, include_kdj: bool = True) -> pd.DataFrame:
        """
        Create features that match the trained model expectations.
        """
        features = pd.DataFrame(index=df.index)
        
        # Basic OHLC features (no lag needed for prediction)
        features['open'] = df['open']
        features['high'] = df['high']
        features['low'] = df['low']
        features['close'] = df['close']
        
        # Volume (if available)
        if 'volume' in df.columns:
            features['volume'] = df['volume']
        else:
            features['volume'] = 1000000  # Default volume
        
        # Lag features
        features['close_lag_1'] = df['close'].shift(1)
        features['close_lag_2'] = df['close'].shift(2)
        features['close_lag_5'] = df['close'].shift(5)
        features['close_lag_10'] = df['close'].shift(10)
        
        # Return features
        features['close_return_1'] = df['close'].pct_change(1)
        features['close_return_5'] = df['close'].pct_change(5)
        features['close_return_10'] = df['close'].pct_change(10)
        
        # Moving averages
        features['close_ma_5'] = df['close'].rolling(5).mean()
        features['close_ma_10'] = df['close'].rolling(10).mean()
        features['close_ma_20'] = df['close'].rolling(20).mean()
        
        # Standard deviations
        features['close_std_5'] = df['close'].rolling(5).std()
        features['close_std_10'] = df['close'].rolling(10).std()
        features['close_std_20'] = df['close'].rolling(20).std()
        
        # Volume moving averages
        features['volume_ma_5'] = features['volume'].rolling(5).mean()
        features['volume_ma_10'] = features['volume'].rolling(10).mean()
        features['volume_ma_20'] = features['volume'].rolling(20).mean()
        
        # RSI
        features['close_rsi_14'] = self._calculate_rsi(df['close'], self.config['rsi_period'])
        
        # KDJ indicators
        if include_kdj:
            kdj_features = self._calculate_kdj_indicators(df)
            features['close_kdj_k'] = kdj_features['kdj_k']
            features['close_kdj_d'] = kdj_features['kdj_d']
            features['close_kdj_j'] = kdj_features['kdj_j']
            features['close_j_minus_d'] = kdj_features['j_minus_d']
            features['close_j_position_relative_d'] = kdj_features['j_position_relative_d']
        
        # MACD
        macd_features = self._calculate_macd(df['close'])
        features['close_macd'] = macd_features['macd']
        features['close_macd_signal'] = macd_features['signal']
        
        # Bollinger Bands
        bb_features = self._calculate_bollinger_bands(df['close'])
        features['close_bollinger_upper'] = bb_features['upper']
        features['close_bollinger_lower'] = bb_features['lower']
        
        # Fill NaN values with forward fill, then backward fill
        features = features.ffill().bfill()
        
        # Remove rows with any remaining NaN values
        features_clean = features.dropna()
        
        # Reorder columns to match the trained model exactly
        expected_order = [
            'open', 'high', 'low', 'close', 'volume', 'close_lag_1', 'close_lag_2',
            'close_lag_5', 'close_lag_10', 'close_return_1', 'close_return_5',
            'close_return_10', 'close_ma_5', 'close_std_5', 'volume_ma_5',
            'close_ma_10', 'close_std_10', 'volume_ma_10', 'close_ma_20',
            'close_std_20', 'volume_ma_20', 'close_rsi_14', 'close_kdj_k',
            'close_kdj_d', 'close_kdj_j', 'close_j_minus_d',
            'close_j_position_relative_d', 'close_macd', 'close_macd_signal',
            'close_bollinger_upper', 'close_bollinger_lower'
        ]
        
        # Reorder columns to match expected order
        features_ordered = features_clean[expected_order]
        
        self.logger.info(f"Created {len(features_ordered.columns)} features, {len(features_ordered)} valid samples")
        
        return features_ordered
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_kdj_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate KDJ (Stochastic) indicators."""
        kdj_period = self.config['kdj_period']
        k_smooth = self.config['k_smooth']
        d_smooth = self.config['d_smooth']
        
        # Calculate RSV (Raw Stochastic Value)
        low_min = df['low'].rolling(window=kdj_period).min()
        high_max = df['high'].rolling(window=kdj_period).max()
        rsv = 100 * (df['close'] - low_min) / (high_max - low_min)
        
        # Calculate K, D, J lines
        k_line = rsv.ewm(span=k_smooth).mean()
        d_line = k_line.ewm(span=d_smooth).mean()
        j_line = 3 * k_line - 2 * d_line
        
        # Create KDJ features DataFrame
        kdj_features = pd.DataFrame(index=df.index)
        kdj_features['kdj_k'] = k_line
        kdj_features['kdj_d'] = d_line
        kdj_features['kdj_j'] = j_line
        kdj_features['j_minus_d'] = j_line - d_line
        kdj_features['j_position_relative_d'] = np.where(j_line > d_line, 1, 0)
        
        return kdj_features
    
    def _calculate_macd(self, prices: pd.Series) -> pd.DataFrame:
        """Calculate MACD indicator."""
        fast_period = self.config['macd_fast']
        slow_period = self.config['macd_slow']
        signal_period = self.config['macd_signal']
        
        ema_fast = prices.ewm(span=fast_period).mean()
        ema_slow = prices.ewm(span=slow_period).mean()
        macd = ema_fast - ema_slow
        signal = macd.ewm(span=signal_period).mean()
        
        macd_features = pd.DataFrame(index=prices.index)
        macd_features['macd'] = macd
        macd_features['signal'] = signal
        
        return macd_features
    
    def _calculate_bollinger_bands(self, prices: pd.Series) -> pd.DataFrame:
        """Calculate Bollinger Bands."""
        period = self.config['bollinger_period']
        std_mult = self.config['bollinger_std']
        
        ma = prices.rolling(period).mean()
        std = prices.rolling(period).std()
        
        bb_features = pd.DataFrame(index=prices.index)
        bb_features['upper'] = ma + (std * std_mult)
        bb_features['lower'] = ma - (std * std_mult)
        
        return bb_features
    
    def validate_features(self, features: pd.DataFrame) -> Dict:
        """Validate feature quality and statistics."""
        validation_results = {
            'total_features': len(features.columns),
            'total_samples': len(features),
            'missing_values': dict(features.isnull().sum()),
            'infinite_values': dict(features.isin([np.inf, -np.inf]).sum()),
            'feature_ranges': {},
            'kdj_features': [],
            'warnings': []
        }
        
        # Check for KDJ features
        kdj_cols = [col for col in features.columns if 'kdj' in col.lower()]
        validation_results['kdj_features'] = kdj_cols
        
        # Feature ranges
        for col in features.columns:
            if features[col].dtype in ['float64', 'int64']:
                validation_results['feature_ranges'][col] = {
                    'min': float(features[col].min()),
                    'max': float(features[col].max()),
                    'mean': float(features[col].mean()),
                    'std': float(features[col].std())
                }
        
        # Validation warnings
        if features.isnull().sum().sum() > 0:
            validation_results['warnings'].append("Missing values detected")
            
        if features.isin([np.inf, -np.inf]).sum().sum() > 0:
            validation_results['warnings'].append("Infinite values detected")
            
        if len(features) < 100:
            validation_results['warnings'].append("Low sample count for training")
            
        return validation_results
