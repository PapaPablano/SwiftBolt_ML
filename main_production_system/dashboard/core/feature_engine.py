"""
PHASE 2: Feature Pipeline Integration
"""

import pandas as pd
import logging
from typing import Optional, List, Dict, Tuple
import streamlit as st
import numpy as np
from datetime import datetime
from pathlib import Path
import joblib
import hashlib
import pickle
import time

# Scikit-learn scalers and clustering
from sklearn.preprocessing import RobustScaler, MinMaxScaler
from sklearn.cluster import KMeans

from core.wave_detection.ultimate_feature_engineer import UltimateFeatureEngineer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Version and commit info
try:
    from main_production_system import __version__
    SYSTEM_VERSION = __version__
except ImportError:
    SYSTEM_VERSION = "2.0.0"

def engineer_supertrend_features(df_ohlcv: pd.DataFrame, atr_length: int = 10) -> pd.DataFrame:
    '''
    SuperTrend K-Means Clustering for Adaptive Trend + ATR
    
    Replaces: SMA(20/50/200), EMA(12/26), ATR(14)
    Provides: Trend signal + Dynamic risk (atr_adaptive)
    
    Args:
        df_ohlcv: DataFrame with ['open','high','low','close']
        atr_length: ATR calculation period (default 10)
    
    Returns:
        DataFrame with SuperTrend features
    '''
    import sys
    
    # SuperTrendAI optional - fallback to K-Means if unavailable
    try:
        # Primary import path (Phase 4 AI integration)
        from main_production_system.core.supertrend_ai import SuperTrendAI
        SUPERTREND_AVAILABLE = True
    except ImportError:
        try:
            # Legacy path fallback
            from main_production_system.core.wave_detection.supertrend_ai import SuperTrendAI
            SUPERTREND_AVAILABLE = True
        except ImportError:
            try:
                # Fallback: relative to repository root
                from core.wave_detection.supertrend_ai import SuperTrendAI  # type: ignore
                SUPERTREND_AVAILABLE = True
            except ImportError:
                SuperTrendAI = None  # type: ignore
                SUPERTREND_AVAILABLE = False
                logging.warning("SuperTrendAI not available - using K-Means fallback")

    # Prepare data (ensure lowercase)
    df_prep = df_ohlcv[["open", "high", "low", "close"]].copy()
    df_prep.columns = df_prep.columns.str.lower()

    try:
        # Initialize SuperTrendAI with K-means
        if not SUPERTREND_AVAILABLE:
            # Use K-Means K clusters instead
            df_prep_with_volume = df_prep.copy()
            if 'volume' in df_ohlcv.columns:
                df_prep_with_volume['volume'] = df_ohlcv['volume'].values
            else:
                df_prep_with_volume['volume'] = 1.0  # Default volume
            
            # Use K-Means clustering as fallback
            kmeans_result = KMeans(n_clusters=3, random_state=42, n_init=10).fit_predict(
                df_prep_with_volume[['close', 'volume']].values
            )
            
            # Return fallback features with cluster information
            return pd.DataFrame({
                'supertrend_trend': np.sign(np.diff(np.concatenate([[0], kmeans_result]))),  # Trend from cluster changes
                'supertrend_line': df_prep['close'].values,
                'perf_ama': df_prep['close'].values,
                'atr_adaptive': [0.1] * len(df_ohlcv),
                'supertrend_signal': kmeans_result,  # Use cluster as signal
                'target_factor': [0] * len(df_ohlcv),
                'performance_index': [0] * len(df_ohlcv),
            })
        
        st_ai = SuperTrendAI(
            df=df_prep,
            atr_length=atr_length,
            min_mult=1.0,           # Test from 1.0x ATR
            max_mult=5.0,           # To 5.0x ATR
            step=0.5,               # 0.5 increments = 9 factors
            perf_alpha=10,          # Performance memory
            from_cluster='Best',    # Use best cluster
            max_iter=1000,
            max_data=10000,
        )

        # Calculate SuperTrend with K-means
        result_df, info = st_ai.calculate()

        # Extract features
        supertrend_features = pd.DataFrame({
            'supertrend_trend': result_df['trend'].values,        # 1=UP, -1=DOWN
            'supertrend_line': result_df['supertrend'].values,    # Support/Resistance line
            'perf_ama': result_df.get('perf_ama', result_df['supertrend']).values,  # fallback
            'atr_adaptive': result_df['atr'].values,              # Dynamic ATR for risk
            'supertrend_signal': result_df.get('signal', result_df['trend']).values,
        })

        # Attach diagnostics if provided
        if isinstance(info, dict):
            supertrend_features['target_factor'] = info.get('target_factor', 0)
            supertrend_features['performance_index'] = info.get('performance_index', 0)
        else:
            supertrend_features['target_factor'] = 0
            supertrend_features['performance_index'] = 0

        return supertrend_features

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f'SuperTrend calculation error: {e}')
        # Return zero-filled fallback
        return pd.DataFrame({
            'supertrend_trend': [0] * len(df_ohlcv),
            'supertrend_line': df_ohlcv['close'].values if 'close' in df_ohlcv.columns else [0] * len(df_ohlcv),
            'perf_ama': df_ohlcv['close'].values if 'close' in df_ohlcv.columns else [0] * len(df_ohlcv),
            'atr_adaptive': [0.1] * len(df_ohlcv),
            'supertrend_signal': [0] * len(df_ohlcv),
            'target_factor': [0] * len(df_ohlcv),
            'performance_index': [0] * len(df_ohlcv),
        })


def _log_with_context(level: str, message: str, **kwargs):
    """
    Enhanced logging with ISO 8601 timestamps and context.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        message: Log message
        **kwargs: Additional context to include in message
    """
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
    
    context_parts = []
    if kwargs:
        context = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
        context_parts.append(context)
    context_parts.append(f"version={SYSTEM_VERSION}")
    
    if context_parts:
        context_str = " | " + " | ".join(context_parts)
    else:
        context_str = ""
    
    full_message = f"[{timestamp}]{context_str} {message}"
    
    if level == "DEBUG":
        logger.debug(full_message)
    elif level == "INFO":
        logger.info(full_message)
    elif level == "WARNING":
        logger.warning(full_message)
    elif level == "ERROR":
        logger.error(full_message)


