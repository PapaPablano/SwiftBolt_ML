import SwiftUI
import Charts

/// Dedicated SuperTrend AI panel showing the adaptive SuperTrend line with signals
struct SuperTrendChartView: View {

    // MARK: - Properties

    let bars: [OHLCBar]
    let superTrendAIIndicator: SuperTrendAIIndicator?
    let signals: [SuperTrendSignal]
    let visibleRange: ClosedRange<Int>

    /// Scroll position binding (synced with parent chart)
    @Binding var scrollPosition: Int
    var barsToShow: Int

    // MARK: - Computed Properties

    private var result: SuperTrendAIResult? {
        superTrendAIIndicator?.result
    }

    private var superTrendLine: [Double?] {
        result?.supertrend ?? []
    }

    private var trendValues: [Int] {
        result?.trend ?? []
    }

    private var adaptiveFactors: [Double] {
        result?.adaptiveFactor ?? []
    }

    private var performanceMetrics: [Double?] {
        result?.performanceMetrics ?? []
    }

    private var adaptiveMA: [Double?] {
        result?.adaptiveMA ?? []
    }

    private var currentTrend: Int {
        superTrendAIIndicator?.currentTrend ?? 0
    }

    private var currentFactor: Double {
        superTrendAIIndicator?.currentFactor ?? 3.0
    }

    private var currentPerformance: Double {
        superTrendAIIndicator?.currentPerformance ?? 0.0
    }

    private var currentCluster: Int {
        superTrendAIIndicator?.currentCluster ?? 0
    }

    private var trendLabel: String {
        switch currentTrend {
        case 1: return "BULLISH"
        case -1: return "BEARISH"
        default: return "NEUTRAL"
        }
    }

    private var trendColor: Color {
        switch currentTrend {
        case 1: return .green
        case -1: return .red
        default: return .gray
        }
    }

    private var clusterLabel: String {
        switch currentCluster {
        case 0: return "Below Avg"
        case 1: return "Average"
        case 2: return "Exceptional"
        default: return "Unknown"
        }
    }

    private var clusterColor: Color {
        switch currentCluster {
        case 0: return .red
        case 1: return .yellow
        case 2: return .green
        default: return .gray
        }
    }

    private var chartVisibleRange: ClosedRange<Double> {
        let startIdx = max(0, scrollPosition)
        let endIdx = min(bars.count - 1, scrollPosition + barsToShow - 1)

        guard startIdx <= endIdx, !bars.isEmpty else {
            return 0...100
        }

        // Get visible SuperTrend values
        var minVal = Double.infinity
        var maxVal = -Double.infinity

        for i in startIdx...endIdx {
            if i < superTrendLine.count,
               let value = superTrendLine[i] {
                minVal = min(minVal, value)
                maxVal = max(maxVal, value)
            }
            // Also include price for context
            if i < bars.count {
                minVal = min(minVal, bars[i].low)
                maxVal = max(maxVal, bars[i].high)
            }
        }

        guard minVal < Double.infinity && maxVal > -Double.infinity else {
            return 0...100
        }

        // Add padding
        let range = maxVal - minVal
        let padding = range * 0.1
        return (minVal - padding)...(maxVal + padding)
    }

    // MARK: - Body

    var body: some View {
        VStack(spacing: 0) {
            // Header with current stats
            headerView

            // Main chart
            chartView
        }
    }

    // MARK: - Header

