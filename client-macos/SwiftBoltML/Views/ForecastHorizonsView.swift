import SwiftUI
import Charts

/// Modern Mac-friendly visualization for multi-horizon ML forecasts
struct ForecastHorizonsView: View {
    let horizons: [ForecastSeries]
    let currentPrice: Double?
    let mlSummary: MLSummary?
    @Binding var selectedHorizon: String?
    @State private var isExpanded = false
    private let collapsedHeight: CGFloat = 58
    private let expandedHeaderHeight: CGFloat = 96

    private var displaySeries: [ForecastDisplayData] {
        horizons.compactMap { series in
            guard let lastPoint = series.points.last else { return nil }
            let confidence = ForecastDisplayData.confidenceScore(for: lastPoint)
            let qualityScore = series.targets?.qualityScore
            let color = ForecastDisplayData.directionColor(
                target: lastPoint.value,
                currentPrice: currentPrice
            )
            let timelinePosition = ForecastDisplayData.tradingDayEstimate(for: series.horizon)
            return ForecastDisplayData(
                horizon: series.horizon,
                target: lastPoint.value,
                lower: lastPoint.lower,
                upper: lastPoint.upper,
                confidence: confidence,
                qualityScore: qualityScore,
                points: series.points,
                color: color,
                deltaPct: ForecastDisplayData.deltaPct(
                    target: lastPoint.value,
                    currentPrice: currentPrice
                ),
                timelinePosition: timelinePosition
            )
        }
        .sorted { $0.timelinePosition < $1.timelinePosition }
    }

    private var bestSeries: ForecastDisplayData? {
        displaySeries.max(by: { $0.confidence < $1.confidence })
    }

    private var selectedSeries: ForecastDisplayData? {
        if let selectedHorizon {
            return displaySeries.first(where: { $0.horizon == selectedHorizon }) ?? bestSeries
        }
        return bestSeries
    }

    private var longestHorizonLabel: String? {
        displaySeries.last?.horizon.uppercased()
    }

    private var horizonCountText: String? {
        let count = displaySeries.count
        return count > 0 ? "\(count) horizons" : nil
    }

    private var longRangeCount: Int {
        let monthlyThreshold = ForecastDisplayData.tradingDayEstimate(for: "1m")
        return displaySeries.filter { $0.timelinePosition >= monthlyThreshold }.count
    }

    private var minLower: Double {
        displaySeries.compactMap(\.lower).min() ?? displaySeries.compactMap(\.target).min() ?? 0
    }

    private var maxUpper: Double {
        displaySeries.compactMap(\.upper).max() ?? displaySeries.compactMap(\.target).max() ?? 0
    }

