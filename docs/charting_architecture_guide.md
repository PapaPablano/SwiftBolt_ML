# SwiftBolt ML - Charting Architecture Guide

## Overview

This document outlines the charting architecture for the SwiftBolt ML platform, a macOS SwiftUI application for stock/futures/options analysis with ML-powered forecasts.

**Two Viable Options:**
- **Option A (Current):** Swift Charts - Native SwiftUI, simpler integration
- **Option B (Alternative):** Lightweight Charts via WKWebView - TradingView UX, better performance

---

## Architecture Decision

### Four Approaches Evaluated

| Approach | Performance | Native Integration | ML Forecast Support | Best For |
|----------|-------------|-------------------|-------------------|----------|
| **Swift Charts** | 10k points | Full SwiftUI | Medium (custom) | **Current implementation** |
| **Lightweight Charts** | 100k+ points | WKWebView bridge | Medium (custom) | **TradingView UX** |
| SciChart iOS | 500k+ points | Full integration | Built-in | Enterprise trading |
| Custom Metal | Unlimited | Full control | Custom | High-frequency only |

### Why Swift Charts

1. **Native to macOS 14+**: Zero interop overhead, full SwiftUI integration
2. **Candlestick support**: Custom `CandlestickMark` with OHLC data
3. **Automatic scaling**: Axes adapt to data range
4. **Built-in animation**: Smooth transitions on data updates
5. **Forecast overlay-ready**: Dashed lines for bands on top of candles
6. **No external dependencies**: Reduces app size and build complexity
7. **Performance**: ~500 historical candles + 10 forecast points = well within limits

### When to Consider SciChart

Upgrade to SciChart only if:
- >10k visible historical candles
- Real-time updates >100 ticks/second
- Need pre-built technical indicators (RSI, MACD, Bollinger Bands)
- Professional trading app for institutional clients

**Cost**: $499-$2,999/year (includes Metal rendering)

---

## Option B: TradingView Lightweight Charts (WKWebView)

An alternative approach for TradingView-style UX is to bundle **Lightweight Charts** (free, Apache 2.0) inside a `WKWebView` with a Swift↔JS message bridge.

### Comparison: Swift Charts vs Lightweight Charts

| Feature | Swift Charts (Option A) | Lightweight Charts (Option B) |
|---------|------------------------|------------------------------|
| **Rendering** | Native SwiftUI | HTML5 Canvas via WKWebView |
| **Performance** | ~10k points | ~100k+ points |
| **TradingView UX** | Custom implementation | Built-in (same library TV uses) |
| **Drawing Tools** | Must implement | Plugin ecosystem available |
| **Indicator Support** | Custom calculations | Same custom approach |
| **Dependencies** | None (Apple framework) | JS bundle (~45KB gzipped) |
| **Cost** | Free | Free (Apache 2.0, attribution required) |
| **Platform** | macOS 14+/iOS 16+ | Any WKWebView-capable platform |

### Lightweight Charts Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    SwiftUI View                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │            WebChartView (WKWebView)             │   │
│  │  ┌─────────────────────────────────────────┐   │   │
│  │  │          Lightweight Charts (JS)        │   │   │
│  │  │  • Candlestick series                   │   │   │
│  │  │  • Line series (indicators, forecast)   │   │   │
│  │  │  • Custom markers (signals)             │   │   │
│  │  └─────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
         ↑                              ↓
    JS → Swift                    Swift → JS
  (WKScriptMessageHandler)    (evaluateJavaScript)
         │                              │
         └──── ChartBridge.swift ───────┘
```

### File Structure (Option B)

```
client-macos/SwiftBoltML/
├── Resources/
│   └── WebChart/
│       ├── index.html           # Chart container + JS loader
│       ├── chart.js             # Chart API + command handlers
│       └── lightweight-charts.min.js  # Vendored library
├── Views/
│   └── WebChartView.swift       # SwiftUI wrapper for WKWebView
└── Services/
    └── ChartBridge.swift        # Swift↔JS message bridge
```

### Implementation Phases

#### Phase 1: Bundle Lightweight Charts (0.5 day)
- Vendor `lightweight-charts.min.js` locally (offline support)
- Add attribution notice (required by Apache 2.0 license)
- Create `index.html` with chart container

#### Phase 2: Build JS Command API (0.5-1 day)
```javascript
// chart.js
window.chartApi = {
  chart: null,
  series: {},

  apply: (cmd) => {
    switch (cmd.type) {
      case 'init':
        this.chart = LightweightCharts.createChart(container, cmd.options);
        break;
      case 'setCandles':
        this.series.candles = this.chart.addCandlestickSeries();
        this.series.candles.setData(cmd.data);
        break;
      case 'setLine':
        const line = this.chart.addLineSeries(cmd.options);
        line.setData(cmd.data);
        this.series[cmd.id] = line;
        break;
      case 'setMarkers':
        this.series[cmd.seriesId]?.setMarkers(cmd.markers);
        break;
    }
  }
};

