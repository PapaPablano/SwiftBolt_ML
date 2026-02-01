"""
Compare TabPFN vs XGBoost forecasts side-by-side.

Uses run_at for "recent" (same as display_tabpfn_results) since forecasts
are upserted by (symbol_id, timeframe, horizon).
"""
import sys
from datetime import datetime, timedelta
from src.data.supabase_db import SupabaseDatabase

db = SupabaseDatabase()

print("=" * 120)
print("MODEL COMPARISON: TabPFN vs Ensemble (XGBoost/ARIMA-GARCH+LSTM)")
print("=" * 120)

# Get recent forecasts for both models (last 24 hours by run_at)
recent_cutoff = (datetime.now() - timedelta(hours=24)).isoformat()

forecasts = (
    db.client.table("ml_forecasts")
    .select("*, symbols!inner(ticker)")
    .in_("model_type", ["xgboost", "tabpfn"])
    .gte("run_at", recent_cutoff)
    .order("run_at", desc=True)
    .execute()
)

if not forecasts.data:
    print("\n⚠ No forecasts in last 24 hours. Checking all recent forecasts...")
    forecasts = (
        db.client.table("ml_forecasts")
        .select("*, symbols!inner(ticker)")
        .in_("model_type", ["xgboost", "tabpfn"])
        .order("run_at", desc=True)
        .limit(50)
        .execute()
    )

if not forecasts.data:
    print("✗ No forecasts found at all!")
    sys.exit(1)

# Group by (symbol, horizon); keep one row per model (latest run_at wins)
comparisons = {}
for f in forecasts.data:
    key = (f["symbols"]["ticker"], f["horizon"])
    if key not in comparisons:
        comparisons[key] = {}
    if f["model_type"] not in comparisons[key]:
        comparisons[key][f["model_type"]] = f

def _dir(row):
    return (row.get("overall_label") or row.get("direction") or "").upper()

# Display comparison table
print(
    f"\n{'Symbol':<8} {'Horizon':<8} {'TabPFN Dir':<12} {'TabPFN Conf':<13} {'TabPFN Return':<14} "
    f"{'Ensemble Dir':<12} {'Ensemble Conf':<13} {'Ensemble Return':<14} {'Match':<8}"
)
print("-" * 120)

matches = 0
total = 0
tabpfn_only = 0
xgboost_only = 0

for (ticker, horizon), models in sorted(comparisons.items()):
    if "tabpfn" in models and "xgboost" in models:
        t = models["tabpfn"]
        x = models["xgboost"]
        t_dir = _dir(t)
        x_dir = _dir(x)

        match = "✓ Yes" if t_dir == x_dir else "✗ No"
        if t_dir == x_dir:
            matches += 1
        total += 1

        t_return = t.get("forecast_return") or 0
        x_return = x.get("forecast_return") or 0

        print(
            f"{ticker:<8} {horizon:<8} "
            f"{t_dir:<12} {t['confidence']:>11.1%}  {t_return:>12.2%}  "
            f"{x_dir:<12} {x['confidence']:>11.1%}  {x_return:>12.2%}  "
            f"{match:<8}"
        )

    elif "tabpfn" in models:
        tabpfn_only += 1
        t = models["tabpfn"]
        t_dir = _dir(t)
        t_return = t.get("forecast_return") or 0
        print(
            f"{ticker:<8} {horizon:<8} "
            f"{t_dir:<12} {t['confidence']:>11.1%}  {t_return:>12.2%}  "
            f"{'---':<12} {'---':>11}  {'---':>12}  {'TabPFN only':<8}"
        )

    elif "xgboost" in models:
        xgboost_only += 1
        x = models["xgboost"]
        x_dir = _dir(x)
        x_return = x.get("forecast_return") or 0
        print(
            f"{ticker:<8} {horizon:<8} "
            f"{'---':<12} {'---':>11}  {'---':>12}  "
            f"{x_dir:<12} {x['confidence']:>11.1%}  {x_return:>12.2%}  "
            f"{'Ensemble only':<8}"
        )

# Summary
print("-" * 120)
print(f"\n📊 SUMMARY:")
print(f"   Forecasts with both models: {total}")
if total > 0:
    print(f"   Agreement rate: {matches}/{total} = {matches/total*100:.1f}%")
print(f"   TabPFN only: {tabpfn_only}")
print(f"   Ensemble only: {xgboost_only}")
print("=" * 120)

# Show detailed disagreements
if total > 0:
    print("\n🔍 DETAILED DISAGREEMENTS:")
    print("-" * 120)
    disagreements = []
    for (ticker, horizon), models in sorted(comparisons.items()):
        if "tabpfn" in models and "xgboost" in models:
            t = models["tabpfn"]
            x = models["xgboost"]
            if _dir(t) != _dir(x):
                disagreements.append(
                    {"ticker": ticker, "horizon": horizon, "tabpfn": t, "xgboost": x}
                )

    if disagreements:
        for d in disagreements:
            print(f"\n{d['ticker']} - {d['horizon']}:")
            t = d["tabpfn"]
            x = d["xgboost"]
            print(
                f"  TabPFN:  {_dir(t):8} (conf: {t['confidence']:.1%}, return: {t.get('forecast_return') or 0:+.2%})"
            )
            print(
                f"  Ensemble: {_dir(x):8} (conf: {x['confidence']:.1%}, return: {x.get('forecast_return') or 0:+.2%})"
            )
            t_ret = t.get("forecast_return") or 0
            x_ret = x.get("forecast_return") or 0
            diff = abs(t_ret - x_ret)
            print(f"  Return difference: {diff:.2%}")
    else:
        print("✓ All forecasts agree!")
    print("-" * 120)
