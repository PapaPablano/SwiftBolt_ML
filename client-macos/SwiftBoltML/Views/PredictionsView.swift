import SwiftUI

struct PredictionsView: View {
    @EnvironmentObject var appViewModel: AppViewModel

    private var viewModel: PredictionsViewModel {
        appViewModel.predictionsViewModel
    }

    var body: some View {
        VStack(spacing: 0) {
            // Header
            headerSection

            // Tab selector
            Picker("", selection: Binding.deferred(get: { appViewModel.selectedPredictionsTab }, set: { appViewModel.selectedPredictionsTab = $0 })) {
                Text("Overview").tag(0)
                Text("Model Performance").tag(1)
                Text("Statistical Validation").tag(2)
                Text("Feature Importance").tag(3)
                Text("Forecast Accuracy").tag(4)
            }
            .pickerStyle(.segmented)
            .padding(.horizontal, 24)
            .padding(.vertical, 12)

            Divider()

            // Content
            if viewModel.isLoading && viewModel.dashboardData == nil {
                Spacer()
                ProgressView("Loading dashboard...")
                Spacer()
            } else if let error = viewModel.error, viewModel.dashboardData == nil {
                errorView(error)
            } else {
                ScrollView {
                    VStack(spacing: 20) {
                        switch appViewModel.selectedPredictionsTab {
                        case 0:
                            PredictionsOverviewTabView(viewModel: viewModel)
                        case 1:
                            ModelPerformanceTabView(viewModel: viewModel)
                        case 2:
                            ValidationDashboardView(viewModel: appViewModel.validationViewModel)
                        case 3:
                            FeatureImportanceTabView(viewModel: viewModel)
                        case 4:
                            ForecastAccuracyTabView()
                        default:
                            EmptyView()
                        }
                    }
                    .padding(24)
                }
            }
        }
        .background(Color(nsColor: .windowBackgroundColor))
        .onAppear {
            Task { await viewModel.loadDashboard() }
        }
    }

