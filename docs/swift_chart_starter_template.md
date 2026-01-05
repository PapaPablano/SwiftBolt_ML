# Swift Charts Starter Template

A copy-paste ready reference for building candlestick charts with ML forecast overlays using Swift Charts.

---

## Quick Start: Minimal Candlestick Chart

```swift
import SwiftUI
import Charts

struct SimpleCandlestickChart: View {
    let bars: [OHLCBar]

    var body: some View {
        Chart(bars) { bar in
            // Candlestick body
            RectangleMark(
                x: .value("Date", bar.ts),
                yStart: .value("Open", min(bar.open, bar.close)),
                yEnd: .value("Close", max(bar.open, bar.close)),
                width: .ratio(0.6)
            )
            .foregroundStyle(bar.close >= bar.open ? .green : .red)

            // Candlestick wick
            RuleMark(
                x: .value("Date", bar.ts),
                yStart: .value("Low", bar.low),
                yEnd: .value("High", bar.high)
            )
            .foregroundStyle(bar.close >= bar.open ? .green : .red)
            .lineStyle(StrokeStyle(lineWidth: 1))
        }
        .chartYAxis {
            AxisMarks(position: .trailing)
        }
    }
}
```

---

## Data Models

### OHLCBar

```swift
struct OHLCBar: Identifiable, Codable, Equatable {
    var id: Date { ts }

    let ts: Date
    let open: Double
    let high: Double
    let low: Double
    let close: Double
    let volume: Double
}
```

### ForecastPoint

```swift
struct ForecastPoint: Codable, Equatable {
    let ts: Int           // Unix timestamp
    let value: Double     // Predicted price
    let lower: Double     // Lower confidence bound
    let upper: Double     // Upper confidence bound

    var date: Date {
        Date(timeIntervalSince1970: TimeInterval(ts))
    }
}

struct ForecastSeries: Codable, Equatable {
    let horizon: String   // "1d", "5d", etc.
    let points: [ForecastPoint]
}

struct MLSummary: Codable, Equatable {
    let overallLabel: String?  // "bullish", "bearish", "neutral"
    let confidence: Double
    let horizons: [ForecastSeries]
}
```

---

## Index-Based Chart (Even Spacing)

For professional TradingView-style even spacing (ignoring market gaps):

```swift
struct IndexedCandlestickChart: View {
    let bars: [OHLCBar]
    @State private var scrollPosition: Int = 0
    @State private var barsToShow: Int = 100

    private var indexedBars: [(index: Int, bar: OHLCBar)] {
        bars.enumerated().map { (index: $0.offset, bar: $0.element) }
    }

    var body: some View {
        Chart {
            ForEach(indexedBars, id: \.bar.id) { item in
                // Candlestick body
                RectangleMark(
                    x: .value("Index", item.index),
                    yStart: .value("Open", min(item.bar.open, item.bar.close)),
                    yEnd: .value("Close", max(item.bar.open, item.bar.close)),
                    width: .ratio(0.6)
                )
                .foregroundStyle(item.bar.close >= item.bar.open ? .green : .red)

                // Wick
                RuleMark(
                    x: .value("Index", item.index),
                    yStart: .value("Low", item.bar.low),
                    yEnd: .value("High", item.bar.high)
                )
                .foregroundStyle((item.bar.close >= item.bar.open ? Color.green : .red).opacity(0.8))
                .lineStyle(StrokeStyle(lineWidth: 1.5))
            }
        }
        .chartXScale(domain: 0...max(0, bars.count - 1))
        .chartScrollableAxes(.horizontal)
        .chartXVisibleDomain(length: barsToShow)
        .chartScrollPosition(x: $scrollPosition)
        .chartXAxis {
            AxisMarks(values: .automatic(desiredCount: 6)) { value in
                if let index = value.as(Int.self), index >= 0 && index < bars.count {
                    AxisGridLine()
                    AxisTick()
                    AxisValueLabel {
                        Text(formatDate(bars[index].ts))
                            .font(.caption)
                    }
                }
            }
        }
        .chartYAxis {
            AxisMarks(position: .trailing, values: .automatic(desiredCount: 8))
        }
    }

    private func formatDate(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "M/d"
        return formatter.string(from: date)
    }
}
```

---

## Adding Moving Averages

