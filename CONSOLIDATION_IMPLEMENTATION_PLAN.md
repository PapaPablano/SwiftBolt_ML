# SwiftBolt ML - Consolidation & Optimization Implementation Plan
**Date**: January 23, 2026  
**Target**: Unified processing pipeline with 4-6x performance improvement

---

## PHASE 1: ANALYSIS & PLANNING (Week 1)

### Step 1.1: Script Dependency Mapping

**Action**: Create comprehensive dependency graph

```bash
# Commands to run:
cd /Users/ericpeterson/SwiftBolt_ML

# 1. Map all imports between forecast jobs
grep -r "from src" ml/src/forecast_job.py ml/src/multi_horizon_forecast_job.py ml/src/intraday_forecast_job.py > IMPORTS_MAPPING.txt

# 2. Identify feature_cache usage
grep -r "fetch_or_build_features" ml/src/*.py > FEATURE_CACHE_USAGE.txt

# 3. Find all DB writes
grep -r "db.insert\|db.upsert" ml/src/*.py > DB_WRITES_MAPPING.txt

# 4. Identify weights usage
grep -r "get_calibrated_weights\|fetch_symbol_model_weights\|get_default_weights" ml/src/*.py > WEIGHTS_USAGE.txt
```

**Deliverable**: `/Users/ericpeterson/SwiftBolt_ML/DEPENDENCY_ANALYSIS.md`

---

### Step 1.2: Current Behavior Baseline

**Action**: Instrument existing scripts to measure:
- Processing time per symbol
- Feature cache hit rate
- Database write conflicts
- Weight selection path

**Code snippet to add to forecast_job.py**:

```python
import json
import time
from datetime import datetime

class ProcessingMetrics:
    def __init__(self):
        self.metrics = {
            'start_time': datetime.now().isoformat(),
            'symbols_processed': 0,
            'feature_cache_hits': 0,
            'feature_cache_misses': 0,
            'feature_rebuild_times': [],
            'forecast_times': [],
            'weight_source': [],
            'db_writes': 0,
            'errors': []
        }
    
    def log_feature_access(self, symbol, cache_hit, rebuild_time):
        if cache_hit:
            self.metrics['feature_cache_hits'] += 1
        else:
            self.metrics['feature_cache_misses'] += 1
            self.metrics['feature_rebuild_times'].append(rebuild_time)
    
    def log_weight_source(self, symbol, source):
        self.metrics['weight_source'].append({
            'symbol': symbol,
            'source': source,
            'timestamp': datetime.now().isoformat()
        })
    
    def save_to_file(self, filename='processing_metrics.json'):
        with open(filename, 'w') as f:
            json.dump(self.metrics, f, indent=2, default=str)

# Usage in forecast_job.py
metrics = ProcessingMetrics()

# Before feature fetch
start = time.time()
features = fetch_or_build_features(...)
rebuild_time = time.time() - start
metrics.log_feature_access(symbol, cache_hit=False, rebuild_time=rebuild_time)

# After weights selection
weights = _get_symbol_layer_weights(...)
metrics.log_weight_source(symbol, source_used)

# At end
metrics.save_to_file('forecast_job_metrics_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.json')
```

**Deliverable**: Baseline metrics files in `/Users/ericpeterson/SwiftBolt_ML/metrics/baseline/`

---

### Step 1.3: Testing Infrastructure Setup

**Action**: Create test harness for parallel execution

```bash
# Create test directory
mkdir -p /Users/ericpeterson/SwiftBolt_ML/tests/audit_tests

# Create comparison test
cat > tests/audit_tests/test_forecast_consolidation.py << 'EOF'
"""Test that consolidated forecast matches original."""
import pytest
from src.forecast_job import generate_forecast_daily as original_forecast
from src.unified_forecast_job import generate_forecast_daily as unified_forecast

@pytest.mark.parametrize('symbol_id', ['AAPL', 'MSFT', 'GOOGL', 'TSLA'])
def test_forecast_equivalence(symbol_id):
    """Both forecast methods should produce equivalent results."""
    # Generate forecasts using both methods
    original_result = original_forecast(symbol_id, horizons=['1D', '1W', '1M'])
    unified_result = unified_forecast(symbol_id, horizons=['1D', '1W', '1M'])
    
    # Compare predictions (allow 0.5% variance due to numerical precision)
    for horizon in ['1D', '1W', '1M']:
        orig_price = original_result[horizon]['target_price']
        unified_price = unified_result[horizon]['target_price']
        variance = abs(orig_price - unified_price) / orig_price
        assert variance < 0.005, f"Price variance {variance*100:.2f}% for {symbol_id} {horizon}"
        
        # Confidence should be very close
        orig_conf = original_result[horizon]['confidence']
        unified_conf = unified_result[horizon]['confidence']
        assert abs(orig_conf - unified_conf) < 0.01
        
        # Overall label should match
        assert original_result[horizon]['overall_label'] == unified_result[horizon]['overall_label']

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
EOF
```

