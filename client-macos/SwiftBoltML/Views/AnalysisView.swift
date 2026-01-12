import SwiftUI

struct AnalysisView: View {
    @EnvironmentObject var appViewModel: AppViewModel
    @StateObject private var analysisViewModel = AnalysisViewModel()
    @State private var loadTask: Task<Void, Never>?

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

                // Support & Resistance Section
                SupportResistanceView(analysisViewModel: analysisViewModel)

                // Technical Summary Section
                TechnicalSummarySection(chartViewModel: chartViewModel)
            }
            .padding()
        }
        .background(Color(nsColor: .windowBackgroundColor))
        .onChange(of: appViewModel.selectedSymbol) { oldValue, newValue in
            loadTask?.cancel()
            if let symbol = newValue?.ticker {
                loadTask = Task {
                    await analysisViewModel.loadAlerts(for: symbol)
                    if !Task.isCancelled {
                        await analysisViewModel.loadEnhancedInsights(for: symbol)
                    }
                    if !Task.isCancelled {
                        await analysisViewModel.loadSupportResistance(for: symbol)
                    }
                }
            }
        }
        .onAppear {
            loadTask?.cancel()
            if let symbol = appViewModel.selectedSymbol?.ticker {
                loadTask = Task {
                    await analysisViewModel.loadAlerts(for: symbol)
                    if !Task.isCancelled {
                        await analysisViewModel.loadEnhancedInsights(for: symbol)
                    }
                    if !Task.isCancelled {
                        await analysisViewModel.loadSupportResistance(for: symbol)
                    }
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
    @State private var selectedHorizon: String? = nil

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
                mlSummary: mlSummary,
                selectedHorizon: $selectedHorizon
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