    var body: some View {
        VStack(spacing: 0) {
            Button {
                withAnimation(.spring(response: 0.45, dampingFraction: 0.82)) {
                    isExpanded.toggle()
                }
            } label: {
                headerContent
                    .frame(height: isExpanded ? expandedHeaderHeight : collapsedHeight, alignment: .center)
                    .padding(.horizontal, 16)
            }
            .buttonStyle(.plain)
            .background(headerBackgroundStyle)
            .contentShape(Rectangle())

            if isExpanded {
                Divider()
                    .background(Color.black.opacity(0.05))
                expandedContent
                    .padding(16)
                    .background(Color(nsColor: .controlBackgroundColor))
            }
        }
        .onAppear {
            if selectedHorizon == nil {
                selectedHorizon = horizons.first?.horizon
            }
        }
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .stroke(isExpanded ? Color.black.opacity(0.05) : Color.white.opacity(0.08), lineWidth: 1)
        )
        .shadow(color: .black.opacity(isExpanded ? 0.14 : 0.1), radius: isExpanded ? 18 : 10, x: 0, y: isExpanded ? 10 : 4)
        .animation(.spring(response: 0.4, dampingFraction: 0.85), value: isExpanded)
    }

    private var headerBackgroundStyle: AnyShapeStyle {
        if isExpanded {
            return AnyShapeStyle(Color(nsColor: .controlBackgroundColor))
        } else {
            return AnyShapeStyle(collapsedGradient)
        }
    }

    private var collapsedGradient: LinearGradient {
        LinearGradient(
            colors: [
                Color(red: 0.16, green: 0.23, blue: 0.42),
                Color(red: 0.09, green: 0.14, blue: 0.28)
            ],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
    }

    @ViewBuilder
    private var headerContent: some View {
        if isExpanded {
            expandedHeader
        } else {
            collapsedHeader
        }
    }

    private var collapsedHeader: some View {
        HStack(spacing: 12) {
            HStack(spacing: 8) {
                Image(systemName: "brain.head.profile")
                    .font(.headline)
                    .foregroundStyle(.purple)
                    .frame(width: 28, height: 28)
                    .background(Color.white.opacity(0.1), in: RoundedRectangle(cornerRadius: 8, style: .continuous))

                VStack(alignment: .leading, spacing: 2) {
                    Text("ML Forecast")
                        .font(.callout.bold())
                    if let summary = mlSummary, let selected = selectedSeries {
                        Text("\(summary.overallLabel?.capitalized ?? "Unknown") • \(selected.horizon.uppercased()) target \(selected.formattedTarget) · \(selected.shortDeltaDescription)")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                    } else {
                        Text("Awaiting ML forecast data")
                            .font(.caption2)
                            .foregroundStyle(.tertiary)
                    }
                }
            }

            Spacer(minLength: 8)

            if let summary = mlSummary {
                VStack(alignment: .trailing, spacing: 2) {
                    Text("\(Int(summary.confidence * 100))%")
                        .font(.headline.bold())
                        .foregroundStyle(labelColor(for: summary.overallLabel))
                    Text(summary.overallLabel?.capitalized ?? "Unknown")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
            }

            HStack(spacing: 6) {
                if let longest = longestHorizonLabel {
                    Text("Longest \(longest)")
                        .font(.caption2.bold())
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(Color.white.opacity(0.1))
                        .clipShape(Capsule())
                }

                if let countText = horizonCountText {
                    Text(countText)
                        .font(.caption2.bold())
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(Color.white.opacity(0.08))
                        .clipShape(Capsule())
                }

                if longRangeCount > 0 {
                    Text("\(longRangeCount) long-range")
                        .font(.caption2.bold())
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(Color.white.opacity(0.08))
                        .clipShape(Capsule())
                }
            }

            Image(systemName: "chevron.down")
                .font(.caption.bold())
                .foregroundStyle(.secondary)
        }
        .frame(maxHeight: .infinity, alignment: .center)
    }

    private var expandedHeader: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 8) {
                    Image(systemName: "brain.head.profile")
                        .foregroundStyle(.purple)
                        .font(.title3)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("ML Forecast")
                            .font(.headline)
                        if let summary = mlSummary {
                            Text(summaryHeadline(summary))
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        } else {
                            Text("Awaiting ML forecast data")
                                .font(.caption)
                                .foregroundStyle(.tertiary)
                        }
                    }
                }

                if let selected = selectedSeries {
                    Text("\(selected.horizon.uppercased()) target \(selected.formattedTarget) • \(selected.shortDeltaDescription) vs last")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            Spacer()

            primaryMetrics

            Image(systemName: "chevron.down")
                .font(.caption.bold())
                .rotationEffect(.degrees(isExpanded ? 180 : 0))
                .foregroundStyle(.secondary)
                .animation(.spring(response: 0.45, dampingFraction: 0.82), value: isExpanded)
        }
    }

    private var expandedContent: some View {
        VStack(alignment: .leading, spacing: 12) {
            if displaySeries.count > 1 {
                let fallback = displaySeries.first?.horizon
                let selection = Binding<String>(
                    get: {
                        if let selectedHorizon, displaySeries.contains(where: { $0.horizon == selectedHorizon }) {
                            return selectedHorizon
                        }
                        return fallback ?? ""
                    },
                    set: { selectedHorizon = $0 }
                )

                Picker("Forecast Horizon", selection: selection) {
                    ForEach(displaySeries, id: \.horizon) { series in
                        Text(series.horizon.uppercased()).tag(series.horizon)
                    }
                }
                .pickerStyle(.segmented)
            }

            if displaySeries.isEmpty {
                Text("No horizon data available.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.vertical, 12)
            } else {
                ForecastHorizonCarousel(
                    series: displaySeries,
                    scaleRange: minLower...maxUpper,
                    currentPrice: currentPrice
                )

                ForecastTimelineView(series: displaySeries)
            }

            if let currentPrice {
                Text("Reference price \(String(format: "$%.2f", currentPrice)) · align ranges across horizons for quick comparison.")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
    }

    private var primaryMetrics: some View {
        VStack(alignment: .trailing, spacing: 4) {
            if let summary = mlSummary {
                Text("\(Int(summary.confidence * 100))%")
                    .font(.title3.bold())
                    .foregroundStyle(labelColor(for: summary.overallLabel))
                Text(summary.overallLabel?.capitalized ?? "Unknown")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            if let longest = longestHorizonLabel {
                Text("Longest \(longest)")
                    .font(.caption2)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 4)
                    .background(Color.secondary.opacity(0.15))
                    .clipShape(Capsule())
            }
        }
    }

    private func summaryHeadline(_ summary: MLSummary) -> String {
        let label = summary.overallLabel?.capitalized ?? "Unknown"
        return "\(label) • \(Int(summary.confidence * 100))% confidence"
    }

    private func labelColor(for label: String?) -> Color {
        switch (label ?? "").lowercased() {
        case "bullish": return .green
        case "bearish": return .red
        case "neutral": return .orange
        default: return .gray
        }
    }
}

// MARK: - Carousel

private struct ForecastHorizonCarousel: View {
    let series: [ForecastDisplayData]
    let scaleRange: ClosedRange<Double>
    let currentPrice: Double?

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 16) {
                ForEach(series) { series in
                    ForecastHorizonCard(
                        series: series,
                        scaleRange: scaleRange,
                        currentPrice: currentPrice
                    )
                    .frame(width: 280)
                }
            }
            .padding(.vertical, 4)
        }
    }
}

