import SwiftUI

struct MLReportCard: View {
    let mlSummary: MLSummary

    private var labelColor: Color {
        switch mlSummary.overallLabel.lowercased() {
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
        switch mlSummary.overallLabel.lowercased() {
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
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack {
                Image(systemName: "brain.head.profile")
                    .foregroundStyle(.purple)
                Text("ML Forecast")
                    .font(.headline)
                Spacer()
            }

            // Overall Prediction
            HStack(spacing: 12) {
                // Label Badge
                HStack(spacing: 6) {
                    Image(systemName: labelIcon)
                    Text(mlSummary.overallLabel.capitalized)
                        .font(.subheadline.bold())
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(labelColor.opacity(0.15))
                .foregroundStyle(labelColor)
                .clipShape(RoundedRectangle(cornerRadius: 8))

                // Confidence Bar
                VStack(alignment: .leading, spacing: 4) {
                    Text("Confidence")
                        .font(.caption2)
                        .foregroundStyle(.secondary)

                    GeometryReader { geometry in
                        ZStack(alignment: .leading) {
                            // Background
                            RoundedRectangle(cornerRadius: 4)
                                .fill(Color.gray.opacity(0.2))

                            // Confidence fill
                            RoundedRectangle(cornerRadius: 4)
                                .fill(labelColor)
                                .frame(width: geometry.size.width * mlSummary.confidence)
                        }
                        .frame(height: 6)
                        .overlay(alignment: .trailing) {
                            Text("\(Int(mlSummary.confidence * 100))%")
                                .font(.caption2.bold())
                                .foregroundStyle(labelColor)
                                .padding(.trailing, 4)
                        }
                    }
                    .frame(height: 20)
                }
            }

            // Horizons
            HStack(spacing: 8) {
                ForEach(mlSummary.horizons, id: \.horizon) { series in
                    HorizonBadge(horizon: series.horizon)
                }
            }
        }
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color(nsColor: .controlBackgroundColor))
                .shadow(color: .black.opacity(0.1), radius: 4, x: 0, y: 2)
        )
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
        ]
    ))
    .padding()
    .frame(width: 300)
}
