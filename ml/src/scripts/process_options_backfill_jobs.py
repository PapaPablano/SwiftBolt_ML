#!/usr/bin/env python3
"""
Process Options Backfill Jobs.

This script processes pending options backfill jobs from the queue.
It fetches options chain data and stores snapshots with ml_score.

Usage:
    python src/scripts/process_options_backfill_jobs.py
"""

import sys
import logging
import time
from pathlib import Path
from datetime import date

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.supabase_db import db  # noqa: E402
from src.scripts.backfill_options import (  # noqa: E402
    fetch_options_chain,
    persist_options_snapshot,
    update_options_ranks,
    calculate_ml_scores,
    RATE_LIMIT_DELAY,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_next_job():
    """Get the next pending backfill job from the queue."""
    try:
        result = db.client.rpc("get_next_options_backfill_job").execute()
        if result.data and len(result.data) > 0:
            job = result.data[0]
            logger.info(f"📥 Got job: {job['job_id']} for {job['ticker']}")
            return job
        return None
    except Exception as e:
        logger.error(f"Error getting next job: {e}")
        return None


def complete_job(job_id: str):
    """Mark a job as completed."""
    try:
        db.client.rpc(
            "complete_options_backfill_job", {"p_job_id": job_id}
        ).execute()
        logger.info(f"✅ Completed job {job_id}")
    except Exception as e:
        logger.error(f"Error completing job: {e}")


def fail_job(job_id: str, error: str):
    """Mark a job as failed."""
    try:
        db.client.rpc(
            "fail_options_backfill_job",
            {"p_job_id": job_id, "p_error": error[:500]},
        ).execute()
        logger.error(f"❌ Failed job {job_id}: {error}")
    except Exception as e:
        logger.error(f"Error failing job: {e}")


def process_job(job: dict) -> bool:
    """
    Process a single backfill job.

    Fetches options chain and stores snapshot with ml_score.
    """
    ticker = job["ticker"]
    job_id = job["job_id"]
    snapshot_date = date.today()

    logger.info(f"🔄 Processing backfill for {ticker}...")

    try:
        # Fetch options chain
        chain_data = fetch_options_chain(ticker)
        calls = chain_data.get("calls", [])
        puts = chain_data.get("puts", [])

        if not calls and not puts:
            fail_job(job_id, f"No options data for {ticker}")
            return False

        # Calculate ML scores
        ml_scores = calculate_ml_scores(ticker, calls, puts)

        # Store snapshot with ml_scores
        inserted, skipped = persist_options_snapshot(
            ticker, calls, puts, snapshot_date, ml_scores=ml_scores
        )

        # Update ranks
        ranks_updated = update_options_ranks(ticker, calls, puts)

        logger.info(
            f"✅ {ticker}: {inserted} snapshots, {ranks_updated} ranks"
        )

        complete_job(job_id)
        return True

    except Exception as e:
        fail_job(job_id, str(e))
        return False


def main():
    """Process all pending backfill jobs."""
    logger.info("=" * 60)
    logger.info("OPTIONS BACKFILL JOB PROCESSOR")
    logger.info("=" * 60)

    processed = 0
    failed = 0

    while True:
        job = get_next_job()
        if not job:
            logger.info("No more pending jobs")
            break

        success = process_job(job)
        if success:
            processed += 1
        else:
            failed += 1

        # Rate limiting
        time.sleep(RATE_LIMIT_DELAY)

    logger.info("=" * 60)
    logger.info(f"Backfill Complete: {processed} processed, {failed} failed")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
