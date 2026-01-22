#!/usr/bin/env python
"""Test script for training pipeline.

Quick verification that training modules work correctly.
"""

import logging
import sys
from pathlib import Path

from src.data.supabase_db import SupabaseDatabase
from src.training.ensemble_training_job import train_ensemble_for_symbol_timeframe
from src.models.ensemble_loader import EnsembleLoader, EnsemblePredictor

logger = logging.getLogger(__name__)


def test_data_collection():
    """Test Step 1: Data collection."""
    logger.info("Testing data collection...")
    
    from src.training.data_preparation import collect_training_data
    
    db = SupabaseDatabase()
    data = collect_training_data(
        db=db,
        symbols=["AAPL"],
        timeframes={"d1": 250},
        lookback_days=90,
    )
    
    assert "d1" in data, "Missing d1 timeframe"
    assert "AAPL" in data["d1"], "Missing AAPL symbol"
    assert len(data["d1"]["AAPL"]) > 100, "Insufficient data rows"
    
    logger.info(f"✅ Data collection OK: {len(data['d1']['AAPL'])} bars")
    return data


def test_label_creation(data):
    """Test Step 2: Label creation."""
    logger.info("Testing label creation...")
    
    from src.training.data_preparation import create_labels
    
    df = data["d1"]["AAPL"]
    features, labels = create_labels(df, prediction_horizon_bars=5, threshold=0.01)
    
    assert len(features) == len(labels), "Feature/label length mismatch"
    assert len(features) < len(df), "Labels should trim last N rows"
    assert set(labels.unique()).issubset({"BULLISH", "NEUTRAL", "BEARISH"}), "Invalid labels"
    
    logger.info(f"✅ Label creation OK: {len(labels)} labels")
    logger.info(f"   Distribution: {labels.value_counts().to_dict()}")
    return features, labels


def test_feature_selection(features):
    """Test Step 3: Feature selection."""
    logger.info("Testing feature selection...")
    
    from src.training.data_preparation import select_features_for_training
    
    selected = select_features_for_training(features)
    
    assert len(selected.columns) > 0, "No features selected"
    assert "close" not in selected.columns, "Raw OHLC should be excluded"
    assert "ts" not in selected.columns, "Timestamp should be excluded"
    
    logger.info(f"✅ Feature selection OK: {len(selected.columns)} features")
    return selected


def test_train_validation_split(features, labels):
    """Test Step 4: Train/validation split."""
    logger.info("Testing train/validation split...")
    
    from src.training.data_preparation import prepare_train_validation_split
    
    train_f, valid_f, train_l, valid_l = prepare_train_validation_split(
        features, labels, train_fraction=0.7
    )
    
    assert len(train_f) + len(valid_f) == len(features), "Split size mismatch"
    assert len(train_f) > len(valid_f), "Train set should be larger"
    assert train_f.columns.equals(valid_f.columns), "Feature column mismatch"
    
    logger.info(f"✅ Split OK: {len(train_f)} train, {len(valid_f)} valid")
    return train_f, valid_f, train_l, valid_l


def test_model_training(train_f, train_l, valid_f, valid_l):
    """Test Step 5: Model training."""
    logger.info("Testing model training...")
    
    from src.training.model_training import ModelTrainer
    
    trainer = ModelTrainer("AAPL", "d1")
    perfs = trainer.train_all_models(train_f, train_l, valid_f, valid_l)
    
    assert "rf" in perfs, "Missing RF model"
    assert "gb" in perfs, "Missing GB model"
    assert "rf" in trainer.models, "RF model not stored"
    assert "gb" in trainer.models, "GB model not stored"
    
    logger.info("✅ Model training OK")
    logger.info(f"   RF valid acc: {perfs['rf']['valid_accuracy']:.1%}")
    logger.info(f"   GB valid acc: {perfs['gb']['valid_accuracy']:.1%}")
    return trainer


def test_weight_optimization(trainer, valid_f, valid_l):
    """Test Step 6: Weight optimization."""
    logger.info("Testing weight optimization...")
    
    from src.training.weight_optimizer import EnsembleWeightOptimizer
    
    model_predictions = trainer.get_model_predictions(valid_f)
    
    optimizer = EnsembleWeightOptimizer(alpha=1.0)
    weights = optimizer.optimize_weights(model_predictions, valid_l)
    
    assert "rf" in weights, "Missing RF weight"
    assert "gb" in weights, "Missing GB weight"
    assert abs(sum(weights.values()) - 1.0) < 0.01, "Weights don't sum to 1"
    assert all(w >= 0 for w in weights.values()), "Negative weights found"
    
    logger.info("✅ Weight optimization OK")
    logger.info(f"   Weights: {weights}")
    return weights


