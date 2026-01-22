# Part 4: Integration with Production

## Loading Trained Models into Production

This guide shows how to integrate trained ensemble models with your existing forecast pipeline.

---

## Module: Ensemble Loader (`ml/src/models/ensemble_loader.py`)

```python
"""Load trained ensemble models from disk."""

import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# Where trained models are stored
MODELS_DIR = Path(__file__).parent.parent.parent / "trained_models"
MODELS_DIR.mkdir(exist_ok=True)


class EnsembleLoader:
    """Load trained ensemble models from disk."""
    
    @staticmethod
    def load_latest_model(
        symbol: str,
        timeframe: str,
    ) -> Optional[Dict]:
        """
        Load most recent trained model for symbol/timeframe.
        
        Args:
            symbol: Stock ticker (e.g., "AAPL")
            timeframe: Timeframe (e.g., "d1")
        
        Returns:
            {
                "models": {...trained sklearn models...},
                "weights": {"rf": 0.50, "gb": 0.50, ...},
                "timestamp": "20250121",
                "ensemble_accuracy": 0.59,
            }
            or None if not found
        """
        
        # Find all model files for this symbol/timeframe
        pattern = f"{symbol}_{timeframe}_*.pkl"
        candidates = list(MODELS_DIR.glob(pattern))
        
        if not candidates:
            logger.warning(f"No models found for {symbol}/{timeframe}")
            logger.info(f"  Search path: {MODELS_DIR}")
            logger.info(f"  Search pattern: {pattern}")
            return None
        
        # Load most recent (sorted by filename)
        latest_file = sorted(candidates)[-1]
        
        logger.info(f"Found {len(candidates)} model files for {symbol}/{timeframe}")
        logger.info(f"Loading latest: {latest_file.name}")
        
        try:
            with open(latest_file, "rb") as f:
                artifact = pickle.load(f)
            
            logger.info(f"Successfully loaded model from {latest_file.name}")
            return artifact
            
        except Exception as e:
            logger.error(f"Failed to load {latest_file}: {e}")
            return None
    
    @staticmethod
    def list_available_models() -> Dict[str, list[str]]:
        """
        List all available trained models.
        
        Returns:
            {
                "AAPL_d1": ["20250121", "20250114"],
                "AAPL_h1": ["20250121"],
                ...
            }
        """
        models = {}
        
        for pkl_file in MODELS_DIR.glob("*.pkl"):
            # Parse filename: SYMBOL_TIMEFRAME_YYYYMMDD.pkl
            stem = pkl_file.stem
            parts = stem.rsplit("_", 1)
            
            if len(parts) == 2:
                symbol_tf = parts[0]
                timestamp = parts[1]
                
                if symbol_tf not in models:
                    models[symbol_tf] = []
                models[symbol_tf].append(timestamp)
        
        # Sort timestamps descending (newest first)
        for key in models:
            models[key].sort(reverse=True)
        
        return models
    
    @staticmethod
    def get_model_info(symbol: str, timeframe: str) -> Optional[Dict]:
        """
        Get metadata about a trained model without loading the full artifact.
        
        Returns:
            {
                "symbol": "AAPL",
                "timeframe": "d1",
                "timestamp": "20250121",
                "ensemble_accuracy": 0.59,
                "weights": {"rf": 0.50, "gb": 0.50},
                "file_size_mb": 1.2,
            }
        """
        artifact = EnsembleLoader.load_latest_model(symbol, timeframe)
        
        if not artifact:
            return None
        
        pattern = f"{symbol}_{timeframe}_*.pkl"
        candidates = list(MODELS_DIR.glob(pattern))
        latest_file = sorted(candidates)[-1]
        
        return {
            "symbol": artifact.get("symbol"),
            "timeframe": artifact.get("timeframe"),
            "timestamp": artifact.get("timestamp"),
            "ensemble_accuracy": artifact.get("ensemble_accuracy"),
            "weights": artifact.get("weights"),
            "file_size_mb": latest_file.stat().st_size / (1024 * 1024),
            "file_path": str(latest_file),
        }


def get_production_ensemble_with_trained_weights(
    symbol: str,
    timeframe: str,
) -> 'EnhancedEnsembleForecaster':
    """
    Create EnhancedEnsembleForecaster and load trained weights.
    
    This is the KEY INTEGRATION POINT with your existing ensemble.
    
    Args:
        symbol: Stock ticker
        timeframe: Timeframe identifier
    
    Returns:
        Initialized EnhancedEnsembleForecaster with trained models + weights
    
    Example:
        ensemble = get_production_ensemble_with_trained_weights("AAPL", "d1")
        result = ensemble.predict(df)  # Now works!
    """
    from src.models.enhanced_ensemble_integration import EnhancedEnsembleForecaster
    from config.settings import TIMEFRAME_HORIZONS
    
    logger.info(f"Loading production ensemble for {symbol}/{timeframe}")
    
    # Create ensemble (uninitialized)
    config = TIMEFRAME_HORIZONS.get(timeframe, {})
    horizon = config.get("base_horizon", "1D")
    
    ensemble = EnhancedEnsembleForecaster(
        horizon=horizon,
        symbol_id=symbol,
        enable_arima_garch=True,
        enable_prophet=True,
        enable_lstm=False,
    )
    
    # Load trained models
    artifact = EnsembleLoader.load_latest_model(symbol, timeframe)
    
    if not artifact:
        logger.warning(
            f"No trained models for {symbol}/{timeframe}, using empty ensemble"
        )
        logger.warning("Run training job to generate models")
        return ensemble
    
    # Inject trained models into ensemble
    try:
        ensemble.models = artifact.get("models", {})
        
        # Access internal ensemble manager if available
        if hasattr(ensemble, "ensemble_manager"):
            if hasattr(ensemble.ensemble_manager, "ensemble"):
                ensemble.ensemble_manager.ensemble.models = artifact.get("models", {})
                ensemble.ensemble_manager.ensemble.weights = artifact.get("weights", {})
        
        ensemble.is_trained = True
        ensemble.training_stats = {
            "ensemble_accuracy": artifact.get("ensemble_accuracy"),
            "weights": artifact.get("weights"),
            "loaded_from": f"{symbol}_{timeframe}_{artifact.get('timestamp')}",
            "model_performances": artifact.get("performances", {}),
        }
        
        logger.info(f"Ensemble initialized with trained weights")
        logger.info(f"  Weights: {artifact.get('weights')}")
        logger.info(f"  Validation Accuracy: {artifact.get('ensemble_accuracy'):.1%}")
        
        return ensemble
        
    except Exception as e:
        logger.error(f"Failed to inject trained models: {e}")
        logger.error("Ensemble may not be fully functional")
        return ensemble
```