**Deliverable**: Test suite in `/Users/ericpeterson/SwiftBolt_ML/tests/audit_tests/`

---

## PHASE 2: CONSOLIDATION (Week 2-3)

### Step 2.1: Create Unified Forecast Job

**Action**: Merge `forecast_job.py`, `multi_horizon_forecast_job.py`, and `multi_horizon_forecast.py`

**File**: `/Users/ericpeterson/SwiftBolt_ML/ml/src/unified_forecast_job.py` (NEW)

```python
"""
Unified ML forecasting job - consolidates all daily forecast generation.

Merges:
- forecast_job.py (primary daily forecasts)
- multi_horizon_forecast_job.py (multi-horizon variant)
- multi_horizon_forecast.py (service layer)

Goals:
- Single write path to ml_forecasts table
- Eliminate redundant features rebuilds
- Explicit weight precedence with logging
- Version tracking for all outputs
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from src.data.data_validator import OHLCValidator, ValidationResult
from src.data.supabase_db import db
from src.features.feature_cache import fetch_or_build_features, FeatureCache
from src.forecast_synthesizer import ForecastResult, ForecastSynthesizer
from src.forecast_weights import get_default_weights
from src.models.enhanced_ensemble_integration import get_production_ensemble
from src.monitoring.confidence_calibrator import ConfidenceCalibrator
from src.monitoring.forecast_quality import ForecastQualityMonitor
from src.monitoring.forecast_validator import ForecastValidator
from src.monitoring.price_monitor import PriceMonitor
from src.strategies.supertrend_ai import SuperTrendAI

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


class UnifiedForecastProcessor:
    """Central forecast processor for daily forecasts (1D, 1W, 1M)."""
    
    def __init__(self, redis_cache=None, metrics_file=None):
        """
        Initialize processor.
        
        Args:
            redis_cache: Optional Redis connection for distributed caching
            metrics_file: Optional file to write processing metrics
        """
        self.redis_cache = redis_cache
        self.metrics_file = metrics_file or 'unified_forecast_metrics.json'
        self.metrics = {
            'start_time': datetime.now().isoformat(),
            'symbols_processed': 0,
            'feature_cache_hits': 0,
            'feature_cache_misses': 0,
            'forecast_times': [],
            'weight_sources': {},
            'db_writes': 0,
            'errors': [],
            'version_id': None,
        }
        
        # Initialize global calibrator once
        self.calibrator = ConfidenceCalibrator()
        self._load_calibrator()
        
        # Initialize ensemble (loaded once, reused)
        self.ensemble = get_production_ensemble()
        
        # Validation metrics cached
        self.validation_metrics = self._load_validation_metrics()
    
    def _load_calibrator(self):
        """Load confidence calibrator from DB."""
        try:
            historical = db.fetch_historical_forecasts_for_calibration(
                lookback_days=90,
                min_samples=100,
            )
            if historical is not None and len(historical) >= 100:
                results = self.calibrator.fit(historical)
                logger.info(f"Calibrator fitted with {len(historical)} samples")
                for result in results:
                    try:
                        # Persist buckets
                        db.upsert_confidence_calibration(
                            horizon='global',
                            bucket_low=float(result.bucket.split('-')[0]) / 100,
                            bucket_high=float(result.bucket.split('-')[1]) / 100,
                            predicted_confidence=result.predicted_confidence,
                            actual_accuracy=result.actual_accuracy,
                            adjustment_factor=result.adjustment_factor,
                            n_samples=result.n_samples,
                            is_calibrated=result.is_calibrated,
                        )
                    except Exception as exc:
                        logger.warning(f"Failed to persist calibration: {exc}")
        except Exception as e:
            logger.warning(f"Could not load calibrator: {e}")
    
    def _load_validation_metrics(self) -> Optional[Dict]:
        """Load validation metrics for logging."""
        try:
            lookback = int(os.getenv('FORECAST_VALIDATION_LOOKBACK_DAYS', '90'))
            forecasts_df, actuals_df = db.fetch_forecast_validation_data(lookback_days=lookback)
            if forecasts_df.empty or actuals_df.empty:
                return None
            
            validator = ForecastValidator()
            metrics = validator.validate(forecasts_df, actuals_df)
            return metrics.to_dict()
        except Exception as e:
            logger.warning(f"Could not load validation metrics: {e}")
            return None
    
    def _get_weight_source(self, symbol_id: str, horizon: str) -> tuple[Dict[str, float], str]:
        """
        Get forecast layer weights with explicit precedence.
        
        Priority order:
        1. Intraday-calibrated weights (if available and fresh)
        2. Symbol-specific daily weights (if enabled)
        3. Default weights (hardcoded fallback)
        
        Returns:
            (weights_dict, source_name)
        """
        # Priority 1: Intraday-calibrated weights
        if os.getenv('ENABLE_INTRADAY_CALIBRATION', 'true').lower() == 'true':
            try:
                calibrated = db.get_calibrated_weights(
                    symbol_id=symbol_id,
                    horizon=horizon,
                    min_samples=50,
                )
                if calibrated is not None:
                    weights = {
                        k: float(calibrated.get(k, 0))
                        for k in ('supertrend_component', 'sr_component', 'ensemble_component')
                    }
                    if sum(weights.values()) > 0:
                        normalized = {k: v / sum(weights.values()) for k, v in weights.items()}
                        logger.debug(f"Using intraday-calibrated weights for {symbol_id} {horizon}")
                        self.metrics['weight_sources']['intraday'] = self.metrics['weight_sources'].get('intraday', 0) + 1
                        return normalized, 'intraday_calibrated'
            except Exception as e:
                logger.debug(f"Intraday weights failed: {e}")
        
        # Priority 2: Symbol-specific daily weights
        if os.getenv('ENABLE_SYMBOL_WEIGHTS', 'false').lower() == 'true':
            try:
                row = db.fetch_symbol_model_weights(symbol_id=symbol_id, horizon=horizon)
                if row is not None:
                    synth_weights = row.get('synth_weights', {})
                    layer_weights = synth_weights.get('layer_weights', {})
                    weights = {
                        k: float(layer_weights.get(k, 0))
                        for k in ('supertrend_component', 'sr_component', 'ensemble_component')
                    }
                    if sum(weights.values()) > 0:
                        normalized = {k: v / sum(weights.values()) for k, v in weights.items()}
                        logger.debug(f"Using symbol weights for {symbol_id} {horizon}")
                        self.metrics['weight_sources']['daily_symbol'] = self.metrics['weight_sources'].get('daily_symbol', 0) + 1
                        return normalized, 'daily_symbol'
            except Exception as e:
                logger.debug(f"Symbol weights failed: {e}")
        
        # Priority 3: Default weights
        defaults = get_default_weights()
        self.metrics['weight_sources']['default'] = self.metrics['weight_sources'].get('default', 0) + 1
        return defaults, 'default'
    
    def process_symbol(
        self,
        symbol_id: str,
        horizons: list[str] = None,
        force_refresh: bool = False,
    ) -> Dict:
        """
        Generate forecast for single symbol across all horizons.
        
        Args:
            symbol_id: Symbol ID
            horizons: List of horizons ['1D', '1W', '1M']
            force_refresh: Skip cache, rebuild features
        
        Returns:
            Processing result dict
        """
        if horizons is None:
            horizons = ['1D', '1W', '1M']
        
        start_time = datetime.now()
        result = {
            'symbol_id': symbol_id,
            'success': False,
            'error': None,
            'forecasts': {},
            'processing_time': 0,
            'feature_cache_hit': False,
            'weight_source': {},
        }
        
        try:
            # === STEP 1: Get features (cached) ===
            logger.debug(f"Fetching features for {symbol_id}...")
            features = fetch_or_build_features(
                symbol_id=symbol_id,
                force_rebuild=force_refresh,
                redis_cache=self.redis_cache,
            )
            result['feature_cache_hit'] = not force_refresh
            if not force_refresh:
                self.metrics['feature_cache_hits'] += 1
            else:
                self.metrics['feature_cache_misses'] += 1
            
            # === STEP 2: Generate forecasts for each horizon ===
            for horizon in horizons:
                logger.debug(f"Generating {horizon} forecast for {symbol_id}...")
                
                # Get ensemble predictions
                ensemble_pred = self.ensemble.predict(
                    features=features,
                    horizon=horizon,
                )
                
                # Get layer weights
                weights, weight_source = self._get_weight_source(symbol_id, horizon)
                result['weight_source'][horizon] = weight_source
                
                # Synthesize forecast
                synthesizer = ForecastSynthesizer(
                    supertrend_ai=SuperTrendAI(),
                    support_resistance_detector=None,  # Already in features
                    layer_weights=weights,
                )
                
                forecast = synthesizer.synthesize(
                    ensemble_prediction=ensemble_pred,
                    features=features,
                    symbol_id=symbol_id,
                    horizon=horizon,
                )
                
                # Calibrate confidence
                if self.calibrator is not None:
                    forecast['confidence'] = self.calibrator.calibrate(
                        raw_confidence=forecast.get('confidence', 0.5),
                        horizon=horizon,
                    )
                
                result['forecasts'][horizon] = forecast
            
            # === STEP 3: Write to database ===
            for horizon in horizons:
                forecast = result['forecasts'][horizon]
                forecast['symbol_id'] = symbol_id
                forecast['horizon'] = horizon
                forecast['validation_metrics'] = self.validation_metrics
                forecast['weight_source'] = result['weight_source'][horizon]
                
                db.upsert_forecast(forecast, table='ml_forecasts')
            
            result['success'] = True
            self.metrics['db_writes'] += len(horizons)
            
        except Exception as e:
            logger.error(f"Error processing {symbol_id}: {e}", exc_info=True)
            result['error'] = str(e)
            self.metrics['errors'].append({
                'symbol_id': symbol_id,
                'error': str(e),
                'timestamp': datetime.now().isoformat(),
            })
        
        finally:
            result['processing_time'] = (datetime.now() - start_time).total_seconds()
            self.metrics['forecast_times'].append(result['processing_time'])
            self.metrics['symbols_processed'] += 1
        
        return result
    
    def process_universe(
        self,
        symbols: Optional[list[str]] = None,
        force_refresh: bool = False,
        max_workers: int = 4,
    ) -> Dict:
        """
        Process entire symbol universe.
        
        Args:
            symbols: Optional list of symbols (if None, uses watchlist)
            force_refresh: Skip cache
            max_workers: Number of parallel workers
        
        Returns:
            Aggregated results
        """
        # Get symbol universe if not provided
        if symbols is None:
            logger.info("Fetching symbol universe...")
            symbols = db.get_symbol_universe()  # From watchlists
        
        logger.info(f"Processing {len(symbols)} symbols...")
        
        results = []
        for i, symbol_id in enumerate(symbols):
            if (i + 1) % 100 == 0:
                logger.info(f"Progress: {i + 1}/{len(symbols)}")
            result = self.process_symbol(symbol_id, force_refresh=force_refresh)
            results.append(result)
        
        # Aggregate results
        aggregated = {
            'total_symbols': len(symbols),
            'successful': sum(1 for r in results if r['success']),
            'failed': sum(1 for r in results if not r['success']),
            'total_processing_time': sum(r['processing_time'] for r in results),
            'avg_processing_time': np.mean([r['processing_time'] for r in results]),
            'feature_cache_hit_rate': self.metrics['feature_cache_hits'] / (
                self.metrics['feature_cache_hits'] + self.metrics['feature_cache_misses']
            ) if (self.metrics['feature_cache_hits'] + self.metrics['feature_cache_misses']) > 0 else 0,
        }
        
        logger.info(f"\nProcessing Complete:")
        logger.info(f"  Successful: {aggregated['successful']}/{aggregated['total_symbols']}")
        logger.info(f"  Failed: {aggregated['failed']}")
        logger.info(f"  Total time: {aggregated['total_processing_time']:.1f}s")
        logger.info(f"  Avg per symbol: {aggregated['avg_processing_time']:.2f}s")
        logger.info(f"  Feature cache hit rate: {aggregated['feature_cache_hit_rate']*100:.1f}%")
        logger.info(f"  Weight sources: {self.metrics['weight_sources']}")
        
        self.metrics['aggregated'] = aggregated
        self.save_metrics()
        
        return aggregated
    
    def save_metrics(self):
        """Save processing metrics to file."""
        self.metrics['end_time'] = datetime.now().isoformat()
        with open(self.metrics_file, 'w') as f:
            json.dump(self.metrics, f, indent=2, default=str)
        logger.info(f"Metrics saved to {self.metrics_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Unified ML Forecast Job')
    parser.add_argument('--symbol', help='Process single symbol (for testing)')
    parser.add_argument('--force-refresh', action='store_true', help='Rebuild features')
    parser.add_argument('--metrics-file', help='Output metrics file')
    parser.add_argument('--redis-host', default='localhost', help='Redis host')
    parser.add_argument('--redis-port', type=int, default=6379, help='Redis port')
    
    args = parser.parse_args()
    
    # Initialize Redis cache if available
    redis_cache = None
    try:
        import redis
        redis_cache = redis.Redis(
            host=args.redis_host,
            port=args.redis_port,
            decode_responses=True,
        )
        logger.info(f"Connected to Redis at {args.redis_host}:{args.redis_port}")
    except Exception as e:
        logger.warning(f"Could not connect to Redis: {e}")
    
    # Create processor
    processor = UnifiedForecastProcessor(
        redis_cache=redis_cache,
        metrics_file=args.metrics_file or 'unified_forecast_metrics.json',
    )
    
    # Process
    if args.symbol:
        logger.info(f"Processing single symbol: {args.symbol}")
        result = processor.process_symbol(args.symbol, force_refresh=args.force_refresh)
        logger.info(f"Result: {json.dumps(result, indent=2, default=str)}")
    else:
        logger.info("Processing full universe")
        results = processor.process_universe(force_refresh=args.force_refresh)
        logger.info(f"Aggregated: {json.dumps(results, indent=2, default=str)}")


if __name__ == '__main__':
    main()
```

