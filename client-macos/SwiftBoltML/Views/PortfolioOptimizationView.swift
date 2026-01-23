import SwiftUI
import Charts

struct PortfolioOptimizationView: View {
    @StateObject private var viewModel = PortfolioOptimizationViewModel()
    
    @State private var showConfiguration = true
    @State private var newSymbol = ""
    
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
        .navigationTitle("Portfolio Optimization")
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
                
                // Symbols Input
                VStack(alignment: .leading, spacing: 8) {
                    Text("Symbols")
                        .font(.headline)
                    
                    HStack {
                        TextField("AAPL", text: $newSymbol)
                            .textFieldStyle(.roundedBorder)
                            .onSubmit {
                                viewModel.addSymbol(newSymbol)
                                newSymbol = ""
                            }
                        
                        Button("Add") {
                            viewModel.addSymbol(newSymbol)
                            newSymbol = ""
                        }
                        .buttonStyle(.bordered)
                    }
                    
                    if !viewModel.symbols.isEmpty {
                        VStack(alignment: .leading, spacing: 4) {
                            ForEach(viewModel.symbols, id: \.self) { symbol in
                                HStack {
                                    Text(symbol)
                                    Spacer()
                                    Button(action: { viewModel.removeSymbol(symbol) }) {
                                        Image(systemName: "xmark.circle.fill")
                                            .foregroundStyle(.red)
                                    }
                                    .buttonStyle(.plain)
                                }
                                .padding(.vertical, 2)
                            }
                        }
                        .padding(8)
                        .background(Color(nsColor: .controlBackgroundColor))
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                    }
                }
                
                Divider()
                
