#!/usr/bin/env python3
"""
Compare metrics between baseline and unified forecast implementations.

Usage:
    python scripts/compare_metrics.py \
        metrics/baseline/forecast_job_metrics.json \
        metrics/unified/unified_forecast_metrics.json
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


def load_metrics(filepath: str) -> Dict[str, Any]:
    """Load metrics from JSON file."""
    path = Path(filepath)
    if not path.exists():
        print(f"Error: Metrics file not found: {filepath}")
        sys.exit(1)
    
    with open(path, 'r') as f:
        return json.load(f)


def calculate_cache_hit_rate(metrics: Dict) -> float:
    """Calculate feature cache hit rate."""
    hits = metrics.get('feature_cache_hits', 0)
    misses = metrics.get('feature_cache_misses', 0)
    total = hits + misses
    return (hits / total * 100) if total > 0 else 0.0


def calculate_avg_processing_time(metrics: Dict) -> float:
    """Calculate average processing time per symbol."""
    times = metrics.get('forecast_times', [])
    return sum(times) / len(times) if times else 0.0


def analyze_weight_sources(metrics: Dict) -> Dict[str, int]:
    """Analyze weight source distribution."""
    weight_sources = metrics.get('weight_sources', {})
    if isinstance(weight_sources, dict):
        return weight_sources
    
    # If weight_source is a list (from baseline), count occurrences
    weight_list = metrics.get('weight_source', [])
    if isinstance(weight_list, list):
        counts = {}
        for entry in weight_list:
            source = entry.get('source', 'unknown')
            counts[source] = counts.get(source, 0) + 1
        return counts
    
    return {}


def print_comparison_report(baseline: Dict, unified: Dict):
    """Print detailed comparison report."""
    print("=" * 80)
    print("FORECAST METRICS COMPARISON REPORT")
    print("=" * 80)
    print()
    
    # Execution times
    print("📊 EXECUTION SUMMARY")
    print("-" * 80)
    baseline_start = baseline.get('start_time', 'N/A')
    baseline_end = baseline.get('end_time', 'N/A')
    unified_start = unified.get('start_time', 'N/A')
    unified_end = unified.get('end_time', 'N/A')
    
    print(f"Baseline: {baseline_start} → {baseline_end}")
    print(f"Unified:  {unified_start} → {unified_end}")
    print()
    
    # Symbols processed
    print("📈 SYMBOLS PROCESSED")
    print("-" * 80)
    baseline_symbols = baseline.get('symbols_processed', 0)
    unified_symbols = unified.get('symbols_processed', 0)
    
    print(f"Baseline: {baseline_symbols} symbols")
    print(f"Unified:  {unified_symbols} symbols")
    
    if baseline_symbols == unified_symbols:
        print("✅ Same number of symbols processed")
    else:
        diff = unified_symbols - baseline_symbols
        print(f"⚠️  Difference: {diff:+d} symbols")
    print()
    
    # Cache performance
    print("💾 FEATURE CACHE PERFORMANCE")
    print("-" * 80)
    baseline_hit_rate = calculate_cache_hit_rate(baseline)
    unified_hit_rate = calculate_cache_hit_rate(unified)
    
    baseline_hits = baseline.get('feature_cache_hits', 0)
    baseline_misses = baseline.get('feature_cache_misses', 0)
    unified_hits = unified.get('feature_cache_hits', 0)
    unified_misses = unified.get('feature_cache_misses', 0)
    
    print(f"Baseline: {baseline_hits} hits / {baseline_misses} misses ({baseline_hit_rate:.1f}% hit rate)")
    print(f"Unified:  {unified_hits} hits / {unified_misses} misses ({unified_hit_rate:.1f}% hit rate)")
    
    if unified_hit_rate > baseline_hit_rate:
        improvement = unified_hit_rate - baseline_hit_rate
        print(f"✅ Cache hit rate improved by {improvement:.1f} percentage points")
    elif unified_hit_rate < baseline_hit_rate:
        degradation = baseline_hit_rate - unified_hit_rate
        print(f"⚠️  Cache hit rate decreased by {degradation:.1f} percentage points")
    else:
        print("➡️  Cache hit rate unchanged")
    print()
    
    # Processing time
    print("⏱️  PROCESSING TIME")
    print("-" * 80)
    baseline_avg = calculate_avg_processing_time(baseline)
    unified_avg = calculate_avg_processing_time(unified)
    
    baseline_total = sum(baseline.get('forecast_times', []))
    unified_total = sum(unified.get('forecast_times', []))
    
    print(f"Baseline: {baseline_total:.2f}s total, {baseline_avg:.2f}s avg per symbol")
    print(f"Unified:  {unified_total:.2f}s total, {unified_avg:.2f}s avg per symbol")
    
    if unified_avg < baseline_avg:
        speedup = baseline_avg / unified_avg if unified_avg > 0 else 0
        savings = baseline_avg - unified_avg
        print(f"✅ Unified is {speedup:.2f}x faster ({savings:.2f}s saved per symbol)")
    elif unified_avg > baseline_avg:
        slowdown = unified_avg / baseline_avg if baseline_avg > 0 else 0
        overhead = unified_avg - baseline_avg
        print(f"⚠️  Unified is {slowdown:.2f}x slower ({overhead:.2f}s overhead per symbol)")
    else:
        print("➡️  Processing time unchanged")
    print()
    
    # Weight sources
    print("⚖️  WEIGHT SOURCE DISTRIBUTION")
    print("-" * 80)
    baseline_sources = analyze_weight_sources(baseline)
    unified_sources = analyze_weight_sources(unified)
    
    print("Baseline:")
    for source, count in sorted(baseline_sources.items()):
        pct = (count / baseline_symbols * 100) if baseline_symbols > 0 else 0
        print(f"  {source}: {count} ({pct:.1f}%)")
    
    print("\nUnified:")
    for source, count in sorted(unified_sources.items()):
        pct = (count / unified_symbols * 100) if unified_symbols > 0 else 0
        print(f"  {source}: {count} ({pct:.1f}%)")
    print()
    
    # Database writes
    print("💾 DATABASE WRITES")
    print("-" * 80)
    baseline_writes = baseline.get('db_writes', 0)
    unified_writes = unified.get('db_writes', 0)
    
    print(f"Baseline: {baseline_writes} writes")
    print(f"Unified:  {unified_writes} writes")
    
    if unified_writes < baseline_writes:
        reduction = baseline_writes - unified_writes
        pct = (reduction / baseline_writes * 100) if baseline_writes > 0 else 0
        print(f"✅ Reduced by {reduction} writes ({pct:.1f}%)")
    elif unified_writes > baseline_writes:
        increase = unified_writes - baseline_writes
        pct = (increase / baseline_writes * 100) if baseline_writes > 0 else 0
        print(f"⚠️  Increased by {increase} writes ({pct:.1f}%)")
    else:
        print("➡️  Same number of writes")
    print()
    
    # Errors
    print("❌ ERRORS")
    print("-" * 80)
    baseline_errors = baseline.get('errors', [])
    unified_errors = unified.get('errors', [])
    
    print(f"Baseline: {len(baseline_errors)} errors")
    print(f"Unified:  {len(unified_errors)} errors")
    
    if len(unified_errors) < len(baseline_errors):
        improvement = len(baseline_errors) - len(unified_errors)
        print(f"✅ Reduced errors by {improvement}")
    elif len(unified_errors) > len(baseline_errors):
        increase = len(unified_errors) - len(baseline_errors)
        print(f"⚠️  Increased errors by {increase}")
    else:
        print("➡️  Same error count")
    
    if unified_errors:
        print("\nUnified errors:")
        for error in unified_errors[:5]:  # Show first 5
            symbol = error.get('symbol', 'unknown')
            msg = error.get('error', 'unknown error')
            print(f"  - {symbol}: {msg[:80]}")
        if len(unified_errors) > 5:
            print(f"  ... and {len(unified_errors) - 5} more")
    print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    improvements = []
    regressions = []
    
    if unified_hit_rate > baseline_hit_rate:
        improvements.append(f"Cache hit rate +{unified_hit_rate - baseline_hit_rate:.1f}%")
    elif unified_hit_rate < baseline_hit_rate:
        regressions.append(f"Cache hit rate -{baseline_hit_rate - unified_hit_rate:.1f}%")
    
    if unified_avg < baseline_avg:
        speedup = baseline_avg / unified_avg if unified_avg > 0 else 0
        improvements.append(f"Processing speed {speedup:.2f}x faster")
    elif unified_avg > baseline_avg:
        slowdown = unified_avg / baseline_avg if baseline_avg > 0 else 0
        regressions.append(f"Processing speed {slowdown:.2f}x slower")
    
    if unified_writes < baseline_writes:
        reduction_pct = ((baseline_writes - unified_writes) / baseline_writes * 100) if baseline_writes > 0 else 0
        improvements.append(f"DB writes -{reduction_pct:.1f}%")
    elif unified_writes > baseline_writes:
        increase_pct = ((unified_writes - baseline_writes) / baseline_writes * 100) if baseline_writes > 0 else 0
        regressions.append(f"DB writes +{increase_pct:.1f}%")
    
    if len(unified_errors) < len(baseline_errors):
        improvements.append(f"Errors -{len(baseline_errors) - len(unified_errors)}")
    elif len(unified_errors) > len(baseline_errors):
        regressions.append(f"Errors +{len(unified_errors) - len(baseline_errors)}")
    
    if improvements:
        print("✅ Improvements:")
        for imp in improvements:
            print(f"   • {imp}")
    
    if regressions:
        print("\n⚠️  Regressions:")
        for reg in regressions:
            print(f"   • {reg}")
    
    if not improvements and not regressions:
        print("➡️  No significant changes detected")
    
    print()
    print("=" * 80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Compare metrics between baseline and unified implementations'
    )
    parser.add_argument('baseline', help='Path to baseline metrics JSON')
    parser.add_argument('unified', help='Path to unified metrics JSON')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    args = parser.parse_args()
    
    # Load metrics
    baseline = load_metrics(args.baseline)
    unified = load_metrics(args.unified)
    
    if args.json:
        # Output comparison as JSON
        comparison = {
            'baseline': {
                'symbols_processed': baseline.get('symbols_processed', 0),
                'cache_hit_rate': calculate_cache_hit_rate(baseline),
                'avg_processing_time': calculate_avg_processing_time(baseline),
                'db_writes': baseline.get('db_writes', 0),
                'errors': len(baseline.get('errors', [])),
            },
            'unified': {
                'symbols_processed': unified.get('symbols_processed', 0),
                'cache_hit_rate': calculate_cache_hit_rate(unified),
                'avg_processing_time': calculate_avg_processing_time(unified),
                'db_writes': unified.get('db_writes', 0),
                'errors': len(unified.get('errors', [])),
            }
        }
        print(json.dumps(comparison, indent=2))
    else:
        # Print human-readable report
        print_comparison_report(baseline, unified)


if __name__ == '__main__':
    main()