```swift
struct ChartWithIndicators: View {
    let bars: [OHLCBar]
    let sma20: [IndicatorDataPoint]
    let sma50: [IndicatorDataPoint]

    var body: some View {
        Chart {
            // Candlesticks
            ForEach(indexedBars, id: \.bar.id) { item in
                candlestickMarks(index: item.index, bar: item.bar)
            }

            // SMA 20
            ForEach(sma20) { point in
                if let value = point.value, let index = indicatorIndex(for: point.date) {
                    LineMark(
                        x: .value("Index", index),
                        y: .value("SMA20", value)
                    )
                    .foregroundStyle(.blue)
                    .lineStyle(StrokeStyle(lineWidth: 2))
                    .interpolationMethod(.catmullRom)
                }
            }

            // SMA 50
            ForEach(sma50) { point in
                if let value = point.value, let index = indicatorIndex(for: point.date) {
                    LineMark(
                        x: .value("Index", index),
                        y: .value("SMA50", value)
                    )
                    .foregroundStyle(.orange)
                    .lineStyle(StrokeStyle(lineWidth: 2))
                    .interpolationMethod(.catmullRom)
                }
            }
        }
    }

    private func indicatorIndex(for date: Date) -> Int? {
        bars.firstIndex { Calendar.current.isDate($0.ts, equalTo: date, toGranularity: .second) }
    }
}

struct IndicatorDataPoint: Identifiable {
    var id: Date { date }
    let date: Date
    let value: Double?

    init(bar: OHLCBar, value: Double?) {
        self.date = bar.ts
        self.value = value
    }
}
```

---

## ML Forecast Overlay

```swift
@ChartContentBuilder
private func forecastOverlay(_ mlSummary: MLSummary) -> some ChartContent {
    let forecastColor: Color = {
        switch (mlSummary.overallLabel ?? "").lowercased() {
        case "bullish": return .green
        case "bearish": return .red
        default: return .yellow
        }
    }()

    let lastBarIndex = bars.count - 1
    let lastClose = bars.last?.close ?? 0

    // Connection line from last bar to forecast
    if let firstPoint = mlSummary.horizons.first?.points.first {
        LineMark(x: .value("Index", lastBarIndex), y: .value("Price", lastClose))
            .foregroundStyle(forecastColor)
            .lineStyle(StrokeStyle(lineWidth: 2.5, dash: [6, 4]))

        LineMark(x: .value("Index", lastBarIndex + 1), y: .value("Price", firstPoint.value))
            .foregroundStyle(forecastColor)
            .lineStyle(StrokeStyle(lineWidth: 2.5, dash: [6, 4]))
    }

    // Forecast points
    ForEach(mlSummary.horizons, id: \.horizon) { series in
        ForEach(Array(series.points.enumerated()), id: \.offset) { offset, point in
            let forecastIndex = lastBarIndex + offset + 1

            // Main prediction line
            LineMark(
                x: .value("Index", forecastIndex),
                y: .value("Forecast", point.value)
            )
            .foregroundStyle(forecastColor)
            .lineStyle(StrokeStyle(lineWidth: 2.5, dash: [6, 4]))
            .opacity(0.9)

            // Confidence band (shaded area)
            AreaMark(
                x: .value("Index", forecastIndex),
                yStart: .value("Lower", point.lower),
                yEnd: .value("Upper", point.upper)
            )
            .foregroundStyle(forecastColor.opacity(0.15))

            // Upper bound
            LineMark(x: .value("Index", forecastIndex), y: .value("Upper", point.upper))
                .foregroundStyle(forecastColor.opacity(0.4))
                .lineStyle(StrokeStyle(lineWidth: 1.5, dash: [3, 3]))

            // Lower bound
            LineMark(x: .value("Index", forecastIndex), y: .value("Lower", point.lower))
                .foregroundStyle(forecastColor.opacity(0.4))
                .lineStyle(StrokeStyle(lineWidth: 1.5, dash: [3, 3]))
        }
    }

    // Endpoint marker
    if let lastPoint = mlSummary.horizons.last?.points.last {
        PointMark(
            x: .value("Index", lastBarIndex + (mlSummary.horizons.last?.points.count ?? 0)),
            y: .value("Forecast", lastPoint.value)
        )
        .foregroundStyle(forecastColor)
        .symbolSize(60)
    }
}
```

---

## RSI Panel