// MARK: - Card

private struct ForecastHorizonCard: View {
    let series: ForecastDisplayData
    let scaleRange: ClosedRange<Double>
    let currentPrice: Double?

    private var targetText: String {
        guard let target = series.target else { return "N/A" }
        return "$\(String(format: "%.2f", target))"
    }

    private var rangeText: String {
        guard let lower = series.lower, let upper = series.upper else { return "—" }
        return "$\(String(format: "%.2f", lower)) – $\(String(format: "%.2f", upper))"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(series.horizon.uppercased())
                        .font(.caption.bold())
                        .foregroundStyle(.secondary)
                    Text(targetText)
                        .font(.system(size: 22, weight: .semibold, design: .rounded))
                        .foregroundStyle(series.color)
                }

                Spacer()

                HorizonConfidenceBadge(
                    label: "Confidence",
                    percent: series.confidence,
                    color: series.color
                )

                if let qualityPercent = series.qualityPercent {
                    HorizonConfidenceBadge(
                        label: "Quality",
                        percent: qualityPercent,
                        color: series.color.opacity(0.8)
                    )
                }
            }

            if let delta = series.deltaPct {
                Text(delta.asPercentString)
                    .font(.caption)
                    .foregroundStyle(delta >= 0 ? Color.green : Color.red)
            } else {
                Text("Δ vs price unavailable")
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }

            HorizonRangeBand(
                series: series,
                scaleRange: scaleRange,
                currentPrice: currentPrice
            )
            .frame(height: 28)

            HStack(spacing: 12) {
                Label(rangeText, systemImage: "chart.bar.xaxis")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer()
                if let upper = series.upper, let lower = series.lower {
                    Text(String(format: "Spread %.2f%%", (upper - lower) / ((upper + lower) / 2) * 100))
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }

            if series.points.count > 1 {
                ForecastSparkline(points: series.points, tint: series.color)
                    .frame(height: 70)
            }
        }
        .padding(14)
        .background(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(series.color.opacity(0.08))
                .overlay(
                    RoundedRectangle(cornerRadius: 14, style: .continuous)
                        .stroke(series.color.opacity(0.3), lineWidth: 1)
                )
        )
        // Improvement 2: Forecast UX consistency - tooltip with confidence + time delta
        .help(tooltipText)
    }

    private var tooltipText: String {
        var lines: [String] = []
        lines.append("\(series.horizon.uppercased()) Forecast")
        lines.append("Confidence: \(Int(series.confidence * 100))%")

        if let qualityPercent = series.qualityPercent {
            lines.append("Quality: \(qualityPercent)%")
        }

        if let target = series.target {
            lines.append("Target: $\(String(format: "%.2f", target))")
        }
        if let delta = series.deltaPct {
            let direction = delta >= 0 ? "+" : ""
            lines.append("Delta: \(direction)\(String(format: "%.2f", delta))% vs current price")
        }
        if let lower = series.lower, let upper = series.upper {
            lines.append("Range: $\(String(format: "%.2f", lower)) - $\(String(format: "%.2f", upper))")
        }

        // Time estimate
        lines.append("Timeline: ~\(series.timelinePosition) trading days")

        return lines.joined(separator: "\n")
    }
}

// MARK: - Range Band

private struct HorizonRangeBand: View {
    let series: ForecastDisplayData
    let scaleRange: ClosedRange<Double>
    let currentPrice: Double?