// Signal ready to Swift
window.webkit.messageHandlers.bridge.postMessage({ type: 'ready' });
```

#### Phase 3: Build Swift↔JS Bridge (1 day)
```swift
import WebKit

final class ChartBridge: NSObject, WKScriptMessageHandler {
    weak var webView: WKWebView?
    private var isReady = false
    private var pendingCommands: [String] = []

    func userContentController(_ controller: WKUserContentController,
                               didReceive message: WKScriptMessage) {
        guard let dict = message.body as? [String: Any],
              let type = dict["type"] as? String else { return }

        switch type {
        case "ready":
            isReady = true
            flushPendingCommands()
        case "crosshair":
            // Handle crosshair move events
            break
        case "visibleRange":
            // Handle pan/zoom for lazy loading
            break
        }
    }

    func send(command: ChartCommand) {
        let json = try! JSONEncoder().encode(command)
        let jsonString = String(data: json, encoding: .utf8)!
        let js = "window.chartApi.apply(\(jsonString))"

        if isReady {
            webView?.evaluateJavaScript(js)
        } else {
            pendingCommands.append(js)
        }
    }

    private func flushPendingCommands() {
        pendingCommands.forEach { webView?.evaluateJavaScript($0) }
        pendingCommands.removeAll()
    }
}
```

#### Phase 4: SwiftUI Wrapper (0.5 day)
```swift
import SwiftUI
import WebKit

struct WebChartView: NSViewRepresentable {
    @ObservedObject var viewModel: ChartViewModel
    let bridge = ChartBridge()

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.userContentController.add(bridge, name: "bridge")

        let webView = WKWebView(frame: .zero, configuration: config)
        bridge.webView = webView

        // Load bundled HTML
        if let url = Bundle.main.url(forResource: "index",
                                      withExtension: "html",
                                      subdirectory: "WebChart") {
            webView.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())
        }

        return webView
    }

    func updateNSView(_ webView: WKWebView, context: Context) {
        // Send data updates when viewModel changes
        if let bars = viewModel.chartData?.bars {
            bridge.send(command: .setCandles(bars.map { $0.toLightweightFormat() }))
        }
    }
}
```

#### Phase 5: Data Mapping + Overlays (1-2 days)
```swift
// Map OHLCBar to Lightweight Charts format
extension OHLCBar {
    func toLightweightFormat() -> [String: Any] {
        [
            "time": Int(ts.timeIntervalSince1970),
            "open": open,
            "high": high,
            "low": low,
            "close": close
        ]
    }
}

// Map forecast to line series
extension ForecastSeries {
    func toLightweightFormat() -> [[String: Any]] {
        points.map { [
            "time": $0.ts,
            "value": $0.value
        ]}
    }
}
```

### Pros & Cons

#### Pros
- **TradingView-identical UX**: Same library powers TradingView charts
- **Better performance**: Canvas-based rendering handles 100k+ points
- **Drawing tools ready**: Plugins available for trendlines, Fibonacci, etc.
- **Responsive**: Handles resize, themes, touch events natively
- **Free**: Apache 2.0 license (attribution required)

#### Cons
- **WebView overhead**: Slight latency for JS bridge communication
- **Debugging complexity**: Two runtime environments (Swift + JS)
- **Memory**: WKWebView has higher baseline memory
- **SwiftUI integration**: Less seamless than native Charts
- **Attribution requirement**: Must display TradingView link in UI

### When to Choose Option B

Consider Lightweight Charts when:
- You want exact TradingView-style UX
- Drawing tools are a priority
- Performance with large datasets matters
- You're already familiar with web charting

### Attribution Requirement

Per the Apache 2.0 license, you must include:
1. The NOTICE file contents
2. A visible link to TradingView somewhere in your app/site

Example footer:
```
Charts powered by TradingView Lightweight Charts
```

---

## Current Implementation (Option A: Swift Charts)

### File Structure

```
client-macos/SwiftBoltML/
├── Views/
│   ├── ChartView.swift              # Main chart container
│   ├── AdvancedChartView.swift      # Core chart rendering (2200+ lines)
│   ├── PriceChartView.swift         # Simplified price chart
│   ├── SuperTrendChartView.swift    # SuperTrend AI panel
│   └── IndicatorPanelViews.swift    # MACD, RSI, Stochastic panels
├── ViewModels/
│   └── ChartViewModel.swift         # Chart state & indicator calculations
├── Models/
│   ├── ChartResponse.swift          # API response models
│   ├── OHLCBar.swift                # Candlestick data model
│   └── MLDashboardModels.swift      # ML forecast models
└── Services/
    ├── TechnicalIndicators.swift    # Indicator calculations
    └── SuperTrendAIIndicator.swift  # AI-powered SuperTrend
