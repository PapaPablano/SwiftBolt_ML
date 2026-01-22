# SwiftBolt_ML: Part 4 - Integration with Production (COMPLETE)

## Part 4: Integration with Production

### Loading Trained Models

**File: `ml/src/models/ensemble_loader.py`**

```python
import pickle
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
import numpy as np
import pandas as pd

from config.settings import TIMEFRAME_HORIZONS
from src.models.enhanced_ensemble_integration import EnhancedEnsembleForecaster

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent.parent.parent / "trained_models"
MODELS_DIR.mkdir(exist_ok=True)


class EnsembleLoader:
    """Load trained ensemble models from disk."""
    
    @staticmethod
    def load_latest_model(
        symbol: str,
        timeframe: str,
        max_age_days: int = 60,
    ) -> Optional[dict]:
        """
        Load most recent trained model for symbol/timeframe.
        
        Args:
            symbol: Ticker (e.g., "AAPL")
            timeframe: Timeframe ID (e.g., "d1", "h1")
            max_age_days: Reject models older than this (60 = monthly retrain)
        
        Returns:
            {
                "models": {...trained sklearn models...},
                "weights": {"rf": 0.50, "gb": 0.50, ...},
                "timestamp": "20250121",
                "ensemble_accuracy": 0.59,
                "model_performances": {"rf": {...}, "gb": {...}},
            }
            OR None if no valid model found
        """
        
        # Find all model files for this symbol/timeframe
        pattern = f"{symbol}_{timeframe}_*.pkl"
        candidates = list(MODELS_DIR.glob(pattern))
        
        if not candidates:
            logger.warning(f"No models found for {symbol}/{timeframe} in {MODELS_DIR}")
            return None
        
        # Load most recent file
        latest_file = sorted(candidates)[-1]
        
        # Check age
        file_timestamp_str = latest_file.stem.split("_")[-1]  # e.g., "20250121"
        file_date = datetime.strptime(file_timestamp_str, "%Y%m%d")
        age_days = (datetime.utcnow() - file_date).days
        
        if age_days > max_age_days:
            logger.warning(
                f"Model too old: {age_days} days (max: {max_age_days}). "
                f"Run monthly retraining job."
            )
            return None
        
        try:
            with open(latest_file, "rb") as f:
                artifact = pickle.load(f)
            
            logger.info(
                f"Loaded {symbol}/{timeframe} from {latest_file.name} "
                f"({age_days} days old, accuracy: {artifact.get('ensemble_accuracy', 'N/A'):.1%})"
            )
            return artifact
            
        except Exception as e:
            logger.error(f"Failed to load {latest_file}: {e}", exc_info=True)
            return None
    
    @staticmethod
    def list_available_models() -> dict:
        """List all available trained models on disk."""
        models = {}
        
        for pkl_file in MODELS_DIR.glob("*.pkl"):
            parts = pkl_file.stem.split("_")
            if len(parts) >= 3:
                symbol = parts[0]
                timeframe = parts[1]
                timestamp = parts[2]
                
                if symbol not in models:
                    models[symbol] = {}
                if timeframe not in models[symbol]:
                    models[symbol][timeframe] = []
                
                models[symbol][timeframe].append({"file": pkl_file.name, "timestamp": timestamp})
        
        logger.info(f"Available models: {models}")
        return models


def get_production_ensemble_with_trained_weights(
    symbol: str,
    timeframe: str,
    fallback_to_defaults: bool = True,
) -> tuple[EnhancedEnsembleForecaster, bool]:
    """
    Create EnhancedEnsembleForecaster and load trained weights.
    
    This is the PRIMARY integration point with your existing ensemble.
    Replaces get_production_ensemble() calls.
    
    Args:
        symbol: Ticker (e.g., "AAPL")
        timeframe: Timeframe ID (e.g., "d1")
        fallback_to_defaults: If True, return uninitialized ensemble if no trained model
                            If False, raise exception
    
    Returns:
        (ensemble, is_trained)
        - ensemble: EnhancedEnsembleForecaster with weights loaded
        - is_trained: Boolean indicating if ensemble was successfully initialized with trained weights
    
    Raises:
        RuntimeError if fallback_to_defaults=False and no model found
    """
    
    # Create base ensemble
    try:
        ensemble = EnhancedEnsembleForecaster(
            horizon=TIMEFRAME_HORIZONS[timeframe].get("base_horizon", "1D"),
            enable_arima_garch=True,
            enable_prophet=True,
            enable_lstm=False,
        )
    except Exception as e:
        logger.error(f"Failed to create ensemble: {e}")
        raise
    
    # Load trained models and weights
    artifact = EnsembleLoader.load_latest_model(symbol, timeframe)
    
    if not artifact:
        if fallback_to_defaults:
            logger.warning(
                f"No trained models for {symbol}/{timeframe}. "
                f"Using default uniform weights (0.50/0.50). "
                f"Run: python ml/src/training/ensemble_training_job.py"
            )
            return ensemble, False
        else:
            raise RuntimeError(
                f"Ensemble not trained for {symbol}/{timeframe}. "
                f"Run: python ml/src/training/ensemble_training_job.py"
            )
    
    try:
        # Inject trained models and weights
        trained_models = artifact.get("models", {})
        trained_weights = artifact.get("weights", {})
        
        # Update ensemble's internal models
        ensemble.models = trained_models
        if hasattr(ensemble, 'ensemble_manager') and hasattr(ensemble.ensemble_manager, 'ensemble'):
            ensemble.ensemble_manager.ensemble.models = trained_models
            ensemble.ensemble_manager.ensemble.weights = trained_weights
        
        # Set metadata
        ensemble.is_trained = True
        ensemble.training_stats = {
            "ensemble_accuracy": artifact.get("ensemble_accuracy"),
            "weights": trained_weights,
            "loaded_from": f"{symbol}_{timeframe}_{artifact.get('timestamp')}",
            "model_performances": artifact.get("model_performances", {}),
        }
        
        logger.info(
            f"✓ Ensemble initialized with trained weights for {symbol}/{timeframe}: "
            f"{trained_weights}"
        )
        
        return ensemble, True
        
    except Exception as e:
        logger.error(f"Failed to initialize ensemble with trained weights: {e}", exc_info=True)
        if not fallback_to_defaults:
            raise
        return ensemble, False


class EnsemblePredictor:
    """
    High-level predictor: handles model loading, prediction, and error handling.
    
    USAGE in your jobs:
        predictor = EnsemblePredictor(symbol="AAPL", timeframe="d1")
        result = predictor.predict(df)
        if result:
            forecast = result["forecast"]
            confidence = result["confidence"]
        else:
            # Handle error
    """
    
    def __init__(
        self,
        symbol: str,
        timeframe: str,
        use_trained_weights: bool = True,
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.ensemble = None
        self.is_trained = False
        
        try:
            self.ensemble, self.is_trained = get_production_ensemble_with_trained_weights(
                symbol=symbol,
                timeframe=timeframe,
                fallback_to_defaults=(not use_trained_weights),
            )
        except Exception as e:
            logger.error(f"Failed to initialize predictor: {e}")
            self.ensemble = None
    
    def predict(self, df: pd.DataFrame) -> Optional[dict]:
        """
        Generate prediction from ensemble.
        
        Args:
            df: OHLCV DataFrame with features
        
        Returns:
            {
                "forecast": "BULLISH",
                "confidence": 0.72,
                "model_agreements": {"rf": "BULLISH", "gb": "BULLISH"},
                "weights_used": {"rf": 0.50, "gb": 0.50},
                "is_trained_model": True,
            }
            OR None on error
        """
        
        if self.ensemble is None:
            logger.error(f"Ensemble not initialized for {self.symbol}/{self.timeframe}")
            return None
        
        try:
            # Get prediction
            result = self.ensemble.predict(df)
            
            if result is None:
                logger.error("Ensemble returned None")
                return None
            
            # Extract direction and confidence
            forecast = result.get("direction", "NEUTRAL")
            confidence = result.get("confidence", 0.33)
            
            return {
                "forecast": forecast,
                "confidence": confidence,
                "model_agreements": result.get("individual_predictions", {}),
                "weights_used": self.ensemble.training_stats.get("weights") if self.is_trained else None,
                "is_trained_model": self.is_trained,
                "timestamp": datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Prediction failed for {self.symbol}/{self.timeframe}: {e}", exc_info=True)
            return None
```

