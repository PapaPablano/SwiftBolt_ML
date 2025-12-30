import SwiftUI

struct SupportResistanceView: View {
    @ObservedObject var analysisViewModel: AnalysisViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Section header
            HStack {
                Image(systemName: "chart.line.uptrend.xyaxis")
                    .foregroundStyle(.cyan)
                Text("Support & Resistance")
                    .font(.headline)

                Spacer()

                if analysisViewModel.isLoadingSR {
                    ProgressView()
                        .scaleEffect(0.7)
                }
            }

            if analysisViewModel.isLoadingSR {
                ProgressView("Loading S/R levels...")
                    .frame(maxWidth: .infinity)
                    .padding()
            } else if let sr = analysisViewModel.supportResistance {
                // Main S/R content
                SRLevelsContent(sr: sr)
            } else if analysisViewModel.srError != nil {
                // Error state
                HStack {
                    Image(systemName: "exclamationmark.triangle")
                        .foregroundStyle(.orange)
                    Text("S/R data unavailable")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .padding()
            } else {
                Text("Select a symbol to view S/R levels")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity)
                    .padding()
            }
        }
        .padding()
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

// MARK: - S/R Levels Content

struct SRLevelsContent: View {
    let sr: SupportResistanceResponse

    var body: some View {
        VStack(spacing: 12) {
            // Key metrics row
            HStack(spacing: 16) {
                // Current Price
                SRMetricCard(
                    title: "Price",
                    value: String(format: "$%.2f", sr.currentPrice),
                    color: .primary
                )

                // Nearest Support
                if let support = sr.nearestSupport {
                    SRMetricCard(
                        title: "Support",
                        value: String(format: "$%.2f", support),
                        subtitle: sr.supportDistancePct.map { String(format: "%.1f%% below", $0) },
                        color: .green
                    )
                }

                // Nearest Resistance
                if let resistance = sr.nearestResistance {
                    SRMetricCard(
                        title: "Resistance",
                        value: String(format: "$%.2f", resistance),
                        subtitle: sr.resistanceDistancePct.map { String(format: "%.1f%% above", $0) },
                        color: .red
                    )
                }
            }

            Divider()

            // Bias indicator
            BiasIndicator(sr: sr)

            // Active Signals (from Logistic indicator)
            if sr.hasActiveSignals {
                SignalsSection(signals: sr.activeSignals)
            }

            Divider()

            // Multi-timeframe Pivot Levels
            if let pivots = sr.pivotLevels {
                PivotLevelsSection(pivots: pivots, currentPrice: sr.currentPrice)
            }

            // Polynomial Regression S/R
            if let polynomial = sr.polynomial {
                PolynomialSRSection(polynomial: polynomial, currentPrice: sr.currentPrice)
            }

            // Logistic ML S/R
            if let logistic = sr.logistic {
                LogisticSRSection(logistic: logistic, currentPrice: sr.currentPrice)
            }
        }
    }
}

// MARK: - S/R Metric Card

