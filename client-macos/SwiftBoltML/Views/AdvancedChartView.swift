import SwiftUI
import Charts

struct AdvancedChartView: View {
    let bars: [OHLCBar]
    let sma20: [IndicatorDataPoint]
    let sma50: [IndicatorDataPoint]
    let ema9: [IndicatorDataPoint]
    let ema21: [IndicatorDataPoint]
    let rsi: [IndicatorDataPoint]
    let config: IndicatorConfig

    @State private var selectedBar: OHLCBar?
    @State private var selectedIndex: Int?

    // Chart pan/zoom state
    @State private var visibleRange: ClosedRange<Int>
    @State private var barsToShow: Int = 100 // Default visible bars

    init(bars: [OHLCBar], sma20: [IndicatorDataPoint], sma50: [IndicatorDataPoint], ema9: [IndicatorDataPoint], ema21: [IndicatorDataPoint], rsi: [IndicatorDataPoint], config: IndicatorConfig) {
        self.bars = bars
        self.sma20 = sma20
        self.sma50 = sma50
        self.ema9 = ema9
        self.ema21 = ema21
        self.rsi = rsi
        self.config = config

        // Initialize visible range to show most recent bars
        let count = bars.count
        let initialBarsToShow = min(100, count)
        let endIndex = max(0, count - 1)
        let startIndex = max(0, endIndex - initialBarsToShow + 1)
        _visibleRange = State(initialValue: startIndex...endIndex)
        _barsToShow = State(initialValue: initialBarsToShow)
    }

    // Create indexed versions for even spacing (TradingView style)
    private var indexedBars: [(index: Int, bar: OHLCBar)] {
        bars.enumerated().map { (index: $0.offset, bar: $0.element) }
    }

    // Visible bars based on current range
    private var visibleBars: [(index: Int, bar: OHLCBar)] {
        indexedBars.filter { visibleRange.contains($0.index) }
    }

    // Map indicator data points to bar indices
    private func indicatorIndex(for date: Date) -> Int? {
        bars.firstIndex(where: { Calendar.current.isDate($0.ts, equalTo: date, toGranularity: .second) })
    }

    var body: some View {
        VStack(spacing: 0) {
            // Chart controls
            chartControls
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(Color(nsColor: .controlBackgroundColor))

            Divider()

            // Main price chart with indicators
            priceChartView
                .frame(height: config.showRSI ? 400 : 500)

            if config.showRSI {
                Divider()
                rsiChartView
                    .frame(height: 120)
            }

            if config.showVolume {
                Divider()
                volumeChartView
                    .frame(height: 100)
            }
        }
        .onChange(of: bars.count) { oldCount, newCount in
            // Reset to latest bars when data changes
            if oldCount != newCount {
                resetToLatest()
            }
        }
    }

    // MARK: - Chart Controls

    private var chartControls: some View {
        HStack(spacing: 12) {
            // Data range info
            Text("\(bars.count) bars")
                .font(.caption.monospacedDigit())
                .foregroundStyle(.secondary)

            if bars.count > 0 {
                Text("•")
                    .foregroundStyle(.tertiary)
                Text("\(formatDate(bars[visibleRange.lowerBound].ts)) - \(formatDate(bars[visibleRange.upperBound].ts))")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            // Zoom controls
            Button(action: zoomOut) {
                Image(systemName: "minus.magnifyingglass")
                    .font(.caption)
            }
            .buttonStyle(.borderless)
            .disabled(visibleRange.count >= bars.count)

            Button(action: zoomIn) {
                Image(systemName: "plus.magnifyingglass")
                    .font(.caption)
            }
            .buttonStyle(.borderless)
            .disabled(visibleRange.count <= 10)

            // Pan controls
            Button(action: panLeft) {
                Image(systemName: "chevron.left")
                    .font(.caption)
            }
            .buttonStyle(.borderless)
            .disabled(visibleRange.lowerBound <= 0)

            Button(action: panRight) {
                Image(systemName: "chevron.right")
                    .font(.caption)
            }
            .buttonStyle(.borderless)
            .disabled(visibleRange.upperBound >= bars.count - 1)

            // Reset to most recent
            Button("Latest") {
                resetToLatest()
            }
            .buttonStyle(.borderless)
            .font(.caption)
        }
    }

    // MARK: - Price Chart

    private var priceChartView: some View {
        Chart {
            // Candlesticks - using index for even spacing
            ForEach(visibleBars, id: \.bar.id) { item in
                candlestickMarks(index: item.index, bar: item.bar)
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
            if let selectedIdx = selectedIndex {
                RuleMark(x: .value("Index", selectedIdx))
                    .foregroundStyle(.blue.opacity(0.3))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))
            }
        }
        .chartXScale(domain: visibleRange.lowerBound...visibleRange.upperBound)
        .chartYScale(domain: visiblePriceRange)
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
                if let value = point.value, let index = indicatorIndex(for: point.date), visibleRange.contains(index) {
                    LineMark(
                        x: .value("Index", index),
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
            if let selectedIdx = selectedIndex {
                RuleMark(x: .value("Index", selectedIdx))
                    .foregroundStyle(.blue.opacity(0.3))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))
            }
        }
        .chartXScale(domain: visibleRange.lowerBound...visibleRange.upperBound)
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
        Chart(visibleBars, id: \.bar.id) { item in
            BarMark(
                x: .value("Index", item.index),
                y: .value("Volume", item.bar.volume)
            )
            .foregroundStyle(item.bar.close >= item.bar.open ? Color.green.opacity(0.5) : Color.red.opacity(0.5))
        }
        .chartXScale(domain: visibleRange.lowerBound...visibleRange.upperBound)
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
    private func candlestickMarks(index: Int, bar: OHLCBar) -> some ChartContent {
        // Candlestick body
        RectangleMark(
            x: .value("Index", index),
            yStart: .value("Open", min(bar.open, bar.close)),
            yEnd: .value("Close", max(bar.open, bar.close)),
            width: .ratio(0.6)
        )
        .foregroundStyle(bar.close >= bar.open ? Color.green : Color.red)
        .opacity(selectedIndex == index ? 1.0 : 0.8)

        // Candlestick wick
        RuleMark(
            x: .value("Index", index),
            yStart: .value("Low", bar.low),
            yEnd: .value("High", bar.high)
        )
        .foregroundStyle(bar.close >= bar.open ? Color.green.opacity(0.8) : Color.red.opacity(0.8))
        .lineStyle(StrokeStyle(lineWidth: 1.5))
    }

