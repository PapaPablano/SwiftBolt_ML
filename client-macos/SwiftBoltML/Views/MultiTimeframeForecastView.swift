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

        var timeframes: [Timeframe] {
            switch self {
            case .swing: return [.w1, .d1, .h4]
            case .day: return [.d1, .h1, .m15]
            case .all: return Timeframe.allOrdered
            }
        }
    }

    @State private var selectedPreset: TimeframePreset = .all

    // Local model for a mapped forecast entry
    private struct ForecastEntry {
        let key: String
        let timeframe: Timeframe?
        let response: ChartResponse
    }

    private var filteredForecasts: [ForecastEntry] {
        // Map backend keys (strings) to Timeframe enum when possible.
        let mapped = chartViewModel.multiTimeframeForecasts.compactMap { (key, response) -> ForecastEntry? in
            if let tf = Timeframe(from: key) {
                return ForecastEntry(key: key, timeframe: tf, response: response)
            } else {
                // Keep unknown keys only when showing the full set to help surface bad data
                if selectedPreset == .all {
                    return ForecastEntry(key: key, timeframe: nil, response: response)
                }
                return nil
            }
        }

        // Filter by preset and sort by canonical order (unknowns at end)
        let filtered = mapped.filter { entry in
            if let tf = entry.timeframe {
                return selectedPreset.timeframes.contains(tf)
            }
            return selectedPreset == .all
        }

        return filtered.sorted { lhs, rhs in
            switch (lhs.timeframe, rhs.timeframe) {
            case let (l?, r?): return l.orderIndex < r.orderIndex
            case (_, nil): return true
            case (nil, _): return false
            }
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
                    ForEach(filteredForecasts, id: \.key) { entry in
                        MultiTimeframeForecastCard(
                            timeframe: entry.timeframe,
                            timeframeLabel: entry.key,
                            response: entry.response,
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
    // Accept either a known Timeframe or a raw label for unknown/legacy tokens
    let timeframe: Timeframe?
    let timeframeLabel: String
    let response: ChartResponse
    let currentPrice: Double?

    private var mlSummary: MLSummary? {
        response.mlSummary
    }

    // Color mapping for labels (normalized)
    private var labelColor: Color {
        guard let raw = mlSummary?.overallLabel?.lowercased() else { return .gray }
        switch raw {
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

    private func clampedConfidencePercent() -> Int? {
        guard let c = mlSummary?.confidence else { return nil }
        if c.isNaN { return nil }
        let pct = Int((min(max(c, 0.0), 1.0)) * 100.0)
        return pct
    }

    private func confidenceTier(_ pct: Int) -> String {
        switch pct {
        case 0..<40: return "Low"
        case 40..<70: return "Medium"
        default: return "High"
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Header
            HStack {
                Text(timeframe?.displayName ?? timeframeLabel.uppercased())
                    .font(.caption.bold())
                    .foregroundStyle(.secondary)

                Spacer()

                if mlSummary != nil {
                    HStack(spacing: 6) {
                        Image(systemName: labelIcon)
                            .font(.caption)
                        if let pct = clampedConfidencePercent() {
                            Text("\(pct)%")
                                .font(.caption.bold())
                                .accessibilityLabel(Text("Confidence \(pct) percent"))
                        } else {
                            Text("—")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
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
                    } else {
                        Text("—")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }

            // Bar count indicator
            Text("\(response.bars.count) bars")
                .font(.caption2)
                .foregroundStyle(.tertiary)
        }
        .padding(10)
        .background(labelColor.opacity(0.12))
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(labelColor.opacity(0.22), lineWidth: 1)
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