    private var normalizedLower: Double {
        guard let lower = series.lower else { return normalizedTarget }
        return normalized(lower)
    }

    private var normalizedUpper: Double {
        guard let upper = series.upper else { return normalizedTarget }
        return normalized(upper)
    }

    private var normalizedTarget: Double {
        guard let target = series.target else { return 0 }
        return normalized(target)
    }

    private var normalizedCurrentPrice: Double? {
        guard let price = currentPrice else { return nil }
        return normalized(price)
    }

    var body: some View {
        GeometryReader { geometry in
            let width = geometry.size.width
            let bandX = width * normalizedLower
            let bandWidth = max(4, width * (normalizedUpper - normalizedLower))
            let targetX = width * normalizedTarget

            ZStack(alignment: .leading) {
                Capsule()
                    .fill(Color.primary.opacity(0.08))

                Capsule()
                    .fill(
                        LinearGradient(
                            colors: [series.color.opacity(0.2), series.color.opacity(0.7)],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .frame(width: bandWidth)
                    .offset(x: bandX)

                Circle()
                    .fill(series.color)
                    .frame(width: 12, height: 12)
                    .offset(x: targetX - 6)
                    .overlay(
                        Circle()
                            .stroke(Color.white, lineWidth: 2)
                            .offset(x: targetX - 6)
                    )

                if let normalizedCurrentPrice {
                    let priceX = width * normalizedCurrentPrice
                    Capsule()
                        .stroke(style: StrokeStyle(lineWidth: 1, dash: [4, 4]))
                        .fill(Color.secondary)
                        .frame(width: 2, height: geometry.size.height)
                        .offset(x: priceX - 1)

                    Text("Now")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .offset(x: min(max(priceX - 14, 0), width - 28), y: geometry.size.height / 2)
                }
            }
        }
    }

    private func normalized(_ value: Double) -> Double {
        guard scaleRange.upperBound != scaleRange.lowerBound else { return 0.5 }
        return min(
            max(
                (value - scaleRange.lowerBound) / (scaleRange.upperBound - scaleRange.lowerBound),
                0
            ),
            1
        )
    }
}

// MARK: - Timeline

private struct ForecastTimelineView: View {
    let series: [ForecastDisplayData]

    private var minPosition: Double {
        series.map(\.timelinePosition).min() ?? 0
    }

    private var maxPosition: Double {
        series.map(\.timelinePosition).max() ?? 1
    }

    private var normalizedSeries: [ForecastDisplayData] {
        let minPos = minPosition
        let maxPos = max(minPosition + 1, maxPosition)
        return series.map { data in
            var normalized = data
            normalized.normalizedTimelinePosition = (data.timelinePosition - minPos) / (maxPos - minPos)
            return normalized
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Forecast Timeline")
                .font(.caption)
                .foregroundStyle(.secondary)

            GeometryReader { geometry in
                let width = geometry.size.width
                ZStack(alignment: .leading) {
                    Capsule()
                        .fill(Color.primary.opacity(0.08))
                        .frame(height: 6)

                    ForEach(normalizedSeries) { data in
                        let x = width * data.normalizedTimelinePosition
                        VStack(spacing: 4) {
                            Circle()
                                .fill(data.color)
                                .frame(width: 18, height: 18)
                                .overlay(
                                    Circle()
                                        .stroke(Color.white, lineWidth: 2)
                                )
                                .overlay(
                                    Text(data.shortHorizonLabel)
                                        .font(.system(size: 8, weight: .bold, design: .rounded))
                                        .foregroundColor(.white)
                                )
                            Text(data.horizon.uppercased())
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                        .offset(x: max(0, min(x - 9, width - 18)))
                        .animation(.spring(response: 0.4, dampingFraction: 0.85), value: series.count)
                    }
                }
            }
            .frame(height: 44)
        }
        .padding(.top, 12)
    }
}

// MARK: - Sparkline

private struct ForecastSparkline: View {
    let points: [ForecastPoint]
    let tint: Color

    private var chartPoints: [ChartDataPoint] {
        points.compactMap { point in
            ChartDataPoint(
                date: Date(timeIntervalSince1970: TimeInterval(point.ts)),
                value: point.value
            )
        }
    }

    var body: some View {
        Chart {
            ForEach(chartPoints) { data in
                LineMark(
                    x: .value("Time", data.date),
                    y: .value("Value", data.value)
                )
                .interpolationMethod(.catmullRom)
                .lineStyle(StrokeStyle(lineWidth: 2, lineCap: .round))
                .foregroundStyle(tint)

                AreaMark(
                    x: .value("Time", data.date),
                    y: .value("Value", data.value)
                )
                .interpolationMethod(.catmullRom)
                .foregroundStyle(
                    LinearGradient(
                        colors: [tint.opacity(0.25), tint.opacity(0.05)],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                )
            }
        }
        .chartXAxis(.hidden)
        .chartYAxis(.hidden)
        .chartLegend(.hidden)
    }
}

// MARK: - Confidence Badge

private struct HorizonConfidenceBadge: View {
    let label: String
    let percent: Int
    let color: Color

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: "shield.checkerboard")
                .font(.caption2)
            Text(label)
            Divider()
                .frame(height: 10)
            Text("\(percent)%")
                .font(.caption.bold())
        }
        .font(.caption2)
        .foregroundStyle(color)
        .padding(.horizontal, 10)
        .padding(.vertical, 4)
        .background(color.opacity(0.12))
        .clipShape(Capsule(style: .continuous))
    }
}

// MARK: - Models & Helpers

private struct ForecastDisplayData: Identifiable {
    let id = UUID()
    let horizon: String
    let target: Double?
    let lower: Double?
    let upper: Double?
    let confidence: Int
    let qualityScore: Double?
    let points: [ForecastPoint]
    let color: Color
    let deltaPct: Double?
    let timelinePosition: Double
    var normalizedTimelinePosition: Double = 0

