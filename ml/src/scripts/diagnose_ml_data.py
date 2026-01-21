#!/usr/bin/env python3
"""Diagnostic script to check ML data freshness and identify issues."""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import settings  # noqa: E402
from src.data.supabase_db import db  # noqa: E402


def check_forecasts():
    """Check recent forecast data."""
    print("\n" + "=" * 60)
    print("FORECAST DATA CHECK")
    print("=" * 60)

    # Check total forecasts
    result = db.client.table("ml_forecasts").select("id", count="exact").execute()
    total = result.count or 0
    print(f"\nTotal forecasts in database: {total}")

    # Check recent forecasts (last 48 hours)
    cutoff = (datetime.utcnow() - timedelta(hours=48)).isoformat()
    result = (
        db.client.table("ml_forecasts")
        .select("id, symbol, horizon, label, confidence, created_at")
        .gte("created_at", cutoff)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )

    recent = result.data or []
    print(f"Forecasts in last 48 hours: {len(recent)}")

    if recent:
        print("\nMost recent forecasts:")
        for f in recent[:10]:
            print(
                f"  {f.get('created_at', 'N/A')[:19]} | "
                f"{f.get('symbol', 'N/A')[:10]:10} | "
                f"{f.get('horizon', 'N/A'):3} | "
                f"{f.get('label', 'N/A'):8} | "
                f"conf={f.get('confidence', 0):.2f}"
            )
    else:
        print("\n⚠️  NO RECENT FORECASTS - This is the problem!")
        print("   Forecasts need to be generated for evaluations to work.")


def check_ohlc_bars():
    """Check OHLC bar data freshness by provider."""
    print("\n" + "=" * 60)
    print("OHLC BAR DATA CHECK (by provider)")
    print("=" * 60)

    # Get a sample symbol
    symbol_result = (
        db.client.table("symbols")
        .select("id, ticker")
        .eq("ticker", "AAPL")
        .single()
        .execute()
    )

    if not symbol_result.data:
        print("⚠️  Could not find AAPL symbol")
        return

    symbol_id = symbol_result.data["id"]
    print(f"\nChecking AAPL (symbol_id: {symbol_id})")

    # Check each provider
    providers = ["alpaca", "polygon", "yfinance", "tradier"]

    for provider in providers:
        result = (
            db.client.table("ohlc_bars_v2")
            .select("ts, close, provider")
            .eq("symbol_id", symbol_id)
            .eq("timeframe", "d1")
            .eq("provider", provider)
            .eq("is_forecast", False)
            .order("ts", desc=True)
            .limit(5)
            .execute()
        )

        bars = result.data or []
        if bars:
            latest = bars[0]
            print(
                f"\n  {provider:10}: {len(bars)} recent bars, "
                f"latest: {latest.get('ts', 'N/A')[:10]} @ ${latest.get('close', 0):.2f}"
            )
        else:
            print(f"\n  {provider:10}: ⚠️  NO DATA")


def check_pending_evaluations():
    """Check pending evaluations via RPC."""
    print("\n" + "=" * 60)
    print("PENDING EVALUATIONS CHECK")
    print("=" * 60)

    for horizon in ["1D", "1W", "1M"]:
        result = db.client.rpc(
            "get_pending_evaluations",
            {"p_horizon": horizon},
        ).execute()

        pending = result.data or []
        print(f"\n  {horizon}: {len(pending)} pending evaluations")

        if pending:
            for p in pending[:3]:
                print(
                    f"    - {p.get('symbol', 'N/A')} | "
                    f"created: {p.get('created_at', 'N/A')[:10]}"
                )


def check_evaluations():
    """Check existing evaluation records."""
    print("\n" + "=" * 60)
    print("EVALUATION RECORDS CHECK")
    print("=" * 60)

    # Count total evaluations
    result = db.client.table("forecast_evaluations").select("id", count="exact").execute()
    total = result.count or 0
    print(f"\nTotal evaluation records: {total}")

    # Check recent evaluations
    cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
    result = (
        db.client.table("forecast_evaluations")
        .select("id, forecast_id, evaluation_date, was_correct")
        .gte("evaluation_date", cutoff)
        .order("evaluation_date", desc=True)
        .limit(10)
        .execute()
    )

    recent = result.data or []
    print(f"Evaluations in last 7 days: {len(recent)}")

    if recent:
        correct = sum(1 for e in recent if e.get("was_correct"))
        print(f"Accuracy (last {len(recent)}): {correct}/{len(recent)} = {100*correct/len(recent):.1f}%")


def check_data_refresh_jobs():
    """Check recent data refresh job activity."""
    print("\n" + "=" * 60)
    print("JOB QUEUE STATUS")
    print("=" * 60)

    # Check recent jobs
    result = (
        db.client.table("job_queue")
        .select("id, job_type, status, created_at, started_at, completed_at")
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )

    jobs = result.data or []
    print(f"\nRecent jobs: {len(jobs)}")

    # Group by type
    job_types = {}
    for j in jobs:
        jt = j.get("job_type", "unknown")
        if jt not in job_types:
            job_types[jt] = {"total": 0, "completed": 0, "failed": 0}
        job_types[jt]["total"] += 1
        status = j.get("status", "")
        if status == "completed":
            job_types[jt]["completed"] += 1
        elif status == "failed":
            job_types[jt]["failed"] += 1

    for jt, counts in sorted(job_types.items()):
        print(
            f"  {jt:20}: {counts['total']} total, "
            f"{counts['completed']} completed, {counts['failed']} failed"
        )


def main():
    print("\n" + "=" * 60)
    print("ML DATA DIAGNOSTIC REPORT")
    print(f"Generated: {datetime.utcnow().isoformat()[:19]} UTC")
    print("=" * 60)

    check_forecasts()
    check_ohlc_bars()
    check_pending_evaluations()
    check_evaluations()
    check_data_refresh_jobs()

    print("\n" + "=" * 60)
    print("DIAGNOSIS COMPLETE")
    print("=" * 60)
    print("\nIf forecasts are missing, run the forecast_job manually:")
    print("  cd ml && python -m src.forecast_job")
    print("\nIf OHLC data is stale, check the daily-data-refresh workflow.")
    print()


if __name__ == "__main__":
    main()