---

## Integration with Multi-Horizon Forecast Job

### Current Code (Broken)

```python
# ml/src/multi_horizon_forecast_job.py (CURRENT)

def generate_multi_horizon_forecasts(
    symbol: str,
    timeframe: str,
    df: pd.DataFrame,
) -> Optional[MultiHorizonForecast]:
    # ... setup code ...
    
    try:
        # PROBLEM: This returns an untrained ensemble
        ensemble = get_production_ensemble()
        ensemble_result = ensemble.predict(df)  # RuntimeError!
    
    except Exception as exc:
        logger.error(f"Failed to get ensemble predictions: {exc}")
        return None
```

### Fixed Code (Working)

```python
# ml/src/multi_horizon_forecast_job.py (FIXED)

from src.models.ensemble_loader import get_production_ensemble_with_trained_weights

def generate_multi_horizon_forecasts(
    symbol: str,
    timeframe: str,
    df: pd.DataFrame,
) -> Optional[MultiHorizonForecast]:
    # ... setup code ...
    
    try:
        # FIXED: Load ensemble with trained weights
        ensemble = get_production_ensemble_with_trained_weights(symbol, timeframe)
        
        # Verify ensemble is trained
        if not ensemble.is_trained:
            logger.error(
                f"Ensemble not trained for {symbol}/{timeframe}\n"
                f"Run: python -m ml.src.training.ensemble_training_job --all"
            )
            return None
        
        # Now predict will work
        ensemble_result = ensemble.predict(df)
    
    except Exception as exc:
        logger.error(f"Failed to get ensemble predictions: {exc}")
        logger.error(f"Ensure trained models exist in {MODELS_DIR}")
        return None
```

