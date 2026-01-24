"""Data preparation for ensemble training.

Handles:
- Data collection from feature cache
- Label generation from future price movements
- Train/validation splitting (time-ordered)
- Feature selection for training
"""

import logging
from typing import Dict, Tuple

import pandas as pd
import numpy as np

from src.data.supabase_db import SupabaseDatabase
from src.features.feature_cache import fetch_or_build_features

logger = logging.getLogger(__name__)

# Feature columns to exclude from training (non-predictive)
EXCLUDE_COLS = [
    "ts", "timestamp", "created_at", "updated_at",
    "open", "high", "low", "close", "volume",  # Raw OHLC (use derived features instead)
    "symbol", "ticker", "symbol_id", "timeframe",
    "id", "uuid", "forecast_id",
]


def collect_training_data(
    db: SupabaseDatabase,
    symbols: list[str],
    timeframes: Dict[str, int],
    lookback_days: int = 90,
) -> Dict[str, Dict[str, pd.DataFrame]]:
    """
    Collect training data across symbols and timeframes.
    
    Args:
        db: Database connection
        symbols: List of tickers (e.g., ['AAPL', 'SPY'])
        timeframes: Dict mapping timeframe to bar count (e.g., {"d1": 500})
        lookback_days: Days of history (used for logging only)
    
    Returns:
        Nested dict: {timeframe: {symbol: df_with_features}}
    
    Example:
        data = collect_training_data(
            db, 
            symbols=["AAPL"], 
            timeframes={"d1": 500, "h1": 500}
        )
        # Returns: {"d1": {"AAPL": <DataFrame>}, "h1": {"AAPL": <DataFrame>}}
    """
    
    training_data = {}
    
    for symbol in symbols:
        logger.info(f"Collecting data for {symbol}...")
        
        try:
            # Fetch features using existing feature cache
            features_by_tf = fetch_or_build_features(
                db=db,
                symbol=symbol,
                timeframes=list(timeframes.keys()),
                limits=timeframes,
            )
            
            for timeframe, df in features_by_tf.items():
                if df.empty:
                    logger.warning(f"No data for {symbol}/{timeframe}")
                    continue
                
                # Initialize timeframe dict if needed
                if timeframe not in training_data:
                    training_data[timeframe] = {}
                
                # Ensure time ordering (oldest → newest)
                if "ts" in df.columns:
                    df = df.sort_values("ts").reset_index(drop=True)
                
                training_data[timeframe][symbol] = df
                logger.info(f"  {timeframe}: {len(df)} bars")
                
        except Exception as e:
            logger.error(f"Failed to collect {symbol}: {e}", exc_info=True)
            continue
    
    return training_data


