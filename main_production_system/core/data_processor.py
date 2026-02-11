#!/usr/bin/env python3
"""
Main Production System - Data Processor
Handles all data loading, cleaning, and preparation for KDJ-enhanced models.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Union
import logging
from pathlib import Path
import os

class DataProcessor:
    """
    Production-grade data processor for stock market data.
    Handles multiple data sources and ensures data quality.
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        self.supported_formats = ['.csv', '.pkl', '.parquet']
        
    def load_data(self, source: Union[str, Path], **kwargs) -> pd.DataFrame:
        """Load data from various sources with validation."""
        source = Path(source)
        
        if not source.exists():
            raise FileNotFoundError(f"Data source not found: {source}")
            
        # Determine file type and load accordingly
        if source.suffix == '.csv':
            df = pd.read_csv(source, **kwargs)
        elif source.suffix == '.pkl':
            df = pd.read_pickle(source, **kwargs)
        elif source.suffix == '.parquet':
            df = pd.read_parquet(source, **kwargs)
        else:
            raise ValueError(f"Unsupported file format: {source.suffix}")
            
        self.logger.info(f"Loaded {len(df)} rows from {source}")
        return self.validate_and_clean(df)
    
    def validate_and_clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate and clean the loaded data."""
        original_length = len(df)
        
        # Standardize column names
        df = self._standardize_columns(df)
        
        # Validate required columns
        required_cols = ['open', 'high', 'low', 'close']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")
            
        # Basic data validation
        df = self._validate_ohlc_data(df)
        
        # Remove duplicates
        if 'timestamp' in df.columns or 'date' in df.columns:
            date_col = 'timestamp' if 'timestamp' in df.columns else 'date'
            df = df.drop_duplicates(subset=[date_col])
            
        # Sort by date
        if 'timestamp' in df.columns:
            df = df.sort_values('timestamp').reset_index(drop=True)
        elif 'date' in df.columns:
            df = df.sort_values('date').reset_index(drop=True)
            
        cleaned_length = len(df)
        if cleaned_length != original_length:
            self.logger.warning(f"Data cleaned: {original_length} → {cleaned_length} rows")
            
        return df
    
    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names to lowercase."""
        column_mapping = {
            'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close',
            'Volume': 'volume', 'Date': 'date', 'Time': 'timestamp',
            'OPEN': 'open', 'HIGH': 'high', 'LOW': 'low', 'CLOSE': 'close',
            'VOLUME': 'volume', 'DATE': 'date', 'TIME': 'timestamp'
        }
        
        return df.rename(columns=column_mapping)
    
    def _validate_ohlc_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate OHLC data integrity."""
        # Remove rows with negative prices
        price_cols = ['open', 'high', 'low', 'close']
        for col in price_cols:
            if col in df.columns:
                df = df[df[col] > 0]
                
        # Validate OHLC relationships
        if all(col in df.columns for col in price_cols):
            # High should be >= max(open, close)
            # Low should be <= min(open, close)
            valid_high = df['high'] >= df[['open', 'close']].max(axis=1)
            valid_low = df['low'] <= df[['open', 'close']].min(axis=1)
            
            invalid_rows = ~(valid_high & valid_low)
            if invalid_rows.sum() > 0:
                self.logger.warning(f"Removing {invalid_rows.sum()} rows with invalid OHLC relationships")
                df = df[~invalid_rows]
                
        return df.reset_index(drop=True)
    
    def prepare_for_training(self, df: pd.DataFrame, target_col: str = 'close') -> Tuple[pd.DataFrame, pd.Series]:
        """Prepare data for model training."""
        # Ensure we have enough data
        if len(df) < 50:
            raise ValueError(f"Insufficient data for training: {len(df)} rows")
            
        # Create target (next period's close price)
        target = df[target_col].shift(-1).dropna()
        
        # Align features with target
        features_df = df.iloc[:-1].reset_index(drop=True)
        target = target.reset_index(drop=True)
        
        return features_df, target
    
    def split_data(self, 
                   features: pd.DataFrame, 
                   target: pd.Series, 
                   test_size: float = 0.2,
                   validation_size: float = 0.1) -> Dict[str, Union[pd.DataFrame, pd.Series]]:
        """Split data into train/validation/test sets with time awareness."""
        
        total_samples = len(features)
        test_samples = int(total_samples * test_size)
        val_samples = int(total_samples * validation_size)
        train_samples = total_samples - test_samples - val_samples
        
        # Time-based split (no shuffling)
        train_end = train_samples
        val_end = train_end + val_samples
        
        return {
            'X_train': features.iloc[:train_end],
            'y_train': target.iloc[:train_end],
            'X_val': features.iloc[train_end:val_end],
            'y_val': target.iloc[train_end:val_end], 
            'X_test': features.iloc[val_end:],
            'y_test': target.iloc[val_end:]
        }
    
    def get_data_summary(self, df: pd.DataFrame) -> Dict:
        """Get comprehensive data summary."""
        summary = {
            'shape': df.shape,
            'columns': list(df.columns),
            'dtypes': dict(df.dtypes),
            'missing_values': dict(df.isnull().sum()),
            'date_range': None,
            'memory_usage_mb': df.memory_usage(deep=True).sum() / 1024**2
        }
        
        # Date range if available
        date_cols = [col for col in df.columns if 'date' in col.lower() or 'time' in col.lower()]
        if date_cols:
            date_col = date_cols[0]
            try:
                summary['date_range'] = {
                    'start': str(df[date_col].min()),
                    'end': str(df[date_col].max()),
                    'periods': len(df)
                }
            except:
                pass
                
        return summary