"""
Check for fresh TabPFN forecasts in ml_forecasts.
Run from ml/ directory: python check_tabpfn.py
"""
from datetime import datetime, timedelta

from src.data.supabase_db import SupabaseDatabase

db = SupabaseDatabase()
recent_cutoff = (datetime.now() - timedelta(minutes=10)).isoformat()

forecasts = (
    db.client.table("ml_forecasts")
    .select("*, symbols!inner(ticker)")
    .eq("model_type", "tabpfn")
    .gte("created_at", recent_cutoff)
    .order("created_at", desc=True)
    .execute()
)

if forecasts.data:
    print("✓ FRESH TABPFN FORECASTS (last 10 min):")
    print("=" * 80)
    for f in forecasts.data:
        ticker = f["symbols"]["ticker"]
        direction = f.get("direction") or f.get("overall_label", "")
        print(
            f"{ticker:6} {f['horizon']:4} {direction:8} "
            f"conf={f['confidence']:5.1%} return={f.get('forecast_return', 0):6.2%} "
            f"created={f['created_at']}"
        )
else:
    print("✗ No fresh TabPFN forecasts in last 10 minutes")
    # Try 60 min in case job ran earlier
    hour_cutoff = (datetime.now() - timedelta(minutes=60)).isoformat()
    hourly = (
        db.client.table("ml_forecasts")
        .select("*, symbols!inner(ticker)")
        .eq("model_type", "tabpfn")
        .gte("created_at", hour_cutoff)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )
    if hourly.data:
        print(f"\n✓ TabPFN forecasts in last 60 min ({len(hourly.data)}):")
        for f in hourly.data:
            ticker = f["symbols"]["ticker"]
            direction = f.get("direction") or f.get("overall_label", "")
            print(
                f"  {ticker:6} {f['horizon']:4} {direction:8} "
                f"conf={f['confidence']:5.1%} {f['created_at']}"
            )
    else:
        print("\nDebug: recent forecasts (any model_type):")
        recent = (
            db.client.table("ml_forecasts")
            .select("model_type, horizon, overall_label, confidence, created_at")
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        if recent.data:
            for r in recent.data:
                direction = r.get("overall_label", r.get("direction", "?"))
                print(
                    f"  {r.get('model_type', '?'):10} {r.get('horizon', '?'):4} "
                    f"{direction:8} {r.get('confidence', 0):5.1%} {r['created_at']}"
                )
            print(
                "\nIf model_type is not 'tabpfn', the save path may not be setting model_type."
            )
        else:
            print("  No forecasts in database.")
