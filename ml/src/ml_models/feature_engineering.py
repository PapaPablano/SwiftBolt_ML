"""Feature engineering for options ML models.

Creates features from market data including:
- Technical indicators (RSI, MACD, Bollinger Bands)
- Greeks (Delta, Gamma, Vega, Theta)
- Volatility metrics (Historical vol, IV, IV rank)
- Price patterns (momentum, mean reversion)
- Volume & open interest

Usage:
    from src.ml_models.feature_engineering import FeatureEngineer
    
    engineer = FeatureEngineer()
    features_df = engineer.create_features(price_data, options_data)
    
    # Get feature importance
    importance = engineer.get_feature_importance(X, y)
"""

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """Calculate technical indicators for feature engineering."""
    
    @staticmethod
    def rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index.
        
        Args:
            prices: Price series
            period: RSI period
        
        Returns:
            RSI values
        """
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series]:
        """Calculate MACD and signal line.
        
        Args:
            prices: Price series
            fast: Fast EMA period
            slow: Slow EMA period
            signal: Signal line period
        
        Returns:
            Tuple of (MACD, signal_line)
        """
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=signal).mean()
        
        return macd, signal_line
    
    @staticmethod
    def bollinger_bands(prices: pd.Series, period: int = 20, std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate Bollinger Bands.
        
        Args:
            prices: Price series
            period: Moving average period
            std_dev: Standard deviations for bands
        
        Returns:
            Tuple of (upper_band, middle_band, lower_band)
        """
        middle = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        
        return upper, middle, lower
    
    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Average True Range.
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: ATR period
        
        Returns:
            ATR values
        """
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr


class FeatureEngineer:
    """Feature engineering for options ML models."""
    
    def __init__(self):
        """Initialize feature engineer."""
        self.feature_names: List[str] = []
        logger.info("FeatureEngineer initialized")
    
    def create_features(
        self,
        price_data: pd.DataFrame,
        options_data: Optional[pd.DataFrame] = None,
        include_greeks: bool = True
    ) -> pd.DataFrame:
        """Create features from market data.
        
        Args:
            price_data: DataFrame with columns: open, high, low, close, volume
            options_data: Optional DataFrame with Greeks
            include_greeks: Whether to include Greeks features
        
        Returns:
            DataFrame with engineered features
        """
        features = pd.DataFrame(index=price_data.index)
        
        # Price-based features
        features = self._add_price_features(features, price_data)
        
        # Technical indicators
        features = self._add_technical_indicators(features, price_data)
        
        # Volatility features
        features = self._add_volatility_features(features, price_data)
        
        # Greeks features (if available)
        if include_greeks and options_data is not None:
            features = self._add_greeks_features(features, options_data)
        
        # Time-based features
        features = self._add_time_features(features)
        
        # Store feature names
        self.feature_names = list(features.columns)
        
        logger.info(f"Created {len(self.feature_names)} features")
        
        return features
    
    def _add_price_features(self, features: pd.DataFrame, price_data: pd.DataFrame) -> pd.DataFrame:
        """Add price-based features."""
        close = price_data['close']
        
        # Returns
        features['returns_1d'] = close.pct_change(1)
        features['returns_5d'] = close.pct_change(5)
        features['returns_20d'] = close.pct_change(20)
        
        # Log returns
        features['log_returns_1d'] = np.log(close / close.shift(1))
        
        # Price momentum
        features['momentum_10d'] = close / close.shift(10) - 1
        features['momentum_20d'] = close / close.shift(20) - 1
        
        # Moving averages
        features['sma_5'] = close.rolling(5).mean()
        features['sma_20'] = close.rolling(20).mean()
        features['sma_50'] = close.rolling(50).mean()
        
        # MA ratios
        features['price_to_sma20'] = close / features['sma_20']
        features['sma5_to_sma20'] = features['sma_5'] / features['sma_20']
        
        # Price range
        if 'high' in price_data.columns and 'low' in price_data.columns:
            features['daily_range'] = (price_data['high'] - price_data['low']) / close
        
        # Volume features
        if 'volume' in price_data.columns:
            volume = price_data['volume']
            features['volume_ratio'] = volume / volume.rolling(20).mean()
            features['volume_trend'] = volume.rolling(5).mean() / volume.rolling(20).mean()
        
        return features
    
    def _add_technical_indicators(self, features: pd.DataFrame, price_data: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicator features."""
        close = price_data['close']
        
        # RSI
        features['rsi_14'] = TechnicalIndicators.rsi(close, 14)
        features['rsi_28'] = TechnicalIndicators.rsi(close, 28)
        
        # MACD
        macd, signal = TechnicalIndicators.macd(close)
        features['macd'] = macd
        features['macd_signal'] = signal
        features['macd_histogram'] = macd - signal
        
        # Bollinger Bands
        upper, middle, lower = TechnicalIndicators.bollinger_bands(close)
        features['bb_upper'] = upper
        features['bb_middle'] = middle
        features['bb_lower'] = lower
        features['bb_width'] = (upper - lower) / middle
        features['bb_position'] = (close - lower) / (upper - lower)
        
        # ATR
        if all(col in price_data.columns for col in ['high', 'low', 'close']):
            features['atr_14'] = TechnicalIndicators.atr(
                price_data['high'],
                price_data['low'],
                price_data['close'],
                14
            )
        
        return features
    
    def _add_volatility_features(self, features: pd.DataFrame, price_data: pd.DataFrame) -> pd.DataFrame:
        """Add volatility-based features."""
        returns = price_data['close'].pct_change()
        
        # Historical volatility (different windows)
        features['hvol_5d'] = returns.rolling(5).std() * np.sqrt(252)
        features['hvol_20d'] = returns.rolling(20).std() * np.sqrt(252)
        features['hvol_60d'] = returns.rolling(60).std() * np.sqrt(252)
        
        # Volatility ratios
        features['hvol_ratio_5_20'] = features['hvol_5d'] / features['hvol_20d']
        features['hvol_ratio_20_60'] = features['hvol_20d'] / features['hvol_60d']
        
        # Parkinson volatility (high-low estimator)
        if 'high' in price_data.columns and 'low' in price_data.columns:
            hl_ratio = np.log(price_data['high'] / price_data['low'])
            features['parkinson_vol'] = hl_ratio.rolling(20).std() * np.sqrt(252 / (4 * np.log(2)))
        
        return features
    
    def _add_greeks_features(self, features: pd.DataFrame, options_data: pd.DataFrame) -> pd.DataFrame:
        """Add Greeks-based features."""
        # Assume options_data has: delta, gamma, vega, theta, implied_vol
        
        if 'delta' in options_data.columns:
            features['delta'] = options_data['delta']
            features['delta_change'] = options_data['delta'].diff()
        
        if 'gamma' in options_data.columns:
            features['gamma'] = options_data['gamma']
        
        if 'vega' in options_data.columns:
            features['vega'] = options_data['vega']
        
        if 'theta' in options_data.columns:
            features['theta'] = options_data['theta']
        
        if 'implied_vol' in options_data.columns:
            features['implied_vol'] = options_data['implied_vol']
            features['iv_change'] = options_data['implied_vol'].diff()
            
            # IV rank/percentile (simplified)
            iv_series = options_data['implied_vol']
            features['iv_rank'] = iv_series.rolling(252).apply(
                lambda x: (x.iloc[-1] - x.min()) / (x.max() - x.min()) if x.max() > x.min() else 0.5
            )
        
        return features
    
    def _add_time_features(self, features: pd.DataFrame) -> pd.DataFrame:
        """Add time-based features."""
        if isinstance(features.index, pd.DatetimeIndex):
            features['day_of_week'] = features.index.dayofweek
            features['day_of_month'] = features.index.day
            features['month'] = features.index.month
            features['quarter'] = features.index.quarter
            
            # Cyclical encoding for day of week
            features['dow_sin'] = np.sin(2 * np.pi * features['day_of_week'] / 7)
            features['dow_cos'] = np.cos(2 * np.pi * features['day_of_week'] / 7)
        
        return features
    
    def get_feature_importance(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        method: str = 'random_forest'
    ) -> pd.Series:
        """Calculate feature importance.
        
        Args:
            X: Features DataFrame
            y: Target variable
            method: 'random_forest' or 'correlation'
        
        Returns:
            Series with feature importances
        """
        if method == 'correlation':
            # Simple correlation-based importance
            importance = X.corrwith(y).abs().sort_values(ascending=False)
            return importance
        
        elif method == 'random_forest':
            try:
                from sklearn.ensemble import RandomForestRegressor
                
                # Remove NaN values
                valid_mask = ~(X.isna().any(axis=1) | y.isna())
                X_clean = X[valid_mask]
                y_clean = y[valid_mask]
                
                if len(X_clean) < 100:
                    logger.warning("Not enough data for RF importance, using correlation")
                    return self.get_feature_importance(X, y, method='correlation')
                
                rf = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
                rf.fit(X_clean, y_clean)
                
                importance = pd.Series(
                    rf.feature_importances_,
                    index=X.columns
                ).sort_values(ascending=False)
                
                return importance
                
            except ImportError:
                logger.warning("scikit-learn not available, using correlation")
                return self.get_feature_importance(X, y, method='correlation')
        
        else:
            raise ValueError(f"Unknown method: {method}")