**Deliverable**: `/Users/ericpeterson/SwiftBolt_ML/ml/src/unified_forecast_job.py`

---

### Step 2.2: Split Evaluation Jobs

**Action**: Create separate daily and intraday evaluation jobs

**File 1**: `/Users/ericpeterson/SwiftBolt_ML/ml/src/evaluation_job_daily.py` (NEW)

```python
"""
Daily evaluation job - evaluates 1D, 1W, 1M forecasts only.

Runs AFTER daily forecasts complete.
Writes to forecast_evaluations_daily (separate table).
Populates live_predictions_daily.
"""

import logging
from src.monitoring.forecast_validator import ForecastValidator
from src.data.supabase_db import db

logger = logging.getLogger(__name__)

def evaluate_daily_forecasts():
    """Evaluate only daily forecasts (1D, 1W, 1M)."""
    logger.info("Starting daily forecast evaluation...")
    
    # Fetch ONLY daily forecasts
    forecasts = db.fetch_forecasts(
        horizons=['1D', '1W', '1M'],
        table='ml_forecasts',
        status='pending_evaluation',
    )
    
    logger.info(f"Found {len(forecasts)} forecasts to evaluate")
    
    validator = ForecastValidator()
    evaluated_count = 0
    
    for forecast in forecasts:
        try:
            # Get realized price
            realized_price = db.get_realized_price(
                symbol_id=forecast['symbol_id'],
                horizon=forecast['horizon'],
                as_of=forecast['created_at'],
            )
            
            if realized_price is None:
                logger.debug(f"No realized price yet for {forecast['symbol_id']} {forecast['horizon']}")
                continue
            
            # Evaluate
            evaluation = validator.evaluate_single(
                forecast=forecast,
                realized_price=realized_price,
            )
            
            # Write to DAILY table (not mixed with intraday)
            db.insert_evaluation(
                evaluation,
                table='forecast_evaluations_daily',
            )
            
            evaluated_count += 1
            
        except Exception as e:
            logger.error(f"Error evaluating forecast: {e}")
    
    # Populate live_predictions_daily
    logger.info("Updating live_predictions_daily...")
    db.populate_live_predictions(
        lookback_days=90,
        horizons=['1D', '1W', '1M'],
        table='forecast_evaluations_daily',
        output_table='live_predictions_daily',
    )
    
    logger.info(f"Daily evaluation complete: {evaluated_count} forecasts evaluated")

if __name__ == '__main__':
    evaluate_daily_forecasts()
```