```

### Key Components

#### 1. AdvancedChartView

The main chart view (~2200 lines) handles:

- **Candlestick rendering** using custom `ChartContentBuilder`
- **Moving averages**: SMA(20, 50, 200), EMA(9, 21)
- **Oscillators**: RSI, MACD, Stochastic, KDJ, ADX
- **Trend indicators**: SuperTrend, SuperTrend AI, Bollinger Bands
- **Support/Resistance**: Pivot Levels, Polynomial S&R, Logistic S&R
- **ML forecast overlay**: Confidence bands with dashed lines
- **Pan/zoom**: Native `chartScrollableAxes` with button controls

#### 2. ChartViewModel

Manages chart state with:

- Indicator caching for performance
- Live quote updates (60-second polling)
- API integration for chart data
- S&R indicator recalculation

#### 3. ML Forecast Integration

Forecasts are rendered via `forecastOverlay(_:)`:

```swift
@ChartContentBuilder
private func forecastOverlay(_ mlSummary: MLSummary) -> some ChartContent {
    // Forecast line (main prediction)
    LineMark(...)
        .foregroundStyle(forecastColor)
        .lineStyle(StrokeStyle(lineWidth: 2.5, dash: [6, 4]))

    // Upper/lower confidence bands
    AreaMark(...)
        .foregroundStyle(forecastColor.opacity(0.15))
}
```

---

## Data Flow

```
Supabase Edge Function (chart endpoint)
    ↓
Returns: { symbol, timeframe, bars: [OHLCBar], mlSummary: MLSummary }
    ↓
ChartViewModel
    ├─ Stores raw bar data
    ├─ Calculates technical indicators (cached)
    ├─ Triggers S&R indicator recalculation
    └─ Updates published properties
    ↓
ChartView (SwiftUI)
    └─ AdvancedChartView
        ├─ Renders candlesticks
        ├─ Overlays indicators
        ├─ Draws forecast bands
        └─ Handles user interaction
```

---

## Models

### OHLCBar

```swift
struct OHLCBar: Codable, Identifiable, Equatable {
    let ts: Date          // Timestamp
    let open: Double
    let high: Double
    let low: Double
    let close: Double
    let volume: Double
}
```

### MLSummary

```swift
struct MLSummary: Codable, Equatable {
    let overallLabel: String?     // "bullish", "bearish", "neutral"
    let confidence: Double
    let horizons: [ForecastSeries]
    let srLevels: SRLevels?
    let ensembleType: String?     // "RF+GB" or "Enhanced5"
    let modelAgreement: Double?
}

struct ForecastSeries: Codable, Equatable {
    let horizon: String           // "1d", "3d", "5d", etc.
    let points: [ForecastPoint]
}

struct ForecastPoint: Codable, Equatable {
    let ts: Int                   // Unix timestamp
    let value: Double             // Predicted price
    let lower: Double             // Lower confidence bound
    let upper: Double             // Upper confidence bound
}
```

---

## Indicator Configuration

Users can toggle indicators via `IndicatorConfig`:

```swift
struct IndicatorConfig {
    // Moving Averages
    var showSMA20, showSMA50, showSMA200: Bool
    var showEMA9, showEMA21: Bool

    // Oscillators
    var showRSI, showMACD, showStochastic, showKDJ: Bool

    // Trend & Volatility
    var showADX, showSuperTrend, showBollingerBands, showATR: Bool

    // SuperTrend AI
    var showSuperTrendAIPanel, showTrendZones: Bool
    var showSignalMarkers, showConfidenceBadges: Bool

    // Support & Resistance
    var showPivotLevels, showPolynomialSR, showLogisticSR: Bool

    // Display
    var showVolume: Bool
}
```

---

## Color Palette

Defined in `ChartColors` struct for consistency:

```swift
struct ChartColors {
    // Candlesticks
    static let bullish = Color(red: 0.2, green: 0.85, blue: 0.4)
    static let bearish = Color(red: 1.0, green: 0.3, blue: 0.25)

    // Moving Averages
    static let sma20 = Color(red: 0.3, green: 0.7, blue: 1.0)   // Sky blue
    static let sma50 = Color(red: 1.0, green: 0.65, blue: 0.0)  // Orange
    static let ema9 = Color(red: 0.0, green: 1.0, blue: 0.75)   // Teal

