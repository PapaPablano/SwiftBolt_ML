import SwiftUI

struct AnalysisView: View {
    @EnvironmentObject var appViewModel: AppViewModel
    @StateObject private var analysisViewModel = AnalysisViewModel()

    private var chartViewModel: ChartViewModel {
        appViewModel.chartViewModel
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                // Scanner Alerts Section
                AlertsSection(analysisViewModel: analysisViewModel)

                Divider()

                // ML Forecast Breakdown Section
                if let mlSummary = chartViewModel.chartData?.mlSummary {
                    let referencePrice = chartViewModel.liveQuote?.last ?? chartViewModel.bars.last?.close
                    MLForecastBreakdownSection(
                        mlSummary: mlSummary,
                        referencePrice: referencePrice
                    )
                    Divider()
                }
                
                // Enhanced ML Insights Section
                EnhancedInsightsSection(analysisViewModel: analysisViewModel)

                Divider()

                // Statistical Relevance Scores Section
                StatisticalRelevanceSection(analysisViewModel: analysisViewModel)

                Divider()

                // Support & Resistance Section
                SupportResistanceView(analysisViewModel: analysisViewModel)

                // Technical Summary Section
                TechnicalSummarySection(chartViewModel: chartViewModel)
            }
            .padding()
        }
        .background(Color(nsColor: .windowBackgroundColor))
        .onChange(of: appViewModel.selectedSymbol) { oldValue, newValue in
            if let symbol = newValue?.ticker {
                Task {
                    await analysisViewModel.loadAlerts(for: symbol)
                    await analysisViewModel.loadEnhancedInsights(for: symbol)
                    await analysisViewModel.loadSupportResistance(for: symbol)
                }
            }
        }
        .onAppear {
            if let symbol = appViewModel.selectedSymbol?.ticker {
                Task {
                    await analysisViewModel.loadAlerts(for: symbol)
                    await analysisViewModel.loadEnhancedInsights(for: symbol)
                    await analysisViewModel.loadSupportResistance(for: symbol)
                }
            }
        }
    }
}

// MARK: - Alerts Section

struct AlertsSection: View {
    @ObservedObject var analysisViewModel: AnalysisViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "bell.fill")
                    .foregroundStyle(.orange)
                Text("Active Alerts")
                    .font(.headline)

                Spacer()

                if analysisViewModel.unreadCount > 0 {
                    Text("\(analysisViewModel.unreadCount)")
                        .font(.caption.bold())
                        .foregroundStyle(.white)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.orange)
                        .clipShape(Capsule())
                }
            }

            if analysisViewModel.isLoadingAlerts {
                ProgressView()
                    .frame(maxWidth: .infinity)
                    .padding()
            } else if let error = analysisViewModel.alertsError {
                AnalysisErrorBanner(message: error) {
                    // Retry logic would go here
                }
            } else if analysisViewModel.alerts.isEmpty {
                EmptyAlertsView()
            } else {
                VStack(spacing: 8) {
                    // Critical alerts
                    ForEach(analysisViewModel.criticalAlerts) { alert in
                        AlertRow(alert: alert)
                    }

                    // Warning alerts
                    ForEach(analysisViewModel.warningAlerts) { alert in
                        AlertRow(alert: alert)
                    }

                    // Info alerts (limit to 3)
                    ForEach(analysisViewModel.infoAlerts.prefix(3)) { alert in
                        AlertRow(alert: alert)
                    }
                }
            }
        }
        .padding()
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

struct AlertRow: View {
    let alert: ScannerAlert

