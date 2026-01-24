"""
Ranking Job Worker - Processes ranking jobs from the queue.

This worker polls the ranking_jobs table for pending jobs and executes
the options ranking script for each symbol in the queue.

Usage:
    python src/ranking_job_worker.py           # Run once
    python src/ranking_job_worker.py --watch   # Run continuously
                                              (poll every 10s)
"""

import argparse
import logging
import subprocess
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.supabase_db import db  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_next_job():
    """Get the next pending job from the queue using the database function."""
    try:
        # Call the database function to get and lock the next job
        result = db.client.rpc("get_next_ranking_job").execute()

        if result.data and len(result.data) > 0:
            job = result.data[0]
            logger.info(
                "📥 Got job: %s for symbol %s",
                job["job_id"],
                job["symbol"],
            )
            return job
        return None

    except Exception as e:
        logger.error(f"Error getting next job: {e}")
        return None


def complete_job(job_id: str):
    """Mark a job as completed."""
    try:
        db.client.rpc("complete_ranking_job", {"job_id": job_id}).execute()
        logger.info(f"✅ Marked job {job_id} as completed")
    except Exception as e:
        logger.error(f"Error completing job {job_id}: {e}")


def fail_job(job_id: str, error_message: str):
    """Mark a job as failed."""
    try:
        db.client.rpc(
            "fail_ranking_job",
            {
                "job_id": job_id,
                "error_msg": error_message[:500],  # Limit error message length
            },
        ).execute()
        logger.error(f"❌ Marked job {job_id} as failed: {error_message}")
    except Exception as e:
        logger.error(f"Error marking job as failed {job_id}: {e}")


def process_job(job: dict) -> bool:
    """
    Process a ranking job by running the options_ranking_job.py script.

    Args:
        job: Job dictionary with 'job_id', 'symbol', and 'created_at'

    Returns:
        True if successful, False otherwise
    """
    job_id = job["job_id"]
    symbol = job["symbol"]

    logger.info("🔄 Processing job %s for %s...", job_id, symbol)

    try:
        # Get the path to the ranking script
        script_path = Path(__file__).parent / "options_ranking_job.py"
        python_path = sys.executable  # Use the same Python interpreter

        # Run the ranking job script as a subprocess
        result = subprocess.run(
            [python_path, str(script_path), "--symbol", symbol],
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout
        )

        if result.returncode == 0:
            logger.info("✅ Successfully processed job %s for %s", job_id, symbol)
            logger.debug("Output: %s", result.stdout)
            complete_job(job_id)
            return True

        error_msg = f"Script failed with exit code {result.returncode}: " f"{result.stderr}"
        logger.error("❌ Job %s failed: %s", job_id, error_msg)
        fail_job(job_id, error_msg)
        return False

    except subprocess.TimeoutExpired:
        error_msg = "Job timed out after 120 seconds"
        logger.error("❌ Job %s timed out", job_id)
        fail_job(job_id, error_msg)
        return False

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error("❌ Job %s error: %s", job_id, error_msg)
        fail_job(job_id, error_msg)
        return False


def process_queue_once() -> int:
    """
    Process all pending jobs in the queue once.

    Returns:
        Number of jobs processed
    """
    logger.info("=" * 60)
    logger.info("Checking for pending jobs...")
    logger.info("=" * 60)

    processed = 0

    while True:
        job = get_next_job()

        if job is None:
            logger.info("No more pending jobs in queue")
            break

        process_job(job)
        processed += 1

    logger.info(f"Processed {processed} job(s)")
    return processed


def watch_queue(poll_interval: int = 10):
    """
    Continuously watch the queue and process jobs as they arrive.

    Args:
        poll_interval: Seconds to wait between polls (default: 10)
    """
    logger.info("=" * 60)
    logger.info("Ranking Job Worker - Watch Mode")
    logger.info(f"Polling every {poll_interval} seconds")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 60)

    try:
        while True:
            processed = process_queue_once()

            if processed == 0:
                logger.info(f"Waiting {poll_interval} seconds before next poll...")
                time.sleep(poll_interval)
            # If jobs were processed, check again immediately for more

    except KeyboardInterrupt:
        logger.info("\n🛑 Worker stopped by user")
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Process ranking jobs from the queue")

    parser.add_argument(
        "--watch",
        action="store_true",
        help="Continuously watch the queue and process jobs as they arrive",
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Poll interval in seconds when in watch mode (default: 10)",
    )

    args = parser.parse_args()

    if args.watch:
        watch_queue(poll_interval=args.interval)
    else:
        process_queue_once()


if __name__ == "__main__":
    main()
