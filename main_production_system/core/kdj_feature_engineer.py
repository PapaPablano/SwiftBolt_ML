#!/usr/bin/env python3
"""
KDJ Feature Engineer - Production System
Handles KDJ technical indicator calculation and feature engineering.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging

class KDJFeatureEngineer:
    """
    Production-grade KDJ (Stochastic) feature engineer.
    Implements KDJ indicators with proper data leakage prevention.
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {
            'kdj_period': 9,
            'k_smooth': 3,
            'd_smooth': 3,
            'include_divergence': True,
            'include_position': True
        }
        self.logger = logging.getLogger(__name__)
    
    def create_features(self, df: pd.DataFrame, include_kdj: bool = True) -> pd.DataFrame:
        """
        Create comprehensive feature set with optional KDJ indicators.
        Includes data leakage prevention (all features shifted by 1 period).
        """
        features = pd.DataFrame(index=df.index)
        
        # Basic price features (shifted to prevent leakage)
        features['open_lag1'] = df['open'].shift(1)
        features['high_lag1'] = df['high'].shift(1)
        features['low_lag1'] = df['low'].shift(1)
        features['close_lag1'] = df['close'].shift(1)
        
        # Price ratios (shifted)
        features['hl_ratio'] = (df['high'] / df['low']).shift(1)
        features['oc_ratio'] = (df['open'] / df['close']).shift(1)
        features['ch_ratio'] = (df['close'] / df['high']).shift(1)
        features['cl_ratio'] = (df['close'] / df['low']).shift(1)
        
        # Returns (shifted)
        features['return_1d'] = df['close'].pct_change(1).shift(1)
        features['return_3d'] = df['close'].pct_change(3).shift(1)
        features['return_5d'] = df['close'].pct_change(5).shift(1)
        
        # Volatility measures (shifted)
        features['volatility_5d'] = df['close'].rolling(5).std().shift(1)
        features['volatility_10d'] = df['close'].rolling(10).std().shift(1)
        
        # Volume features (if available, shifted)
        if 'volume' in df.columns:
            features['volume_lag1'] = df['volume'].shift(1)
            features['volume_ma5'] = df['volume'].rolling(5).mean().shift(1)
            features['volume_ratio'] = (df['volume'] / df['volume'].rolling(10).mean()).shift(1)
        
        # SuperTrend AI replaces moving averages (volatility-aware regime detection)
        supertrend_features = self._calculate_supertrend_ai(df)
        for col in supertrend_features.columns:
            features[col] = supertrend_features[col]  # Already shifted in _calculate_supertrend_ai
        
        # Price position in range (shifted)
        for period in [5, 10, 20]:
            period_high = df['high'].rolling(period).max()
            period_low = df['low'].rolling(period).min()
            features[f'price_position_{period}d'] = ((df['close'] - period_low) / (period_high - period_low)).shift(1)
        
        # Momentum indicators (shifted)
        features['momentum_3d'] = (df['close'] / df['close'].shift(3) - 1).shift(1)
        features['momentum_7d'] = (df['close'] / df['close'].shift(7) - 1).shift(1)
        
        # KDJ Technical Indicators (optional, shifted)
        if include_kdj:
            kdj_features = self._calculate_kdj_indicators(df)
            for col in kdj_features.columns:
                features[col] = kdj_features[col].shift(1)  # Prevent data leakage
                
        # Drop rows with NaN values
        features_clean = features.dropna()
        
        self.logger.info(f"Created {len(features_clean.columns)} features, {len(features_clean)} valid samples")
        
        return features_clean
    
    def _calculate_supertrend_ai(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate SuperTrend AI features to replace moving averages."""
        try:
            # Import SuperTrend AI module
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from src.option_analysis.supertrend_ai import calculate_supertrend_ai_features
            
            # Calculate SuperTrend AI features (already shifted internally)
            st_features = calculate_supertrend_ai_features(
                df,
                atr_length=10,
                min_mult=1.0,
                max_mult=5.0,
                step=0.5,
                perf_alpha=10.0,
                from_cluster='Best',
            )
            
            # Map to feature names expected by the system
            result = pd.DataFrame(index=df.index)
            result['super_supertrend'] = st_features['supertrend_ai']
            result['super_trend'] = st_features['supertrend_ai_trend']
            result['super_ama'] = st_features['supertrend_ai_ama']
            result['super_signal'] = st_features['supertrend_ai_signal']
            result['super_distance'] = st_features['supertrend_ai_distance']
            result['super_upper'] = st_features['supertrend_ai_upper']
            result['super_lower'] = st_features['supertrend_ai_lower']
            
            return result
        except Exception as e:
            self.logger.warning(f"SuperTrend AI calculation failed: {e}")
            return pd.DataFrame(index=df.index)
    
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
        k_line = rsv.ewm(span=k_smooth).mean()  # Fast %K
        d_line = k_line.ewm(span=d_smooth).mean()  # Slow %D
        j_line = 3 * k_line - 2 * d_line  # J line (leading indicator)
        
        # Create KDJ features DataFrame
        kdj_features = pd.DataFrame(index=df.index)
        kdj_features['kdj_k'] = k_line
        kdj_features['kdj_d'] = d_line  
        kdj_features['kdj_j'] = j_line
        
        # Additional KDJ-derived features
        if self.config.get('include_divergence', True):
            kdj_features['j_minus_d'] = j_line - d_line  # J-D divergence
            
        if self.config.get('include_position', True):
            kdj_features['j_position_relative_d'] = np.where(j_line > d_line, 1, 0)  # J above D
            
        return kdj_features
    
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
    
    def get_feature_importance_groups(self, features: pd.DataFrame) -> Dict[str, List[str]]:
        """Group features by type for importance analysis."""
        feature_groups = {
            'price_basic': [],
            'price_ratios': [],
            'returns': [],
            'volatility': [],
            'volume': [],
            'supertrend_ai': [],
            'momentum': [],
            'kdj_indicators': [],
            'position': []
        }
        
        for col in features.columns:
            if any(term in col for term in ['open_lag', 'high_lag', 'low_lag', 'close_lag']):
                feature_groups['price_basic'].append(col)
            elif 'ratio' in col:
                feature_groups['price_ratios'].append(col)
            elif 'return' in col:
                feature_groups['returns'].append(col)
            elif 'volatility' in col:
                feature_groups['volatility'].append(col)
            elif 'volume' in col:
                feature_groups['volume'].append(col)
            elif 'super_' in col:
                feature_groups['supertrend_ai'].append(col)
            elif 'momentum' in col:
                feature_groups['momentum'].append(col)
            elif 'kdj' in col:
                feature_groups['kdj_indicators'].append(col)
            elif 'position' in col:
                feature_groups['position'].append(col)
        
        # Remove empty groups
        return {k: v for k, v in feature_groups.items() if v}
    
    def update_config(self, new_config: Dict):
        """Update KDJ configuration parameters."""
        self.config.update(new_config)
        self.logger.info(f"Updated KDJ config: {self.config}")