    private var headerView: some View {
        HStack(spacing: 16) {
            // Indicator name
            HStack(spacing: 4) {
                Image(systemName: "waveform.path.ecg")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text("SuperTrend AI")
                    .font(.caption.bold())
                    .foregroundStyle(.primary)
            }

            Divider()
                .frame(height: 12)

            // Current trend
            HStack(spacing: 4) {
                Circle()
                    .fill(trendColor)
                    .frame(width: 8, height: 8)
                Text(trendLabel)
                    .font(.caption.bold())
                    .foregroundStyle(trendColor)
            }

            // Adaptive factor
            HStack(spacing: 2) {
                Text("Factor:")
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
                Text(String(format: "%.2f", currentFactor))
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
            }

            // Performance
            HStack(spacing: 2) {
                Text("Perf:")
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
                Text(String(format: "%.4f", currentPerformance))
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(currentPerformance >= 0 ? .green : .red)
            }

            // Cluster
            HStack(spacing: 2) {
                Text("Cluster:")
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
                Text(clusterLabel)
                    .font(.caption)
                    .foregroundStyle(clusterColor)
            }

            Spacer()

            // Signal count
            let buyCount = signals.filter { $0.type == .buy }.count
            let sellCount = signals.filter { $0.type == .sell }.count
            HStack(spacing: 8) {
                HStack(spacing: 2) {
                    Image(systemName: "arrowtriangle.up.fill")
                        .font(.system(size: 8))
                        .foregroundStyle(.green)
                    Text("\(buyCount)")
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.secondary)
                }
                HStack(spacing: 2) {
                    Image(systemName: "arrowtriangle.down.fill")
                        .font(.system(size: 8))
                        .foregroundStyle(.red)
                    Text("\(sellCount)")
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.secondary)
                }
            }
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(Color(nsColor: .controlBackgroundColor).opacity(0.5))
    }

    // MARK: - Chart

    private var chartView: some View {
        Chart {
            // SuperTrend AI line with color coding
            superTrendLineMarks

            // Buy/Sell signal markers
            signalMarkers

            // Adaptive MA line (if available)
            adaptiveMALine
        }
        .chartXScale(domain: 0...(max(1, bars.count - 1)))
        .chartYScale(domain: chartVisibleRange)
        .chartScrollableAxes(.horizontal)
        .chartXVisibleDomain(length: barsToShow)
        .chartScrollPosition(x: $scrollPosition)
        .chartXAxis {
            AxisMarks(values: .automatic(desiredCount: 6)) { value in
                if let index = value.as(Int.self), index >= 0 && index < bars.count {
                    AxisGridLine(stroke: StrokeStyle(lineWidth: 0.5, dash: [2, 2]))
                        .foregroundStyle(.tertiary)
                }
            }
        }
        .chartYAxis {
            AxisMarks(position: .trailing, values: .automatic(desiredCount: 4)) { value in
                AxisGridLine(stroke: StrokeStyle(lineWidth: 0.5, dash: [2, 2]))
                    .foregroundStyle(.tertiary)
                AxisValueLabel {
                    if let price = value.as(Double.self) {
                        Text(formatPrice(price))
                            .font(.caption2.monospacedDigit())
                            .foregroundStyle(.secondary)
                    }
                }
            }
        }
        .chartLegend(.hidden)
    }

    // MARK: - Chart Content

    @ChartContentBuilder
    private var superTrendLineMarks: some ChartContent {
        // Create points with trend information for color coding
        let points = createSuperTrendPoints()

        ForEach(points) { point in
            LineMark(
                x: .value("Index", point.index),
                y: .value("SuperTrend", point.value),
                series: .value("Trend", point.seriesKey)
            )
            .foregroundStyle(point.isBullish ? Color.green : Color.red)
            .lineStyle(StrokeStyle(lineWidth: 2))
        }
    }

    @ChartContentBuilder
    private var signalMarkers: some ChartContent {
        ForEach(signals) { signal in
            if signal.barIndex < superTrendLine.count,
               let stValue = superTrendLine[signal.barIndex] {
                // Signal point
                PointMark(
                    x: .value("Index", signal.barIndex),
                    y: .value("Price", stValue)
                )
                .symbol {
                    signalSymbol(for: signal)
                }
                .symbolSize(120)
            }
        }
    }

    @ChartContentBuilder
    private var adaptiveMALine: some ChartContent {
        // Show adaptive MA as a dashed line
        let maPoints = createAdaptiveMAPoints()

        ForEach(maPoints) { point in
            LineMark(
                x: .value("Index", point.index),
                y: .value("MA", point.value)
            )
            .foregroundStyle(.purple.opacity(0.6))
            .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 2]))
        }
    }

    // MARK: - Helpers

    private struct ChartPoint: Identifiable {
        let id: String
        let index: Int
        let value: Double
        let isBullish: Bool
        let seriesKey: String
    }

    private struct MAPoint: Identifiable {
        let id = UUID()
        let index: Int
        let value: Double
    }

    private func createSuperTrendPoints() -> [ChartPoint] {
        var points: [ChartPoint] = []
        var seriesCounter = 0
        var lastTrend: Int?

        for i in 0..<bars.count {
            guard i < superTrendLine.count,
                  let value = superTrendLine[i],
                  i < trendValues.count else { continue }

            let trend = trendValues[i]
            let isBullish = trend == 1

            // Start new series on trend change
            if let last = lastTrend, last != trend {
                seriesCounter += 1
            }
            lastTrend = trend

            points.append(ChartPoint(
                id: "\(i)-\(seriesCounter)",
                index: i,
                value: value,
                isBullish: isBullish,
                seriesKey: "series-\(seriesCounter)"
            ))
        }

        return points
    }

    private func createAdaptiveMAPoints() -> [MAPoint] {
        var points: [MAPoint] = []

        for i in 0..<bars.count {
            guard i < adaptiveMA.count,
                  let value = adaptiveMA[i] else { continue }

            points.append(MAPoint(index: i, value: value))
        }

        return points
    }

    private func signalSymbol(for signal: SuperTrendSignal) -> some View {
        let color: Color = signal.type == .buy ? .green : .red

        return Group {
            if signal.type == .buy {
                Image(systemName: "arrowtriangle.up.fill")
                    .font(.system(size: 10, weight: .bold))
                    .foregroundStyle(color)
            } else {
                Image(systemName: "arrowtriangle.down.fill")
                    .font(.system(size: 10, weight: .bold))
                    .foregroundStyle(color)
            }
        }
    }

    private func formatPrice(_ price: Double) -> String {
        if price >= 1000 {
            return String(format: "%.0f", price)
        } else if price >= 100 {
            return String(format: "%.1f", price)
        } else {
            return String(format: "%.2f", price)
        }
    }
}

// MARK: - Preview

#Preview {
    SuperTrendChartView(
        bars: [],
        superTrendAIIndicator: nil,
        signals: [],
        visibleRange: 0...100,
        scrollPosition: .constant(0),
        barsToShow: 100
    )
    .frame(width: 800, height: 150)
}
