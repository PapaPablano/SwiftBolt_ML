import SwiftUI
import Charts

struct AdvancedChartView: View {
    let bars: [OHLCBar]
    let timeframe: String
    let sma20: [IndicatorDataPoint]
    let sma50: [IndicatorDataPoint]
    let ema9: [IndicatorDataPoint]
    let ema21: [IndicatorDataPoint]
    let rsi: [IndicatorDataPoint]
    let config: IndicatorConfig

    @State private var selectedBar: OHLCBar?

    // Filter bars to only show regular market hours for intraday timeframes
    private var filteredBars: [OHLCBar] {
        // Only filter for intraday timeframes
        guard timeframe == "m15" || timeframe == "h1" || timeframe == "h4" else {
            return bars
        }

        return bars.filter { bar in
            let calendar = Calendar.current
            let components = calendar.dateComponents(in: TimeZone(identifier: "America/New_York")!, from: bar.ts)

            guard let hour = components.hour, let minute = components.minute else {
                return true // Keep if we can't determine time
            }

            // Market hours: 9:30 AM - 4:00 PM ET
            let minutesSinceMidnight = hour * 60 + minute
            let marketOpen = 9 * 60 + 30  // 9:30 AM
            let marketClose = 16 * 60     // 4:00 PM

            return minutesSinceMidnight >= marketOpen && minutesSinceMidnight < marketClose
        }
    }

    var body: some View {
        print("[DEBUG] 🟡 AdvancedChartView.body rendering with \(bars.count) bars (filtered to \(filteredBars.count))")

        return VStack(spacing: 0) {
            // Main price chart with indicators
            priceChartView
                .frame(height: config.showRSI ? 400 : 500)
                .id("price-\(filteredBars.count)-\(filteredBars.first?.ts.timeIntervalSince1970 ?? 0)")

            if config.showRSI {
                Divider()
                rsiChartView
                    .frame(height: 120)
                    .id("rsi-\(rsi.count)")
            }

            if config.showVolume {
                Divider()
                volumeChartView
                    .frame(height: 100)
                    .id("volume-\(filteredBars.count)")
            }
        }
        .id("advanced-chart-\(filteredBars.count)-\(filteredBars.first?.ts.timeIntervalSince1970 ?? 0)")
    }

    // MARK: - Price Chart

