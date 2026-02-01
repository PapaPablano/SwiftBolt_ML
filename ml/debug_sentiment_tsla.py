#!/usr/bin/env python3
"""
Debug sentiment for TSLA (news-driven stock) with real OHLCV (min 100 bars).
Reports: bar range, sentiment source, series stats, alignment, and sentiment_score in features.

Optional --as-of YYYY-MM-DD: pretend run date is that day (e.g. Thursday).
Then last bar = that day, lag1 = day before (e.g. Wed), lag7 = 7 days before (e.g. prior Thu).
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

MIN_BARS = 100
BARS_TO_FETCH = 350  # enough for start_idx=200 and ~100+ samples


def main():
    parser = argparse.ArgumentParser(description="Debug TSLA sentiment (optional: --as-of YYYY-MM-DD)")
    parser.add_argument("--as-of", type=str, metavar="YYYY-MM-DD", help="Pretend run date (e.g. Thursday); last bar = this day, lag1 = day before, lag7 = 7 days before")
    args = parser.parse_args()

    as_of_date = None
    if args.as_of:
        as_of_date = pd.Timestamp(args.as_of).normalize().date()

    from src.data.supabase_db import SupabaseDatabase
    from src.features.stock_sentiment import get_historical_sentiment_series, get_sentiment_for_ticker
    from src.models.baseline_forecaster import BaselineForecaster

    symbol = "TSLA"
    print("=" * 60)
    print(f"DEBUG SENTIMENT: {symbol} (min {MIN_BARS} bars real data)")
    if as_of_date:
        lag1_day = as_of_date - pd.Timedelta(days=1)
        lag7_day = as_of_date - pd.Timedelta(days=7)
        print(f"  Simulated as-of: {as_of_date} (last bar) → lag1={lag1_day}, lag7={lag7_day}")
    print("=" * 60)

    # 1) Load real OHLCV
    db = SupabaseDatabase()
    df = db.fetch_ohlc_bars(symbol, timeframe="d1", limit=BARS_TO_FETCH)
    if df is None or len(df) < MIN_BARS:
        print(f"  ERROR: Need at least {MIN_BARS} bars. Got: {len(df) if df is not None else 0}")
        return
    df = df.sort_values("ts").reset_index(drop=True)
    ts = pd.to_datetime(df["ts"])
    if as_of_date:
        df = df[ts.dt.date <= as_of_date].reset_index(drop=True)
        if len(df) < MIN_BARS:
            print(f"  ERROR: After as-of filter, only {len(df)} bars.")
            return
        ts = pd.to_datetime(df["ts"])
    start_date = ts.min().date()
    end_date = ts.max().date()
    print(f"\n1) OHLCV: {len(df)} bars, range {start_date} -> {end_date}")

    # 2) Check sentiment_scores in DB for this range
    try:
        from supabase import create_client
        from config.settings import settings
        client = create_client(
            settings.supabase_url,
            settings.supabase_key or settings.supabase_service_role_key or "",
        )
        sym = client.table("symbols").select("id").eq("ticker", symbol.upper()).single().execute()
        db_rows = 0
        if sym.data:
            r = (
                client.table("sentiment_scores")
                .select("as_of_date, sentiment_score")
                .eq("symbol_id", sym.data["id"])
                .gte("as_of_date", start_date.isoformat())
                .lte("as_of_date", end_date.isoformat())
                .execute()
            )
            db_rows = len(r.data or [])
        print(f"2) DB sentiment_scores in range: {db_rows} rows")
    except Exception as e:
        print(f"2) DB sentiment_scores check: {e}")
        db_rows = 0

    # 3) Get historical sentiment series (DB or FinViz fallback)
    sentiment_series = get_historical_sentiment_series(symbol, start_date, end_date)
    print(f"\n3) get_historical_sentiment_series:")
    print(f"   length={len(sentiment_series)}, index range={sentiment_series.index.min()} -> {sentiment_series.index.max()}")
    non_zero = (sentiment_series != 0).sum()
    print(f"   non-zero count={non_zero}, min={sentiment_series.min():.4f}, max={sentiment_series.max():.4f}, mean={sentiment_series.mean():.4f}")
    if non_zero > 0:
        sample = sentiment_series[sentiment_series != 0].tail(5)
        print(f"   sample (last 5 non-zero):\n{sample}")

    # 4) Raw FinViz snapshot (for comparison)
    scored = get_sentiment_for_ticker(symbol)
    print(f"\n4) FinViz raw: {len(scored)} items, index range {scored.index.min() if not scored.empty else 'N/A'} -> {scored.index.max() if not scored.empty else 'N/A'}")
    if not scored.empty and "sentiment_score" in scored.columns:
        print(f"   daily mean range: {scored['sentiment_score'].resample('D').mean().min():.4f} -> {scored['sentiment_score'].resample('D').mean().max():.4f}")

    # 5) Pipeline: prepare_training_data and inspect sentiment features in X
    forecaster = BaselineForecaster()
    X, y = forecaster.prepare_training_data(df, horizon_days=1, sentiment_series=sentiment_series)
    sent_cols = [c for c in X.columns if "sentiment" in c.lower()]
    if not sent_cols:
        print("\n5) FEATURE MATRIX: no sentiment columns (sentiment_score or sentiment_score_lag*)")
    else:
        print(f"\n5) FEATURE MATRIX sentiment: {sent_cols}")
        for c in sent_cols:
            s = X[c]
            print(f"   {c}: non-zero={(s != 0).sum()}, min={s.min():.4f}, max={s.max():.4f}, mean={s.mean():.4f}, std={s.std():.4f}")
        # Last bar dates for lag1/lag7
        last_bar_date = pd.to_datetime(df["ts"]).iloc[-1].date() if "ts" in df.columns else None
        if last_bar_date and "sentiment_score_lag1" in sent_cols:
            d1 = last_bar_date - pd.Timedelta(days=1)
            d7 = last_bar_date - pd.Timedelta(days=7)
            print(f"   (Last bar date {last_bar_date} → lag1 pulls {d1}, lag7 pulls {d7})")

    # Variance check for first sentiment column
    if sent_cols:
        s_std = float(X[sent_cols[0]].std() or 0)
        if s_std < 1e-9:
            print("\nNOTE: Sentiment has zero variance (constant). Fix: run backfill or ensure FinViz overrides recent bars.")
        elif s_std < 0.01:
            print("\nNOTE: Sentiment variance low (std < 0.01). Consider backfill for more history.")
        else:
            print(f"\nOK: Sentiment variance sufficient (std={s_std:.4f} > 0.01).")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
