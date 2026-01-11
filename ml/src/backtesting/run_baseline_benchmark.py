"""
Baseline Benchmark Runner
=========================
Runs comprehensive baseline metrics before applying ML improvements.
Creates a snapshot of current model performance for comparison.

Usage:
    python -m src.backtesting.run_baseline_benchmark
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import settings  # noqa: E402
from src.backtesting.walk_forward_tester import WalkForwardBacktester  # noqa: E402
from src.data.data_validator import OHLCValidator  # noqa: E402
from src.models.baseline_forecaster import BaselineForecaster  # noqa: E402
from src.monitoring.confidence_calibrator import ConfidenceCalibrator  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def generate_synthetic_data(n_bars: int = 600, seed: int = 42) -> pd.DataFrame:
    """
    Generate synthetic OHLC data for benchmarking.

    Args:
        n_bars: Number of bars to generate
        seed: Random seed for reproducibility

    Returns:
        DataFrame with OHLC + volume data
    """
    np.random.seed(seed)

    # Start price and generate returns
    start_price = 100.0
    returns = np.random.normal(0.0005, 0.02, n_bars)

    # Add some trend and mean reversion
    trend = np.linspace(0, 0.001, n_bars)
    returns = returns + trend

    # Generate prices
    prices = start_price * np.cumprod(1 + returns)

    # Generate OHLC
    daily_volatility = 0.015
    opens = prices * (1 + np.random.normal(0, daily_volatility / 2, n_bars))
    highs = np.maximum(prices, opens) * (1 + np.abs(np.random.normal(0, daily_volatility, n_bars)))
    lows = np.minimum(prices, opens) * (1 - np.abs(np.random.normal(0, daily_volatility, n_bars)))
    closes = prices

    # Ensure OHLC constraints
    highs = np.maximum(highs, np.maximum(opens, closes))
    lows = np.minimum(lows, np.minimum(opens, closes))

    # Generate volume
    base_volume = 1_000_000
    volumes = base_volume * (1 + np.random.normal(0, 0.3, n_bars))
    volumes = np.maximum(volumes, 100_000)

    # Create timestamps
    start_date = datetime(2023, 1, 1)
    timestamps = pd.date_range(start=start_date, periods=n_bars, freq="B")

    df = pd.DataFrame(
        {
            "ts": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes.astype(int),
        }
    )

    return df


def run_data_validation_benchmark(df: pd.DataFrame) -> dict[str, Any]:
    """Run data validation and return quality metrics."""
    validator = OHLCValidator()
    cleaned_df, result = validator.validate(df, fix_issues=False)
    quality_score = validator.get_data_quality_score(df)

    return {
        "is_valid": result.is_valid,
        "issues": result.issues,
        "rows_flagged": result.rows_flagged,
        "quality_score": quality_score,
        "total_rows": len(df),
    }


def run_forecaster_benchmark(
    df: pd.DataFrame,
    horizons: list[str],
) -> dict[str, Any]:
    """Run forecaster benchmarks across multiple horizons."""
    results = {}

    for horizon in horizons:
        logger.info(f"Benchmarking horizon: {horizon}")

        try:
            forecaster = BaselineForecaster()
            backtester = WalkForwardBacktester(horizon=horizon)

            metrics = backtester.backtest(df, forecaster, horizons=[horizon])

            results[horizon] = {
                "accuracy": metrics.accuracy,
                "precision": metrics.precision,
                "recall": metrics.recall,
                "f1_score": metrics.f1_score,
                "sharpe_ratio": metrics.sharpe_ratio,
                "sortino_ratio": metrics.sortino_ratio,
                "max_drawdown": metrics.max_drawdown,
                "win_rate": metrics.win_rate,
                "profit_factor": metrics.profit_factor,
                "total_trades": metrics.total_trades,
                "test_periods": metrics.test_periods,
            }

            logger.info(
                f"  {horizon}: accuracy={metrics.accuracy:.2%}, sharpe={metrics.sharpe_ratio:.2f}"
            )

        except Exception as e:
            logger.error(f"  {horizon}: FAILED - {e}")
            results[horizon] = {"error": str(e)}

    return results


def run_calibration_benchmark(
    n_samples: int = 500,
) -> dict[str, Any]:
    """Run confidence calibration benchmark with synthetic data."""
    np.random.seed(42)

    # Generate synthetic forecast data with known miscalibration
    confidences = np.random.uniform(0.4, 0.95, n_samples)
    predicted_labels = np.random.choice(["bullish", "neutral", "bearish"], n_samples)

    # Simulate actual outcomes with calibration gap
    # Higher confidence = slightly better accuracy, but not as good as predicted
    actual_labels = []
    for i in range(n_samples):
        # True accuracy is 70% of predicted confidence
        true_accuracy = confidences[i] * 0.7
        if np.random.random() < true_accuracy:
            actual_labels.append(predicted_labels[i])
        else:
            other_labels = [
                level for level in ["bullish", "neutral", "bearish"] if level != predicted_labels[i]
            ]
            actual_labels.append(np.random.choice(other_labels))

    forecasts = pd.DataFrame(
        {
            "confidence": confidences,
            "predicted_label": predicted_labels,
            "actual_label": actual_labels,
        }
    )

    calibrator = ConfidenceCalibrator()
    calibration_results = calibrator.fit(forecasts, min_samples_per_bucket=20)

    bucket_stats = {}
    for result in calibration_results:
        bucket_stats[result.bucket] = {
            "predicted_confidence": result.predicted_confidence,
            "actual_accuracy": result.actual_accuracy,
            "n_samples": result.n_samples,
            "is_calibrated": result.is_calibrated,
            "adjustment_factor": result.adjustment_factor,
        }

    return {
        "total_samples": n_samples,
        "buckets": bucket_stats,
        "report": calibrator.get_calibration_report(),
    }


def save_benchmark_results(results: dict[str, Any], output_dir: Path) -> Path:
    """Save benchmark results to JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"baseline_benchmark_{timestamp}.json"

    # Convert any non-serializable types
    def convert(obj):
        if isinstance(obj, (np.floating, float)):
            return float(obj)
        if isinstance(obj, (np.integer, int)):
            return int(obj)
        if isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=convert)

    logger.info(f"Results saved to: {output_file}")
    return output_file


