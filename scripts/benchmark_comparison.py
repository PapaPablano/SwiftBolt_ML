#!/usr/bin/env python3
"""
Compare performance benchmarks between baseline and unified implementations.

Usage:
    python scripts/benchmark_comparison.py baseline_output.log unified_output.log
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


def parse_log_file(filepath: str) -> Dict:
    """Parse log file and extract performance metrics."""
    path = Path(filepath)
    if not path.exists():
        print(f"Error: Log file not found: {filepath}")
        sys.exit(1)
    
    with open(path, 'r') as f:
        content = f.read()
    
    metrics = {
        'symbols_processed': 0,
        'symbols_failed': 0,
        'processing_times': [],
        'cache_hits': [],
        'cache_misses': [],
        'errors': [],
    }
    
    # Extract symbols processed/failed from summary
    match = re.search(r'Processed:\s*(\d+)', content)
    if match:
        metrics['symbols_processed'] = int(match.group(1))
    
    match = re.search(r'Failed:\s*(\d+)', content)
    if match:
        metrics['symbols_failed'] = int(match.group(1))
    
    # Extract processing times per symbol
    for match in re.finditer(r'Processing ([A-Z]+)\.\.\.', content):
        symbol = match.group(1)
        # Try to find corresponding completion time
        # This is approximate - actual timing would need instrumentation
    
    # Extract cache hits/misses
    for line in content.split('\n'):
        if 'Cache hit' in line or 'cache HIT' in line:
            metrics['cache_hits'].append(line)
        elif 'Cache miss' in line or 'cache MISS' in line:
            metrics['cache_misses'].append(line)
        elif 'ERROR' in line or 'Error' in line:
            metrics['errors'].append(line.strip())
    
    return metrics


def print_benchmark_report(baseline_file: str, unified_file: str):
    """Print benchmark comparison report."""
    print("=" * 80)
    print("PERFORMANCE BENCHMARK COMPARISON")
    print("=" * 80)
    print()
    
    print("📊 INPUT FILES")
    print("-" * 80)
    print(f"Baseline: {baseline_file}")
    print(f"Unified:  {unified_file}")
    print()
    
    # Parse logs
    baseline = parse_log_file(baseline_file)
    unified = parse_log_file(unified_file)
    
    # Symbols processed
    print("📈 PROCESSING SUMMARY")
    print("-" * 80)
    print(f"Baseline: {baseline['symbols_processed']} processed, {baseline['symbols_failed']} failed")
    print(f"Unified:  {unified['symbols_processed']} processed, {unified['symbols_failed']} failed")
    
    if baseline['symbols_processed'] == unified['symbols_processed']:
        print("✅ Same number of symbols processed")
    else:
        diff = unified['symbols_processed'] - baseline['symbols_processed']
        print(f"{'✅' if diff > 0 else '⚠️ '} Difference: {diff:+d} symbols")
    print()
    
    # Cache performance
    print("💾 CACHE PERFORMANCE")
    print("-" * 80)
    baseline_hits = len(baseline['cache_hits'])
    baseline_misses = len(baseline['cache_misses'])
    unified_hits = len(unified['cache_hits'])
    unified_misses = len(unified['cache_misses'])
    
    baseline_total = baseline_hits + baseline_misses
    unified_total = unified_hits + unified_misses
    
    baseline_rate = (baseline_hits / baseline_total * 100) if baseline_total > 0 else 0
    unified_rate = (unified_hits / unified_total * 100) if unified_total > 0 else 0
    
    print(f"Baseline: {baseline_hits}/{baseline_total} hits ({baseline_rate:.1f}%)")
    print(f"Unified:  {unified_hits}/{unified_total} hits ({unified_rate:.1f}%)")
    
    if unified_rate > baseline_rate:
        improvement = unified_rate - baseline_rate
        print(f"✅ Cache efficiency improved by {improvement:.1f} percentage points")
    elif unified_rate < baseline_rate:
        degradation = baseline_rate - unified_rate
        print(f"⚠️  Cache efficiency decreased by {degradation:.1f} percentage points")
    else:
        print("➡️  Cache efficiency unchanged")
    print()
    
    # Errors
    print("❌ ERROR ANALYSIS")
    print("-" * 80)
    print(f"Baseline: {len(baseline['errors'])} errors")
    print(f"Unified:  {len(unified['errors'])} errors")
    
    if len(unified['errors']) < len(baseline['errors']):
        improvement = len(baseline['errors']) - len(unified['errors'])
        print(f"✅ Reduced errors by {improvement}")
    elif len(unified['errors']) > len(baseline['errors']):
        increase = len(unified['errors']) - len(baseline['errors'])
        print(f"⚠️  Increased errors by {increase}")
    else:
        print("➡️  Same error count")
    
    if unified['errors']:
        print("\nSample unified errors (first 5):")
        for error in unified['errors'][:5]:
            print(f"  {error[:120]}")
        if len(unified['errors']) > 5:
            print(f"  ... and {len(unified['errors']) - 5} more")
    print()
    
    # Overall assessment
    print("=" * 80)
    print("ASSESSMENT")
    print("=" * 80)
    
    score = 0
    
    # Processing success
    if unified['symbols_processed'] >= baseline['symbols_processed']:
        score += 1
        print("✅ Processed same or more symbols")
    else:
        print("⚠️  Processed fewer symbols")
    
    # Cache performance
    if unified_rate >= baseline_rate + 5:  # 5% improvement threshold
        score += 1
        print("✅ Significantly improved cache performance")
    elif unified_rate >= baseline_rate:
        score += 1
        print("✅ Maintained or slightly improved cache performance")
    else:
        print("⚠️  Cache performance regression")
    
    # Error reduction
    if len(unified['errors']) <= len(baseline['errors']):
        score += 1
        print("✅ Maintained or reduced error rate")
    else:
        print("⚠️  Increased error rate")
    
    print()
    print(f"Overall Score: {score}/3")
    
    if score == 3:
        print("🎉 EXCELLENT: Unified implementation meets all performance criteria")
    elif score == 2:
        print("✅ GOOD: Unified implementation is acceptable with minor regressions")
    elif score == 1:
        print("⚠️  FAIR: Unified implementation has notable regressions")
    else:
        print("❌ POOR: Unified implementation has significant regressions")
    
    print("=" * 80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Compare performance between baseline and unified implementations'
    )
    parser.add_argument('baseline', help='Path to baseline output log')
    parser.add_argument('unified', help='Path to unified output log')
    
    args = parser.parse_args()
    
    print_benchmark_report(args.baseline, args.unified)


if __name__ == '__main__':
    main()