    private var headerSection: some View {
        HStack {
            VStack(alignment: .leading, spacing: 6) {
                Text("ML Predictions Dashboard")
                    .font(.title.bold())
                if let lastUpdated = viewModel.overview?.lastUpdatedDate {
                    Text("Last updated: \(lastUpdated, formatter: dateFormatter)")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()

            Button(action: {
                Task { await viewModel.refresh() }
            }) {
                HStack(spacing: 6) {
                    Image(systemName: "arrow.clockwise")
                    Text("Refresh")
                }
            }
            .buttonStyle(.bordered)
            .disabled(viewModel.isLoading)
        }
        .padding(24)
    }

    private func errorView(_ error: String) -> some View {
        VStack {
            Spacer()
            VStack(spacing: 16) {
                Image(systemName: "exclamationmark.triangle")
                    .font(.system(size: 48))
                    .foregroundStyle(.orange)
                Text("Failed to load dashboard")
                    .font(.title3.bold())
                Text(error)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                Button("Try Again") {
                    Task { await viewModel.refresh() }
                }
                .buttonStyle(.bordered)
            }
            Spacer()
        }
    }

    private var dateFormatter: DateFormatter {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .short
        return formatter
    }
}

// MARK: - Overview Tab

struct PredictionsOverviewTabView: View {
    @ObservedObject var viewModel: PredictionsViewModel
    @EnvironmentObject var appViewModel: AppViewModel
    @StateObject private var qualityViewModel = ForecastQualityViewModel()

    var body: some View {
        VStack(spacing: 20) {
            // Key Metrics Row
            if let overview = viewModel.overview {
                HStack(spacing: 20) {
                    MetricCard(
                        title: "Total Forecasts",
                        value: "\(overview.totalForecasts)",
                        icon: "chart.line.uptrend.xyaxis",
                        color: .blue
                    )

                    MetricCard(
                        title: "Tracked Symbols",
                        value: "\(overview.totalSymbols)",
                        icon: "list.bullet.rectangle",
                        color: .purple
                    )

                    MetricCard(
                        title: "Avg Confidence",
                        value: "\(Int(overview.avgConfidence * 100))%",
                        icon: "gauge.with.dots.needle.50percent",
                        color: confidenceColor(overview.avgConfidence)
                    )
                }
                .frame(height: 120)
            }
            
            // Forecast Quality Section (if symbol is selected)
            if let symbol = appViewModel.selectedSymbol {
                ForecastQualitySection(viewModel: qualityViewModel, symbol: symbol.ticker)
                    .onAppear {
                        Task {
                            await qualityViewModel.fetchQuality(symbol: symbol.ticker, horizon: "1D", timeframe: "d1")
                        }
                    }
            }

            // Signal & Confidence Distribution side by side
            HStack(spacing: 20) {
                SignalDistributionSection(viewModel: viewModel)
                ConfidenceDistributionSection(viewModel: viewModel)
            }

            // Recent Forecasts
            RecentForecastsSection(viewModel: viewModel)
        }
    }

    private func confidenceColor(_ confidence: Double) -> Color {
        if confidence > 0.7 { return .green }
        if confidence > 0.4 { return .orange }
        return .red
    }
}

// MARK: - Forecast Quality Section

private struct ForecastQualitySection: View {
    @ObservedObject var viewModel: ForecastQualityViewModel
    let symbol: String
    
    var body: some View {
        DashboardCard(title: "Forecast Quality", icon: "chart.bar.doc.horizontal", iconColor: .cyan) {
            if viewModel.isLoading {
                ProgressView("Loading quality metrics...")
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 20)
            } else if let result = viewModel.qualityResult {
                VStack(spacing: 16) {
                    // Quality Score
                    HStack(spacing: 30) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Quality Score")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            HStack(spacing: 8) {
                                Text("\(String(format: "%.1f", result.qualityScore * 100))%")
                                    .font(.title2.bold())
                                    .foregroundStyle(result.qualityScore >= 0.7 ? .green : result.qualityScore >= 0.5 ? .orange : .red)
                                Image(systemName: result.qualityScore >= 0.7 ? "checkmark.circle.fill" : result.qualityScore >= 0.5 ? "exclamationmark.triangle.fill" : "xmark.circle.fill")
                                    .foregroundStyle(result.qualityScore >= 0.7 ? .green : result.qualityScore >= 0.5 ? .orange : .red)
                            }
                        }
                        
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Confidence")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            Text("\(String(format: "%.1f", result.confidence * 100))%")
                                .font(.title3.bold())
                        }
                        
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Model Agreement")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            Text("\(String(format: "%.1f", result.modelAgreement * 100))%")
                                .font(.title3.bold())
                        }
                        
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Issues")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            Text("\(result.issues.count)")
                                .font(.title3.bold())
                                .foregroundStyle(result.issues.isEmpty ? .green : .orange)
                        }
                    }
                    
                    // Issues List
                    if !result.issues.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Quality Issues")
                                .font(.subheadline.bold())
                                .foregroundStyle(.orange)
                            
                            ForEach(Array(result.issues.enumerated()), id: \.offset) { index, issue in
                                HStack(alignment: .top, spacing: 8) {
                                    Image(systemName: issue.level == "warning" ? "exclamationmark.triangle.fill" : "info.circle.fill")
                                        .foregroundStyle(issue.level == "warning" ? .orange : .blue)
                                        .font(.caption)
                                    
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(issue.type.replacingOccurrences(of: "_", with: " ").capitalized)
                                            .font(.caption.bold())
                                        Text(issue.message)
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                    }
                                    
                                    Spacer()
                                }
                                .padding(.vertical, 4)
                                
                                if index < result.issues.count - 1 {
                                    Divider()
                                }
                            }
                        }
                        .padding(.top, 8)
                    } else {
                        HStack {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundStyle(.green)
                            Text("No quality issues detected")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.top, 8)
                    }
                }
                .padding(.top, 8)
            } else if let error = viewModel.error {
                Text("Error: \(error)")
                    .font(.caption)
                    .foregroundStyle(.red)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, 20)
            } else {
                Text("No quality data available")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, 20)
            }
        }
    }
}

