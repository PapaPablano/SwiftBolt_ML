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
                }
                
                Divider()
                
                // Refresh Button
                Button(action: {
                    Task {
                        await viewModel.fetchQuality(symbol: symbol, horizon: viewModel.horizon, timeframe: timeframe)
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
                    ProgressView("Loading quality metrics...")
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if let error = viewModel.error {
                    errorView(error)
                } else if let result = viewModel.qualityResult {
                    resultsView(result)
                } else {
                    emptyStateView
                }
            }
            .padding()
        }
    }
    
    private var emptyStateView: some View {
        VStack(spacing: 16) {
            Image(systemName: "chart.bar.doc.horizontal")
                .font(.system(size: 48))
                .foregroundStyle(.secondary)
            Text("No Quality Data")
                .font(.title2.bold())
            Text("Click 'Refresh' to load forecast quality metrics")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
    
    private func errorView(_ error: String) -> some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 48))
                .foregroundStyle(.orange)
            Text("Error Loading Quality")
                .font(.title2.bold())
            Text(error)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
            
            Button("Retry") {
                Task {
                    await viewModel.fetchQuality(symbol: symbol, horizon: viewModel.horizon, timeframe: timeframe)
                }
            }
            .buttonStyle(.borderedProminent)
        }
        .frame(maxWidth: .infinity)
        .padding()
    }
    
    private func resultsView(_ result: ForecastQualityResponse) -> some View {
        VStack(alignment: .leading, spacing: 24) {
            // Header
            HStack {
                Text("Quality Metrics")
                    .font(.title2.bold())
                Spacer()
                qualityScoreBadge(result.qualityScore)
            }
            
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
    
    private func qualityScoreBadge(_ score: Double) -> some View {
        HStack(spacing: 4) {
            Image(systemName: score >= 0.7 ? "checkmark.circle.fill" : score >= 0.5 ? "exclamationmark.triangle.fill" : "xmark.circle.fill")
            Text("\(String(format: "%.0f", score * 100))%")
                .font(.headline)
        }
        .foregroundStyle(score >= 0.7 ? .green : score >= 0.5 ? .orange : .red)
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background((score >= 0.7 ? Color.green : score >= 0.5 ? Color.orange : Color.red).opacity(0.2))
        .cornerRadius(8)
    }
    
    private func qualityScoreCard(_ result: ForecastQualityResponse) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Overall Quality Score")
                .font(.headline)
            
            HStack(spacing: 20) {
                VStack(alignment: .leading) {
                    Text("Quality Score")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text("\(String(format: "%.1f", result.qualityScore * 100))%")
                        .font(.title.bold())
                        .foregroundStyle(result.qualityScore >= 0.7 ? .green : result.qualityScore >= 0.5 ? .orange : .red)
                }
                
                VStack(alignment: .leading) {
                    Text("Confidence")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text("\(String(format: "%.1f", result.confidence * 100))%")
                        .font(.title2.bold())
                }
                
                VStack(alignment: .leading) {
                    Text("Model Agreement")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text("\(String(format: "%.1f", result.modelAgreement * 100))%")
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
