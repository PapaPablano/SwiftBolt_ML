import SwiftUI
import Charts

// MARK: - SuperTrend Panel View

struct SuperTrendPanelView: View {
    let bars: [OHLCBar]
    let superTrendLine: [IndicatorDataPoint]
    let superTrendTrend: [Int]  // 1 = bullish, 0 = bearish
    let signals: [SignalMetadata]
    let performanceIndex: Double
    let signalStrength: Int
    let currentTrend: String
    let stopLevel: Double
    let visibleRange: ClosedRange<Int>

    var body: some View {
        VStack(spacing: 0) {
            headerView
            chartView
        }
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    // MARK: - Header

    private var headerView: some View {
        HStack {
            Text("SuperTrend AI")
                .font(.caption.bold())
                .foregroundStyle(.secondary)

            Spacer()

            PerformanceBadge(score: signalStrength)

            TrendBadge(trend: currentTrend)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
    }

    // MARK: - Chart

    private var chartView: some View {
        Chart {
            // Trend zone backgrounds
            ForEach(trendZones, id: \.startIndex) { zone in
                RectangleMark(
                    xStart: .value("Start", zone.startIndex),
                    xEnd: .value("End", zone.endIndex),
                    yStart: .value("Low", visibleMinPrice),
                    yEnd: .value("High", visibleMaxPrice)
                )
                .foregroundStyle(
                    zone.isBullish
                        ? Color.green.opacity(0.08)
                        : Color.red.opacity(0.08)
                )
            }

            // Candlesticks
            ForEach(Array(visibleBarsData.enumerated()), id: \.offset) { _, item in
                candlestickMark(for: item.bar, at: item.index)
            }

            // SuperTrend line (color-coded by trend)
            ForEach(Array(superTrendLine.enumerated()), id: \.element.id) { idx, point in
                if let value = point.value,
                   let barIndex = indicatorIndex(for: point.date),
                   visibleRange.contains(barIndex),
                   barIndex < superTrendTrend.count {
                    let trend = superTrendTrend[barIndex]

                    LineMark(
                        x: .value("Index", barIndex),
                        y: .value("SuperTrend", value)
                    )
                    .foregroundStyle(trend == 1 ? .green : .red)
                    .lineStyle(StrokeStyle(lineWidth: 2))
                }
            }

            // Signal markers
            ForEach(visibleSignals, id: \.id) { signal in
                if let barIndex = signalBarIndex(for: signal) {
                    PointMark(
                        x: .value("Index", barIndex),
                        y: .value("Price", signal.price)
                    )
                    .symbol(signal.type == "BUY" ? .triangle : .diamond)
                    .foregroundStyle(signal.type == "BUY" ? .green : .red)
                    .symbolSize(80)
                }
            }
        }
        .chartYScale(domain: visiblePriceRange)
        .chartXScale(domain: visibleRange)
        .chartXAxis(.hidden)
        .chartYAxis {
            AxisMarks(position: .trailing) { value in
                AxisValueLabel {
                    if let price = value.as(Double.self) {
                        Text(formatPrice(price))
                            .font(.caption2)
                    }
                }
            }
        }
        .frame(height: 180)
        .padding(.horizontal, 4)
    }

    // MARK: - Candlestick Mark

    @ChartContentBuilder
    private func candlestickMark(for bar: OHLCBar, at index: Int) -> some ChartContent {
        let isGreen = bar.close >= bar.open

        // Body
        RectangleMark(
            x: .value("Index", index),
            yStart: .value("Open", min(bar.open, bar.close)),
            yEnd: .value("Close", max(bar.open, bar.close)),
            width: 6
        )
        .foregroundStyle(isGreen ? Color.green.opacity(0.8) : Color.red.opacity(0.8))

        // Wick
        RuleMark(
            x: .value("Index", index),
            yStart: .value("Low", bar.low),
            yEnd: .value("High", bar.high)
        )
        .foregroundStyle(isGreen ? Color.green.opacity(0.6) : Color.red.opacity(0.6))
        .lineStyle(StrokeStyle(lineWidth: 1))
    }

    // MARK: - Computed Properties

    private var visibleBarsData: [(index: Int, bar: OHLCBar)] {
        visibleRange.compactMap { index in
            guard index >= 0 && index < bars.count else { return nil }
            return (index, bars[index])
        }
    }

    private var visibleBars: [(index: Int, bar: OHLCBar)] {
        visibleBarsData
    }

    private var visibleMinPrice: Double {
        let prices = visibleBars.map(\.bar.low)
        let stValues = superTrendLine.compactMap { point -> Double? in
            guard let value = point.value,
                  let index = indicatorIndex(for: point.date),
                  visibleRange.contains(index) else { return nil }
            return value
        }
        return min(prices.min() ?? 0, stValues.min() ?? Double.infinity)
    }

    private var visibleMaxPrice: Double {
        let prices = visibleBars.map(\.bar.high)
        let stValues = superTrendLine.compactMap { point -> Double? in
            guard let value = point.value,
                  let index = indicatorIndex(for: point.date),
                  visibleRange.contains(index) else { return nil }
            return value
        }
        return max(prices.max() ?? 0, stValues.max() ?? 0)
    }

    private var visiblePriceRange: ClosedRange<Double> {
        let padding = (visibleMaxPrice - visibleMinPrice) * 0.05
        return (visibleMinPrice - padding)...(visibleMaxPrice + padding)
    }

    private var trendZones: [TrendZone] {
        guard !superTrendTrend.isEmpty else { return [] }

        var zones: [TrendZone] = []
        var currentZoneStart = visibleRange.lowerBound
        var currentTrendValue = superTrendTrend[safe: visibleRange.lowerBound] ?? 1

        for i in visibleRange {
            let trend = superTrendTrend[safe: i] ?? currentTrendValue
            if trend != currentTrendValue && i > currentZoneStart {
                zones.append(TrendZone(
                    startIndex: currentZoneStart,
                    endIndex: i - 1,
                    isBullish: currentTrendValue == 1
                ))
                currentZoneStart = i
                currentTrendValue = trend
            }
        }

        // Close final zone
        zones.append(TrendZone(
            startIndex: currentZoneStart,
            endIndex: visibleRange.upperBound,
            isBullish: currentTrendValue == 1
        ))

        return zones
    }

    private var visibleSignals: [SignalMetadata] {
        signals.filter { signal in
            guard let barIndex = signalBarIndex(for: signal) else { return false }
            return visibleRange.contains(barIndex)
        }
    }

    // MARK: - Helper Functions

    private func indicatorIndex(for date: Date) -> Int? {
        bars.firstIndex { bar in
            Calendar.current.isDate(bar.ts, equalTo: date, toGranularity: .second)
        }
    }

    private func signalBarIndex(for signal: SignalMetadata) -> Int? {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]

        guard let signalDate = formatter.date(from: signal.date) else {
            // Try without fractional seconds
            formatter.formatOptions = [.withInternetDateTime]
            guard let date = formatter.date(from: signal.date) else { return nil }
            return indicatorIndex(for: date)
        }
        return indicatorIndex(for: signalDate)
    }

    private func formatPrice(_ price: Double) -> String {
        String(format: "$%.2f", price)
    }
}

// MARK: - Trend Zone

struct TrendZone: Equatable {
    let startIndex: Int
    let endIndex: Int
    let isBullish: Bool
}

// MARK: - Performance Badge

struct PerformanceBadge: View {
    let score: Int  // 0-10