    // Forecast
    static let forecastBullish = Color(red: 0.3, green: 0.9, blue: 0.5)
    static let forecastBearish = Color(red: 1.0, green: 0.35, blue: 0.3)
    static let forecastNeutral = Color(red: 1.0, green: 0.75, blue: 0.0)

    // SuperTrend
    static let superTrendBull = Color(red: 0.0, green: 1.0, blue: 0.5)
    static let superTrendBear = Color(red: 1.0, green: 0.25, blue: 0.5)
}
```

---

## Performance Optimizations

### 1. Indicator Caching

Indicators are computed once and cached until data changes:

```swift
private var _cachedSMA20: [IndicatorDataPoint]?

var sma20: [IndicatorDataPoint] {
    if let cached = _cachedSMA20 { return cached }
    guard !bars.isEmpty else { return [] }
    let values = TechnicalIndicators.sma(bars: bars, period: 20)
    let result = zip(bars, values).map { IndicatorDataPoint(bar: $0, value: $1) }
    _cachedSMA20 = result
    return result
}
```

### 2. Visible Range Filtering

Only process data within the visible range:

```swift
private var visibleBars: [(index: Int, bar: OHLCBar)] {
    let startIdx = max(0, scrollPosition)
    let endIdx = min(bars.count - 1, scrollPosition + barsToShow - 1)
    return indexedBars.filter { $0.index >= startIdx && $0.index <= endIdx }
}
```

### 3. Native Scrolling

Use Swift Charts' built-in scrolling instead of manual gestures:

```swift
Chart { ... }
    .chartScrollableAxes(.horizontal)
    .chartXVisibleDomain(length: barsToShow)
    .chartScrollPosition(x: $scrollPosition)
```

### 4. View Identity

Use stable IDs to prevent unnecessary redraws:

```swift
AdvancedChartView(...)
    .id("advanced-chart-\(symbol)-\(bars.count)-\(bars.first?.ts.timeIntervalSince1970 ?? 0)")
```

---

## Forecast Rendering

### Connection to Historical Data

The forecast connects seamlessly from the last historical bar:

```swift
// Draw connection line from last bar to first forecast point
if let firstPoint = firstHorizon.points.first {
    LineMark(x: .value("Index", lastBarIndex), y: .value("Price", lastClose))
    LineMark(x: .value("Index", lastBarIndex + 1), y: .value("Price", firstPoint.value))
}
```

### Confidence Bands

Upper and lower bounds rendered with semi-transparent fill:

```swift
// Shaded area between confidence bands
AreaMark(
    x: .value("Index", forecastIndex),
    yStart: .value("Lower", point.lower),
    yEnd: .value("Upper", point.upper)
)
.foregroundStyle(forecastColor.opacity(0.15))
```

---

## API Contract

### Chart Endpoint

```
GET /functions/v1/chart?symbol=AAPL&timeframe=d1
```

Response:
```json
{
  "symbol": "AAPL",
  "assetType": "stock",
  "timeframe": "d1",
  "bars": [...],
  "mlSummary": {
    "overallLabel": "bullish",
    "confidence": 0.82,
    "horizons": [
      {
        "horizon": "5d",
        "points": [
          {"ts": 1704326400, "value": 195.50, "lower": 192.0, "upper": 199.0}
        ]
      }
    ],
    "srLevels": {"support": 188.50, "resistance": 201.25}
  }
}
```

---

## Future Enhancements

### Planned Features

1. **WebSocket Live Updates**: Real-time price streaming during market hours
2. **Drawing Tools**: Trendlines, Fibonacci retracements
3. **Multi-Chart Layout**: Side-by-side symbol comparison
4. **Alert Annotations**: Visual markers for price alerts
5. **Export Functionality**: Chart image export for sharing

### Performance Monitoring

Track these metrics:
- Chart render time (target: <16ms for 60fps)
- Indicator calculation time
- Memory usage with large datasets
- Scroll performance (frames dropped)

---

## References

### Swift Charts (Option A)
- [Swift Charts Documentation](https://developer.apple.com/documentation/Charts)
- [Mastering Charts in SwiftUI - Custom Marks](https://swiftwithmajid.com/2023/01/26/mastering-charts-in-swiftui-custom-marks/)

### Lightweight Charts (Option B)
- [Lightweight Charts GitHub](https://github.com/tradingview/lightweight-charts)
- [Lightweight Charts Documentation](https://tradingview.github.io/lightweight-charts/docs)
- [WKScriptMessageHandler (Apple Docs)](https://developer.apple.com/documentation/webkit/wkscriptmessagehandler)
- [LightweightChartsIOS Wrapper](https://github.com/tradingview/LightweightChartsIOS)

### Enterprise Options
- [SciChart iOS Stock Charts](https://www.scichart.com/ios-stock-charts/)
