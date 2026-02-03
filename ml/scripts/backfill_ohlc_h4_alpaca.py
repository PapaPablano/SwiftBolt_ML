"""
Backfill Alpaca 4h bars into ohlc_bars_h4_alpaca for TabPFN/hybrid experiments.

Use this table only for ML experiment variants (ML house rules); regime analysis
stays on d1 from ohlc_bars_v2.

Usage:
    cd ml && python scripts/backfill_ohlc_h4_alpaca.py
    python scripts/backfill_ohlc_h4_alpaca.py --symbols PG KO JNJ MRK MSFT AMGN NVDA MU ALB
    python scripts/backfill_ohlc_h4_alpaca.py --start 2020-01-01 --end 2025-12-31

Requires: ALPACA_API_KEY, ALPACA_API_SECRET, Supabase (SUPABASE_URL, SUPABASE_KEY).
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

root_dir = Path(__file__).resolve().parent.parent.parent
load_dotenv(root_dir / ".env")
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.supabase_db import SupabaseDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

ALPACA_BASE_URL = "https://data.alpaca.markets/v2"
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET")
RATE_LIMIT_DELAY = 0.3  # 60/200 per minute

# 10-stock universe for regime/TabPFN experiments
DEFAULT_SYMBOLS = [
    "PG", "KO", "JNJ", "MRK",
    "MSFT", "AMGN", "BRK.B",
    "NVDA", "MU", "ALB",
]


def get_alpaca_headers() -> dict:
    return {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
        "Accept": "application/json",
    }


def fetch_alpaca_4h_bars(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
) -> list[dict]:
    """Fetch 4h bars from Alpaca. Returns list of {ts, open, high, low, close, volume}."""
    if not ALPACA_API_KEY or not ALPACA_API_SECRET:
        raise ValueError("ALPACA_API_KEY and ALPACA_API_SECRET must be set")

    start_str = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    all_bars = []
    page_token = None
    page_count = 0
    max_pages = 100

    while page_count < max_pages:
        url = (
            f"{ALPACA_BASE_URL}/stocks/bars?"
            f"symbols={symbol.upper()}&"
            "timeframe=4Hour&"
            f"start={start_str}&"
            f"end={end_str}&"
            "limit=10000&"
            "adjustment=raw&"
            "feed=iex&"
            "sort=asc"
        )
        if page_token:
            url += f"&page_token={page_token}"

        try:
            response = requests.get(
                url,
                headers=get_alpaca_headers(),
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error("Alpaca fetch %s: %s", symbol, e)
            return all_bars

        bars_data = data.get("bars", {}).get(symbol.upper(), [])
        if not bars_data and page_count == 0:
            logger.warning("No 4h data for %s", symbol)
            return []

        for bar in bars_data:
            bar_ts = datetime.fromisoformat(bar["t"].replace("Z", "+00:00"))
            all_bars.append({
                "ts": bar_ts.isoformat().replace("+00:00", "Z"),
                "open": bar["o"],
                "high": bar["h"],
                "low": bar["l"],
                "close": bar["c"],
                "volume": bar["v"],
            })

        page_token = data.get("next_page_token")
        page_count += 1
        if page_token:
            time.sleep(RATE_LIMIT_DELAY)
        else:
            break

    logger.info("Fetched %s 4h bars for %s", len(all_bars), symbol)
    return all_bars


def persist_h4_alpaca(db: SupabaseDatabase, symbol: str, bars: list[dict]) -> int:
    """Upsert bars into ohlc_bars_h4_alpaca. Returns count persisted."""
    if not bars:
        return 0

    try:
        symbol_id = db.get_or_create_symbol_id(symbol)
    except Exception as e:
        logger.error("get_or_create_symbol_id %s: %s", symbol, e)
        return 0

    batch = []
    for bar in bars:
        batch.append({
            "symbol_id": symbol_id,
            "ts": bar["ts"],
            "open": bar["open"],
            "high": bar["high"],
            "low": bar["low"],
            "close": bar["close"],
            "volume": bar["volume"],
            "provider": "alpaca",
        })

    try:
        inserted = 0
        batch_size = 1000
        for i in range(0, len(batch), batch_size):
            chunk = batch[i : i + batch_size]
            db.client.table("ohlc_bars_h4_alpaca").upsert(
                chunk,
                on_conflict="symbol_id,ts",
            ).execute()
            inserted += len(chunk)
        logger.info("Persisted %s 4h bars for %s to ohlc_bars_h4_alpaca", inserted, symbol)
        return inserted
    except Exception as e:
        logger.error("Persist %s: %s", symbol, e)
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Alpaca 4h bars into ohlc_bars_h4_alpaca")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS, help="Symbols to backfill")
    parser.add_argument("--start", default="2020-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=None, help="End date (YYYY-MM-DD), default today")
    args = parser.parse_args()

    end_date = datetime.now(timezone.utc)
    if args.end:
        end_date = datetime.fromisoformat(args.end.replace("Z", "+00:00"))
    start_date = datetime.fromisoformat(args.start.replace("Z", "+00:00"))
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=timezone.utc)

    db = SupabaseDatabase()
    total = 0
    for symbol in args.symbols:
        bars = fetch_alpaca_4h_bars(symbol, start_date, end_date)
        if bars:
            total += persist_h4_alpaca(db, symbol, bars)
        time.sleep(RATE_LIMIT_DELAY)

    logger.info("Done. Total bars persisted: %s", total)


if __name__ == "__main__":
    main()
