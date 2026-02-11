#!/usr/bin/env python3
"""
Kaggle-Inspired Hybrid: BiLSTM + XGBoost Residuals + Prophet
Weighted ensemble integration

Phase 6.1: LSTM-XGBoost Residual Refinement + Prophet Baseline
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, Union
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Optional imports with graceful fallbacks
try:
    from tensorflow.keras import Sequential, layers
    from tensorflow.keras.callbacks import EarlyStopping
    import tensorflow as tf
    TF_AVAILABLE = True
    logger.info(f"✅ TensorFlow {tf.__version__} enabled (BiLSTM wave features active)")
except ImportError:
    TF_AVAILABLE = False
    logger.info("⚠️ TensorFlow not available - BiLSTM features disabled (install: pip install tensorflow)")

try:
    from xgboost import XGBRegressor
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False
    logger.warning("❌ XGBoost not available")

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
    logger.info("✅ Prophet enabled (seasonal forecasting active)")
except ImportError:
    PROPHET_AVAILABLE = False
    logger.info("⚠️ Prophet not available - seasonal features disabled (install: pip install prophet)")


def create_sequences(
    features: pd.DataFrame,
    targets: pd.Series,
    sequence_length: int = 30,
    step_size: int = 1
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Convert 2D feature DataFrame to 3D sequences for LSTM/BiLSTM.
    
    Args:
        features: DataFrame with shape (N, feature_count)
        targets: Series with shape (N,)
        sequence_length: Number of time steps per sequence (default: 30)
        step_size: Step size between sequences (default: 1)
    
    Returns:
        X: Array with shape (num_sequences, sequence_length, feature_count)
        y: Array with shape (num_sequences,)
    """
    if len(features) != len(targets):
        raise ValueError(f"Features and targets must have same length: {len(features)} vs {len(targets)}")
    
    if len(features) < sequence_length:
        raise ValueError(f"Insufficient data: need at least {sequence_length} rows, got {len(features)}")
    
    # Convert to numpy arrays
    feature_values = features.values
    target_values = targets.values
    
    # Ensure numeric types
    if not np.issubdtype(feature_values.dtype, np.number):
        raise ValueError("Features must be numeric")
    
    X_sequences = []
    y_sequences = []
    
    for i in range(0, len(features) - sequence_length + 1, step_size):
        X_sequences.append(feature_values[i:i + sequence_length])
        y_sequences.append(target_values[i + sequence_length - 1])
    
    X = np.array(X_sequences)
    y = np.array(y_sequences)
    
    logger.info(f"Created sequences: X.shape={X.shape}, y.shape={y.shape}")
    return X, y