**File 2**: `/Users/ericpeterson/SwiftBolt_ML/ml/src/evaluation_job_intraday.py` (NEW)

```python
"""
Intraday evaluation job - evaluates 15m, 1h forecasts only.

Runs hourly (separate from daily evaluation).
Writes to forecast_evaluations_intraday (separate table).
Populates live_predictions_intraday.

"""

import logging
from src.monitoring.forecast_validator import ForecastValidator
from src.data.supabase_db import db

logger = logging.getLogger(__name__)

def evaluate_intraday_forecasts():
    """Evaluate only intraday forecasts (15m, 1h)."""
    logger.info("Starting intraday forecast evaluation...")
    
    # Fetch ONLY intraday forecasts
    forecasts = db.fetch_forecasts(
        horizons=['15m', '1h'],
        table='ml_forecasts_intraday',
        status='pending_evaluation',
    )
    
    logger.info(f"Found {len(forecasts)} intraday forecasts to evaluate")
    
    validator = ForecastValidator()
    evaluated_count = 0
    
    for forecast in forecasts:
        try:
            # Get realized price (shorter lookback for intraday)
            realized_price = db.get_realized_price(
                symbol_id=forecast['symbol_id'],
                horizon=forecast['horizon'],
                as_of=forecast['created_at'],
            )
            
            if realized_price is None:
                logger.debug(f"No realized price yet for {forecast['symbol_id']} {forecast['horizon']}")
                continue
            
            # Evaluate
            evaluation = validator.evaluate_single(
                forecast=forecast,
                realized_price=realized_price,
            )
            
            # Write to INTRADAY table (not mixed with daily)
            db.insert_evaluation(
                evaluation,
                table='forecast_evaluations_intraday',
            )
            
            evaluated_count += 1
            
        except Exception as e:
            logger.error(f"Error evaluating intraday forecast: {e}")
    
    # Populate live_predictions_intraday
    logger.info("Updating live_predictions_intraday...")
    db.populate_live_predictions(
        lookback_days=7,  # Shorter lookback for intraday
        horizons=['15m', '1h'],
        table='forecast_evaluations_intraday',
        output_table='live_predictions_intraday',
    )
    
    logger.info(f"Intraday evaluation complete: {evaluated_count} forecasts evaluated")

if __name__ == '__main__':
    evaluate_intraday_forecasts()
```