                // Method Selector
                VStack(alignment: .leading, spacing: 8) {
                    Text("Optimization Method")
                        .font(.headline)
                    
                    Picker("", selection: $viewModel.selectedMethod) {
                        ForEach(OptimizationMethod.allCases, id: \.self) { method in
                            HStack {
                                Image(systemName: method.icon)
                                Text(method.displayName)
                            }
                            .tag(method)
                        }
                    }
                    .pickerStyle(.menu)
                    
                    Text(viewModel.selectedMethod.description)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                
                Divider()
                
                // Parameters
                VStack(alignment: .leading, spacing: 8) {
                    Text("Parameters")
                        .font(.headline)
                    
                    HStack {
                        Text("Lookback Days:")
                        TextField("252", value: $viewModel.lookbackDays, format: .number)
                            .textFieldStyle(.roundedBorder)
                    }
                    
                    HStack {
                        Text("Risk-Free Rate:")
                        TextField("0.02", value: $viewModel.riskFreeRate, format: .number)
                            .textFieldStyle(.roundedBorder)
                    }
                    
                    if viewModel.selectedMethod == .efficient {
                        HStack {
                            Text("Target Return:")
                            TextField("0.10", value: $viewModel.targetReturn, format: .number)
                                .textFieldStyle(.roundedBorder)
                        }
                    }
                    
                    HStack {
                        Text("Min Weight:")
                        TextField("0.0", value: $viewModel.minWeight, format: .number)
                            .textFieldStyle(.roundedBorder)
                    }
                    
                    HStack {
                        Text("Max Weight:")
                        TextField("1.0", value: $viewModel.maxWeight, format: .number)
                            .textFieldStyle(.roundedBorder)
                    }
                }
                
                Spacer()
                
                // Run Button
                Button(action: {
                    Task {
                        await viewModel.optimizePortfolio()
                    }
                }) {
                    HStack {
                        if viewModel.isLoading {
                            ProgressView()
                                .scaleEffect(0.7)
                        } else {
                            Image(systemName: "play.fill")
                        }
                        Text(viewModel.isLoading ? "Optimizing..." : "Optimize Portfolio")
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .disabled(viewModel.isLoading || viewModel.symbols.isEmpty)
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
                } else if let result = viewModel.optimizationResult {
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
            Text("Optimizing portfolio...")
                .font(.headline)
            Text("This may take a few moments")
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
                    await viewModel.optimizePortfolio()
                }
            }
            .buttonStyle(.borderedProminent)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 40)
    }
    
    private var emptyStateView: some View {
        VStack(spacing: 16) {
            Image(systemName: "chart.pie")
                .font(.largeTitle)
                .foregroundStyle(.secondary)
            Text("No Optimization Results")
                .font(.headline)
            Text("Add symbols and click 'Optimize Portfolio' to see results")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 40)
    }
    
    private func resultsView(_ result: PortfolioOptimizeResponse) -> some View {
        VStack(spacing: 20) {
            // Performance Summary
            performanceSummaryCard(result)
            
            // Allocation Chart
            allocationChart(result)
            
            // Allocation Table
            allocationTable(result)
        }
    }
    
    // MARK: - Performance Summary
    
    private func performanceSummaryCard(_ result: PortfolioOptimizeResponse) -> some View {
        DashboardCard(title: "Portfolio Performance", icon: "chart.bar", iconColor: .blue) {
            VStack(spacing: 16) {
                HStack(spacing: 30) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Expected Return")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text("\(result.allocation.expectedReturn * 100, specifier: "%.2f")%")
                            .font(.title3.bold())
                    }
                    
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Volatility")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text("\(result.allocation.volatility * 100, specifier: "%.2f")%")
                            .font(.title3.bold())
                    }
                    
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Sharpe Ratio")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text("\(result.allocation.sharpeRatio, specifier: "%.2f")")
                            .font(.title2.bold())
                            .foregroundStyle(result.allocation.sharpeRatio > 1.0 ? .green : result.allocation.sharpeRatio > 0.5 ? .orange : .red)
                    }
                }
                .frame(maxWidth: .infinity)
            }
        }
    }
    
    // MARK: - Allocation Chart
    
    private func allocationChart(_ result: PortfolioOptimizeResponse) -> some View {
        DashboardCard(title: "Portfolio Allocation", icon: "chart.pie", iconColor: .purple) {
            if #available(macOS 13.0, *) {
                Chart {
                    ForEach(Array(result.allocation.weights.keys.sorted()), id: \.self) { symbol in
                        if let weight = result.allocation.weights[symbol] {
                            SectorMark(
                                angle: .value("Weight", weight),
                                innerRadius: .ratio(0.5),
                                angularInset: 2
                            )
                            .foregroundStyle(by: .value("Symbol", symbol))
                            .annotation(position: .overlay) {
                                if weight > 0.05 {
                                    Text("\(weight * 100, specifier: "%.0f")%")
                                        .font(.caption2.bold())
                                }
                            }
                        }
                    }
                }
                .frame(height: 300)
            } else {
                Text("Allocation chart requires macOS 13.0+")
                    .foregroundStyle(.secondary)
                    .frame(height: 300)
            }
        }
    }
    
    // MARK: - Allocation Table
    
    private func allocationTable(_ result: PortfolioOptimizeResponse) -> some View {
        DashboardCard(title: "Allocation Details", icon: "list.bullet", iconColor: .green) {
            let sortedSymbols = Array(result.allocation.weights.keys.sorted())
            List(sortedSymbols, id: \.self) { symbol in
                HStack {
                    Text(symbol)
                        .font(.caption.bold())
                        .frame(width: 100, alignment: .leading)
                    
                    if let weight = result.allocation.weights[symbol] {
                        Text("\(String(format: "%.2f", weight * 100))%")
                            .font(.caption.monospacedDigit())
                            .frame(width: 100, alignment: .trailing)
                        
                        ProgressView(value: weight)
                            .progressViewStyle(.linear)
                            .frame(maxWidth: .infinity)
                    }
                }
                .padding(.vertical, 4)
            }
            .frame(height: 200)
        }
    }
}

// MARK: - Preview

#Preview {
    PortfolioOptimizationView()
        .frame(width: 1200, height: 800)
}