    private var priceChartView: some View {
        Chart {
            // Candlesticks
            ForEach(filteredBars) { bar in
                candlestickMarks(for: bar)
            }

            // Moving Average Overlays
            if config.showSMA20 {
                indicatorLine(sma20, color: .blue, label: "SMA(20)")
            }
            if config.showSMA50 {
                indicatorLine(sma50, color: .orange, label: "SMA(50)")
            }
            if config.showEMA9 {
                indicatorLine(ema9, color: .purple, label: "EMA(9)")
            }
            if config.showEMA21 {
                indicatorLine(ema21, color: .pink, label: "EMA(21)")
            }

            // Selection indicator
            if let selected = selectedBar {
                RuleMark(x: .value("Date", selected.ts))
                    .foregroundStyle(.blue.opacity(0.3))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))
            }
        }
        .chartYScale(domain: priceRange)
        .chartXAxis {
            AxisMarks(values: xAxisStride) { value in
                AxisGridLine()
                AxisTick()
                AxisValueLabel(format: xAxisFormat)
            }
        }
        .chartYAxis {
            AxisMarks(position: .trailing, values: .automatic(desiredCount: 8)) { value in
                AxisGridLine()
                AxisTick()
                AxisValueLabel {
                    if let price = value.as(Double.self) {
                        Text(formatPrice(price))
                            .font(.caption.monospacedDigit())
                    }
                }
            }
        }
        .chartLegend(position: .top, alignment: .leading) {
            legendView
        }
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

    // MARK: - RSI Chart

    private var rsiChartView: some View {
        Chart {
            // RSI line
            ForEach(rsi) { point in
                if let value = point.value {
                    LineMark(
                        x: .value("Date", point.date),
                        y: .value("RSI", value)
                    )
                    .foregroundStyle(.purple)
                    .interpolationMethod(.catmullRom)
                }
            }

            // Overbought line (70)
            RuleMark(y: .value("Overbought", 70))
                .foregroundStyle(.red.opacity(0.3))
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))

            // Oversold line (30)
            RuleMark(y: .value("Oversold", 30))
                .foregroundStyle(.green.opacity(0.3))
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))

            // Midline (50)
            RuleMark(y: .value("Midline", 50))
                .foregroundStyle(.gray.opacity(0.2))

            // Selection indicator
            if let selected = selectedBar {
                RuleMark(x: .value("Date", selected.ts))
                    .foregroundStyle(.blue.opacity(0.3))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))
            }
        }
        .chartYScale(domain: 0...100)
        .chartXAxis(.hidden)
        .chartYAxis {
            AxisMarks(position: .trailing, values: [30, 50, 70]) { value in
                AxisGridLine()
                AxisValueLabel()
            }
        }
        .chartLegend(position: .top, alignment: .leading) {
            HStack(spacing: 8) {
                Label("RSI(14)", systemImage: "waveform.path.ecg")
                    .font(.caption)
                    .foregroundStyle(.purple)
                Spacer()
                if let latestRSI = rsi.last?.value {
                    Text(String(format: "%.1f", latestRSI))
                        .font(.caption.bold().monospacedDigit())
                        .foregroundStyle(rsiColor(latestRSI))
                }
            }
            .padding(.horizontal, 8)
        }
    }

    // MARK: - Volume Chart

    private var volumeChartView: some View {
        Chart(filteredBars) { bar in
            BarMark(
                x: .value("Date", bar.ts),
                y: .value("Volume", bar.volume)
            )
            .foregroundStyle(bar.close >= bar.open ? Color.green.opacity(0.5) : Color.red.opacity(0.5))
        }
        .chartXAxis(.hidden)
        .chartYAxis {
            AxisMarks(position: .trailing, values: .automatic(desiredCount: 3)) { value in
                AxisGridLine()
                AxisValueLabel {
                    if let volume = value.as(Double.self) {
                        Text(formatVolume(volume))
                            .font(.caption2)
                    }
                }
            }
        }
        .chartLegend(position: .top, alignment: .leading) {
            Label("Volume", systemImage: "chart.bar.fill")
                .font(.caption)
                .foregroundStyle(.secondary)
                .padding(.horizontal, 8)
        }
    }

    // MARK: - Helper Views

    @ChartContentBuilder
    private func candlestickMarks(for bar: OHLCBar) -> some ChartContent {
        // Candlestick body
        RectangleMark(
            x: .value("Date", bar.ts),
            yStart: .value("Open", min(bar.open, bar.close)),
            yEnd: .value("Close", max(bar.open, bar.close)),
            width: .ratio(0.6)
        )
        .foregroundStyle(bar.close >= bar.open ? Color.green : Color.red)
        .opacity(bar.ts == selectedBar?.ts ? 1.0 : 0.8)

        // Candlestick wick
        RuleMark(
            x: .value("Date", bar.ts),
            yStart: .value("Low", bar.low),
            yEnd: .value("High", bar.high)
        )
        .foregroundStyle(bar.close >= bar.open ? Color.green.opacity(0.8) : Color.red.opacity(0.8))
        .lineStyle(StrokeStyle(lineWidth: 1.5))
    }

    @ChartContentBuilder
    private func indicatorLine(_ data: [IndicatorDataPoint], color: Color, label: String) -> some ChartContent {
        ForEach(data) { point in
            if let value = point.value {
                LineMark(
                    x: .value("Date", point.date),
                    y: .value(label, value)
                )
                .foregroundStyle(color)
                .lineStyle(StrokeStyle(lineWidth: 2))
                .interpolationMethod(.catmullRom)
            }
        }
    }

    private var legendView: some View {
        HStack(spacing: 12) {
            if config.showSMA20 {
                LegendItem(color: .blue, label: "SMA(20)", value: sma20.last?.value)
            }
            if config.showSMA50 {
                LegendItem(color: .orange, label: "SMA(50)", value: sma50.last?.value)
            }
            if config.showEMA9 {
                LegendItem(color: .purple, label: "EMA(9)", value: ema9.last?.value)
            }
            if config.showEMA21 {
                LegendItem(color: .pink, label: "EMA(21)", value: ema21.last?.value)
            }
        }
        .padding(.horizontal, 8)
    }

    // MARK: - X-Axis Configuration

    private var xAxisStride: AxisMarkValues {
        switch timeframe {
        case "m15":
            // For 15-minute bars, show every 2 hours (8 bars)
            return .stride(by: .hour, count: 2)
        case "h1":
            // For 1-hour bars, show every 6 hours
            return .stride(by: .hour, count: 6)
        case "h4":
            // For 4-hour bars, show every day
            return .stride(by: .day, count: 1)
        case "d1":
            // For daily bars, show every week (adaptive)
            return .stride(by: .day, count: max(1, filteredBars.count / 6))
        case "w1":
            // For weekly bars, show every month
            return .stride(by: .month, count: 1)
        default:
            return .stride(by: .day, count: 1)
        }
    }

    private var xAxisFormat: Date.FormatStyle {
        switch timeframe {
        case "m15", "h1":
            // For intraday, show time
            return .dateTime.month().day().hour().minute()
        case "h4":
            // For 4-hour, show date and time
            return .dateTime.month().day().hour()
        case "d1":
            // For daily, show month and day
            return .dateTime.month().day()
        case "w1":
            // For weekly, show month and year
            return .dateTime.month().year()
        default:
            return .dateTime.month().day()
        }
    }

    // MARK: - Helper Functions

    private var minPrice: Double {
        filteredBars.map(\.low).min() ?? 0
    }

    private var maxPrice: Double {
        // Include indicator values in range calculation
        var maxValue = filteredBars.map(\.high).max() ?? 0
        if config.showSMA20, let sma20Max = sma20.compactMap(\.value).max() {
            maxValue = max(maxValue, sma20Max)
        }
        if config.showSMA50, let sma50Max = sma50.compactMap(\.value).max() {
            maxValue = max(maxValue, sma50Max)
        }
        return maxValue
    }

    private var priceRange: ClosedRange<Double> {
        let padding = (maxPrice - minPrice) * 0.05
        return (minPrice - padding)...(maxPrice + padding)
    }

    private func updateSelection(at location: CGPoint, proxy: ChartProxy, geometry: GeometryProxy) {
        guard let plotFrame = proxy.plotFrame else { return }
        let xPosition = location.x - geometry[plotFrame].origin.x
        guard let date: Date = proxy.value(atX: xPosition) else { return }

        selectedBar = filteredBars.min(by: { abs($0.ts.timeIntervalSince(date)) < abs($1.ts.timeIntervalSince(date)) })
    }

    private func formatPrice(_ price: Double) -> String {
        String(format: "$%.2f", price)
    }

    private func formatVolume(_ volume: Double) -> String {
        if volume >= 1_000_000 {
            return String(format: "%.1fM", volume / 1_000_000)
        } else if volume >= 1_000 {
            return String(format: "%.1fK", volume / 1_000)
        }
        return String(format: "%.0f", volume)
    }

    private func rsiColor(_ value: Double) -> Color {
        if value >= 70 {
            return .red
        } else if value <= 30 {
            return .green
        } else {
            return .purple
        }
    }
}

struct LegendItem: View {
    let color: Color
    let label: String
    let value: Double?

    var body: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
            Text(label)
                .font(.caption)
            if let value = value {
                Text(String(format: "%.2f", value))
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
            }
        }
    }
}
