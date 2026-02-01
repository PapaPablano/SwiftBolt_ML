"""
Display TabPFN forecasts in a clean format.
"""
import json
from datetime import datetime, timedelta
from src.data.supabase_db import SupabaseDatabase

db = SupabaseDatabase()

print("=" * 80)
print("TABPFN FORECAST RESULTS")
print("=" * 80)

# Get all symbols with recent TabPFN forecasts
recent_cutoff = (datetime.now() - timedelta(hours=1)).isoformat()

forecasts = db.client.table('ml_forecasts') \
    .select('*, symbols!inner(ticker)') \
    .eq('model_type', 'tabpfn') \
    .gte('created_at', recent_cutoff) \
    .order('created_at', desc=True) \
    .execute()

if not forecasts.data:
    print("\n⚠ No recent TabPFN forecasts found (last 1 hour)")
    print("Trying last 24 hours...")
    recent_cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
    forecasts = db.client.table('ml_forecasts') \
        .select('*, symbols!inner(ticker)') \
        .eq('model_type', 'tabpfn') \
        .gte('created_at', recent_cutoff) \
        .order('created_at', desc=True) \
        .execute()

if not forecasts.data:
    print("No TabPFN in last 24 hours. Showing all TabPFN forecasts...")
    forecasts = db.client.table('ml_forecasts') \
        .select('*, symbols!inner(ticker)') \
        .eq('model_type', 'tabpfn') \
        .order('created_at', desc=True) \
        .limit(100) \
        .execute()

if forecasts.data:
    # Group by symbol
    by_symbol = {}
    for f in forecasts.data:
        ticker = f['symbols']['ticker']
        if ticker not in by_symbol:
            by_symbol[ticker] = []
        by_symbol[ticker].append(f)

    for ticker, symbol_forecasts in by_symbol.items():
        print(f"\n{'='*80}")
        print(f"Symbol: {ticker}")
        print(f"{'='*80}")

        # Sort by horizon
        horizon_order = {'1d': 1, '5d': 2, '10d': 3, '20d': 4}
        symbol_forecasts.sort(key=lambda x: horizon_order.get(x['horizon'].lower(), 99))

        for f in symbol_forecasts:
            print(f"\n  Horizon: {f['horizon'].upper()}")
            direction = f.get('direction') or f.get('overall_label', '')
            print(f"  Direction: {str(direction).upper()}")
            print(f"  Confidence: {f['confidence']:.1%}")

            if f.get('forecast_return'):
                print(f"  Forecast Return: {f['forecast_return']:.2%}")

            if f.get('points'):
                points = json.loads(f['points']) if isinstance(f['points'], str) else f['points']
                if isinstance(points, dict) and points.get('q10') is not None and points.get('q90') is not None:
                    print(f"  Prediction Interval:")
                    print(f"    10th percentile: {points['q10']:.4f} ({points['q10']*100:.2f}%)")
                    print(f"    Median: {points.get('median', f.get('forecast_return', 0)):.4f}")
                    print(f"    90th percentile: {points['q90']:.4f} ({points['q90']*100:.2f}%)")
                    print(f"    Interval Width: {points.get('interval_width', 0):.4f}")
                elif isinstance(points, (list, tuple)) and len(points) >= 2:
                    # TabPFN-style: list of {ts, type, lower, price, upper, value}
                    target_pts = [p for p in points if isinstance(p, dict) and p.get('type') == 'target']
                    if target_pts:
                        t = target_pts[0]
                        print(f"  Prediction Interval: [{t.get('lower', 0):.2f}, {t.get('upper', 0):.2f}] (price: {t.get('price', t.get('value', 0)):.2f})")
                    else:
                        print(f"  Prediction Interval (raw): {points[:5]}{'...' if len(points) > 5 else ''}")

            if f.get('quality_score'):
                print(f"  Quality Score: {f['quality_score']:.2f}/1.0")

            if f.get('quality_issues'):
                issues = json.loads(f['quality_issues']) if isinstance(f['quality_issues'], str) else f['quality_issues']
                if issues:
                    if isinstance(issues, dict):
                        print(f"  ⚠ Quality Issues: {', '.join(issues.keys())}")
                    elif isinstance(issues, list) and issues and isinstance(issues[0], dict):
                        msgs = [x.get('message', x.get('type', str(x))) for x in issues]
                        print(f"  ⚠ Quality Issues: {'; '.join(msgs)}")
                    else:
                        print(f"  ⚠ Quality Issues: {issues}")

            if f.get('synthesis_data'):
                synth = json.loads(f['synthesis_data']) if isinstance(f['synthesis_data'], str) else f['synthesis_data']
                if synth.get('train_time_sec'):
                    print(f"  Training Time: {synth['train_time_sec']:.2f}s")
                if synth.get('train_samples'):
                    print(f"  Training Samples: {synth['train_samples']}")

            print(f"  Created: {f['created_at']}")
            print(f"  {'-'*76}")

    print(f"\n{'='*80}")
    print(f"Total forecasts: {len(forecasts.data)}")
    print(f"{'='*80}")
else:
    print("\n✗ No TabPFN forecasts found in database")
    print("\nDebugging info:")

    # Check if any forecasts exist
    all_forecasts = db.client.table('ml_forecasts') \
        .select('model_type') \
        .limit(10) \
        .execute()

    if all_forecasts.data:
        print(f"  ✓ Found {len(all_forecasts.data)} total forecasts")
        model_types = set(f['model_type'] for f in all_forecasts.data if f.get('model_type'))
        print(f"  Model types in DB: {model_types}")
    else:
        print("  ✗ No forecasts in database at all")