    var body: some View {
        HStack(spacing: 12) {
            // Severity icon
            Image(systemName: alert.severityIcon)
                .foregroundStyle(alert.severityColor)
                .frame(width: 24)

            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(alert.conditionLabel)
                        .font(.subheadline.bold())

                    Spacer()

                    if alert.conditionType != nil {
                        Image(systemName: alert.conditionTypeIcon)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                if let date = alert.triggeredDate {
                    Text(timeAgo(from: date))
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()
        }
        .padding(10)
        .background(alert.severityColor.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(alert.severityColor.opacity(0.3), lineWidth: 1)
        )
    }

    private func timeAgo(from date: Date) -> String {
        let interval = Date().timeIntervalSince(date)
        let minutes = Int(interval / 60)
        let hours = Int(interval / 3600)
        let days = Int(interval / 86400)

        if days > 0 {
            return "\(days)d ago"
        } else if hours > 0 {
            return "\(hours)h ago"
        } else if minutes > 0 {
            return "\(minutes)m ago"
        } else {
            return "just now"
        }
    }
}

struct EmptyAlertsView: View {
    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: "checkmark.circle")
                .font(.largeTitle)
                .foregroundStyle(.green)
            Text("No active alerts")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding()
    }
}

// MARK: - ML Forecast Breakdown Section

struct MLForecastBreakdownSection: View {
    let mlSummary: MLSummary
    let referencePrice: Double?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "brain.head.profile")
                    .foregroundStyle(.purple)
                Text("ML Forecast Breakdown")
                    .font(.headline)
            }

            // Overall prediction
            HStack(spacing: 12) {
                HStack(spacing: 6) {
                    let label = mlSummary.overallLabel ?? "unknown"
                    Image(systemName: labelIcon(for: label))
                    Text(label.uppercased())
                        .font(.title3.bold())
                }
                .foregroundStyle(labelColor(for: mlSummary.overallLabel ?? "unknown"))

                Spacer()

                Text("\(Int(mlSummary.confidence * 100))%")
                    .font(.title2.bold())
                    .foregroundStyle(labelColor(for: mlSummary.overallLabel ?? "unknown"))
            }
            .padding()
            .background(labelColor(for: mlSummary.overallLabel ?? "unknown").opacity(0.1))
            .clipShape(RoundedRectangle(cornerRadius: 12))

            ForecastHorizonsView(
                horizons: mlSummary.horizons,
                currentPrice: referencePrice,
                mlSummary: mlSummary
            )
        }
        .padding()
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func labelColor(for label: String) -> Color {
        switch label.lowercased() {
        case "bullish": return .green
        case "bearish": return .red
        case "neutral": return .orange
        default: return .gray
        }
    }

    private func labelIcon(for label: String) -> String {
        switch label.lowercased() {
        case "bullish": return "arrow.up.right"
        case "bearish": return "arrow.down.right"
        case "neutral": return "arrow.left.and.right"
        default: return "questionmark"
        }
    }
}

// MARK: - Technical Summary Section

struct TechnicalSummarySection: View {
    @ObservedObject var chartViewModel: ChartViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "waveform.path.ecg")
                    .foregroundStyle(.blue)
                Text("Technical Summary")
                    .font(.headline)
            }

            VStack(spacing: 8) {
                // RSI
                if let rsi = chartViewModel.rsi.last,
                   let rsiValue = rsi.value {
                    TechnicalIndicatorRow(
                        name: "RSI(14)",
                        value: String(format: "%.1f", rsiValue),
                        status: rsiStatus(rsiValue),
                        statusColor: rsiColor(rsiValue)
                    )
                }

                // Volume
                if let bars = chartViewModel.chartData?.bars,
                   bars.count >= 20 {
                    let avgVolume = bars.suffix(20).map { $0.volume }.reduce(0, +) / 20
                    let currentVolume = bars.last?.volume ?? 0
                    let volumeRatio = currentVolume / avgVolume

                    TechnicalIndicatorRow(
                        name: "Volume",
                        value: formatVolume(currentVolume),
                        status: volumeRatio > 1.5 ? "Above Average" : volumeRatio < 0.5 ? "Below Average" : "Normal",
                        statusColor: volumeRatio > 1.5 ? .green : volumeRatio < 0.5 ? .orange : .secondary
                    )
                }

                // Moving averages
                if let sma20 = chartViewModel.sma20.last,
                   let sma20Value = sma20.value,
                   let currentPrice = chartViewModel.bars.last?.close {
                    TechnicalIndicatorRow(
                        name: "Price vs SMA(20)",
                        value: String(format: "%.2f%%", ((currentPrice - sma20Value) / sma20Value) * 100),
                        status: currentPrice > sma20Value ? "Above" : "Below",
                        statusColor: currentPrice > sma20Value ? .green : .red
                    )
                }
            }
        }
        .padding()
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func rsiStatus(_ value: Double) -> String {
        if value >= 70 {
            return "Overbought"
        } else if value <= 30 {
            return "Oversold"
        } else {
            return "Neutral"
        }
    }

    private func rsiColor(_ value: Double) -> Color {
        if value >= 70 {
            return .red
        } else if value <= 30 {
            return .green
        } else {
            return .orange
        }
    }

    private func formatVolume(_ volume: Double) -> String {
        if volume >= 1_000_000 {
            return String(format: "%.1fM", volume / 1_000_000)
        } else if volume >= 1_000 {
            return String(format: "%.1fK", volume / 1_000)
        }
        return String(format: "%.0f", volume)
    }
}

