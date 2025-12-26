import SwiftUI

struct PredictionsView: View {
    @StateObject private var viewModel = PredictionsViewModel()
    @State private var selectedTab = 0

    var body: some View {
        VStack(spacing: 0) {
            // Header
            headerSection

            // Tab selector
            Picker("", selection: $selectedTab) {
                Text("Overview").tag(0)
                Text("Model Performance").tag(1)
                Text("Feature Importance").tag(2)
                Text("Forecast Accuracy").tag(3)
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
                        switch selectedTab {
                        case 0:
                            OverviewTabView(viewModel: viewModel)
                        case 1:
                            ModelPerformanceTabView(viewModel: viewModel)
                        case 2:
                            FeatureImportanceTabView()
                        case 3:
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

struct OverviewTabView: View {
    @ObservedObject var viewModel: PredictionsViewModel

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

// MARK: - Metric Card

struct MetricCard: View {
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

// MARK: - Feature Importance Tab

struct FeatureImportanceTabView: View {
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
        .frame(width: 900, height: 800)
}
