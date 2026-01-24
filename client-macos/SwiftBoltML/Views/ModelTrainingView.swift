import SwiftUI
import Charts

struct ModelTrainingView: View {
    @StateObject private var viewModel = ModelTrainingViewModel()
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
        .navigationTitle("Model Training: \(symbol)")
        .toolbar {
            ToolbarItem(placement: .automatic) {
                Button(action: { showConfiguration.toggle() }) {
                    Image(systemName: showConfiguration ? "sidebar.left" : "sidebar.right")
                }
            }
        }
        .onAppear {
            Task {
                await viewModel.trainModel(symbol: symbol, timeframe: viewModel.timeframe, lookbackDays: viewModel.lookbackDays)
            }
        }
        .refreshable {
            await viewModel.trainModel(symbol: symbol, timeframe: viewModel.timeframe, lookbackDays: viewModel.lookbackDays, forceRefresh: true)
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
                
                // Timeframe Selector
                VStack(alignment: .leading, spacing: 8) {
                    Text("Timeframe")
                        .font(.headline)
                    
                    Picker("", selection: $viewModel.timeframe) {
                        Text("Daily (d1)").tag("d1")
                        Text("Hourly (h1)").tag("h1")
                        Text("4-Hour (h4)").tag("h4")
                        Text("15-Minute (m15)").tag("m15")
                    }
                    .pickerStyle(.menu)
                }
                
                Divider()
                
                // Lookback Days
                VStack(alignment: .leading, spacing: 8) {
                    Text("Lookback Days")
                        .font(.headline)
                    
                    TextField("Days", value: $viewModel.lookbackDays, format: .number)
                        .textFieldStyle(.roundedBorder)
                    
                    Text("Number of days of historical data to use for training")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                
                Spacer()
                
                // Train Button
                Button(action: {
                    Task {
                        await viewModel.trainModel(symbol: symbol, timeframe: viewModel.timeframe, lookbackDays: viewModel.lookbackDays)
                    }
                }) {
                    HStack {
                        if viewModel.isLoading {
                            ProgressView()
                                .scaleEffect(0.8)
                        } else {
                            Image(systemName: "brain.head.profile")
                        }
                        Text(viewModel.isLoading ? "Training..." : "Train Model")
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
                    ModelTrainingSkeleton()
                        .padding()
                } else if let error = viewModel.error {
                    errorView(error)
                } else if let result = viewModel.trainingResult {
                    resultsView(result)
                        .fadeIn()
                } else {
                    StandardEmptyView(
                        title: "No Training Results",
                        message: "Train ML models to improve forecast accuracy. Training analyzes historical data to optimize model parameters and ensemble weights.",
                        icon: "brain.head.profile",
                        actionLabel: "Train Model",
                        action: {
                            Task {
                                await viewModel.trainModel(symbol: symbol, timeframe: viewModel.timeframe, lookbackDays: viewModel.lookbackDays)
                            }
                        },
                        tips: [
                            "Training uses \(viewModel.lookbackDays) days of historical data",
                            "Longer lookback periods may improve accuracy but take longer",
                            "Training results are cached for quick access"
                        ]
                    )
                }
            }
            .padding()
        }
        .refreshable {
            await viewModel.trainModel(symbol: symbol, timeframe: viewModel.timeframe, lookbackDays: viewModel.lookbackDays, forceRefresh: true)
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
                    await viewModel.trainModel(symbol: symbol, timeframe: viewModel.timeframe, lookbackDays: viewModel.lookbackDays)
                }
            }
        )
    }
    
    private func resultsView(_ result: ModelTrainingResponse) -> some View {
        VStack(alignment: .leading, spacing: 24) {
            // Header
            HStack {
                Text("Training Results")
                    .font(.title2.bold())
                Spacer()
                
                // Offline indicator
                if viewModel.isOffline {
                    InlineStatusBadge(status: .warning, message: "Offline")
                        .padding(.trailing, 8)
                }
                
                statusBadge(result.status)
            }
            
            // Performance Summary
            performanceSummaryCard(result)
            
            // Training Metrics
            metricsGrid(result)
            
            // Model Info
            modelInfoCard(result)
            
            // Ensemble Weights
            if !result.ensembleWeights.isEmpty {
                ensembleWeightsCard(result)
            }
        }
    }
    
    private func statusBadge(_ status: String) -> some View {
        Text(status.uppercased())
            .font(.caption.bold())
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(status == "success" ? Color.green.opacity(0.2) : Color.orange.opacity(0.2))
            .foregroundStyle(status == "success" ? .green : .orange)
            .cornerRadius(4)
    }
    
    private func performanceSummaryCard(_ result: ModelTrainingResponse) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Performance Summary")
                .font(.headline)
            
            HStack(spacing: 20) {
                VStack(alignment: .leading) {
                    Text("Validation Accuracy")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text("\(String(format: "%.2f", result.trainingMetrics.validationAccuracy * 100))%")
                        .font(.title2.bold())
                        .foregroundStyle(result.trainingMetrics.validationAccuracy >= 0.5 ? .green : .orange)
                }
                
                VStack(alignment: .leading) {
                    Text("Train Accuracy")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text("\(String(format: "%.2f", result.trainingMetrics.trainAccuracy * 100))%")
                        .font(.title2.bold())
                }
            }
        }
        .padding()
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(8)
    }
    
    private func metricsGrid(_ result: ModelTrainingResponse) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Training Metrics")
                .font(.headline)
            
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                ModelTrainingMetricCard(title: "Train Samples", value: "\(result.trainingMetrics.trainSamples)")
                ModelTrainingMetricCard(title: "Validation Samples", value: "\(result.trainingMetrics.validationSamples)")
                ModelTrainingMetricCard(title: "Test Samples", value: "\(result.trainingMetrics.testSamples)")
                ModelTrainingMetricCard(title: "Feature Count", value: "\(result.modelInfo.featureCount)")
            }
        }
        .padding()
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(8)
    }
    
    private func modelInfoCard(_ result: ModelTrainingResponse) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Model Information")
                .font(.headline)
            
            VStack(alignment: .leading, spacing: 8) {
                InfoRow(label: "Model Hash", value: result.modelInfo.modelHash)
                InfoRow(label: "Trained At", value: formatDate(result.modelInfo.trainedAt))
                InfoRow(label: "Timeframe", value: result.timeframe)
                InfoRow(label: "Lookback Days", value: "\(result.lookbackDays)")
            }
        }
        .padding()
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(8)
    }
    
    private func ensembleWeightsCard(_ result: ModelTrainingResponse) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Ensemble Weights")
                .font(.headline)
            
            VStack(alignment: .leading, spacing: 8) {
                ForEach(Array(result.ensembleWeights.keys.sorted()), id: \.self) { key in
                    HStack {
                        Text(key.uppercased())
                            .font(.subheadline)
                        Spacer()
                        Text("\(String(format: "%.3f", result.ensembleWeights[key] ?? 0))")
                            .font(.subheadline.monospacedDigit())
                            .foregroundStyle(.secondary)
                    }
                }
            }
        }
        .padding()
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(8)
    }
    
    private func formatDate(_ dateString: String) -> String {
        let formatter = ISO8601DateFormatter()
        if let date = formatter.date(from: dateString) {
            let displayFormatter = DateFormatter()
            displayFormatter.dateStyle = .medium
            displayFormatter.timeStyle = .short
            return displayFormatter.string(from: date)
        }
        return dateString
    }
}

// MARK: - Helper Views

fileprivate struct ModelTrainingMetricCard: View {
    let title: String
    let value: String
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.headline)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(NSColor.secondarySystemFill))
        .cornerRadius(6)
    }
}

struct InfoRow: View {
    let label: String
    let value: String
    
    var body: some View {
        HStack {
            Text(label)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Spacer()
            Text(value)
                .font(.subheadline)
        }
    }
}

#Preview {
    ModelTrainingView(symbol: "AAPL", timeframe: "d1")
        .frame(width: 1000, height: 600)
}
