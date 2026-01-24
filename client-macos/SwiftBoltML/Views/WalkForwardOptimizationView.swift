import SwiftUI
import Charts

struct WalkForwardOptimizationView: View {
    @StateObject private var viewModel = WalkForwardViewModel()
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
        .navigationTitle("Walk-Forward Optimization: \(symbol)")
        .toolbar {
            ToolbarItem(placement: .automatic) {
                Button(action: { showConfiguration.toggle() }) {
                    Image(systemName: showConfiguration ? "sidebar.left" : "sidebar.right")
                }
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
                
                // Forecaster Selector
                VStack(alignment: .leading, spacing: 8) {
                    Text("Forecaster")
                        .font(.headline)
                    
                    Picker("", selection: $viewModel.selectedForecaster) {
                        ForEach(ForecasterType.allCases, id: \.self) { forecaster in
                            HStack {
                                Image(systemName: forecaster.icon)
                                Text(forecaster.displayName)
                            }
                            .tag(forecaster)
                        }
                    }
                    .pickerStyle(.menu)
                    
                    Text(viewModel.selectedForecaster.description)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                
                Divider()
                
                // Horizon Selector
                VStack(alignment: .leading, spacing: 8) {
                    Text("Forecast Horizon")
                        .font(.headline)
                    
                    Picker("", selection: $viewModel.selectedHorizon) {
                        ForEach(ForecastHorizon.allCases, id: \.self) { horizon in
                            Text(horizon.displayName)
                                .tag(horizon)
                        }
                    }
                    .pickerStyle(.menu)
                }
                
                Divider()
                
                // Custom Windows (Optional)
                VStack(alignment: .leading, spacing: 8) {
                    Text("Custom Windows (Optional)")
                        .font(.headline)
                    
                    Text("Leave empty to use horizon-optimized defaults")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    
                    HStack {
                        Text("Train:")
                        TextField("Auto", value: Binding(
                            get: { viewModel.customWindows?.trainWindow },
                            set: { 
                                if viewModel.customWindows == nil {
                                    viewModel.customWindows = WalkForwardViewModel.WindowConfig()
                                }
                                viewModel.customWindows?.trainWindow = $0
                            }
                        ), format: .number)
                            .textFieldStyle(.roundedBorder)
                    }
                    
                    HStack {
                        Text("Test:")
                        TextField("Auto", value: Binding(
                            get: { viewModel.customWindows?.testWindow },
                            set: { 
                                if viewModel.customWindows == nil {
                                    viewModel.customWindows = WalkForwardViewModel.WindowConfig()
                                }
                                viewModel.customWindows?.testWindow = $0
                            }
                        ), format: .number)
                            .textFieldStyle(.roundedBorder)
                    }
                    
                    HStack {
                        Text("Step:")
                        TextField("Auto", value: Binding(
                            get: { viewModel.customWindows?.stepSize },
                            set: { 
                                if viewModel.customWindows == nil {
                                    viewModel.customWindows = WalkForwardViewModel.WindowConfig()
                                }
                                viewModel.customWindows?.stepSize = $0
                            }
                        ), format: .number)
                            .textFieldStyle(.roundedBorder)
                    }
                    
                    Button("Reset to Defaults") {
                        viewModel.customWindows = nil
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                }
                
                Spacer()
                
                // Run Button
                Button(action: {
                    Task {
                        await viewModel.runWalkForward(symbol: symbol, timeframe: timeframe)
                    }
                }) {
                    HStack {
                        if viewModel.isLoading {
                            ProgressView()
                                .scaleEffect(0.7)
                        } else {
                            Image(systemName: "play.fill")
                        }
                        Text(viewModel.isLoading ? "Running..." : "Run Optimization")
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .disabled(viewModel.isLoading)
            }
            .padding()
        }
        .background(Color(nsColor: .controlBackgroundColor))
    }
    
    // MARK: - Results Panel
    
    private var resultsPanel: some View {
        ScrollView {
            VStack(spacing: 20) {
                if viewModel.isLoading {
                    loadingView
                } else if let error = viewModel.error {
                    errorView(error)
                } else if let result = viewModel.walkForwardResult {
                    resultsView(result)
                } else {
                    emptyStateView
                }
            }
            .padding()
        }
    }
    
    private var loadingView: some View {
        VStack(spacing: 16) {
            ProgressView()
                .scaleEffect(1.5)
            Text("Running walk-forward optimization...")
                .font(.headline)
            Text("This may take several minutes")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(.vertical, 60)
    }
    
    private func errorView(_ error: String) -> some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.largeTitle)
                .foregroundStyle(.orange)
            Text("Optimization Failed")
                .font(.headline)
            Text(error)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
            
            Button("Retry") {
                Task {
                    await viewModel.runWalkForward(symbol: symbol, timeframe: timeframe)
                }
            }
            .buttonStyle(.borderedProminent)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 40)
    }
    
    private var emptyStateView: some View {
        VStack(spacing: 16) {
            Image(systemName: "arrow.triangle.2.circlepath")
                .font(.largeTitle)
                .foregroundStyle(.secondary)
            Text("No Optimization Results")
                .font(.headline)
            Text("Configure your settings and click 'Run Optimization' to see results")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 40)
    }
    
    private func resultsView(_ result: WalkForwardResponse) -> some View {
        VStack(spacing: 20) {
            // Performance Summary
            performanceSummaryCard(result)
            
            // Metrics Grid
            metricsGrid(result)
            
            // Window Information
            windowInfoCard(result)
        }
    }
    
    // MARK: - Performance Summary
    
    private func performanceSummaryCard(_ result: WalkForwardResponse) -> some View {
        DashboardCard(title: "Performance Summary", icon: "chart.bar", iconColor: .blue) {
            VStack(spacing: 16) {
                HStack(spacing: 30) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Accuracy")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text("\(String(format: "%.2f", result.metrics.accuracy * 100))%")
                            .font(.title2.bold())
                            .foregroundStyle(result.metrics.accuracy >= 0.6 ? .green : result.metrics.accuracy >= 0.5 ? .orange : .red)
                    }
                    
                    VStack(alignment: .leading, spacing: 4) {
                        Text("F1 Score")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text(String(format: "%.3f", result.metrics.f1Score))
                            .font(.title3.bold())
                    }
                    
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Sharpe Ratio")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text(String(format: "%.2f", result.metrics.sharpeRatio))
                            .font(.title3.bold())
                            .foregroundStyle(result.metrics.sharpeRatio > 1.0 ? .green : result.metrics.sharpeRatio > 0.5 ? .orange : .red)
                    }
                    
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Win Rate")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text("\(String(format: "%.1f", result.metrics.winRate * 100))%")
                            .font(.title3.bold())
                            .foregroundStyle(result.metrics.winRate > 0.5 ? .green : result.metrics.winRate > 0.4 ? .orange : .red)
                    }
                }
                .frame(maxWidth: .infinity)
            }
        }
    }
    
    // MARK: - Metrics Grid
    
    private func metricsGrid(_ result: WalkForwardResponse) -> some View {
        LazyVGrid(columns: [
            GridItem(.flexible()),
            GridItem(.flexible()),
            GridItem(.flexible()),
            GridItem(.flexible())
        ], spacing: 16) {
            MetricCard(
                title: "Precision",
                value: "\(String(format: "%.2f", result.metrics.precision * 100))%",
                icon: "target",
                color: result.metrics.precision > 0.6 ? Color.green : Color.orange
            )
            
            MetricCard(
                title: "Recall",
                value: "\(String(format: "%.2f", result.metrics.recall * 100))%",
                icon: "arrow.clockwise",
                color: result.metrics.recall > 0.6 ? .green : .orange
            )
            
            MetricCard(
                title: "Max Drawdown",
                value: "\(String(format: "%.2f", result.metrics.maxDrawdown * 100))%",
                icon: "arrow.down",
                color: abs(result.metrics.maxDrawdown) < 0.1 ? .green : abs(result.metrics.maxDrawdown) < 0.2 ? .orange : .red
            )
            
            MetricCard(
                title: "Profit Factor",
                value: String(format: "%.2f", result.metrics.profitFactor),
                icon: "dollarsign.circle",
                color: result.metrics.profitFactor > 1.5 ? .green : result.metrics.profitFactor > 1.0 ? .orange : .red
            )
            
            MetricCard(
                title: "Total Trades",
                value: "\(result.metrics.totalTrades)",
                icon: "arrow.left.arrow.right",
                color: .blue
            )
            
            MetricCard(
                title: "Winning Trades",
                value: "\(result.metrics.winningTrades)",
                icon: "checkmark.circle",
                color: .green
            )
            
            MetricCard(
                title: "Losing Trades",
                value: "\(result.metrics.losingTrades)",
                icon: "xmark.circle",
                color: .red
            )
            
            MetricCard(
                title: "Sortino Ratio",
                value: String(format: "%.2f", result.metrics.sortinoRatio),
                icon: "chart.line.uptrend.xyaxis",
                color: result.metrics.sortinoRatio > 1.0 ? .green : .orange
            )
        }
    }
    
    // MARK: - Window Info Card
    
    private func windowInfoCard(_ result: WalkForwardResponse) -> some View {
        DashboardCard(title: "Walk-Forward Windows", icon: "rectangle.split.2x1", iconColor: .purple) {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("Training Window:")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Text("\(result.windows.trainWindow) bars")
                        .font(.caption.bold())
                }
                
                HStack {
                    Text("Test Window:")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Text("\(result.windows.testWindow) bars")
                        .font(.caption.bold())
                }
                
                HStack {
                    Text("Step Size:")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Text("\(result.windows.stepSize) bars")
                        .font(.caption.bold())
                }
                
                HStack {
                    Text("Test Periods:")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Text("\(result.windows.testPeriods.count)")
                        .font(.caption.bold())
                }
                
                Divider()
                
                HStack {
                    Text("Period:")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Text("\(result.period.start) to \(result.period.end)")
                        .font(.caption)
                }
                
                HStack {
                    Text("Bars Used:")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Text("\(result.barsUsed)")
                        .font(.caption.bold())
                }
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
            
            Text(value)
                .font(.title.bold())
                .foregroundStyle(.primary)
            
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding()
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(8)
    }
}

// MARK: - Preview

#Preview {
    WalkForwardOptimizationView(symbol: "AAPL", timeframe: "d1")
        .frame(width: 1200, height: 800)
}
