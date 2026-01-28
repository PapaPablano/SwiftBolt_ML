#!/usr/bin/env python3
"""
Generate ensemble validation metrics for canary monitoring.

Runs walk-forward validation on AAPL, MSFT, SPY with 1D horizon
and records metrics to ensemble_validation_metrics table.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from src.data.supabase_db import db
from src.models.walk_forward_ensemble import WalkForwardEnsemble
from src.monitoring.divergence_monitor import DivergenceMonitor

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Canary configuration
CANARY_SYMBOLS = ["AAPL", "MSFT", "SPY"]
HORIZON = "1D"
TRAIN_DAYS = 250
VAL_DAYS = 50
TEST_DAYS = 50


def run_canary_validation():
    """Run walk-forward validation for canary symbols and record metrics."""

    logger.info("="*70)
    logger.info("CANARY METRICS GENERATION")
    logger.info("="*70)
    logger.info(f"Symbols: {CANARY_SYMBOLS}")
    logger.info(f"Horizon: {HORIZON}")
    logger.info(f"Train/Val/Test: {TRAIN_DAYS}/{VAL_DAYS}/{TEST_DAYS} days")

    divergence_monitor = DivergenceMonitor(db_client=db.client)
    total_metrics = 0

    for symbol in CANARY_SYMBOLS:
        logger.info("")
        logger.info(f"Processing {symbol}...")

        try:
            # Get symbol ID
            symbols_result = db.client.table("symbols").select("id").eq("ticker", symbol).execute()
            if not symbols_result.data:
                logger.warning(f"Symbol {symbol} not found")
                continue

            symbol_id = symbols_result.data[0]["id"]

            # Run walk-forward ensemble validation
            wf_ensemble = WalkForwardEnsemble(
                symbol_id=symbol_id,
                symbol=symbol,
                horizon=HORIZON,
                train_days=TRAIN_DAYS,
                val_days=VAL_DAYS,
                test_days=TEST_DAYS,
            )

            # Run validation and get results
            result = wf_ensemble.run_walk_forward_validation()

            if result:
                # Log metrics for each window
                for window_idx, window_result in enumerate(result.get("windows", []), 1):
                    divergence_monitor.log_window_result(
                        symbol=symbol,
                        symbol_id=symbol_id,
                        horizon=HORIZON,
                        window_id=window_idx,
                        val_rmse=window_result.get("val_rmse", 0),
                        test_rmse=window_result.get("test_rmse", 0),
                        train_rmse=window_result.get("train_rmse"),
                        val_mae=window_result.get("val_mae"),
                        test_mae=window_result.get("test_mae"),
                        n_train_samples=window_result.get("n_train_samples"),
                        n_val_samples=window_result.get("n_val_samples"),
                        n_test_samples=window_result.get("n_test_samples"),
                        data_span_days=window_result.get("data_span_days"),
                        model_count=window_result.get("model_count", 2),
                        models_used=window_result.get("models_used", ["LSTM", "ARIMA_GARCH"]),
                        directional_accuracy=window_result.get("directional_accuracy"),
                    )
                    total_metrics += 1

            logger.info(f"✓ Generated {len(result.get('windows', []))} metric(s) for {symbol}")

        except Exception as e:
            logger.error(f"✗ Failed to process {symbol}: {e}", exc_info=True)

    logger.info("")
    logger.info("="*70)
    logger.info(f"COMPLETE: Generated {total_metrics} validation metrics")
    logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
    logger.info("="*70)
    return total_metrics > 0


if __name__ == "__main__":
    success = run_canary_validation()
    sys.exit(0 if success else 1)
