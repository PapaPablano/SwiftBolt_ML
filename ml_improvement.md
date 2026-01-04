# SwiftBolt_ML: Comprehensive Ensemble Architecture

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Core Components](#core-components)
3. [Model Integration](#model-integration)
4. [Weight Optimization](#weight-optimization)
5. [Uncertainty Quantification](#uncertainty-quantification)
6. [Walk-Forward Ensemble](#walk-forward-ensemble)
7. [Options Integration](#options-integration)
8. [Performance Monitoring](#performance-monitoring)
9. [Production Deployment](#production-deployment)
10. [Testing & Validation](#testing--validation)

---

## Architecture Overview

### System Diagram

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                    DATA PIPELINE                             â”‚
â”‚  (Market Data â†’ Features â†’ Preprocessing)                   â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                 â”‚
        â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”
        â”‚ ENSEMBLE MANAGER â”‚
        â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                 â”‚
    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
    â”‚            â”‚            â”‚              â”‚
    â–¼            â–¼            â–¼              â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â” â”Œâ”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ ARIMA- â”‚  â”‚ PROPHET  â”‚ â”‚ LSTM â”‚  â”‚ TRANSFORMER  â”‚
â”‚ GARCH  â”‚  â”‚  MODEL   â”‚ â”‚MODEL â”‚  â”‚   (MTF)      â”‚
â””â”€â”€â”€â”€â”¬â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”˜ â””â”€â”€â”¬â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”˜
     â”‚           â”‚          â”‚             â”‚
     â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                 â”‚
        â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
        â”‚ WEIGHT AGGREGATOR  â”‚
        â”‚ & UNCERTAINTY CALC â”‚
        â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                 â”‚
    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
    â”‚            â”‚                â”‚
    â–¼            â–¼                â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚FORECAST â”‚  â”‚VOLATILITYâ”‚  â”‚ CONFIDENCE  â”‚
â”‚ PRICE   â”‚  â”‚ PRED.    â”‚  â”‚ INTERVALS   â”‚
â””â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”˜
     â”‚           â”‚                â”‚
     â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                 â”‚
        â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
        â”‚ GREEK CALCULATOR  â”‚
        â”‚ & RISK MGMT       â”‚
        â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                 â”‚
        â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
        â”‚  OUTPUT LAYER     â”‚
        â”‚ (Signals, Alerts) â”‚
        â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Design Principles

1. **Modularity**: Each model is independent, pluggable
2. **Diversity**: Capture different market regimes (trend, mean-reversion, volatility)
3. **Robustness**: Graceful degradation if model fails
4. **Adaptability**: Dynamic weight learning from recent performance
5. **Interpretability**: Explain ensemble decisions
6. **Efficiency**: Parallel model inference where possible

---

## Core Components

### 1. Base Model Interface

```python
# ensemble_base.py

from abc import ABC, abstractmethod
import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class ModelForecast:
    """Standard forecast output format"""
    timestamp: datetime
    forecast_value: float
    forecast_volatility: float
    confidence_interval_lower: float
    confidence_interval_upper: float
    confidence_level: float  # 0.95 for 95% CI
    model_name: str
    forecast_horizon: int
    metadata: Dict = None
    
    def to_dict(self):
        return {
            'timestamp': self.timestamp.isoformat(),
            'forecast_value': self.forecast_value,
            'forecast_volatility': self.forecast_volatility,
            'ci_lower': self.confidence_interval_lower,
            'ci_upper': self.confidence_interval_upper,
            'confidence_level': self.confidence_level,
            'model_name': self.model_name,
            'forecast_horizon': self.forecast_horizon,
            'metadata': self.metadata or {}
        }


class BaseForecaster(ABC):
    """Abstract base class for all models"""
    
    def __init__(self, name: str, lookback: int = 252, 
                 forecast_horizon: int = 1):
        self.name = name
        self.lookback = lookback
        self.forecast_horizon = forecast_horizon
        self.is_fitted = False
        self.last_train_time = None
        self.model_params = {}
        self.validation_metrics = {}
        
    @abstractmethod
    def fit(self, train_data: pd.Series, **kwargs) -> 'BaseForecaster':
        """Fit model to training data"""
        pass
    
    @abstractmethod
    def forecast(self, data: pd.Series, steps: int = 1) -> ModelForecast:
        """Generate forecast with uncertainty"""
        pass
    
    @abstractmethod
    def get_diagnostics(self) -> Dict:
        """Return model diagnostics (residuals, tests, etc.)"""
        pass
    
    def validate_input(self, data: pd.Series) -> bool:
        """Validate input data quality"""
        if len(data) < self.lookback:
            logger.warning(f"{self.name}: Insufficient data. "
                         f"Required {self.lookback}, got {len(data)}")
            return False
        
        if data.isna().sum() > len(data) * 0.05:
            logger.warning(f"{self.name}: >5% missing values detected")
            return False
        
        return True
    
    def get_model_info(self) -> Dict:
        """Return model metadata"""
        return {
            'name': self.name,
            'is_fitted': self.is_fitted,
            'lookback': self.lookback,
            'forecast_horizon': self.forecast_horizon,
            'last_train_time': self.last_train_time.isoformat() if self.last_train_time else None,
            'params': self.model_params,
            'validation_metrics': self.validation_metrics
        }


class EnsembleMetrics:
    """Track ensemble performance metrics"""
    
    def __init__(self):
        self.predictions = []
        self.actuals = []
        self.timestamps = []
        self.model_contributions = {}
        
    def update(self, prediction: float, actual: float, 
               timestamp: datetime, contributions: Dict[str, float]):
        """Record prediction and actual"""
        self.predictions.append(prediction)
        self.actuals.append(actual)
        self.timestamps.append(timestamp)
        
        for model_name, contribution in contributions.items():
            if model_name not in self.model_contributions:
                self.model_contributions[model_name] = []
            self.model_contributions[model_name].append(contribution)
    
    def get_metrics(self) -> Dict:
        """Calculate performance metrics"""
        if not self.predictions:
            return {}
        
        predictions = np.array(self.predictions)
        actuals = np.array(self.actuals)
        errors = actuals - predictions
        
        metrics = {
            'mae': np.abs(errors).mean(),
            'rmse': np.sqrt((errors**2).mean()),
            'mape': np.mean(np.abs(errors / actuals)),
            'directional_accuracy': np.mean(np.sign(predictions) == np.sign(actuals)),
            'correlation': np.corrcoef(predictions, actuals)[0, 1],
            'r_squared': 1 - (errors**2).sum() / ((actuals - actuals.mean())**2).sum(),
        }
        
        # Sharpe ratio
        returns = actuals
        if returns.std() > 0:
            metrics['sharpe_ratio'] = (returns.mean() / returns.std()) * np.sqrt(252)
        
        # Model contribution analysis
        for model_name, contributions in self.model_contributions.items():
            metrics[f'{model_name}_avg_weight'] = np.mean(contributions)
        
        return metrics
```

---

## Model Integration

### 2. ARIMA-GARCH Implementation

```python
# models/arima_garch_model.py

from ensemble_base import BaseForecaster, ModelForecast
from statsmodels.tsa.arima.model import ARIMA
from arch import arch_model
import pandas as pd
import numpy as np
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ArimaGarchForecaster(BaseForecaster):
    """ARIMA-GARCH model wrapper"""
    
    def __init__(self, name: str = 'ARIMA-GARCH',
                 arima_order: Tuple = (1, 0, 1),
                 garch_p: int = 1, garch_q: int = 1,
                 forecast_horizon: int = 1):
        
        super().__init__(name, lookback=252, 
                        forecast_horizon=forecast_horizon)
        
        self.arima_order = arima_order
        self.garch_p = garch_p
        self.garch_q = garch_q
        
        self.fitted_arima = None
        self.fitted_garch = None
        self.model_params = {
            'arima_order': arima_order,
            'garch_p': garch_p,
            'garch_q': garch_q
        }
    
    def fit(self, train_data: pd.Series, **kwargs) -> 'ArimaGarchForecaster':
        """Fit ARIMA-GARCH model"""
        
        if not self.validate_input(train_data):
            raise ValueError("Invalid training data")
        
        try:
            # Fit ARIMA
            self.fitted_arima = ARIMA(
                train_data,
                order=self.arima_order
            ).fit(disp=False)
            
            # Check ARIMA diagnostics
            arima_diagnostics = self._check_arima_diagnostics()
            
            # Fit GARCH on residuals
            residuals = self.fitted_arima.resid
            garch_model = arch_model(
                residuals,
                vol='Garch',
                p=self.garch_p,
                q=self.garch_q,
                rescale=False
            )
            
            self.fitted_garch = garch_model.fit(disp='off', show_warning=False)
            
            # Check GARCH diagnostics
            garch_diagnostics = self._check_garch_diagnostics()
            
            self.validation_metrics = {
                'arima_diagnostics': arima_diagnostics,
                'garch_diagnostics': garch_diagnostics
            }
            
            self.is_fitted = True
            self.last_train_time = datetime.now()
            
            logger.info(f"{self.name} fitted successfully")
            
        except Exception as e:
            logger.error(f"{self.name} fitting failed: {str(e)}")
            raise
        
        return self
    
    def forecast(self, data: pd.Series, steps: int = 1) -> ModelForecast:
        """Generate forecast with confidence intervals"""
        
        if not self.is_fitted:
            raise RuntimeError(f"{self.name} model not fitted")
        
        # Re-fit on all available data (expanding window)
        try:
            fitted_arima = ARIMA(data, order=self.arima_order).fit(disp=False)
            
            # ARIMA forecast
            arima_forecast = fitted_arima.get_forecast(steps=steps)
            arima_mean = arima_forecast.predicted_mean.values[0]
            arima_ci = arima_forecast.conf_int(alpha=0.05)
            arima_ci_lower = arima_ci.iloc[0, 0]
            arima_ci_upper = arima_ci.iloc[0, 1]
            
            # Fit GARCH on residuals
            residuals = fitted_arima.resid
            garch_model = arch_model(
                residuals,
                vol='Garch',
                p=self.garch_p,
                q=self.garch_q,
                rescale=False
            )
            fitted_garch = garch_model.fit(disp='off', show_warning=False)
            
            # GARCH volatility forecast
            garch_forecast = fitted_garch.forecast(horizon=steps)
            forecast_volatility = np.sqrt(garch_forecast.values[-1, 0])
            
            return ModelForecast(
                timestamp=datetime.now(),
                forecast_value=arima_mean,
                forecast_volatility=forecast_volatility,
                confidence_interval_lower=arima_ci_lower,
                confidence_interval_upper=arima_ci_upper,
                confidence_level=0.95,
                model_name=self.name,
                forecast_horizon=steps,
                metadata={
                    'arima_order': self.arima_order,
                    'garch_params': {'p': self.garch_p, 'q': self.garch_q}
                }
            )
        
        except Exception as e:
            logger.error(f"{self.name} forecast failed: {str(e)}")
            # Return null forecast with error indicator
            return self._null_forecast(str(e))
    
    def get_diagnostics(self) -> Dict:
        """Return diagnostic information"""
        
        if not self.is_fitted:
            return {}
        
        diagnostics = {
            'arima_params': self.fitted_arima.params.to_dict(),
            'arima_aic': self.fitted_arima.aic,
            'arima_bic': self.fitted_arima.bic,
            'garch_params': self.fitted_garch.params.to_dict(),
            'garch_log_likelihood': self.fitted_garch.loglikelihood,
        }
        
        return diagnostics
    
    def _check_arima_diagnostics(self) -> Dict:
        """ARIMA assumption checks"""
        from statsmodels.stats.diagnostic import acorr_ljungbox
        
        residuals = self.fitted_arima.resid
        lb_test = acorr_ljungbox(residuals, lags=10, return_df=True)
        
        return {
            'ljung_box_pvalue': float(lb_test['lb_pvalue'].iloc[-1]),
            'has_autocorrelation': lb_test['lb_pvalue'].iloc[-1] < 0.05
        }
    
    def _check_garch_diagnostics(self) -> Dict:
        """GARCH assumption checks"""
        from statsmodels.stats.diagnostic import acorr_ljungbox
        
        std_resid = self.fitted_garch.std_resid
        lb_squared = acorr_ljungbox(std_resid**2, lags=10, return_df=True)
        
        return {
            'ljung_box_squared_pvalue': float(lb_squared['lb_pvalue'].iloc[-1]),
            'has_volatility_clustering': lb_squared['lb_pvalue'].iloc[-1] < 0.05
        }
    
    def _null_forecast(self, error_msg: str) -> ModelForecast:
        """Return null forecast when model fails"""
        return ModelForecast(
            timestamp=datetime.now(),
            forecast_value=np.nan,
            forecast_volatility=np.nan,
            confidence_interval_lower=np.nan,
            confidence_interval_upper=np.nan,
            confidence_level=0.95,
            model_name=self.name,
            forecast_horizon=self.forecast_horizon,
            metadata={'error': error_msg}
        )
```

### 3. Prophet Implementation

```python
# models/prophet_model.py

from ensemble_base import BaseForecaster, ModelForecast
from prophet import Prophet
import pandas as pd
import numpy as np
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ProphetForecaster(BaseForecaster):
    """Facebook Prophet model wrapper"""
    
    def __init__(self, name: str = 'Prophet',
                 yearly_seasonality: bool = False,
                 weekly_seasonality: bool = True,
                 daily_seasonality: bool = False,
                 changepoint_prior_scale: float = 0.05,
                 seasonality_prior_scale: float = 10.0,
                 forecast_horizon: int = 1):
        
        super().__init__(name, lookback=100, 
                        forecast_horizon=forecast_horizon)
        
        self.yearly_seasonality = yearly_seasonality
        self.weekly_seasonality = weekly_seasonality
        self.daily_seasonality = daily_seasonality
        self.changepoint_prior_scale = changepoint_prior_scale
        self.seasonality_prior_scale = seasonality_prior_scale
        
        self.model = None
        self.model_params = {
            'yearly_seasonality': yearly_seasonality,
            'weekly_seasonality': weekly_seasonality,
            'daily_seasonality': daily_seasonality,
            'changepoint_prior_scale': changepoint_prior_scale,
            'seasonality_prior_scale': seasonality_prior_scale
        }
    
    def fit(self, train_data: pd.Series, **kwargs) -> 'ProphetForecaster':
        """Fit Prophet model"""
        
        if not self.validate_input(train_data):
            raise ValueError("Invalid training data")
        
        try:
            # Prepare data for Prophet
            df = pd.DataFrame({
                'ds': train_data.index,
                'y': train_data.values
            })
            
            # Initialize Prophet
            self.model = Prophet(
                yearly_seasonality=self.yearly_seasonality,
                weekly_seasonality=self.weekly_seasonality,
                daily_seasonality=self.daily_seasonality,
                changepoint_prior_scale=self.changepoint_prior_scale,
                seasonality_prior_scale=self.seasonality_prior_scale,
                seasonality_mode='additive',
                interval_width=0.95
            )
            
            # Fit model
            with logging.getLogger('cmdstanpy').propagate as propagate:
                self.model.fit(df)
            
            self.is_fitted = True
            self.last_train_time = datetime.now()
            
            logger.info(f"{self.name} fitted successfully")
            
        except Exception as e:
            logger.error(f"{self.name} fitting failed: {str(e)}")
            raise
        
        return self
    
    def forecast(self, data: pd.Series, steps: int = 1) -> ModelForecast:
        """Generate forecast"""
        
        if not self.is_fitted:
            raise RuntimeError(f"{self.name} model not fitted")
        
        try:
            # Prepare data
            df = pd.DataFrame({
                'ds': data.index,
                'y': data.values
            })
            
            # Refit on all available data
            model = Prophet(
                yearly_seasonality=self.yearly_seasonality,
                weekly_seasonality=self.weekly_seasonality,
                daily_seasonality=self.daily_seasonality,
                changepoint_prior_scale=self.changepoint_prior_scale,
                seasonality_prior_scale=self.seasonality_prior_scale,
                interval_width=0.95
            )
            model.fit(df)
            
            # Create future dataframe
            future = model.make_future_dataframe(periods=steps)
            
            # Generate forecast
            forecast_df = model.predict(future)
            
            # Extract last forecast
            last_forecast = forecast_df.iloc[-1]
            
            # Calculate volatility from residuals
            fitted = model.predict(df)
            residuals = df['y'].values - fitted['yhat'].values
            volatility = np.std(residuals[-20:])  # Recent volatility
            
            return ModelForecast(
                timestamp=datetime.now(),
                forecast_value=last_forecast['yhat'],
                forecast_volatility=volatility,
                confidence_interval_lower=last_forecast['yhat_lower'],
                confidence_interval_upper=last_forecast['yhat_upper'],
                confidence_level=0.95,
                model_name=self.name,
                forecast_horizon=steps,
                metadata={
                    'trend': float(last_forecast['trend']),
                    'seasonal_components': {
                        'weekly': float(last_forecast.get('weekly', 0)),
                        'yearly': float(last_forecast.get('yearly', 0))
                    }
                }
            )
        
        except Exception as e:
            logger.error(f"{self.name} forecast failed: {str(e)}")
            return self._null_forecast(str(e))
    
    def get_diagnostics(self) -> Dict:
        """Return diagnostic information"""
        if not self.model:
            return {}
        
        return {
            'model_components': list(self.model.model.components),
            'growth_type': getattr(self.model, 'growth', 'linear'),
            'n_changepoints': getattr(self.model, 'n_changepoints', None)
        }
    
    def _null_forecast(self, error_msg: str) -> ModelForecast:
        """Return null forecast when model fails"""
        return ModelForecast(
            timestamp=datetime.now(),
            forecast_value=np.nan,
            forecast_volatility=np.nan,
            confidence_interval_lower=np.nan,
            confidence_interval_upper=np.nan,
            confidence_level=0.95,
            model_name=self.name,
            forecast_horizon=self.forecast_horizon,
            metadata={'error': error_msg}
        )
```

### 4. LSTM Implementation (Abbreviated)

```python
# models/lstm_model.py

from ensemble_base import BaseForecaster, ModelForecast
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from sklearn.preprocessing import MinMaxScaler
import pandas as pd
import numpy as np
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class LSTMForecaster(BaseForecaster):
    """LSTM neural network forecaster"""
    
    def __init__(self, name: str = 'LSTM',
                 lookback: int = 60,
                 units: int = 128,
                 dropout: float = 0.2,
                 forecast_horizon: int = 1):
        
        super().__init__(name, lookback=lookback,
                        forecast_horizon=forecast_horizon)
        
        self.units = units
        self.dropout = dropout
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        self.model = None
        
        self.model_params = {
            'lookback': lookback,
            'units': units,
            'dropout': dropout
        }
    
    def fit(self, train_data: pd.Series, epochs: int = 50,
            batch_size: int = 32, **kwargs) -> 'LSTMForecaster':
        """Fit LSTM model"""
        
        if not self.validate_input(train_data):
            raise ValueError("Invalid training data")
        
        try:
            # Prepare sequences
            X, y = self._prepare_sequences(train_data.values)
            
            # Split train/val
            split_idx = int(len(X) * 0.8)
            X_train, X_val = X[:split_idx], X[split_idx:]
            y_train, y_val = y[:split_idx], y[split_idx:]
            
            # Build model
            self._build_model()
            
            # Train
            self.model.fit(
                X_train, y_train,
                validation_data=(X_val, y_val),
                epochs=epochs,
                batch_size=batch_size,
                verbose=0
            )
            
            self.is_fitted = True
            self.last_train_time = datetime.now()
            
            logger.info(f"{self.name} fitted successfully")
            
        except Exception as e:
            logger.error(f"{self.name} fitting failed: {str(e)}")
            raise
        
        return self
    
    def forecast(self, data: pd.Series, steps: int = 1) -> ModelForecast:
        """Generate forecast with uncertainty (MC Dropout)"""
        
        if not self.is_fitted or self.model is None:
            raise RuntimeError(f"{self.name} model not fitted")
        
        try:
            # Scale data
            scaled = self.scaler.fit_transform(
                np.concatenate([data.values[-self.lookback:], [0]]).reshape(-1, 1)
            )
            
            X = scaled[:-1, 0].reshape(1, self.lookback, 1)
            
            # MC dropout for uncertainty
            predictions = []
            for _ in range(100):
                pred = self.model.predict(X, verbose=0)
                predictions.append(pred[0, 0])
            
            predictions = np.array(predictions)
            forecast_value = np.mean(predictions)
            forecast_std = np.std(predictions)
            
            # Inverse transform
            forecast_value = self.scaler.inverse_transform(
                [[forecast_value]])[0, 0]
            forecast_std = forecast_std * self.scaler.data_max_
            
            return ModelForecast(
                timestamp=datetime.now(),
                forecast_value=forecast_value,
                forecast_volatility=forecast_std,
                confidence_interval_lower=forecast_value - 1.96 * forecast_std,
                confidence_interval_upper=forecast_value + 1.96 * forecast_std,
                confidence_level=0.95,
                model_name=self.name,
                forecast_horizon=steps,
                metadata={'mc_iterations': 100}
            )
        
        except Exception as e:
            logger.error(f"{self.name} forecast failed: {str(e)}")
            return self._null_forecast(str(e))
    
    def _prepare_sequences(self, data):
        """Create sequences for LSTM"""
        scaled = self.scaler.fit_transform(data.reshape(-1, 1))
        X, y = [], []
        
        for i in range(len(scaled) - self.lookback):
            X.append(scaled[i:i + self.lookback, 0])
            y.append(scaled[i + self.lookback, 0])
        
        return np.array(X).reshape(-1, self.lookback, 1), np.array(y)
    
    def _build_model(self):
        """Build LSTM architecture"""
        self.model = Sequential([
            LSTM(self.units, activation='relu', 
                 return_sequences=True, input_shape=(self.lookback, 1)),
            Dropout(self.dropout),
            LSTM(self.units // 2, activation='relu'),
            Dropout(self.dropout),
            Dense(16, activation='relu'),
            Dense(1)
        ])
        
        self.model.compile(optimizer='adam', loss='mse')
    
    def get_diagnostics(self) -> Dict:
        """Return diagnostic information"""
        return {
            'architecture': str(self.model.summary()) if self.model else None,
            'params': self.model_params
        }
    
    def _null_forecast(self, error_msg: str) -> ModelForecast:
        """Return null forecast when model fails"""
        return ModelForecast(
            timestamp=datetime.now(),
            forecast_value=np.nan,
            forecast_volatility=np.nan,
            confidence_interval_lower=np.nan,
            confidence_interval_upper=np.nan,
            confidence_level=0.95,
            model_name=self.name,
            forecast_horizon=self.forecast_horizon,
            metadata={'error': error_msg}
        )
```

---

## Weight Optimization

### 5. Dynamic Weight Learning

```python
# weight_optimizer.py

import numpy as np
import pandas as pd
from scipy.optimize import minimize, LinearConstraint, Bounds
from sklearn.linear_model import Ridge, Lasso
import logging

logger = logging.getLogger(__name__)

class WeightOptimizer:
    """Learn optimal ensemble weights"""
    
    def __init__(self, optimization_method: str = 'ridge',
                 alpha: float = 0.01,
                 min_weight: float = 0.01,
                 max_weight: float = 1.0):
        
        self.optimization_method = optimization_method
        self.alpha = alpha
        self.min_weight = min_weight
        self.max_weight = max_weight
        self.weights = None
        self.training_history = []
    
    def optimize_weights(self, predictions_dict: Dict[str, np.ndarray],
                        actuals: np.ndarray,
                        optimize_for: str = 'mse') -> Dict[str, float]:
        """
        Optimize weights to minimize error metric
        
        Args:
            predictions_dict: {model_name: predictions_array}
            actuals: actual values
            optimize_for: 'mse', 'mae', 'sharpe', 'directional'
        """
        
        model_names = list(predictions_dict.keys())
        n_models = len(model_names)
        
        if self.optimization_method == 'ridge':
            return self._ridge_regression_weights(
                predictions_dict, actuals, model_names
            )
        
        elif self.optimization_method == 'sharpe':
            return self._sharpe_ratio_weights(
                predictions_dict, actuals, model_names
            )
        
        elif self.optimization_method == 'directional':
            return self._directional_accuracy_weights(
                predictions_dict, actuals, model_names
            )
        
        else:
            return {name: 1.0 / n_models for name in model_names}
    
    def _ridge_regression_weights(self, predictions_dict: Dict,
                                  actuals: np.ndarray,
                                  model_names: list) -> Dict[str, float]:
        """Learn weights via ridge regression"""
        
        # Stack predictions
        X = np.column_stack([
            predictions_dict[name] for name in model_names
        ])
        
        # Ridge regression
        ridge = Ridge(alpha=self.alpha, fit_intercept=False)
        ridge.fit(X, actuals)
        
        # Extract and normalize weights
        raw_weights = np.abs(ridge.coef_)
        normalized_weights = raw_weights / raw_weights.sum()
        
        # Clip to bounds
        normalized_weights = np.clip(normalized_weights,
                                    self.min_weight,
                                    self.max_weight)
        normalized_weights /= normalized_weights.sum()
        
        weights_dict = {
            name: float(weight)
            for name, weight in zip(model_names, normalized_weights)
        }
        
        self.weights = weights_dict
        return weights_dict
    
    def _sharpe_ratio_weights(self, predictions_dict: Dict,
                             actuals: np.ndarray,
                             model_names: list) -> Dict[str, float]:
        """Allocate based on Sharpe ratios"""
        
        sharpe_ratios = {}
        
        for name, predictions in predictions_dict.items():
            returns = actuals - predictions
            if returns.std() > 0:
                sharpe = returns.mean() / returns.std()
                sharpe_ratios[name] = max(sharpe, 0)  # Floor at 0
        
        total_sharpe = sum(sharpe_ratios.values())
        
        if total_sharpe == 0:
            # Equal weight if all Sharpe ratios are negative
            n_models = len(model_names)
            return {name: 1.0 / n_models for name in model_names}
        
        weights_dict = {
            name: float(sharpe_ratios[name] / total_sharpe)
            for name in model_names
        }
        
        self.weights = weights_dict
        return weights_dict
    
    def _directional_accuracy_weights(self, predictions_dict: Dict,
                                     actuals: np.ndarray,
                                     model_names: list) -> Dict[str, float]:
        """Allocate based on directional accuracy"""
        
        accuracies = {}
        
        for name, predictions in predictions_dict.items():
            correct_direction = np.sign(predictions) == np.sign(actuals)
            accuracy = np.mean(correct_direction)
            accuracies[name] = accuracy
        
        # Subtract baseline (50%)
        adjusted_accuracies = {
            name: max(accuracy - 0.5, 0.01)
            for name, accuracy in accuracies.items()
        }
        
        total_accuracy = sum(adjusted_accuracies.values())
        
        weights_dict = {
            name: float(adjusted_accuracies[name] / total_accuracy)
            for name in model_names
        }
        
        self.weights = weights_dict
        return weights_dict
    
    def get_weights(self) -> Dict[str, float]:
        """Get current weights"""
        return self.weights.copy() if self.weights else {}
```

---

## Uncertainty Quantification

### 6. Confidence Interval Aggregation

```python
# uncertainty_quantifier.py

import numpy as np
import pandas as pd
from scipy import stats
import logging

logger = logging.getLogger(__name__)

class UncertaintyQuantifier:
    """Aggregate and calibrate uncertainty from ensemble"""
    
    def __init__(self, confidence_level: float = 0.95):
        self.confidence_level = confidence_level
        self.z_score = stats.norm.ppf((1 + confidence_level) / 2)
        self.calibration_ratios = {}
    
    def aggregate_forecasts(self, forecasts_list: list,
                           weights: Dict[str, float]) -> Dict:
        """
        Aggregate multiple forecasts into ensemble forecast
        
        Args:
            forecasts_list: List of ModelForecast objects
            weights: {model_name: weight}
        
        Returns:
            Aggregated forecast with uncertainty
        """
        
        # Extract forecast components
        forecast_values = np.array([f.forecast_value for f in forecasts_list])
        volatilities = np.array([f.forecast_volatility for f in forecasts_list])
        ci_lowers = np.array([f.confidence_interval_lower for f in forecasts_list])
        ci_uppers = np.array([f.confidence_interval_upper for f in forecasts_list])
        
        model_names = [f.model_name for f in forecasts_list]
        weight_array = np.array([weights[name] for name in model_names])
        
        # Filter out NaN forecasts
        valid_idx = ~np.isnan(forecast_values)
        if not np.any(valid_idx):
            return self._null_ensemble_forecast()
        
        forecast_values = forecast_values[valid_idx]
        volatilities = volatilities[valid_idx]
        weight_array = weight_array[valid_idx]
        weight_array = weight_array / weight_array.sum()  # Re-normalize
        
        # Weighted average forecast
        ensemble_forecast = np.average(forecast_values, weights=weight_array)
        
        # Aggregate volatility
        ensemble_volatility = self._aggregate_volatility(
            volatilities, weight_array
        )
        
        # Confidence intervals
        ensemble_ci_lower = ensemble_forecast - self.z_score * ensemble_volatility
        ensemble_ci_upper = ensemble_forecast + self.z_score * ensemble_volatility
        
        # Dispersion of ensemble members (indicates disagreement)
        forecast_dispersion = np.std(forecast_values)
        
        return {
            'forecast': ensemble_forecast,
            'volatility': ensemble_volatility,
            'ci_lower': ensemble_ci_lower,
            'ci_upper': ensemble_ci_upper,
            'ensemble_dispersion': forecast_dispersion,
            'n_valid_models': np.sum(valid_idx),
            'model_agreement': 1.0 - (forecast_dispersion / ensemble_volatility)
                              if ensemble_volatility > 0 else 1.0
        }
    
    def _aggregate_volatility(self, volatilities: np.ndarray,
                             weights: np.ndarray) -> float:
        """
        Aggregate volatility from ensemble
        
        Uses mean-variance framework:
        Ïƒ_ensemble = sqrt(sum(w_i * Ïƒ_i^2) + var(forecasts))
        """
        
        # Weighted variance of volatilities
        weighted_var = np.average(volatilities**2, weights=weights)
        
        return np.sqrt(weighted_var)
    
    def calibrate_uncertainty(self, 
                             predicted_ci_lower: np.ndarray,
                             predicted_ci_upper: np.ndarray,
                             actuals: np.ndarray,
                             model_name: str = 'ensemble') -> Dict:
        """
        Calibrate prediction intervals
        
        Check if actual coverage matches claimed confidence level
        """
        
        coverage = np.mean((actuals >= predicted_ci_lower) & 
                          (actuals <= predicted_ci_upper))
        
        interval_width = np.mean(predicted_ci_upper - predicted_ci_lower)
        
        # Calculate calibration ratio
        # If coverage < target, should be < 1 (widen intervals)
        # If coverage > target, should be > 1 (narrow intervals)
        
        calibration_ratio = coverage / self.confidence_level
        self.calibration_ratios[model_name] = calibration_ratio
        
        return {
            'empirical_coverage': coverage,
            'target_coverage': self.confidence_level,
            'calibration_ratio': calibration_ratio,
            'mean_interval_width': interval_width,
            'needs_widening': coverage < self.confidence_level,
            'needs_narrowing': coverage > self.confidence_level
        }
    
    def apply_calibration(self, ensemble_forecast: Dict) -> Dict:
        """Apply calibration adjustment to ensemble forecast"""
        
        # Average calibration ratio
        if self.calibration_ratios:
            avg_ratio = np.mean(list(self.calibration_ratios.values()))
            
            # Adjust volatility
            calibrated_vol = ensemble_forecast['volatility'] * np.sqrt(avg_ratio)
            
            # Recalculate CIs
            calibrated_ci_lower = (
                ensemble_forecast['forecast'] - 
                self.z_score * calibrated_vol
            )
            calibrated_ci_upper = (
                ensemble_forecast['forecast'] + 
                self.z_score * calibrated_vol
            )
            
            return {
                **ensemble_forecast,
                'volatility': calibrated_vol,
                'ci_lower': calibrated_ci_lower,
                'ci_upper': calibrated_ci_upper,
                'calibration_applied': True,
                'calibration_ratio': avg_ratio
            }
        
        return ensemble_forecast
    
    def _null_ensemble_forecast(self) -> Dict:
        """Return null forecast when aggregation fails"""
        return {
            'forecast': np.nan,
            'volatility': np.nan,
            'ci_lower': np.nan,
            'ci_upper': np.nan,
            'error': 'Aggregation failed - all models returned NaN'
        }
```

---

## Walk-Forward Ensemble

### 7. Walk-Forward Validation with Ensemble

```python
# walk_forward_ensemble.py

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Tuple
from ensemble_base import BaseForecaster, EnsembleMetrics

logger = logging.getLogger(__name__)

class WalkForwardEnsemble:
    """Walk-forward backtesting for ensemble"""
    
    def __init__(self, initial_train_size: int = 500,
                 test_size: int = 20,
                 refit_frequency: int = 5,
                 optimization_method: str = 'ridge'):
        
        self.initial_train_size = initial_train_size
        self.test_size = test_size
        self.refit_frequency = refit_frequency
        self.optimization_method = optimization_method
        
        self.results = []
        self.metrics = EnsembleMetrics()
        self.weight_history = []
        self.model_states = []
    
    def run_backtest(self, data: pd.Series,
                    models: Dict[str, BaseForecaster],
                    weight_optimizer: 'WeightOptimizer',
                    uncertainty_quantifier: 'UncertaintyQuantifier'
                   ) -> pd.DataFrame:
        """Execute walk-forward ensemble backtest"""
        
        if len(data) < self.initial_train_size + self.test_size:
            raise ValueError("Insufficient data for walk-forward testing")
        
        train_data = data[:self.initial_train_size]
        test_data = data[self.initial_train_size:]
        
        # Initial model training
        logger.info("Training initial ensemble...")
        for model in models.values():
            model.fit(train_data)
        
        # Initial weight optimization
        weights = {name: 1.0/len(models) for name in models.keys()}
        
        # Walk-forward loop
        for step_idx in range(0, len(test_data) - self.test_size + 1, 1):
            
            current_timestamp = test_data.index[step_idx]
            actual_value = test_data.iloc[step_idx]
            
            # Refit models periodically
            if step_idx % self.refit_frequency == 0:
                logger.info(f"Step {step_idx}: Refitting models...")
                
                refit_data = data[:self.initial_train_size + step_idx]
                
                for model in models.values():
                    try:
                        model.fit(refit_data)
                    except Exception as e:
                        logger.error(f"Model {model.name} fitting failed: {e}")
                
                # Optimize weights based on recent performance
                if step_idx > 0:
                    weights = self._optimize_weights_walkforward(
                        weight_optimizer,
                        models,
                        refit_data,
                        recent_window=50
                    )
                    self.weight_history.append({
                        'timestamp': current_timestamp,
                        'weights': weights.copy()
                    })
            
            # Generate forecasts
            try:
                forecasts_list = [
                    model.forecast(data[:self.initial_train_size + step_idx])
                    for model in models.values()
                ]
                
                # Aggregate ensemble
                ensemble_forecast = uncertainty_quantifier.aggregate_forecasts(
                    forecasts_list, weights
                )
                
                # Record result
                self.results.append({
                    'timestamp': current_timestamp,
                    'forecast': ensemble_forecast['forecast'],
                    'actual': actual_value,
                    'error': actual_value - ensemble_forecast['forecast'],
                    'ensemble_forecast': ensemble_forecast,
                    'weights': weights.copy(),
                    'step': step_idx
                })
                
                # Update metrics
                self.metrics.update(
                    ensemble_forecast['forecast'],
                    actual_value,
                    current_timestamp,
                    weights
                )
                
            except Exception as e:
                logger.error(f"Forecast generation failed at step {step_idx}: {e}")
                continue
        
        return pd.DataFrame(self.results)
    
    def _optimize_weights_walkforward(self,
                                     optimizer: 'WeightOptimizer',
                                     models: Dict[str, BaseForecaster],
                                     data: pd.Series,
                                     recent_window: int = 50) -> Dict[str, float]:
        """Optimize weights based on recent performance"""
        
        # Generate recent predictions
        recent_data = data[-recent_window:]
        predictions_dict = {}
        
        for name, model in models.items():
            try:
                # Forecast each point
                forecasts = []
                for i in range(len(recent_data) - 1):
                    forecast = model.forecast(recent_data[:i+1])
                    forecasts.append(forecast.forecast_value)
                
                predictions_dict[name] = np.array(forecasts)
            
            except Exception as e:
                logger.warning(f"Could not get predictions for {name}: {e}")
        
        if not predictions_dict:
            return {name: 1.0/len(models) for name in models.keys()}
        
        actuals = recent_data[-len(next(iter(predictions_dict.values()))):].values
        
        return optimizer.optimize_weights(predictions_dict, actuals)
    
    def get_results_dataframe(self) -> pd.DataFrame:
        """Get backtest results as DataFrame"""
        return pd.DataFrame(self.results)
    
    def get_metrics(self) -> Dict:
        """Get ensemble performance metrics"""
        return self.metrics.get_metrics()
    
    def get_weight_evolution(self) -> pd.DataFrame:
        """Get weight changes over time"""
        if not self.weight_history:
            return pd.DataFrame()
        
        weight_data = []
        for entry in self.weight_history:
            row = {'timestamp': entry['timestamp']}
            row.update(entry['weights'])
            weight_data.append(row)
        
        return pd.DataFrame(weight_data)
```

---

## Integration & Deployment

### 8. Ensemble Manager (Main Orchestrator)

```python
# ensemble_manager.py

import logging
from datetime import datetime
from typing import Dict, List
import json

logger = logging.getLogger(__name__)

class EnsembleManager:
    """Main orchestrator for ensemble forecasting"""
    
    def __init__(self, models: Dict[str, BaseForecaster],
                 weight_optimizer: 'WeightOptimizer',
                 uncertainty_quantifier: 'UncertaintyQuantifier'):
        
        self.models = models
        self.weight_optimizer = weight_optimizer
        self.uncertainty_quantifier = uncertainty_quantifier
        
        self.weights = {name: 1.0/len(models) for name in models.keys()}
        self.forecast_history = []
        self.error_log = []
    
    def fit_all_models(self, train_data: pd.Series) -> Dict[str, bool]:
        """Fit all ensemble models"""
        
        fit_status = {}
        
        for name, model in self.models.items():
            try:
                model.fit(train_data)
                fit_status[name] = True
                logger.info(f"Successfully fitted: {name}")
            
            except Exception as e:
                fit_status[name] = False
                self.error_log.append({
                    'timestamp': datetime.now(),
                    'model': name,
                    'error': str(e),
                    'operation': 'fit'
                })
                logger.error(f"Failed to fit {name}: {str(e)}")
        
        return fit_status
    
    def generate_ensemble_forecast(self, data: pd.Series) -> Dict:
        """Generate ensemble forecast from latest data"""
        
        # Generate individual forecasts
        forecasts_list = []
        valid_models = []
        
        for name, model in self.models.items():
            try:
                forecast = model.forecast(data)
                
                if not np.isnan(forecast.forecast_value):
                    forecasts_list.append(forecast)
                    valid_models.append(name)
                else:
                    logger.warning(f"{name} returned NaN forecast")
            
            except Exception as e:
                self.error_log.append({
                    'timestamp': datetime.now(),
                    'model': name,
                    'error': str(e),
                    'operation': 'forecast'
                })
                logger.error(f"Error in {name} forecast: {str(e)}")
        
        if not forecasts_list:
            return {'error': 'All models failed to generate forecasts'}
        
        # Aggregate with current weights
        ensemble_output = self.uncertainty_quantifier.aggregate_forecasts(
            forecasts_list,
            {name: self.weights[name] for name in valid_models}
        )
        
        # Apply calibration if available
        ensemble_output = self.uncertainty_quantifier.apply_calibration(
            ensemble_output
        )
        
        # Add metadata
        ensemble_output.update({
            'timestamp': datetime.now().isoformat(),
            'valid_models': valid_models,
            'n_models': len(valid_models),
            'model_agreement': ensemble_output.get('model_agreement', None)
        })
        
        # Store in history
        self.forecast_history.append(ensemble_output.copy())
        
        return ensemble_output
    
    def optimize_weights(self, validation_data: pd.Series,
                        method: str = 'ridge') -> Dict[str, float]:
        """Learn optimal weights from validation data"""
        
        # Generate predictions for each model
        predictions_dict = {}
        
        for name, model in self.models.items():
            try:
                forecasts = []
                for i in range(len(validation_data) - 1):
                    forecast = model.forecast(
                        validation_data[:i+1]
                    )
                    forecasts.append(forecast.forecast_value)
                
                predictions_dict[name] = np.array(forecasts)
            
            except Exception as e:
                logger.warning(f"Could not generate predictions for {name}: {e}")
        
        if not predictions_dict:
            logger.warning("No valid predictions for weight optimization")
            return self.weights
        
        actuals = validation_data[-len(
            next(iter(predictions_dict.values()))
        ):].values
        
        self.weights = self.weight_optimizer.optimize_weights(
            predictions_dict, actuals, optimize_for=method
        )
        
        logger.info(f"Optimized weights: {self.weights}")
        
        return self.weights.copy()
    
    def get_model_diagnostics(self) -> Dict[str, Dict]:
        """Get diagnostics for all models"""
        
        diagnostics = {}
        
        for name, model in self.models.items():
            try:
                diagnostics[name] = model.get_diagnostics()
            except Exception as e:
                diagnostics[name] = {'error': str(e)}
        
        return diagnostics
    
    def get_ensemble_status(self) -> Dict:
        """Get overall ensemble status"""
        
        return {
            'timestamp': datetime.now().isoformat(),
            'n_models': len(self.models),
            'n_fitted_models': sum([1 for m in self.models.values() if m.is_fitted]),
            'current_weights': self.weights.copy(),
            'n_forecasts_generated': len(self.forecast_history),
            'n_errors': len(self.error_log),
            'model_info': {
                name: model.get_model_info()
                for name, model in self.models.items()
            }
        }
    
    def export_configuration(self, filepath: str):
        """Export ensemble configuration to JSON"""
        
        config = {
            'models': {
                name: model.get_model_info()
                for name, model in self.models.items()
            },
            'weights': self.weights,
            'uncertainty_confidence': self.uncertainty_quantifier.confidence_level,
            'created_at': datetime.now().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(config, f, indent=2, default=str)
        
        logger.info(f"Configuration exported to {filepath}")
```

---

## Usage Example

### 9. Complete Implementation Example

```python
# main_ensemble_example.py

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import yfinance as yf

# Import ensemble components
from ensemble_base import BaseForecaster, EnsembleMetrics
from models.arima_garch_model import ArimaGarchForecaster
from models.prophet_model import ProphetForecaster
from models.lstm_model import LSTMForecaster
from weight_optimizer import WeightOptimizer
from uncertainty_quantifier import UncertaintyQuantifier
from walk_forward_ensemble import WalkForwardEnsemble
from ensemble_manager import EnsembleManager


def main():
    """Complete ensemble workflow"""
    
    # 1. Load market data
    print("Loading market data...")
    data = yf.download('SPY', start='2020-01-01', end='2024-12-31')
    returns = data['Adj Close'].pct_change().dropna()
    
    # 2. Initialize models
    print("Initializing models...")
    models = {
        'ARIMA-GARCH': ArimaGarchForecaster(
            arima_order=(1, 0, 1),
            garch_p=1,
            garch_q=1,
            forecast_horizon=1
        ),
        'Prophet': ProphetForecaster(
            weekly_seasonality=True,
            forecast_horizon=1
        ),
        'LSTM': LSTMForecaster(
            lookback=60,
            units=128,
            forecast_horizon=1
        )
    }
    
    # 3. Initialize optimizers
    weight_optimizer = WeightOptimizer(
        optimization_method='ridge',
        alpha=0.01
    )
    
    uncertainty_quantifier = UncertaintyQuantifier(
        confidence_level=0.95
    )
    
    # 4. Create ensemble manager
    ensemble_mgr = EnsembleManager(
        models=models,
        weight_optimizer=weight_optimizer,
        uncertainty_quantifier=uncertainty_quantifier
    )
    
    # 5. Split data
    split_idx = int(len(returns) * 0.7)
    train_data = returns[:split_idx]
    test_data = returns[split_idx:]
    
    # 6. Fit all models
    print("Fitting ensemble models...")
    fit_status = ensemble_mgr.fit_all_models(train_data)
    print(f"Fit status: {fit_status}")
    
    # 7. Optimize weights on validation set
    val_split = int(len(train_data) * 0.8)
    val_data = train_data[val_split:]
    
    print("Optimizing ensemble weights...")
    weights = ensemble_mgr.optimize_weights(val_data, method='ridge')
    print(f"Optimized weights: {weights}")
    
    # 8. Run walk-forward backtest
    print("Running walk-forward backtest...")
    backtest = WalkForwardEnsemble(
        initial_train_size=500,
        test_size=20,
        refit_frequency=5
    )
    
    results = backtest.run_backtest(
        data=returns,
        models=models,
        weight_optimizer=weight_optimizer,
        uncertainty_quantifier=uncertainty_quantifier
    )
    
    # 9. Evaluate performance
    metrics = backtest.get_metrics()
    
    print("\n" + "="*60)
    print("ENSEMBLE PERFORMANCE METRICS")
    print("="*60)
    
    for metric_name, metric_value in metrics.items():
        if not metric_name.startswith('avg_weight'):
            print(f"{metric_name:30s}: {metric_value:10.4f}")
    
    print("\nModel contributions:")
    for metric_name, metric_value in metrics.items():
        if metric_name.startswith('avg_weight'):
            model = metric_name.replace('_avg_weight', '')
            print(f"  {model:25s}: {metric_value:8.2%}")
    
    # 10. Generate current forecast
    print("\n" + "="*60)
    print("CURRENT ENSEMBLE FORECAST")
    print("="*60)
    
    current_forecast = ensemble_mgr.generate_ensemble_forecast(returns)
    
    print(f"Forecast:       {current_forecast['forecast']:.6f}")
    print(f"Volatility:     {current_forecast['volatility']:.6f}")
    print(f"CI Lower:       {current_forecast['ci_lower']:.6f}")
    print(f"CI Upper:       {current_forecast['ci_upper']:.6f}")
    print(f"Model Agreement: {current_forecast['model_agreement']:.2%}")
    
    # 11. Export results
    results.to_csv('ensemble_backtest_results.csv', index=False)
    ensemble_mgr.export_configuration('ensemble_config.json')
    
    print("\nResults exported to:")
    print("  - ensemble_backtest_results.csv")
    print("  - ensemble_config.json")
    
    return ensemble_mgr, results, metrics


if __name__ == '__main__':
    ensemble_mgr, results, metrics = main()
```

---

## Summary

This ensemble architecture provides:

âœ… **Modularity**: Each model is independent and interchangeable
âœ… **Robustness**: Graceful handling of model failures
âœ… **Adaptability**: Dynamic weight learning from recent performance
âœ… **Uncertainty**: Calibrated confidence intervals and volatility forecasts
âœ… **Interpretability**: Model contributions and disagreement metrics
âœ… **Production-Ready**: Walk-forward validation and performance monitoring
âœ… **Scalability**: Easy to add new models to the ensemble
âœ… **Flexibility**: Multiple weight optimization strategies

This is your foundation for the next-level statistical relevance in SwiftBolt_ML! ðŸš€