**Deliverables**:
- `/Users/ericpeterson/SwiftBolt_ML/ml/src/evaluation_job_daily.py`
- `/Users/ericpeterson/SwiftBolt_ML/ml/src/evaluation_job_intraday.py`

---

### Step 2.3: Implement Redis Feature Caching

**File**: Modify `/Users/ericpeterson/SwiftBolt_ML/ml/src/features/feature_cache.py`

```python
# Add to existing feature_cache.py

import json
import pickle
from typing import Optional, Dict

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

class DistributedFeatureCache:
    """Redis-backed distributed feature cache with TTL."""
    
    def __init__(self, redis_client=None, ttl_seconds=86400):
        """
        Args:
            redis_client: Redis connection (if None, creates new)
            ttl_seconds: Cache TTL (default 24 hours)
        """
        self.redis_client = redis_client
        self.ttl_seconds = ttl_seconds
    
    def get_cache_key(self, symbol_id: str, timeframe: str) -> str:
        """Generate cache key."""
        return f"features:{symbol_id}:{timeframe}"
    
    def get(self, symbol_id: str, timeframe: str) -> Optional[Dict]:
        """Get features from cache."""
        if self.redis_client is None:
            return None
        
        try:
            key = self.get_cache_key(symbol_id, timeframe)
            data = self.redis_client.get(key)
            if 
                return json.loads(data)
        except Exception as e:
            logger.debug(f"Cache get error: {e}")
        
        return None
    
    def set(self, symbol_id: str, timeframe: str, features: Dict) -> bool:
        """Set features in cache with TTL."""
        if self.redis_client is None:
            return False
        
        try:
            key = self.get_cache_key(symbol_id, timeframe)
            data = json.dumps(features, default=str)
            self.redis_client.setex(key, self.ttl_seconds, data)
            return True
        except Exception as e:
            logger.debug(f"Cache set error: {e}")
        
        return False
    
    def delete(self, symbol_id: str, timeframe: str) -> bool:
        """Delete features from cache."""
        if self.redis_client is None:
            return False
        
        try:
            key = self.get_cache_key(symbol_id, timeframe)
            self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.debug(f"Cache delete error: {e}")
        
        return False


# Modify fetch_or_build_features to use Redis cache
def fetch_or_build_features(
    symbol_id: str,
    ohlc_ Optional[pd.DataFrame] = None,
    force_rebuild: bool = False,
    redis_cache: Optional = None,
    timeframes: list[str] = None,
) -> Dict:
    """Fetch or build features with Redis caching."""
    if timeframes is None:
        timeframes = ['d1', 'h1', 'm15']
    
    cache = DistributedFeatureCache(redis_client=redis_cache, ttl_seconds=86400)
    features = {}
    
    for timeframe in timeframes:
        # Check Redis cache first
        if not force_rebuild:
            cached = cache.get(symbol_id, timeframe)
            if cached is not None:
                logger.debug(f"Cache hit: {symbol_id} {timeframe}")
                features[timeframe] = cached
                continue
        
        # Miss or force rebuild - build features
        logger.debug(f"Building features: {symbol_id} {timeframe}")
        
        # Get OHLC data if not provided
        if ohlc_data is None:
            ohlc_data = db.fetch_ohlc_bars(
                symbol_id=symbol_id,
                timeframe=timeframe,
                limit=500,
            )
        
        # Build features
        indicators = calculate_technical_indicators(ohlc_data)
        sr_levels = detect_support_resistance(ohlc_data)
        regime = detect_market_regime(ohlc_data)
        
        features[timeframe] = {
            'indicators': indicators,
            'sr_levels': sr_levels,
            'regime': regime,
            'ohlc': ohlc_data.to_dict('records'),
        }
        
        # Store in Redis for next worker
        cache.set(symbol_id, timeframe, features[timeframe])
        logger.debug(f"Cached: {symbol_id} {timeframe}")
    
    return features
```

