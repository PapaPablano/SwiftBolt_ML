"""
Process the symbol backfill queue.

This script claims pending backfill jobs from the queue and fetches
historical OHLC data from Alpaca API.

Designed to run as a GitHub Action every 5 minutes.
"""

import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import requests  # noqa: E402

from src.data.supabase_db import db  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Alpaca API configuration
ALPACA_BASE_URL = "https://data.alpaca.markets/v2"
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET")

# Rate limiting: Alpaca allows 200 requests/minute
RATE_LIMIT_DELAY = 0.3  # 60/200 = 0.3 seconds between requests

# Timeframe configurations (Alpaca format)
TIMEFRAME_CONFIG = {
    "m15": {"alpaca_tf": "15Min", "max_days": 60},
    "h1": {"alpaca_tf": "1Hour", "max_days": 180},
    "h4": {"alpaca_tf": "4Hour", "max_days": 365},
    "d1": {"alpaca_tf": "1Day", "max_days": 2555},  # 7 years
    "w1": {"alpaca_tf": "1Week", "max_days": 2555},  # 7 years
}

# Maximum jobs to process per run (to stay within GitHub Action timeout)
MAX_JOBS_PER_RUN = 3


def get_alpaca_headers() -> dict:
    """Get authentication headers for Alpaca API."""
    return {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
        "Accept": "application/json",
    }


def fetch_alpaca_bars(
    symbol: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime,
) -> list[dict]:
    """Fetch OHLC bars from Alpaca API with automatic pagination."""
    if not ALPACA_API_KEY or not ALPACA_API_SECRET:
        raise ValueError("ALPACA_API_KEY and ALPACA_API_SECRET must be set")

    config = TIMEFRAME_CONFIG.get(timeframe)
    if not config:
        raise ValueError(f"Invalid timeframe: {timeframe}")

    alpaca_timeframe = config["alpaca_tf"]

    # Format dates to RFC-3339
    start_str = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")

    logger.info(f"Fetching {symbol} {timeframe} from {start_str} to {end_str}")

    all_bars = []
    page_token = None
    page_count = 0
    max_pages = 100  # Safety limit

    try:
        while page_count < max_pages:
            # Build URL
            url = (
                f"{ALPACA_BASE_URL}/stocks/bars?"
                f"symbols={symbol.upper()}&"
                f"timeframe={alpaca_timeframe}&"
                f"start={start_str}&"
                f"end={end_str}&"
                f"limit=10000&"
                f"adjustment=raw&"
                f"feed=iex&"
                f"sort=asc"
            )

            if page_token:
                url += f"&page_token={page_token}"

            response = requests.get(
                url,
                headers=get_alpaca_headers(),
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            # Extract bars for this symbol
            bars_data = data.get("bars", {}).get(symbol.upper(), [])

            if not bars_data and page_count == 0:
                logger.warning(f"No data returned for {symbol} {timeframe}")
                return []

            # Transform to our format
            for bar in bars_data:
                all_bars.append(
                    {
                        "ts": bar["t"],  # Already RFC-3339 format
                        "open": bar["o"],
                        "high": bar["h"],
                        "low": bar["l"],
                        "close": bar["c"],
                        "volume": bar["v"],
                    }
                )

            # Check for next page
            page_token = data.get("next_page_token")
            page_count += 1

            if page_token:
                logger.info(f"Fetched page {page_count} with {len(bars_data)} bars, continuing...")
                time.sleep(RATE_LIMIT_DELAY)
            else:
                break

        logger.info(f"Fetched {len(all_bars)} bars for {symbol} {timeframe}")
        return all_bars

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            logger.error("Rate limit exceeded!")
        elif e.response.status_code == 401:
            logger.error("Authentication failed! Verify Alpaca API credentials.")
        else:
            logger.error(f"HTTP error fetching {symbol}: {e}")
        return []
    except Exception as e:
        logger.error(f"Error fetching {symbol}: {e}")
        return []


def persist_bars(symbol_id: str, timeframe: str, bars: list[dict]) -> int:
    """Persist bars to ohlc_bars_v2 with provider='alpaca'. Returns count of inserted bars."""
    if not bars:
        return 0

    batch = []
    for bar in bars:
        batch.append(
            {
                "symbol_id": symbol_id,
                "timeframe": timeframe,
                "ts": bar["ts"],
                "open": bar["open"],
                "high": bar["high"],
                "low": bar["low"],
                "close": bar["close"],
                "volume": bar["volume"],
                "provider": "alpaca",
                "is_forecast": False,
                "data_status": "verified",
            }
        )

    try:
        # Batch upsert (1000 rows per request limit)
        inserted = 0
        batch_size = 1000

        for i in range(0, len(batch), batch_size):
            chunk = batch[i:i + batch_size]
            db.client.table("ohlc_bars_v2").upsert(
                chunk,
                on_conflict="symbol_id,timeframe,ts,provider,is_forecast",
            ).execute()
            inserted += len(chunk)

        logger.info(f"Persisted {inserted} bars")
        return inserted
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
    Process a single backfill job using Alpaca API.

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

            # Fetch from Alpaca
            bars = fetch_alpaca_bars(ticker, tf, start_date, end_date)

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
    if not ALPACA_API_KEY or not ALPACA_API_SECRET:
        logger.error("ALPACA_API_KEY and ALPACA_API_SECRET must be set!")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("Symbol Backfill Queue Processor (Alpaca)")
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
