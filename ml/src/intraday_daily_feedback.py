"""
Intraday-to-Daily Weight Feedback Loop
======================================

Orchestrates the complete feedback loop from STOCK_FORECASTING_FRAMEWORK.md:
1. Intraday forecasts (15m, 1h) generate rapid outcomes
2. Evaluation computes accuracy metrics
3. Calibration optimizes layer weights
4. Daily forecasts use calibrated weights

This module provides:
- Automatic weight recalibration when enough new evaluations exist
- Staleness detection for calibrated weights
- Fallback to default weights when calibration is insufficient
- Metrics tracking for feedback loop health

Usage:
    # Check if recalibration is needed
    feedback = IntradayDailyFeedback()
    if feedback.needs_recalibration("AAPL"):
        feedback.run_recalibration("AAPL")

    # Get best available weights
    weights = feedback.get_best_weights("AAPL", "1D")
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from config.settings import settings
from src.data.supabase_db import db
from src.forecast_weights import ForecastWeights, get_default_weights
from src.intraday_weight_calibrator import CalibrationResult, IntradayWeightCalibrator

logger = logging.getLogger(__name__)


@dataclass
class FeedbackLoopStatus:
    """Status of the intraday-daily feedback loop for a symbol."""

    symbol: str
    symbol_id: str
    last_calibration: Optional[datetime]
    calibration_age_hours: Optional[float]
    evaluation_count: int
    new_evaluations_since_calibration: int
    calibration_stale: bool
    has_valid_weights: bool
    weight_source: str
    current_weights: Dict[str, float]


class IntradayDailyFeedback:
    """
    Manages the feedback loop between intraday and daily forecasts.

    Key responsibilities:
    - Track calibration freshness
    - Determine when recalibration is needed
    - Provide best available weights for forecasting
    - Monitor feedback loop health
    """

    def __init__(
        self,
        calibration_staleness_hours: int = 24,
        min_new_evaluations: int = 20,
        min_calibration_samples: int = 50,
    ):
        """
        Initialize feedback loop manager.

        Args:
            calibration_staleness_hours: Hours before calibration is considered stale
            min_new_evaluations: Minimum new evaluations to trigger recalibration
            min_calibration_samples: Minimum samples required for calibration
        """
        self.calibration_staleness_hours = calibration_staleness_hours
        self.min_new_evaluations = min_new_evaluations
        self.min_calibration_samples = min_calibration_samples

        self.calibrator = IntradayWeightCalibrator(
            min_samples=min_calibration_samples,
        )

        # Track recalibration results
        self.recalibration_history: List[Dict[str, Any]] = []

    def get_feedback_status(self, symbol: str) -> Optional[FeedbackLoopStatus]:
        """
        Get current status of the feedback loop for a symbol.

        Args:
            symbol: Stock ticker

        Returns:
            FeedbackLoopStatus or None if symbol not found
        """
        symbol_id = db.get_symbol_id(symbol)
        if not symbol_id:
            return None

        # Get last calibration info
        calibration_info = self._get_calibration_info(symbol_id)
        last_calibration = calibration_info.get("updated_at")

        # Calculate staleness
        calibration_age_hours = None
        calibration_stale = True
        if last_calibration:
            age = datetime.now() - last_calibration
            calibration_age_hours = age.total_seconds() / 3600
            calibration_stale = calibration_age_hours > self.calibration_staleness_hours

        # Count evaluations
        eval_count = self._count_evaluations(symbol_id)
        new_evals = self._count_new_evaluations(symbol_id, last_calibration)

        # Get current weights
        weights, source = self._get_current_weights(symbol_id, "1D")

        return FeedbackLoopStatus(
            symbol=symbol,
            symbol_id=symbol_id,
            last_calibration=last_calibration,
            calibration_age_hours=calibration_age_hours,
            evaluation_count=eval_count,
            new_evaluations_since_calibration=new_evals,
            calibration_stale=calibration_stale,
            has_valid_weights=source != "default",
            weight_source=source,
            current_weights=weights,
        )

    def needs_recalibration(self, symbol: str) -> bool:
        """
        Check if a symbol needs weight recalibration.

        Triggers recalibration when:
        - Calibration is stale (> calibration_staleness_hours old)
        - Enough new evaluations have accumulated
        - No valid calibration exists

        Args:
            symbol: Stock ticker

        Returns:
            True if recalibration is needed
        """
        status = self.get_feedback_status(symbol)
        if status is None:
            return False

        # Need calibration if stale and have enough new data
        if status.calibration_stale and status.new_evaluations_since_calibration >= self.min_new_evaluations:
            logger.info(
                "%s needs recalibration: stale (%.1f hours) with %d new evaluations",
                symbol,
                status.calibration_age_hours or 0,
                status.new_evaluations_since_calibration,
            )
            return True

        # Need calibration if no valid weights exist
        if not status.has_valid_weights and status.evaluation_count >= self.min_calibration_samples:
            logger.info(
                "%s needs calibration: no valid weights, %d evaluations available",
                symbol,
                status.evaluation_count,
            )
            return True

        return False

    def run_recalibration(self, symbol: str) -> Optional[CalibrationResult]:
        """
        Run weight recalibration for a symbol.

        Args:
            symbol: Stock ticker

        Returns:
            CalibrationResult or None if calibration failed
        """
        logger.info("Running recalibration for %s", symbol)

        try:
            # Run calibration
            result = self.calibrator.calibrate_symbol(symbol)

            if result is None:
                logger.warning("Calibration failed for %s: insufficient data", symbol)
                return None

            # Save to database
            if self.calibrator.calibrate_and_save(symbol):
                logger.info(
                    "Recalibration complete for %s: ST=%.2f SR=%.2f ENS=%.2f (acc=%.1f%%)",
                    symbol,
                    result.supertrend_weight,
                    result.sr_weight,
                    result.ensemble_weight,
                    result.direction_accuracy * 100,
                )

                # Track history
                self.recalibration_history.append({
                    "symbol": symbol,
                    "timestamp": datetime.now(),
                    "result": result,
                })

                return result

            return None

        except Exception as e:
            logger.error("Recalibration error for %s: %s", symbol, e, exc_info=True)
            return None

    def get_best_weights(
        self,
        symbol: str,
        horizon: str,
    ) -> Tuple[ForecastWeights, str]:
        """
        Get the best available weights for forecasting.

        Priority:
        1. Fresh calibrated weights (< staleness threshold)
        2. Stale calibrated weights (with warning)
        3. Symbol-specific weights from database
        4. Default weights

        Args:
            symbol: Stock ticker
            horizon: Forecast horizon ("1D", "1W", etc.)

        Returns:
            Tuple of (ForecastWeights, source_description)
        """
        symbol_id = db.get_symbol_id(symbol)
        if not symbol_id:
            return get_default_weights(), "default (symbol not found)"

        weights, source = self._get_current_weights(symbol_id, horizon)

        # Convert to ForecastWeights object
        weight_obj = get_default_weights()
        weight_obj.layer_weights.update(weights)

        return weight_obj, source

    def _get_calibration_info(self, symbol_id: str) -> Dict[str, Any]:
        """Get calibration metadata for a symbol."""
        try:
            result = db.client.table("symbol_weight_overrides").select(
                "updated_at", "calibration_source", "calibration_accuracy", "calibration_samples"
            ).eq("symbol_id", symbol_id).eq("horizon", "1D").single().execute()

            if result.data:
                data = result.data
                updated_at = data.get("updated_at")
                if updated_at:
                    data["updated_at"] = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                return data
            return {}
        except Exception as e:
            logger.debug("Error fetching calibration info: %s", e)
            return {}

    def _count_evaluations(self, symbol_id: str) -> int:
        """Count total evaluation samples for a symbol."""
        try:
            result = db.client.table("ml_forecast_evaluations_intraday").select(
                "id", count="exact"
            ).eq("symbol_id", symbol_id).execute()
            return result.count or 0
        except Exception as e:
            logger.debug("Error counting evaluations: %s", e)
            return 0

    def _count_new_evaluations(
        self,
        symbol_id: str,
        since: Optional[datetime],
    ) -> int:
        """Count evaluations since last calibration."""
        if since is None:
            return self._count_evaluations(symbol_id)

        try:
            result = db.client.table("ml_forecast_evaluations_intraday").select(
                "id", count="exact"
            ).eq("symbol_id", symbol_id).gte(
                "evaluated_at", since.isoformat()
            ).execute()
            return result.count or 0
        except Exception as e:
            logger.debug("Error counting new evaluations: %s", e)
            return 0

    def _get_current_weights(
        self,
        symbol_id: str,
        horizon: str,
    ) -> Tuple[Dict[str, float], str]:
        """Get current weights and their source."""
        # Try calibrated weights first
        try:
            calibrated = db.get_calibrated_weights(
                symbol_id=symbol_id,
                horizon=horizon,
                min_samples=self.min_calibration_samples,
            )

            if calibrated and all(v is not None for v in calibrated.values()):
                # Check freshness
                calibration_info = self._get_calibration_info(symbol_id)
                updated_at = calibration_info.get("updated_at")

                if updated_at:
                    age_hours = (datetime.now() - updated_at).total_seconds() / 3600
                    if age_hours <= self.calibration_staleness_hours:
                        return calibrated, "intraday_calibrated (fresh)"
                    else:
                        return calibrated, f"intraday_calibrated (stale: {age_hours:.0f}h)"
                else:
                    return calibrated, "intraday_calibrated"
        except Exception as e:
            logger.debug("Error fetching calibrated weights: %s", e)

        # Try symbol-specific weights
        try:
            symbol_weights = db.get_symbol_weights(symbol_id, horizon)
            if symbol_weights:
                return symbol_weights, "symbol_specific"
        except Exception as e:
            logger.debug("Error fetching symbol weights: %s", e)

        # Fall back to defaults
        default = get_default_weights()
        return default.layer_weights, "default"


def run_feedback_loop(symbols: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Run the complete feedback loop for all symbols.

    Args:
        symbols: Optional list of symbols (defaults to all tracked symbols)

    Returns:
        Dict with results summary
    """
    if symbols is None:
        symbols = settings.intraday_symbols

    feedback = IntradayDailyFeedback()
    results = {
        "checked": 0,
        "recalibrated": 0,
        "skipped": 0,
        "failed": 0,
        "details": [],
    }

    for symbol in symbols:
        results["checked"] += 1

        status = feedback.get_feedback_status(symbol)
        if status is None:
            results["skipped"] += 1
            continue

        if feedback.needs_recalibration(symbol):
            result = feedback.run_recalibration(symbol)
            if result:
                results["recalibrated"] += 1
                results["details"].append({
                    "symbol": symbol,
                    "action": "recalibrated",
                    "accuracy": result.direction_accuracy,
                })
            else:
                results["failed"] += 1
                results["details"].append({
                    "symbol": symbol,
                    "action": "failed",
                })
        else:
            results["skipped"] += 1
            results["details"].append({
                "symbol": symbol,
                "action": "skipped",
                "reason": "not stale or insufficient new data",
            })

    logger.info(
        "Feedback loop complete: %d checked, %d recalibrated, %d skipped, %d failed",
        results["checked"],
        results["recalibrated"],
        results["skipped"],
        results["failed"],
    )

    return results


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(description="Run intraday-daily feedback loop")
    parser.add_argument(
        "--symbol",
        type=str,
        default=None,
        help="Single symbol to process",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force recalibration even if not needed",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show status without recalibrating",
    )
    args = parser.parse_args()

    feedback = IntradayDailyFeedback()

    if args.symbol:
        symbols = [args.symbol.upper()]
    else:
        symbols = settings.intraday_symbols

    for symbol in symbols:
        status = feedback.get_feedback_status(symbol)
        if status is None:
            print(f"{symbol}: Not found")
            continue

        print(f"\n{symbol}:")
        print(f"  Last calibration: {status.last_calibration}")
        print(f"  Calibration age: {status.calibration_age_hours:.1f}h" if status.calibration_age_hours else "  Calibration age: N/A")
        print(f"  Total evaluations: {status.evaluation_count}")
        print(f"  New evaluations: {status.new_evaluations_since_calibration}")
        print(f"  Stale: {status.calibration_stale}")
        print(f"  Weight source: {status.weight_source}")
        print(f"  Weights: {status.current_weights}")

        if not args.status:
            if args.force or feedback.needs_recalibration(symbol):
                print(f"  -> Running recalibration...")
                result = feedback.run_recalibration(symbol)
                if result:
                    print(f"  -> Success! Accuracy: {result.direction_accuracy:.1%}")
                else:
                    print(f"  -> Failed")
            else:
                print(f"  -> No recalibration needed")