```swift
struct RSIPanel: View {
    let rsi: [IndicatorDataPoint]
    let visibleRange: ClosedRange<Int>

    var body: some View {
        Chart {
            // Overbought zone
            RectangleMark(
                xStart: .value("Start", visibleRange.lowerBound),
                xEnd: .value("End", visibleRange.upperBound),
                yStart: .value("Low", 70),
                yEnd: .value("High", 100)
            )
            .foregroundStyle(Color.red.opacity(0.08))

            // Oversold zone
            RectangleMark(
                xStart: .value("Start", visibleRange.lowerBound),
                xEnd: .value("End", visibleRange.upperBound),
                yStart: .value("Low", 0),
                yEnd: .value("High", 30)
            )
            .foregroundStyle(Color.green.opacity(0.08))

            // RSI line
            ForEach(rsi) { point in
                if let value = point.value {
                    LineMark(
                        x: .value("Date", point.date),
                        y: .value("RSI", value)
                    )
                    .foregroundStyle(.purple)
                    .lineStyle(StrokeStyle(lineWidth: 2))
                }
            }

            // Reference lines
            RuleMark(y: .value("Overbought", 70))
                .foregroundStyle(.red.opacity(0.5))
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))

            RuleMark(y: .value("Oversold", 30))
                .foregroundStyle(.green.opacity(0.5))
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))

            RuleMark(y: .value("Midline", 50))
                .foregroundStyle(.gray.opacity(0.4))
        }
        .chartYScale(domain: 0...100)
        .chartXAxis(.hidden)
        .frame(height: 100)
    }
}
```

---

## Crosshair Tooltip

```swift
struct ChartWithCrosshair: View {
    let bars: [OHLCBar]
    @State private var selectedBar: OHLCBar?
    @State private var selectedIndex: Int?

    var body: some View {
        Chart { ... }
        .chartOverlay { proxy in
            GeometryReader { geometry in
                Rectangle()
                    .fill(.clear)
                    .contentShape(Rectangle())
                    .onContinuousHover { phase in
                        switch phase {
                        case .active(let location):
                            updateSelection(at: location, proxy: proxy, geometry: geometry)
                        case .ended:
                            selectedBar = nil
                            selectedIndex = nil
                        }
                    }
            }
        }
        .overlay(alignment: .topLeading) {
            if let bar = selectedBar {
                CandlestickTooltip(bar: bar)
                    .padding(8)
            }
        }
    }

    private func updateSelection(at location: CGPoint, proxy: ChartProxy, geometry: GeometryProxy) {
        guard let plotFrame = proxy.plotFrame else { return }
        let xPosition = location.x - geometry[plotFrame].origin.x
        guard let index: Int = proxy.value(atX: xPosition) else { return }

        let clampedIndex = max(0, min(index, bars.count - 1))
        selectedIndex = clampedIndex
        selectedBar = bars[clampedIndex]
    }
}

struct CandlestickTooltip: View {
    let bar: OHLCBar

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(bar.ts, style: .date)
                .font(.caption.bold())
            HStack(spacing: 8) {
                Text("O: \(bar.open, specifier: "%.2f")")
                Text("H: \(bar.high, specifier: "%.2f")")
                Text("L: \(bar.low, specifier: "%.2f")")
                Text("C: \(bar.close, specifier: "%.2f")")
            }
            .font(.caption.monospacedDigit())
        }
        .padding(8)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8))
    }
}
```

---

## Color Palette

```swift
struct ChartColors {
    // Candlesticks
    static let bullish = Color(red: 0.2, green: 0.85, blue: 0.4)
    static let bearish = Color(red: 1.0, green: 0.3, blue: 0.25)

    // Moving Averages
    static let sma20 = Color(red: 0.3, green: 0.7, blue: 1.0)   // Sky blue
    static let sma50 = Color(red: 1.0, green: 0.65, blue: 0.0)  // Orange
    static let sma200 = Color(red: 0.85, green: 0.4, blue: 0.95) // Purple
    static let ema9 = Color(red: 0.0, green: 1.0, blue: 0.75)   // Teal
    static let ema21 = Color(red: 1.0, green: 0.5, blue: 0.7)   // Pink

    // Forecast
    static let forecastBullish = Color(red: 0.3, green: 0.9, blue: 0.5)
    static let forecastBearish = Color(red: 1.0, green: 0.35, blue: 0.3)
    static let forecastNeutral = Color(red: 1.0, green: 0.75, blue: 0.0)

    // Bollinger Bands
    static let bollingerBand = Color(red: 0.7, green: 0.7, blue: 0.85)
    static let bollingerFill = Color(red: 0.6, green: 0.6, blue: 0.75).opacity(0.12)

    // SuperTrend
    static let superTrendBull = Color(red: 0.0, green: 1.0, blue: 0.5)
    static let superTrendBear = Color(red: 1.0, green: 0.25, blue: 0.5)

    // Oscillators
    static let rsi = Color(red: 0.8, green: 0.5, blue: 1.0)
    static let macdLine = Color(red: 0.2, green: 0.85, blue: 1.0)
    static let macdSignal = Color(red: 1.0, green: 0.6, blue: 0.1)
}
```

---

## Technical Indicator Calculations

### SMA (Simple Moving Average)