struct SRMetricCard: View {
    let title: String
    let value: String
    var subtitle: String? = nil
    let color: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)

            Text(value)
                .font(.subheadline.bold())
                .foregroundStyle(color)

            if let subtitle = subtitle {
                Text(subtitle)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(8)
        .background(color.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

// MARK: - Bias Indicator

struct BiasIndicator: View {
    let sr: SupportResistanceResponse

    private var biasColor: Color {
        switch sr.biasType {
        case .bullish: return .green
        case .bearish: return .red
        case .neutral: return .orange
        }
    }

    private var biasIcon: String {
        switch sr.biasType {
        case .bullish: return "arrow.up.right.circle.fill"
        case .bearish: return "arrow.down.right.circle.fill"
        case .neutral: return "arrow.left.and.right.circle.fill"
        }
    }

    var body: some View {
        HStack {
            Image(systemName: biasIcon)
                .font(.title2)
                .foregroundStyle(biasColor)

            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text("S/R Bias:")
                        .font(.subheadline)
                    Text(sr.biasType.rawValue)
                        .font(.subheadline.bold())
                        .foregroundStyle(biasColor)

                    if let ratio = sr.srRatio {
                        Text(String(format: "(%.2f)", ratio))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                Text(sr.biasDescription)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Spacer()
        }
        .padding(10)
        .background(biasColor.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

// MARK: - Signals Section

struct SignalsSection: View {
    let signals: [SRSignal]

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Active Signals")
                .font(.caption.bold())
                .foregroundStyle(.secondary)

            HStack(spacing: 8) {
                ForEach(signals, id: \.rawValue) { signal in
                    SignalBadge(signal: signal)
                }
            }
        }
    }
}

struct SignalBadge: View {
    let signal: SRSignal

    private var color: Color {
        signal.isBullish ? .green : .red
    }

    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: signal.icon)
                .font(.caption2)
            Text(signal.displayName)
                .font(.caption2)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(color.opacity(0.15))
        .foregroundStyle(color)
        .clipShape(Capsule())
    }
}

// MARK: - Multi-Timeframe Pivot Levels Section

struct PivotLevelsSection: View {
    let pivots: PivotLevelsResponse
    let currentPrice: Double

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Multi-Timeframe Pivots")
                .font(.caption.bold())
                .foregroundStyle(.secondary)

            VStack(spacing: 4) {
                ForEach(pivots.allPeriods, id: \.name) { period in
                    if let data = period.period {
                        PivotPeriodRow(name: period.name, pivot: data, currentPrice: currentPrice)
                    }
                }
            }
        }
    }
}

struct PivotPeriodRow: View {
    let name: String
    let pivot: PivotLevelPeriodResponse
    let currentPrice: Double

    var body: some View {
        HStack {
            Text(name)
                .font(.caption)
                .foregroundStyle(.secondary)
                .frame(width: 50, alignment: .leading)

            // Low (Support)
            if let low = pivot.low {
                PivotLevelBadge(
                    label: "Low",
                    value: low,
                    status: pivot.lowStatusEnum,
                    currentPrice: currentPrice
                )
            }

            Spacer()

            // High (Resistance)
            if let high = pivot.high {
                PivotLevelBadge(
                    label: "High",
                    value: high,
                    status: pivot.highStatusEnum,
                    currentPrice: currentPrice
                )
            }
        }
        .padding(.vertical, 2)
    }
}

struct PivotLevelBadge: View {
    let label: String
    let value: Double
    let status: PivotStatus
    let currentPrice: Double

    private var statusColor: Color {
        switch status {
        case .support: return .green
        case .resistance: return .red
        case .active: return .blue
        case .inactive: return .gray
        }
    }

    private var isNearPrice: Bool {
        abs(value - currentPrice) / currentPrice < 0.02
    }

    var body: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(statusColor)
                .frame(width: 6, height: 6)

            Text(String(format: "%.2f", value))
                .font(.caption)
                .foregroundStyle(.primary)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(isNearPrice ? statusColor.opacity(0.2) : Color(nsColor: .windowBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 4))
        .overlay(
            RoundedRectangle(cornerRadius: 4)
                .stroke(isNearPrice ? statusColor : Color.clear, lineWidth: 1)
        )
    }
}

// MARK: - Polynomial Regression S/R Section

struct PolynomialSRSection: View {
    let polynomial: PolynomialSRResponse
    let currentPrice: Double

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Polynomial Regression S/R")
                    .font(.caption.bold())
                    .foregroundStyle(.secondary)

                Spacer()

                // Trend badges
                if polynomial.isConverging {
                    SRTrendBadge(text: "Squeeze", color: .purple)
                } else if polynomial.isDiverging {
                    SRTrendBadge(text: "Expansion", color: .orange)
                }
            }

            HStack(spacing: 12) {
                // Support with trend
                if let support = polynomial.support {
                    PolySRCard(
                        title: "Support",
                        value: support,
                        trend: polynomial.supportTrend,
                        currentPrice: currentPrice,
                        isSupport: true
                    )
                }

                // Resistance with trend
                if let resistance = polynomial.resistance {
                    PolySRCard(
                        title: "Resistance",
                        value: resistance,
                        trend: polynomial.resistanceTrend,
                        currentPrice: currentPrice,
                        isSupport: false
                    )
                }
            }

            // Forecast preview
            if let forecastS = polynomial.forecastSupport?.first,
               let forecastR = polynomial.forecastResistance?.first {
                HStack {
                    Text("Next bar forecast:")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Text(String(format: "S: $%.2f", forecastS))
                        .font(.caption2)
                        .foregroundStyle(.green)
                    Text("|")
                        .foregroundStyle(.secondary)
                    Text(String(format: "R: $%.2f", forecastR))
                        .font(.caption2)
                        .foregroundStyle(.red)
                }
            }
        }
    }
}