def preprocess_ohlcv_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Preprocessing layer for OHLCV data quality and governance.
    
    Performs:
    - Drop rows with NaN in OHLCV columns
    - Outlier treatment (Z-score > 3 capping)
    - Time continuity validation
    - Zero-volume inconsistency detection
    - Comprehensive logging of all steps
    
    Args:
        df: Raw OHLCV DataFrame with columns ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
    
    Returns:
        Cleaned OHLCV DataFrame
    
    Raises:
        ValueError: If input data is invalid or preprocessing fails
    """
    _log_with_context("INFO", "[PREPROCESS] Starting OHLCV preprocessing", rows=len(df))
    
    # Validate input
    if df is None or df.empty:
        _log_with_context("ERROR", "[PREPROCESS] Input DataFrame is None or empty")
        raise ValueError("Input DataFrame is None or empty")
    
    required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        _log_with_context("ERROR", f"[PREPROCESS] Missing required columns: {missing_cols}")
        raise ValueError(f"Missing required columns: {missing_cols}")
    
    df_clean = df.copy()
    initial_rows = len(df_clean)
    
    try:
        # Step 1: Drop rows with NaN in OHLCV columns
        _log_with_context("INFO", "[PREPROCESS] Step 1/4: Removing NaN rows from OHLCV columns")
        ohlcv_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        nan_mask = df_clean[ohlcv_cols].isna().any(axis=1)
        nan_count = nan_mask.sum()
        
        if nan_count > 0:
            _log_with_context("WARNING", f"[PREPROCESS] Found {nan_count} rows with NaN in OHLCV columns ({nan_count/initial_rows*100:.2f}%)")
            df_clean = df_clean[~nan_mask].copy()
            _log_with_context("INFO", f"[PREPROCESS] Removed {nan_count} rows, {len(df_clean)} remain")
        else:
            _log_with_context("DEBUG", "[PREPROCESS] No NaN rows found in OHLCV columns")
        
        # Step 2: Outlier treatment using Z-score (cap values > 3 std dev)
        _log_with_context("INFO", "[PREPROCESS] Step 2/4: Treating outliers (Z-score > 3)")
        outlier_cols = ['Close', 'Volume']
        
        for col in outlier_cols:
            if col not in df_clean.columns:
                continue
            
            mean_val = df_clean[col].mean()
            std_val = df_clean[col].std()
            
            if std_val == 0:
                _log_with_context("DEBUG", f"[PREPROCESS] Column {col} has zero std dev, skipping outlier treatment")
                continue
            
            z_scores = np.abs((df_clean[col] - mean_val) / std_val)
            outliers = (z_scores > 3).sum()
            
            if outliers > 0:
                _log_with_context("WARNING", f"[PREPROCESS] Found {outliers} outliers in {col} (Z-score > 3)")
                # Cap outliers at 3 standard deviations
                upper_bound = mean_val + 3 * std_val
                lower_bound = mean_val - 3 * std_val
                df_clean[col] = df_clean[col].clip(lower=lower_bound, upper=upper_bound)
                _log_with_context("INFO", f"[PREPROCESS] Capped {col} outliers at [{lower_bound:.2f}, {upper_bound:.2f}]")
            else:
                _log_with_context("DEBUG", f"[PREPROCESS] No outliers found in {col}")
        
        # Step 3: Validate time continuity and detect gaps
        _log_with_context("INFO", "[PREPROCESS] Step 3/4: Validating time continuity")
        if 'Date' in df_clean.columns:
            df_clean['Date'] = pd.to_datetime(df_clean['Date'])
            df_clean = df_clean.sort_values('Date').reset_index(drop=True)
            
            # Calculate expected frequency (most common time delta)
            time_deltas = df_clean['Date'].diff().dropna()
            if len(time_deltas) > 0:
                mode_delta = time_deltas.mode()
                if len(mode_delta) > 0:
                    expected_freq = mode_delta.iloc[0]
                    
                    # Detect gaps larger than 1.5x expected frequency
                    large_gaps = time_deltas[time_deltas > 1.5 * expected_freq]
                    
                    if len(large_gaps) > 0:
                        _log_with_context("WARNING", f"[PREPROCESS] Found {len(large_gaps)} time gaps > 1.5x expected frequency")
                        for idx, gap in large_gaps.items():
                            _log_with_context("DEBUG", f"[PREPROCESS] Gap at index {idx}: {gap}")
                    else:
                        _log_with_context("DEBUG", "[PREPROCESS] No significant time gaps detected")
        
        # Step 4: Validate OHLCV logical consistency
        _log_with_context("INFO", "[PREPROCESS] Step 4/4: Validating OHLCV logical consistency")
        
        # Check: High >= Low
        invalid_hl = (df_clean['High'] < df_clean['Low']).sum()
        if invalid_hl > 0:
            _log_with_context("WARNING", f"[PREPROCESS] Found {invalid_hl} rows where High < Low")
            # Fix by swapping
            df_clean.loc[df_clean['High'] < df_clean['Low'], ['High', 'Low']] = \
                df_clean.loc[df_clean['High'] < df_clean['Low'], ['Low', 'High']].values
            _log_with_context("INFO", f"[PREPROCESS] Fixed {invalid_hl} High/Low inconsistencies")
        
        # Check: Close within High/Low range
        invalid_close = ((df_clean['Close'] < df_clean['Low']) | (df_clean['Close'] > df_clean['High'])).sum()
        if invalid_close > 0:
            _log_with_context("WARNING", f"[PREPROCESS] Found {invalid_close} rows where Close outside High/Low range")
            # Clip Close to High/Low bounds
            df_clean['Close'] = df_clean['Close'].clip(lower=df_clean['Low'], upper=df_clean['High'])
            _log_with_context("INFO", f"[PREPROCESS] Clipped {invalid_close} Close prices to valid range")
        
        # Check: Open within High/Low range
        invalid_open = ((df_clean['Open'] < df_clean['Low']) | (df_clean['Open'] > df_clean['High'])).sum()
        if invalid_open > 0:
            _log_with_context("WARNING", f"[PREPROCESS] Found {invalid_open} rows where Open outside High/Low range")
            df_clean['Open'] = df_clean['Open'].clip(lower=df_clean['Low'], upper=df_clean['High'])
            _log_with_context("INFO", f"[PREPROCESS] Clipped {invalid_open} Open prices to valid range")
        
        # Check: Zero volume inconsistencies (non-zero price change with zero volume)
        if 'Date' in df_clean.columns and len(df_clean) > 1:
            price_change = df_clean['Close'].diff().abs()
            zero_vol_rows = df_clean['Volume'] == 0
            price_change_on_zero_vol = (price_change > 0.01) & zero_vol_rows
            inconsistency_count = price_change_on_zero_vol.sum()
            
            if inconsistency_count > 0:
                _log_with_context("WARNING", f"[PREPROCESS] Found {inconsistency_count} zero-volume inconsistencies (price changed with zero volume)")
                # Mark for review but don't drop (may be valid for some assets)
                df_clean['_zero_vol_flag'] = price_change_on_zero_vol
        
        _log_with_context("INFO", f"[PREPROCESS] ✅ Complete: {len(df_clean)}/{initial_rows} rows retained ({len(df_clean)/initial_rows*100:.2f}%)")
        return df_clean
        
    except Exception as e:
        _log_with_context("ERROR", f"[PREPROCESS] Failed: {str(e)}")
        logger.exception("Preprocessing failed")
        raise ValueError(f"OHLCV preprocessing failed: {str(e)}") from e


def normalize_features(df: pd.DataFrame, save_scalers: bool = True, scaler_dir: Optional[str] = None) -> Tuple[pd.DataFrame, Dict]:
    """
    Normalize and scale features for statistical excellence.
    
    Applies:
    - RobustScaler for Volume, MACD, ATR (robust to outliers)
    - MinMaxScaler (per rolling window) for MA features
    - MinMaxScaler to [0,1] for bounded ratios/features
    
    Args:
        df: DataFrame with engineered features
        save_scalers: Whether to save scaler objects for inference
        scaler_dir: Directory to save scalers (default: data/cache/scalers)
    
    Returns:
        Tuple: (normalized_df, scalers_dict)
        - normalized_df: DataFrame with normalized features
        - scalers_dict: Dictionary of scaler objects for reproducibility
    """
    _log_with_context("INFO", "[NORMALIZE] Starting feature normalization", rows=len(df), columns=len(df.columns))
    
    if df is None or df.empty:
        _log_with_context("ERROR", "[NORMALIZE] Input DataFrame is None or empty")
        raise ValueError("Input DataFrame is None or empty")
    
    # Keep Date and OHLCV columns unnormalized
    preserve_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
    df_normalized = df.copy()
    scalers_dict = {}
    
    try:
        # Step 1: RobustScaler for volume, MACD, ATR (robust to outliers)
        _log_with_context("INFO", "[NORMALIZE] Step 1/3: Applying RobustScaler to Volume, MACD, ATR")
        robust_features = []
        
        # Volume features
        volume_features = [col for col in df.columns if 'Volume' in col or 'volume' in col.lower()]
        robust_features.extend(volume_features)
        
        # MACD features
        macd_features = [col for col in df.columns if 'MACD' in col or 'macd' in col.lower()]
        robust_features.extend(macd_features)
        
        # ATR features
        atr_features = [col for col in df.columns if 'ATR' in col or 'atr' in col.lower()]
        robust_features.extend(atr_features)
        
        # Remove duplicates and ensure they exist
        robust_features = list(set([f for f in robust_features if f in df.columns and f not in preserve_cols]))
        
        if robust_features:
            robust_scaler = RobustScaler()
            df_normalized[robust_features] = robust_scaler.fit_transform(df[robust_features])
            scalers_dict['robust_scaler'] = robust_scaler
            scalers_dict['robust_features'] = robust_features
            _log_with_context("INFO", f"[NORMALIZE] Applied RobustScaler to {len(robust_features)} features")
        else:
            _log_with_context("DEBUG", "[NORMALIZE] No RobustScaler features found")
        
        # Step 2: MinMaxScaler (per rolling window) for MA features
        _log_with_context("INFO", "[NORMALIZE] Step 2/3: Applying MinMaxScaler to MA features")
        ma_features = [col for col in df.columns if 'MA' in col or 'SMA' in col or 'EMA' in col or 
                      'ma' in col.lower() or 'sma' in col.lower() or 'ema' in col.lower()]
        ma_features = [f for f in ma_features if f in df.columns and f not in preserve_cols]
        
        if ma_features:
            # For rolling window normalization, we'll use a rolling window approach
            # But for simplicity and reproducibility, we'll use global MinMaxScaler
            # In production, you might want to implement rolling window normalization
            ma_scaler = MinMaxScaler(feature_range=(0, 1))
            df_normalized[ma_features] = ma_scaler.fit_transform(df[ma_features])
            scalers_dict['ma_scaler'] = ma_scaler
            scalers_dict['ma_features'] = ma_features
            _log_with_context("INFO", f"[NORMALIZE] Applied MinMaxScaler to {len(ma_features)} MA features")
        else:
            _log_with_context("DEBUG", "[NORMALIZE] No MA features found")
        
        # Step 3: MinMaxScaler to [0,1] for bounded ratios/features (RSI, KDJ, BB, etc.)
        _log_with_context("INFO", "[NORMALIZE] Step 3/3: Applying MinMaxScaler to bounded ratios")
        bounded_features = []
        
        # RSI features (typically 0-100, but normalize to 0-1)
        rsi_features = [col for col in df.columns if 'RSI' in col or 'rsi' in col.lower()]
        bounded_features.extend(rsi_features)
        
        # KDJ features (typically 0-100)
        kdj_features = [col for col in df.columns if 'KDJ' in col or 'kdj' in col.lower()]
        bounded_features.extend(kdj_features)
        
        # Bollinger Bands (already normalized ratios)
        bb_features = [col for col in df.columns if 'BB' in col or 'Bollinger' in col or 'bollinger' in col.lower()]
        bounded_features.extend(bb_features)
        
        # SuperTrend (directional indicator, normalize)
        st_features = [col for col in df.columns if 'SuperTrend' in col or 'super' in col.lower() or 'trend' in col.lower()]
        bounded_features.extend(st_features)
        
        # Remove duplicates and already processed features
        bounded_features = list(set([f for f in bounded_features if f in df.columns and 
                                     f not in preserve_cols and 
                                     f not in robust_features and 
                                     f not in ma_features]))
        
        if bounded_features:
            bounded_scaler = MinMaxScaler(feature_range=(0, 1))
            df_normalized[bounded_features] = bounded_scaler.fit_transform(df[bounded_features])
            scalers_dict['bounded_scaler'] = bounded_scaler
            scalers_dict['bounded_features'] = bounded_features
            _log_with_context("INFO", f"[NORMALIZE] Applied MinMaxScaler to {len(bounded_features)} bounded features")
        else:
            _log_with_context("DEBUG", "[NORMALIZE] No bounded ratio features found")
        
        # Save scalers for inference/reproducibility
        if save_scalers:
            if scaler_dir is None:
                scaler_dir = Path("data/cache/scalers")
            else:
                scaler_dir = Path(scaler_dir)
            
            scaler_dir.mkdir(parents=True, exist_ok=True)
            scaler_path = scaler_dir / "feature_scalers.pkl"
            
            try:
                joblib.dump(scalers_dict, scaler_path)
                _log_with_context("INFO", f"[NORMALIZE] Saved scalers to {scaler_path}")
            except Exception as e:
                _log_with_context("WARNING", f"[NORMALIZE] Failed to save scalers: {str(e)}")
        
        _log_with_context("INFO", f"[NORMALIZE] ✅ Complete: Normalized {len(robust_features) + len(ma_features) + len(bounded_features)} features")
        return df_normalized, scalers_dict
        
    except Exception as e:
        _log_with_context("ERROR", f"[NORMALIZE] Failed: {str(e)}")
        logger.exception("Feature normalization failed")
        raise ValueError(f"Feature normalization failed: {str(e)}") from e


def load_scalers(scaler_path: Optional[str] = None) -> Dict:
    """
    Load saved scaler objects for inference.
    
    Args:
        scaler_path: Path to scaler file (default: data/cache/scalers/feature_scalers.pkl)
    
    Returns:
        Dictionary of scaler objects
    """
    if scaler_path is None:
        scaler_path = Path("data/cache/scalers/feature_scalers.pkl")
    else:
        scaler_path = Path(scaler_path)
    
    if not scaler_path.exists():
        _log_with_context("WARNING", f"[NORMALIZE] Scaler file not found: {scaler_path}")
        return {}
    
    try:
        scalers_dict = joblib.load(scaler_path)
        _log_with_context("INFO", f"[NORMALIZE] Loaded scalers from {scaler_path}")
        return scalers_dict
    except Exception as e:
        _log_with_context("ERROR", f"[NORMALIZE] Failed to load scalers: {str(e)}")
        return {}


def add_lag_features(df: pd.DataFrame, lags: List[int] = [1, 2, 3, 5, 10]) -> pd.DataFrame:
    """
    Add lag features for temporal sequences.
    
    Creates lagged versions of key features:
    - Close: Price lags for trend analysis
    - MACD: Momentum lags
    - RSI: Momentum oscillator lags
    - Volume: Trading volume lags
    
    Args:
        df: DataFrame with features
        lags: List of lag periods (default: [1, 2, 3, 5, 10])
    
    Returns:
        DataFrame with lag features added (NaNs from lags are dropped)
    """
    _log_with_context("INFO", "[LAGS] Starting lag feature generation", rows=len(df), lags=lags)
    
    if df is None or df.empty:
        _log_with_context("ERROR", "[LAGS] Input DataFrame is None or empty")
        raise ValueError("Input DataFrame is None or empty")
    
    df_lagged = df.copy()
    initial_cols = len(df_lagged.columns)
    
    try:
        # Features to create lags for
        lag_features = []
        
        # Close price
        if 'Close' in df_lagged.columns:
            lag_features.append('Close')
        
        # MACD features
        macd_cols = [col for col in df_lagged.columns if 'MACD' in col]
        if macd_cols:
            lag_features.extend(macd_cols[:2])  # Take first 2 MACD features to avoid too many columns
        
        # RSI features
        rsi_cols = [col for col in df_lagged.columns if 'RSI' in col]
        if rsi_cols:
            lag_features.append(rsi_cols[0])  # Take first RSI feature
        
        # Volume features
        volume_cols = [col for col in df_lagged.columns if 'Volume' in col and col != 'Date']
        if volume_cols:
            lag_features.append(volume_cols[0])  # Take first Volume feature
        
        # Remove duplicates
        lag_features = list(set(lag_features))
        
        _log_with_context("INFO", f"[LAGS] Creating lags for {len(lag_features)} features: {lag_features}")
        
        # Create lag features
        lag_count = 0
        for feature in lag_features:
            if feature not in df_lagged.columns:
                continue
            
            for lag in lags:
                lag_col_name = f"{feature}_lag_{lag}"
                df_lagged[lag_col_name] = df_lagged[feature].shift(lag)
                lag_count += 1
        
        _log_with_context("INFO", f"[LAGS] Created {lag_count} lag features")
        
        # Drop NaN rows introduced by lag features
        initial_rows = len(df_lagged)
        df_lagged = df_lagged.dropna()
        dropped_rows = initial_rows - len(df_lagged)
        
        if dropped_rows > 0:
            _log_with_context("INFO", f"[LAGS] Dropped {dropped_rows} rows with NaN from lags ({dropped_rows/initial_rows*100:.2f}%)")
        else:
            _log_with_context("DEBUG", "[LAGS] No NaN rows to drop")
        
        final_cols = len(df_lagged.columns)
        new_cols = final_cols - initial_cols
        
        _log_with_context("INFO", f"[LAGS] ✅ Complete: Added {new_cols} lag features, {len(df_lagged)} rows remaining")
        return df_lagged
        
    except Exception as e:
        _log_with_context("ERROR", f"[LAGS] Failed: {str(e)}")
        logger.exception("Lag feature generation failed")
        raise ValueError(f"Lag feature generation failed: {str(e)}") from e


class FeatureCacheManager:
    """
    Cache engineered features to avoid recomputation.
    
    Cache key based on: symbol + timeframe + date_range + feature_set
    Cache expires after 1 hour for fresh data.
    """
    
    def __init__(self, cache_dir: str = ".feature_cache"):
        """
        Initialize feature cache manager.
        
        Args:
            cache_dir: Directory to store cache files (default: .feature_cache)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        logger.info(f"[CACHE] Feature cache dir: {self.cache_dir}")
    
    def _generate_cache_key(self, symbol: str, timeframe: str, start_date: str, end_date: str, feature_set: str) -> str:
        """
        Generate unique cache key from parameters.
        
        Args:
            symbol: Stock ticker symbol
            timeframe: Time interval ('1h', '4h', '1d', etc.)
            start_date: Start date string (YYYY-MM-DD format)
            end_date: End date string (YYYY-MM-DD format)
            feature_set: Feature set name ('all', 'minimal', 'legacy')
        
        Returns:
            MD5 hash string for cache key
        """
        key_str = f"{symbol}_{timeframe}_{start_date}_{end_date}_{feature_set}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get_cached_features(
        self, 
        symbol: str, 
        timeframe: str, 
        start_date: str, 
        end_date: str, 
        feature_set: str
    ) -> Optional[pd.DataFrame]:
        """
        Retrieve cached features if available and fresh (<1 hour old).
        
        Args:
            symbol: Stock ticker symbol
            timeframe: Time interval
            start_date: Start date string
            end_date: End date string
            feature_set: Feature set name
        
        Returns:
            Cached DataFrame if available and fresh, None otherwise
        """
        cache_key = self._generate_cache_key(symbol, timeframe, start_date, end_date, feature_set)
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        
        if not cache_file.exists():
            logger.debug(f"[CACHE] MISS: {symbol} {timeframe} (key: {cache_key[:8]}...)")
            return None
        
        # Check cache age (invalidate if >1 hour old)
        try:
            cache_age = time.time() - cache_file.stat().st_mtime
            if cache_age > 3600:  # 1 hour in seconds
                logger.debug(f"[CACHE] EXPIRED: {symbol} (age: {cache_age/60:.1f} min)")
                cache_file.unlink()
                return None
        except OSError as e:
            logger.warning(f"[CACHE] Failed to check cache age: {e}")
            return None
        
        try:
            with open(cache_file, 'rb') as f:
                cached_df = pickle.load(f)
            
            if cached_df is None or (isinstance(cached_df, pd.DataFrame) and cached_df.empty):
                logger.debug(f"[CACHE] EMPTY: {symbol} {timeframe}")
                cache_file.unlink()
                return None
            
            logger.info(f"[CACHE] HIT: {symbol} {timeframe} ({len(cached_df)} rows, {len(cached_df.columns)} cols)")
            return cached_df
            
        except Exception as e:
            logger.warning(f"[CACHE] Load error for {symbol}: {e}")
            try:
                cache_file.unlink()  # Remove corrupted cache file
            except Exception:
                pass
            return None
    
    def save_features(
        self, 
        df: pd.DataFrame, 
        symbol: str, 
        timeframe: str, 
        start_date: str, 
        end_date: str, 
        feature_set: str
    ):
        """
        Save engineered features to cache.
        
        Args:
            df: DataFrame with engineered features
            symbol: Stock ticker symbol
            timeframe: Time interval
            start_date: Start date string
            end_date: End date string
            feature_set: Feature set name
        """
        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            logger.warning(f"[CACHE] Skipping save: DataFrame is None or empty")
            return
        
        cache_key = self._generate_cache_key(symbol, timeframe, start_date, end_date, feature_set)
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(df, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            logger.debug(f"[CACHE] SAVED: {symbol} {timeframe} ({len(df)} rows, {len(df.columns)} cols)")
            
        except Exception as e:
            logger.error(f"[CACHE] Save error for {symbol}: {e}")


# Global cache manager instance
_feature_cache = FeatureCacheManager()


def engineer_features(df: pd.DataFrame, feature_set: str = 'all', 
                      normalize: bool = True, add_lags: bool = True, 
                      lag_periods: List[int] = [1, 2, 3, 5, 10],
                      cache_params: Optional[Dict] = None) -> pd.DataFrame:
    """
    Unified feature engineering pipeline using UltimateFeatureEngineer.
    
    NEW: Includes normalization and lag features for statistical excellence.
    NEW: Optional incremental feature caching to avoid recomputation.

    IMPORTANT: This function is wrapped by @st.cache_data in data_pipeline.load_and_engineer()
    Do NOT add caching decorator here—caching happens at the call site (data_pipeline.py).
    
    Args:
        df: Input OHLCV DataFrame
        feature_set: Feature set to return ('all', 'minimal', 'legacy')
        normalize: Whether to apply feature normalization (default: True)
        add_lags: Whether to add lag features (default: True)
        lag_periods: List of lag periods for lag features (default: [1, 2, 3, 5, 10])
        cache_params: If provided, enables caching. Dict with keys:
            - symbol: str (ticker symbol)
            - timeframe: str (time interval)
            - start_date: str (YYYY-MM-DD format, optional - extracted from DataFrame if missing)
            - end_date: str (YYYY-MM-DD format, optional - extracted from DataFrame if missing)
    """
    
    _log_with_context("INFO", "[FEATURES] Starting feature engineering", rows=len(df), feature_set=feature_set, normalize=normalize, add_lags=add_lags)
    logger.info(f"[FEATURES] Starting feature engineering on {len(df)} candles (feature_set='{feature_set}')...")
    
    # Check cache if params provided
    if cache_params:
        symbol = cache_params.get('symbol', 'UNKNOWN')
        timeframe = cache_params.get('timeframe', '1d')
        
        # Extract date range from DataFrame if not provided
        start_date = cache_params.get('start_date')
        end_date = cache_params.get('end_date')
        
        if not start_date or not end_date:
            if 'Date' in df.columns:
                dates = pd.to_datetime(df['Date'])
                if not start_date:
                    start_date = dates.min().strftime('%Y-%m-%d')
                if not end_date:
                    end_date = dates.max().strftime('%Y-%m-%d')
            else:
                # Fallback: use current date if Date column missing
                if not start_date:
                    start_date = datetime.now().strftime('%Y-%m-%d')
                if not end_date:
                    end_date = datetime.now().strftime('%Y-%m-%d')
        
        # Try to get from cache
        cached_df = _feature_cache.get_cached_features(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            feature_set=feature_set
        )
        
        if cached_df is not None:
            logger.info(f"[FEATURES] ✅ Using cached features for {symbol} ({len(cached_df)} rows)")
            return cached_df

    if df is None or df.empty:
        raise ValueError("[FEATURES] Input DataFrame is None or empty")

    if len(df) < 14:
        logger.warning(f"[FEATURES] ⚠️ DataFrame has only {len(df)} rows (recommended: 30+). Some indicators may fail.")

    try:
        logger.info(f"[FEATURES] Step 1/7: Initializing UltimateFeatureEngineer...")
        engineer = UltimateFeatureEngineer()

        logger.info(f"[FEATURES] Step 2/7: Generating 39+ features (SuperTrend, KDJ, RSI, MACD, BB, etc.)...")
        # Normalize column names to what the engineer expects
        rename_map = {
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume',
            'Date': 'date',
        }
        df_input = df.rename(columns=rename_map)
        df_features = engineer.engineer_features(df_input.copy())

        # Restore standard OHLCV column names for downstream compatibility
        restore_map = {
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume',
            'date': 'Date',
        }
        df_features = df_features.rename(columns=restore_map)

        # Ensure 'Date' column exists (engineer may keep it as index)
        if 'Date' not in df_features.columns:
            if 'date' in df_input.columns:
                df_features['Date'] = df_input['date'].values
            elif df_features.index is not None:
                df_features['Date'] = df_features.index

        if df_features is None or df_features.empty:
            raise ValueError("[FEATURES] Feature engineer returned None or empty DataFrame")

        original_cols = 6
        new_cols_count = len(df_features.columns) - original_cols
        logger.info(f"[FEATURES] Step 2/7: ✅ Generated {new_cols_count} new feature columns ({len(df_features.columns)} total)")

        # Add SuperTrend K-Means features
        try:
            st_features = engineer_supertrend_features(df_input, atr_length=10)

            # Drop legacy trend/ATR columns (avoid feature leakage + clutter)
            drop_cols = [
                c for c in df_features.columns
                if any(x in c.lower() for x in ['sma', 'ema', 'dema'])
            ] + [
                c for c in df_features.columns
                if c.lower().startswith('atr') or 'bbands' in c.lower()
            ]
            df_features = df_features.drop(
                columns=[c for c in drop_cols if c in df_features.columns],
                errors='ignore'
            )

            # Concatenate SuperTrend features
            df_features = pd.concat([df_features, st_features], axis=1)

            logger.info(f"[FEATURES] SuperTrend K-Means added. Shape: {df_features.shape}")
            logger.info(f"[FEATURES] Removed legacy trend/ATR columns. New feature count: {df_features.shape[1]}")
        except Exception as e:
            logger.warning(f"[FEATURES] SuperTrend integration skipped due to error: {e}")

        # Override/compute Bollinger Bands with new parameters (SMA basis, window=30, source=Close, std=2)
        try:
            if 'Close' in df_features.columns:
                close_series = pd.to_numeric(df_features['Close'], errors='coerce')
                bb_middle = close_series.rolling(window=30, min_periods=30).mean()
                bb_std = close_series.rolling(window=30, min_periods=30).std()
                df_features['BB_Middle'] = bb_middle
                df_features['BB_Upper'] = bb_middle + (2 * bb_std)
                df_features['BB_Lower'] = bb_middle - (2 * bb_std)
                logger.info("[FEATURES] Updated Bollinger Bands: window=30, basis=SMA, source=Close, std=2, offset=0")
        except Exception as e:
            logger.warning(f"[FEATURES] Could not update Bollinger Bands: {e}")

        logger.info(f"[FEATURES] Step 3/7: Validating critical features...")
        critical_features = [
            'SuperTrend', 'KDJ_K', 'KDJ_D', 'RSI',
            'MACD', 'MACD_Signal', 'MACD_Histogram',
            'BB_Upper', 'BB_Middle', 'BB_Lower',
            'Volume_SMA'
        ]

        missing_features = [f for f in critical_features if f not in df_features.columns]
        available_critical = len(critical_features) - len(missing_features)

        if missing_features:
            logger.warning(f"[FEATURES] Step 3/7: ⚠️ Missing {len(missing_features)} critical features: {missing_features}")
            logger.warning(f"[FEATURES]         Available: {available_critical}/{len(critical_features)}")
        else:
            logger.info(f"[FEATURES] Step 3/7: ✅ All {len(critical_features)} critical features present")

        logger.info(f"[FEATURES] Step 4/7: Checking for NaN values...")
        total_cells = df_features.shape[0] * df_features.shape[1]
        nan_count = df_features.isna().sum().sum()
        nan_pct = (nan_count / total_cells) * 100 if total_cells else 0.0

        cols_with_nan = df_features.columns[df_features.isna().any()].tolist()
        if cols_with_nan:
            logger.info(f"[FEATURES] Step 4/7: {len(cols_with_nan)} columns with NaN (expected for indicators)")
            nan_by_col = df_features[cols_with_nan].isna().sum()
            high_nan_cols = nan_by_col[nan_by_col > len(df_features) * 0.3]
            if len(high_nan_cols) > 0:
                logger.warning(f"[FEATURES]         High NaN columns: {high_nan_cols.to_dict()}")
        else:
            logger.info(f"[FEATURES] Step 4/7: ✅ No NaN values detected")

        # Step 5: Add lag features (before normalization)
        if add_lags:
            logger.info(f"[FEATURES] Step 5/7: Adding lag features (periods: {lag_periods})...")
            df_features = add_lag_features(df_features, lags=lag_periods)
            logger.info(f"[FEATURES] Step 5/7: ✅ Added lag features: {df_features.shape[1]} columns, {len(df_features)} rows")
        else:
            logger.info(f"[FEATURES] Step 5/7: Skipping lag features (add_lags=False)")

        # Step 6: Normalize features
        if normalize:
            logger.info(f"[FEATURES] Step 6/7: Normalizing features...")
            df_features, scalers_dict = normalize_features(df_features, save_scalers=True)
            logger.info(f"[FEATURES] Step 6/7: ✅ Normalized features: {len(scalers_dict)} scaler groups")
        else:
            logger.info(f"[FEATURES] Step 6/7: Skipping normalization (normalize=False)")

        logger.info(f"[FEATURES] Step 7/7: Filtering to feature_set='{feature_set}'...")
        # Create standardized alias columns expected by downstream consumers
        alias_map = {
            'SuperTrend': 'st_trend_dir',
            'KDJ_K': 'close_kdj_k',
            'KDJ_D': 'close_kdj_d',
            'RSI': 'close_rsi_14',
            'MACD': 'close_macd',
            'MACD_Signal': 'close_macd_signal',
            'BB_Upper': 'close_bollinger_upper',
            'BB_Lower': 'close_bollinger_lower',
            # Optional middle band derived if available
            'BB_Middle': 'close_ma_20',
            'Volume_SMA': 'volume_ma_20',
        }
        for alias_name, source_name in alias_map.items():
            if alias_name not in df_features.columns and source_name in df_features.columns:
                df_features[alias_name] = df_features[source_name]

        df_filtered = _filter_feature_set(df_features, feature_set)
        
        # CRITICAL: Validate feature count matches model expectations
        # This prevents dimension mismatch errors during inference
        # Note: Expected count is dynamic - models are trained on actual generated features
        # Current pipeline generates ~66-70 features (base indicators + lags + aliases)
        actual_feature_count = len([col for col in df_filtered.columns if col not in ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']])
        
        logger.info(f"[FEATURES] Step 7/7: ✅ Final output: {df_filtered.shape[0]} rows × {df_filtered.shape[1]} columns")
        logger.info(f"[FEATURES] Feature count: {actual_feature_count} engineered features (excluding OHLCV)")
        logger.info(f"[FEATURES] Models will dynamically adapt to {actual_feature_count} features during inference")
        
        # Log feature breakdown for debugging
        if actual_feature_count < 60:
            logger.warning(f"[FEATURES] ⚠️ Feature count low: {actual_feature_count} features. Expected 66+.")
            logger.warning(f"[FEATURES] This may indicate missing indicators or lag features.")
        elif actual_feature_count > 100:
            extra_count = actual_feature_count - 66
            logger.warning(f"[FEATURES] ⚠️ Feature count high: Generated {actual_feature_count} features (66 baseline). Extra {extra_count} features will be truncated during inference.")
        else:
            logger.info(f"[FEATURES] ✅ Feature count nominal: {actual_feature_count} features (66-100 range)")

        # Save to cache if params provided
        if cache_params:
            symbol = cache_params.get('symbol', 'UNKNOWN')
            timeframe = cache_params.get('timeframe', '1d')
            
            # Extract date range from DataFrame if not provided (reuse logic from above)
            start_date = cache_params.get('start_date')
            end_date = cache_params.get('end_date')
            
            if not start_date or not end_date:
                if 'Date' in df_filtered.columns:
                    dates = pd.to_datetime(df_filtered['Date'])
                    if not start_date:
                        start_date = dates.min().strftime('%Y-%m-%d')
                    if not end_date:
                        end_date = dates.max().strftime('%Y-%m-%d')
                else:
                    # Fallback: use current date if Date column missing
                    if not start_date:
                        start_date = datetime.now().strftime('%Y-%m-%d')
                    if not end_date:
                        end_date = datetime.now().strftime('%Y-%m-%d')
            
            _feature_cache.save_features(
                df=df_filtered,
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                feature_set=feature_set
            )

        logger.info(f"[FEATURES] ✅ COMPLETE: Feature engineering successful (normalized={normalize}, lags={add_lags})")
        return df_filtered

    except Exception as e:
        logger.error(f"[FEATURES] ❌ CRITICAL: Feature engineering failed")
        logger.error(f"[FEATURES] Exception: {type(e).__name__}: {str(e)[:200]}")
        raise ValueError(f"Feature engineering pipeline failed: {str(e)}") from e


def _filter_feature_set(df_features: pd.DataFrame, feature_set: str) -> pd.DataFrame:
    base_columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']

    if feature_set == 'all':
        logger.info(f"[FILTER] Mode 'all': Keeping all {len(df_features.columns)} columns")
        return df_features
    elif feature_set == 'minimal':
        minimal_features = [
            'Date', 'Open', 'High', 'Low', 'Close', 'Volume',
            'SuperTrend', 'KDJ_K', 'KDJ_D', 'RSI', 'MACD', 'MACD_Signal'
        ]
        available = [f for f in minimal_features if f in df_features.columns]
        logger.info(f"[FILTER] Mode 'minimal': Keeping {len(available)} critical columns")
        return df_features[available]
    elif feature_set == 'legacy':
        logger.info(f"[FILTER] Mode 'legacy': Keeping all {len(df_features.columns)} columns for XGBoost")
        return df_features
    else:
        raise ValueError(f"Unknown feature_set: {feature_set}. Use 'all', 'minimal', or 'legacy'")


def validate_features(df_features: pd.DataFrame, expected_count: int = 39) -> bool:
    feature_cols = len(df_features.columns) - 6
    threshold_min = expected_count * 0.7
    threshold_good = expected_count * 0.9

    if feature_cols < threshold_min:
        logger.warning(f"[VALIDATE] ⚠️ Feature count low: {feature_cols}/{expected_count} (threshold: {threshold_min})")
        return False
    if feature_cols >= threshold_good:
        logger.info(f"[VALIDATE] ✅ Feature count excellent: {feature_cols}/{expected_count}")
    else:
        logger.info(f"[VALIDATE] ✅ Feature count acceptable: {feature_cols}/{expected_count}")
    return True


def get_feature_info(df_features: pd.DataFrame, include_normalization_stats: bool = True) -> dict:
    """
    Enhanced feature information including normalization stats, value ranges, and distribution alerts.
    
    Args:
        df_features: DataFrame with features
        include_normalization_stats: Whether to include normalization statistics
    
    Returns:
        Dictionary with comprehensive feature information
    """
    base_cols = 6
    total_cols = len(df_features.columns)
    engineering_cols = total_cols - base_cols
    nan_count = df_features.isna().sum().sum()
    nan_pct = (nan_count / (df_features.shape[0] * df_features.shape[1])) * 100 if df_features.size else 0.0
    memory_mb = df_features.memory_usage(deep=True).sum() / 1024 / 1024
    critical = ['SuperTrend', 'KDJ_K', 'KDJ_D', 'RSI', 'MACD', 'BB_Upper', 'BB_Lower']
    present = [f for f in critical if f in df_features.columns]
    missing = [f for f in critical if f not in df_features.columns]
    
    info = {
        'total_features': total_cols,
        'engineering_features': engineering_cols,
        'nan_count': nan_count,
        'nan_percent': nan_pct,
        'memory_mb': memory_mb,
        'critical_features_present': present,
        'critical_features_missing': missing,
        'rows': len(df_features),
    }
    
    # Post-normalization feature stats
    if include_normalization_stats:
        numeric_cols = df_features.select_dtypes(include=[np.number]).columns
        numeric_cols = [c for c in numeric_cols if c not in ['Date']]
        
        if len(numeric_cols) > 0:
            # Value ranges for all numeric features
            value_ranges = {}
            normalization_alerts = []
            
            for col in numeric_cols[:20]:  # Limit to first 20 to avoid huge dicts
                if col in df_features.columns:
                    col_data = df_features[col].dropna()
                    if len(col_data) > 0:
                        min_val = float(col_data.min())
                        max_val = float(col_data.max())
                        mean_val = float(col_data.mean())
                        std_val = float(col_data.std())
                        
                        value_ranges[col] = {
                            'min': min_val,
                            'max': max_val,
                            'mean': mean_val,
                            'std': std_val,
                            'range': max_val - min_val
                        }
                        
                        # Alert unusual distributions
                        # Check if feature is normalized (should be in [0,1] range)
                        if max_val <= 1.1 and min_val >= -0.1:
                            # Likely normalized, check for proper normalization
                            if max_val > 1.0 or min_val < 0.0:
                                normalization_alerts.append(f"{col}: normalized but out of [0,1] range")
                        else:
                            # Not normalized, check for extreme ranges
                            if std_val > mean_val * 2 and mean_val != 0:
                                normalization_alerts.append(f"{col}: high variance (std/mean = {std_val/mean_val:.2f})")
                            elif max_val / min_val > 1000 if min_val > 0 else False:
                                normalization_alerts.append(f"{col}: extreme range ({min_val:.2f} to {max_val:.2f})")
            
            info['value_ranges'] = value_ranges
            info['normalization_alerts'] = normalization_alerts
            
            # Feature distribution summary
            normalized_count = sum(1 for v in value_ranges.values() if v['max'] <= 1.1 and v['min'] >= -0.1)
            info['normalized_features_count'] = normalized_count
            info['unnormalized_features_count'] = len(value_ranges) - normalized_count
    
    return info


def display_feature_info(df_features: pd.DataFrame):
    """
    Enhanced feature information display with normalization stats, value ranges, and distribution alerts.
    """
    info = get_feature_info(df_features, include_normalization_stats=True)
    
    # Main metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Features", info['total_features'])
    with col2:
        st.metric("Engineering Features", info['engineering_features'])
    with col3:
        st.metric("Rows", info['rows'])
    with col4:
        st.metric("Memory (MB)", f"{info['memory_mb']:.2f}")
    
    # Critical indicators
    with st.expander("🔍 Critical Features & Quality"):
        st.write(f"**NaN Count**: {info['nan_count']} ({info['nan_percent']:.1f}%)")
        st.write(f"**Critical Features**:")
        st.write(f"  - ✅ Present ({len(info['critical_features_present'])}): {info['critical_features_present']}")
        if info['critical_features_missing']:
            st.write(f"  - ❌ Missing ({len(info['critical_features_missing'])}): {info['critical_features_missing']}")
    
    # Normalization stats
    if 'normalized_features_count' in info:
        with st.expander("📊 Normalization Statistics"):
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Normalized Features", info['normalized_features_count'])
            with col2:
                st.metric("Unnormalized Features", info['unnormalized_features_count'])
            
            # Normalization alerts
            if info.get('normalization_alerts'):
                st.warning("⚠️ Normalization Alerts:")
                for alert in info['normalization_alerts'][:10]:  # Show first 10
                    st.write(f"  - {alert}")
            else:
                st.success("✅ No normalization issues detected")
    
    # Value ranges
    if 'value_ranges' in info and info['value_ranges']:
        with st.expander("📈 Feature Value Ranges"):
            # Show key feature ranges
            key_features = ['Close', 'RSI', 'MACD', 'Volume', 'KDJ_K', 'SuperTrend']
            shown_features = set()
            
            for feat in key_features:
                # Try exact match first
                if feat in info['value_ranges']:
                    shown_features.add(feat)
                    ranges = info['value_ranges'][feat]
                    st.write(f"**{feat}**:")
                    st.write(f"  - Range: [{ranges['min']:.4f}, {ranges['max']:.4f}]")
                    st.write(f"  - Mean: {ranges['mean']:.4f}, Std: {ranges['std']:.4f}")
            
            # Show other features (up to 10 more)
            other_features = [f for f in info['value_ranges'].keys() if f not in shown_features][:10]
            if other_features:
                st.write("**Other Features:**")
                for feat in other_features:
                    ranges = info['value_ranges'][feat]
                    st.write(f"  - {feat}: [{ranges['min']:.4f}, {ranges['max']:.4f}] (mean: {ranges['mean']:.4f})")


