import SwiftUI
import Charts

struct ForecastQualityView: View {
    @StateObject private var viewModel = ForecastQualityViewModel()
    let symbol: String
    let timeframe: String
    
    @State private var showConfiguration = true
    
    var body: some View {
        HSplitView {
            // Configuration Panel
            if showConfiguration {
                configurationPanel
                    .frame(minWidth: 300, idealWidth: 350)
            }
            
            // Results Panel
            resultsPanel
        }
        .navigationTitle("Forecast Quality: \(symbol)")
        .toolbar {
            ToolbarItem(placement: .automatic) {
                Button(action: { showConfiguration.toggle() }) {
                    Image(systemName: showConfiguration ? "sidebar.left" : "sidebar.right")
                }
            }
        }
        .onAppear {
            Task {
                await viewModel.fetchQuality(symbol: symbol, horizon: viewModel.horizon, timeframe: timeframe)
            }
        }
        .refreshable {
            await viewModel.fetchQuality(symbol: symbol, horizon: viewModel.horizon, timeframe: timeframe, forceRefresh: true)
        }
    }
    
    // MARK: - Configuration Panel
    
    private var configurationPanel: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // Header
                HStack {
                    Text("Configuration")
                        .font(.title2.bold())
                    Spacer()
                }
                .padding(.bottom, 8)
                
                // Horizon Selector
                VStack(alignment: .leading, spacing: 8) {
                    Text("Forecast Horizon")
                        .font(.headline)
                    
                    Picker("", selection: $viewModel.horizon) {
                        Text("1 Day").tag("1D")
                        Text("1 Week").tag("1W")
                        Text("1 Month").tag("1M")
                    }
                    .pickerStyle(.menu)
                    .onChange(of: viewModel.horizon) { oldValue, newValue in
                        Task {
                            await viewModel.fetchQuality(symbol: symbol, horizon: newValue, timeframe: timeframe)
                        }
                    }
                }
                
                Divider()
                
