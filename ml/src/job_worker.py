"""
Job Worker - Processes pending jobs from the job_queue table.

This worker polls the job_queue for pending forecast jobs and processes them.
It can be run as a cron job or continuously in the background.

Usage:
    python -m src.job_worker              # Process all pending jobs once
    python -m src.job_worker --continuous # Run continuously (poll every 30s)
    python -m src.job_worker --job-type forecast  # Only process forecast jobs
"""

import argparse
import logging
import time
from typing import Optional

from config.settings import settings
from src.data.supabase_db import SupabaseDatabase
from src.features.technical_indicators import add_technical_features
from src.models.baseline_forecaster import BaselineForecaster
from src.strategies.supertrend_ai import SuperTrendAI

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def process_forecast_job(
    db: SupabaseDatabase, symbol: str, payload: dict
) -> tuple[bool, Optional[str]]:
    """Process a forecast job for a symbol."""
    try:
        logger.info(f"Processing forecast job for {symbol}")

        # Fetch OHLC data (252 bars = 1 year for S/R detection, newest first)
        df = db.fetch_ohlc_bars(symbol, timeframe="d1", limit=252)

        if len(df) < settings.min_bars_for_training:
            msg = (
                f"Insufficient data for {symbol}: {len(df)} bars "
                f"(need {settings.min_bars_for_training})"
            )
            logger.warning(msg)
            return False, msg

        # Add technical features (includes S/R features)
        df = add_technical_features(df)

        # Get symbol_id for database operations
        symbol_id = db.get_symbol_id(symbol)

        # Run SuperTrend AI analysis
        supertrend_data = None
        try:
            supertrend = SuperTrendAI(df)
            st_df, st_info = supertrend.calculate()

            supertrend_data = {
                "supertrend_factor": st_info["target_factor"],
                "supertrend_performance": st_info["performance_index"],
                "supertrend_signal": int(st_df["supertrend_signal"].iloc[-1]),
                "trend_label": st_info["current_trend"],
                "trend_confidence": st_info["signal_strength"],
                "stop_level": float(st_df["supertrend"].iloc[-1]),
                "trend_duration_bars": st_info["trend_duration_bars"],
            }

            logger.info(
                f"SuperTrend AI for {symbol}: "
                f"factor={st_info['target_factor']:.2f}, "
                f"trend={st_info['current_trend']}, "
                f"confidence={st_info['signal_strength']}/10"
            )

            # Store signals
            if st_info.get("signals"):
                db.upsert_supertrend_signals(symbol, st_info["signals"])

        except Exception as e:
            logger.warning(f"SuperTrend AI failed for {symbol}: {e}")

        # Get horizons to process
        horizons = payload.get("horizons", settings.forecast_horizons)

        # Generate forecasts for each horizon
        for horizon in horizons:
            logger.info(f"Generating {horizon} forecast for {symbol}")

            # Create forecaster and generate forecast
            forecaster = BaselineForecaster()
            forecast = forecaster.generate_forecast(df, horizon)

            # Save to database
            db.upsert_forecast(
                symbol_id=symbol_id,
                horizon=forecast["horizon"],
                overall_label=forecast["label"],
                confidence=forecast["confidence"],
                points=forecast["points"],
                supertrend_data=supertrend_data,
            )

            logger.info(
                f"Saved {horizon} forecast for {symbol}: "
                f"{forecast['label']} ({forecast['confidence']*100:.2f}%)"
            )

        return True, None

    except Exception as e:
        logger.error(f"Failed to process forecast for {symbol}: {e}")
        return False, str(e)


def process_job(db: SupabaseDatabase, job: dict) -> tuple[bool, Optional[str]]:
    """Process a single job from the queue."""
    job_id = job["job_id"]
    job_type = job["job_type"]
    symbol = job["symbol"]
    payload = job.get("payload", {}) or {}

    logger.info(f"Processing job {job_id}: {job_type} for {symbol}")

    try:
        if job_type == "forecast":
            success, error = process_forecast_job(db, symbol, payload)
            return success, error or "Forecast generation failed"
        logger.warning(f"Unknown job type: {job_type}")
        return False, f"Unknown job type: {job_type}"
    except Exception as e:
        logger.error("Job %s failed with error: %s", job_id, e)
        return False, str(e)


def claim_and_process_job(db: SupabaseDatabase, job_type: Optional[str] = None) -> bool:
    """Claim the next pending job and process it."""
    # Claim next job using the database function
    result = db.client.rpc(
        "claim_next_job",
        {"p_job_type": job_type},
    ).execute()

    if not result.data:
        return False  # No pending jobs

    job = result.data[0]
    job_id = job["job_id"]

    # Process the job
    success, error = process_job(db, job)

    # Mark job as completed or failed
    db.client.rpc(
        "complete_job", {"p_job_id": str(job_id), "p_success": success, "p_error": error}
    ).execute()

    return True


def run_worker(
    continuous: bool = False,
    job_type: Optional[str] = None,
    poll_interval: int = 30,
):
    """Run the job worker."""
    logger.info("=" * 60)
    logger.info("Job Worker Starting")
    logger.info(f"Mode: {'Continuous' if continuous else 'Single Run'}")
    if job_type:
        logger.info(f"Job Type Filter: {job_type}")
    logger.info("=" * 60)

    db = SupabaseDatabase()
    jobs_processed = 0

    try:
        while True:
            # Process all pending jobs
            while claim_and_process_job(db, job_type):
                jobs_processed += 1

            if not continuous:
                break

            logger.debug(f"No pending jobs, sleeping for {poll_interval}s...")
            time.sleep(poll_interval)

    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    finally:
        db.close()
        logger.info("=" * 60)
        logger.info(f"Job Worker Complete - Processed {jobs_processed} jobs")
        logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Process jobs from the queue")
    parser.add_argument(
        "--continuous", action="store_true", help="Run continuously, polling for new jobs"
    )
    parser.add_argument(
        "--job-type",
        type=str,
        choices=["forecast", "backfill", "ranking"],
        help="Only process jobs of this type",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=30,
        help="Seconds between polls in continuous mode (default: 30)",
    )

    args = parser.parse_args()
    run_worker(continuous=args.continuous, job_type=args.job_type, poll_interval=args.poll_interval)


if __name__ == "__main__":
    main()
