"""
Display TabPFN forecast results with full details.

Shows saved forecasts, raw vs adjusted confidence, synthesis/weights, and prediction intervals.

Note: Forecasts are upserted by (symbol_id, timeframe, horizon). The same row is updated
each run, so use run_at (or updated_at) for "when this was generated"; created_at is the
original insert time and does not change on update.
"""
import json
from datetime import datetime, timedelta
from src.data.supabase_db import SupabaseDatabase

db = SupabaseDatabase()

print("=" * 100)
print("TABPFN FORECAST RESULTS - DETAILED VIEW")
print("=" * 100)

# Use run_at for "recent" — upsert updates the same row so created_at stays old
recent_cutoff = (datetime.now() - timedelta(hours=1)).isoformat()

forecasts = (
    db.client.table("ml_forecasts")
    .select("*, symbols!inner(ticker)", count="exact")
    .eq("model_type", "tabpfn")
    .gte("run_at", recent_cutoff)
    .order("run_at", desc=True)
    .execute()
)

if not forecasts.data:
    print("\n⚠ No TabPFN runs in last hour. Checking last 24 hours (by run_at)...")
    recent_cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
    forecasts = (
        db.client.table("ml_forecasts")
        .select("*, symbols!inner(ticker)", count="exact")
        .eq("model_type", "tabpfn")
        .gte("run_at", recent_cutoff)
        .order("run_at", desc=True)
        .execute()
    )

if not forecasts.data:
    print("No TabPFN runs in last 24 hours. Showing latest by run_at...")
    forecasts = (
        db.client.table("ml_forecasts")
        .select("*, symbols!inner(ticker)", count="exact")
        .eq("model_type", "tabpfn")
        .order("run_at", desc=True)
        .limit(100)
        .execute()
    )

if forecasts.data:
    # Group by symbol (ticker from join)
    by_symbol = {}
    for f in forecasts.data:
        ticker = (f.get("symbols") or {}).get("ticker", "UNKNOWN")
        if ticker not in by_symbol:
            by_symbol[ticker] = []
        by_symbol[ticker].append(f)

    for ticker, symbol_forecasts in by_symbol.items():
        print(f"\n{'='*100}")
        print(f"Symbol: {ticker}")
        print(f"{'='*100}")

        horizon_order = {"1d": 1, "5d": 2, "10d": 3, "20d": 4}
        symbol_forecasts.sort(
            key=lambda x: horizon_order.get((x.get("horizon") or "").lower(), 99)
        )

        for f in symbol_forecasts:
            direction = f.get("overall_label") or f.get("direction", "")
            print(f"\n📊 Horizon: {(f.get('horizon') or '').upper()}")
            print(f"   Direction: {str(direction).upper()}")
            print(f"   Final Confidence: {f['confidence']:.1%}")

            fcast_return = f.get("forecast_return", 0) or 0
            print(f"   Forecast Return: {fcast_return:.2%}")

            if f.get("synthesis_data"):
                synth = (
                    json.loads(f["synthesis_data"])
                    if isinstance(f["synthesis_data"], str)
                    else f["synthesis_data"]
                )

                # Raw vs adjusted confidence
                raw_conf = synth.get("raw_confidence")
                if raw_conf is not None:
                    print(f"\n   🔬 TabPFN Raw Output:")
                    print(f"      Raw Confidence: {raw_conf:.1%}")
                if synth.get("tabpfn"):
                    tabpfn_data = synth["tabpfn"]
                    print(f"\n   🔬 TabPFN Raw Output:")
                    print(f"      Raw Confidence: {tabpfn_data.get('confidence', 0):.1%}")
                    print(f"      Raw Return: {tabpfn_data.get('return', 0):.2%}")
                    print(f"      Direction: {tabpfn_data.get('direction', 'N/A')}")

                if synth.get("weights"):
                    weights = synth["weights"]
                    print(f"\n   ⚖️  Model Weights Applied:")
                    for model, weight in weights.items():
                        print(f"      {model}: {weight:.2f}")

                if synth.get("train_samples") is not None:
                    print(f"\n   📈 Training Info:")
                    print(f"      Samples: {synth['train_samples']}")
                    print(f"      Training Time: {synth.get('train_time_sec', 0):.2f}s")
                    if synth.get("mae") is not None:
                        print(f"      MAE: {synth['mae']:.4f}")
                    if synth.get("r2") is not None:
                        print(f"      R²: {synth['r2']:.3f}")
                    if synth.get("dir_acc") is not None:
                        print(f"      Direction Accuracy: {synth['dir_acc']:.1%}")

            if f.get("points"):
                points = (
                    json.loads(f["points"])
                    if isinstance(f["points"], str)
                    else f["points"]
                )
                if isinstance(points, dict) and points.get("q10") is not None and points.get("q90") is not None:
                    med = points.get("median", fcast_return)
                    print(f"\n   📏 Prediction Interval (80%):")
                    print(f"      10th %ile: {points['q10']:.4f} ({points['q10']*100:+.2f}%)")
                    print(f"      Median:    {med:.4f} ({med*100:+.2f}%)")
                    print(f"      90th %ile: {points['q90']:.4f} ({points['q90']*100:+.2f}%)")
                    print(f"      Width:     {points.get('interval_width', 0):.4f}")

            if f.get("quality_score") is not None:
                print(f"\n   ✅ Quality Score: {f['quality_score']:.2f}/1.0")

            if f.get("quality_issues"):
                issues = (
                    json.loads(f["quality_issues"])
                    if isinstance(f["quality_issues"], str)
                    else f["quality_issues"]
                )
                if issues:
                    print(f"\n   ⚠️  Quality Issues:")
                    if isinstance(issues, dict):
                        for issue, details in issues.items():
                            print(f"      - {issue}: {details}")
                    elif isinstance(issues, list):
                        for item in issues:
                            msg = item.get("message", item.get("type", str(item)))
                            print(f"      - {msg}")
                    else:
                        print(f"      - {issues}")

            run_at = f.get("run_at") or f.get("created_at")
            print(f"\n   🕐 Generated (run_at): {run_at}")
            if f.get("created_at") and str(f.get("run_at", "")) != str(f.get("created_at", "")):
                print(f"   📌 Row created_at: {f['created_at']} (unchanged by upsert)")
            print(f"   {'-'*96}")

    print(f"\n{'='*100}")
    print(f"Total forecasts: {len(forecasts.data)}")
    print(f"{'='*100}")
else:
    print("\n✗ No TabPFN forecasts found")
