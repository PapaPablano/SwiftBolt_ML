#!/usr/bin/env python3
"""Verify options data in Supabase after backfill."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add ml directory to path
ml_dir = Path(__file__).parent.parent
sys.path.insert(0, str(ml_dir))

from src.data.supabase_db import db

EXPECTED_SYMBOLS = ["AAPL", "AMD", "CRWD", "GOOG", "MU", "NVDA", "PLTR", "TSLA"]
SNAPSHOT_DATE = "2026-01-24"


def verify_options_chain_snapshots():
    """Verify options_chain_snapshots table has data."""
    print("\n" + "=" * 80)
    print("VERIFYING: options_chain_snapshots (Current Snapshot)")
    print("=" * 80)

    total_records = 0
    for symbol in EXPECTED_SYMBOLS:
        try:
            # Get symbol_id
            symbol_response = (
                db.client.table("symbols").select("id").eq("ticker", symbol).single().execute()
            )
            symbol_id = symbol_response.data["id"]

            # Count records for today
            response = (
                db.client.table("options_chain_snapshots")
                .select("*", count="exact")
                .eq("underlying_symbol_id", symbol_id)
                .eq("snapshot_date", SNAPSHOT_DATE)
                .execute()
            )

            count = response.count or 0
            total_records += count
            status = "✅" if count > 0 else "❌"
            print(f"{status} {symbol}: {count:,} records")

        except Exception as e:
            print(f"❌ {symbol}: Error - {e}")

    print(f"\n📊 Total chain snapshots: {total_records:,}")
    return total_records


def verify_options_snapshots():
    """Verify options_snapshots table has historical data."""
    print("\n" + "=" * 80)
    print("VERIFYING: options_snapshots (Historical Backfill)")
    print("=" * 80)

    cutoff_date = (datetime.now() - timedelta(days=15)).isoformat()
    total_records = 0

    for symbol in EXPECTED_SYMBOLS:
        try:
            # Get symbol_id
            symbol_response = (
                db.client.table("symbols").select("id").eq("ticker", symbol).single().execute()
            )
            symbol_id = symbol_response.data["id"]

            # Count historical records (last 15 days)
            response = (
                db.client.table("options_snapshots")
                .select("*", count="exact")
                .eq("underlying_symbol_id", symbol_id)
                .gte("snapshot_time", cutoff_date)
                .execute()
            )

            count = response.count or 0
            total_records += count

            # Get date range
            date_response = (
                db.client.table("options_snapshots")
                .select("snapshot_time")
                .eq("underlying_symbol_id", symbol_id)
                .gte("snapshot_time", cutoff_date)
                .order("snapshot_time", desc=False)
                .limit(1)
                .execute()
            )

            oldest = "N/A"
            if date_response.data:
                oldest = date_response.data[0]["snapshot_time"][:10]

            status = "✅" if count > 0 else "❌"
            print(f"{status} {symbol}: {count:,} records (oldest: {oldest})")

        except Exception as e:
            print(f"❌ {symbol}: Error - {e}")

    print(f"\n📊 Total historical snapshots: {total_records:,}")
    return total_records


def verify_options_ranks():
    """Verify options_ranks table has ranking data."""
    print("\n" + "=" * 80)
    print("VERIFYING: options_ranks (Rankings)")
    print("=" * 80)

    total_records = 0
    for symbol in EXPECTED_SYMBOLS:
        try:
            # Get symbol_id
            symbol_response = (
                db.client.table("symbols").select("id").eq("ticker", symbol).single().execute()
            )
            symbol_id = symbol_response.data["id"]

            # Count ranks for today
            response = (
                db.client.table("options_ranks")
                .select("*", count="exact")
                .eq("underlying_symbol_id", symbol_id)
                .gte("run_at", f"{SNAPSHOT_DATE}T00:00:00")
                .execute()
            )

            count = response.count or 0
            total_records += count

            # Get latest run timestamp
            latest_response = (
                db.client.table("options_ranks")
                .select("run_at")
                .eq("underlying_symbol_id", symbol_id)
                .order("run_at", desc=True)
                .limit(1)
                .execute()
            )

            latest = "N/A"
            if latest_response.data:
                latest = latest_response.data[0]["run_at"][11:19]  # HH:MM:SS

            status = "✅" if count > 0 else "❌"
            print(f"{status} {symbol}: {count:,} records (latest run: {latest} UTC)")

        except Exception as e:
            print(f"❌ {symbol}: Error - {e}")

    print(f"\n📊 Total rankings: {total_records:,}")
    return total_records


def verify_options_price_history():
    """Verify options_price_history table has snapshot data."""
    print("\n" + "=" * 80)
    print("VERIFYING: options_price_history (Price Snapshots)")
    print("=" * 80)

    total_records = 0
    cutoff_date = (datetime.now() - timedelta(days=2)).isoformat()

    for symbol in EXPECTED_SYMBOLS:
        try:
            # Get symbol_id
            symbol_response = (
                db.client.table("symbols").select("id").eq("ticker", symbol).single().execute()
            )
            symbol_id = symbol_response.data["id"]

            # Count recent price history records
            response = (
                db.client.table("options_price_history")
                .select("*", count="exact")
                .eq("underlying_symbol_id", symbol_id)
                .gte("snapshot_at", cutoff_date)
                .execute()
            )

            count = response.count or 0
            total_records += count
            status = "✅" if count > 0 else "⚠️ "
            print(f"{status} {symbol}: {count:,} records")

        except Exception as e:
            print(f"❌ {symbol}: Error - {e}")

    print(f"\n📊 Total price history: {total_records:,}")
    return total_records


def main():
    """Run all verification checks."""
    print("\n" + "=" * 80)
    print("SUPABASE OPTIONS DATA VERIFICATION")
    print(f"Snapshot Date: {SNAPSHOT_DATE}")
    print(f"Symbols: {', '.join(EXPECTED_SYMBOLS)}")
    print("=" * 80)

    # Run all checks
    chain_count = verify_options_chain_snapshots()
    historical_count = verify_options_snapshots()
    ranks_count = verify_options_ranks()
    price_history_count = verify_options_price_history()

    # Summary
    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)
    print(f"✅ Chain Snapshots:     {chain_count:,} records")
    print(f"✅ Historical Snapshots: {historical_count:,} records")
    print(f"✅ Rankings:            {ranks_count:,} records")
    print(f"✅ Price History:       {price_history_count:,} records")
    print("=" * 80)

    # Expected counts from workflow logs
    expected_chain = 21_395
    expected_historical = 94_000  # Approximate
    expected_ranks = 21_395

    all_good = True

    if chain_count < expected_chain * 0.95:
        print(f"⚠️  Chain snapshots lower than expected ({expected_chain:,})")
        all_good = False

    if historical_count < 50_000:
        print(f"⚠️  Historical snapshots lower than expected (~{expected_historical:,})")
        all_good = False

    if ranks_count < expected_ranks * 0.95:
        print(f"⚠️  Rankings lower than expected ({expected_ranks:,})")
        all_good = False

    if all_good:
        print("\n🎉 ALL DATA VERIFIED SUCCESSFULLY!")
    else:
        print("\n⚠️  Some data counts are lower than expected")

    return 0 if all_good else 1


if __name__ == "__main__":
    sys.exit(main())