struct TechnicalIndicatorRow: View {
    let name: String
    let value: String
    let status: String
    let statusColor: Color

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(name)
                    .font(.subheadline)
                Text(value)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            Text(status)
                .font(.caption.bold())
                .foregroundStyle(statusColor)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(statusColor.opacity(0.15))
                .clipShape(RoundedRectangle(cornerRadius: 6))
        }
        .padding(10)
        .background(Color(nsColor: .windowBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

// MARK: - Enhanced Insights Section

struct EnhancedInsightsSection: View {
    @ObservedObject var analysisViewModel: AnalysisViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Section header
            HStack {
                Image(systemName: "sparkles")
                    .foregroundStyle(.purple)
                Text("Enhanced ML Insights")
                    .font(.headline)
                
                Spacer()
                
                if analysisViewModel.isLoadingEnhancedInsights {
                    ProgressView()
                        .scaleEffect(0.7)
                }
            }
            
            if analysisViewModel.isLoadingEnhancedInsights {
                ProgressView("Loading insights...")
                    .frame(maxWidth: .infinity)
                    .padding()
            } else {
                // Multi-Timeframe Consensus
                if let consensus = analysisViewModel.multiTimeframeConsensus {
                    MultiTimeframeConsensusView(consensus: consensus)
                }
                
                // Forecast Explainer
                if let explanation = analysisViewModel.forecastExplanation {
                    ForecastExplainerView(explanation: explanation)
                }
                
                // Data Health
                if let dataQuality = analysisViewModel.dataQuality {
                    DataHealthView(dataQuality: dataQuality)
                }
                
                // Show message if no data available
                if analysisViewModel.multiTimeframeConsensus == nil &&
                   analysisViewModel.forecastExplanation == nil &&
                   analysisViewModel.dataQuality == nil {
                    if analysisViewModel.enhancedInsightsError != nil {
                        HStack {
                            Image(systemName: "exclamationmark.triangle")
                                .foregroundStyle(.orange)
                            Text("Enhanced insights unavailable")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        .padding()
                    } else {
                        Text("Select a symbol to view enhanced insights")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .frame(maxWidth: .infinity)
                            .padding()
                    }
                }
            }
        }
        .padding()
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

// MARK: - Statistical Relevance Section

struct StatisticalRelevanceSection: View {
    @ObservedObject var analysisViewModel: AnalysisViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Section header
            HStack {
                Image(systemName: "chart.bar.xaxis")
                    .foregroundStyle(.blue)
                Text("Statistical Relevance Scores")
                    .font(.headline)

                Spacer()

                if analysisViewModel.isLoadingEnhancedInsights {
                    ProgressView()
                        .scaleEffect(0.7)
                }
            }

            if analysisViewModel.isLoadingEnhancedInsights {
                ProgressView("Loading scores...")
                    .frame(maxWidth: .infinity)
                    .padding()
            } else if let explanation = analysisViewModel.forecastExplanation {
                VStack(spacing: 16) {
                    // Feature Scores Grid
                    if !explanation.topFeatures.isEmpty {
                        FeatureScoresGrid(features: explanation.topFeatures)
                    }

                    // Signal Category Scores
                    if !explanation.signalBreakdown.isEmpty {
                        SignalCategoryScoresView(breakdown: explanation.signalBreakdown)
                    }

                    // Model Confidence Score
                    if let consensus = analysisViewModel.multiTimeframeConsensus {
                        ModelConfidenceScoreView(consensus: consensus)
                    }
                }
            } else {
                Text("Select a symbol to view statistical scores")
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

// MARK: - Feature Scores Grid

struct FeatureScoresGrid: View {
    let features: [FeatureContribution]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Feature Scores")
                .font(.subheadline.bold())
                .foregroundStyle(.secondary)

            ForEach(features, id: \.name) { feature in
                HStack {
                    // Feature name
                    Text(formatFeatureName(feature.name))
                        .font(.caption)
                        .foregroundStyle(.primary)
                        .frame(width: 120, alignment: .leading)

                    // Value with color
                    if let value = feature.value {
                        Text(formatFeatureValue(feature.name, value: value))
                            .font(.system(.caption, design: .monospaced).bold())
                            .foregroundStyle(directionColor(feature.direction))
                            .frame(width: 70, alignment: .trailing)
                    } else {
                        Text("N/A")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .frame(width: 70, alignment: .trailing)
                    }

                    // Direction indicator
                    HStack(spacing: 4) {
                        Image(systemName: directionIcon(feature.direction))
                            .font(.caption2)
                        Text(feature.direction.capitalized)
                            .font(.caption2)
                    }
                    .foregroundStyle(directionColor(feature.direction))
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(directionColor(feature.direction).opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: 4))

                    Spacer()

                    // Score bar visualization
                    if let value = feature.value {
                        ScoreBar(
                            value: normalizeValue(feature.name, value: value),
                            color: directionColor(feature.direction)
                        )
                        .frame(width: 60)
                    }
                }
                .padding(.vertical, 4)
            }
        }
        .padding(12)
        .background(Color(nsColor: .windowBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func formatFeatureName(_ name: String) -> String {
        name.replacingOccurrences(of: "_", with: " ")
            .split(separator: " ")
            .map { $0.capitalized }
            .joined(separator: " ")
    }

    private func formatFeatureValue(_ name: String, value: Double) -> String {
        if name.lowercased().contains("rsi") {
            return String(format: "%.1f", value)
        } else if name.lowercased().contains("ratio") {
            return String(format: "%.2fx", value)
        } else if name.lowercased().contains("momentum") || name.lowercased().contains("pct") {
            return String(format: "%+.1f%%", value)
        }
        return String(format: "%.2f", value)
    }

    private func normalizeValue(_ name: String, value: Double) -> Double {
        if name.lowercased().contains("rsi") {
            return value / 100.0
        } else if name.lowercased().contains("momentum") {
            return min(1.0, max(0.0, (value + 10) / 20.0))
        } else if name.lowercased().contains("ratio") {
            return min(1.0, value / 2.0)
        }
        return min(1.0, max(0.0, abs(value) / 100.0))
    }

    private func directionColor(_ direction: String) -> Color {
        switch direction.lowercased() {
        case "bullish": return .green
        case "bearish": return .red
        default: return .gray
        }
    }

    private func directionIcon(_ direction: String) -> String {
        switch direction.lowercased() {
        case "bullish": return "arrow.up.right"
        case "bearish": return "arrow.down.right"
        default: return "minus"
        }
    }
}

struct ScoreBar: View {
    let value: Double
    let color: Color

    var body: some View {
        GeometryReader { geometry in
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: 2)
                    .fill(Color.gray.opacity(0.2))
                RoundedRectangle(cornerRadius: 2)
                    .fill(color)
                    .frame(width: geometry.size.width * min(1.0, max(0.0, value)))
            }
        }
        .frame(height: 6)
    }
}

// MARK: - Signal Category Scores View

struct SignalCategoryScoresView: View {
    let breakdown: [SignalCategory]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Category Strength Scores")
                .font(.subheadline.bold())
                .foregroundStyle(.secondary)

            HStack(spacing: 12) {
                ForEach(breakdown, id: \.category) { category in
                    CategoryScoreCard(category: category)
                }
            }
        }
    }
}

struct CategoryScoreCard: View {
    let category: SignalCategory

    private var signalColor: Color {
        switch category.signal.lowercased() {
        case "bullish": return .green
        case "bearish": return .red
        default: return .orange
        }
    }

    private var categoryIcon: String {
        switch category.category.lowercased() {
        case "trend": return "chart.line.uptrend.xyaxis"
        case "momentum": return "speedometer"
        case "volatility": return "waveform.path.ecg"
        case "volume": return "chart.bar.fill"
        default: return "chart.pie"
        }
    }

    var body: some View {
        VStack(spacing: 8) {
            // Score circle
            ZStack {
                Circle()
                    .stroke(signalColor.opacity(0.2), lineWidth: 4)
                Circle()
                    .trim(from: 0, to: category.strength)
                    .stroke(signalColor, style: StrokeStyle(lineWidth: 4, lineCap: .round))
                    .rotationEffect(.degrees(-90))

                VStack(spacing: 0) {
                    Text("\(Int(category.strength * 100))")
                        .font(.system(size: 16, weight: .bold, design: .rounded))
                        .foregroundStyle(signalColor)
                    Text("%")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
            .frame(width: 50, height: 50)

            // Category info
            VStack(spacing: 2) {
                Image(systemName: categoryIcon)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text(category.category.capitalized)
                    .font(.caption2.bold())
                    .foregroundStyle(.primary)
                Text(category.signal.uppercased())
                    .font(.system(size: 9, weight: .bold))
                    .foregroundStyle(signalColor)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12)
        .background(Color(nsColor: .windowBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

// MARK: - Model Confidence Score View

struct ModelConfidenceScoreView: View {
    let consensus: MultiTimeframeConsensus

    private var signalColor: Color {
        switch consensus.signal.lowercased() {
        case "buy": return .green
        case "sell": return .red
        default: return .orange
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Model Confidence Breakdown")
                .font(.subheadline.bold())
                .foregroundStyle(.secondary)

            HStack(spacing: 16) {
                // Overall confidence
                VStack(spacing: 4) {
                    Text("\(Int(consensus.confidence * 100))%")
                        .font(.system(size: 28, weight: .bold, design: .rounded))
                        .foregroundStyle(signalColor)
                    Text("Overall")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
                .frame(width: 80)

                Divider()
                    .frame(height: 50)

                // Timeframe agreement
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Text("Bullish Timeframes:")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text("\(consensus.bullishCount)/4")
                            .font(.caption.bold())
                            .foregroundStyle(.green)
                    }

                    HStack {
                        Text("Bearish Timeframes:")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text("\(consensus.bearishCount)/4")
                            .font(.caption.bold())
                            .foregroundStyle(.red)
                    }

                    if let dominantTf = consensus.dominantTf {
                        HStack {
                            Text("Dominant Timeframe:")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            Text(dominantTf.uppercased())
                                .font(.caption.bold())
                                .foregroundStyle(.blue)
                        }
                    }
                }

                Spacer()

                // Signal value meter
                if let signalValue = consensus.signalValue {
                    VStack(spacing: 4) {
                        Text(signalValue > 0 ? "+" : "") + Text(String(format: "%.2f", signalValue))
                            .font(.system(size: 20, weight: .bold, design: .monospaced))
                        Text("Signal Value")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                    .foregroundStyle(signalValue > 0 ? .green : signalValue < 0 ? .red : .gray)
                }
            }
            .padding(12)
            .background(Color(nsColor: .windowBackgroundColor))
            .clipShape(RoundedRectangle(cornerRadius: 8))
        }
    }
}

// MARK: - Error Banner

struct AnalysisErrorBanner: View {
    let message: String
    let onRetry: () -> Void

    var body: some View {
        HStack {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(.orange)
            Text(message)
                .font(.caption)
                .foregroundStyle(.secondary)
            Spacer()
            Button("Retry", action: onRetry)
                .buttonStyle(.borderless)
                .font(.caption)
        }
        .padding(10)
        .background(Color.orange.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

#Preview {
    AnalysisView()
        .environmentObject(AppViewModel())
        .frame(width: 400, height: 600)
}