// MARK: - Metric Card

private struct MetricCard: View {
    let title: String
    let value: String
    let icon: String
    let color: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: icon)
                    .font(.title2)
                    .foregroundStyle(color)
                Spacer()
            }

            Spacer()

            Text(value)
                .font(.system(size: 36, weight: .bold, design: .rounded))
                .foregroundStyle(.primary)

            Text(title)
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .padding(20)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

// MARK: - Signal Distribution Section

struct SignalDistributionSection: View {
    @ObservedObject var viewModel: PredictionsViewModel

    var body: some View {
        DashboardCard(title: "Signal Distribution", icon: "chart.pie.fill", iconColor: .purple) {
            if let dist = viewModel.overview?.signalDistribution {
                HStack(spacing: 24) {
                    SignalBar(label: "Bullish", count: dist.bullish, pct: dist.bullishPct, color: .green)
                    SignalBar(label: "Neutral", count: dist.neutral, pct: dist.neutralPct, color: .orange)
                    SignalBar(label: "Bearish", count: dist.bearish, pct: dist.bearishPct, color: .red)
                }
                .padding(.top, 8)
            } else {
                Text("No data available")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .center)
            }
        }
    }
}

struct SignalBar: View {
    let label: String
    let count: Int
    let pct: Double
    let color: Color

    var body: some View {
        VStack(spacing: 10) {
            Text("\(count)")
                .font(.system(size: 28, weight: .bold, design: .rounded))
                .foregroundStyle(color)

            GeometryReader { geo in
                ZStack(alignment: .bottom) {
                    RoundedRectangle(cornerRadius: 6)
                        .fill(color.opacity(0.15))

                    RoundedRectangle(cornerRadius: 6)
                        .fill(color)
                        .frame(height: max(4, geo.size.height * pct))
                }
            }
            .frame(height: 100)

            VStack(spacing: 2) {
                Text(label)
                    .font(.subheadline.bold())
                Text("\(Int(pct * 100))%")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - Confidence Distribution Section

struct ConfidenceDistributionSection: View {
    @ObservedObject var viewModel: PredictionsViewModel

    var body: some View {
        DashboardCard(title: "Confidence Levels", icon: "gauge.with.dots.needle.bottom.50percent", iconColor: .blue) {
            if let dist = viewModel.confidenceDistribution {
                VStack(spacing: 16) {
                    ConfidenceRow(label: "High", detail: "> 70%", count: dist.high, pct: dist.highPct, color: .green)
                    ConfidenceRow(label: "Medium", detail: "40-70%", count: dist.medium, pct: dist.mediumPct, color: .orange)
                    ConfidenceRow(label: "Low", detail: "< 40%", count: dist.low, pct: dist.lowPct, color: .red)
                }
                .padding(.top, 8)
            }
        }
    }
}

struct ConfidenceRow: View {
    let label: String
    let detail: String
    let count: Int
    let pct: Double
    let color: Color

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                Text(label)
                    .font(.subheadline.bold())
                Text(detail)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .frame(width: 80, alignment: .leading)

            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(color.opacity(0.15))

                    RoundedRectangle(cornerRadius: 4)
                        .fill(color)
                        .frame(width: max(4, geo.size.width * pct))
                }
            }
            .frame(height: 24)

            Text("\(count)")
                .font(.system(size: 18, weight: .bold, design: .rounded))
                .foregroundStyle(color)
                .frame(width: 40, alignment: .trailing)
        }
    }
}

// MARK: - Recent Forecasts Section

struct RecentForecastsSection: View {
    @ObservedObject var viewModel: PredictionsViewModel

    var body: some View {
        DashboardCard(
            title: "Recent Forecasts",
            icon: "clock.fill",
            iconColor: .orange,
            trailing: AnyView(
                Text("\(viewModel.recentForecasts.count) total")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            )
        ) {
            if viewModel.recentForecasts.isEmpty {
                Text("No recent forecasts")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, 20)
            } else {
                VStack(spacing: 0) {
                    ForEach(Array(viewModel.recentForecasts.prefix(10).enumerated()), id: \.element.id) { index, forecast in
                        ForecastRow(forecast: forecast)
                        if index < min(9, viewModel.recentForecasts.count - 1) {
                            Divider()
                                .padding(.vertical, 4)
                        }
                    }
                }
                .padding(.top, 8)
            }
        }
    }
}