def main() -> None:
    """Run full baseline benchmark suite."""
    logger.info("=" * 60)
    logger.info("BASELINE BENCHMARK - ML Improvement Plan")
    logger.info("=" * 60)
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info(
        f"Settings: min_bars={settings.min_bars_for_training}, high_conf_bars={settings.min_bars_for_high_confidence}"
    )

    # Generate synthetic data for benchmarking
    logger.info("\n1. Generating synthetic data...")
    df = generate_synthetic_data(n_bars=600)
    logger.info(f"   Generated {len(df)} bars from {df['ts'].min()} to {df['ts'].max()}")

    results = {
        "timestamp": datetime.now().isoformat(),
        "settings": {
            "min_bars_for_training": settings.min_bars_for_training,
            "min_bars_for_high_confidence": settings.min_bars_for_high_confidence,
            "forecast_horizons": settings.forecast_horizons,
        },
        "data_info": {
            "n_bars": len(df),
            "start_date": df["ts"].min().isoformat(),
            "end_date": df["ts"].max().isoformat(),
        },
    }

    # Run data validation benchmark
    logger.info("\n2. Running data validation benchmark...")
    results["data_validation"] = run_data_validation_benchmark(df)
    logger.info(f"   Quality score: {results['data_validation']['quality_score']:.2%}")

    # Run forecaster benchmarks
    logger.info("\n3. Running forecaster benchmarks...")
    test_horizons = ["1D", "1W", "1M"]  # Subset for faster benchmark
    results["forecaster"] = run_forecaster_benchmark(df, test_horizons)

    # Run calibration benchmark
    logger.info("\n4. Running calibration benchmark...")
    results["calibration"] = run_calibration_benchmark()

    # Calculate summary metrics
    logger.info("\n5. Calculating summary metrics...")
    forecaster_results = results["forecaster"]
    valid_results = {k: v for k, v in forecaster_results.items() if "error" not in v}

    if valid_results:
        avg_accuracy = np.mean([v["accuracy"] for v in valid_results.values()])
        avg_sharpe = np.mean([v["sharpe_ratio"] for v in valid_results.values()])
        avg_f1 = np.mean([v["f1_score"] for v in valid_results.values()])

        results["summary"] = {
            "avg_accuracy": avg_accuracy,
            "avg_sharpe_ratio": avg_sharpe,
            "avg_f1_score": avg_f1,
            "horizons_tested": len(valid_results),
            "horizons_failed": len(forecaster_results) - len(valid_results),
        }

        logger.info(f"   Average Accuracy: {avg_accuracy:.2%}")
        logger.info(f"   Average Sharpe:   {avg_sharpe:.2f}")
        logger.info(f"   Average F1:       {avg_f1:.2f}")

    # Save results
    output_dir = Path(__file__).parent.parent.parent / "data" / "benchmarks"
    output_file = save_benchmark_results(results, output_dir)

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("BENCHMARK COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Results saved to: {output_file}")
    logger.info("\nUse this baseline to compare against after improvements.")


if __name__ == "__main__":
    main()