**Deliverable**: Updated `/Users/ericpeterson/SwiftBolt_ML/ml/src/features/feature_cache.py`

---

### Step 2.4: Update GitHub Actions Workflows

**File**: `/Users/ericpeterson/SwiftBolt_ML/.github/workflows/ml-orchestration.yml` (REPLACE)

```yaml
name: ml-orchestration

on:
  workflow_dispatch:
  schedule:
    # 04:00 UTC (10:00 PM CST)
    - cron: '0 4 * * *'
  # Trigger after daily data refresh completes
  workflow_run:
    workflows: [daily-data-refresh]
    types: [completed]

jobs:
  unified-forecast:
    name: Unified Daily Forecasts (1D, 1W, 1M)
    runs-on: ubuntu-latest
    timeout-minutes: 60
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - name: Run Unified Forecast Job
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
          REDIS_HOST: ${{ secrets.REDIS_HOST }}
          REDIS_PORT: ${{ secrets.REDIS_PORT }}
        run: |
          python ml/src/unified_forecast_job.py \
            --redis-host $REDIS_HOST \
            --redis-port $REDIS_PORT \
            --metrics-file unified_forecast_metrics.json
      - name: Upload Metrics
        if: always()
        run: |
          # Upload metrics to artifact or DB
          python scripts/publish_metrics.py unified_forecast_metrics.json

  daily-evaluation:
    name: Daily Forecast Evaluation
    needs: [unified-forecast]
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - name: Run Daily Evaluation
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
        run: |
          python ml/src/evaluation_job_daily.py

  options-processing:
    name: Options Ranking (Daily)
    needs: [unified-forecast]
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - name: Run Options Processing
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
        run: |
          python ml/src/options_ranking_job.py
```

