"""Intraday forecast evaluation job.

Evaluates expired intraday forecasts against actual prices to enable
rapid feedback for weight calibration.
"""

import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings  # noqa: E402
from src.data.supabase_db import db  # noqa: E402
from src.forecast_validator import evaluate_single_forecast  # noqa: E402

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Direction thresholds for classifying returns
BULLISH_THRESHOLD = 0.002  # +0.2% = bullish
BEARISH_THRESHOLD = -0.002  # -0.2% = bearish

# Intraday horizons map to Option B tolerance (all <3 days = 1%)
INTRADAY_HORIZON_DAYS = {
    "15m": 1,  # Treat as 1-day horizon for tolerance calc
    "1h": 1,  # Treat as 1-day horizon for tolerance calc
}


def classify_return(pct_return: float) -> str:
    """Classify a return percentage into direction label."""
    if pct_return > BULLISH_THRESHOLD:
        return "bullish"
    elif pct_return < BEARISH_THRESHOLD:
        return "bearish"
    return "neutral"


def evaluate_forecast(forecast: dict) -> dict | None:
    """
    Evaluate a single intraday forecast.

    Args:
        forecast: Dict with forecast data from get_pending_intraday_evaluations

    Returns:
        Evaluation result dict or None if evaluation failed
    """
    symbol = forecast["symbol"]
    symbol_id = forecast["symbol_id"]
    horizon = forecast["horizon"]
    forecast_id = forecast["forecast_id"]
    created_at = forecast["created_at"]

    # Determine timeframe from horizon
    timeframe = "m15" if horizon == "15m" else "h1"

    try:
        # Get the realized price at expiry time
        # Fetch the bar that covers the expiry time
        result = db.get_last_close_at_or_before(
            symbol=symbol,
            target_ts=forecast["expires_at"],
            timeframe=timeframe,
        )

        if result is None:
            logger.warning(
                "No price data found for %s at %s",
                symbol,
                forecast["expires_at"],
            )
            return None

        _, realized_price = result

        # Get predicted values
        predicted_price = float(forecast["target_price"])
        current_price = float(forecast["current_price"])
        predicted_label = forecast["overall_label"]

        # Calculate realized return and label
        realized_return = (realized_price - current_price) / current_price
        realized_label = classify_return(realized_return)

        # Calculate price error
        price_error = abs(realized_price - predicted_price)
        price_error_pct = price_error / current_price

        # Direction correct?
        direction_correct = predicted_label == realized_label

        # Component accuracy
        supertrend_direction = forecast.get("supertrend_direction", "NEUTRAL")
        supertrend_label = (
            "bullish"
            if supertrend_direction == "BULLISH"
            else ("bearish" if supertrend_direction == "BEARISH" else "neutral")
        )
        supertrend_direction_correct = supertrend_label == realized_label

        ensemble_label = forecast.get("ensemble_label", "neutral")
        ensemble_direction_correct = ensemble_label.lower() == realized_label

        # S/R containment - check if price stayed within component range
        sr_component = float(forecast.get("sr_component", current_price))
        st_component = float(forecast.get("supertrend_component", current_price))

        # Price is "contained" if it stayed between the two component targets
        lower_bound = min(sr_component, st_component, current_price) * 0.98
        upper_bound = max(sr_component, st_component, current_price) * 1.02
        sr_containment = lower_bound <= realized_price <= upper_bound

        # Option B Framework evaluation
        # Get bands from forecast (use sr_component range as proxy)
        forecast_low = float(forecast.get("lower_band", lower_bound))
        forecast_high = float(forecast.get("upper_band", upper_bound))
        horizon_days = INTRADAY_HORIZON_DAYS.get(horizon, 1)

        option_b_eval = evaluate_single_forecast(
            forecast_low=forecast_low,
            forecast_mid=predicted_price,
            forecast_high=forecast_high,
            horizon_days=horizon_days,
            actual_close=realized_price,
            prior_close=current_price,
        )

        return {
            "forecast_id": forecast_id,
            "symbol_id": symbol_id,
            "symbol": symbol,
            "horizon": horizon,
            "predicted_label": predicted_label,
            "predicted_price": predicted_price,
            "predicted_confidence": float(forecast.get("confidence", 0.5)),
            "realized_price": realized_price,
            "realized_return": realized_return,
            "realized_label": realized_label,
            "direction_correct": direction_correct,
            "price_error": price_error,
            "price_error_pct": price_error_pct,
            "supertrend_direction_correct": supertrend_direction_correct,
            "sr_containment": sr_containment,
            "ensemble_direction_correct": ensemble_direction_correct,
            "forecast_created_at": created_at,
            # Option B Framework fields
            "option_b_outcome": option_b_eval.outcome.value,
            "option_b_direction_correct": option_b_eval.direction_correct,
            "option_b_within_tolerance": option_b_eval.within_tolerance,
            "option_b_mape": option_b_eval.mape,
            "option_b_bias": option_b_eval.bias,
        }

    except Exception as e:
        logger.error(
            "Error evaluating forecast %s for %s: %s",
            forecast_id,
            symbol,
            e,
        )
        return None