def create_labels(
    df: pd.DataFrame,
    prediction_horizon_bars: int = 5,
    threshold: float = 0.002,
) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Create direction labels from future price movement.
    
    Args:
        df: DataFrame with 'close' column
        prediction_horizon_bars: Bars ahead to predict (e.g., 5 = predict 5 bars out)
        threshold: Minimum return to classify as BULLISH/BEARISH (e.g., 0.002 = 0.2%)
    
    Returns:
        (features_df, labels_series)
        - features_df: Original data minus last N rows (where we can't compute labels)
        - labels_series: Direction labels ("BULLISH", "NEUTRAL", "BEARISH")
    
    Example:
        df = pd.DataFrame({"close": [100, 101, 102, 103, 104, 105]})
        features, labels = create_labels(df, prediction_horizon_bars=2, threshold=0.01)
        # labels might be: ["BULLISH", "BULLISH", "BULLISH", "BULLISH"]
        # (last 2 rows dropped because we can't see 2 bars ahead)
    """
    
    if "close" not in df.columns:
        raise ValueError("DataFrame must have 'close' column")
    
    df = df.copy()
    
    # Calculate future returns
    future_close = df["close"].shift(-prediction_horizon_bars)
    future_returns = (future_close - df["close"]) / df["close"]
    
    # Create direction labels
    labels = pd.Series("NEUTRAL", index=df.index)
    labels[future_returns > threshold] = "BULLISH"
    labels[future_returns < -threshold] = "BEARISH"
    
    # Remove last N rows where we don't have future data
    valid_rows = len(df) - prediction_horizon_bars
    
    if valid_rows <= 0:
        raise ValueError(
            f"Insufficient  {len(df)} rows, need at least {prediction_horizon_bars + 1}"
        )
    
    features = df.iloc[:valid_rows].reset_index(drop=True)
    labels_out = labels.iloc[:valid_rows].reset_index(drop=True)
    
    logger.info(
        f"Created {len(labels_out)} labels: "
        f"BULLISH={sum(labels_out == 'BULLISH')}, "
        f"NEUTRAL={sum(labels_out == 'NEUTRAL')}, "
        f"BEARISH={sum(labels_out == 'BEARISH')}"
    )
    
    return features, labels_out


def select_features_for_training(df: pd.DataFrame) -> pd.DataFrame:
    """
    Select numeric feature columns suitable for ML training.
    
    Excludes:
    - Timestamp columns
    - Raw OHLC (use derived features instead)
    - ID/metadata columns
    - Non-numeric columns
    
    Args:
        df: DataFrame with all features
    
    Returns:
        DataFrame with only training-suitable numeric features
    """
    
    # Start with all columns
    feature_cols = df.columns.tolist()
    
    # Remove excluded columns (case-insensitive)
    feature_cols = [
        col for col in feature_cols
        if col.lower() not in [ex.lower() for ex in EXCLUDE_COLS]
    ]
    
    # Keep only numeric columns
    numeric_cols = df[feature_cols].select_dtypes(include=[np.number]).columns.tolist()
    
    if not numeric_cols:
        raise ValueError("No numeric feature columns found after filtering")
    
    features = df[numeric_cols].copy()
    
    # Handle NaN/Inf values
    # Replace inf with NaN
    features = features.replace([np.inf, -np.inf], np.nan)
    
    # Forward fill then backward fill (pandas 2.0+ compatible)
    features = features.ffill().bfill()
    
    # If still NaN, fill with 0
    features = features.fillna(0)
    
    logger.info(f"Selected {len(numeric_cols)} feature columns for training")
    
    return features


def prepare_train_validation_split(
    df: pd.DataFrame,
    labels: pd.Series,
    train_fraction: float = 0.7,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """
    Time-based train/validation split (NO SHUFFLING).
    
    CRITICAL: Split is time-ordered to prevent data leakage.
    - Train set: indices 0 to train_fraction * len (oldest data)
    - Valid set: indices train_fraction * len to end (newest data)
    
    Args:
        df: Feature DataFrame
        labels: Label Series
        train_fraction: Fraction for training (default 70%)
    
    Returns:
        (train_features, valid_features, train_labels, valid_labels)
    
    Example:
        train_f, valid_f, train_l, valid_l = prepare_train_validation_split(
            features, labels, train_fraction=0.7
        )
        # First 70% → training, last 30% → validation
    """
    
    if len(df) != len(labels):
        raise ValueError(f"Feature/label length mismatch: {len(df)} vs {len(labels)}")
    
    split_idx = int(len(df) * train_fraction)
    
    if split_idx < 10 or (len(df) - split_idx) < 10:
        raise ValueError(
            f"Insufficient data for split: {len(df)} rows → "
            f"{split_idx} train, {len(df) - split_idx} valid"
        )
    
    train_features = df.iloc[:split_idx].reset_index(drop=True)
    valid_features = df.iloc[split_idx:].reset_index(drop=True)
    train_labels = labels.iloc[:split_idx].reset_index(drop=True)
    valid_labels = labels.iloc[split_idx:].reset_index(drop=True)
    
    logger.info(f"Train: {len(train_features)} rows, Valid: {len(valid_features)} rows")
    logger.info(f"Train distribution: {train_labels.value_counts().to_dict()}")
    logger.info(f"Valid distribution: {valid_labels.value_counts().to_dict()}")
    
    return train_features, valid_features, train_labels, valid_labels
