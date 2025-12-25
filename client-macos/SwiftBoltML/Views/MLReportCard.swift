import SwiftUI

struct MLReportCard: View {
    let mlSummary: MLSummary
    @State private var isExpanded = false

    private var labelColor: Color {
        let label = (mlSummary.overallLabel ?? "unknown").lowercased()
        switch label {
        case "bullish":
            return .green
        case "bearish":
            return .red
        case "neutral":
            return .orange
        default:
            return .gray
        }
    }

    private var labelIcon: String {
        let label = (mlSummary.overallLabel ?? "unknown").lowercased()
        switch label {
        case "bullish":
            return "arrow.up.right"
        case "bearish":
            return "arrow.down.right"
        case "neutral":
            return "arrow.left.and.right"
        default:
            return "questionmark"
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Compact header (always visible)
            CompactMLHeader(
                mlSummary: mlSummary,
                labelColor: labelColor,
                labelIcon: labelIcon,
                isExpanded: $isExpanded
            )

            // Expanded details (toggle)
            if isExpanded {
                Divider()
                    .padding(.vertical, 8)

                ExpandedMLDetails(mlSummary: mlSummary, labelColor: labelColor)
                    .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color(nsColor: .controlBackgroundColor))
                .shadow(color: .black.opacity(0.1), radius: 4, x: 0, y: 2)
        )
        .animation(.easeInOut(duration: 0.2), value: isExpanded)
    }
}

struct CompactMLHeader: View {
    let mlSummary: MLSummary
    let labelColor: Color
    let labelIcon: String
    @Binding var isExpanded: Bool

    private var horizonSummary: String {
        mlSummary.horizons.map { series in
            let change = calculateChange(for: series)
            return "\(series.horizon): \(change)"
        }.joined(separator: " • ")
    }

    private func calculateChange(for series: ForecastSeries) -> String {
        guard let point = series.points.first else { return "N/A" }
        // This is a placeholder - in real implementation, compare to current price
        return String(format: "%+.1f%%", (point.value - point.lower) / point.value * 100)
    }

    var body: some View {
        Button(action: { isExpanded.toggle() }) {
            HStack(spacing: 12) {
                // Icon
                Image(systemName: "brain.head.profile")
                    .foregroundStyle(.purple)
                    .font(.title3)

                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 6) {
                        Text("ML Forecast")
                            .font(.caption.bold())
                            .foregroundStyle(.primary)

                        Divider()
                            .frame(height: 12)

                        Image(systemName: labelIcon)
                            .font(.caption)
                        Text((mlSummary.overallLabel ?? "UNKNOWN").uppercased())
                            .font(.caption.bold())
                    }
                    .foregroundStyle(labelColor)

                    Text(horizonSummary)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }

                Spacer()

                // Confidence
                VStack(alignment: .trailing, spacing: 2) {
                    Text("\(Int(mlSummary.confidence * 100))%")
                        .font(.title3.bold())
                        .foregroundStyle(labelColor)

                    Text("Confidence")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }

                // Expand indicator
                Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .buttonStyle(.plain)
    }
}

struct ExpandedMLDetails: View {
    let mlSummary: MLSummary
    let labelColor: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Confidence breakdown (simulated)
            VStack(alignment: .leading, spacing: 8) {
                Text("Confidence Breakdown")
                    .font(.caption.bold())
                    .foregroundStyle(.secondary)

                ConfidenceFactorRow(
                    label: "Technical Indicators",
                    percentage: min(100, Int(mlSummary.confidence * 120)),
                    color: labelColor
                )

                ConfidenceFactorRow(
                    label: "Price Momentum",
                    percentage: min(100, Int(mlSummary.confidence * 95)),
                    color: labelColor
                )

                ConfidenceFactorRow(
                    label: "Volume Pattern",
                    percentage: min(100, Int(mlSummary.confidence * 105)),
                    color: labelColor
                )
            }

            Divider()

            // Horizon details
            VStack(alignment: .leading, spacing: 8) {
                Text("Forecast Horizons")
                    .font(.caption.bold())
                    .foregroundStyle(.secondary)

                ForEach(mlSummary.horizons, id: \.horizon) { series in
                    HorizonDetailRow(series: series, labelColor: labelColor)
                }
            }
        }
    }
}

struct ConfidenceFactorRow: View {
    let label: String
    let percentage: Int
    let color: Color

    var body: some View {
        HStack {
            Text(label)
                .font(.caption2)

            Spacer()

            Text("\(percentage)%")
                .font(.caption2.bold())
                .foregroundStyle(color)

            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Color.gray.opacity(0.2))

                    RoundedRectangle(cornerRadius: 2)
                        .fill(color)
                        .frame(width: geometry.size.width * Double(percentage) / 100)
                }
            }
            .frame(width: 60, height: 4)
        }
    }
}

struct HorizonDetailRow: View {
    let series: ForecastSeries
    let labelColor: Color

    private var targetPrice: Double? {
        series.points.first?.value
    }

    private var priceRange: String {
        guard let first = series.points.first else {
            return "N/A"
        }
        return "$\(String(format: "%.2f", first.lower))-$\(String(format: "%.2f", first.upper))"
    }

    var body: some View {
        HStack {
            Text(series.horizon)
                .font(.caption.bold())
                .frame(width: 40, alignment: .leading)

            if let target = targetPrice {
                Text("$\(String(format: "%.2f", target))")
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(labelColor)
            }

            Spacer()

            Text(priceRange)
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .padding(.vertical, 4)
    }
}

struct HorizonBadge: View {
    let horizon: String

    var body: some View {
        Text(horizon)
            .font(.caption.bold())
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(Color.accentColor.opacity(0.1))
            .foregroundStyle(.secondary)
            .clipShape(RoundedRectangle(cornerRadius: 6))
    }
}

#Preview {
    MLReportCard(mlSummary: MLSummary(
        overallLabel: "bullish",
        confidence: 0.78,
        horizons: [
            ForecastSeries(horizon: "1D", points: [
                ForecastPoint(ts: 1734186600, value: 248.13, lower: 247.43, upper: 248.83)
            ]),
            ForecastSeries(horizon: "1W", points: [
                ForecastPoint(ts: 1734186600, value: 249.29, lower: 246.54, upper: 252.04)
            ])
        ],
        srLevels: nil,
        srDensity: nil
    ))
    .padding()
    .frame(width: 300)
}