---

## Database Schema for Training Artifacts

### New Table: `training_runs`

```sql
CREATE TABLE training_runs (
    id BIGSERIAL PRIMARY KEY,
    symbol_id BIGINT NOT NULL REFERENCES symbols(id),
    timeframe TEXT NOT NULL,
    run_date TIMESTAMP NOT NULL DEFAULT NOW(),
    lookback_days INT,
    n_training_samples INT,
    n_validation_samples INT,
    ensemble_validation_accuracy FLOAT,
    model_performances JSONB,  -- {"rf": {...}, "gb": {...}}
    weights JSONB,             -- {"rf": 0.50, "gb": 0.50}
    models_artifact_path TEXT,
    status TEXT DEFAULT 'completed',
    error_message TEXT,
    
    UNIQUE(symbol_id, timeframe, run_date)
);

CREATE INDEX idx_training_runs_symbol_timeframe 
    ON training_runs(symbol_id, timeframe, run_date DESC);
```

### Query: Latest Training Run

```sql
-- Get latest training for each symbol/timeframe
SELECT 
    s.ticker,
    tr.timeframe,
    tr.run_date,
    tr.ensemble_validation_accuracy,
    tr.weights,
    tr.models_artifact_path
FROM training_runs tr
JOIN symbols s ON tr.symbol_id = s.id
WHERE (s.id, tr.timeframe, tr.run_date) IN (
    SELECT symbol_id, timeframe, MAX(run_date)
    FROM training_runs
    GROUP BY symbol_id, timeframe
)
ORDER BY s.ticker, tr.timeframe;
```

---

## Model Serialization Format

### File Structure

```
trained_models/
├── AAPL_d1_20250121.pkl      # (symbol)_(timeframe)_(YYYYMMDD).pkl
├── AAPL_d1_20250114.pkl      # Previous version
├── AAPL_h1_20250121.pkl
├── AAPL_h4_20250121.pkl
├── AAPL_m15_20250121.pkl
├── AAPL_w1_20250121.pkl
├─┐─ SPY_d1_20250121.pkl
└─┐─ ... more symbols ...
```

### Artifact Contents

```python
artifact = {
    # Metadata
    "symbol": "AAPL",
    "timeframe": "d1",
    "timestamp": "20250121",
    
    # Models (sklearn objects)
    "models": {
        "rf": RandomForestClassifier(...),      # Trained model
        "gb": GradientBoostingClassifier(...),  # Trained model
    },
    
    # Optimized weights
    "weights": {
        "rf": 0.473,
        "gb": 0.527,
    },
    
    # Performance metrics
    "ensemble_accuracy": 0.601,
    "performances": {
        "rf": {
            "train_accuracy": 0.823,
            "valid_accuracy": 0.587,
            "precision": 0.582,
            "recall": 0.587,
            "f1": 0.575,
        },
        "gb": {
            "train_accuracy": 0.794,
            "valid_accuracy": 0.592,
            "precision": 0.589,
            "recall": 0.592,
            "f1": 0.582,
        },
    },
    
    # Sample predictions for validation
    "model_predictions_sample": {
        "rf": [[0.7, 0.2, 0.1], [0.6, 0.3, 0.1], ...],
        "gb": [[0.6, 0.3, 0.1], [0.7, 0.2, 0.1], ...],
    },
}
```

---

## Version Management & Rollback

### List Available Versions