def evaluate_pending_forecasts(horizon: str | None = None) -> tuple[int, int]:
    """
    Evaluate all pending intraday forecasts.

    Args:
        horizon: Optional filter for '15m' or '1h'

    Returns:
        Tuple of (success_count, fail_count)
    """
    # Get pending forecasts
    pending = db.get_pending_intraday_evaluations(horizon=horizon)

    if not pending:
        logger.info("No pending intraday evaluations")
        return 0, 0

    logger.info("Found %d pending intraday forecasts to evaluate", len(pending))

    success_count = 0
    fail_count = 0

    for forecast in pending:
        eval_result = evaluate_forecast(forecast)

        if eval_result is None:
            fail_count += 1
            continue

        # Save evaluation
        saved = db.save_intraday_evaluation(
            forecast_id=eval_result["forecast_id"],
            symbol_id=eval_result["symbol_id"],
            symbol=eval_result["symbol"],
            horizon=eval_result["horizon"],
            predicted_label=eval_result["predicted_label"],
            predicted_price=eval_result["predicted_price"],
            predicted_confidence=eval_result["predicted_confidence"],
            realized_price=eval_result["realized_price"],
            realized_return=eval_result["realized_return"],
            realized_label=eval_result["realized_label"],
            direction_correct=eval_result["direction_correct"],
            price_error=eval_result["price_error"],
            price_error_pct=eval_result["price_error_pct"],
            supertrend_direction_correct=eval_result["supertrend_direction_correct"],
            sr_containment=eval_result["sr_containment"],
            ensemble_direction_correct=eval_result["ensemble_direction_correct"],
            forecast_created_at=eval_result["forecast_created_at"],
            # Option B Framework fields
            option_b_outcome=eval_result.get("option_b_outcome"),
            option_b_direction_correct=eval_result.get("option_b_direction_correct"),
            option_b_within_tolerance=eval_result.get("option_b_within_tolerance"),
            option_b_mape=eval_result.get("option_b_mape"),
            option_b_bias=eval_result.get("option_b_bias"),
        )

        if saved:
            success_count += 1
            # Show Option B outcome in log
            outcome = eval_result.get("option_b_outcome", "N/A")
            status = (
                "✓"
                if outcome == "FULL_HIT"
                else ("◐" if outcome in ("DIRECTIONAL_HIT", "DIRECTIONAL_ONLY") else "✗")
            )
            logger.info(
                "%s %s %s: %s pred=%s actual=%s MAPE=%.2f%%",
                status,
                eval_result["symbol"],
                eval_result["horizon"],
                outcome,
                eval_result["predicted_label"],
                eval_result["realized_label"],
                eval_result.get("option_b_mape", 0),
            )
        else:
            fail_count += 1

    return success_count, fail_count


def print_summary_stats(horizon: str | None = None) -> None:
    """Print summary statistics for recent intraday evaluations."""
    # Get symbols to check
    symbols = settings.intraday_symbols

    logger.info("\n" + "=" * 60)
    logger.info("Intraday Calibration Summary (Last 72 Hours)")
    logger.info("=" * 60)

    for symbol in symbols:
        try:
            symbol_id = db.get_symbol_id(symbol)
            if not symbol_id:
                continue

            stats = db.get_intraday_calibration_stats(
                symbol_id=symbol_id,
                lookback_hours=72,
            )

            if not stats:
                logger.info("%s: No evaluation data yet", symbol)
                continue

            for hz, data in stats.items():
                if horizon and hz != horizon:
                    continue

                logger.info(
                    "%s %s: n=%d dir_acc=%.1f%% ST_acc=%.1f%% SR_cont=%.1f%% ML_acc=%.1f%%",
                    symbol,
                    hz,
                    data.get("total_forecasts", 0),
                    (data.get("direction_accuracy") or 0) * 100,
                    (data.get("supertrend_accuracy") or 0) * 100,
                    (data.get("sr_containment_rate") or 0) * 100,
                    (data.get("ensemble_accuracy") or 0) * 100,
                )

        except Exception as e:
            logger.warning("Could not get stats for %s: %s", symbol, e)

    logger.info("=" * 60 + "\n")


def main() -> None:
    """Main entry point for intraday evaluation job."""
    parser = argparse.ArgumentParser(description="Evaluate intraday forecasts")
    parser.add_argument(
        "--horizon",
        type=str,
        choices=["15m", "1h"],
        default=None,
        help="Horizon to evaluate (default: all)",
    )
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Only print stats, don't evaluate",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Starting Intraday Evaluation Job")
    if args.horizon:
        logger.info("Horizon: %s", args.horizon)
    logger.info("=" * 60)

    if args.stats_only:
        print_summary_stats(args.horizon)
        return

    # Evaluate pending forecasts
    success, failed = evaluate_pending_forecasts(args.horizon)

    logger.info("=" * 60)
    logger.info("Intraday Evaluation Job Complete")
    logger.info("Evaluated: %d success, %d failed", success, failed)
    logger.info("=" * 60)

    # Print summary stats
    if success > 0:
        print_summary_stats(args.horizon)


if __name__ == "__main__":
    main()
