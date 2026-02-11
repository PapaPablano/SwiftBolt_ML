#!/usr/bin/env python3
"""
Advanced Directional Features Engine

This module implements sophisticated directional features beyond basic KDJ crossovers,
including multi-timeframe consensus, price action patterns, volume confirmation,
momentum divergence, and regime transition signals.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class AdvancedDirectionalFeatures:
    """
    Advanced directional feature engineering for enhanced prediction accuracy.
    
    This class creates sophisticated features that capture:
    1. Multi-timeframe KDJ consensus
    2. Price action patterns (engulfing, higher highs/lows)
    3. Volume confirmation signals
    4. Momentum divergence detection
    5. Regime transition signals
    6. Advanced technical indicators
    """
    
    def __init__(self):
        self.feature_cache = {}
        
    def calculate_kdj(self, df: pd.DataFrame, period: int = 9) -> pd.DataFrame:
        """Calculate KDJ indicators for a given period."""
        low_min = df['low'].rolling(window=period).min()
        high_max = df['high'].rolling(window=period).max()
        rsv = (df['close'] - low_min) / (high_max - low_min) * 100
        k = rsv.ewm(com=2).mean()
        d = k.ewm(com=2).mean()
        j = 3 * k - 2 * d
        
        return pd.DataFrame({
            'k': k,
            'd': d,
            'j': j
        }, index=df.index)
    
    def detect_bullish_engulfing(self, df: pd.DataFrame) -> pd.Series:
        """Detect bullish engulfing candlestick patterns."""
        prev_open = df['open'].shift(1)
        prev_close = df['close'].shift(1)
        
        # Current candle is bullish (close > open)
        current_bullish = df['close'] > df['open']
        
        # Previous candle is bearish (close < open)
        prev_bearish = prev_close < prev_open
        
        # Current candle engulfs previous (open < prev_close and close > prev_open)
        engulfs = (df['open'] < prev_close) & (df['close'] > prev_open)
        
        return (current_bullish & prev_bearish & engulfs).astype(int)
    
    def detect_bearish_engulfing(self, df: pd.DataFrame) -> pd.Series:
        """Detect bearish engulfing candlestick patterns."""
        prev_open = df['open'].shift(1)
        prev_close = df['close'].shift(1)
        
        # Current candle is bearish (close < open)
        current_bearish = df['close'] < df['open']
        
        # Previous candle is bullish (close > open)
        prev_bullish = prev_close > prev_open
        
        # Current candle engulfs previous (open > prev_close and close < prev_open)
        engulfs = (df['open'] > prev_close) & (df['close'] < prev_open)
        
        return (current_bearish & prev_bullish & engulfs).astype(int)
    
    def detect_higher_highs_lows(self, df: pd.DataFrame, lookback: int = 5) -> pd.DataFrame:
        """Detect higher highs and higher lows patterns."""
        features = pd.DataFrame(index=df.index)
        
        # Higher highs: current high > max of previous N highs
        features['higher_high'] = (df['high'] > df['high'].rolling(lookback).max().shift(1)).astype(int)
        
        # Higher lows: current low > min of previous N lows
        features['higher_low'] = (df['low'] > df['low'].rolling(lookback).min().shift(1)).astype(int)
        
        # Lower highs: current high < max of previous N highs
        features['lower_high'] = (df['high'] < df['high'].rolling(lookback).max().shift(1)).astype(int)
        
        # Lower lows: current low < min of previous N lows
        features['lower_low'] = (df['low'] < df['low'].rolling(lookback).min().shift(1)).astype(int)
        
        return features
    
    def detect_volume_patterns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect volume-based directional signals."""
        features = pd.DataFrame(index=df.index)
        
        if 'volume' not in df.columns:
            # Create dummy volume if not present
            df['volume'] = 1000000
        
        # Volume surge: current volume > 1.5x average
        volume_ma = df['volume'].rolling(20).mean()
        features['volume_surge'] = (df['volume'] > volume_ma * 1.5).astype(int)
        
        # Volume spike: current volume > 2x average
        features['volume_spike'] = (df['volume'] > volume_ma * 2.0).astype(int)
        
        # Bullish volume: price up + volume up
        price_up = df['close'] > df['open']
        volume_up = df['volume'] > df['volume'].shift(1)
        features['bullish_volume'] = (price_up & volume_up).astype(int)
        
        # Bearish volume: price down + volume up
        price_down = df['close'] < df['open']
        features['bearish_volume'] = (price_down & volume_up).astype(int)
        
        # Volume divergence: price and volume moving in opposite directions
        price_direction = np.sign(df['close'].diff())
        volume_direction = np.sign(df['volume'].diff())
        features['volume_divergence'] = (price_direction != volume_direction).astype(int)
        
        return features
    
    def detect_momentum_divergence(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect momentum divergence between price and indicators."""
        features = pd.DataFrame(index=df.index)
        
        # Price direction
        price_direction = np.sign(df['close'].diff())
        
        # RSI divergence
        if 'close_rsi_14' in df.columns:
            rsi_direction = np.sign(df['close_rsi_14'].diff())
            features['rsi_divergence'] = (price_direction != rsi_direction).astype(int)
        
        # KDJ divergence
        if 'close_kdj_j' in df.columns:
            kdj_direction = np.sign(df['close_kdj_j'].diff())
            features['kdj_divergence'] = (price_direction != kdj_direction).astype(int)
        
        # MACD divergence
        if 'close_macd' in df.columns:
            macd_direction = np.sign(df['close_macd'].diff())
            features['macd_divergence'] = (price_direction != macd_direction).astype(int)
        
        return features
    
    def detect_regime_transitions(self, df: pd.DataFrame, regime_col: str = 'volatility_regime') -> pd.DataFrame:
        """Detect regime transition signals."""
        features = pd.DataFrame(index=df.index)
        
        if regime_col not in df.columns:
            # Calculate volatility regime if not present
            returns = df['close'].pct_change().dropna()
            volatility = returns.rolling(20).std()
            vol_33 = volatility.quantile(0.33)
            vol_67 = volatility.quantile(0.67)
            
            regime = pd.Series(index=volatility.index, dtype='object')
            regime[volatility <= vol_33] = 'LOW'
            regime[(volatility > vol_33) & (volatility <= vol_67)] = 'MEDIUM'
            regime[volatility > vol_67] = 'HIGH'
            df[regime_col] = regime
        
        # Entering high volatility
        features['entering_high_volatility'] = (
            (df[regime_col] == 'HIGH') & 
            (df[regime_col].shift(1) == 'MEDIUM')
        ).astype(int)
        
        # Exiting high volatility
        features['exiting_high_volatility'] = (
            (df[regime_col] == 'MEDIUM') & 
            (df[regime_col].shift(1) == 'HIGH')
        ).astype(int)
        
        # Entering low volatility
        features['entering_low_volatility'] = (
            (df[regime_col] == 'LOW') & 
            (df[regime_col].shift(1) == 'MEDIUM')
        ).astype(int)
        
        # Exiting low volatility
        features['exiting_low_volatility'] = (
            (df[regime_col] == 'MEDIUM') & 
            (df[regime_col].shift(1) == 'LOW')
        ).astype(int)
        
        return features
    
    def create_multi_timeframe_kdj(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create multi-timeframe KDJ consensus features."""
        features = pd.DataFrame(index=df.index)
        
        # Calculate KDJ for different periods
        periods = [9, 14, 21]
        kdj_data = {}
        
        for period in periods:
            kdj = self.calculate_kdj(df, period)
            kdj_data[period] = kdj
            
            # Individual KDJ signals
            features[f'kdj_{period}_j_above_d'] = (kdj['j'] > kdj['d']).astype(int)
            features[f'kdj_{period}_j_cross_d_up'] = (
                (kdj['j'] > kdj['d']) & 
                (kdj['j'].shift(1) <= kdj['d'].shift(1))
            ).astype(int)
            features[f'kdj_{period}_j_cross_d_down'] = (
                (kdj['j'] < kdj['d']) & 
                (kdj['j'].shift(1) >= kdj['d'].shift(1))
            ).astype(int)
        
        # Consensus signals
        features['kdj_consensus_bullish'] = (
            features['kdj_9_j_above_d'] & 
            features['kdj_14_j_above_d'] & 
            features['kdj_21_j_above_d']
        ).astype(int)
        
        features['kdj_consensus_bearish'] = (
            (~features['kdj_9_j_above_d'].astype(bool)) & 
            (~features['kdj_14_j_above_d'].astype(bool)) & 
            (~features['kdj_21_j_above_d'].astype(bool))
        ).astype(int)
        
        # Strength of consensus (how many timeframes agree)
        features['kdj_consensus_strength'] = (
            features['kdj_9_j_above_d'].astype(int) + 
            features['kdj_14_j_above_d'].astype(int) + 
            features['kdj_21_j_above_d'].astype(int)
        )
        
        return features
    
    def create_multi_timeframe_kdj_indicators(self, df: pd.DataFrame,
                                             timeframes: List[int] = [5, 20, 50, 200]
                                            ) -> pd.DataFrame:
        """
        Create KDJ indicators at multiple timeframes.
        
        This creates K, D, J indicators at different periods to capture
        multi-timeframe KDJ signals.
        
        Args:
            df: DataFrame with OHLCV data
            timeframes: List of periods for multi-timeframe analysis
            
        Returns:
            DataFrame with multi-timeframe KDJ indicators
        """
        logger.info(f"Creating multi-timeframe KDJ indicators for periods: {timeframes}")
        
        features = pd.DataFrame(index=df.index)
        
        for tf in timeframes:
            # Calculate KDJ for each timeframe
            kdj = self.calculate_kdj(df, period=9)  # Use period 9 as base
            
            # Rolling average of K, D, J at each timeframe
            features[f'kdj_k_{tf}'] = kdj['k'].rolling(tf).mean()
            features[f'kdj_d_{tf}'] = kdj['d'].rolling(tf).mean()
            features[f'kdj_j_{tf}'] = kdj['j'].rolling(tf).mean()
            
            # J minus D at each timeframe
            features[f'kdj_j_minus_d_{tf}'] = features[f'kdj_j_{tf}'] - features[f'kdj_d_{tf}']
            
            # Position of J relative to D at each timeframe
            features[f'kdj_j_position_{tf}'] = (
                (features[f'kdj_j_{tf}'] - features[f'kdj_d_{tf}']) / 
                (features[f'kdj_d_{tf}'].abs() + 0.001)  # Avoid division by zero
            )
            
            # KDJ overbought/oversold signals
            features[f'kdj_overbought_{tf}'] = (kdj['j'] > 80).astype(int)
            features[f'kdj_oversold_{tf}'] = (kdj['j'] < 20).astype(int)
            
            # J crossing D signals
            features[f'kdj_j_cross_d_up_{tf}'] = (
                (kdj['j'] > kdj['d']) & 
                (kdj['j'].shift(1) <= kdj['d'].shift(1))
            ).astype(int)
            
            features[f'kdj_j_cross_d_down_{tf}'] = (
                (kdj['j'] < kdj['d']) & 
                (kdj['j'].shift(1) >= kdj['d'].shift(1))
            ).astype(int)
        
        logger.info(f"Created {len(features.columns)} multi-timeframe KDJ indicators")
        
        return features
    
    def create_multi_timeframe_kdj_consensus_features(self, df: pd.DataFrame,
                                                      timeframes: List[int] = [5, 20, 50, 200]
                                                     ) -> pd.DataFrame:
        """
        Create KDJ consensus features showing when timeframes agree.
        
        These features capture high-confidence KDJ signals when multiple
        timeframes align.
        
        Args:
            df: DataFrame with multi-timeframe KDJ indicators
            timeframes: List of periods used in KDJ indicators
            
        Returns:
            DataFrame with KDJ consensus features
        """
        logger.info("Creating KDJ timeframe consensus features...")
        
        features = pd.DataFrame(index=df.index)
        
        # Find available KDJ indicators for consensus
        available_tfs = []
        for tf in timeframes:
            if f'kdj_j_{tf}' in df.columns and f'kdj_d_{tf}' in df.columns:
                available_tfs.append(tf)
        
        if len(available_tfs) < 2:
            logger.warning("Not enough timeframes available for KDJ consensus features")
            return features
        
        # KDJ bullish/bearish signals at each timeframe
        kdj_j_above_d = pd.DataFrame({
            f'kdj_j_above_d_{tf}': df[f'kdj_j_{tf}'] > df[f'kdj_d_{tf}']
            for tf in available_tfs if f'kdj_j_{tf}' in df.columns and f'kdj_d_{tf}' in df.columns
        })
        
        if not kdj_j_above_d.empty:
            # All timeframes bullish (J > D at all timeframes)
            features['kdj_tf_all_bullish'] = kdj_j_above_d.all(axis=1).astype(int)
            features['kdj_tf_all_bearish'] = (~kdj_j_above_d).all(axis=1).astype(int)
            features['kdj_tf_bullish_count'] = kdj_j_above_d.sum(axis=1)
            
            # Consensus strength
            features['kdj_tf_consensus_strength'] = features['kdj_tf_bullish_count'] / len(available_tfs)
            features['kdj_tf_unanimous_bullish'] = (features['kdj_tf_consensus_strength'] == 1.0).astype(int)
            features['kdj_tf_unanimous_bearish'] = (features['kdj_tf_consensus_strength'] == 0.0).astype(int)
        
        # J crossing D up/down signals across timeframes
        cross_up_cols = [f'kdj_j_cross_d_up_{tf}' for tf in available_tfs if f'kdj_j_cross_d_up_{tf}' in df.columns]
        cross_down_cols = [f'kdj_j_cross_d_down_{tf}' for tf in available_tfs if f'kdj_j_cross_d_down_{tf}' in df.columns]
        
        if cross_up_cols:
            cross_up_df = pd.DataFrame({col: df[col] for col in cross_up_cols})
            features['kdj_tf_any_cross_up'] = cross_up_df.any(axis=1).astype(int)
            features['kdj_tf_all_cross_up'] = cross_up_df.all(axis=1).astype(int)
            features['kdj_tf_cross_up_count'] = cross_up_df.sum(axis=1)
        
        if cross_down_cols:
            cross_down_df = pd.DataFrame({col: df[col] for col in cross_down_cols})
            features['kdj_tf_any_cross_down'] = cross_down_df.any(axis=1).astype(int)
            features['kdj_tf_all_cross_down'] = cross_down_df.all(axis=1).astype(int)
            features['kdj_tf_cross_down_count'] = cross_down_df.sum(axis=1)
        
        # Overbought/oversold consensus
        overbought_cols = [f'kdj_overbought_{tf}' for tf in available_tfs if f'kdj_overbought_{tf}' in df.columns]
        oversold_cols = [f'kdj_oversold_{tf}' for tf in available_tfs if f'kdj_oversold_{tf}' in df.columns]
        
        if overbought_cols:
            overbought_df = pd.DataFrame({col: df[col] for col in overbought_cols})
            features['kdj_tf_any_overbought'] = overbought_df.any(axis=1).astype(int)
            features['kdj_tf_all_overbought'] = overbought_df.all(axis=1).astype(int)
        
        if oversold_cols:
            oversold_df = pd.DataFrame({col: df[col] for col in oversold_cols})
            features['kdj_tf_any_oversold'] = oversold_df.any(axis=1).astype(int)
            features['kdj_tf_all_oversold'] = oversold_df.all(axis=1).astype(int)
        
        logger.info(f"Created {len(features.columns)} KDJ consensus features")
        
        return features
    
    def create_advanced_macd_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create advanced MACD-based features."""
        features = pd.DataFrame(index=df.index)
        
        if 'close_macd' not in df.columns:
            # Calculate MACD if not present
            exp1 = df['close'].ewm(span=12).mean()
            exp2 = df['close'].ewm(span=26).mean()
            df['close_macd'] = exp1 - exp2
            df['close_macd_signal'] = df['close_macd'].ewm(span=9).mean()
        
        # Basic MACD signals
        features['macd_positive'] = (df['close_macd'] > 0).astype(int)
        features['macd_above_signal'] = (df['close_macd'] > df['close_macd_signal']).astype(int)
        features['macd_cross_signal'] = (
            (df['close_macd'] > df['close_macd_signal']) & 
            (df['close_macd'].shift(1) <= df['close_macd_signal'].shift(1))
        ).astype(int)
        
        # MACD momentum
        features['macd_momentum'] = df['close_macd'].diff()
        features['macd_acceleration'] = features['macd_momentum'].diff()
        
        # MACD histogram
        features['macd_histogram'] = df['close_macd'] - df['close_macd_signal']
        features['macd_histogram_positive'] = (features['macd_histogram'] > 0).astype(int)
        
        return features
    
    def create_bollinger_band_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create Bollinger Band-based features."""
        features = pd.DataFrame(index=df.index)
        
        if 'close_bollinger_upper' not in df.columns:
            # Calculate Bollinger Bands if not present
            bb_middle = df['close'].rolling(20).mean()
            bb_std = df['close'].rolling(20).std()
            df['close_bollinger_upper'] = bb_middle + (bb_std * 2)
            df['close_bollinger_lower'] = bb_middle - (bb_std * 2)
        
        # Position within bands
        features['bb_position'] = (df['close'] - df['close_bollinger_lower']) / (
            df['close_bollinger_upper'] - df['close_bollinger_lower']
        )
        
        # Band width
        features['bb_width'] = (df['close_bollinger_upper'] - df['close_bollinger_lower']) / df['close']
        
        # Band squeeze (low volatility)
        features['bb_squeeze'] = (features['bb_width'] < features['bb_width'].rolling(20).mean() * 0.8).astype(int)
        
        # Price touching bands
        features['price_touch_upper_bb'] = (df['close'] >= df['close_bollinger_upper']).astype(int)
        features['price_touch_lower_bb'] = (df['close'] <= df['close_bollinger_lower']).astype(int)
        
        return features
    
    def create_advanced_directional_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create comprehensive advanced directional features.
        
        Args:
            df: DataFrame with OHLC data and basic technical indicators
            
        Returns:
            DataFrame with advanced directional features
        """
        logger.info("Creating advanced directional features...")
        
        features = pd.DataFrame(index=df.index)
        
        # 1. Multi-timeframe KDJ consensus
        logger.info("  - Multi-timeframe KDJ consensus...")
        kdj_features = self.create_multi_timeframe_kdj(df)
        features = pd.concat([features, kdj_features], axis=1)
        
        # 2. Price action patterns
        logger.info("  - Price action patterns...")
        features['bullish_engulfing'] = self.detect_bullish_engulfing(df)
        features['bearish_engulfing'] = self.detect_bearish_engulfing(df)
        
        # Higher highs/lows
        hh_hl_features = self.detect_higher_highs_lows(df)
        features = pd.concat([features, hh_hl_features], axis=1)
        
        # 3. Volume confirmation
        logger.info("  - Volume confirmation signals...")
        volume_features = self.detect_volume_patterns(df)
        features = pd.concat([features, volume_features], axis=1)
        
        # 4. Momentum divergence
        logger.info("  - Momentum divergence detection...")
        momentum_features = self.detect_momentum_divergence(df)
        features = pd.concat([features, momentum_features], axis=1)
        
        # 5. Regime transition signals
        logger.info("  - Regime transition signals...")
        regime_features = self.detect_regime_transitions(df)
        features = pd.concat([features, regime_features], axis=1)
        
        # 6. Advanced MACD features
        logger.info("  - Advanced MACD features...")
        macd_features = self.create_advanced_macd_features(df)
        features = pd.concat([features, macd_features], axis=1)
        
        # 7. Bollinger Band features
        logger.info("  - Bollinger Band features...")
        bb_features = self.create_bollinger_band_features(df)
        features = pd.concat([features, bb_features], axis=1)
        
        # 8. Additional momentum features
        logger.info("  - Additional momentum features...")
        features['price_momentum_5'] = df['close'].pct_change(5)
        features['price_momentum_10'] = df['close'].pct_change(10)
        features['price_momentum_20'] = df['close'].pct_change(20)
        
        # Volatility features
        features['volatility_5'] = df['close'].pct_change().rolling(5).std()
        features['volatility_20'] = df['close'].pct_change().rolling(20).std()
        features['volatility_ratio'] = features['volatility_5'] / features['volatility_20']
        
        # Trend strength
        if 'close_ma_20' in df.columns:
            features['trend_strength'] = (df['close'] - df['close_ma_20']) / df['close_ma_20']
            features['trend_above_ma20'] = (df['close'] > df['close_ma_20']).astype(int)
        
        logger.info(f"Created {len(features.columns)} advanced directional features")
        
        return features
    
    def get_feature_importance_weights(self) -> Dict[str, float]:
        """
        Get feature importance weights for different feature categories.
        
        Returns:
            Dictionary mapping feature patterns to importance weights
        """
        return {
            'kdj_consensus': 1.5,      # Multi-timeframe consensus is very important
            'volume_': 1.3,            # Volume confirmation is important
            'divergence': 1.4,         # Momentum divergence is critical
            'regime_transition': 1.2,  # Regime changes are important
            'engulfing': 1.1,          # Price patterns are moderately important
            'higher_': 1.0,            # Basic price action
            'macd_': 1.0,              # MACD features
            'bb_': 0.9,                # Bollinger Bands
            'momentum': 0.8,           # Basic momentum
            'volatility': 0.7          # Volatility features
        }
    
    def apply_feature_weights(self, features: pd.DataFrame) -> pd.DataFrame:
        """
        Apply importance weights to features based on their category.
        
        Args:
            features: DataFrame with advanced features
            
        Returns:
            DataFrame with weighted features
        """
        weights = self.get_feature_importance_weights()
        weighted_features = features.copy()
        
        for pattern, weight in weights.items():
            matching_cols = [col for col in features.columns if pattern in col.lower()]
            for col in matching_cols:
                # Only apply weights to numeric columns
                if pd.api.types.is_numeric_dtype(features[col]):
                    weighted_features[col] = features[col] * weight
                else:
                    # Keep non-numeric columns as-is
                    weighted_features[col] = features[col]
        
        return weighted_features


def create_advanced_directional_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convenience function to create advanced directional features.
    
    Args:
        df: DataFrame with OHLC data
        
    Returns:
        DataFrame with advanced directional features
    """
    engine = AdvancedDirectionalFeatures()
    return engine.create_advanced_directional_features(df)


if __name__ == "__main__":
    # Test the advanced features
    import sys
    from pathlib import Path
    
    # Add the main production system to path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    # Load sample data
    data_file = Path("CRWD_engineered.csv")
    if data_file.exists():
        df = pd.read_csv(data_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        # Create advanced features
        engine = AdvancedDirectionalFeatures()
        advanced_features = engine.create_advanced_directional_features(df)
        
        print(f"Created {len(advanced_features.columns)} advanced directional features")
        print(f"Feature columns: {list(advanced_features.columns)}")
        print(f"Sample data shape: {advanced_features.shape}")
        
        # Show feature importance weights
        weights = engine.get_feature_importance_weights()
        print(f"\nFeature importance weights: {weights}")
    else:
        print(f"Data file not found: {data_file}")