**New File**: `/Users/ericpeterson/SwiftBolt_ML/.github/workflows/intraday-orchestration.yml`

```yaml
name: intraday-orchestration

on:
  schedule:
    # Every hour during market hours (9:30 AM - 4:00 PM EST)
    - cron: '0 13-20 * * 1-5'  # 1 PM - 8 PM UTC = 9 AM - 4 PM EST
  workflow_dispatch:

jobs:
  intraday-forecast:
    name: Intraday Forecasts (15m, 1h)
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - name: Run Intraday Forecast
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
          REDIS_HOST: ${{ secrets.REDIS_HOST }}
          REDIS_PORT: ${{ secrets.REDIS_PORT }}
        run: |
          python ml/src/intraday_forecast_job.py \
            --redis-host $REDIS_HOST \
            --redis-port $REDIS_PORT

  intraday-evaluation:
    name: Intraday Forecast Evaluation
    needs: [intraday-forecast]
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - name: Run Intraday Evaluation
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
        run: |
          python ml/src/evaluation_job_intraday.py
```

**Deliverables**:
- Updated `/Users/ericpeterson/SwiftBolt_ML/.github/workflows/ml-orchestration.yml`
- New `/Users/ericpeterson/SwiftBolt_ML/.github/workflows/intraday-orchestration.yml`

---

## PHASE 3: TESTING & VALIDATION (Week 3)

### Step 3.1: Run Parallel Tests

```bash
cd /Users/ericpeterson/SwiftBolt_ML

# Run test suite
python -m pytest tests/audit_tests/test_forecast_consolidation.py -v

# Run metrics comparison
python scripts/compare_metrics.py \
  metrics/baseline/forecast_job_metrics.json \
  metrics/unified/unified_forecast_metrics.json
```

**Deliverable**: Test report in `tests/audit_tests/test_results.md`

---

### Step 3.2: Performance Benchmarking