struct ForecastRow: View {
    let forecast: ForecastSummary

    var body: some View {
        HStack(spacing: 16) {
            Text(forecast.ticker)
                .font(.system(size: 15, weight: .semibold, design: .rounded))
                .frame(width: 60, alignment: .leading)

            Text(forecast.label.capitalized)
                .font(.caption.bold())
                .foregroundStyle(.white)
                .padding(.horizontal, 10)
                .padding(.vertical, 4)
                .background(labelColor)
                .clipShape(Capsule())

            Spacer()

            HStack(spacing: 4) {
                Image(systemName: "percent")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                Text("\(Int(forecast.confidence * 100))")
                    .font(.system(size: 14, weight: .medium, design: .rounded))
            }
            .frame(width: 50)

            Text(forecast.horizon)
                .font(.caption)
                .foregroundStyle(.secondary)
                .padding(.horizontal, 8)
                .padding(.vertical, 3)
                .background(Color.gray.opacity(0.15))
                .clipShape(RoundedRectangle(cornerRadius: 4))
        }
        .padding(.vertical, 6)
    }

    private var labelColor: Color {
        switch forecast.label.lowercased() {
        case "bullish": return .green
        case "bearish": return .red
        default: return .orange
        }
    }
}

// MARK: - Model Performance Tab

struct ModelPerformanceTabView: View {
    @ObservedObject var viewModel: PredictionsViewModel

    var body: some View {
        DashboardCard(title: "Symbol Performance", icon: "star.fill", iconColor: .yellow) {
            if viewModel.symbolPerformance.isEmpty {
                Text("No performance data available")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, 40)
            } else {
                VStack(spacing: 0) {
                    // Header
                    HStack(spacing: 0) {
                        Text("Symbol")
                            .frame(width: 80, alignment: .leading)
                        Text("Forecasts")
                            .frame(width: 80, alignment: .center)
                        Text("Confidence")
                            .frame(width: 100, alignment: .center)
                        Text("Dominant")
                            .frame(width: 80, alignment: .center)
                        Spacer()
                        Text("Distribution")
                            .frame(width: 140, alignment: .center)
                    }
                    .font(.caption.bold())
                    .foregroundStyle(.secondary)
                    .padding(.vertical, 12)
                    .padding(.horizontal, 16)
                    .background(Color.gray.opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: 8))

                    ForEach(viewModel.symbolPerformance) { perf in
                        SymbolPerformanceRow(performance: perf)
                        if perf.id != viewModel.symbolPerformance.last?.id {
                            Divider()
                        }
                    }
                }
                .padding(.top, 8)
            }
        }
    }
}

struct SymbolPerformanceRow: View {
    let performance: SymbolPerformance

    var body: some View {
        HStack(spacing: 0) {
            Text(performance.ticker)
                .font(.system(size: 15, weight: .semibold, design: .rounded))
                .frame(width: 80, alignment: .leading)

            Text("\(performance.totalForecasts)")
                .font(.system(size: 14, weight: .medium))
                .frame(width: 80, alignment: .center)

            HStack(spacing: 4) {
                Circle()
                    .fill(confidenceColor)
                    .frame(width: 8, height: 8)
                Text("\(Int(performance.avgConfidence * 100))%")
                    .font(.system(size: 14, weight: .bold, design: .rounded))
                    .foregroundStyle(confidenceColor)
            }
            .frame(width: 100, alignment: .center)

            Text(performance.dominantSignal)
                .font(.caption.bold())
                .foregroundStyle(signalColor)
                .frame(width: 80, alignment: .center)

            Spacer()

            // Distribution bar
            HStack(spacing: 2) {
                let total = performance.signalDistribution.bullish + performance.signalDistribution.neutral + performance.signalDistribution.bearish
                if total > 0 {
                    RoundedRectangle(cornerRadius: 3)
                        .fill(Color.green)
                        .frame(width: max(2, CGFloat(performance.signalDistribution.bullish) / CGFloat(total) * 130))
                    RoundedRectangle(cornerRadius: 3)
                        .fill(Color.orange)
                        .frame(width: max(2, CGFloat(performance.signalDistribution.neutral) / CGFloat(total) * 130))
                    RoundedRectangle(cornerRadius: 3)
                        .fill(Color.red)
                        .frame(width: max(2, CGFloat(performance.signalDistribution.bearish) / CGFloat(total) * 130))
                }
            }
            .frame(width: 140, height: 14)
        }
        .padding(.vertical, 12)
        .padding(.horizontal, 16)
    }