```python
from ml.src.models.ensemble_loader import EnsembleLoader

# List all versions
models = EnsembleLoader.list_available_models()
print(models)
# Output:
# {
#     "AAPL_d1": ["20250121", "20250114", "20250107"],
#     "AAPL_h1": ["20250121", "20250114"],
# }
```

### Rollback to Previous Version

```python
from ml.src.models.ensemble_loader import EnsembleLoader
import shutil
from pathlib import Path

# Get current model
current = EnsembleLoader.load_latest_model("AAPL", "d1")
print(f"Current: {current['timestamp']}")

# Load previous version
models_dir = Path("/Users/ericpeterson/SwiftBolt_ML/trained_models")
all_versions = sorted(models_dir.glob("AAPL_d1_*.pkl"), reverse=True)

if len(all_versions) > 1:
    previous = all_versions[1]
    print(f"Rolling back to: {previous.name}")
    # The loader will automatically pick this as "latest" after current is removed
```

---

## Testing the Integration

### Test 1: Verify Models Can Be Loaded

```python
from ml.src.models.ensemble_loader import EnsembleLoader

# Check what models are available
available = EnsembleLoader.list_available_models()
print(f"Available models: {available}")

# Load specific model
model_info = EnsembleLoader.get_model_info("AAPL", "d1")
if model_info:
    print(f"Loaded: {model_info['timestamp']}")
    print(f"Accuracy: {model_info['ensemble_accuracy']:.1%}")
    print(f"Weights: {model_info['weights']}")
else:
    print("No trained models found - run training job first")
```

### Test 2: Verify Ensemble Initialization

```python
from ml.src.models.ensemble_loader import get_production_ensemble_with_trained_weights

ensemble = get_production_ensemble_with_trained_weights("AAPL", "d1")

if ensemble.is_trained:
    print("✅ Ensemble is trained")
    print(f"Weights: {ensemble.ensemble_manager.ensemble.weights}")
else:
    print("❌ Ensemble not trained")
```

### Test 3: Verify End-to-End Prediction

```python
import pandas as pd
from ml.src.models.ensemble_loader import get_production_ensemble_with_trained_weights

# Create dummy data
df = pd.DataFrame({
    "close": [100, 101, 102, 103, 104],
    "rsi": [50, 55, 60, 65, 70],
    "macd": [0, 0.1, 0.2, 0.3, 0.4],
    # ... add other required features ...
})

ensemble = get_production_ensemble_with_trained_weights("AAPL", "d1")

if ensemble.is_trained:
    result = ensemble.predict(df)
    print(f"Prediction: {result['label']}")
    print(f"Confidence: {result['confidence']:.1%}")
    print(f"Agreement: {result['agreement']:.1%}")
else:
    print("Ensemble not trained")
```

---

## Troubleshooting

### Issue: "No models found for AAPL/d1"

**Solution**: Run training job first

```bash
cd /Users/ericpeterson/SwiftBolt_ML
python -m ml.src.training.ensemble_training_job --symbol AAPL
```

### Issue: "Failed to load model"

**Solution**: Check file permissions and pickle compatibility

```bash
ls -lh trained_models/  # Check files exist
python -c "import pickle; pickle.load(open('trained_models/AAPL_d1_*.pkl', 'rb'))"  # Test load
```

### Issue: "Ensemble prediction returns error"

**Solution**: Verify feature columns match training

```python
# Check what features were used for training
artifact = EnsembleLoader.load_latest_model("AAPL", "d1")
print(f"Training used {artifact['performances']['rf']['n_features']} features")
print(f"Current data has {len(df.columns)} columns")
```

---

## Next Steps

1. ✅ Review this integration guide
2. → Implement `ensemble_loader.py` in `ml/src/models/`
3. → Update `multi_horizon_forecast_job.py` to use new loader
4. → Test with single symbol (AAPL)
5. → See `DRIFT_MONITORING_SYSTEM.md` for production monitoring
