# Pivot Levels - Quick Reference

## Most Common Usage Patterns

### 1. Basic Multi-Period Detection
```swift
let results = OptimizedPivotDetector.detectMultiPeriodPivots(
    bars: myBars,
    periods: [5, 25, 50, 100]
)
```

### 2. Using Presets
```swift
// Balanced (default)
PivotPeriodManager.shared.resetToPreset(.balanced)

// Aggressive
PivotPeriodManager.shared.resetToPreset(.aggressive)

// Conservative
PivotPeriodManager.shared.resetToPreset(.conservative)

// Get enabled periods
let periods = PivotPeriodManager.shared.enabledPeriods
```

### 3. Analyzing Metrics
```swift
let metrics = PivotStatisticalMetrics.analyzeMetrics(
    levels: pivotLevels,
    bars: bars,
    detectedPivots: (highs: highs, lows: lows)
)
print("Overall Strength: \(metrics.overallStrength * 100)%")
```

### 4. Finding Strong Zones
```swift
let zones = PivotStatisticalMetrics.findConfluenceZones(levels)
// Shows where multiple periods converge
for zone in zones {
    print("Strong zone at \(zone.price) - \(zone.strength) levels")
}
```

### 5. Chart Drawing
```swift
let path = PivotChartDrawing.generateLevelPath(
    level: 100.0,
    chartWidth: 800,
    startIndex: 0,
    endIndex: 200,
    extendMode: .both,
    yScale: { CGFloat($0) },
    xScale: { CGFloat($0) }
)
```

## Key Files Location

| Component | File | Purpose |
|-----------|------|---------|
| Period Management | `PivotPeriodManager.swift` | Presets & configuration |
| Detection (Optimized) | `OptimizedPivotDetector.swift` | Fast multi-period detection |
| Statistics | `PivotStatisticalMetrics.swift` | Pivot analysis & metrics |
| Chart Utilities | `PivotChartDrawing.swift` | Visualization helpers |
| Tests | `PivotDetectionTests.swift` | 25+ unit tests |
| Original | `PivotLevelsIndicator.swift` | Unchanged base class |
| Models | `PivotLevel.swift` | Data structures |

## Period Presets Summary

### Conservative (2 periods)
- **Periods**: 50, 100
- **Use When**: Stable markets, want less noise
- **Characteristics**: Fewer signals, high reliability

### Balanced (4 periods) ⭐ DEFAULT
- **Periods**: 5, 25, 50, 100
- **Use When**: Most market conditions
- **Characteristics**: Good mix, reasonable signal frequency

### Aggressive (6 periods)
- **Periods**: 3, 5, 13, 25, 50, 100
- **Use When**: Trending markets, want early signals
- **Characteristics**: More signals, higher sensitivity

## Metric Definitions

### Strength (0-1)
How often price bounces off levels
- 0.8-1.0: Very Strong
- 0.6-0.8: Strong
- 0.4-0.6: Moderate
- 0.2-0.4: Weak

### Frequency (0-1)
Density of pivots relative to bars
- Higher = More pivots detected

### Clustering (0-1)
How tightly pivots are grouped
- 1.0 = All pivots at same distance
- 0.0 = Very irregular spacing

### Recency (0-1)
How recent are the latest pivots
- 1.0 = All recent pivots
- 0.0 = No recent pivots

### Consistency (0-1)
Regularity of pivot spacing
- 1.0 = Perfectly regular
- 0.0 = Highly irregular

## Performance Metrics

### Detection Speed
- Single period: ~1-5ms (for 500 bars)
- Batch (5 periods): ~10-20ms
- Cache hit: <1ms

### Memory
- Cache: ~50KB for 100 entries
- Per period config: ~50 bytes
- Detection arrays: ~1KB per 100 bars

## Common Customizations

### Custom Period
```swift
let custom = PeriodConfig(
    length: 35,
    style: .solid,
    extend: .both,
    enabled: true,
    label: "Custom35"
)
PivotPeriodManager.shared.addPeriod(custom)
```

### Filter by Price Range
```swift
let inRange = OptimizedPivotDetector.filterByPriceRange(
    pivots: pivots,
    minPrice: 95,
    maxPrice: 105
)
```

### Get Recent Pivots
```swift
let recent = OptimizedPivotDetector.getRecentPivots(from: results)
// [period: (high: DetectedPivot?, low: DetectedPivot?)]
```

## Troubleshooting Checklist

- [ ] Period values > 2 and < bar count / 2?
- [ ] Cache cleared after major data changes?
- [ ] Using batch detection for multiple periods?
- [ ] Enough bars (>period*2)?
- [ ] Metrics calculated with complete data set?

## Integration Checklist

- [ ] Import new services in your view controller
- [ ] Use PivotPeriodManager for period selection
- [ ] Cache detection results when possible
- [ ] Calculate metrics only when needed
- [ ] Use OptimizedPivotDetector for multi-period
- [ ] Handle empty pivot arrays gracefully

## Python Usage

```python
from polynomial_sr_chart import create_flux_chart

fig = create_flux_chart(
    df=ohlc_data,
    regressor=sr_regressor,
    pivot_levels=[
        {'period': 5, 'levelHigh': 105, 'levelLow': 95},
        {'period': 25, 'levelHigh': 107, 'levelLow': 93},
    ],
    analytics={
        'overall_strength': 0.75,
        'pivot_count': 12,
        'confidence': 0.82
    },
    save_path='chart.png'
)
```

## Performance Tips

1. **Batch Detection** instead of sequential
2. **Enable Caching** for stable data
3. **Limit Periods** to 4-6 for real-time
4. **Filter Results** by price/time when possible
5. **Pre-calculate** metrics for historical analysis
6. **Clear Cache** after major updates

## Testing

```swift
// Run unit tests
cmd + U in Xcode

// Or command line
xcodebuild test -scheme SwiftBoltML

// 25+ tests covering:
// - Detection accuracy
// - Optimization correctness
// - Caching effectiveness
// - Edge cases
// - Integration pipeline
```

## Documentation Files

- **PIVOT_ENHANCEMENTS_GUIDE.md** - Comprehensive documentation
- **PIVOT_QUICK_REFERENCE.md** - This file
- **Source files** - Inline comments and docstrings

## Common Questions

**Q: Should I use Balanced or Aggressive?**
A: Start with Balanced (default), switch to Aggressive only in trending markets.

**Q: How many periods should I use?**
A: 4-6 is optimal. More than 10 may cause performance issues.

**Q: When should I clear the cache?**
A: After major data reloads (e.g., symbol change), not on every tick.

**Q: Can I combine multiple presets?**
A: Yes, enable/disable individual periods and customize as needed.

**Q: What's the difference between Strength and Frequency?**
A: Strength = how effective pivots are, Frequency = how many pivots exist.