    private var confidenceColor: Color {
        if performance.avgConfidence > 0.7 { return .green }
        if performance.avgConfidence > 0.4 { return .orange }
        return .red
    }

    private var signalColor: Color {
        switch performance.dominantSignal.lowercased() {
        case "bullish": return .green
        case "bearish": return .red
        default: return .orange
        }
    }
}

// MARK: - Statistical Validation Tab

struct StatisticalValidationTabView: View {
    @ObservedObject var viewModel: PredictionsViewModel

    var body: some View {
        VStack(spacing: 20) {
            // Core Metrics Section
            DashboardCard(title: "Core Validation Metrics", icon: "target", iconColor: .red) {
                VStack(spacing: 0) {
                    // Header
                    HStack(spacing: 0) {
                        Text("Metric")
                            .frame(width: 120, alignment: .leading)
                        Text("Answers")
                            .frame(width: 180, alignment: .leading)
                        Text("Week")
                            .frame(width: 50, alignment: .center)
                        Text("Setup")
                            .frame(width: 80, alignment: .center)
                        Text("Target")
                            .frame(width: 100, alignment: .center)
                        Spacer()
                        Text("Current")
                            .frame(width: 100, alignment: .trailing)
                    }
                    .font(.caption.bold())
                    .foregroundStyle(.secondary)
                    .padding(.vertical, 12)
                    .padding(.horizontal, 16)
                    .background(Color.gray.opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: 8))

                    // Metrics rows
                    ValidationMetricRow(
                        metric: "Precision@10",
                        question: "Are top picks good?",
                        week: 1,
                        difficulty: .easy,
                        target: "75%+",
                        currentValue: viewModel.validationMetrics?.precisionAt10,
                        formatter: { String(format: "%.1f%%", $0 * 100) },
                        isGood: { $0 >= 0.75 }
                    )
                    Divider()

                    ValidationMetricRow(
                        metric: "Win Rate",
                        question: "% trades profitable?",
                        week: 1,
                        difficulty: .easy,
                        target: "55%+",
                        currentValue: viewModel.validationMetrics?.winRate,
                        formatter: { String(format: "%.1f%%", $0 * 100) },
                        isGood: { $0 >= 0.55 }
                    )
                    Divider()

                    ValidationMetricRow(
                        metric: "Expectancy",
                        question: "Profit per trade?",
                        week: 1,
                        difficulty: .easy,
                        target: "+0.5% to +2%",
                        currentValue: viewModel.validationMetrics?.expectancy,
                        formatter: { String(format: "%+.2f%%", $0 * 100) },
                        isGood: { $0 >= 0.005 && $0 <= 0.02 }
                    )
                    Divider()

                    ValidationMetricRow(
                        metric: "Sharpe Ratio",
                        question: "Risk-adjusted return?",
                        week: 2,
                        difficulty: .medium,
                        target: "1.5+",
                        currentValue: viewModel.validationMetrics?.sharpeRatio,
                        formatter: { String(format: "%.2f", $0) },
                        isGood: { $0 >= 1.5 }
                    )
                    Divider()

                    ValidationMetricRow(
                        metric: "Kendall Tau",
                        question: "Rank → Profit correlation?",
                        week: 2,
                        difficulty: .medium,
                        target: "0.30+",
                        currentValue: viewModel.validationMetrics?.kendallTau,
                        formatter: { String(format: "%.3f", $0) },
                        isGood: { $0 >= 0.30 }
                    )
                    Divider()

                    ValidationMetricRow(
                        metric: "Monte Carlo",
                        question: "Real edge or luck?",
                        week: 2,
                        difficulty: .hard,
                        target: "<5% luck",
                        currentValue: viewModel.validationMetrics?.monteCarloLuck,
                        formatter: { String(format: "%.1f%% luck", $0 * 100) },
                        isGood: { $0 < 0.05 }
                    )
                    Divider()

                    ValidationMetricRow(
                        metric: "t-test p-value",
                        question: "Statistically significant?",
                        week: 3,
                        difficulty: .hard,
                        target: "<0.05",
                        currentValue: viewModel.validationMetrics?.tTestPValue,
                        formatter: { String(format: "%.4f", $0) },
                        isGood: { $0 < 0.05 }
                    )
                }
                .padding(.top, 8)
            }

            // Visual Summary Cards
            HStack(spacing: 16) {
                ValidationSummaryCard(
                    title: "Model Edge",
                    subtitle: "vs Random",
                    value: viewModel.validationMetrics?.modelEdge ?? 0,
                    target: 0.10,
                    color: .blue
                )

                ValidationSummaryCard(
                    title: "Confidence",
                    subtitle: "Calibration",
                    value: viewModel.validationMetrics?.confidenceCalibration ?? 0,
                    target: 0.90,
                    color: .purple
                )

                ValidationSummaryCard(
                    title: "Consistency",
                    subtitle: "Across Symbols",
                    value: viewModel.validationMetrics?.consistency ?? 0,
                    target: 0.70,
                    color: .green
                )

                ValidationSummaryCard(
                    title: "Robustness",
                    subtitle: "Out-of-Sample",
                    value: viewModel.validationMetrics?.robustness ?? 0,
                    target: 0.60,
                    color: .orange
                )
            }
            .frame(height: 140)

            // Implementation Levels
            DashboardCard(title: "Implementation Levels", icon: "slider.horizontal.3", iconColor: .blue) {
                HStack(alignment: .top, spacing: 16) {
                    ImplementationLevelCard(
                        level: 1,
                        title: "Basic",
                        description: "Win rate, Precision@10, Expectancy",
                        status: .complete,
                        color: .green
                    )

                    ImplementationLevelCard(
                        level: 2,
                        title: "Intermediate",
                        description: "Sharpe Ratio, Kendall Tau, Monte Carlo",
                        status: .inProgress,
                        color: .orange
                    )

                    ImplementationLevelCard(
                        level: 3,
                        title: "Advanced",
                        description: "t-test, Walk-forward, Regime analysis",
                        status: .planned,
                        color: .gray
                    )
                }
                .padding(.top, 8)
            }
        }
    }
}