```bash
# Baseline: Old system
time python ml/src/forecast_job.py > baseline_output.log

# New: Unified system
time python ml/src/unified_forecast_job.py > unified_output.log

# Compare
python scripts/benchmark_comparison.py baseline_output.log unified_output.log
```

**Deliverable**: Performance report in `PERFORMANCE_COMPARISON.md`

---

## PHASE 4: PRODUCTION DEPLOYMENT (Week 4)

### Step 4.1: Archive Old Scripts

```bash
cd /Users/ericpeterson/SwiftBolt_ML

# Create archive directory
mkdir -p ml/src/_legacy

# Move old scripts
mv ml/src/forecast_job.py ml/src/_legacy/
mv ml/src/multi_horizon_forecast_job.py ml/src/_legacy/
mv ml/src/multi_horizon_forecast.py ml/src/_legacy/
mv ml/src/evaluation_job.py ml/src/_legacy/forecast_job_original.py
mv ml/src/intraday_evaluation_job.py ml/src/_legacy/
mv ml/src/forecast_job_worker.py ml/src/_legacy/
mv ml/src/job_worker.py ml/src/_legacy/
mv ml/src/ranking_job_worker.py ml/src/_legacy/
mv ml/src/hourly_ranking_scheduler.py ml/src/_legacy/

# Create README explaining legacy
cat > ml/src/_legacy/README.md << 'EOF'
# Legacy Scripts (Archived)

These scripts have been consolidated into unified processors:

- `forecast_job.py` → `unified_forecast_job.py`
- `multi_horizon_forecast_job.py` → `unified_forecast_job.py`
- `multi_horizon_forecast.py` → `unified_forecast_job.py`
- `evaluation_job.py` → `evaluation_job_daily.py`
- `intraday_evaluation_job.py` → `evaluation_job_intraday.py`
- `ranking_job_worker.py` → Removed (redundant)
- `hourly_ranking_scheduler.py` → Removed (integrated into daily processing)

Kept for reference only.
EOF
```

### Step 4.2: Update Configuration

```bash
# Update .env to disable old jobs
echo "\n# NEW UNIFIED JOBS" >> .env
echo "USE_UNIFIED_FORECAST=true" >> .env
echo "USE_SEPARATE_EVALUATIONS=true" >> .env
echo "REDIS_FEATURE_CACHE=true" >> .env
```

### Step 4.3: Deploy & Monitor

```bash
# Push changes
git add -A
git commit -m "feat: consolidate forecast jobs into unified pipeline

- Merge forecast_job + multi_horizon variants → unified_forecast_job
- Split evaluation: daily + intraday (separate tables)
- Add Redis feature caching (24h TTL)
- Update GitHub Actions workflows
- Expected improvement: 4-6x processing speedup"

git push origin consolidation-unified-pipeline

# Create PR for review
# After approval, merge to master
```

---

## EXPECTED OUTCOMES

### Performance Improvements

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Feature Rebuilds | 9-14x | 1-2x | 7-12x fewer |
| Daily Processing Time | 60-90 min | 15-20 min | 4-6x faster |
| Cache Hit Rate | 0% | 95%+ | Massive reduction in computation |
| API Response Time | 2-3s | 200-400ms | 5-15x faster |
| Data Freshness Skew | 30-60 min | <5 min | 6-12x better |

### Data Quality Improvements

- Elimination of forecast_evaluations data mixing
- No more race conditions in weight selection
- Clear audit trail of which weights were used
- Separate daily/intraday pipelines (no interference)
- Version tracking for all outputs

### Maintenance Benefits

- 60% fewer scripts to maintain
- Explicit job dependencies (no implicit ordering)
- Clear error propagation and logging
- Easier to debug and modify
- Better test coverage

---

## ROLLBACK PLAN

If issues arise:

```bash
# 1. Revert code
git revert consolidation-unified-pipeline

# 2. Restore old scripts from legacy
cp ml/src/_legacy/forecast_job.py ml/src/
cp ml/src/_legacy/evaluation_job.py ml/src/
# ... etc

# 3. Revert workflows
git checkout HEAD~1 .github/workflows/ml-orchestration.yml

# 4. Re-enable old jobs
sed -i 's/USE_UNIFIED_FORECAST=true/USE_UNIFIED_FORECAST=false/' .env

# 5. Re-run old pipeline
python ml/src/forecast_job.py
```

---

**Total Timeline**: 4 weeks  
**Effort**: ~80-120 hours  
**Expected ROI**: 20-40 hours/month in perpetuity

