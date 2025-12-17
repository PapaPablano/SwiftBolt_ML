"""
Forecast Job Worker - Processes ML forecast jobs from the queue.

This worker polls the forecast_jobs table for pending jobs and executes
the forecast generation script for each symbol in the queue.

Usage:
    python src/forecast_job_worker.py           # Run once
    python src/forecast_job_worker.py --watch   # Run continuously (poll every 10s)
"""

import argparse
import logging
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from src.data.supabase_db import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_next_job():
    """Get the next pending job from the queue using the database function."""
    try:
        # Call the database function to get and lock the next job
        result = db.client.rpc("get_next_forecast_job").execute()

        if result.data and len(result.data) > 0:
            job = result.data[0]
            logger.info(f"📥 Got forecast job: {job['job_id']} for symbol {job['symbol']}")
            return job
        else:
            return None

    except Exception as e:
        logger.error(f"Error getting next forecast job: {e}")
        return None


def complete_job(job_id: str):
    """Mark a job as completed."""
    try:
        db.client.rpc("complete_forecast_job", {"p_job_id": job_id}).execute()
        logger.info(f"✅ Marked forecast job {job_id} as completed")
    except Exception as e:
        logger.error(f"Error completing forecast job {job_id}: {e}")


def fail_job(job_id: str, error_message: str):
    """Mark a job as failed."""
    try:
        db.client.rpc("fail_forecast_job", {
            "p_job_id": job_id,
            "p_error_message": error_message[:500]  # Limit error message length
        }).execute()
        logger.error(f"❌ Marked forecast job {job_id} as failed: {error_message}")
    except Exception as e:
        logger.error(f"Error marking forecast job as failed {job_id}: {e}")


def process_job(job: dict) -> bool:
    """
    Process a forecast job by running the forecast_job.py script.

    Args:
        job: Job dictionary with 'job_id', 'symbol', and 'created_at'

    Returns:
        True if successful, False otherwise
    """
    job_id = job['job_id']
    symbol = job['symbol']

    logger.info(f"🔄 Processing forecast job {job_id} for {symbol}...")

    try:
        # Get the path to the forecast script
        script_path = Path(__file__).parent / "forecast_job.py"
        python_path = sys.executable  # Use the same Python interpreter

        # Run the forecast job script as a subprocess
        result = subprocess.run(
            [python_path, str(script_path), "--symbol", symbol],
            capture_output=True,
            text=True,
            timeout=180  # 3 minute timeout (forecasts can take longer)
        )

        if result.returncode == 0:
            logger.info(f"✅ Successfully processed forecast job {job_id} for {symbol}")
            logger.debug(f"Output: {result.stdout}")
            complete_job(job_id)
            return True
        else:
            error_msg = f"Script failed with exit code {result.returncode}: {result.stderr}"
            logger.error(f"❌ Forecast job {job_id} failed: {error_msg}")
            fail_job(job_id, error_msg)
            return False

    except subprocess.TimeoutExpired:
        error_msg = "Forecast job timed out after 180 seconds"
        logger.error(f"❌ Forecast job {job_id} timed out")
        fail_job(job_id, error_msg)
        return False

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"❌ Forecast job {job_id} error: {error_msg}")
        fail_job(job_id, error_msg)
        return False


def process_queue_once() -> int:
    """
    Process all pending forecast jobs in the queue once.

    Returns:
        Number of jobs processed
    """
    logger.info("="*60)
    logger.info("Checking for pending forecast jobs...")
    logger.info("="*60)

    processed = 0

    while True:
        job = get_next_job()

        if job is None:
            logger.info("No more pending forecast jobs in queue")
            break

        process_job(job)
        processed += 1

    logger.info(f"Processed {processed} forecast job(s)")
    return processed


def watch_queue(poll_interval: int = 10):
    """
    Continuously watch the queue and process forecast jobs as they arrive.

    Args:
        poll_interval: Seconds to wait between polls (default: 10)
    """
    logger.info("="*60)
    logger.info("Forecast Job Worker - Watch Mode")
    logger.info(f"Polling every {poll_interval} seconds")
    logger.info("Press Ctrl+C to stop")
    logger.info("="*60)

    try:
        while True:
            processed = process_queue_once()

            if processed == 0:
                logger.info(f"Waiting {poll_interval} seconds before next poll...")
                time.sleep(poll_interval)
            # If jobs were processed, check again immediately for more

    except KeyboardInterrupt:
        logger.info("\n🛑 Forecast worker stopped by user")
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description="Process ML forecast jobs from the queue"
    )

    parser.add_argument(
        "--watch",
        action="store_true",
        help="Continuously watch the queue and process jobs as they arrive"
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Poll interval in seconds when in watch mode (default: 10)"
    )

    args = parser.parse_args()

    if args.watch:
        watch_queue(poll_interval=args.interval)
    else:
        process_queue_once()


if __name__ == "__main__":
    main()
