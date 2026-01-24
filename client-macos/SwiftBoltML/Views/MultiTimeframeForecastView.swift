import SwiftUI

// MARK: - Improvements 6-7: Multi-Timeframe Forecast UX Enhancements

/// Grid view showing forecasts across multiple timeframes
struct MultiTimeframeForecastGridView: View {
    @ObservedObject var chartViewModel: ChartViewModel
    let currentPrice: Double?

    // Timeframe presets
    enum TimeframePreset: String, CaseIterable {
        case swing = "Swing"   // w1, d1, h4
        case day = "Day"       // d1, h1, m15
        case all = "All"       // all 5

        var timeframes: [String] {
            switch self {
            case .swing: return ["w1", "d1", "h4"]
            case .day: return ["d1", "h1", "m15"]
            case .all: return ["m15", "h1", "h4", "d1", "w1"]
            }
        }
    }

    @State private var selectedPreset: TimeframePreset = .all

    private var filteredForecasts: [(String, ChartResponse)] {
        chartViewModel.multiTimeframeForecasts
            .filter { selectedPreset.timeframes.contains($0.key) }
            .sorted { lhs, rhs in
                let order = ["m15", "h1", "h4", "d1", "w1"]
                return (order.firstIndex(of: lhs.key) ?? 0) < (order.firstIndex(of: rhs.key) ?? 0)
            }
    }

    var body: some View {
        VStack(spacing: 12) {
            // Preset selector
            HStack {
                Text("Timeframe Preset")
                    .font(.caption)
                    .foregroundStyle(.secondary)

                Picker("", selection: $selectedPreset) {
                    ForEach(TimeframePreset.allCases, id: \.self) { preset in
                        Text(preset.rawValue).tag(preset)
                    }
                }
                .pickerStyle(.segmented)
                .frame(maxWidth: 200)

                Spacer()

                // Refresh button
                Button(action: {
                    Task { await chartViewModel.loadMultiTimeframeForecasts() }
                }) {
                    Image(systemName: "arrow.clockwise")
                        .font(.caption)
                }
                .buttonStyle(.borderless)
                .disabled(chartViewModel.isLoadingMultiTimeframe)
            }
            .padding(.horizontal)

            if chartViewModel.isLoadingMultiTimeframe {
                ProgressView("Loading multi-timeframe forecasts...")
                    .padding()
            } else if filteredForecasts.isEmpty {
                Text("No forecast data available")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .padding()
            } else {
                // Grid of forecast cards
                LazyVGrid(columns: [
                    GridItem(.flexible(), spacing: 12),
                    GridItem(.flexible(), spacing: 12),
                    GridItem(.flexible(), spacing: 12)
                ], spacing: 12) {
                    ForEach(filteredForecasts, id: \.0) { timeframe, response in
                        MultiTimeframeForecastCard(
                            timeframe: timeframe,
                            response: response,
                            currentPrice: currentPrice
                        )
                    }
                }
                .padding(.horizontal)
            }
        }
        .padding(.vertical, 8)
        .background(Color(nsColor: .controlBackgroundColor).opacity(0.5))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

/// Individual forecast card for a single timeframe
struct MultiTimeframeForecastCard: View {
    let timeframe: String
    let response: ChartResponse
    let currentPrice: Double?

    private var mlSummary: MLSummary? {
        response.mlSummary
    }

    private var labelColor: Color {
        switch mlSummary?.overallLabel?.lowercased() {
        case "bullish": return .green
        case "bearish": return .red
        case "neutral": return .orange
        default: return .gray
        }
    }

    private var labelIcon: String {
        switch mlSummary?.overallLabel?.lowercased() {
        case "bullish": return "arrow.up.right"
        case "bearish": return "arrow.down.right"
        case "neutral": return "arrow.left.and.right"
        default: return "questionmark"
        }
    }

    private var targetPrice: Double? {
        mlSummary?.horizons.first?.points.last?.value
    }

    private var deltaPct: Double? {
        guard let target = targetPrice, let current = currentPrice, current > 0 else { return nil }
        return ((target - current) / current) * 100
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Header
            HStack {
                Text(timeframe.uppercased())
                    .font(.caption.bold())
                    .foregroundStyle(.secondary)

                Spacer()

                if let summary = mlSummary {
                    HStack(spacing: 4) {
                        Image(systemName: labelIcon)
                            .font(.caption)
                        Text("\(Int(summary.confidence * 100))%")
                            .font(.caption.bold())
                    }
                    .foregroundStyle(labelColor)
                }
            }

            // Prediction label
            if let label = mlSummary?.overallLabel {
                Text(label.uppercased())
                    .font(.headline.bold())
                    .foregroundStyle(labelColor)
            } else {
                Text("NO DATA")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
            }

            // Target and delta
            if let target = targetPrice {
                HStack {
                    Text("$\(String(format: "%.2f", target))")
                        .font(.subheadline)
                        .foregroundStyle(.primary)

                    if let delta = deltaPct {
                        Text(delta >= 0 ? "+\(String(format: "%.1f", delta))%" : "\(String(format: "%.1f", delta))%")
                            .font(.caption)
                            .foregroundStyle(delta >= 0 ? .green : .red)
                    }
                }
            }

            // Bar count indicator
            Text("\(response.bars.count) bars")
                .font(.caption2)
                .foregroundStyle(.tertiary)
        }
        .padding(10)
        .background(labelColor.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(labelColor.opacity(0.3), lineWidth: 1)
        )
    }
}

// MARK: - Previews

#if DEBUG
struct MultiTimeframeForecastView_Previews: PreviewProvider {
    static var previews: some View {
        MultiTimeframeForecastGridView(
            chartViewModel: ChartViewModel(),
            currentPrice: 150.0
        )
        .frame(width: 600, height: 400)
    }
}
#endif
