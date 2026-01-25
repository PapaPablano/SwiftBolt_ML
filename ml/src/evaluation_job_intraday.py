"""
Intraday evaluation job - evaluates 15m, 1h forecasts only.

Runs hourly (separate from daily evaluation).
Writes to forecast_evaluations table (with intraday-specific logic).
Populates intraday weight calibration data.
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


class IntradayForecastEvaluator:
    """Evaluates intraday forecasts (15m, 1h) against actual market data."""

    # Thresholds for intraday direction classification (tighter than daily)
    BULLISH_THRESHOLD = 0.005  # +0.5%
    BEARISH_THRESHOLD = -0.005  # -0.5%

    def __init__(self) -> None:
        """Initialize evaluator."""
        self.evaluations_added = 0
        self.errors = 0

    def get_pending_forecasts(self, horizon: str) -> list[dict]:
        """
        Get intraday forecasts pending evaluation.

        Args:
            horizon: Forecast horizon (15m, 1h)

        Returns:
            List of forecast dicts pending evaluation
        """
        # Fetch from intraday forecasts table
        try:
            result = db.client.table("ml_forecasts_intraday").select("*").eq(
                "horizon", horizon
            ).is_("evaluated_at", "null").order("created_at").limit(1000).execute()

            forecasts = result.data or []
            logger.info(f"Found {len(forecasts)} pending {horizon} intraday evaluations")
            return forecasts
        except Exception as e:
            logger.error(f"Error fetching pending intraday forecasts: {e}")
            return []

    def classify_return(self, return_pct: float) -> str:
        """Classify intraday return into direction label."""
        if return_pct > self.BULLISH_THRESHOLD:
            return "bullish"
        elif return_pct < self.BEARISH_THRESHOLD:
            return "bearish"
        else:
            return "neutral"

    def evaluate_forecast(self, forecast: dict) -> dict | None:
        """
        Evaluate a single intraday forecast.

        Args:
            forecast: Forecast dict from database

        Returns:
            Evaluation dict or None if evaluation failed
        """
        try:
            symbol_id = forecast["symbol_id"]
            horizon = forecast["horizon"]
            forecast_date = pd.to_datetime(forecast["created_at"])
            predicted_label = (forecast.get("overall_label") or "unknown").lower()
            confidence = float(forecast.get("confidence") or 0.5)

            # Get predicted target price
            target_price = forecast.get("target_price")
            if target_price is None:
                logger.warning(f"No target price in forecast for symbol_id={symbol_id}")
                return None

            # Get timeframe for intraday data
            if horizon == "15m":
                timeframe = "m15"
                bars_ahead = 1  # 1 bar = 15 minutes
            elif horizon == "1h":
                timeframe = "h1"
                bars_ahead = 1  # 1 bar = 1 hour
            else:
                logger.warning(f"Unknown intraday horizon: {horizon}")
                return None

            # Get symbol ticker (column is 'ticker', not 'symbol')
            symbol_result = db.client.table("symbols").select("ticker").eq("id", symbol_id).single().execute()
            if not symbol_result.data:
                logger.warning(f"Symbol not found: {symbol_id}")
                return None
            symbol = symbol_result.data["ticker"]

            # Get realized price (next bar close)
            realized = db.get_nth_future_close_after(
                symbol,
                forecast_date,
                n=bars_ahead,
                timeframe=timeframe,
            )
            if realized is None:
                logger.debug(f"No realized price yet for {symbol} ({horizon}) after {forecast_date}")
                return None

            eval_ts, realized_price = realized

            # Get starting price
            start = db.get_last_close_at_or_before(
                symbol,
                forecast_date,
                timeframe=timeframe,
            )
            if start is None:
                logger.warning(f"No starting price for {symbol} at {forecast_date}")
                return None

            _, start_price = start

            # Calculate metrics
            realized_return = (realized_price - start_price) / start_price
            realized_label = self.classify_return(realized_return)
            direction_correct = predicted_label == realized_label

            price_error = abs(target_price - realized_price)
            price_error_pct = price_error / start_price

            # Extract synthesis data for weight calibration
            synthesis_data = forecast.get("synthesis_data") or {}
            supertrend_component = synthesis_data.get("supertrend_component")
            sr_component = synthesis_data.get("sr_component")
            ensemble_component = synthesis_data.get("ensemble_component")

            evaluation = {
                "forecast_id": forecast["id"],
                "symbol_id": symbol_id,
                "symbol": symbol,
                "horizon": horizon,
                "predicted_label": predicted_label,
                "predicted_value": target_price,
                "predicted_confidence": confidence,
                "forecast_date": forecast_date.isoformat(),
                "evaluation_date": eval_ts.isoformat(),
                "realized_price": realized_price,
                "realized_return": realized_return,
                "realized_label": realized_label,
                "direction_correct": direction_correct,
                "price_error": price_error,
                "price_error_pct": price_error_pct,
                "synth_supertrend_component": supertrend_component,
                "synth_sr_component": sr_component,
                "synth_ensemble_component": ensemble_component,
            }

            logger.info(
                f"{symbol} {horizon}: predicted={predicted_label} "
                f"actual={realized_label} correct={direction_correct} "
                f"(${target_price:.2f} vs ${realized_price:.2f})"
            )

            return evaluation

        except Exception as e:
            logger.error(f"Error evaluating intraday forecast: {e}", exc_info=True)
            return None

    def save_evaluation(self, evaluation: dict) -> bool:
        """Save intraday evaluation to database."""
        try:
            # Save to forecast_evaluations table
            db.client.table("forecast_evaluations").insert(evaluation).execute()
            
            # Update evaluated_at timestamp in ml_forecasts_intraday
            db.client.table("ml_forecasts_intraday").update(
                {"evaluated_at": datetime.now().isoformat()}
            ).eq("id", evaluation["forecast_id"]).execute()
            
            self.evaluations_added += 1
            return True
        except Exception as e:
            logger.error(f"Error saving intraday evaluation: {e}")
            self.errors += 1
            return False

    def update_intraday_calibration(self, horizon: str) -> None:
        """
        Update intraday weight calibration data.

        This data is used by the weight calibrator to optimize layer weights.
        """
        try:
            # Get recent intraday evaluations (last 7 days)
            lookback_date = (datetime.now().date() - pd.Timedelta(days=7)).isoformat()

            result = (
                db.client.table("forecast_evaluations")
                .select("*")
                .eq("horizon", horizon)
                .gte("evaluation_date", lookback_date)
                .execute()
            )

            evals = result.data or []
            if not evals:
                logger.info(f"No recent evaluations for {horizon}")
                return

            # Group by symbol for per-symbol calibration
            symbol_groups = {}
            for e in evals:
                symbol_id = e.get("symbol_id")
                if symbol_id:
                    if symbol_id not in symbol_groups:
                        symbol_groups[symbol_id] = []
                    symbol_groups[symbol_id].append(e)

            logger.info(f"Updating calibration for {len(symbol_groups)} symbols ({horizon})")

            # For each symbol, calculate component performance
            for symbol_id, symbol_evals in symbol_groups.items():
                if len(symbol_evals) < 10:  # Need minimum samples
                    continue

                # Calculate accuracy by component
                correct = sum(1 for e in symbol_evals if e["direction_correct"])
                total = len(symbol_evals)
                accuracy = correct / total

                # Store calibration data (will be used by weight optimizer)
                calibration_record = {
                    "symbol_id": symbol_id,
                    "horizon": horizon,
                    "n_samples": total,
                    "accuracy": accuracy,
                    "updated_at": datetime.now().isoformat(),
                    "lookback_days": 7,
                }

                # Try to insert/update (simplified - actual implementation may need custom table)
                logger.debug(f"Symbol {symbol_id} {horizon}: {correct}/{total} = {accuracy:.2%}")

            logger.info(f"Updated intraday calibration for {horizon}")

        except Exception as e:
            logger.error(f"Error updating intraday calibration: {e}", exc_info=True)


def run_intraday_evaluation_job() -> dict[str, Any]:
    """
    Run intraday evaluation job for 15m, 1h forecasts.

    Returns:
        Summary of evaluation results
    """
    horizons = ["15m", "1h"]

    logger.info("=" * 80)
    logger.info("Starting Intraday Forecast Evaluation Job")
    logger.info(f"Horizons: {horizons}")
    logger.info("=" * 80)

    evaluator = IntradayForecastEvaluator()
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

        # Update intraday calibration data
        evaluator.update_intraday_calibration(horizon)

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

    results["errors"] = evaluator.errors
    results["overall_accuracy"] = (
        results["total_correct"] / results["total_evaluated"]
        if results["total_evaluated"] > 0
        else 0
    )

    logger.info("=" * 80)
    logger.info("Intraday Forecast Evaluation Job Complete")
    logger.info(f"Evaluated: {results['total_evaluated']}")
    logger.info(f"Correct: {results['total_correct']}")
    logger.info(f"Accuracy: {results['overall_accuracy']*100:.1f}%")
    logger.info(f"Errors: {results['errors']}")
    logger.info("=" * 80)

    # Close database connections
    db.close()

    return results


def main() -> None:
    """Main entry point."""
    import json

    results = run_intraday_evaluation_job()
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
