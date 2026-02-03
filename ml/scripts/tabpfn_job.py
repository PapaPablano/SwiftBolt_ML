#!/usr/bin/env python3
"""
Entry point for TabPFN walk-forward validation in Docker.

Usage:
    docker-compose -f docker/docker-compose.tabpfn.yml run tabpfn-walk-forward

Environment variables:
    SYMBOL: Stock symbol (default: TSLA)
    INITIAL_TRAIN_DAYS: Initial training window (default: 300)
    TEST_DAYS: Test window size (default: 50)
    STEP_DAYS: Step size between windows (default: 50)
    USE_TABPFN: Use TabPFN vs Baseline (default: true)
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Add /app to path when running in Docker
sys.path.insert(0, "/app")

# Ensure logs dir exists before configuring file handler
LOG_DIR = Path("/app/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"tabpfn_job_{datetime.now():%Y%m%d_%H%M%S}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE),
    ],
)
logger = logging.getLogger(__name__)


def check_gpu() -> bool:
    """Check GPU availability."""
    try:
        import torch

        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            logger.info("GPU detected: %s", gpu_name)
            logger.info("CUDA version: %s", torch.version.cuda)
            logger.info("Available GPUs: %s", torch.cuda.device_count())
            return True
        logger.warning("No GPU detected, using CPU (will be slow)")
        return False
    except ImportError:
        logger.error("PyTorch not installed")
        return False


def main() -> None:
    """Run TabPFN walk-forward validation."""
    from src.evaluation.walk_forward import walk_forward_validate

    has_gpu = check_gpu()

    symbol = os.getenv("SYMBOL", "TSLA")
    initial_train_days = int(os.getenv("INITIAL_TRAIN_DAYS", "300"))
    test_days = int(os.getenv("TEST_DAYS", "50"))
    step_days = int(os.getenv("STEP_DAYS", "50"))
    use_tabpfn = os.getenv("USE_TABPFN", "true").lower() == "true"

    logger.info("=" * 60)
    logger.info("TABPFN WALK-FORWARD VALIDATION (Docker)")
    logger.info("=" * 60)
    logger.info("Symbol: %s", symbol)
    logger.info("Initial train days: %s", initial_train_days)
    logger.info("Test days: %s", test_days)
    logger.info("Step days: %s", step_days)
    logger.info("Use TabPFN: %s", use_tabpfn)
    logger.info("GPU available: %s", has_gpu)
    logger.info("=" * 60)

    try:
        result = walk_forward_validate(
            symbol=symbol,
            timeframe="d1",
            horizon_days=1,
            initial_train_days=initial_train_days,
            test_days=test_days,
            step_days=step_days,
            use_tabpfn=use_tabpfn,
        )

        logger.info("=" * 60)
        logger.info("RESULTS")
        logger.info("=" * 60)
        logger.info("Mean accuracy: %.1f%%", result["mean_accuracy"] * 100)
        logger.info("Std deviation: %.1f%%", result["std_accuracy"] * 100)
        logger.info("Overall accuracy: %.1f%%", result["overall_accuracy"] * 100)
        logger.info("Windows tested: %s", result["n_windows"])
        logger.info("Per-window accuracies:")
        for i, acc in enumerate(result["window_accuracies"], 1):
            logger.info("  Window %s: %.1f%%", i, acc * 100)
        logger.info("=" * 60)

        results_dir = Path("/app/results")
        results_dir.mkdir(parents=True, exist_ok=True)

        csv_path = results_dir / f"{symbol}_walk_forward_predictions.csv"
        result["predictions_df"].to_csv(csv_path, index=False)
        logger.info("Predictions saved: %s", csv_path)

        plot_path = results_dir / f"{symbol}_walk_forward_plot.png"
        try:
            from analyze_walk_forward import plot_walk_forward_results

            plot_walk_forward_results(result, out_path=plot_path)
            logger.info("Plot saved: %s", plot_path)
        except Exception as e:
            logger.warning("Could not generate plot: %s", e)

        if result["mean_accuracy"] > 0.40:
            logger.info(
                "SUCCESS: Mean accuracy %.1f%% > 40%%",
                result["mean_accuracy"] * 100,
            )
            sys.exit(0)
        logger.warning(
            "BELOW TARGET: Mean accuracy %.1f%% < 40%%",
            result["mean_accuracy"] * 100,
        )
        sys.exit(1)

    except Exception as e:
        logger.exception("ERROR: %s", e)
        sys.exit(2)


if __name__ == "__main__":
    main()
