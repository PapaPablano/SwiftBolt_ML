# Chart Indicators Fix - Volume and SuperTrend

## Issue Summary
Sub-indicators (volume) and SuperTrend were not displaying on the chart. The user reported that these indicators were working in a previous chart implementation but are missing in the current WebChart view.

## Root Cause

1. **Volume sub-panel missing**: No volume panel was defined in the HTML or chart.js
2. **SuperTrend coloring issue**: SuperTrend was being rendered as a single-color line via `setIndicator()`, which doesn't support dynamic coloring based on trend direction (bullish=green, bearish=red)
3. **Missing JavaScript methods**: No `setVolume()` or `setSuperTrend()` methods in chart.js
4. **Missing Swift bridge support**: ChartBridge didn't have commands for volume or trend-aware SuperTrend

## Changes Made

### 1. HTML (`index.html`)
Added volume sub-panel:
```html
<div id="volume-panel" class="sub-panel">
    <div class="sub-panel-label">Volume</div>
</div>
```

### 2. JavaScript (`chart.js`)

**Added volume panel configuration:**
```javascript
volume: { id: 'volume-panel', height: 120 }
```

**Added volume colors:**
```javascript
volumeUp: '#26a69a80',    // Semi-transparent green
volumeDown: '#ef535080',  // Semi-transparent red
```

**Added `setVolume()` method:**
- Renders volume as histogram bars
- Colors bars based on price direction (green=up, red=down)
- Syncs with main chart time scale

**Added `setSuperTrend()` method:**
- Splits SuperTrend data into bullish and bearish segments
- Renders two separate line series with different colors
- Bullish segments: green (`#00ff80`)
- Bearish segments: red (`#ff4080`)
- Creates visual gaps between trend changes

### 3. Swift Bridge (`ChartBridge.swift`)

**Added new command cases:**
```swift
case setVolume(data: [VolumeDataPoint])
case setSuperTrend(data: [LightweightDataPoint], trendData: [LightweightDataPoint])
```

**Added `VolumeDataPoint` struct:**
```swift
struct VolumeDataPoint: Encodable {
    let time: Int
    let value: Double
    let direction: String  // "up" or "down"
    let color: String?
}
```

**Added convenience methods:**
- `setVolume(bars:)`: Converts OHLC bars to volume data with direction
- `setSuperTrend(data:trend:)`: Sends SuperTrend line and trend direction data

### 4. WebChartView (`WebChartView.swift`)

**Updated SuperTrend rendering:**
```swift
// Old: Single-color line
bridge.setIndicator(id: "supertrend", name: "SuperTrend", data: ..., color: "#00e676")

// New: Trend-aware coloring
bridge.setSuperTrend(data: parent.viewModel.superTrendLine, trend: parent.viewModel.superTrendTrend)
```

**Added volume rendering:**
```swift
if config.showVolume {
    bridge.setVolume(bars: data.bars)
} else {
    bridge.hidePanel("volume")
}
```

## How It Works

### Volume Display
1. Swift passes OHLC bars to `bridge.setVolume(bars:)`
2. Bridge determines direction by comparing close vs open
3. JavaScript receives volume data with direction flags
4. Histogram series renders bars with appropriate colors
5. Volume panel appears below main chart

### SuperTrend Display
1. Swift passes SuperTrend line values and trend direction (1=bull, -1=bear)
2. JavaScript splits data into bullish and bearish segments
3. Two separate line series are created:
   - `supertrend_bull`: Green line for bullish periods
   - `supertrend_bear`: Red line for bearish periods
4. Null values create visual gaps at trend changes
5. Lines overlay on main price chart

## Testing Checklist
- [ ] Volume bars display below main chart
- [ ] Volume bars colored correctly (green=up, red=down)
- [ ] SuperTrend shows green line during bullish trends
- [ ] SuperTrend shows red line during bearish trends
- [ ] Visual gap appears at trend reversals
- [ ] Volume panel can be toggled on/off via settings
- [ ] SuperTrend can be toggled on/off via settings
- [ ] All other indicators still work (RSI, MACD, etc.)
- [ ] Time scales sync across all panels

## Files Modified
- `client-macos/SwiftBoltML/Resources/WebChart/index.html`
- `client-macos/SwiftBoltML/Resources/WebChart/chart.js`
- `client-macos/SwiftBoltML/Services/ChartBridge.swift`
- `client-macos/SwiftBoltML/Views/WebChartView.swift`

## Configuration
Volume display is controlled by `IndicatorConfig.showVolume` (default: true)
SuperTrend display is controlled by `IndicatorConfig.showSuperTrend` (default: true)

## Visual Result
- **Volume**: Histogram bars at bottom, color-coded by price direction
- **SuperTrend**: Dynamic green/red line on main chart following price trend
- **Sub-indicators**: RSI, MACD, Stochastic, KDJ, ADX, ATR all functional
