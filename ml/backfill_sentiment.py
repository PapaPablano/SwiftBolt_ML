#!/usr/bin/env python3
"""
Backfill sentiment_scores from news API (Alpaca/FinViz via edge) + VADER.

Fetches news per symbol per day, scores headlines with VADER, writes daily mean
to sentiment_scores so get_historical_sentiment_series returns non-zero values.

Usage:
  cd ml && python backfill_sentiment.py [--symbols AAPL,MSFT,...] [--days 365]
  cd ml && python backfill_sentiment.py --symbols SPY --from 2024-01-01 --to 2024-12-31

Phased strategy:
  Phase 1 (2-3 min):  --symbols TSLA,AAPL,NVDA --days 7 --delay 0.3
  Phase 2 (10-15 min): --symbols ALL --days 90 --delay 0.3 [--workers 4]
  Phase 3 (optional):  --days 365 --workers 4 --skip-existing (incremental fast)
"""

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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


def _get_existing_dates(client, symbol_id: str, start_iso: str, end_iso: str) -> set:
    """Return set of as_of_date (YYYY-MM-DD) already in sentiment_scores for this symbol."""
    try:
        r = (
            client.table("sentiment_scores")
            .select("as_of_date")
            .eq("symbol_id", symbol_id)
            .gte("as_of_date", start_iso)
            .lte("as_of_date", end_iso)
            .execute()
        )
        return {row["as_of_date"] for row in (r.data or [])}
    except Exception:
        return set()


def _backfill_one_symbol(
    symbol: str,
    symbol_id: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    supabase_url: str,
    key: str,
    delay: float,
    skip_existing: bool,
    quiet: bool,
) -> int:
    """
    Backfill one symbol for [start, end]. Creates its own Supabase client (thread-safe).
    Returns number of rows written.
    """
    from supabase import create_client

    client = create_client(supabase_url, key)
    edge_url = f"{supabase_url.rstrip('/')}/functions/v1/news"
    start_iso = start.date().isoformat()
    end_iso = end.date().isoformat()

    total_days = (end - start).days + 1
    if skip_existing:
        existing = _get_existing_dates(client, symbol_id, start_iso, end_iso)
        to_fetch = [
            start + timedelta(days=i)
            for i in range(total_days)
            if (start + timedelta(days=i)).date().isoformat() not in existing
        ]
        if not quiet and (len(existing) or to_fetch):
            print(f"  {symbol}: {len(to_fetch)}/{total_days} dates need backfill")
    else:
        to_fetch = [start + timedelta(days=i) for i in range(total_days)]

    written = 0
    for d in to_fetch:
        if backfill_symbol_date(symbol, symbol_id, d, edge_url, key, client):
            written += 1
        time.sleep(delay)
    return written


def run_sentiment_backfill(
    symbols: list[str] | None = None,
    days: int = 7,
    from_date: str | None = None,
    to_date: str | None = None,
    delay: float = 0.5,
    quiet: bool = False,
    workers: int = 1,
    skip_existing: bool = False,
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
        workers: Number of symbols to process in parallel (default 1). Use 2-4 for faster backfill.
        skip_existing: If True, only fetch dates not already in sentiment_scores (fast re-runs).

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
    supabase_url = settings.supabase_url
    client = create_client(supabase_url, key)

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

    if workers is None or workers < 1:
        workers = 1
    if workers > 1:
        # Parallel: one task per symbol, each with its own client
        written = 0
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    _backfill_one_symbol,
                    sym,
                    symbol_ids[sym],
                    start,
                    end,
                    supabase_url,
                    key,
                    delay,
                    skip_existing,
                    quiet,
                ): sym
                for sym in sym_list
                if symbol_ids.get(sym)
            }
            for future in as_completed(futures):
                sym = futures[future]
                try:
                    written += future.result()
                    if not quiet:
                        print(f"  {sym}: done")
                except Exception as e:
                    if not quiet:
                        print(f"  {sym}: {e}")
        return written, None

    # Sequential (original behavior)
    written = 0
    for sym in sym_list:
        sid = symbol_ids.get(sym)
        if not sid:
            continue
        written += _backfill_one_symbol(
            sym, sid, start, end, supabase_url, key, delay, skip_existing, quiet
        )
    return written, None


def main():
    parser = argparse.ArgumentParser(description="Backfill sentiment_scores from news API + VADER")
    parser.add_argument("--symbols", type=str, default=",".join(DEFAULT_SYMBOLS), help="Comma-separated symbols")
    parser.add_argument("--days", type=int, default=365, help="Number of days back from today (used if --from/--to not set)")
    parser.add_argument("--from", dest="from_date", type=str, help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", type=str, help="End date YYYY-MM-DD")
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between API calls")
    parser.add_argument("--workers", type=int, default=1, help="Parallel workers (symbols). Use 2-4 for faster backfill.")
    parser.add_argument("--skip-existing", action="store_true", help="Skip dates already in DB (fast incremental re-runs)")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    written, err = run_sentiment_backfill(
        symbols=symbols,
        days=args.days,
        from_date=args.from_date,
        to_date=args.to_date,
        delay=args.delay,
        quiet=False,
        workers=args.workers,
        skip_existing=args.skip_existing,
    )
    if err:
        print(err)
        sys.exit(1)
    print(f"Backfill done. Rows written: {written}")


if __name__ == "__main__":
    main()