    @ChartContentBuilder
    private func indicatorLine(_ data: [IndicatorDataPoint], color: Color, label: String) -> some ChartContent {
        ForEach(data) { point in
            if let value = point.value, let index = indicatorIndex(for: point.date) {
                LineMark(
                    x: .value("Index", index),
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

    // MARK: - Helper Functions

    private var visibleMinPrice: Double {
        visibleBars.map(\.bar.low).min() ?? 0
    }

    private var visibleMaxPrice: Double {
        // Include indicator values in range calculation for visible range
        var maxValue = visibleBars.map(\.bar.high).max() ?? 0

        // Check visible indicators
        let visibleIndicatorValues = sma20.compactMap { point -> Double? in
            guard let value = point.value, let index = indicatorIndex(for: point.date), visibleRange.contains(index) else { return nil }
            return value
        }
        if let indicatorMax = visibleIndicatorValues.max() {
            maxValue = max(maxValue, indicatorMax)
        }

        return maxValue
    }

    private var visiblePriceRange: ClosedRange<Double> {
        let padding = (visibleMaxPrice - visibleMinPrice) * 0.05
        return (visibleMinPrice - padding)...(visibleMaxPrice + padding)
    }

    // Pan/Zoom functions
    private func zoomIn() {
        let currentWidth = visibleRange.count
        let newWidth = max(10, currentWidth / 2)
        let center = (visibleRange.lowerBound + visibleRange.upperBound) / 2
        let newStart = max(0, center - newWidth / 2)
        let newEnd = min(bars.count - 1, newStart + newWidth - 1)
        visibleRange = newStart...newEnd
    }

    private func zoomOut() {
        let currentWidth = visibleRange.count
        let newWidth = min(bars.count, currentWidth * 2)
        let center = (visibleRange.lowerBound + visibleRange.upperBound) / 2
        let newStart = max(0, center - newWidth / 2)
        let newEnd = min(bars.count - 1, newStart + newWidth - 1)
        visibleRange = newStart...newEnd
    }

    private func panLeft() {
        let width = visibleRange.count
        let shift = width / 4
        let newStart = max(0, visibleRange.lowerBound - shift)
        let newEnd = newStart + width - 1
        visibleRange = newStart...newEnd
    }

    private func panRight() {
        let width = visibleRange.count
        let shift = width / 4
        let newEnd = min(bars.count - 1, visibleRange.upperBound + shift)
        let newStart = max(0, newEnd - width + 1)
        visibleRange = newStart...newEnd
    }

    private func resetToLatest() {
        let newWidth = min(100, bars.count)
        let newEnd = bars.count - 1
        let newStart = max(0, newEnd - newWidth + 1)
        visibleRange = newStart...newEnd
    }

    private func updateSelection(at location: CGPoint, proxy: ChartProxy, geometry: GeometryProxy) {
        guard let plotFrame = proxy.plotFrame else { return }
        let xPosition = location.x - geometry[plotFrame].origin.x
        guard let index: Int = proxy.value(atX: xPosition) else { return }

        // Clamp index to valid range
        let clampedIndex = max(0, min(index, bars.count - 1))
        selectedIndex = clampedIndex
        selectedBar = bars[clampedIndex]
    }

    private func formatDate(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "M/d"
        return formatter.string(from: date)
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