                // Refresh Button
                Button(action: {
                    Task {
                        await viewModel.fetchQuality(symbol: symbol, horizon: viewModel.horizon, timeframe: timeframe, forceRefresh: true)
                    }
                }) {
                    HStack {
                        if viewModel.isLoading {
                            ProgressView()
                                .scaleEffect(0.8)
                        } else {
                            Image(systemName: "arrow.clockwise")
                        }
                        Text(viewModel.isLoading ? "Loading..." : "Refresh")
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .disabled(viewModel.isLoading)
            }
            .padding()
        }
    }
    
    // MARK: - Results Panel
    
    private var resultsPanel: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                if viewModel.isLoading {
                    ForecastQualitySkeleton()
                        .padding()
                } else if let error = viewModel.error {
                    errorView(error)
                } else if let result = viewModel.qualityResult {
                    resultsView(result)
                        .fadeIn()
                } else {
                    StandardEmptyView(
                        title: "No Quality Data",
                        message: "Forecast quality metrics help you assess the reliability of ML predictions. Load metrics to see confidence scores, model agreement, and quality issues.",
                        icon: "chart.bar.doc.horizontal",
                        actionLabel: "Load Quality Metrics",
                        action: {
                            Task {
                                await viewModel.fetchQuality(symbol: symbol, horizon: viewModel.horizon, timeframe: timeframe, forceRefresh: true)
                            }
                        },
                        tips: [
                            "Quality scores above 70% indicate high confidence",
                            "Check for quality issues that may affect predictions",
                            "Different forecast horizons may have different quality scores"
                        ]
                    )
                }
            }
            .padding()
        }
        .refreshable {
            await viewModel.fetchQuality(symbol: symbol, horizon: viewModel.horizon, timeframe: timeframe, forceRefresh: true)
        }
    }
    
    
    private func errorView(_ error: String) -> some View {
        // Try to parse as Error to get user-friendly message
        let apiError = APIError.serviceUnavailable(message: error)
        let formatted = ErrorFormatter.userFriendlyMessage(from: apiError)
        
        return StandardErrorView(
            title: formatted.title,
            message: formatted.message,
            icon: formatted.icon,
            retryAction: {
                Task {
                    await viewModel.fetchQuality(symbol: symbol, horizon: viewModel.horizon, timeframe: timeframe, forceRefresh: true)
                }
            }
        )
    }
    
    private func resultsView(_ result: ForecastQualityResponse) -> some View {
        VStack(alignment: .leading, spacing: 24) {
            // Header
            HStack {
                Text("Quality Metrics")
                    .font(.title2.bold())
                Spacer()
                
                // Offline indicator
                if viewModel.isOffline {
                    InlineStatusBadge(status: .warning, message: "Offline")
                        .padding(.trailing, 8)
                        .transition(.opacity)
                }
                
                qualityScoreBadge(result.qualityScore)
            }
            .slideIn()
            
            // Quality Score Card
            qualityScoreCard(result)
            
            // Metrics Grid
            metricsGrid(result)
            
            // Issues Section
            if !result.issues.isEmpty {
                issuesCard(result.issues)
            } else {
                noIssuesCard
            }
        }
    }
    
    // MARK: - View Helpers (Optimized with computed properties)
    
    @ViewBuilder
    private func qualityScoreBadge(_ score: Double) -> some View {
        let (icon, color) = qualityScoreIconAndColor(score)
        let formattedScore = String(format: "%.0f", score * 100)
        
        HStack(spacing: 4) {
            Image(systemName: icon)
            Text("\(formattedScore)%")
                .font(.headline)
        }
        .foregroundStyle(color)
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background(color.opacity(0.2))
        .cornerRadius(8)
    }
    
    // Extract expensive computations to avoid repeated calculations
    private func qualityScoreIconAndColor(_ score: Double) -> (icon: String, color: Color) {
        if score >= 0.7 {
            return ("checkmark.circle.fill", .green)
        } else if score >= 0.5 {
            return ("exclamationmark.triangle.fill", .orange)
        } else {
            return ("xmark.circle.fill", .red)
        }
    }
    
    @ViewBuilder
    private func qualityScoreCard(_ result: ForecastQualityResponse) -> some View {
        // Pre-compute formatted values to avoid repeated String formatting
        let qualityScoreText = String(format: "%.1f", result.qualityScore * 100)
        let confidenceText = String(format: "%.1f", result.confidence * 100)
        let agreementText = String(format: "%.1f", result.modelAgreement * 100)
        let (_, qualityColor) = qualityScoreIconAndColor(result.qualityScore)
        
        VStack(alignment: .leading, spacing: 12) {
            Text("Overall Quality Score")
                .font(.headline)
            
            HStack(spacing: 20) {
                VStack(alignment: .leading) {
                    Text("Quality Score")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text("\(qualityScoreText)%")
                        .font(.title.bold())
                        .foregroundStyle(qualityColor)
                }
                
                VStack(alignment: .leading) {
                    Text("Confidence")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text("\(confidenceText)%")
                        .font(.title2.bold())
                }
                
                VStack(alignment: .leading) {
                    Text("Model Agreement")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text("\(agreementText)%")
                        .font(.title2.bold())
                }
            }
        }
        .padding()
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(8)
    }
    
    private func metricsGrid(_ result: ForecastQualityResponse) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Quality Metrics")
                .font(.headline)
            
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                QualityMetricCard(title: "Quality Score", value: "\(String(format: "%.1f", result.qualityScore * 100))%", color: result.qualityScore >= 0.7 ? .green : result.qualityScore >= 0.5 ? .orange : .red)
                QualityMetricCard(title: "Confidence", value: "\(String(format: "%.1f", result.confidence * 100))%", color: result.confidence >= 0.7 ? .green : result.confidence >= 0.5 ? .orange : .red)
                QualityMetricCard(title: "Model Agreement", value: "\(String(format: "%.1f", result.modelAgreement * 100))%", color: result.modelAgreement >= 0.7 ? .green : result.modelAgreement >= 0.5 ? .orange : .red)
                QualityMetricCard(title: "Issues", value: "\(result.issues.count)", color: result.issues.isEmpty ? .green : .orange)
            }
        }
        .padding()
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(8)
    }
    
    private var noIssuesCard: some View {
        VStack(spacing: 12) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 32))
                .foregroundStyle(.green)
            Text("No Quality Issues")
                .font(.headline)
            Text("All quality metrics are within acceptable ranges")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding()
        .background(Color.green.opacity(0.1))
        .cornerRadius(8)
    }
    
    private func issuesCard(_ issues: [QualityIssue]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Quality Issues")
                    .font(.headline)
                Spacer()
                Text("\(issues.count)")
                    .font(.headline)
                    .foregroundStyle(.orange)
            }
            
            ForEach(Array(issues.enumerated()), id: \.offset) { index, issue in
                IssueRow(issue: issue)
            }
        }
        .padding()
        .background(Color.orange.opacity(0.1))
        .cornerRadius(8)
    }
}

// MARK: - Helper Views

struct QualityMetricCard: View {
    let title: String
    let value: String
    let color: Color
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.headline)
                .foregroundStyle(color)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(NSColor.secondarySystemFill))
        .cornerRadius(6)
    }
}

struct IssueRow: View {
    let issue: QualityIssue
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Image(systemName: issue.level == "warning" ? "exclamationmark.triangle.fill" : "info.circle.fill")
                    .foregroundStyle(issue.level == "warning" ? .orange : .blue)
                Text(issue.type.replacingOccurrences(of: "_", with: " ").capitalized)
                    .font(.subheadline.bold())
                Spacer()
            }
            
            Text(issue.message)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            
            HStack {
                Text("Action:")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text(issue.action)
                    .font(.caption)
            }
        }
        .padding()
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(6)
    }
}

#Preview {
    ForecastQualityView(symbol: "AAPL", timeframe: "d1")
        .frame(width: 1000, height: 600)
}
