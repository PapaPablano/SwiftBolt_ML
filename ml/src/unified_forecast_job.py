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
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from src.data.data_validator import OHLCValidator
from src.data.supabase_db import db
from src.features.feature_cache import fetch_or_build_features
from src.features.support_resistance_detector import SupportResistanceDetector
from src.features.timeframe_consensus import add_consensus_to_forecast
from src.forecast_synthesizer import ForecastSynthesizer
from src.forecast_weights import get_default_weights
from src.intraday_daily_feedback import IntradayDailyFeedback
from src.models.baseline_forecaster import BaselineForecaster
from src.models.enhanced_ensemble_integration import get_production_ensemble
from src.monitoring.confidence_calibrator import ConfidenceCalibrator
from src.monitoring.forecast_quality import ForecastQualityMonitor
from src.monitoring.forecast_validator import ForecastValidator
from src.strategies.supertrend_ai import SuperTrendAI

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


class UnifiedForecastProcessor:
    """Central forecast processor for framework horizons (1D, 5D, 10D, 20D)."""
    
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
                        # Parse bucket string like "50-60%"
                        bucket_parts = result.bucket.replace('%', '').split('-')
                        bucket_low = float(bucket_parts[0]) / 100
                        bucket_high = float(bucket_parts[1]) / 100
                        
                        db.upsert_confidence_calibration(
                            horizon='global',
                            bucket_low=bucket_low,
                            bucket_high=bucket_high,
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
    
    def _get_weight_source(self, symbol: str, symbol_id: str, horizon: str) -> tuple:
        """
        Get forecast layer weights with explicit precedence using IntradayDailyFeedback.
        
        Priority order (handled by IntradayDailyFeedback):
        1. Fresh intraday-calibrated weights (< staleness threshold)
        2. Stale intraday-calibrated weights (with warning)
        3. Symbol-specific weights from database
        4. Default weights
        
        Returns:
            (ForecastWeights object, source_name)
        """
        try:
            # Use IntradayDailyFeedback abstraction layer (as per INTEGRATION_WORKFLOW_GUIDE.md)
            feedback_loop = IntradayDailyFeedback()
            weights_obj, source = feedback_loop.get_best_weights(symbol, horizon)
            
            # Track weight source in metrics
            source_key = source.split()[0].lower() if source else 'default'
            if 'intraday' in source_key or 'calibrated' in source_key:
                self.metrics['weight_sources']['intraday'] = self.metrics['weight_sources'].get('intraday', 0) + 1
            elif 'symbol' in source_key:
                self.metrics['weight_sources']['daily_symbol'] = self.metrics['weight_sources'].get('daily_symbol', 0) + 1
            else:
                self.metrics['weight_sources']['default'] = self.metrics['weight_sources'].get('default', 0) + 1
            
            logger.debug(f"Using weights from {source} for {symbol} {horizon}")
            return weights_obj, source
            
        except Exception as e:
            logger.warning(f"IntradayDailyFeedback failed for {symbol} {horizon}: {e}. Using default weights.")
            # Fallback to default weights
            defaults = get_default_weights()
            self.metrics['weight_sources']['default'] = self.metrics['weight_sources'].get('default', 0) + 1
            return defaults, 'default (fallback)'
    
    def process_symbol(
        self,
        symbol: str,
        horizons: list = None,
        force_refresh: bool = False,
    ) -> Dict:
        """
        Generate forecast for single symbol across all horizons.
        
        This method reuses the core logic from forecast_job.py but with
        improved metrics tracking and explicit weight source logging.
        
        Args:
            symbol: Symbol ticker
            horizons: List of horizons ['1D', '5D', '10D', '20D']
            force_refresh: Skip cache, rebuild features
        
        Returns:
            Processing result dict
        """
        if horizons is None:
            horizons = settings.forecast_horizons

        # Focus on framework horizons (1D/5D/10D/20D)
        focus_horizons = {"1D", "5D", "10D", "20D"}
        horizons = [h for h in horizons if str(h).upper() in focus_horizons]
        
        start_time = time.time()
        result = {
            'symbol': symbol,
            'success': False,
            'error': None,
            'forecasts': {},
            'processing_time': 0,
            'feature_cache_hit': False,
            'weight_source': {},
        }
        
        try:
            logger.info(f"Processing {symbol}...")
            
            # === STEP 1: Get features (with Redis cache if available) ===
            feature_start = time.time()
            cutoff_ts = pd.Timestamp.utcnow().normalize()
            features_by_tf = fetch_or_build_features(
                db=db,
                symbol=symbol,
                limits={"d1": 252},
                cutoff_ts=cutoff_ts,
                force_refresh=force_refresh,
            )
            feature_time = time.time() - feature_start
            df = features_by_tf.get("d1", pd.DataFrame())
            
            # Estimate cache hit based on timing
            cache_hit = feature_time < 0.5
            result['feature_cache_hit'] = cache_hit
            if cache_hit:
                self.metrics['feature_cache_hits'] += 1
            else:
                self.metrics['feature_cache_misses'] += 1
            
            if len(df) < settings.min_bars_for_training:
                logger.warning(
                    f"Insufficient data for {symbol}: {len(df)} bars "
                    f"(need {settings.min_bars_for_training})"
                )
                result['error'] = 'insufficient_data'
                return result
            
            # Get symbol_id
            symbol_id = db.get_symbol_id(symbol)
            
            # === STEP 2: Data validation ===
            validator = OHLCValidator()
            df, validation_result = validator.validate(df, fix_issues=True)
            data_quality_score = validator.get_data_quality_score(df)
            
            # Calculate quality multipliers
            data_quality_multiplier = max(
                0.9, 1.0 - (validation_result.rows_flagged / max(1, len(df)) * 0.2)
            )
            sample_size_multiplier = min(1.0, len(df) / settings.min_bars_for_high_confidence)
            
            # === STEP 3: Extract S/R levels ===
            sr_detector = SupportResistanceDetector()
            sr_levels = sr_detector.find_all_levels(df)
            current_price = df["close"].iloc[-1]
            
            # === STEP 4: SuperTrend processing ===
            supertrend_data = None
            try:
                supertrend = SuperTrendAI(df)
                st_df, st_info_raw = supertrend.calculate()
                
                supertrend_data = {
                    "supertrend_factor": st_info_raw["target_factor"],
                    "supertrend_performance": st_info_raw["performance_index"],
                    "supertrend_signal": int(st_df["supertrend_signal"].iloc[-1]),
                    "trend_label": st_info_raw["current_trend"],
                    "trend_confidence": st_info_raw["signal_strength"],
                    "stop_level": float(st_df["supertrend"].iloc[-1]),
                    "trend_duration_bars": st_info_raw["trend_duration_bars"],
                }
            except Exception as e:
                logger.warning(f"SuperTrend AI failed for {symbol}: {e}")
                st_info_raw = {
                    "current_trend": "NEUTRAL",
                    "signal_strength": 5,
                    "performance_index": 0.5,
                    "atr": current_price * 0.02,
                }
            
            # === STEP 5: Generate forecasts for each horizon ===
            for horizon in horizons:
                try:
                    horizon_key = str(horizon).upper()
                    logger.debug(f"Generating {horizon_key} forecast for {symbol}...")
                    
                    # Get horizon days
                    horizon_days = {
                        "1D": 1,
                        "5D": 5,
                        "10D": 10,
                        "20D": 20,
                    }.get(horizon_key, 1)
                    
                    # Use production ensemble (includes Transformer if ENABLE_TRANSFORMER=true)
                    # Fallback to BaselineForecaster if ensemble training fails
                    ml_pred = None
                    try:
                        # Get production ensemble (reads ENABLE_TRANSFORMER env var)
                        ensemble = get_production_ensemble(
                            horizon=horizon_key,
                            symbol_id=symbol_id,
                        )
                        
                        # Prepare training data using BaselineForecaster's method
                        baseline_prep = BaselineForecaster()
                        X_train, y_train = baseline_prep.prepare_training_data(df, horizon_days=horizon_days)
                        
                        if len(X_train) >= settings.min_bars_for_training and len(y_train) > 0:
                            # Calculate training data range (features correspond to indices after min_offset)
                            min_offset = 50 if len(df) >= 100 else (26 if len(df) >= 60 else 14)
                            start_idx = max(min_offset, 14)
                            end_idx = len(df) - horizon_days
                            
                            # Align OHLC data with training features
                            # Features are created for indices [start_idx, end_idx)
                            ohlc_train = df.iloc[start_idx:end_idx].copy()
                            
                            # Train ensemble
                            ensemble.train(
                                features_df=X_train,
                                labels_series=y_train,
                                ohlc_df=ohlc_train,
                            )
                            
                            # Get prediction using last row of features and corresponding OHLC
                            ml_pred = ensemble.predict(
                                features_df=X_train.tail(1),
                                ohlc_df=df.tail(1),
                            )
                            
                            logger.info(
                                f"Ensemble prediction for {symbol} {horizon_key}: "
                                f"{ml_pred.get('label', 'unknown').upper()} "
                                f"({ml_pred.get('confidence', 0):.0%} conf, "
                                f"n_models={ml_pred.get('n_models', 0)})"
                            )
                        else:
                            logger.warning(
                                f"Insufficient training data for ensemble: "
                                f"{len(X_train)} samples (need {settings.min_bars_for_training})"
                            )
                            raise ValueError("Insufficient training data")
                    except Exception as e:
                        logger.warning(
                            f"Ensemble training/prediction failed for {symbol} {horizon_key}: {e}. "
                            f"Falling back to BaselineForecaster."
                        )
                        # Fallback to BaselineForecaster
                        baseline_forecaster = BaselineForecaster()
                        baseline_forecaster.fit(df, horizon_days=horizon_days)
                        ml_pred = baseline_forecaster.predict(df, horizon_days=horizon_days)
                    
                    # Get layer weights with explicit source tracking (using IntradayDailyFeedback)
                    weights, weight_source = self._get_weight_source(symbol, symbol_id, horizon_key)
                    result['weight_source'][horizon_key] = weight_source
                    
                    # Create synthesizer
                    synthesizer = ForecastSynthesizer(weights=weights)
                    
                    # Generate synthesis
                    if horizon_days == 1:
                        synth_result = synthesizer.generate_1d_forecast(
                            current_price=current_price,
                            df=df,
                            supertrend_info=st_info_raw,
                            sr_response=sr_levels,
                            ensemble_result=ml_pred,
                            symbol=symbol,
                        )
                    else:
                        synth_result = synthesizer.generate_forecast(
                            current_price=current_price,
                            df=df,
                            supertrend_info=st_info_raw,
                            sr_response=sr_levels,
                            ensemble_result=ml_pred,
                            horizon_days=horizon_days,
                            symbol=symbol,
                            timeframe="d1",
                        )
                    
                    # Build forecast dict
                    forecast = {
                        "label": synth_result.direction.lower(),
                        "confidence": synth_result.confidence,
                        "horizon": horizon_key,
                        "points": self._build_forecast_points(synth_result, df["ts"].iloc[-1], horizon_days),
                        "synthesis": synth_result.to_dict(),
                        "weight_source": weight_source,
                    }
                    
                    # Apply confidence calibration
                    raw_confidence = forecast["confidence"]
                    adjusted_confidence = raw_confidence
                    
                    if self.calibrator.is_fitted:
                        adjusted_confidence = self.calibrator.calibrate(adjusted_confidence)
                    
                    adjusted_confidence *= data_quality_multiplier
                    adjusted_confidence *= sample_size_multiplier
                    adjusted_confidence = float(np.clip(adjusted_confidence, 0.40, 0.95))
                    
                    forecast["confidence"] = adjusted_confidence
                    forecast["raw_confidence"] = raw_confidence

                    # Add consensus scoring (cross-timeframe alignment)
                    try:
                        forecast = add_consensus_to_forecast(forecast, symbol_id)
                        logger.debug(
                            f"Consensus for {symbol} {horizon_key}: "
                            f"{forecast.get('consensus_direction', 'unknown')} "
                            f"(alignment={forecast.get('alignment_score', 0):.2f})"
                        )
                    except Exception as e:
                        logger.warning(f"Consensus scoring failed for {symbol} {horizon_key}: {e}")

                    # Quality gating + issue tracking
                    quality_context = {
                        "confidence": adjusted_confidence,
                        "model_agreement": forecast.get("model_agreement", 0.75),
                        "created_at": datetime.now(),
                        "conflicting_signals": 0,
                    }
                    quality_issues = ForecastQualityMonitor.check_quality_issues(quality_context)
                    quality_score = None
                    if isinstance(forecast.get("synthesis"), dict):
                        quality_score = forecast["synthesis"].get("quality_score")

                    confidence_gate_passed = adjusted_confidence >= settings.confidence_threshold
                    if not confidence_gate_passed:
                        quality_issues.append(
                            {
                                "level": "warning",
                                "type": "below_threshold",
                                "message": (
                                    f"Confidence {adjusted_confidence:.0%} below "
                                    f"threshold {settings.confidence_threshold:.0%}"
                                ),
                                "action": "review",
                            }
                        )
                        forecast["label"] = "neutral"

                    if isinstance(forecast.get("synthesis"), dict):
                        forecast["synthesis"]["confidence_gate"] = {
                            "passed": confidence_gate_passed,
                            "threshold": settings.confidence_threshold,
                        }
                    
                    result['forecasts'][horizon] = forecast
                    
                    # === STEP 6: Write to database ===
                    db.upsert_forecast(
                        symbol_id=symbol_id,
                        horizon=forecast["horizon"],
                        overall_label=forecast["label"],
                        confidence=forecast["confidence"],
                        points=forecast["points"],
                        supertrend_data=supertrend_data,
                        quality_score=quality_score,
                        quality_issues=quality_issues,
                        synthesis_data=forecast.get("synthesis"),
                    )
                    self.metrics['db_writes'] += 1
                    
                    logger.info(
                        f"Saved {horizon_key} forecast for {symbol}: "
                        f"{forecast['label'].upper()} "
                        f"({forecast['confidence']:.0%} conf, source={weight_source})"
                    )
                    
                except Exception as e:
                    logger.error(f"Error generating {horizon_key} forecast for {symbol}: {e}")
                    self.metrics['errors'].append({
                        'symbol': symbol,
                        'horizon': horizon_key,
                        'error': str(e),
                        'timestamp': datetime.now().isoformat(),
                    })
            
            result['success'] = len(result['forecasts']) > 0
            
        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}", exc_info=True)
            result['error'] = str(e)
            self.metrics['errors'].append({
                'symbol': symbol,
                'error': str(e),
                'timestamp': datetime.now().isoformat(),
            })
        
        finally:
            result['processing_time'] = time.time() - start_time
            self.metrics['forecast_times'].append(result['processing_time'])
            self.metrics['symbols_processed'] += 1
        
        return result
    
    def _build_forecast_points(self, synth_result, current_ts, horizon_days):
        """Build forecast points from synthesis result."""
        target_ts = current_ts + timedelta(days=horizon_days)
        current_price = float(synth_result.current_price or synth_result.target)
        target_price = float(synth_result.target)
        lower_band = float(synth_result.lower_band)
        upper_band = float(synth_result.upper_band)
        return [
            {
                "ts": current_ts.isoformat(),
                "value": current_price,
                "lower": current_price,
                "upper": current_price,
                "price": current_price,
                "type": "current",
            },
            {
                "ts": target_ts.isoformat(),
                "value": target_price,
                "lower": lower_band,
                "upper": upper_band,
                "price": target_price,
                "type": "target",
            },
        ]
    
    def process_universe(
        self,
        symbols: Optional[list] = None,
        force_refresh: bool = False,
    ) -> Dict:
        """
        Process entire symbol universe.
        
        Args:
            symbols: Optional list of symbols (if None, uses settings)
            force_refresh: Skip cache
        
        Returns:
            Aggregated results
        """
        # Get symbol universe if not provided
        if symbols is None:
            symbols = list(settings.symbols_to_process)
        
        logger.info(f"Processing {len(symbols)} symbols...")
        
        results = []
        for i, symbol in enumerate(symbols):
            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i + 1}/{len(symbols)}")
            result = self.process_symbol(symbol, force_refresh=force_refresh)
            results.append(result)
        
        # Aggregate results
        aggregated = {
            'total_symbols': len(symbols),
            'successful': sum(1 for r in results if r['success']),
            'failed': sum(1 for r in results if not r['success']),
            'total_processing_time': sum(r['processing_time'] for r in results),
            'avg_processing_time': np.mean([r['processing_time'] for r in results]) if results else 0,
            'feature_cache_hit_rate': self.metrics['feature_cache_hits'] / (
                self.metrics['feature_cache_hits'] + self.metrics['feature_cache_misses']
            ) if (self.metrics['feature_cache_hits'] + self.metrics['feature_cache_misses']) > 0 else 0,
        }
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing Complete:")
        logger.info(f"  Successful: {aggregated['successful']}/{aggregated['total_symbols']}")
        logger.info(f"  Failed: {aggregated['failed']}")
        logger.info(f"  Total time: {aggregated['total_processing_time']:.1f}s")
        logger.info(f"  Avg per symbol: {aggregated['avg_processing_time']:.2f}s")
        logger.info(f"  Feature cache hit rate: {aggregated['feature_cache_hit_rate']*100:.1f}%")
        logger.info(f"  Weight sources: {self.metrics['weight_sources']}")
        logger.info(f"{'='*60}\n")
        
        self.metrics['aggregated'] = aggregated
        self.save_metrics()
        
        return aggregated
    
    def save_metrics(self):
        """Save processing metrics to file."""
        self.metrics['end_time'] = datetime.now().isoformat()
        
        # Ensure metrics directory exists
        metrics_dir = Path(self.metrics_file).parent
        metrics_dir.mkdir(parents=True, exist_ok=True)
        
        with open(self.metrics_file, 'w') as f:
            json.dump(self.metrics, f, indent=2, default=str)
        logger.info(f"Metrics saved to {self.metrics_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Unified ML Forecast Job')
    parser.add_argument('--symbol', help='Process single symbol (for testing)')
    parser.add_argument('--symbols', help='Comma-separated list of symbols to process')
    parser.add_argument('--force-refresh', action='store_true', help='Rebuild features')
    parser.add_argument('--metrics-file', help='Output metrics file', 
                        default='metrics/unified/unified_forecast_metrics.json')
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
            socket_connect_timeout=2,
        )
        redis_cache.ping()
        logger.info(f"✓ Connected to Redis at {args.redis_host}:{args.redis_port}")
    except Exception as e:
        logger.warning(f"Could not connect to Redis: {e}")
        logger.info("Continuing without Redis cache...")
    
    # Create processor
    processor = UnifiedForecastProcessor(
        redis_cache=redis_cache,
        metrics_file=args.metrics_file,
    )
    
    logger.info("=" * 80)
    logger.info("Starting Unified ML Forecasting Job")
    logger.info("=" * 80)
    
    # Process
    if args.symbol:
        logger.info(f"Processing single symbol: {args.symbol}")
        result = processor.process_symbol(args.symbol, force_refresh=args.force_refresh)
        logger.info(f"\nResult: {json.dumps(result, indent=2, default=str)}")
    elif args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
        logger.info(f"Processing symbol list: {', '.join(symbols)}")
        results = processor.process_universe(
            symbols=symbols,
            force_refresh=args.force_refresh,
        )
        logger.info(f"\nAggregated: {json.dumps(results, indent=2, default=str)}")
    else:
        logger.info("Processing full universe")
        results = processor.process_universe(force_refresh=args.force_refresh)
        logger.info(f"\nAggregated: {json.dumps(results, indent=2, default=str)}")
    
    # Close database connections
    db.close()


if __name__ == '__main__':
    main()