if __name__ == "__main__":
    # Self-test
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("Feature Engineering - Self Test")
    print("=" * 70)
    
    # Create synthetic price data
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', periods=200, freq='D')
    
    prices = 100 * (1 + np.random.randn(200) * 0.02).cumprod()
    
    price_data = pd.DataFrame({
        'open': prices * (1 + np.random.randn(200) * 0.005),
        'high': prices * (1 + abs(np.random.randn(200)) * 0.01),
        'low': prices * (1 - abs(np.random.randn(200)) * 0.01),
        'close': prices,
        'volume': np.random.randint(1000000, 5000000, 200)
    }, index=dates)
    
    print(f"\nGenerated {len(price_data)} days of price data")
    print(f"Price range: ${price_data['close'].min():.2f} - ${price_data['close'].max():.2f}")
    
    # Test feature engineering
    print("\n📊 Creating Features...")
    engineer = FeatureEngineer()
    features = engineer.create_features(price_data, include_greeks=False)
    
    print(f"\nFeatures created: {len(features.columns)}")
    print(f"Feature names: {list(features.columns[:10])}...")
    
    # Check for NaN
    nan_count = features.isna().sum().sum()
    print(f"\nTotal NaN values: {nan_count}")
    print(f"NaN percentage: {100 * nan_count / (len(features) * len(features.columns)):.2f}%")
    
    # Feature statistics
    print("\n📊 Feature Statistics:")
    print(features.describe().iloc[:, :5])
    
    # Test feature importance
    print("\n📊 Testing Feature Importance...")
    target = price_data['close'].pct_change(5).shift(-5)  # 5-day forward return
    
    importance = engineer.get_feature_importance(features, target, method='correlation')
    
    print("\nTop 10 Features by Correlation:")
    print(importance.head(10))
    
    print("\n" + "=" * 70)
    print("✅ Feature engineering test complete!")
    print("=" * 70)