struct PolySRCard: View {
    let title: String
    let value: Double
    let trend: TrendDirection
    let currentPrice: Double
    let isSupport: Bool

    private var color: Color {
        isSupport ? .green : .red
    }

    private var trendColor: Color {
        switch trend {
        case .rising: return .green
        case .falling: return .red
        case .flat: return .gray
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(title)
                    .font(.caption2)
                    .foregroundStyle(.secondary)

                Image(systemName: trend.icon)
                    .font(.caption2)
                    .foregroundStyle(trendColor)
            }

            Text(String(format: "$%.2f", value))
                .font(.caption.bold())
                .foregroundStyle(color)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(6)
        .background(color.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 6))
    }
}

struct SRTrendBadge: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text)
            .font(.caption2)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(color.opacity(0.15))
            .foregroundStyle(color)
            .clipShape(Capsule())
    }
}

// MARK: - Logistic ML S/R Section

struct LogisticSRSection: View {
    let logistic: LogisticSRResponse
    let currentPrice: Double

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("ML-Detected S/R (Logistic Regression)")
                .font(.caption.bold())
                .foregroundStyle(.secondary)

            HStack(alignment: .top, spacing: 12) {
                // Support levels
                VStack(alignment: .leading, spacing: 4) {
                    Text("Support")
                        .font(.caption2)
                        .foregroundStyle(.green)

                    if let levels = logistic.supportLevels, !levels.isEmpty {
                        ForEach(levels.prefix(3)) { level in
                            LogisticLevelRow(level: level, currentPrice: currentPrice, isSupport: true)
                        }
                    } else {
                        Text("None")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)

                Divider()
                    .frame(height: 60)

                // Resistance levels
                VStack(alignment: .leading, spacing: 4) {
                    Text("Resistance")
                        .font(.caption2)
                        .foregroundStyle(.red)

                    if let levels = logistic.resistanceLevels, !levels.isEmpty {
                        ForEach(levels.prefix(3)) { level in
                            LogisticLevelRow(level: level, currentPrice: currentPrice, isSupport: false)
                        }
                    } else {
                        Text("None")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }
}

struct LogisticLevelRow: View {
    let level: LogisticLevelResponse
    let currentPrice: Double
    let isSupport: Bool

    private var color: Color {
        isSupport ? .green : .red
    }

    private var confidenceColor: Color {
        switch level.confidence {
        case .high: return .green
        case .medium: return .orange
        case .low: return .gray
        }
    }

    private var isNearPrice: Bool {
        abs(level.level - currentPrice) / currentPrice < 0.02
    }

    var body: some View {
        HStack(spacing: 6) {
            Text(String(format: "$%.2f", level.level))
                .font(.caption2)
                .foregroundStyle(color)

            // Probability badge
            Text(level.probabilityText)
                .font(.system(size: 9))
                .padding(.horizontal, 4)
                .padding(.vertical, 1)
                .background(confidenceColor.opacity(0.2))
                .foregroundStyle(confidenceColor)
                .clipShape(RoundedRectangle(cornerRadius: 3))

            // Times respected (if available)
            if let times = level.timesRespected, times > 0 {
                Text("×\(times)")
                    .font(.system(size: 9))
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 2)
        .padding(.horizontal, 4)
        .background(isNearPrice ? color.opacity(0.1) : Color.clear)
        .clipShape(RoundedRectangle(cornerRadius: 4))
    }
}

#Preview {
    SupportResistanceView(analysisViewModel: AnalysisViewModel())
        .frame(width: 400)
        .padding()
}
