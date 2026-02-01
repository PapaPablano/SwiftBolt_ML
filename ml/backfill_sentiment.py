#!/usr/bin/env python3
"""
Backfill sentiment_scores from news API (Alpaca/FinViz via edge) + VADER.

Fetches news per symbol per day, scores headlines with VADER, writes daily mean
to sentiment_scores so get_historical_sentiment_series returns non-zero values.

Usage:
  cd ml && python backfill_sentiment.py [--symbols AAPL,MSFT,...] [--days 365]
  cd ml && python backfill_sentiment.py --symbols SPY --from 2024-01-01 --to 2024-12-31
"""

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

# Run from ml/
sys.path.insert(0, str(Path(__file__).resolve().parent))

DEFAULT_SYMBOLS = [
    "AAPL", "AMD", "CRWD", "GOOG", "GOOGL", "HL", "META", "MSFT", "MU", "NVDA", "SPY", "TSLA",
]


def _get_vader():
    from src.features.stock_sentiment import _get_vader as g
    return g()


def score_headline(text: str) -> float:
    """VADER compound score for a headline."""
    if not (text and str(text).strip()):
        return 0.0
    vader = _get_vader()
    return float(vader.polarity_scores(str(text).strip())["compound"])


def fetch_news_for_day(symbol: str, day_start_utc: datetime, edge_url: str, auth_header: str) -> list[dict]:
    """GET /news?symbol=X&from=unix&to=unix for one day; return list of {title, publishedAt}."""
    end = day_start_utc + timedelta(days=1)
    from_ts = int(day_start_utc.timestamp())
    to_ts = int(end.timestamp())
    url = f"{edge_url}?symbol={symbol}&from={from_ts}&to={to_ts}&limit=50"
    try:
        r = requests.get(url, headers={"Authorization": f"Bearer {auth_header}"}, timeout=30)
        r.raise_for_status()
        data = r.json()
        items = data.get("items") or []
        return [{"title": it.get("title") or it.get("headline", ""), "publishedAt": it.get("publishedAt")} for it in items]
    except Exception as e:
        print(f"  fetch_news_for_day {symbol} {day_start_utc.date()}: {e}")
        return []


def backfill_symbol_date(
    symbol: str,
    symbol_id: str,
    as_of_date: datetime,
    edge_url: str,
    auth_header: str,
    supabase_client,
) -> bool:
    """Fetch news for one symbol/day, score with VADER, upsert sentiment_scores. Returns True if row written."""
    day_start = as_of_date.replace(tzinfo=timezone.utc) if as_of_date.tzinfo is None else as_of_date
    items = fetch_news_for_day(symbol, day_start, edge_url, auth_header)
    if not items:
        return False
    scores = [score_headline(it.get("title") or "") for it in items]
    daily_mean = float(pd.Series(scores).mean())
    date_only = as_of_date.date() if hasattr(as_of_date, "date") else pd.Timestamp(as_of_date).date()
    try:
        supabase_client.table("sentiment_scores").upsert(
            {"symbol_id": symbol_id, "as_of_date": date_only.isoformat(), "sentiment_score": daily_mean},
            on_conflict="symbol_id,as_of_date",
        ).execute()
        return True
    except Exception as e:
        print(f"  upsert {symbol} {date_only}: {e}")
        return False


def run_sentiment_backfill(
    symbols: list[str] | None = None,
    days: int = 7,
    from_date: str | None = None,
    to_date: str | None = None,
    delay: float = 0.5,
    quiet: bool = False,
) -> tuple[int, str | None]:
    """
    Run sentiment backfill for the given symbols.

    Callable from other scripts as a pre-run step before forecasts/benchmarks.

    Args:
        symbols: List of tickers; defaults to DEFAULT_SYMBOLS if None.
        days: Days to backfill from today (used if from_date/to_date not set).
        from_date: Start date YYYY-MM-DD (optional).
        to_date: End date YYYY-MM-DD (optional).
        delay: Seconds between API calls.
        quiet: If True, suppress per-row logging.

    Returns:
        (written_count, error_message). error_message is None on success.
    """
    from config.settings import settings
    from supabase import create_client

    if not getattr(settings, "supabase_url", None) or not (
        settings.supabase_key or settings.supabase_service_role_key
    ):
        return 0, "SUPABASE_URL and SUPABASE_KEY required in ml/.env"

    sym_list = symbols or DEFAULT_SYMBOLS
    key = settings.supabase_key or settings.supabase_service_role_key
    client = create_client(settings.supabase_url, key)
    edge_url = f"{settings.supabase_url.rstrip('/')}/functions/v1/news"

    if from_date and to_date:
        start = pd.Timestamp(from_date).tz_localize(None)
        end = pd.Timestamp(to_date).tz_localize(None)
    else:
        end = pd.Timestamp.utcnow().normalize()
        start = end - timedelta(days=days)

    symbol_ids = {}
    for sym in sym_list:
        try:
            r = client.table("symbols").select("id").eq("ticker", sym).single().execute()
            if r.data:
                symbol_ids[sym] = r.data["id"]
        except Exception as e:
            if not quiet:
                print(f"  symbol {sym}: {e}")
    if not symbol_ids:
        return 0, "No symbol_ids resolved"

    total_days = (end - start).days + 1
    written = 0
    for sym in sym_list:
        sid = symbol_ids.get(sym)
        if not sid:
            continue
        for i in range(total_days):
            d = start + timedelta(days=i)
            if backfill_symbol_date(sym, sid, d, edge_url, key, client):
                written += 1
            time.sleep(delay)
    return written, None


def main():
    parser = argparse.ArgumentParser(description="Backfill sentiment_scores from news API + VADER")
    parser.add_argument("--symbols", type=str, default=",".join(DEFAULT_SYMBOLS), help="Comma-separated symbols")
    parser.add_argument("--days", type=int, default=365, help="Number of days back from today (used if --from/--to not set)")
    parser.add_argument("--from", dest="from_date", type=str, help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", type=str, help="End date YYYY-MM-DD")
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between API calls")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    written, err = run_sentiment_backfill(
        symbols=symbols,
        days=args.days,
        from_date=args.from_date,
        to_date=args.to_date,
        delay=args.delay,
        quiet=False,
    )
    if err:
        print(err)
        sys.exit(1)
    print(f"Backfill done. Rows written: {written}")


if __name__ == "__main__":
    main()
