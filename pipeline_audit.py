#!/usr/bin/env python3
"""
SwiftBolt ML - Complete Pipeline Audit Script
Validates data cleaning, feature engineering, and ML processes for regime-aware testing

Usage:
    cd /Users/ericpeterson/SwiftBolt_ML
    python pipeline_audit.py
"""

import sys
from pathlib import Path

# Allow running from project root: imports resolve to ml/src
_ml_dir = Path(__file__).resolve().parent / "ml"
if _ml_dir.exists():
    sys.path.insert(0, str(_ml_dir))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


class PipelineAuditor:
    """Comprehensive audit of data pipeline and ML processes"""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.successes = []
        
    def log_issue(self, category: str, message: str):
        """Log a critical issue"""
        self.issues.append(f"❌ {category}: {message}")
        logger.error(f"❌ {category}: {message}")
    
    def log_warning(self, category: str, message: str):
        """Log a warning"""
        self.warnings.append(f"⚠️  {category}: {message}")
        logger.warning(f"⚠️  {category}: {message}")
    
    def log_success(self, category: str, message: str):
        """Log a success"""
        self.successes.append(f"✅ {category}: {message}")
        logger.info(f"✅ {category}: {message}")
    
    # ========================================================================
    # SECTION 1: DATA LOADING & AVAILABILITY AUDIT
    # ========================================================================
    
    def audit_supabase_connection(self) -> bool:
        """Test Supabase connection and data availability"""
        logger.info("\n" + "="*80)
        logger.info("SECTION 1: SUPABASE DATA AVAILABILITY AUDIT")
        logger.info("="*80)
        
        try:
            from src.data.supabase_db import SupabaseDatabase
            
            db = SupabaseDatabase()
            self.log_success("Connection", "Supabase connection established")
            
            # Test stocks for regime analysis
            test_stocks = ['AAPL', 'MSFT', 'NVDA', 'PG', 'KO']
            
            for symbol in test_stocks:
                try:
                    df = db.fetch_ohlc_bars(symbol, timeframe='d1', limit=2000)
                    
                    if df is None or len(df) == 0:
                        self.log_issue("Data", f"{symbol}: No data returned")
                        continue
                    
                    # Check data sufficiency
                    if len(df) < 250:
                        self.log_warning("Data", 
                            f"{symbol}: Only {len(df)} bars (need 250+ for robust indicators)")
                    else:
                        self.log_success("Data", 
                            f"{symbol}: {len(df)} bars available")
                    
                    # Check required columns
                    required_cols = ['ts', 'open', 'high', 'low', 'close', 'volume']
                    missing_cols = [col for col in required_cols if col not in df.columns]
                    
                    if missing_cols:
                        self.log_issue("Schema", 
                            f"{symbol}: Missing columns: {missing_cols}")
                    else:
                        self.log_success("Schema", 
                            f"{symbol}: All required OHLCV columns present")
                    
                    # Check for NaN values in critical columns
                    for col in ['close', 'volume']:
                        if col in df.columns:
                            nan_pct = df[col].isna().sum() / len(df) * 100
                            if nan_pct > 0:
                                self.log_warning("Data Quality", 
                                    f"{symbol}: {col} has {nan_pct:.1f}% NaN values")
                    
                    # Check date range
                    if 'ts' in df.columns:
                        df['ts'] = pd.to_datetime(df['ts'])
                        date_range = (df['ts'].max() - df['ts'].min()).days
                        
                        if date_range < 365:
                            self.log_warning("Date Range", 
                                f"{symbol}: Only {date_range} days (need 365+ for regime analysis)")
                        else:
                            self.log_success("Date Range", 
                                f"{symbol}: {date_range} days of data")
                            
                            # Check if we have data for key regime periods
                            self._check_regime_coverage(df, symbol)
                    
                except Exception as e:
                    self.log_issue("Data Fetch", f"{symbol}: {str(e)}")
            
            return True
            
        except ImportError as e:
            self.log_issue("Import", f"Cannot import SupabaseDatabase: {e}")
            return False
        except Exception as e:
            self.log_issue("Connection", f"Supabase connection failed: {e}")
            return False
    
    def _check_regime_coverage(self, df: pd.DataFrame, symbol: str):
        """Check if data covers key market regime periods"""
        regimes = {
            'crash_2022': ('2022-03-01', '2022-10-31'),
            'recovery_2023': ('2022-11-01', '2023-12-31'),
            'bull_2024': ('2024-01-01', '2024-12-31'),
        }
        
        df['ts'] = pd.to_datetime(df['ts'])
        min_date = df['ts'].min()
        max_date = df['ts'].max()
        
        for regime_name, (start, end) in regimes.items():
            start_dt = pd.to_datetime(start)
            end_dt = pd.to_datetime(end)
            
            has_coverage = (min_date <= start_dt) and (max_date >= end_dt)
            
            if has_coverage:
                regime_data = df[(df['ts'] >= start_dt) & (df['ts'] <= end_dt)]
                self.log_success("Regime Coverage", 
                    f"{symbol}: {regime_name} - {len(regime_data)} bars")
            else:
                self.log_warning("Regime Coverage", 
                    f"{symbol}: {regime_name} - NO COVERAGE "
                    f"(data: {min_date.date()} to {max_date.date()})")
    
    # ========================================================================
    # SECTION 2: DATA CLEANING AUDIT
    # ========================================================================
    
    def audit_data_cleaning(self) -> bool:
        """Audit the DataCleaner class and its processes"""
        logger.info("\n" + "="*80)
        logger.info("SECTION 2: DATA CLEANING PROCESS AUDIT")
        logger.info("="*80)
        
        try:
            from src.data.data_cleaner import DataCleaner
            from src.data.supabase_db import SupabaseDatabase
            
            self.log_success("Import", "DataCleaner imported successfully")
            
            # Get sample data
            db = SupabaseDatabase()
            df = db.fetch_ohlc_bars('AAPL', timeframe='d1', limit=500)
            
            if df is None or len(df) < 100:
                self.log_issue("Sample Data", "Insufficient data for cleaning test")
                return False
            
            logger.info(f"\nTesting with {len(df)} bars of AAPL data...")
            
            # Test 1: Check for duplicate removal
            original_len = len(df)
            df_clean = DataCleaner.remove_duplicates(df)
            
            if len(df_clean) < original_len:
                self.log_success("Duplicates", 
                    f"Removed {original_len - len(df_clean)} duplicate rows")
            else:
                self.log_success("Duplicates", "No duplicates found")
            
            # Test 2: Check for NaN handling
            df_with_nans = df_clean.copy()
            # Inject some NaN values for testing
            df_with_nans.loc[df_with_nans.index[:5], 'close'] = np.nan
            
            df_no_nans = DataCleaner.handle_missing_values(df_with_nans)
            
            remaining_nans = df_no_nans['close'].isna().sum()
            if remaining_nans == 0:
                self.log_success("NaN Handling", "All NaN values handled correctly")
            else:
                self.log_warning("NaN Handling", 
                    f"{remaining_nans} NaN values remain after cleaning")
            
            # Test 3: Check outlier detection
            df_outliers = DataCleaner.detect_outliers(df_clean)
            
            if 'is_outlier' in df_outliers.columns:
                outlier_count = df_outliers['is_outlier'].sum()
                outlier_pct = outlier_count / len(df_outliers) * 100
                
                if outlier_pct > 10:
                    self.log_warning("Outliers", 
                        f"{outlier_pct:.1f}% outliers detected (may be too aggressive)")
                elif outlier_pct > 0:
                    self.log_success("Outliers", 
                        f"{outlier_count} outliers detected ({outlier_pct:.1f}%)")
                else:
                    self.log_success("Outliers", "No outliers detected")
            else:
                self.log_warning("Outliers", "No outlier column added")
            
            # Test 4: Full cleaning pipeline
            try:
                df_fully_clean = DataCleaner.clean_all(df, verbose=False)
                
                # Validate cleaned data
                issues = []
                
                # Check for NaN in critical columns
                for col in ['close', 'open', 'high', 'low']:
                    if col in df_fully_clean.columns:
                        if df_fully_clean[col].isna().any():
                            issues.append(f"{col} has NaN values")
                
                # Check for zero/negative prices
                for col in ['close', 'open', 'high', 'low']:
                    if col in df_fully_clean.columns:
                        if (df_fully_clean[col] <= 0).any():
                            issues.append(f"{col} has zero/negative values")
                
                # Check high/low relationship
                if 'high' in df_fully_clean.columns and 'low' in df_fully_clean.columns:
                    if (df_fully_clean['high'] < df_fully_clean['low']).any():
                        issues.append("High < Low in some rows")
                
                # Check for extreme returns
                if 'close' in df_fully_clean.columns:
                    returns = df_fully_clean['close'].pct_change()
                    extreme_returns = (returns.abs() > 0.5).sum()
                    if extreme_returns > 0:
                        self.log_warning("Data Quality", 
                            f"{extreme_returns} days with >50% returns (check for splits)")
                
                if issues:
                    for issue in issues:
                        self.log_issue("Clean All", issue)
                else:
                    self.log_success("Clean All", 
                        f"Full cleaning pipeline works correctly ({len(df_fully_clean)} bars)")
                
            except Exception as e:
                self.log_issue("Clean All", f"Full pipeline failed: {e}")
            
            return True
            
        except ImportError as e:
            self.log_issue("Import", f"Cannot import DataCleaner: {e}")
            return False
        except Exception as e:
            self.log_issue("Data Cleaning", f"Unexpected error: {e}")
            return False
    
    # ========================================================================
    # SECTION 3: FEATURE ENGINEERING AUDIT
    # ========================================================================
    
    def audit_feature_engineering(self) -> bool:
        """Audit indicator calculations and feature engineering"""
        logger.info("\n" + "="*80)
        logger.info("SECTION 3: FEATURE ENGINEERING AUDIT")
        logger.info("="*80)
        
        try:
            from src.data.supabase_db import SupabaseDatabase
            from src.data.data_cleaner import DataCleaner
            
            # Get sufficient data
            db = SupabaseDatabase()
            df = db.fetch_ohlc_bars('AAPL', timeframe='d1', limit=500)
            df = DataCleaner.clean_all(df, verbose=False)
            
            if len(df) < 250:
                self.log_warning("Feature Test", 
                    f"Only {len(df)} bars for feature test (need 250+)")
            
            # Check if indicators are being calculated
            indicator_cols = [col for col in df.columns 
                            if any(ind in col.lower() for ind in 
                                   ['sma', 'ema', 'rsi', 'macd', 'atr', 'bb'])]
            
            if len(indicator_cols) == 0:
                self.log_issue("Indicators", 
                    "NO technical indicators found in data - "
                    "indicators may not be calculating automatically")
                
                # Try to add indicators manually
                try:
                    import talib
                    
                    # Test basic indicators
                    df['sma_20'] = talib.SMA(df['close'].values, timeperiod=20)
                    df['rsi_14'] = talib.RSI(df['close'].values, timeperiod=14)
                    df['atr_14'] = talib.ATR(
                        df['high'].values, 
                        df['low'].values, 
                        df['close'].values, 
                        timeperiod=14
                    )
                    
                    # Check if they calculated
                    test_indicators = ['sma_20', 'rsi_14', 'atr_14']
                    for ind in test_indicators:
                        nan_pct = df[ind].isna().sum() / len(df) * 100
                        if nan_pct < 50:
                            self.log_success("Indicators", 
                                f"{ind} calculated ({nan_pct:.1f}% NaN)")
                        else:
                            self.log_warning("Indicators", 
                                f"{ind} mostly NaN ({nan_pct:.1f}%)")
                    
                except ImportError:
                    self.log_issue("TA-Lib", 
                        "TA-Lib not installed - cannot calculate indicators")
                except Exception as e:
                    self.log_issue("Indicators", f"Manual calculation failed: {e}")
                    
            else:
                self.log_success("Indicators", 
                    f"Found {len(indicator_cols)} indicator columns: "
                    f"{indicator_cols[:5]}...")
                
                # Check indicator quality
                for col in indicator_cols[:10]:  # Check first 10
                    nan_pct = df[col].isna().sum() / len(df) * 100
                    
                    if nan_pct > 80:
                        self.log_warning("Indicator Quality", 
                            f"{col}: {nan_pct:.1f}% NaN (likely broken)")
                    elif nan_pct > 50:
                        self.log_warning("Indicator Quality", 
                            f"{col}: {nan_pct:.1f}% NaN (needs more data)")
                    else:
                        non_nan = df[col].dropna()
                        if len(non_nan) > 0 and non_nan.std() == 0:
                            self.log_warning("Indicator Quality", 
                                f"{col}: Static value {non_nan.iloc[0]}")
            
            # Check for feature leakage (future data in past rows)
            self._check_feature_leakage(df)
            
            return True
            
        except Exception as e:
            self.log_issue("Feature Engineering", f"Audit failed: {e}")
            return False
    
    def _check_feature_leakage(self, df: pd.DataFrame):
        """Check for potential feature leakage issues"""
        
        # Check if any features have future information
        if 'close' in df.columns:
            # Calculate returns
            returns_1d = df['close'].pct_change()
            
            # Check if any indicator is too correlated with future returns
            future_returns = returns_1d.shift(-5)  # 5 days ahead
            
            leakage_features = []
            for col in df.select_dtypes(include=[np.number]).columns:
                if col in ['close', 'open', 'high', 'low', 'volume', 'ts']:
                    continue
                
                try:
                    corr = df[col].corr(future_returns)
                    if abs(corr) > 0.7:  # Very high correlation with future
                        leakage_features.append((col, corr))
                except:
                    pass
            
            if leakage_features:
                self.log_warning("Feature Leakage", 
                    f"Found {len(leakage_features)} features with >0.7 correlation "
                    f"to future returns: {[f[0] for f in leakage_features[:3]]}")
            else:
                self.log_success("Feature Leakage", 
                    "No obvious feature leakage detected")
    
    # ========================================================================
    # SECTION 4: ML MODEL STRUCTURE AUDIT
    # ========================================================================
    
    def audit_ml_models(self) -> bool:
        """Audit ML model implementations"""
        logger.info("\n" + "="*80)
        logger.info("SECTION 4: ML MODEL STRUCTURE AUDIT")
        logger.info("="*80)
        
        # Check XGBoost implementation
        try:
            from src.models.xgboost_forecaster import XGBoostForecaster
            
            self.log_success("Import", "XGBoostForecaster imported")
            
            # Test instantiation
            model = XGBoostForecaster()
            self.log_success("XGBoost", "Model instantiated successfully")
            
            # Check if prepare_training_data_binary exists
            if hasattr(model, 'prepare_training_data_binary'):
                self.log_success("XGBoost", "Binary classification method exists")
            else:
                self.log_issue("XGBoost", 
                    "Missing prepare_training_data_binary method")
            
            # Check if train method exists
            if hasattr(model, 'train'):
                self.log_success("XGBoost", "Training method exists")
            else:
                self.log_issue("XGBoost", "Missing train method")
            
            # Check if predict_proba exists
            if hasattr(model, 'predict_proba'):
                self.log_success("XGBoost", "Prediction method exists")
            else:
                self.log_issue("XGBoost", "Missing predict_proba method")
                
        except ImportError as e:
            self.log_issue("XGBoost", f"Cannot import XGBoostForecaster: {e}")
        except Exception as e:
            self.log_issue("XGBoost", f"Model check failed: {e}")
        
        # Check ARIMA implementation
        try:
            from src.models.arima_garch_forecaster import ARIMAGARCHForecaster
            
            self.log_success("Import", "ARIMAGARCHForecaster imported")
            
            model = ARIMAGARCHForecaster()
            self.log_success("ARIMA", "Model instantiated successfully")
            
            # Check required methods
            required_methods = ['fit', 'predict', 'predict_proba']
            for method in required_methods:
                if hasattr(model, method):
                    self.log_success("ARIMA", f"{method} method exists")
                else:
                    self.log_warning("ARIMA", f"Missing {method} method")
                    
        except ImportError as e:
            self.log_warning("ARIMA", f"Cannot import ARIMAGARCHForecaster: {e}")
        except Exception as e:
            self.log_warning("ARIMA", f"Model check failed: {e}")
        
        # Check TabPFN if available
        try:
            from tabpfn import TabPFNClassifier
            self.log_success("TabPFN", "TabPFN available for testing")
        except ImportError:
            self.log_warning("TabPFN", 
                "TabPFN not installed (optional for regime testing)")
        
        return True
    
    # ========================================================================
    # SECTION 5: TRAINING PIPELINE AUDIT
    # ========================================================================
    
    def audit_training_pipeline(self) -> bool:
        """Test the complete training pipeline end-to-end"""
        logger.info("\n" + "="*80)
        logger.info("SECTION 5: END-TO-END TRAINING PIPELINE TEST")
        logger.info("="*80)
        
        try:
            from src.data.supabase_db import SupabaseDatabase
            from src.data.data_cleaner import DataCleaner
            from src.models.xgboost_forecaster import XGBoostForecaster
            
            # Get data
            db = SupabaseDatabase()
            df = db.fetch_ohlc_bars('AAPL', timeframe='d1', limit=500)
            
            if df is None or len(df) < 200:
                self.log_issue("Pipeline Test", 
                    f"Insufficient data for pipeline test (need 200+, got {len(df) if df is not None else 0})")
                return False
            
            self.log_success("Pipeline", f"Loaded {len(df)} bars for testing")
            
            # Clean data
            df = DataCleaner.clean_all(df, verbose=False)
            self.log_success("Pipeline", "Data cleaning completed")
            
            # Prepare features
            model = XGBoostForecaster()
            
            try:
                X, y = model.prepare_training_data_binary(
                    df,
                    horizon_days=5,
                    threshold_pct=0.015
                )
                
                self.log_success("Pipeline", 
                    f"Features prepared: X={X.shape}, y={y.shape}")
                
                # Check feature quality
                if X.shape[0] < 100:
                    self.log_warning("Pipeline", 
                        f"Only {X.shape[0]} samples (need 100+ for robust training)")
                
                # Check for NaN in features
                nan_cols = X.columns[X.isna().any()].tolist()
                if nan_cols:
                    self.log_warning("Pipeline", 
                        f"{len(nan_cols)} features have NaN: {nan_cols[:5]}...")
                else:
                    self.log_success("Pipeline", "No NaN values in features")
                
                # Check for infinite values
                inf_cols = X.columns[np.isinf(X).any()].tolist()
                if inf_cols:
                    self.log_warning("Pipeline", 
                        f"{len(inf_cols)} features have Inf: {inf_cols[:5]}...")
                else:
                    self.log_success("Pipeline", "No Inf values in features")
                
                # Check target distribution (y may be "bullish"/"bearish" or 0/1)
                if hasattr(y, 'dtype') and np.issubdtype(getattr(y.dtype, 'type', type(None)), np.number):
                    pos_pct = float(y.sum()) / len(y) * 100
                else:
                    pos_pct = (y == "bullish").sum() / len(y) * 100 if len(y) else 0
                self.log_success("Pipeline", 
                    f"Target distribution: {pos_pct:.1f}% positive, "
                    f"{100-pos_pct:.1f}% negative")
                
                if pos_pct < 30 or pos_pct > 70:
                    self.log_warning("Pipeline", 
                        f"Imbalanced target ({pos_pct:.1f}% positive)")
                
                # Try training
                split_idx = int(len(X) * 0.8)
                X_train = X.iloc[:split_idx]
                X_test = X.iloc[split_idx:]
                y_train = y.iloc[:split_idx]
                y_test = y.iloc[split_idx:]
                
                self.log_success("Pipeline", 
                    f"Train/test split: {len(X_train)}/{len(X_test)}")
                
                # Train model
                model.train(X_train, y_train)
                self.log_success("Pipeline", "Model training completed")
                
                # Make predictions
                y_pred_proba = model.predict_proba(X_test)
                
                if y_pred_proba is None or len(y_pred_proba) == 0:
                    self.log_issue("Pipeline", "Model returned no predictions")
                else:
                    # Calculate accuracy (y_test may be "bullish"/"bearish"; y_pred is 0/1)
                    # predict_proba may return (n,) P(bullish) or (n, 2) [P(bearish), P(bullish)]
                    p_bull = y_pred_proba[:, 1] if getattr(y_pred_proba, 'ndim', 0) == 2 else np.asarray(y_pred_proba)
                    y_pred = (p_bull > 0.5).astype(int)
                    y_test_vals = np.asarray(y_test)
                    if hasattr(y_test_vals, 'dtype') and not np.issubdtype(getattr(y_test_vals.dtype, 'type', type(None)), np.number):
                        y_test_bin = np.where(np.asarray([str(v).lower() for v in y_test_vals]) == "bullish", 1, 0)
                    else:
                        y_test_bin = np.asarray(y_test_vals).ravel()
                    accuracy = (y_pred == y_test_bin).mean()
                    
                    self.log_success("Pipeline", 
                        f"Predictions generated: accuracy = {accuracy:.1%}")
                    
                    if accuracy < 0.45:
                        self.log_warning("Pipeline", 
                            "Accuracy < 45% - model may not be learning properly")
                    elif accuracy > 0.60:
                        self.log_warning("Pipeline", 
                            "Accuracy > 60% - check for data leakage")
                
            except Exception as e:
                self.log_issue("Pipeline", f"Feature preparation failed: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                return False
            
            return True
            
        except Exception as e:
            self.log_issue("Pipeline", f"End-to-end test failed: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    # ========================================================================
    # SECTION 6: REGIME-SPECIFIC TESTING AUDIT
    # ========================================================================
    
    def audit_regime_testing_readiness(self) -> bool:
        """Check if system is ready for regime-based testing"""
        logger.info("\n" + "="*80)
        logger.info("SECTION 6: REGIME TESTING READINESS")
        logger.info("="*80)
        
        try:
            from src.data.supabase_db import SupabaseDatabase
            from src.data.data_cleaner import DataCleaner
            
            db = SupabaseDatabase()
            
            # Define regimes to test
            regimes = {
                'crash_2022': {
                    'start': '2022-03-01',
                    'end': '2022-10-31',
                    'name': 'Bear Market Crash'
                },
                'recovery_2023': {
                    'start': '2022-11-01',
                    'end': '2023-12-31',
                    'name': 'Post-Crash Recovery'
                },
                'bull_2024': {
                    'start': '2024-01-01',
                    'end': '2024-12-31',
                    'name': 'Bull Market'
                }
            }
            
            # Test stocks by category
            test_stocks = {
                'defensive': ['PG', 'KO'],
                'quality': ['MSFT', 'AMGN'],
                'growth': ['NVDA', 'MU']
            }
            
            for category, stocks in test_stocks.items():
                logger.info(f"\n{category.upper()} STOCKS:")
                
                for symbol in stocks:
                    try:
                        df = db.fetch_ohlc_bars(symbol, timeframe='d1', limit=2000)
                        
                        if df is None or len(df) == 0:
                            self.log_issue("Regime Test", 
                                f"{symbol}: No data available")
                            continue
                        
                        df = DataCleaner.clean_all(df, verbose=False)
                        df['ts'] = pd.to_datetime(df['ts'])
                        
                        # Check each regime
                        for regime_name, regime in regimes.items():
                            start = pd.to_datetime(regime['start'])
                            end = pd.to_datetime(regime['end'])
                            
                            regime_df = df[(df['ts'] >= start) & (df['ts'] <= end)]
                            
                            if len(regime_df) == 0:
                                self.log_warning("Regime Test", 
                                    f"{symbol} - {regime['name']}: NO DATA")
                            elif len(regime_df) < 50:
                                self.log_warning("Regime Test", 
                                    f"{symbol} - {regime['name']}: Only {len(regime_df)} bars")
                            else:
                                self.log_success("Regime Test", 
                                    f"{symbol} - {regime['name']}: {len(regime_df)} bars ✓")
                    
                    except Exception as e:
                        self.log_issue("Regime Test", 
                            f"{symbol}: Failed to load - {str(e)[:50]}")
            
            return True
            
        except Exception as e:
            self.log_issue("Regime Test", f"Readiness check failed: {e}")
            return False
    
    # ========================================================================
    # FINAL REPORT
    # ========================================================================
    
    def generate_report(self):
        """Generate final audit report"""
        logger.info("\n\n" + "="*80)
        logger.info("📋 PIPELINE AUDIT REPORT")
        logger.info("="*80)
        
        logger.info(f"\n✅ SUCCESSES: {len(self.successes)}")
        for success in self.successes:
            logger.info(f"  {success}")
        
        logger.info(f"\n⚠️  WARNINGS: {len(self.warnings)}")
        for warning in self.warnings:
            logger.info(f"  {warning}")
        
        logger.info(f"\n❌ CRITICAL ISSUES: {len(self.issues)}")
        for issue in self.issues:
            logger.info(f"  {issue}")
        
        # Overall assessment
        logger.info("\n" + "="*80)
        logger.info("OVERALL ASSESSMENT")
        logger.info("="*80)
        
        if len(self.issues) == 0 and len(self.warnings) <= 3:
            logger.info("✅ READY FOR REGIME TESTING")
            logger.info("   Your pipeline is properly structured for market regime analysis.")
        elif len(self.issues) == 0:
            logger.info("⚠️  READY WITH CAVEATS")
            logger.info(f"   {len(self.warnings)} warnings need attention, but can proceed.")
        else:
            logger.info("❌ NOT READY")
            logger.info(f"   {len(self.issues)} critical issues must be fixed first.")
        
        logger.info("\n" + "="*80)
        
        # Save detailed report
        report_path = '/tmp/pipeline_audit_report.txt'
        try:
            with open(report_path, 'w') as f:
                f.write("SwiftBolt ML Pipeline Audit Report\n")
                f.write("="*80 + "\n\n")
                
                f.write(f"SUCCESSES ({len(self.successes)}):\n")
                for s in self.successes:
                    f.write(f"  {s}\n")
                
                f.write(f"\nWARNINGS ({len(self.warnings)}):\n")
                for w in self.warnings:
                    f.write(f"  {w}\n")
                
                f.write(f"\nCRITICAL ISSUES ({len(self.issues)}):\n")
                for i in self.issues:
                    f.write(f"  {i}\n")
            
            logger.info(f"📄 Detailed report saved to: {report_path}")
        except:
            pass


def main():
    """Run complete pipeline audit. Use --section to run specific sections (1-6)."""
    import argparse
    parser = argparse.ArgumentParser(
        description="Pipeline audit for regime testing. Sections: 1=Data, 2=Cleaning, 3=Features, 4=ML structure, 5=Training, 6=Regime readiness."
    )
    parser.add_argument(
        "--section",
        type=int,
        choices=[1, 2, 3, 4, 5, 6],
        default=None,
        help="Run only this section (default: all)",
    )
    args = parser.parse_args()

    print("""
╔════════════════════════════════════════════════════════════════════════╗
║           SwiftBolt ML - Pipeline Audit & Validation                   ║
║                                                                        ║
║  This script validates your data pipeline and ML processes to ensure  ║
║  everything is properly structured for market regime-aware testing.   ║
╚════════════════════════════════════════════════════════════════════════╝
    """)

    auditor = PipelineAuditor()
    run_all = args.section is None

    if run_all or args.section == 1:
        auditor.audit_supabase_connection()
    if run_all or args.section == 2:
        auditor.audit_data_cleaning()
    if run_all or args.section == 3:
        auditor.audit_feature_engineering()
    if run_all or args.section == 4:
        auditor.audit_ml_models()
    if run_all or args.section == 5:
        auditor.audit_training_pipeline()
    if run_all or args.section == 6:
        auditor.audit_regime_testing_readiness()

    auditor.generate_report()


if __name__ == '__main__':
    main()