---

### Modified Multi-Horizon Forecast Job

**File: `ml/src/multi_horizon_forecast_job.py` (UPDATED)**

**Changes from original:**
- Import `EnsemblePredictor` from ensemble_loader
- Replace `get_production_ensemble()` calls with `EnsemblePredictor`
- Add is_trained tracking
- Better error handling with graceful degradation

```python
import logging
from datetime import datetime
from typing import Optional

import pandas as pd

from src.models.ensemble_loader import EnsemblePredictor, get_production_ensemble_with_trained_weights
from config.settings import settings, TIMEFRAME_HORIZONS
from src.data.supabase_db import db

logger = logging.getLogger(__name__)


def generate_multi_horizon_forecasts(
    symbol: str,
    timeframe: str,
    df: pd.DataFrame,
) -> Optional[dict]:
    """
    Generate cascading forecasts for a specific symbol and timeframe.
    
    ✅ UPDATED: Uses trained ensemble with weights instead of defaults
    
    Args:
        symbol: Ticker (e.g., "AAPL")
        timeframe: Timeframe ID (e.g., "d1")
        df: OHLCV data with technical features
    
    Returns:
        {
            "symbol": "AAPL",
            "timeframe": "d1",
            "forecast": "BULLISH",
            "confidence": 0.72,
            "is_trained": True,
            "weights": {"rf": 0.50, "gb": 0.50},
            "timestamp": "2025-01-21T06:00:00Z",
        }
    """
    
    logger.info(f"Generating forecast for {symbol}/{timeframe}")
    
    try:
        # ✅ CHANGED: Use EnsemblePredictor instead of get_production_ensemble()
        predictor = EnsemblePredictor(
            symbol=symbol,
            timeframe=timeframe,
            use_trained_weights=True,  # Require trained weights
        )
        
        # Check if ensemble loaded successfully
        if predictor.ensemble is None:
            logger.error(
                f"Failed to load ensemble for {symbol}/{timeframe}. "
                f"Run: python ml/src/training/ensemble_training_job.py"
            )
            return None
        
        # Generate prediction
        pred_result = predictor.predict(df)
        
        if pred_result is None:
            logger.error(f"Prediction failed for {symbol}/{timeframe}")
            return None
        
        # Build forecast object
        forecast = {
            "symbol": symbol,
            "timeframe": timeframe,
            "forecast": pred_result["forecast"],
            "confidence": pred_result["confidence"],
            "is_trained": pred_result["is_trained_model"],
            "weights": pred_result["weights_used"],
            "model_agreements": pred_result["model_agreements"],
            "timestamp": pred_result["timestamp"],
        }
        
        # ✅ Log forecast
        logger.info(
            f"Forecast generated: {symbol}/{timeframe} → {pred_result['forecast']} "
            f"(confidence: {pred_result['confidence']:.1%}, trained: {pred_result['is_trained_model']})"
        )
        
        return forecast
        
    except Exception as exc:
        logger.error(
            f"Failed to generate forecast for {symbol}/{timeframe}: {exc}",
            exc_info=True,
        )
        return None


def multi_horizon_forecast_job():
    """
    Main job: Generate multi-horizon forecasts for all symbols/timeframes.
    
    Scheduled: Daily at 6am UTC
    
    ✅ UPDATED: Loads trained ensemble; fails gracefully if no models trained
    """
    
    logger.info("="*60)
    logger.info(f"Multi-Horizon Forecast Job Started")
    logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
    logger.info("="*60)
    
    symbols = settings.symbols_to_process
    timeframes = list(TIMEFRAME_HORIZONS.keys())
    
    forecasts = []
    failures = []
    
    for symbol in symbols:
        # Fetch latest data for symbol
        try:
            df = db.fetch_latest_ohlcv(symbol, lookback_days=60)
            if df is None or len(df) == 0:
                logger.warning(f"No data for {symbol}")
                failures.append({"symbol": symbol, "reason": "No data"})
                continue
        except Exception as e:
            logger.error(f"Failed to fetch data for {symbol}: {e}")
            failures.append({"symbol": symbol, "reason": str(e)})
            continue
        
        for timeframe in timeframes:
            try:
                # Get forecast using trained ensemble
                forecast = generate_multi_horizon_forecasts(symbol, timeframe, df)
                
                if forecast:
                    forecasts.append(forecast)
                    
                    # Persist to database
                    try:
                        db.client.table("forecasts").insert({
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "forecast_direction": forecast["forecast"],
                            "confidence": forecast["confidence"],
                            "is_trained_ensemble": forecast["is_trained"],
                            "weights_used": forecast["weights"],
                            "generated_at": forecast["timestamp"],
                        }).execute()
                    except Exception as e:
                        logger.warning(f"Failed to persist forecast: {e}")
                else:
                    failures.append({
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "reason": "Prediction failed",
                    })
            
            except Exception as e:
                logger.error(f"Error processing {symbol}/{timeframe}: {e}", exc_info=True)
                failures.append({
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "reason": str(e),
                })
    
    # Summary
    logger.info("="*60)
    logger.info("FORECAST JOB COMPLETE")
    logger.info(f"Generated: {len(forecasts)} forecasts")
    logger.info(f"Failed: {len(failures)}")
    
    if failures:
        logger.warning(f"Failures: {failures}")
    
    logger.info("="*60)
    
    return {"forecasts": forecasts, "failures": failures}


if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    result = multi_horizon_forecast_job()
    sys.exit(0 if len(result["failures"]) == 0 else 1)
```