    var body: some View {
        HStack(spacing: 2) {
            Image(systemName: "chart.line.uptrend.xyaxis")
                .font(.caption2)
            Text("\(score)/10")
                .font(.caption2.bold())
        }
        .padding(.horizontal, 6)
        .padding(.vertical, 2)
        .background(badgeColor.opacity(0.2))
        .foregroundStyle(badgeColor)
        .clipShape(Capsule())
    }

    private var badgeColor: Color {
        switch score {
        case 8...10: return .green
        case 5...7: return .orange
        default: return .red
        }
    }
}

// MARK: - Trend Badge

struct TrendBadge: View {
    let trend: String

    var body: some View {
        HStack(spacing: 2) {
            Image(systemName: trend == "BULLISH" ? "arrow.up.right" : "arrow.down.right")
                .font(.caption2)
            Text(trend)
                .font(.caption2.bold())
        }
        .padding(.horizontal, 6)
        .padding(.vertical, 2)
        .background(trendColor.opacity(0.2))
        .foregroundStyle(trendColor)
        .clipShape(Capsule())
    }

    private var trendColor: Color {
        trend == "BULLISH" ? .green : .red
    }
}

// MARK: - Confidence Badge (for signal annotations)

struct ConfidenceBadge: View {
    let score: Int

    var body: some View {
        Text("\(score)")
            .font(.system(size: 8, weight: .bold))
            .foregroundStyle(.white)
            .frame(width: 14, height: 14)
            .background(badgeColor)
            .clipShape(Circle())
    }

    private var badgeColor: Color {
        switch score {
        case 8...10: return .green
        case 5...7: return .orange
        default: return .red
        }
    }
}

// MARK: - Array Safe Subscript Extension

extension Array {
    subscript(safe index: Int) -> Element? {
        guard index >= 0 && index < count else { return nil }
        return self[index]
    }
}
