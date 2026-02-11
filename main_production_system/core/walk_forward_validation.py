#!/usr/bin/env python3
"""
Walk-Forward Validation System
Implements rolling-window cross-validation for time series models.

This module provides comprehensive walk-forward validation for the Hybrid Ensemble
system, testing model performance across multiple time windows and market regimes.
All results are persistently stored in validation_results/ for historical analysis.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

# Try to import required components
try:
    from ..core.hybrid_ensemble import HybridEnsemble
    HYBRID_ENSEMBLE_AVAILABLE = True
except ImportError:
    try:
        # Fallback to alternative import path
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from hybrid_ensemble import HybridEnsemble
        HYBRID_ENSEMBLE_AVAILABLE = True
    except ImportError:
        HYBRID_ENSEMBLE_AVAILABLE = False

try:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'archive_v1_legacy'))
    from arima_garch_study_protocol import ARIMAGARCHStudyProtocol
    ARIMA_GARCH_AVAILABLE = True
except ImportError:
    ARIMA_GARCH_AVAILABLE = False

logger = logging.getLogger(__name__)

# Log warnings after logger is defined
if not ARIMA_GARCH_AVAILABLE:
    logger.warning("ARIMAGARCHStudyProtocol not available")
if not HYBRID_ENSEMBLE_AVAILABLE:
    logger.warning("HybridEnsemble not available")

try:
    from ..core.kdj_feature_engineer import KDJFeatureEngineer
    FEATURE_ENGINEER_AVAILABLE = True
except ImportError:
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from kdj_feature_engineer import KDJFeatureEngineer
        FEATURE_ENGINEER_AVAILABLE = True
    except ImportError:
        FEATURE_ENGINEER_AVAILABLE = False

if not FEATURE_ENGINEER_AVAILABLE:
    logger.warning("KDJFeatureEngineer not available")


@dataclass
class ValidationWindow:
    """Results for a single validation window."""
    window: int
    train_size: int
    test_start: str
    test_end: str
    mae: float
    rmse: float
    mape: float
    me: float  # Mean error
    directional_accuracy: float
    max_error: float
    volatility_regime: str  # 'STABLE' or 'HIGH_VOLATILITY'
    n_windows: int


@dataclass
class ValidationSummary:
    """Aggregated results across all validation windows."""
    ticker: str
    timestamp: str
    total_windows: int
    mean_mae: float
    std_mae: float
    mean_rmse: float
    std_rmse: float
    mean_mape: float
    mean_directional_accuracy: float
    stable_windows: int
    volatile_windows: int
    low_windows: int
    medium_windows: int
    high_windows: int
    mae_as_pct_of_price: float
    best_window: Dict[str, Any]
    worst_window: Dict[str, Any]
    window_results: List[Dict[str, Any]]


class WalkForwardValidator:
    """
    Rolling-window walk-forward validation for time series models.
    
    Implements the validation strategy recommended in:
    "Model Validation Techniques for Time Series" (Towards Data Science)
    
    Key features:
    - Multiple validation windows (not just one test set)
    - Expanding or rolling window strategies
    - Comprehensive performance metrics across regimes
    - Persistent storage of all validation results
    """
    
    def __init__(
        self,
        initial_train_size: int = 200,
        test_size: int = 15,
        step_size: int = 5,
        window_type: str = 'expanding',  # or 'rolling'
        storage_path: Path = Path('validation_results')
    ):
        """
        Initialize walk-forward validator.
        
        Args:
            initial_train_size: Size of initial training window (e.g., 200 days)
            test_size: Size of each test window (e.g., 15 days)
            step_size: How many periods to step forward each iteration (e.g., 5 days)
            window_type: 'expanding' (growing train set) or 'rolling' (fixed size)
            storage_path: Base directory for storing validation results
        """
        self.initial_train_size = initial_train_size
        self.test_size = test_size
        self.step_size = step_size
        self.window_type = window_type
        self.storage_path = Path(storage_path)
        
        # Create storage directories
        self.runs_path = self.storage_path / 'runs'
        self.history_path = self.storage_path / 'history'
        self.charts_path = self.storage_path / 'charts'
        
        for path in [self.runs_path, self.history_path, self.charts_path]:
            path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"WalkForwardValidator initialized with {window_type} windows")
        logger.info(f"Storage path: {self.storage_path}")
    
    def validate_ensemble(
        self,
        data: pd.DataFrame,
        ticker: str = 'UNKNOWN',
        ensemble: Optional[Any] = None,
        save_results: bool = True
    ) -> ValidationSummary:
        """
        Perform walk-forward validation on hybrid ensemble.
        
        Args:
            data: DataFrame with OHLC data (must have 'close' column)
            ticker: Ticker symbol for tracking
            ensemble: HybridEnsemble instance (optional)
            save_results: Whether to save results to persistent storage
        
        Returns:
            ValidationSummary with comprehensive metrics
        """
        if 'close' not in data.columns:
            raise ValueError("Data must contain 'close' column")
        
        prices = data['close'].values
        n = len(prices)
        
        logger.info(f"\n{'='*70}")
        logger.info(f"WALK-FORWARD VALIDATION: {ticker}")
        logger.info(f"{'='*70}")
        logger.info(f"Total data points: {n}")
        logger.info(f"Initial train size: {self.initial_train_size}")
        logger.info(f"Test size: {self.test_size}")
        logger.info(f"Step size: {self.step_size}")
        logger.info(f"Window type: {self.window_type}")
        
        # Calculate number of windows
        if n < self.initial_train_size + self.test_size:
            raise ValueError(
                f"Not enough data: {n} points. Need at least "
                f"{self.initial_train_size + self.test_size} points"
            )
        
        max_windows = (n - self.initial_train_size - self.test_size) // self.step_size + 1
        logger.info(f"Number of validation windows: {max_windows}\n")
        
        window_results = []
        
        for i in range(max_windows):
            # Define train/test indices
            train_end = self.initial_train_size + (i * self.step_size)
            test_start = train_end
            test_end = test_start + self.test_size
            
            if test_end > n:
                break
            
            # Extract windows
            if self.window_type == 'expanding':
                train_data = data.iloc[:train_end].copy()
            else:  # rolling
                train_start = train_end - self.initial_train_size
                train_data = data.iloc[train_start:train_end].copy()
            
            test_data = data.iloc[test_start:test_end].copy()
            
            logger.info(f"Window {i+1}/{max_windows}:")
            logger.info(f"  Train: {len(train_data)} obs")
            logger.info(f"  Test:  {len(test_data)} obs")
            
            try:
                # Detect volatility regime first
                volatility_regime = self._detect_volatility_regime(train_data['close'])
                
                # Generate ARIMA-GARCH predictions
                arima_forecast = self._get_arima_forecast(train_data, test_data)
                
                # Get XGBoost predictions if ensemble provided
                if ensemble and HYBRID_ENSEMBLE_AVAILABLE:
                    xgb_forecast = self._get_xgb_forecast(train_data, test_data, ensemble)
                else:
                    xgb_forecast = arima_forecast  # Fallback
                
                # Adaptive ensemble prediction based on volatility regime
                arima_w, xgb_w = self.get_adaptive_weights(volatility_regime)
                ensemble_forecast = arima_w * arima_forecast + xgb_w * xgb_forecast
                
                # Compute metrics
                actual = test_data['close'].values
                errors = actual - ensemble_forecast
                
                metrics = {
                    'window': i + 1,
                    'train_size': len(train_data),
                    'test_start': str(test_data.index[0]),
                    'test_end': str(test_data.index[-1]),
                    'mae': float(np.mean(np.abs(errors))),
                    'rmse': float(np.sqrt(np.mean(errors ** 2))),
                    'mape': float(np.mean(np.abs(errors / actual)) * 100),
                    'me': float(np.mean(errors)),
                    'directional_accuracy': self._calc_directional_accuracy(actual, ensemble_forecast),
                    'max_error': float(np.max(np.abs(errors))),
                    'volatility_regime': volatility_regime,
                    'n_windows': max_windows,
                    'avg_actual_price': float(actual.mean()),  # ✅ ADD THIS
                }
                
                window_results.append(metrics)
                
                logger.info(
                    f"  MAE: {metrics['mae']:.2f} | RMSE: {metrics['rmse']:.2f} | "
                    f"Dir Acc: {metrics['directional_accuracy']:.1f}% | "
                    f"Regime: {metrics['volatility_regime']}\n"
                )
                
            except Exception as e:
                logger.warning(f"  ⚠️ Error in window {i+1}: {e}\n")
                continue
        
        if not window_results:
            raise RuntimeError("No successful validation windows")
        
        # Aggregate results
        summary = self._aggregate_results(window_results, ticker)
        
        # Save results if requested
        if save_results:
            self.save_results(summary, ticker)
        
        return summary
    
    def _get_arima_forecast(self, train_data: pd.DataFrame, test_data: pd.DataFrame) -> np.ndarray:
        """Get ARIMA-GARCH forecast for test period."""
        if not ARIMA_GARCH_AVAILABLE:
            # Better baseline: use naive drift forecast
            last_prices = train_data['close'].iloc[-5:].values
            drift = np.mean(np.diff(last_prices))
            forecast = np.zeros(len(test_data))
            forecast[0] = train_data['close'].iloc[-1] + drift
            for i in range(1, len(test_data)):
                forecast[i] = forecast[i-1] + drift
            return forecast
        
        try:
            protocol = ARIMAGARCHStudyProtocol()
            protocol.series = train_data['close']
            
            # Stationarity test
            adf_result = protocol.step1_adf_test(train_data['close'])
            if not adf_result['is_stationary']:
                protocol.step2_differencing()
            
            # ARIMA selection
            arima_order = protocol.step3_arima_order_selection()
            
            # Fit and test residuals
            residual_tests = protocol.step4_fit_arima_and_test_residuals(arima_order)
            
            # Check for ARCH effects
            arch_result = protocol.step5_arch_test(residual_tests['residuals'])
            
            forecast = None
            if arch_result['arch_effects']:
                # Use GARCH
                garch_order = protocol.step6_garch_order_selection()
                protocol.step7_fit_arima_garch(arima_order, garch_order)
                
                # CRITICAL: Use forecast method, not evaluate
                if hasattr(protocol, 'fitted_model') and protocol.fitted_model is not None:
                    forecast_obj = protocol.fitted_model.forecast(horizon=len(test_data), reindex=False)
                    forecast_mean = forecast_obj.mean.values[-len(test_data):]
                    
                    # Convert log returns to prices: price_t = price_{t-1} * exp(return)
                    last_price = train_data['close'].iloc[-1]
                    forecasted_prices = np.zeros(len(test_data))
                    forecasted_prices[0] = last_price * np.exp(forecast_mean[0]/100)
                    for i in range(1, len(test_data)):
                        forecasted_prices[i] = forecasted_prices[i-1] * np.exp(forecast_mean[i]/100)
                    forecast = forecasted_prices
                else:
                    # Fallback to drift
                    last_prices = train_data['close'].iloc[-5:].values
                    drift = np.mean(np.diff(last_prices))
                    forecast = np.zeros(len(test_data))
                    forecast[0] = train_data['close'].iloc[-1] + drift
                    for i in range(1, len(test_data)):
                        forecast[i] = forecast[i-1] + drift
            else:
                # ARIMA only
                if hasattr(protocol, 'arima_result') and protocol.arima_result is not None:
                    # Get ARIMA forecast directly
                    forecast = protocol.arima_result.forecast(steps=len(test_data))
                    forecast = forecast.values
                else:
                    # Fallback to drift
                    last_prices = train_data['close'].iloc[-5:].values
                    drift = np.mean(np.diff(last_prices))
                    forecast = np.zeros(len(test_data))
                    forecast[0] = train_data['close'].iloc[-1] + drift
                    for i in range(1, len(test_data)):
                        forecast[i] = forecast[i-1] + drift
            
            if forecast is None or len(forecast) != len(test_data):
                # Fallback to drift forecast
                last_prices = train_data['close'].iloc[-5:].values
                drift = np.mean(np.diff(last_prices))
                forecast = np.zeros(len(test_data))
                forecast[0] = train_data['close'].iloc[-1] + drift
                for i in range(1, len(test_data)):
                    forecast[i] = forecast[i-1] + drift
            
            return forecast
            
        except Exception as e:
            logger.warning(f"ARIMA-GARCH forecast failed: {e}, using drift forecast")
            # Fallback to drift
            last_prices = train_data['close'].iloc[-5:].values
            drift = np.mean(np.diff(last_prices))
            forecast = np.zeros(len(test_data))
            forecast[0] = train_data['close'].iloc[-1] + drift
            for i in range(1, len(test_data)):
                forecast[i] = forecast[i-1] + drift
            return forecast
    
    def _get_xgb_forecast(self, train_data: pd.DataFrame, test_data: pd.DataFrame, ensemble: Any) -> np.ndarray:
        """Get XGBoost multi-step forecast for test period."""
        try:
            # Import feature engineering
            if not FEATURE_ENGINEER_AVAILABLE:
                raise ImportError("Feature engineer not available")
            
            feature_engineer = KDJFeatureEngineer()
            
            # Iterative multi-step forecasting
            forecast = np.zeros(len(test_data))
            
            # Combine train + test for feature generation
            combined = pd.concat([train_data, test_data], ignore_index=True)
            
            for i in range(len(test_data)):
                # Generate features up to current prediction point
                current_end = len(train_data) + i
                current_data = combined.iloc[:current_end]
                
                # Create features (includes KDJ, lags, etc.)
                features_df = feature_engineer.create_features(current_data, include_kdj=True)
                
                # Get last row features (for next prediction)
                if len(features_df) == 0:
                    raise ValueError("No features generated")
                
                features_array = features_df.iloc[-1:].values
                
                # Predict using XGBoost
                if hasattr(ensemble, 'xgb_model') and ensemble.xgb_model is not None:
                    prediction = ensemble.xgb_model.predict(features_array)[0]
                elif hasattr(ensemble, 'predict'):
                    # Try ensemble predict method
                    prediction = ensemble.predict(current_data)
                    if hasattr(prediction, 'ensemble_forecast'):
                        prediction = prediction.ensemble_forecast
                    elif isinstance(prediction, (int, float)):
                        prediction = prediction
                    else:
                        raise ValueError("Unexpected prediction format")
                else:
                    # Fallback: use last price + drift
                    prediction = current_data['close'].iloc[-1] + np.mean(np.diff(current_data['close'].iloc[-5:]))
                
                forecast[i] = prediction
                
                # Update combined data with prediction for next iteration
                if i < len(test_data) - 1:
                    combined.loc[current_end, 'close'] = prediction
            
            return forecast
            
        except Exception as e:
            logger.warning(f"XGBoost forecast failed: {e}, using drift forecast")
            last_prices = train_data['close'].iloc[-5:].values
            drift = np.mean(np.diff(last_prices))
            forecast = np.zeros(len(test_data))
            forecast[0] = train_data['close'].iloc[-1] + drift
            for i in range(1, len(test_data)):
                forecast[i] = forecast[i-1] + drift
            return forecast
    
    def _detect_volatility_regime(self, prices: pd.Series) -> str:
        """Enhanced 3-tier volatility regime detection."""
        try:
            returns = prices.pct_change().dropna()
            
            if len(returns) < 20:
                return 'LOW'
            
            recent_vol = returns.tail(20).std()
            historical_vol = returns.std()
            vol_ratio = recent_vol / historical_vol
            
            if vol_ratio > 1.8:
                return 'HIGH'
            elif vol_ratio > 1.2:
                return 'MEDIUM'
            else:
                return 'LOW'
        except:
            return 'LOW'
    
    def get_adaptive_weights(self, volatility_regime: str) -> Tuple[float, float]:
        """Return (arima_weight, xgb_weight) based on regime."""
        weights = {
            'LOW': (0.60, 0.40),      # ARIMA better in stable
            'MEDIUM': (0.40, 0.60),   # Balanced
            'HIGH': (0.20, 0.80)      # XGBoost + KDJ better in volatile
        }
        return weights.get(volatility_regime, (0.50, 0.50))
    
    def create_directional_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add features specifically for direction prediction."""
        features = pd.DataFrame(index=df.index)
        
        # KDJ crossover signals
        if 'kdj_j' in df.columns and 'kdj_d' in df.columns:
            features['kdj_j_above_d'] = (df['kdj_j'] > df['kdj_d']).astype(int)
            features['kdj_j_cross_d_up'] = (
                (df['kdj_j'] > df['kdj_d']) & 
                (df['kdj_j'].shift(1) <= df['kdj_d'].shift(1))
            ).astype(int)
        
        # MACD momentum
        if 'macd' in df.columns:
            features['macd_positive'] = (df['macd'] > 0).astype(int)
            features['macd_acceleration'] = df['macd'].diff()
        
        # Price momentum clusters
        if 'ma_20' in df.columns:
            features['price_above_ma20'] = (df['close'] > df['ma_20']).astype(int)
        if 'ma_5' in df.columns and 'ma_20' in df.columns:
            features['ma_5_above_ma_20'] = (df['ma_5'] > df['ma_20']).astype(int)
        
        # Volatility regime binary
        vol_5 = df['close'].pct_change().rolling(5).std()
        vol_20 = df['close'].pct_change().rolling(20).std()
        features['high_volatility'] = (vol_5 > 1.5 * vol_20).astype(int)
        
        return features
    
    def _calc_directional_accuracy(self, actual: np.ndarray, predicted: np.ndarray) -> float:
        """Calculate percentage of correct directional predictions."""
        if len(actual) < 2:
            return 0.0
        
        actual_direction = np.sign(np.diff(actual))
        pred_direction = np.sign(np.diff(predicted))
        
        correct = np.sum(actual_direction == pred_direction)
        total = len(actual_direction)
        
        return (correct / total) * 100 if total > 0 else 0.0
    
    def _aggregate_results(self, window_results: List[Dict], ticker: str) -> ValidationSummary:
        """Aggregate metrics across all validation windows."""
        df = pd.DataFrame(window_results)
        
        # Calculate MAE as percentage of average price using stored actual prices
        avg_price = df['avg_actual_price'].mean()
        mae_as_pct = (df['mae'].mean() / avg_price) * 100 if avg_price > 0 else 0.0
        
        summary = ValidationSummary(
            ticker=ticker,
            timestamp=datetime.now().isoformat(),
            total_windows=len(window_results),
            mean_mae=float(df['mae'].mean()),
            std_mae=float(df['mae'].std()),
            mean_rmse=float(df['rmse'].mean()),
            std_rmse=float(df['rmse'].std()),
            mean_mape=float(df['mape'].mean()),
            mean_directional_accuracy=float(df['directional_accuracy'].mean()),
            stable_windows=int((df['volatility_regime'].isin(['LOW', 'MEDIUM'])).sum()),
            volatile_windows=int((df['volatility_regime'] == 'HIGH').sum()),
            low_windows=int((df['volatility_regime'] == 'LOW').sum()),
            medium_windows=int((df['volatility_regime'] == 'MEDIUM').sum()),
            high_windows=int((df['volatility_regime'] == 'HIGH').sum()),
            mae_as_pct_of_price=float(mae_as_pct),
            best_window=df.loc[df['mae'].idxmin()].to_dict(),
            worst_window=df.loc[df['mae'].idxmax()].to_dict(),
            window_results=df.to_dict('records')
        )
        
        # Print summary
        logger.info(f"\n{'='*70}")
        logger.info(f"WALK-FORWARD VALIDATION SUMMARY: {ticker}")
        logger.info(f"{'='*70}")
        logger.info(f"Total Windows Tested: {summary.total_windows}")
        logger.info(f"\nAggregated Performance:")
        logger.info(f"  Mean MAE:  {summary.mean_mae:.2f} ± {summary.std_mae:.2f}")
        logger.info(f"  Mean RMSE: {summary.mean_rmse:.2f} ± {summary.std_rmse:.2f}")
        logger.info(f"  Mean MAPE: {summary.mean_mape:.2f}%")
        logger.info(f"  MAE as % of avg price: {summary.mae_as_pct_of_price:.2f}%")
        logger.info(f"  Mean Directional Accuracy: {summary.mean_directional_accuracy:.1f}%")
        logger.info(f"\nRegime Distribution (3-Tier):")
        logger.info(f"  Low Volatility:    {summary.low_windows}")
        logger.info(f"  Medium Volatility: {summary.medium_windows}")
        logger.info(f"  High Volatility:   {summary.high_windows}")
        logger.info(f"\nLegacy Regime Distribution:")
        logger.info(f"  Stable Windows:   {summary.stable_windows}")
        logger.info(f"  Volatile Windows: {summary.volatile_windows}")
        logger.info(f"\nBest Window:  #{summary.best_window['window']} (MAE: {summary.best_window['mae']:.2f})")
        logger.info(f"Worst Window: #{summary.worst_window['window']} (MAE: {summary.worst_window['mae']:.2f})")
        logger.info(f"{'='*70}\n")
        
        return summary
    
    def plot_validation_results(self, summary: ValidationSummary, ticker: str):
        """Generate visualization of walk-forward validation results."""
        try:
            import matplotlib.pyplot as plt
            
            # Extract window results
            df = pd.DataFrame(summary.window_results)
            
            fig, axes = plt.subplots(2, 2, figsize=(14, 10))
            fig.suptitle(f'Walk-Forward Validation Results: {ticker}', fontsize=16, fontweight='bold')
            
            # Plot 1: MAE over windows
            axes[0, 0].plot(df['window'], df['mae'], 'o-', linewidth=2, markersize=6)
            axes[0, 0].axhline(summary.mean_mae, color='red', linestyle='--', label='Mean')
            axes[0, 0].fill_between(
                df['window'], 
                summary.mean_mae - summary.std_mae,
                summary.mean_mae + summary.std_mae,
                alpha=0.2, color='red'
            )
            axes[0, 0].set_xlabel('Validation Window')
            axes[0, 0].set_ylabel('MAE')
            axes[0, 0].set_title('Mean Absolute Error')
            axes[0, 0].legend()
            axes[0, 0].grid(True, alpha=0.3)
            
            # Plot 2: Directional accuracy
            axes[0, 1].plot(df['window'], df['directional_accuracy'], 's-', linewidth=2, markersize=6, color='green')
            axes[0, 1].axhline(summary.mean_directional_accuracy, color='red', linestyle='--', label='Mean')
            axes[0, 1].axhline(50, color='gray', linestyle=':', label='Random')
            axes[0, 1].set_xlabel('Validation Window')
            axes[0, 1].set_ylabel('Directional Accuracy (%)')
            axes[0, 1].set_title('Directional Accuracy')
            axes[0, 1].legend()
            axes[0, 1].grid(True, alpha=0.3)
            
            # Plot 3: RMSE over windows
            axes[1, 0].plot(df['window'], df['rmse'], '^-', linewidth=2, markersize=6, color='orange')
            axes[1, 0].axhline(summary.mean_rmse, color='red', linestyle='--', label='Mean')
            axes[1, 0].set_xlabel('Validation Window')
            axes[1, 0].set_ylabel('RMSE')
            axes[1, 0].set_title('Root Mean Squared Error')
            axes[1, 0].legend()
            axes[1, 0].grid(True, alpha=0.3)
            
            # Plot 4: Regime distribution
            def get_regime_color(regime):
                return {'LOW': '#2ecc71', 'MEDIUM': '#f39c12', 'HIGH': '#e74c3c'}.get(regime, '#95a5a6')
            
            regime_colors = [get_regime_color(r) for r in df['volatility_regime']]
            axes[1, 1].bar(df['window'], df['mae'], color=regime_colors)
            axes[1, 1].set_xlabel('Validation Window')
            axes[1, 1].set_ylabel('MAE')
            axes[1, 1].set_title('MAE by Regime (Green=Low, Orange=Medium, Red=High)')
            axes[1, 1].grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            # Save chart
            chart_file = self.charts_path / f"{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            plt.savefig(chart_file, dpi=150, bbox_inches='tight')
            plt.close()
            
            logger.info(f"✓ Saved validation chart: {chart_file}")
            
        except Exception as e:
            logger.warning(f"Failed to generate chart: {e}")

    def save_results(self, summary: ValidationSummary, ticker: str):
        """
        Save validation results to persistent storage.
        
        Saves:
        1. Individual run JSON file in runs/
        2. Aggregated history CSV in history/
        3. Latest summary JSON in history/
        4. Validation charts in charts/
        """
        # Create timestamp for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save individual run
        run_file = self.runs_path / f"{ticker}_{timestamp}_validation.json"
        with open(run_file, 'w') as f:
            json.dump(asdict(summary), f, indent=2)
        logger.info(f"✓ Saved validation results to {run_file}")
        
        # Update aggregated history
        history_file = self.history_path / "validation_history.csv"
        history_summary = {
            'ticker': summary.ticker,
            'timestamp': summary.timestamp,
            'total_windows': summary.total_windows,
            'mean_mae': summary.mean_mae,
            'std_mae': summary.std_mae,
            'mean_rmse': summary.mean_rmse,
            'std_rmse': summary.std_rmse,
            'mean_mape': summary.mean_mape,
            'mean_directional_accuracy': summary.mean_directional_accuracy,
            'stable_windows': summary.stable_windows,
            'volatile_windows': summary.volatile_windows,
            'best_window_mae': summary.best_window['mae'],
            'worst_window_mae': summary.worst_window['mae']
        }
        
        # Load existing history or create new
        if history_file.exists():
            history_df = pd.read_csv(history_file)
            history_df = pd.concat([history_df, pd.DataFrame([history_summary])], ignore_index=True)
        else:
            history_df = pd.DataFrame([history_summary])
        
        history_df.to_csv(history_file, index=False)
        logger.info(f"✓ Updated validation history: {history_file}")
        
        # Save latest summary
        summary_file = self.history_path / "validation_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(asdict(summary), f, indent=2)
        logger.info(f"✓ Saved latest summary: {summary_file}")
        
        # Generate and save visualization
        try:
            self.plot_validation_results(summary, ticker)
        except Exception as e:
            logger.warning(f"Failed to generate chart: {e}")
    
    def load_historical_results(self, ticker: Optional[str] = None) -> pd.DataFrame:
        """
        Load historical validation results.
        
        Args:
            ticker: Optional ticker to filter by
        
        Returns:
            DataFrame with validation history
        """
        history_file = self.history_path / "validation_history.csv"
        
        if not history_file.exists():
            logger.warning("No validation history found")
            return pd.DataFrame()
        
        df = pd.read_csv(history_file)
        
        if ticker:
            df = df[df['ticker'] == ticker]
        
        return df
    
    def backtest_across_regimes(
        self,
        tickers: List[str],
        data_sources: Dict[str, pd.DataFrame]
    ) -> pd.DataFrame:
        """
        Backtest ensemble across multiple stocks and market regimes.
        
        Args:
            tickers: List of ticker symbols to test
            data_sources: Dict mapping ticker -> DataFrame
        
        Returns:
            DataFrame comparing performance across tickers
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"BACKTESTING ACROSS {len(tickers)} TICKERS")
        logger.info(f"{'='*70}\n")
        
        results_list = []
        
        for ticker in tickers:
            if ticker not in data_sources:
                logger.warning(f"⚠️ Data not found for {ticker}, skipping")
                continue
            
            data = data_sources[ticker]
            
            logger.info(f"\n{'='*70}")
            logger.info(f"BACKTESTING: {ticker}")
            logger.info(f"{'='*70}")
            
            try:
                # Run validation
                summary = self.validate_ensemble(data, ticker=ticker, save_results=True)
                
                results_list.append({
                    'ticker': ticker,
                    'total_windows': summary.total_windows,
                    'mean_mae': summary.mean_mae,
                    'std_mae': summary.std_mae,
                    'mean_directional_accuracy': summary.mean_directional_accuracy,
                    'stable_windows': summary.stable_windows,
                    'volatile_windows': summary.volatile_windows,
                    'best_window_mae': summary.best_window['mae'],
                    'worst_window_mae': summary.worst_window['mae']
                })
                
            except Exception as e:
                logger.error(f"❌ Error validating {ticker}: {e}")
                continue
        
        # Create comparison dataframe
        comparison = pd.DataFrame(results_list)
        
        if len(comparison) > 0:
            logger.info(f"\n{'='*70}")
            logger.info("CROSS-ASSET BACKTEST SUMMARY")
            logger.info(f"{'='*70}")
            logger.info(comparison.to_string(index=False))
        
        return comparison