class KaggleProphetHybrid:
    """
    4-Model Weighted Ensemble:
    1. BiLSTM (bidirectional trends)
    2. XGBoost (residual correction)
    3. Transformer (attention - optional)
    4. Prophet (trend/seasonality)
    
    Kaggle-inspired two-stage approach:
    - Stage 1: BiLSTM captures trends and patterns
    - Stage 2: XGBoost refines by learning residuals
    - Prophet provides trend validation baseline
    - Transformer adds attention-based signals (optional)
    """
    
    def __init__(
        self,
        transformer_model=None,
        weights: Optional[list] = None,
        sequence_length: int = 30,
        bilstm_units: int = 50,
        bilstm_dropout: float = 0.2,
        prophet_regressors: Optional[list] = None,
        custom_holidays: Optional[pd.DataFrame] = None,
        use_uncertainty_intervals: bool = True,
        enable_multiscale: bool = False
    ):
        """
        Initialize Kaggle-Prophet Hybrid ensemble.
        
        Args:
            transformer_model: Optional transformer model (assumed to have predict method)
            weights: Ensemble weights [transformer, xgb, bilstm, prophet]. Default: [0.40, 0.30, 0.20, 0.10]
            sequence_length: Time steps per sequence for BiLSTM (default: 30)
            bilstm_units: Number of units in BiLSTM layers (default: 50)
            bilstm_dropout: Dropout rate for BiLSTM (default: 0.2)
            prophet_regressors: List of feature names to add as Prophet regressors (e.g., ['RSI', 'MACD'])
            custom_holidays: DataFrame with custom holidays (columns: 'holiday', 'ds')
            use_uncertainty_intervals: If True, use Prophet uncertainty bands for dynamic weighting
            enable_multiscale: If True, enable multi-timeframe patch segmentation
        """
        self.transformer = transformer_model
        
        # Default weights: Transformer (40%), XGBoost (30%), BiLSTM (20%), Prophet (10%)
        self.weights = weights or [0.40, 0.30, 0.20, 0.10]
        if abs(sum(self.weights) - 1.0) > 1e-6:
            raise ValueError(f"Weights must sum to 1.0, got {sum(self.weights)}")
        
        self.sequence_length = sequence_length
        self.bilstm_units = bilstm_units
        self.bilstm_dropout = bilstm_dropout
        
        # Prophet enhancements
        self.prophet_regressors = prophet_regressors or []
        self.custom_holidays = custom_holidays
        self.use_uncertainty_intervals = use_uncertainty_intervals
        self.enable_multiscale = enable_multiscale
        
        # Models (initialized in fit())
        self.bilstm_model = None
        self.xgb_model = None
        self.prophet_model = None
        
        # Cache for training predictions
        self.bilstm_train_preds = None
        self.y_train = None
        self.feature_count = None
        self.feature_names = None
        
        # Training status
        self.is_trained = False
    
    def _build_bilstm_model(self, input_shape: Tuple[int, int]):
        """
        Build BiLSTM model for trend/pattern capture.
        
        Args:
            input_shape: Tuple of (sequence_length, feature_count)
        
        Returns:
            Compiled Keras Sequential model
        """
        if not TF_AVAILABLE:
            raise ImportError("TensorFlow is required for BiLSTM model")
        
        model = Sequential([
            layers.Bidirectional(
                layers.LSTM(self.bilstm_units, return_sequences=True),
                input_shape=input_shape
            ),
            layers.Bidirectional(layers.LSTM(30)),
            layers.Dropout(self.bilstm_dropout),
            layers.Dense(10, activation='relu'),
            layers.Dense(1)
        ])
        
        model.compile(optimizer='adam', loss='mse', metrics=['mae'])
        return model
    
    def fit(
        self,
        X_train: Union[np.ndarray, pd.DataFrame],
        y_train: Union[np.ndarray, pd.Series],
        df_ohlcv: Optional[pd.DataFrame] = None,
        epochs: int = 50,
        batch_size: int = 32,
        validation_split: float = 0.1,
        verbose: int = 0
    ) -> 'KaggleProphetHybrid':
        """
        Train all components of the hybrid ensemble.
        
        Args:
            X_train: Training features. Can be:
                - 3D array: (N, sequence_length, features) - ready for BiLSTM
                - 2D DataFrame: Will be converted to sequences
            y_train: Training targets (N,)
            df_ohlcv: Raw OHLCV DataFrame for Prophet (required for Prophet training)
            epochs: Number of epochs for BiLSTM training
            batch_size: Batch size for BiLSTM training
            validation_split: Validation split for BiLSTM
            verbose: Verbosity level (0=silent, 1=progress)
        
        Returns:
            Self for method chaining
        """
        # Store original DataFrame for Prophet regressors (before sequence conversion)
        X_train_df_original = X_train if isinstance(X_train, pd.DataFrame) else None
        
        # Convert to numpy arrays
        if isinstance(X_train, pd.DataFrame):
            # Need to create sequences from 2D DataFrame
            if isinstance(y_train, pd.Series):
                y_train_array = y_train.values
            else:
                y_train_array = np.array(y_train)
            
            X_train_3d, y_train_array = create_sequences(
                X_train,
                pd.Series(y_train_array),
                sequence_length=self.sequence_length
            )
            logger.info(f"[KAGGLE-HYBRID] Converted DataFrame to sequences: {X_train_3d.shape}")
        else:
            X_train_3d = np.array(X_train)
            y_train_array = np.array(y_train) if not isinstance(y_train, np.ndarray) else y_train
        
        # Validate shapes
        if len(X_train_3d.shape) != 3:
            raise ValueError(f"X_train must be 3D (samples, timesteps, features), got shape {X_train_3d.shape}")
        
        if X_train_3d.shape[0] != len(y_train_array):
            raise ValueError(f"X_train and y_train must have same length: {X_train_3d.shape[0]} vs {len(y_train_array)}")
        
        self.feature_count = X_train_3d.shape[2]
        _, sequence_length, _ = X_train_3d.shape
        
        # 1. Train BiLSTM (Kaggle bidirectional pattern capture)
        if TF_AVAILABLE:
            logger.info("[KAGGLE-HYBRID] Training BiLSTM...")
            self.bilstm_model = self._build_bilstm_model(
                input_shape=(sequence_length, self.feature_count)
            )
            
            # Early stopping callback
            early_stop = EarlyStopping(
                monitor='val_loss',
                patience=10,
                restore_best_weights=True,
                verbose=verbose
            )
            
            self.bilstm_model.fit(
                X_train_3d,
                y_train_array,
                epochs=epochs,
                batch_size=batch_size,
                validation_split=validation_split,
                callbacks=[early_stop],
                verbose=verbose
            )
            
            self.bilstm_train_preds = self.bilstm_model.predict(X_train_3d, verbose=verbose).flatten()
            logger.info(f"[KAGGLE-HYBRID] BiLSTM training complete. Train preds shape: {self.bilstm_train_preds.shape}")
        else:
            logger.warning("[KAGGLE-HYBRID] TensorFlow not available. Skipping BiLSTM training.")
            # Create dummy predictions for compatibility
            self.bilstm_train_preds = np.zeros(len(y_train_array))
        
        self.y_train = y_train_array
        
        # 2. Train XGBoost on residuals (Kaggle two-stage technique)
        if XGB_AVAILABLE:
            logger.info("[KAGGLE-HYBRID] Training XGBoost on residuals...")
            residuals = y_train_array - self.bilstm_train_preds
            
            # Flatten 3D sequences to 2D for XGBoost
            X_2d = X_train_3d.reshape(X_train_3d.shape[0], -1)
            
            self.xgb_model = XGBRegressor(
                max_depth=5,
                learning_rate=0.05,
                n_estimators=100,
                subsample=0.8,
                random_state=42,
                n_jobs=-1
            )
            self.xgb_model.fit(X_2d, residuals)
            logger.info("[KAGGLE-HYBRID] XGBoost residual training complete")
        else:
            logger.warning("[KAGGLE-HYBRID] XGBoost not available. Skipping residual correction.")
            self.xgb_model = None
        
        # 3. Train Prophet baseline (trend/seasonality) with enhancements
        if PROPHET_AVAILABLE and df_ohlcv is not None:
            logger.info("[KAGGLE-HYBRID] Training Prophet with regressors and custom holidays...")
            try:
                # Prepare Prophet data format
                df_prophet = df_ohlcv.copy()
                
                # Find date/time column
                date_cols = [col for col in df_prophet.columns if 'date' in col.lower() or 'time' in col.lower()]
                if not date_cols:
                    # If no date column, create index-based dates
                    df_prophet['ds'] = pd.date_range(start='2020-01-01', periods=len(df_prophet), freq='D')
                else:
                    df_prophet['ds'] = pd.to_datetime(df_prophet[date_cols[0]])
                
                # Find close price column
                close_cols = [col for col in df_prophet.columns if 'close' in col.lower()]
                if not close_cols:
                    raise ValueError("No 'close' column found in df_ohlcv")
                
                df_prophet['y'] = df_prophet[close_cols[0]]
                
                # Multi-scale: Add daily aggregates if enabled
                if self.enable_multiscale:
                    # Create daily aggregates (for Prophet daily input)
                    df_prophet['daily_high'] = df_prophet.get('high', df_prophet['y'])
                    df_prophet['daily_low'] = df_prophet.get('low', df_prophet['y'])
                    df_prophet['daily_volume'] = df_prophet.get('volume', 0)
                    logger.info("[KAGGLE-HYBRID] Multi-scale features added for Prophet")
                
                # Initialize Prophet with custom holidays if provided
                prophet_params = {
                    'changepoint_prior_scale': 0.05,
                    'seasonality_prior_scale': 10.0,
                    'yearly_seasonality': True,
                    'weekly_seasonality': True,
                    'daily_seasonality': False  # Usually too noisy for daily stock data
                }
                
                # Add holidays if provided
                if self.custom_holidays is not None and len(self.custom_holidays) > 0:
                    # Ensure holidays DataFrame has correct format
                    if 'ds' not in self.custom_holidays.columns:
                        raise ValueError("Custom holidays must have 'ds' column (dates)")
                    if 'holiday' not in self.custom_holidays.columns:
                        self.custom_holidays['holiday'] = 'custom_event'
                    self.prophet_model = Prophet(**prophet_params, holidays=self.custom_holidays)
                    logger.info(f"[KAGGLE-HYBRID] Added {len(self.custom_holidays)} custom holidays")
                else:
                    self.prophet_model = Prophet(**prophet_params)
                
                # Add regressors (external variables + technical indicators)
                if X_train_df_original is not None:
                    # Use stored original DataFrame for regressors
                    feature_df = X_train_df_original
                    if feature_df is not None:
                        # Store feature names for later use
                        self.feature_names = list(feature_df.columns)
                        
                        # Add regressors from feature names
                        available_regressors = []
                        for regressor_name in self.prophet_regressors:
                            # Try various name variations
                            matching_cols = [col for col in feature_df.columns 
                                           if regressor_name.lower() in col.lower()]
                            if matching_cols and len(df_prophet) == len(feature_df):
                                # Align regressor with Prophet data
                                regressor_values = feature_df[matching_cols[0]].values
                                if len(regressor_values) == len(df_prophet):
                                    df_prophet[regressor_name] = regressor_values
                                    self.prophet_model.add_regressor(regressor_name)
                                    available_regressors.append(regressor_name)
                                    logger.info(f"[KAGGLE-HYBRID] Added Prophet regressor: {regressor_name}")
                        
                        # If no specific regressors, add top technical indicators automatically
                        if len(available_regressors) == 0 and len(feature_df.columns) > 0:
                            # Align lengths: feature_df may be shorter due to sequence creation
                            # Use the length of df_prophet as reference
                            feature_df_aligned = feature_df.iloc[:len(df_prophet)]
                            if len(feature_df_aligned) == len(df_prophet):
                                # Look for common technical indicators
                                common_indicators = ['rsi', 'macd', 'kdj', 'volume', 'ma_', 'std_']
                                for indicator in common_indicators:
                                    matching_cols = [col for col in feature_df_aligned.columns 
                                                   if indicator.lower() in col.lower()]
                                    if matching_cols:
                                        col_name = matching_cols[0]
                                        if col_name not in df_prophet.columns:
                                            df_prophet[col_name] = feature_df_aligned[col_name].values
                                            self.prophet_model.add_regressor(col_name)
                                            available_regressors.append(col_name)
                                            logger.info(f"[KAGGLE-HYBRID] Auto-added regressor: {col_name}")
                                            if len(available_regressors) >= 5:  # Limit to 5 to avoid overfitting
                                                break
                            else:
                                logger.warning(f"[KAGGLE-HYBRID] Length mismatch: features={len(feature_df)}, prophet={len(df_prophet)}")
                
                # Prepare final DataFrame for Prophet (ds, y, + regressors)
                regressor_cols = [col for col in df_prophet.columns 
                                if col not in ['ds', 'y', 'daily_high', 'daily_low', 'daily_volume']]
                prophet_cols = ['ds', 'y'] + regressor_cols
                df_prophet_clean = df_prophet[prophet_cols].copy()
                df_prophet_clean = df_prophet_clean.dropna()
                
                if len(df_prophet_clean) < 30:
                    logger.warning(f"[KAGGLE-HYBRID] Insufficient Prophet data: {len(df_prophet_clean)} rows")
                    self.prophet_model = None
                else:
                    self.prophet_model.fit(df_prophet_clean)
                    logger.info(f"[KAGGLE-HYBRID] Prophet training complete with {len(available_regressors)} regressors")
            except Exception as e:
                logger.error(f"[KAGGLE-HYBRID] Prophet training failed: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                self.prophet_model = None
        else:
            if df_ohlcv is None:
                logger.warning("[KAGGLE-HYBRID] df_ohlcv not provided. Skipping Prophet training.")
            if not PROPHET_AVAILABLE:
                logger.warning("[KAGGLE-HYBRID] Prophet not available. Skipping Prophet training.")
            self.prophet_model = None
        
        self.is_trained = True
        logger.info("[KAGGLE-HYBRID] ✅ All models trained")
        return self
    
    def predict(
        self,
        X_test: Union[np.ndarray, pd.DataFrame],
        df_ohlcv_test: Optional[pd.DataFrame] = None,
        transformer_pred: Optional[np.ndarray] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate weighted ensemble predictions.
        
        Args:
            X_test: Test features. Can be:
                - 3D array: (N, sequence_length, features)
                - 2D DataFrame: Will be converted to sequences
            df_ohlcv_test: Raw OHLCV DataFrame for Prophet predictions
            transformer_pred: Optional pre-computed transformer predictions
        
        Returns:
            Tuple of (signals, confidence):
            - signals: Array of -1, 0, or 1 (sell, hold, buy)
            - confidence: Array of confidence scores [0-1]
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction. Call fit() first.")
        
        # Convert to numpy arrays and handle 2D -> 3D conversion
        if isinstance(X_test, pd.DataFrame):
            # For prediction, we need to handle differently
            # If DataFrame, assume we need to create sequences
            # This is a simplified approach - in practice you'd want to maintain state
            logger.warning("[KAGGLE-HYBRID] DataFrame input - converting to sequences. Ensure proper alignment.")
            # For now, create sequences with step_size=1
            # This requires targets which we don't have - will use dummy targets
            dummy_targets = pd.Series(np.zeros(len(X_test)))
            X_test_3d, _ = create_sequences(
                X_test,
                dummy_targets,
                sequence_length=self.sequence_length,
                step_size=1
            )
        else:
            X_test_3d = np.array(X_test)
        
        if len(X_test_3d.shape) != 3:
            raise ValueError(f"X_test must be 3D (samples, timesteps, features), got shape {X_test_3d.shape}")
        
        num_samples = X_test_3d.shape[0]
        
        # Store original X_test DataFrame reference if available (for Prophet regressors)
        X_test_df_original = X_test if isinstance(X_test, pd.DataFrame) else None
        
        # 1. BiLSTM prediction
        if self.bilstm_model is not None:
            bilstm_pred = self.bilstm_model.predict(X_test_3d, verbose=0).flatten()
        else:
            bilstm_pred = np.zeros(num_samples)
            logger.warning("[KAGGLE-HYBRID] BiLSTM model not available. Using zeros.")
        
        # 2. XGBoost residual correction
        if self.xgb_model is not None:
            X_2d = X_test_3d.reshape(X_test_3d.shape[0], -1)
            xgb_correction = self.xgb_model.predict(X_2d)
            xgb_pred = bilstm_pred + xgb_correction  # Refined output (two-stage approach)
        else:
            xgb_pred = bilstm_pred.copy()
            logger.warning("[KAGGLE-HYBRID] XGBoost model not available. Using BiLSTM only.")
        
        # 3. Transformer prediction (optional)
        if self.transformer is not None:
            if transformer_pred is None:
                try:
                    # Assume transformer accepts 3D input
                    if hasattr(self.transformer, 'predict'):
                        trans_pred = self.transformer.predict(X_test_3d).flatten()
                    else:
                        logger.warning("[KAGGLE-HYBRID] Transformer has no predict method")
                        trans_pred = np.zeros(num_samples)
                except Exception as e:
                    logger.warning(f"[KAGGLE-HYBRID] Transformer prediction failed: {e}")
                    trans_pred = np.zeros(num_samples)
            else:
                trans_pred = np.array(transformer_pred).flatten()
        else:
            trans_pred = np.zeros(num_samples)
        
        # 4. Prophet signal (trend/seasonality forecast) with uncertainty intervals
        prophet_signal = np.zeros(num_samples)
        prophet_weight_dynamic = self.weights[3]  # Base Prophet weight
        if self.prophet_model is not None and df_ohlcv_test is not None:
            try:
                # Get the last known close price from training data (baseline)
                last_training_close = self.prophet_model.history['y'].iloc[-1] if len(self.prophet_model.history) > 0 else None
                
                # Create future dataframe for the test period
                future_periods = max(num_samples, len(df_ohlcv_test) if hasattr(df_ohlcv_test, '__len__') else num_samples)
                future = self.prophet_model.make_future_dataframe(periods=future_periods, include_history=False)
                
                # Add external regressors if provided in test data
                if X_test_df_original is not None and self.feature_names:
                    # Add regressors to future dataframe
                    for regressor_name in self.prophet_regressors:
                        if regressor_name in X_test_df_original.columns:
                            # Use last values or extend with forward fill
                            regressor_values = X_test_df_original[regressor_name].values
                            if len(regressor_values) >= future_periods:
                                future[regressor_name] = regressor_values[:future_periods]
                            else:
                                # Extend with last value
                                last_val = regressor_values[-1] if len(regressor_values) > 0 else 0
                                future[regressor_name] = np.concatenate([
                                    regressor_values,
                                    np.full(future_periods - len(regressor_values), last_val)
                                ])
                
                if len(future) > 0:
                    # Predict with uncertainty intervals if enabled
                    forecast = self.prophet_model.predict(future)
                    
                    if len(forecast) > 0:
                        # Get forecast values (trend predictions)
                        prophet_forecasts = forecast['yhat'].values[:num_samples]
                        
                        # Use uncertainty intervals for dynamic weighting
                        if self.use_uncertainty_intervals and 'yhat_lower' in forecast.columns and 'yhat_upper' in forecast.columns:
                            prophet_lower = forecast['yhat_lower'].values[:num_samples]
                            prophet_upper = forecast['yhat_upper'].values[:num_samples]
                            # Calculate uncertainty width (wider = less confident)
                            uncertainty_width = (prophet_upper - prophet_lower) / (np.abs(prophet_forecasts) + 1e-6)
                            # Normalize uncertainty (0-1, higher = less confident)
                            max_uncertainty = np.max(uncertainty_width) if np.max(uncertainty_width) > 0 else 1.0
                            uncertainty_normalized = uncertainty_width / max_uncertainty
                            # Reduce Prophet weight if uncertainty is high (wide bands)
                            # High uncertainty -> low weight multiplier (0.5 to 1.0)
                            weight_multiplier = 1.0 - (uncertainty_normalized * 0.5)
                            prophet_weight_dynamic = self.weights[3] * weight_multiplier
                            logger.debug(f"[KAGGLE-HYBRID] Prophet uncertainty: mean={np.mean(uncertainty_width):.4f}, weight_mult={np.mean(weight_multiplier):.2f}")
                        
                        # Get actual close prices from test data for comparison
                        close_cols = [col for col in df_ohlcv_test.columns if 'close' in col.lower()]
                        
                        if close_cols and len(df_ohlcv_test) >= num_samples:
                            # Get baseline price (use first test close or last training close)
                            baseline_price = df_ohlcv_test[close_cols[0]].iloc[0] if len(df_ohlcv_test) > 0 else last_training_close
                            
                            if baseline_price is not None and baseline_price > 0:
                                # Convert to percentage change predictions
                                # Positive = upward trend, Negative = downward trend
                                prophet_signal = (prophet_forecasts - baseline_price) / baseline_price
                            else:
                                # Fallback: use forecast directly, normalized
                                mean_forecast = np.mean(prophet_forecasts)
                                if mean_forecast > 0:
                                    prophet_signal = (prophet_forecasts - mean_forecast) / mean_forecast
                                else:
                                    prophet_signal = prophet_forecasts
                        else:
                            # No test data available - use forecast relative to training baseline
                            if last_training_close is not None and last_training_close > 0:
                                prophet_signal = (prophet_forecasts - last_training_close) / last_training_close
                            else:
                                # Normalize forecasts to [-1, 1] range
                                mean_forecast = np.mean(prophet_forecasts)
                                std_forecast = np.std(prophet_forecasts)
                                if std_forecast > 0:
                                    prophet_signal = (prophet_forecasts - mean_forecast) / std_forecast
                                else:
                                    prophet_signal = prophet_forecasts - mean_forecast
                    else:
                        prophet_signal = np.zeros(num_samples)
                        logger.warning("[KAGGLE-HYBRID] Prophet forecast is empty")
                else:
                    prophet_signal = np.zeros(num_samples)
                    logger.warning("[KAGGLE-HYBRID] Prophet future dataframe is empty")
            except Exception as e:
                logger.warning(f"[KAGGLE-HYBRID] Prophet prediction failed: {e}")
                prophet_signal = np.zeros(num_samples)
        else:
            if df_ohlcv_test is None:
                logger.debug("[KAGGLE-HYBRID] df_ohlcv_test not provided for Prophet")
            else:
                logger.debug("[KAGGLE-HYBRID] Prophet model not available")
        
        # 5. Weighted ensemble with dynamic Prophet weighting
        # Normalize predictions to similar scales for voting
        preds = [trans_pred, xgb_pred, bilstm_pred, prophet_signal]
        max_abs = max([np.max(np.abs(p)) for p in preds if len(p) > 0], default=1.0)
        
        if max_abs > 0:
            # Scale to [-1, 1] range for voting
            scaled_preds = [
                p / max_abs if max_abs > 0 else p
                for p in preds
            ]
        else:
            scaled_preds = preds
        
        # Adjust weights: redistribute Prophet weight if it changed due to uncertainty
        weights_adjusted = list(self.weights)
        if prophet_weight_dynamic != self.weights[3]:
            weight_diff = self.weights[3] - prophet_weight_dynamic
            # Redistribute the difference proportionally to other models
            other_weights_sum = sum(self.weights[:3])
            if other_weights_sum > 0:
                for i in range(3):
                    weights_adjusted[i] += (weight_diff * self.weights[i] / other_weights_sum)
            weights_adjusted[3] = prophet_weight_dynamic
        
        # Renormalize weights
        weight_sum = sum(weights_adjusted)
        if weight_sum > 0:
            weights_adjusted = [w / weight_sum for w in weights_adjusted]
        
        ensemble_pred = (
            weights_adjusted[0] * scaled_preds[0] +
            weights_adjusted[1] * scaled_preds[1] +
            weights_adjusted[2] * scaled_preds[2] +
            weights_adjusted[3] * scaled_preds[3]
        )
        
        # Convert to signals: -1 (sell), 0 (hold), 1 (buy)
        signals = np.sign(ensemble_pred)
        
        # Calculate confidence (absolute value normalized to [0, 1])
        abs_ensemble = np.abs(ensemble_pred)
        max_confidence = np.max(abs_ensemble) if len(abs_ensemble) > 0 and np.max(abs_ensemble) > 0 else 1.0
        confidence = abs_ensemble / max_confidence
        confidence = np.clip(confidence, 0.0, 1.0)
        
        logger.info(f"[KAGGLE-HYBRID] Predictions: Ensemble mean={ensemble_pred.mean():.4f}, "
                   f"signals: buy={np.sum(signals == 1)}, sell={np.sum(signals == -1)}, hold={np.sum(signals == 0)}")
        
        return signals, confidence
    
    def get_model_info(self) -> Dict:
        """Get information about the trained models."""
        info = {
            'is_trained': self.is_trained,
            'weights': self.weights,
            'sequence_length': self.sequence_length,
            'feature_count': self.feature_count,
            'models': {
                'bilstm': self.bilstm_model is not None,
                'xgboost': self.xgb_model is not None,
                'prophet': self.prophet_model is not None,
                'transformer': self.transformer is not None
            }
        }
        return info
    
    def get_component_predictions(
        self,
        X_test: Union[np.ndarray, pd.DataFrame],
        df_ohlcv_test: Optional[pd.DataFrame] = None,
        transformer_pred: Optional[np.ndarray] = None
    ) -> Dict[str, np.ndarray]:
        """
        Get individual component predictions for visualization.
        
        Args:
            X_test: Test features
            df_ohlcv_test: Test OHLCV data
            transformer_pred: Optional pre-computed transformer predictions
        
        Returns:
            Dictionary with component predictions: {
                'transformer': array,
                'bilstm': array,
                'xgb': array,
                'xgb_refined': array,  # BiLSTM + XGBoost correction
                'prophet': array,
                'ensemble': array
            }
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction. Call fit() first.")
        
        # Store original X_test DataFrame reference if available
        X_test_df_original = X_test if isinstance(X_test, pd.DataFrame) else None
        
        # Convert to numpy arrays and handle 2D -> 3D conversion
        if isinstance(X_test, pd.DataFrame):
            dummy_targets = pd.Series(np.zeros(len(X_test)))
            X_test_3d, _ = create_sequences(
                X_test,
                dummy_targets,
                sequence_length=self.sequence_length,
                step_size=1
            )
        else:
            X_test_3d = np.array(X_test)
        
        if len(X_test_3d.shape) != 3:
            raise ValueError(f"X_test must be 3D (samples, timesteps, features), got shape {X_test_3d.shape}")
        
        num_samples = X_test_3d.shape[0]
        components = {}
        
        # 1. BiLSTM prediction
        if self.bilstm_model is not None:
            components['bilstm'] = self.bilstm_model.predict(X_test_3d, verbose=0).flatten()
        else:
            components['bilstm'] = np.zeros(num_samples)
        
        # 2. XGBoost residual correction
        if self.xgb_model is not None:
            X_2d = X_test_3d.reshape(X_test_3d.shape[0], -1)
            xgb_correction = self.xgb_model.predict(X_2d)
            components['xgb_correction'] = xgb_correction
            components['xgb_refined'] = components['bilstm'] + xgb_correction  # Two-stage output
        else:
            components['xgb_correction'] = np.zeros(num_samples)
            components['xgb_refined'] = components['bilstm']
        
        # 3. Transformer prediction
        if self.transformer is not None:
            if transformer_pred is None:
                try:
                    if hasattr(self.transformer, 'predict'):
                        components['transformer'] = self.transformer.predict(X_test_3d).flatten()
                    else:
                        components['transformer'] = np.zeros(num_samples)
                except Exception:
                    components['transformer'] = np.zeros(num_samples)
            else:
                components['transformer'] = np.array(transformer_pred).flatten()
        else:
            components['transformer'] = np.zeros(num_samples)
        
        # 4. Prophet signal
        prophet_signal = np.zeros(num_samples)
        if self.prophet_model is not None and df_ohlcv_test is not None:
            try:
                last_training_close = self.prophet_model.history['y'].iloc[-1] if len(self.prophet_model.history) > 0 else None
                future_periods = max(num_samples, len(df_ohlcv_test) if hasattr(df_ohlcv_test, '__len__') else num_samples)
                future = self.prophet_model.make_future_dataframe(periods=future_periods, include_history=False)
                
                if len(future) > 0:
                    forecast = self.prophet_model.predict(future)
                    if len(forecast) > 0:
                        prophet_forecasts = forecast['yhat'].values[:num_samples]
                        close_cols = [col for col in df_ohlcv_test.columns if 'close' in col.lower()]
                        
                        if close_cols and len(df_ohlcv_test) >= num_samples:
                            baseline_price = df_ohlcv_test[close_cols[0]].iloc[0] if len(df_ohlcv_test) > 0 else last_training_close
                            if baseline_price is not None and baseline_price > 0:
                                prophet_signal = (prophet_forecasts - baseline_price) / baseline_price
                            else:
                                mean_forecast = np.mean(prophet_forecasts)
                                if mean_forecast > 0:
                                    prophet_signal = (prophet_forecasts - mean_forecast) / mean_forecast
                                else:
                                    prophet_signal = prophet_forecasts
                        else:
                            if last_training_close is not None and last_training_close > 0:
                                prophet_signal = (prophet_forecasts - last_training_close) / last_training_close
            except Exception:
                prophet_signal = np.zeros(num_samples)
        
        components['prophet'] = prophet_signal
        
        # 5. Ensemble (weighted combination)
        preds = [components['transformer'], components['xgb_refined'], components['bilstm'], components['prophet']]
        max_abs = max([np.max(np.abs(p)) for p in preds if len(p) > 0], default=1.0)
        
        if max_abs > 0:
            scaled_preds = [p / max_abs if max_abs > 0 else p for p in preds]
        else:
            scaled_preds = preds
        
        components['ensemble'] = (
            self.weights[0] * scaled_preds[0] +
            self.weights[1] * scaled_preds[1] +
            self.weights[2] * scaled_preds[2] +
            self.weights[3] * scaled_preds[3]
        )
        
        return components