```swift
static func sma(bars: [OHLCBar], period: Int) -> [Double?] {
    guard bars.count >= period else {
        return Array(repeating: nil, count: bars.count)
    }

    var result: [Double?] = Array(repeating: nil, count: period - 1)

    for i in (period - 1)..<bars.count {
        let sum = bars[(i - period + 1)...i].reduce(0) { $0 + $1.close }
        result.append(sum / Double(period))
    }

    return result
}
```

### EMA (Exponential Moving Average)

```swift
static func ema(bars: [OHLCBar], period: Int) -> [Double?] {
    guard bars.count >= period else {
        return Array(repeating: nil, count: bars.count)
    }

    var result: [Double?] = Array(repeating: nil, count: period - 1)
    let multiplier = 2.0 / Double(period + 1)

    // First EMA is SMA
    let firstSMA = bars[0..<period].reduce(0) { $0 + $1.close } / Double(period)
    result.append(firstSMA)

    // Subsequent EMAs
    for i in period..<bars.count {
        if let prevEMA = result.last ?? nil {
            let ema = (bars[i].close - prevEMA) * multiplier + prevEMA
            result.append(ema)
        }
    }

    return result
}
```

### RSI (Relative Strength Index)

```swift
static func rsi(bars: [OHLCBar], period: Int = 14) -> [Double?] {
    guard bars.count > period else {
        return Array(repeating: nil, count: bars.count)
    }

    var result: [Double?] = [nil]  // First bar has no RSI
    var gains: [Double] = []
    var losses: [Double] = []

    for i in 1..<bars.count {
        let change = bars[i].close - bars[i-1].close
        gains.append(max(0, change))
        losses.append(max(0, -change))

        if i < period {
            result.append(nil)
        } else if i == period {
            let avgGain = gains.reduce(0, +) / Double(period)
            let avgLoss = losses.reduce(0, +) / Double(period)
            let rs = avgLoss == 0 ? 100 : avgGain / avgLoss
            result.append(100 - (100 / (1 + rs)))
        } else {
            let prevRSI = result.last ?? 50
            let avgGain = (gains.suffix(period).reduce(0, +) / Double(period))
            let avgLoss = (losses.suffix(period).reduce(0, +) / Double(period))
            let rs = avgLoss == 0 ? 100 : avgGain / avgLoss
            result.append(100 - (100 / (1 + rs)))
        }
    }

    return result
}
```

---

## Performance Tips

1. **Cache indicator calculations** - Only recalculate when data changes
2. **Filter to visible range** - Don't render off-screen data
3. **Use stable IDs** - Prevent unnecessary view recreations
4. **Native scrolling** - Use `chartScrollableAxes` instead of gestures
5. **Limit data points** - ~500 bars is optimal for Swift Charts

```swift
// Example: Cached indicators
@MainActor
class ChartViewModel: ObservableObject {
    private var _cachedSMA20: [IndicatorDataPoint]?

    var sma20: [IndicatorDataPoint] {
        if let cached = _cachedSMA20 { return cached }
        let result = calculateSMA20()
        _cachedSMA20 = result
        return result
    }

    func invalidateCache() {
        _cachedSMA20 = nil
    }
}
```

---

## Complete Example: Chart with Forecast

```swift
struct TradingChartView: View {
    @StateObject private var viewModel = ChartViewModel()

    var body: some View {
        VStack(spacing: 0) {
            // Header
            ChartHeader(symbol: viewModel.symbol, lastBar: viewModel.bars.last)

            // Main chart
            Chart {
                // Candlesticks
                ForEach(viewModel.indexedBars, id: \.bar.id) { item in
                    candlestickMarks(index: item.index, bar: item.bar)
                }

                // Moving averages
                if viewModel.showSMA20 {
                    indicatorLine(viewModel.sma20, color: ChartColors.sma20)
                }

                // Forecast overlay
                if let mlSummary = viewModel.mlSummary {
                    forecastOverlay(mlSummary)
                }
            }
            .chartScrollableAxes(.horizontal)
            .chartXVisibleDomain(length: viewModel.barsToShow)
            .chartScrollPosition(x: $viewModel.scrollPosition)
            .frame(height: 400)

            // RSI panel
            if viewModel.showRSI {
                Divider()
                RSIPanel(rsi: viewModel.rsi, visibleRange: viewModel.visibleRange)
            }
        }
        .task {
            await viewModel.loadChart()
        }
    }
}
```

---

## References

- [Swift Charts Documentation](https://developer.apple.com/documentation/Charts)
- [SwiftBolt ML AdvancedChartView](../client-macos/SwiftBoltML/Views/AdvancedChartView.swift)
- [SwiftBolt ML ChartViewModel](../client-macos/SwiftBoltML/ViewModels/ChartViewModel.swift)