// MARK: - Validation Metric Row

enum MetricDifficulty {
    case easy, medium, hard

    var stars: Int {
        switch self {
        case .easy: return 1
        case .medium: return 2
        case .hard: return 3
        }
    }

    var label: String {
        switch self {
        case .easy: return "Easy"
        case .medium: return "Medium"
        case .hard: return "Hard"
        }
    }

    var color: Color {
        switch self {
        case .easy: return .green
        case .medium: return .orange
        case .hard: return .red
        }
    }
}

struct ValidationMetricRow<T: BinaryFloatingPoint>: View {
    let metric: String
    let question: String
    let week: Int
    let difficulty: MetricDifficulty
    let target: String
    let currentValue: T?
    let formatter: (T) -> String
    let isGood: (T) -> Bool

    var body: some View {
        HStack(spacing: 0) {
            Text(metric)
                .font(.subheadline.bold())
                .frame(width: 120, alignment: .leading)

            Text(question)
                .font(.caption)
                .foregroundStyle(.secondary)
                .frame(width: 180, alignment: .leading)

            Text("\(week)")
                .font(.caption)
                .frame(width: 50, alignment: .center)

            // Difficulty stars
            HStack(spacing: 2) {
                ForEach(0..<difficulty.stars, id: \.self) { _ in
                    Image(systemName: "star.fill")
                        .font(.caption2)
                        .foregroundStyle(.yellow)
                }
                Text(difficulty.label)
                    .font(.caption2)
                    .foregroundStyle(difficulty.color)
            }
            .frame(width: 80, alignment: .center)

            Text(target)
                .font(.caption.bold())
                .foregroundStyle(.blue)
                .frame(width: 100, alignment: .center)

            Spacer()

            // Current value
            if let value = currentValue {
                let good = isGood(value)
                HStack(spacing: 4) {
                    Image(systemName: good ? "checkmark.circle.fill" : "xmark.circle.fill")
                        .foregroundStyle(good ? .green : .red)
                        .font(.caption)
                    Text(formatter(value))
                        .font(.system(.caption, design: .monospaced).bold())
                        .foregroundStyle(good ? .green : .red)
                }
                .frame(width: 100, alignment: .trailing)
            } else {
                Text("—")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .frame(width: 100, alignment: .trailing)
            }
        }
        .padding(.vertical, 12)
        .padding(.horizontal, 16)
    }
}

