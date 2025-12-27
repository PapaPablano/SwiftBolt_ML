"""
Process the symbol backfill queue.

This script claims pending backfill jobs from the queue and fetches
historical OHLC data from Polygon API.

Designed to run as a GitHub Action every 5 minutes.
"""

import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import requests

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.supabase_db import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Polygon API configuration
POLYGON_BASE_URL = "https://api.polygon.io"
POLYGON_API_KEY = os.getenv("MASSIVE_API_KEY") or os.getenv("POLYGON_API_KEY")

# Rate limiting: Polygon free tier = 5 requests/minute
RATE_LIMIT_DELAY = 12.5

# Timeframe configurations
TIMEFRAME_CONFIG = {
    "m15": {"multiplier": 15, "timespan": "minute", "max_days": 60},
    "h1": {"multiplier": 1, "timespan": "hour", "max_days": 180},
    "h4": {"multiplier": 4, "timespan": "hour", "max_days": 365},
    "d1": {"multiplier": 1, "timespan": "day", "max_days": 730},
    "w1": {"multiplier": 1, "timespan": "week", "max_days": 1825},
}

# Maximum jobs to process per run (to stay within GitHub Action timeout)
MAX_JOBS_PER_RUN = 3


def fetch_polygon_bars(
    symbol: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime,
) -> list[dict]:
    """Fetch OHLC bars from Polygon API."""
    if not POLYGON_API_KEY:
        raise ValueError("MASSIVE_API_KEY or POLYGON_API_KEY not set")

    config = TIMEFRAME_CONFIG.get(timeframe)
    if not config:
        raise ValueError(f"Invalid timeframe: {timeframe}")

    multiplier = config["multiplier"]
    timespan = config["timespan"]

    # Format dates
    if timespan in ("day", "week", "month"):
        from_str = start_date.strftime("%Y-%m-%d")
        to_str = end_date.strftime("%Y-%m-%d")
    else:
        from_str = str(int(start_date.timestamp() * 1000))
        to_str = str(int(end_date.timestamp() * 1000))

    url = (
        f"{POLYGON_BASE_URL}/v2/aggs/ticker/{symbol.upper()}/range/"
        f"{multiplier}/{timespan}/{from_str}/{to_str}"
    )
    params = {
        "adjusted": "true",
        "sort": "asc",
        "limit": "50000",
        "apiKey": POLYGON_API_KEY,
    }

    logger.info(f"Fetching {symbol} {timeframe} from {from_str} to {to_str}")

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "ERROR":
            logger.error(f"Polygon API error: {data}")
            return []

        results = data.get("results", [])
        if not results:
            logger.warning(f"No data returned for {symbol} {timeframe}")
            return []

        # Transform to our format
        bars = []
        for r in results:
            bars.append({
                "ts": datetime.fromtimestamp(
                    r["t"] / 1000, tz=timezone.utc
                ).isoformat(),
                "open": r["o"],
                "high": r["h"],
                "low": r["l"],
                "close": r["c"],
                "volume": r["v"],
            })

        logger.info(f"Fetched {len(bars)} bars for {symbol} {timeframe}")
        return bars

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            logger.error("Rate limit exceeded!")
        else:
            logger.error(f"HTTP error fetching {symbol}: {e}")
        return []
    except Exception as e:
        logger.error(f"Error fetching {symbol}: {e}")
        return []


def persist_bars(symbol_id: str, timeframe: str, bars: list[dict]) -> int:
    """Persist bars to database. Returns count of inserted bars."""
    if not bars:
        return 0

    batch = []
    for bar in bars:
        batch.append({
            "symbol_id": symbol_id,
            "timeframe": timeframe,
            "ts": bar["ts"],
            "open": bar["open"],
            "high": bar["high"],
            "low": bar["low"],
            "close": bar["close"],
            "volume": bar["volume"],
            "provider": "massive",
        })

    try:
        db.client.table("ohlc_bars").upsert(
            batch,
            on_conflict="symbol_id,timeframe,ts",
        ).execute()
        logger.info(f"Persisted {len(batch)} bars")
        return len(batch)
    except Exception as e:
        logger.error(f"Error persisting bars: {e}")
        return 0


def process_backfill_job(
    job_id: str,
    symbol_id: str,
    ticker: str,
    timeframes: list[str],
) -> tuple[bool, int, Optional[str]]:
    """
    Process a single backfill job.
    
    Returns: (success, bars_inserted, error_message)
    """
    total_bars = 0
    errors = []

    for tf in timeframes:
        config = TIMEFRAME_CONFIG.get(tf)
        if not config:
            errors.append(f"Invalid timeframe: {tf}")
            continue

        try:
            # Calculate date range
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=config["max_days"])

            # Fetch from Polygon
            bars = fetch_polygon_bars(ticker, tf, start_date, end_date)

            if bars:
                inserted = persist_bars(symbol_id, tf, bars)
                total_bars += inserted

            # Rate limiting
            if tf != timeframes[-1]:
                logger.info(f"Rate limit delay ({RATE_LIMIT_DELAY}s)...")
                time.sleep(RATE_LIMIT_DELAY)

        except Exception as e:
            errors.append(f"{tf}: {str(e)}")
            logger.error(f"Error processing {ticker} {tf}: {e}")

    success = total_bars > 0 or len(errors) == 0
    error_msg = "; ".join(errors) if errors else None

    return success, total_bars, error_msg


def claim_next_job() -> Optional[dict]:
    """Claim the next pending backfill job."""
    try:
        response = db.client.rpc("claim_next_backfill_job").execute()
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"Error claiming job: {e}")
        return None


def complete_job(
    job_id: str,
    success: bool,
    bars_inserted: int = 0,
    error_message: Optional[str] = None,
) -> None:
    """Mark a job as completed or failed."""
    try:
        db.client.rpc(
            "complete_backfill_job",
            {
                "p_job_id": job_id,
                "p_success": success,
                "p_bars_inserted": bars_inserted,
                "p_error_message": error_message,
            },
        ).execute()
    except Exception as e:
        logger.error(f"Error completing job {job_id}: {e}")


def main():
    if not POLYGON_API_KEY:
        logger.error("MASSIVE_API_KEY or POLYGON_API_KEY not set!")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("Symbol Backfill Queue Processor")
    logger.info(f"Max jobs per run: {MAX_JOBS_PER_RUN}")
    logger.info("=" * 60)

    jobs_processed = 0
    total_bars = 0

    while jobs_processed < MAX_JOBS_PER_RUN:
        # Claim next job
        job = claim_next_job()

        if not job:
            logger.info("No pending jobs in queue")
            break

        job_id = job["job_id"]
        symbol_id = job["symbol_id"]
        ticker = job["ticker"]
        timeframes = job["timeframes"]

        logger.info(f"Processing job {job_id}: {ticker} ({timeframes})")

        # Process the job
        success, bars_inserted, error_msg = process_backfill_job(
            job_id, symbol_id, ticker, timeframes
        )

        # Complete the job
        complete_job(job_id, success, bars_inserted, error_msg)

        jobs_processed += 1
        total_bars += bars_inserted

        if success:
            logger.info(f"✅ Completed {ticker}: {bars_inserted} bars")
        else:
            logger.error(f"❌ Failed {ticker}: {error_msg}")

    logger.info("")
    logger.info("=" * 60)
    logger.info("Queue Processing Complete")
    logger.info(f"Jobs processed: {jobs_processed}")
    logger.info(f"Total bars inserted: {total_bars}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