def test_full_training_pipeline():
    """Test complete training pipeline."""
    logger.info("\n" + "=" * 80)
    logger.info("Testing full training pipeline for AAPL/d1")
    logger.info("=" * 80 + "\n")
    
    db = SupabaseDatabase()
    result = train_ensemble_for_symbol_timeframe(
        db=db,
        symbol="AAPL",
        timeframe="d1",
        lookback_days=90,
    )
    
    assert result.get("success", False), f"Training failed: {result.get('error')}"
    assert "validation_accuracy" in result, "Missing validation accuracy"
    assert "weights" in result, "Missing weights"
    assert "models_path" in result, "Missing models path"
    
    models_file = Path(result["models_path"])
    assert models_file.exists(), f"Model file not created: {models_file}"
    
    logger.info("\n✅ Full training pipeline OK")
    logger.info(f"   Accuracy: {result['validation_accuracy']:.1%}")
    logger.info(f"   Weights: {result['weights']}")
    logger.info(f"   Saved to: {models_file}")
    return result


def test_model_loading(symbol="AAPL", timeframe="d1"):
    """Test model loading and prediction."""
    logger.info("\n" + "=" * 80)
    logger.info(f"Testing model loading for {symbol}/{timeframe}")
    logger.info("=" * 80 + "\n")
    
    # Test loader
    artifact = EnsembleLoader.load_latest_model(symbol, timeframe)
    assert artifact is not None, "Failed to load model"
    assert "models" in artifact, "Missing models in artifact"
    assert "weights" in artifact, "Missing weights in artifact"
    
    logger.info("✅ Model loading OK")
    logger.info(f"   Timestamp: {artifact['timestamp']}")
    logger.info(f"   Accuracy: {artifact['ensemble_accuracy']:.1%}")
    
    # Test predictor
    predictor = EnsemblePredictor(symbol, timeframe)
    assert predictor.is_trained, "Predictor not trained"
    
    logger.info("✅ Predictor initialization OK")
    
    # Test prediction (need fresh data)
    db = SupabaseDatabase()
    df = db.fetch_ohlc_bars(symbol, timeframe=timeframe, limit=500)
    
    if not df.empty:
        from src.features.technical_indicators import add_technical_features
        df_with_features = add_technical_features(df)
        
        result = predictor.predict(df_with_features)
        
        if result:
            logger.info("✅ Prediction OK")
            logger.info(f"   Forecast: {result['forecast']}")
            logger.info(f"   Confidence: {result['confidence']:.1%}")
            logger.info(f"   Weights used: {result['weights_used']}")
        else:
            logger.warning("⚠️ Prediction returned None")
    else:
        logger.warning("⚠️ No data available for prediction test")


def main():
    """Run all tests."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    try:
        # Unit tests
        logger.info("\n" + "#" * 80)
        logger.info("# Running Unit Tests")
        logger.info("#" * 80 + "\n")
        
        data = test_data_collection()
        features, labels = test_label_creation(data)
        selected_features = test_feature_selection(features)
        train_f, valid_f, train_l, valid_l = test_train_validation_split(
            selected_features, labels
        )
        trainer = test_model_training(train_f, train_l, valid_f, valid_l)
        weights = test_weight_optimization(trainer, valid_f, valid_l)
        
        # Integration test
        logger.info("\n" + "#" * 80)
        logger.info("# Running Integration Test")
        logger.info("#" * 80 + "\n")
        
        result = test_full_training_pipeline()
        test_model_loading("AAPL", "d1")
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("✅ ALL TESTS PASSED")
        logger.info("=" * 80)
        logger.info("\nTraining pipeline is ready for production use.")
        logger.info("\nNext steps:")
        logger.info("  1. Run full training: python ml/src/training/ensemble_training_job.py")
        logger.info("  2. Verify artifacts: ls trained_models/")
        logger.info("  3. Run forecast job: python ml/src/multi_horizon_forecast_job.py")
        
        return 0
        
    except Exception as e:
        logger.error(f"\n❌ TEST FAILED: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