---

## Integration Checklist

### Step 1: Deploy Loader Module (10 minutes)

- [ ] Copy `ml/src/models/ensemble_loader.py` to your codebase
- [ ] Verify `trained_models/` directory exists
- [ ] Test import: `python -c "from src.models.ensemble_loader import EnsemblePredictor"`

### Step 2: Update Forecast Job (5 minutes)

- [ ] Replace `multi_horizon_forecast_job.py` with updated version
- [ ] Change imports from `get_production_ensemble()` to `EnsemblePredictor`
- [ ] Update function signatures if needed

### Step 3: Train First Models (60 minutes)

```bash
cd /Users/ericpeterson/SwiftBolt_ML
python ml/src/training/ensemble_training_job.py

# Expected output:
# Training run for AAPL/d1...
# Saved to trained_models/AAPL_d1_20250121.pkl
# ...
```

### Step 4: Verify Models Loaded (5 minutes)

```bash
python -c "
from src.models.ensemble_loader import EnsemblePredictor
p = EnsemblePredictor('AAPL', 'd1')
print(f'Loaded: {p.is_trained}')
print(f'Weights: {p.ensemble.training_stats.get(\"weights\")}')
"

# Expected output:
# Loaded: True
# Weights: {'rf': 0.50, 'gb': 0.50}
```

