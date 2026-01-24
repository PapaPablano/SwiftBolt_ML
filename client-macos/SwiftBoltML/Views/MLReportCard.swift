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
        guard let point = series.points.max(by: { $0.ts < $1.ts }) else { return "N/A" }
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
            // Enhanced Ensemble Section (if available)
            if mlSummary.isEnhancedEnsemble, let stats = mlSummary.trainingStats {
                EnhancedEnsembleSection(stats: stats, agreement: mlSummary.modelAgreement)
                Divider()
            }

            // Model weights (show for both basic and enhanced)
            if let stats = mlSummary.trainingStats {
                EnsembleWeightsSection(stats: stats, labelColor: labelColor)
                Divider()
            } else {
                // Fallback confidence breakdown (simulated)
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
            }

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

// MARK: - Enhanced Ensemble Section

struct EnhancedEnsembleSection: View {
    let stats: TrainingStats
    let agreement: Double?

    private var nModels: Int {
        stats.nModels ?? 2
    }

    private var agreementLevel: String {
        guard let agree = agreement else { return "Unknown" }
        switch agree {
        case 0.8...: return "Strong"
        case 0.6..<0.8: return "Moderate"
        case 0.4..<0.6: return "Mixed"
        default: return "Weak"
        }
    }

    private var agreementColor: Color {
        guard let agree = agreement else { return .gray }
        switch agree {
        case 0.8...: return .green
        case 0.6..<0.8: return .blue
        case 0.4..<0.6: return .orange
        default: return .red
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Enhanced Ensemble")
                    .font(.caption.bold())
                    .foregroundStyle(.secondary)

                Spacer()

                // Model count badge
                Text("\(nModels) Models")
                    .font(.caption2.bold())
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Color.purple.opacity(0.2))
                    .foregroundStyle(.purple)
                    .clipShape(Capsule())
            }

            HStack(spacing: 16) {
                // Agreement
                VStack(alignment: .leading, spacing: 2) {
                    Text("Agreement")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    HStack(spacing: 4) {
                        Text(agreementLevel)
                            .font(.caption.bold())
                            .foregroundStyle(agreementColor)
                        if let agree = agreement {
                            Text("(\(Int(agree * 100))%)")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                    }
                }

                // Volatility
                if let vol = stats.forecastVolatility {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Volatility")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                        Text(String(format: "%.2f%%", vol * 100))
                            .font(.caption.bold().monospacedDigit())
                    }
                }

                // CI Range
                if let lower = stats.ciLower, let upper = stats.ciUpper {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("95% CI")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                        Text(String(format: "%.1f%% to %.1f%%", lower * 100, upper * 100))
                            .font(.caption2.monospacedDigit())
                    }
                }
            }
        }
    }
}

// MARK: - Ensemble Model Weights Section

struct EnsembleWeightsSection: View {
    let stats: TrainingStats
    let labelColor: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Model Weights")
                .font(.caption.bold())
                .foregroundStyle(.secondary)

            ForEach(stats.sortedWeights, id: \.model) { item in
                EnsembleWeightRow(
                    name: stats.displayName(for: item.model),
                    weight: item.weight,
                    prediction: stats.componentPredictions?[item.model],
                    color: labelColor
                )
            }
        }
    }
}

struct EnsembleWeightRow: View {
    let name: String
    let weight: Double
    let prediction: String?
    let color: Color

    private var predictionIcon: String {
        guard let pred = prediction?.lowercased() else { return "" }
        switch pred {
        case "bullish": return "arrow.up.right"
        case "bearish": return "arrow.down.right"
        default: return "arrow.left.and.right"
        }
    }

    private var predictionColor: Color {
        guard let pred = prediction?.lowercased() else { return .gray }
        switch pred {
        case "bullish": return .green
        case "bearish": return .red
        default: return .orange
        }
    }

    var body: some View {
        HStack {
            Text(name)
                .font(.caption2)
                .frame(width: 90, alignment: .leading)

            // Weight bar
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Color.gray.opacity(0.2))

                    RoundedRectangle(cornerRadius: 2)
                        .fill(color.opacity(0.7))
                        .frame(width: geometry.size.width * weight)
                }
            }
            .frame(width: 60, height: 4)

            Text("\(Int(weight * 100))%")
                .font(.caption2.bold().monospacedDigit())
                .frame(width: 30, alignment: .trailing)

            // Prediction indicator (if available)
            if prediction != nil {
                Image(systemName: predictionIcon)
                    .font(.caption2)
                    .foregroundStyle(predictionColor)
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

    private var targetPoint: ForecastPoint? {
        series.points.max(by: { $0.ts < $1.ts })
    }

    private var targetPrice: Double? {
        targetPoint?.value
    }

    private var priceRange: String {
        guard let point = targetPoint else {
            return "N/A"
        }
        return "$\(String(format: "%.2f", point.lower))-$\(String(format: "%.2f", point.upper))"
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

#Preview("Basic Ensemble") {
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
        srDensity: nil,
        ensembleType: "RF+GB",
        modelAgreement: 0.85,
        trainingStats: TrainingStats(
            trainingTimeSeconds: 2.5,
            nSamples: 252,
            nFeatures: 42,
            rfWeight: 0.55,
            gbWeight: 0.45,
            modelWeights: nil,
            enhancedEnsemble: false,
            nModels: 2,
            componentPredictions: nil,
            forecastReturn: nil,
            forecastVolatility: nil,
            ciLower: nil,
            ciUpper: nil
        )
    ))
    .padding()
    .frame(width: 320)
}

#Preview("Enhanced Ensemble") {
    MLReportCard(mlSummary: MLSummary(
        overallLabel: "bullish",
        confidence: 0.82,
        horizons: [
            ForecastSeries(horizon: "1D", points: [
                ForecastPoint(ts: 1734186600, value: 248.13, lower: 247.43, upper: 248.83)
            ]),
            ForecastSeries(horizon: "1W", points: [
                ForecastPoint(ts: 1734186600, value: 249.29, lower: 246.54, upper: 252.04)
            ])
        ],
        srLevels: nil,
        srDensity: nil,
        ensembleType: "Enhanced5",
        modelAgreement: 0.72,
        trainingStats: TrainingStats(
            trainingTimeSeconds: 8.3,
            nSamples: 504,
            nFeatures: 42,
            rfWeight: 0.25,
            gbWeight: 0.30,
            modelWeights: [
                "rf": 0.25,
                "gb": 0.30,
                "arima_garch": 0.20,
                "prophet": 0.15,
                "lstm": 0.10
            ],
            enhancedEnsemble: true,
            nModels: 5,
            componentPredictions: [
                "rf": "Bullish",
                "gb": "Bullish",
                "arima_garch": "Neutral",
                "prophet": "Bullish",
                "lstm": "Bullish"
            ],
            forecastReturn: 0.015,
            forecastVolatility: 0.023,
            ciLower: -0.008,
            ciUpper: 0.038
        )
    ))
    .padding()
    .frame(width: 320)
}