    var formattedTarget: String {
        guard let target else { return "—" }
        return "$\(String(format: "%.2f", target))"
    }

    var shortDeltaDescription: String {
        guard let deltaPct else { return "N/A" }
        return deltaPct.asPercentString
    }

    var qualityPercent: Int? {
        guard let qualityScore else { return nil }
        let normalized = qualityScore <= 1 ? qualityScore * 100 : qualityScore
        return Int(normalized.rounded())
    }

    var spreadDescription: String? {
        guard let lower, let upper else { return nil }
        let spreadPct = (upper - lower) / ((upper + lower) / 2)
        return String(format: "%.2f%%", spreadPct * 100)
    }

    var shortHorizonLabel: String {
        let lowercased = horizon.lowercased()
        if lowercased.contains("15") { return "15m" }
        if lowercased.contains("1h") { return "1h" }
        if lowercased.contains("4h") { return "4h" }
        if lowercased.contains("1d") { return "1d" }
        if lowercased.contains("1w") { return "1w" }
        return horizon.lowercased()
    }

    static func confidenceScore(for point: ForecastPoint) -> Int {
        let spread = max(0.0001, point.upper - point.lower)
        let denominator = max(1, abs(point.value))
        let normalized = min(1, spread / denominator)
        let score = 100 - Int(normalized * 65)
        return max(15, min(95, score))
    }

    static func directionColor(target: Double?, currentPrice: Double?) -> Color {
        guard let target, let currentPrice else { return .orange }
        let change = (target - currentPrice) / currentPrice
        if change >= 0.02 { return .green }
        if change <= -0.02 { return .red }
        return .orange
    }

    static func deltaPct(target: Double?, currentPrice: Double?) -> Double? {
        guard let target, let currentPrice, currentPrice != 0 else { return nil }
        return (target - currentPrice) / currentPrice
    }

    static func tradingDayEstimate(for horizon: String) -> Double {
        let normalized = horizon.lowercased()
        if normalized.contains("15") { return 0.03 }
        if normalized.contains("30") { return 0.06 }
        if normalized.contains("1h") { return 0.1 }
        if normalized.contains("4h") { return 0.3 }
        if normalized == "7d" || normalized.contains("7d") { return 5 }
        if normalized.contains("1d") || normalized.contains("daily") { return 1 }
        if normalized.contains("1w") || normalized.contains("weekly") { return 5 }
        if normalized.contains("1m") || normalized.contains("monthly") { return 21 }
        if normalized.contains("2m") { return 42 }
        if normalized.contains("3m") { return 63 }
        if normalized.contains("4m") { return 84 }
        if normalized.contains("5m") { return 105 }
        if normalized.contains("6m") { return 126 }
        if normalized.contains("1y") || normalized.contains("12m") { return 252 }
        return 250
    }
}

private struct ChartDataPoint: Identifiable {
    let id = UUID()
    let date: Date
    let value: Double
}

private extension Double {
    var asPercentString: String {
        String(format: "%+.1f%% vs last", self * 100)
    }
}