### Step 5: Test Forecast Job (10 minutes)

```bash
python ml/src/multi_horizon_forecast_job.py

# Expected output:
# Multi-Horizon Forecast Job Started
# ...
# Forecast generated: AAPL/d1 → BULLISH (confidence: 72.1%, trained: True)
# ...
# FORECAST JOB COMPLETE
# Generated: 25 forecasts
# Failed: 0
```

---

## Troubleshooting

### Error: "Ensemble not trained for AAPL/d1"

**Cause**: No trained models on disk

**Solution**:
```bash
python ml/src/training/ensemble_training_job.py
```

Then verify:
```bash
ls -lh /Users/ericpeterson/SwiftBolt_ML/trained_models/
```

### Error: "No models found for AAPL/d1"

**Cause**: Models saved to wrong location

**Solution**: Verify `MODELS_DIR` in ensemble_loader.py:
```python
MODELS_DIR = Path(__file__).parent.parent.parent / "trained_models"
# Should expand to: /Users/ericpeterson/SwiftBolt_ML/trained_models/
```

### Forecast shows "is_trained: false"

**Cause**: Models older than 60 days (monthly retrain needed)

**Solution**:
```bash
python ml/src/training/ensemble_training_job.py  # Retrain
```

Or adjust `max_age_days` in ensemble_loader.py if needed.

---

## Performance Expectations

After integration, your system should:

| Metric | Target |
|--------|--------|
| Forecast generation time | < 2 sec per symbol/timeframe |
| Model load time | < 500ms |
| Database persistence | < 100ms |
| Total job time for all symbols | < 5 minutes |
| Failed forecasts | 0% (graceful degradation to defaults) |

---

## Key Integration Points

**Critical**: EnsemblePredictor is now your single integration point.

**Before** (broken):
```python
ensemble = get_production_ensemble()  # ❌ Not trained
forecast = ensemble.predict(df)  # ❌ RuntimeError
```

**After** (working):
```python
predictor = EnsemblePredictor("AAPL", "d1")  # ✅ Loads trained weights
result = predictor.predict(df)  # ✅ Uses trained models
print(result["is_trained_model"])  # ✅ True (if trained) or False (if using defaults)
```

---

## Next: Part 5 - Drift Monitoring

Once forecasts are generating successfully with trained models, implement Part 5 (drift_monitor.py) to:
- Track daily accuracy
- Detect performance degradation
- Trigger automatic retraining
- Send alerts to Slack

**Ready to deploy?** Let me know if you need help integrating this into your Supabase jobs or GitHub Actions workflows.
