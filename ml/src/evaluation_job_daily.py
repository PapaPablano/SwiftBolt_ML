"""
Daily evaluation job - evaluates 1D, 1W, 1M forecasts only.

Runs AFTER daily forecasts complete.
Writes to forecast_evaluations table (with daily-specific logic).
Populates live_predictions (daily horizons).
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings  # noqa: E402
from src.data.supabase_db import db  # noqa: E402
from src.models.enhanced_ensemble_integration import (  # noqa: E402
    export_monitoring_metrics,
    record_forecast_outcome,
)

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _bool_env(name: str, default: bool = False) -> bool:
    """Get boolean from environment variable."""
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


class DailyForecastEvaluator:
    """Evaluates daily forecasts (1D, 1W, 1M) against actual market data."""

    # Thresholds for direction classification
    BULLISH_THRESHOLD = 0.02  # +2%
    BEARISH_THRESHOLD = -0.02  # -2%

    def __init__(self) -> None:
        """Initialize evaluator."""
        self.evaluations_added = 0
        self.errors = 0

    def get_pending_forecasts(self, horizon: str) -> list[dict]:
        """
        Get daily forecasts pending evaluation.

        Args:
            horizon: Forecast horizon (1D, 1W, 1M)

        Returns:
            List of forecast dicts pending evaluation
        """
        result = db.client.rpc(
            "get_pending_evaluations",
            {"p_horizon": horizon},
        ).execute()

        forecasts = result.data or []
        logger.info(f"Found {len(forecasts)} pending {horizon} evaluations")

        # De-duplicate overlapping forecasts
        deduped: dict[tuple[str, str, str], dict] = {}
        for f in forecasts:
            symbol = f.get("symbol")
            h = f.get("horizon")
            created_at = f.get("created_at")
            if not symbol or not h or not created_at:
                continue
            dt = pd.to_datetime(created_at)
            key = (symbol, h, dt.date().isoformat())
            prev = deduped.get(key)
            if prev is None:
                deduped[key] = f
                continue
            prev_dt = pd.to_datetime(prev.get("created_at"))
            if dt > prev_dt:
                deduped[key] = f

        deduped_list = list(deduped.values())
        logger.info(f"After de-duplication: {len(deduped_list)}/{len(forecasts)} pending {horizon} evaluations")
        return deduped_list

    def classify_return(self, return_pct: float) -> str:
        """Classify return into direction label."""
        if return_pct > self.BULLISH_THRESHOLD:
            return "bullish"
        elif return_pct < self.BEARISH_THRESHOLD:
            return "bearish"
        else:
            return "neutral"

    def evaluate_forecast(self, forecast: dict) -> dict | None:
        """
        Evaluate a single daily forecast.

        Args:
            forecast: Forecast dict from database

        Returns:
            Evaluation dict or None if evaluation failed
        """
        try:
            symbol = forecast["symbol"]
            horizon = forecast["horizon"]
            forecast_date = pd.to_datetime(forecast["created_at"])
            predicted_label = (forecast["overall_label"] or "unknown").lower()
            confidence = float(forecast["confidence"] or 0.5)

            # Get predicted target price from points
            points = forecast.get("points") or []
            if points:
                predicted_value = float(points[-1].get("value", 0))
            else:
                logger.warning(f"No points in forecast for {symbol}")
                return None

            # Resolve evaluation to next trading-day close
            if horizon == "1D":
                trading_steps = 1
            elif horizon == "1W":
                trading_steps = 5
            elif horizon == "1M":
                trading_steps = 20
            else:
                trading_steps = 1

            realized = db.get_nth_future_close_after(
                symbol,
                forecast_date,
                n=trading_steps,
                timeframe="d1",
            )
            if realized is None:
                logger.warning(f"No realized price for {symbol} ({horizon}) after {forecast_date}")
                return None

            eval_ts, realized_price = realized

            start = db.get_last_close_at_or_before(
                symbol,
                forecast_date,
                timeframe="d1",
            )
            if start is None:
                start_price = predicted_value / 1.02  # Rough estimate
            else:
                _, start_price = start

            # Calculate metrics
            realized_return = (realized_price - start_price) / start_price
            realized_label = self.classify_return(realized_return)
            direction_correct = predicted_label == realized_label

            price_error = abs(predicted_value - realized_price)
            price_error_pct = price_error / start_price

            # Extract model metadata
            rf_prediction = None
            gb_prediction = None
            rf_correct = None
            gb_correct = None
            rf_weight = None
            gb_weight = None
            synth_supertrend_component = None
            synth_polynomial_component = None
            synth_ml_component = None
            model_agreement = forecast.get("model_agreement")

            try:
                meta = (
                    db.client.table("ml_forecasts")
                    .select("training_stats,synthesis_data,model_agreement")
                    .eq("id", forecast["forecast_id"])
                    .single()
                    .execute()
                )
                if meta.data:
                    ts = meta.data.get("training_stats") or {}
                    if isinstance(ts, dict):
                        rf_prediction = ts.get("rf_prediction")
                        gb_prediction = ts.get("gb_prediction")
                        rf_weight = ts.get("rf_weight")
                        gb_weight = ts.get("gb_weight")

                    syn = meta.data.get("synthesis_data") or {}
                    if isinstance(syn, dict):
                        synth_supertrend_component = syn.get("supertrend_component")
                        synth_polynomial_component = syn.get("polynomial_component")
                        synth_ml_component = syn.get("ml_component")

                    if model_agreement is None:
                        model_agreement = meta.data.get("model_agreement")
            except Exception as e:
                logger.debug(f"Could not fetch forecast metadata: {e}")

            if rf_prediction is not None:
                rf_correct = str(rf_prediction).lower() == realized_label
            if gb_prediction is not None:
                gb_correct = str(gb_prediction).lower() == realized_label

            evaluation = {
                "forecast_id": forecast["forecast_id"],
                "symbol_id": forecast["symbol_id"],
                "symbol": symbol,
                "horizon": horizon,
                "predicted_label": predicted_label,
                "predicted_value": predicted_value,
                "predicted_confidence": confidence,
                "forecast_date": forecast_date.isoformat(),
                "evaluation_date": eval_ts.isoformat(),
                "realized_price": realized_price,
                "realized_return": realized_return,
                "realized_label": realized_label,
                "direction_correct": direction_correct,
                "price_error": price_error,
                "price_error_pct": price_error_pct,
                "rf_prediction": rf_prediction,
                "gb_prediction": gb_prediction,
                "rf_correct": rf_correct,
                "gb_correct": gb_correct,
                "model_agreement": model_agreement,
                "rf_weight": rf_weight,
                "gb_weight": gb_weight,
                "synth_supertrend_component": synth_supertrend_component,
                "synth_polynomial_component": synth_polynomial_component,
                "synth_ml_component": synth_ml_component,
            }

            logger.info(
                f"{symbol} {horizon}: predicted={predicted_label} "
                f"actual={realized_label} correct={direction_correct} "
                f"(${predicted_value:.2f} vs ${realized_price:.2f})"
            )

            return evaluation

        except Exception as e:
            logger.error(f"Error evaluating forecast: {e}", exc_info=True)
            return None

    def save_evaluation(self, evaluation: dict) -> bool:
        """Save evaluation to database."""
        try:
            db.client.table("forecast_evaluations").insert(evaluation).execute()
            self.evaluations_added += 1
            return True
        except Exception as e:
            logger.error(f"Error saving evaluation: {e}")
            self.errors += 1
            return False

    def update_performance_history(self, horizon: str) -> None:
        """Update daily performance history for a horizon."""
        try:
            today = datetime.now().date().isoformat()

            # Get today's evaluations for daily horizons
            result = (
                db.client.table("forecast_evaluations")
                .select("*")
                .eq("horizon", horizon)
                .gte("evaluation_date", today)
                .execute()
            )

            evals = result.data or []
            if not evals:
                logger.info(f"No evaluations today for {horizon}")
                return

            # Calculate metrics
            total = len(evals)
            correct = sum(1 for e in evals if e["direction_correct"])
            accuracy = correct / total if total > 0 else 0

            rf_correct = sum(1 for e in evals if e.get("rf_correct"))
            gb_correct = sum(1 for e in evals if e.get("gb_correct"))
            rf_total = sum(1 for e in evals if e.get("rf_correct") is not None)
            gb_total = sum(1 for e in evals if e.get("gb_correct") is not None)

            rf_accuracy = rf_correct / rf_total if rf_total > 0 else None
            gb_accuracy = gb_correct / gb_total if gb_total > 0 else None

            avg_error = sum(e["price_error_pct"] for e in evals) / total
            max_error = max(e["price_error_pct"] for e in evals)

            # By direction
            def _dir_acc(predicted: str) -> float | None:
                dir_evals = [e for e in evals if e["predicted_label"] == predicted]
                if not dir_evals:
                    return None
                correct = sum(1 for e in dir_evals if e["direction_correct"])
                return correct / len(dir_evals)

            bullish_acc = _dir_acc("bullish")
            bearish_acc = _dir_acc("bearish")
            neutral_acc = _dir_acc("neutral")

            # Get current weights
            weights_result = db.client.rpc("get_model_weights", {"p_horizon": horizon}).execute()
            default_weights = {"rf_weight": 0.5, "gb_weight": 0.5}
            weights = weights_result.data[0] if weights_result.data else default_weights

            # Insert/update performance history
            history_record = {
                "evaluation_date": today,
                "horizon": horizon,
                "total_forecasts": total,
                "correct_forecasts": correct,
                "accuracy": accuracy,
                "rf_accuracy": rf_accuracy,
                "gb_accuracy": gb_accuracy,
                "ensemble_accuracy": accuracy,
                "rf_weight": weights["rf_weight"],
                "gb_weight": weights["gb_weight"],
                "avg_price_error_pct": avg_error,
                "max_price_error_pct": max_error,
                "bullish_accuracy": bullish_acc,
                "bearish_accuracy": bearish_acc,
                "neutral_accuracy": neutral_acc,
            }

            db.client.table("model_performance_history").upsert(
                history_record, on_conflict="evaluation_date,horizon"
            ).execute()

            logger.info(
                f"Updated performance history for {horizon}: "
                f"{correct}/{total} correct ({accuracy*100:.1f}%)"
            )

        except Exception as e:
            logger.error(f"Error updating performance history: {e}", exc_info=True)


def run_daily_evaluation_job() -> dict[str, Any]:
    """
    Run daily evaluation job for 1D, 1W, 1M forecasts.

    Returns:
        Summary of evaluation results
    """
    horizons = ["1D", "1W", "1M"]

    logger.info("=" * 80)
    logger.info("Starting Daily Forecast Evaluation Job")
    logger.info(f"Horizons: {horizons}")
    logger.info("=" * 80)

    evaluator = DailyForecastEvaluator()
    results = {
        "horizons_processed": [],
        "total_evaluated": 0,
        "total_correct": 0,
        "errors": 0,
    }

    for horizon in horizons:
        logger.info(f"\n--- Evaluating {horizon} forecasts ---")

        pending = evaluator.get_pending_forecasts(horizon)

        horizon_correct = 0
        horizon_total = 0

        for forecast in pending:
            evaluation = evaluator.evaluate_forecast(forecast)
            if evaluation:
                if evaluator.save_evaluation(evaluation):
                    horizon_total += 1
                    if evaluation["direction_correct"]:
                        horizon_correct += 1

                    # Record to PerformanceMonitor if enhanced ensemble enabled
                    if _bool_env("ENABLE_ENHANCED_ENSEMBLE", default=False):
                        try:
                            ts = forecast.get("training_stats") or {}
                            record_forecast_outcome(
                                symbol=evaluation["symbol"],
                                horizon=evaluation["horizon"],
                                prediction=evaluation["predicted_label"],
                                actual=evaluation["realized_label"],
                                confidence=evaluation["predicted_confidence"],
                                agreement=evaluation.get("model_agreement") or 0.5,
                                probabilities=ts.get("probabilities", {}),
                                weights=ts.get("model_weights", {}),
                                model_predictions=ts.get("component_predictions", {}),
                            )
                        except Exception as e:
                            logger.debug(f"Performance monitor error: {e}")

        # Update performance history
        evaluator.update_performance_history(horizon)

        acc = horizon_correct / horizon_total if horizon_total > 0 else 0
        results["horizons_processed"].append(
            {
                "horizon": horizon,
                "evaluated": horizon_total,
                "correct": horizon_correct,
                "accuracy": acc,
            }
        )
        results["total_evaluated"] += horizon_total
        results["total_correct"] += horizon_correct

    # Trigger weight update
    logger.info("\n--- Updating Model Weights ---")
    try:
        weight_result = db.client.rpc("trigger_weight_update").execute()
        results["weight_update"] = weight_result.data
        logger.info(f"Weight update result: {weight_result.data}")
    except Exception as e:
        logger.error(f"Error triggering weight update: {e}")
        results["weight_update"] = {"error": str(e)}

    results["errors"] = evaluator.errors
    results["overall_accuracy"] = (
        results["total_correct"] / results["total_evaluated"]
        if results["total_evaluated"] > 0
        else 0
    )

    logger.info("=" * 80)
    logger.info("Daily Forecast Evaluation Job Complete")
    logger.info(f"Evaluated: {results['total_evaluated']}")
    logger.info(f"Correct: {results['total_correct']}")
    logger.info(f"Accuracy: {results['overall_accuracy']*100:.1f}%")
    logger.info(f"Errors: {results['errors']}")
    logger.info("=" * 80)

    # Export enhanced ensemble monitoring metrics
    if _bool_env("ENABLE_ENHANCED_ENSEMBLE", default=False):
        try:
            metrics = export_monitoring_metrics()
            results["enhanced_monitoring"] = {
                "n_predictions": metrics.get("n_predictions", 0),
                "rolling_accuracy": metrics.get("rolling_accuracy", 0),
                "calibration_error": metrics.get("calibration_error", 0),
                "alerts": metrics.get("recent_alerts", []),
            }
            logger.info(
                f"Enhanced monitoring: {metrics.get('n_predictions', 0)} predictions, "
                f"{metrics.get('rolling_accuracy', 0)*100:.1f}% accuracy"
            )
        except Exception as e:
            logger.warning(f"Failed to export monitoring metrics: {e}")

    # Close database connections
    db.close()

    return results


def main() -> None:
    """Main entry point."""
    import json

    results = run_daily_evaluation_job()
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