// MARK: - Validation Summary Card

struct ValidationSummaryCard: View {
    let title: String
    let subtitle: String
    let value: Double
    let target: Double
    let color: Color

    private var isGood: Bool { value >= target }
    private var percentage: Double { min(value / target, 1.0) }

    var body: some View {
        VStack(spacing: 12) {
            // Circular progress
            ZStack {
                Circle()
                    .stroke(color.opacity(0.2), lineWidth: 8)

                Circle()
                    .trim(from: 0, to: percentage)
                    .stroke(color, style: StrokeStyle(lineWidth: 8, lineCap: .round))
                    .rotationEffect(.degrees(-90))

                VStack(spacing: 0) {
                    Text("\(Int(value * 100))")
                        .font(.system(size: 24, weight: .bold, design: .rounded))
                        .foregroundStyle(isGood ? .green : color)
                    Text("%")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
            .frame(width: 70, height: 70)

            VStack(spacing: 2) {
                Text(title)
                    .font(.subheadline.bold())
                Text(subtitle)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }

            // Target indicator
            HStack(spacing: 4) {
                Image(systemName: isGood ? "checkmark.circle.fill" : "target")
                    .font(.caption2)
                Text("Target: \(Int(target * 100))%")
                    .font(.caption2)
            }
            .foregroundStyle(isGood ? .green : .secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 16)
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

// MARK: - Implementation Level Card

enum ImplementationStatus {
    case complete, inProgress, planned

    var label: String {
        switch self {
        case .complete: return "Complete"
        case .inProgress: return "In Progress"
        case .planned: return "Planned"
        }
    }

    var icon: String {
        switch self {
        case .complete: return "checkmark.circle.fill"
        case .inProgress: return "clock.fill"
        case .planned: return "calendar"
        }
    }
}

struct ImplementationLevelCard: View {
    let level: Int
    let title: String
    let description: String
    let status: ImplementationStatus
    let color: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Level \(level)")
                    .font(.caption.bold())
                    .foregroundStyle(.white)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(color)
                    .clipShape(Capsule())

                Spacer()

                HStack(spacing: 4) {
                    Image(systemName: status.icon)
                        .font(.caption2)
                    Text(status.label)
                        .font(.caption2)
                }
                .foregroundStyle(color)
            }

            Text(title)
                .font(.headline)

            Text(description)
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(2)

            Spacer()
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(color.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

// MARK: - Feature Importance Tab

struct FeatureImportanceTabView: View {
    @ObservedObject var viewModel: PredictionsViewModel
    // Static feature importance data from the ML model
    private let modelFeatures: [(name: String, importance: Double, category: String)] = [
        ("SuperTrend Signal", 0.18, "trend"),
        ("RSI (14)", 0.15, "momentum"),
        ("ADX", 0.14, "trend"),
        ("MACD Histogram", 0.12, "momentum"),
        ("Bollinger Width", 0.11, "volatility"),
        ("KDJ-J", 0.10, "momentum"),
        ("MFI", 0.08, "volume"),
        ("ATR (14)", 0.07, "volatility"),
        ("Volume Ratio", 0.05, "volume"),
    ]

    var body: some View {
        VStack(spacing: 20) {
            // Feature Importance Chart
            DashboardCard(title: "Feature Importance", icon: "chart.bar.fill", iconColor: .purple) {
                VStack(spacing: 12) {
                    ForEach(modelFeatures, id: \.name) { feature in
                        FeatureImportanceRow(name: feature.name, importance: feature.importance, category: feature.category)
                    }
                }
                .padding(.top, 8)
            }

            // Features by Category
            DashboardCard(title: "Features by Category", icon: "square.grid.2x2.fill", iconColor: .blue) {
                HStack(alignment: .top, spacing: 16) {
                    CategoryCard(
                        category: "Trend",
                        features: modelFeatures.filter { $0.category == "trend" },
                        color: .blue
                    )
                    CategoryCard(
                        category: "Momentum",
                        features: modelFeatures.filter { $0.category == "momentum" },
                        color: .purple
                    )
                    CategoryCard(
                        category: "Volatility",
                        features: modelFeatures.filter { $0.category == "volatility" },
                        color: .orange
                    )
                    CategoryCard(
                        category: "Volume",
                        features: modelFeatures.filter { $0.category == "volume" },
                        color: .green
                    )
                }
                .padding(.top, 8)
            }
        }
    }
}

struct FeatureImportanceRow: View {
    let name: String
    let importance: Double
    let category: String

    var body: some View {
        HStack(spacing: 16) {
            Circle()
                .fill(categoryColor)
                .frame(width: 10, height: 10)

            Text(name)
                .font(.subheadline)
                .frame(width: 140, alignment: .leading)

            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(categoryColor.opacity(0.15))

                    RoundedRectangle(cornerRadius: 4)
                        .fill(categoryColor)
                        .frame(width: geo.size.width * importance)
                }
            }
            .frame(height: 20)

            Text("\(Int(importance * 100))%")
                .font(.system(size: 14, weight: .bold, design: .rounded))
                .foregroundStyle(categoryColor)
                .frame(width: 50, alignment: .trailing)
        }
        .padding(.vertical, 4)
    }

    private var categoryColor: Color {
        switch category {
        case "momentum": return .purple
        case "trend": return .blue
        case "volume": return .green
        case "volatility": return .orange
        default: return .gray
        }
    }
}

struct CategoryCard: View {
    let category: String
    let features: [(name: String, importance: Double, category: String)]
    let color: Color

    private var totalImportance: Double {
        features.reduce(0) { $0 + $1.importance }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Circle()
                    .fill(color)
                    .frame(width: 12, height: 12)
                Text(category)
                    .font(.headline)
            }

            Text("\(Int(totalImportance * 100))% total")
                .font(.system(size: 24, weight: .bold, design: .rounded))
                .foregroundStyle(color)

            Divider()

            VStack(alignment: .leading, spacing: 8) {
                ForEach(features, id: \.name) { feature in
                    HStack {
                        Text(feature.name)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Spacer()
                        Text("\(Int(feature.importance * 100))%")
                            .font(.caption.bold())
                            .foregroundStyle(color)
                    }
                }
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(color.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

// MARK: - Dashboard Card Component

struct DashboardCard<Content: View>: View {
    let title: String
    let icon: String
    let iconColor: Color
    var trailing: AnyView? = nil
    @ViewBuilder let content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: icon)
                    .font(.title3)
                    .foregroundStyle(iconColor)
                Text(title)
                    .font(.title3.bold())
                Spacer()
                if let trailing = trailing {
                    trailing
                }
            }

            content()
        }
        .padding(20)
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

// MARK: - Preview

#Preview {
    PredictionsView()
        .environmentObject(AppViewModel())
        .frame(width: 900, height: 800)
}
