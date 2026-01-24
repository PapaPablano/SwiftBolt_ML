import SwiftUI
import Charts

struct StressTestingView: View {
    @StateObject private var viewModel = StressTestingViewModel()
    
    @State private var showConfiguration = true
    @State private var newSymbol = ""
    @State private var newQuantity: Double = 0
    @State private var newPrice: Double = 0
    @State private var newShockSymbol = ""
    @State private var newShockPercent: Double = 0
    
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
        .navigationTitle("Stress Testing")
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
                
                // Portfolio Positions
                VStack(alignment: .leading, spacing: 8) {
                    Text("Portfolio Positions")
                        .font(.headline)
                    
                    VStack(spacing: 8) {
                        HStack {
                            TextField("Symbol", text: $newSymbol)
                                .textFieldStyle(.roundedBorder)
                            TextField("Qty", value: $newQuantity, format: .number)
                                .textFieldStyle(.roundedBorder)
                                .frame(width: 80)
                            TextField("Price", value: $newPrice, format: .number)
                                .textFieldStyle(.roundedBorder)
                                .frame(width: 100)
                            
                            Button("Add") {
                                viewModel.addPosition(symbol: newSymbol, quantity: newQuantity, price: newPrice)
                                newSymbol = ""
                                newQuantity = 0
                                newPrice = 0
                            }
                            .buttonStyle(.bordered)
                        }
                        
                        if !viewModel.positions.isEmpty {
                            VStack(alignment: .leading, spacing: 4) {
                                ForEach(Array(viewModel.positions.keys.sorted()), id: \.self) { symbol in
                                    HStack {
                                        Text(symbol)
                                        Spacer()
                                        if let qty = viewModel.positions[symbol],
                                           let price = viewModel.prices[symbol] {
                                            Text("\(qty, specifier: "%.0f") @ $\(price, specifier: "%.2f")")
                                                .font(.caption)
                                                .foregroundStyle(.secondary)
                                        }
                                        Button(action: { viewModel.removePosition(symbol) }) {
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
                            
                            Text("Portfolio Value: $\(viewModel.portfolioValue, specifier: "%.2f")")
                                .font(.caption.bold())
                                .foregroundStyle(.secondary)
                        }
                    }
                }
                
                Divider()
                
                // Scenario Selection
                VStack(alignment: .leading, spacing: 8) {
                    Text("Stress Scenario")
                        .font(.headline)
                    
                    Toggle("Use Custom Scenario", isOn: $viewModel.useCustomScenario)
                    
                    if viewModel.useCustomScenario {
                        // Custom Shocks
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                TextField("Symbol", text: $newShockSymbol)
                                    .textFieldStyle(.roundedBorder)
                                TextField("% Change", value: $newShockPercent, format: .number)
                                    .textFieldStyle(.roundedBorder)
                                    .frame(width: 100)
                                
                                Button("Add") {
                                    viewModel.addCustomShock(symbol: newShockSymbol, shockPercent: newShockPercent / 100)
                                    newShockSymbol = ""
                                    newShockPercent = 0
                                }
                                .buttonStyle(.bordered)
                            }
                            
                            if !viewModel.customShocks.isEmpty {
                                VStack(alignment: .leading, spacing: 4) {
                                    ForEach(Array(viewModel.customShocks.keys.sorted()), id: \.self) { symbol in
                                        HStack {
                                            Text(symbol)
                                            Spacer()
                                            if let shock = viewModel.customShocks[symbol] {
                                                Text("\(shock * 100, specifier: "%.1f")%")
                                                    .font(.caption)
                                                    .foregroundStyle(shock < 0 ? .red : .green)
                                            }
                                            Button(action: { viewModel.removeCustomShock(symbol) }) {
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
                    } else {
                        // Historical Scenarios
                        Picker("", selection: $viewModel.selectedScenario) {
                            Text("Select Scenario").tag(nil as HistoricalScenario?)
                            ForEach(HistoricalScenario.allCases, id: \.self) { scenario in
                                HStack {
                                    Image(systemName: scenario.icon)
                                    Text(scenario.displayName)
                                }
                                .tag(scenario as HistoricalScenario?)
                            }
                        }
                        .pickerStyle(.menu)
                        
                        if let scenario = viewModel.selectedScenario {
                            Text(scenario.description)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
                
                Divider()
                
                // VaR Level
                VStack(alignment: .leading, spacing: 8) {
                    Text("VaR Level")
                        .font(.headline)
                    
                    HStack {
                        Text("\(viewModel.varLevel * 100, specifier: "%.0f")%")
                            .font(.caption.bold())
                        Slider(value: $viewModel.varLevel, in: 0.01...0.20)
                    }
                    
                    Text("Confidence level for Value at Risk")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                
                Spacer()
                
                // Run Button
                Button(action: {
                    Task {
                        await viewModel.runStressTest()
                    }
                }) {
                    HStack {
                        if viewModel.isLoading {
                            ProgressView()
                                .scaleEffect(0.7)
                        } else {
                            Image(systemName: "play.fill")
                        }
                        Text(viewModel.isLoading ? "Running..." : "Run Stress Test")
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .disabled(viewModel.isLoading || viewModel.positions.isEmpty || (!viewModel.useCustomScenario && viewModel.selectedScenario == nil) || (viewModel.useCustomScenario && viewModel.customShocks.isEmpty))
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
                } else if let result = viewModel.stressTestResult {
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
            Text("Running stress test...")
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
            Text("Stress Test Failed")
                .font(.headline)
            Text(error)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
            
            Button("Retry") {
                Task {
                    await viewModel.runStressTest()
                }
            }
            .buttonStyle(.borderedProminent)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 40)
    }
    
    private var emptyStateView: some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.largeTitle)
                .foregroundStyle(.secondary)
            Text("No Stress Test Results")
                .font(.headline)
            Text("Configure portfolio and scenario, then click 'Run Stress Test'")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 40)
    }
    
    private func resultsView(_ result: StressTestResponse) -> some View {
        VStack(spacing: 20) {
            // Impact Summary
            impactSummaryCard(result)
            
            // Risk Metrics
            riskMetricsCard(result)
            
            // Position Changes
            positionChangesTable(result)
        }
    }
    
    // MARK: - Impact Summary
    
    private func impactSummaryCard(_ result: StressTestResponse) -> some View {
        DashboardCard(title: "Portfolio Impact", icon: "exclamationmark.triangle.fill", iconColor: .red) {
            VStack(spacing: 16) {
                HStack(spacing: 30) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Current Value")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text("$\(result.portfolio.currentValue, specifier: "%.2f")")
                            .font(.title3.bold())
                    }
                    
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Change")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text("$\(result.portfolio.change, specifier: "%.2f")")
                            .font(.title3.bold())
                            .foregroundStyle(result.portfolio.change >= 0 ? .green : .red)
                    }
                    
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Change %")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text("\(result.portfolio.changePercent >= 0 ? "+" : "")\(result.portfolio.changePercent * 100, specifier: "%.2f")%")
                            .font(.title2.bold())
                            .foregroundStyle(result.portfolio.change >= 0 ? .green : .red)
                    }
                }
                .frame(maxWidth: .infinity)
            }
        }
    }
    
    // MARK: - Risk Metrics
    
    private func riskMetricsCard(_ result: StressTestResponse) -> some View {
        let severity = StressSeverity(rawValue: result.risk.severity) ?? .low
        
        return DashboardCard(title: "Risk Metrics", icon: "shield", iconColor: severity.color) {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("Severity:")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Text(result.risk.severity)
                        .font(.caption.bold())
                        .foregroundStyle(severity.color)
                }
                
                HStack {
                    Text("VaR Level:")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Text("\(result.risk.varLevel * 100, specifier: "%.0f")%")
                        .font(.caption.bold())
                }
                
                HStack {
                    Text("VaR Breached:")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Spacer()
                    HStack(spacing: 4) {
                        Image(systemName: result.risk.varBreached ? "checkmark.circle.fill" : "xmark.circle.fill")
                            .foregroundStyle(result.risk.varBreached ? .red : .green)
                        Text(result.risk.varBreached ? "Yes" : "No")
                            .font(.caption.bold())
                    }
                }
            }
        }
    }
    
    // MARK: - Position Changes Table
    
    private func positionChangesTable(_ result: StressTestResponse) -> some View {
        DashboardCard(title: "Position-Level Impact", icon: "list.bullet", iconColor: .orange) {
            if result.positionChanges.isEmpty {
                Text("No position changes")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity)
                    .padding()
            } else {
                let sortedSymbols = Array(result.positionChanges.keys.sorted())
                List(sortedSymbols, id: \.self) { symbol in
                    HStack {
                        Text(symbol)
                            .font(.caption.bold())
                            .frame(width: 100, alignment: .leading)
                        
                        if let qty = result.positions[symbol] {
                            Text(String(format: "%.0f", qty))
                                .font(.caption.monospacedDigit())
                                .frame(width: 80, alignment: .trailing)
                        }
                        
                        if let price = result.prices[symbol] {
                            Text("$\(String(format: "%.2f", price))")
                                .font(.caption.monospacedDigit())
                                .frame(width: 80, alignment: .trailing)
                        }
                        
                        if let change = result.positionChanges[symbol] {
                            Text("$\(String(format: "%.2f", change))")
                                .font(.caption.bold().monospacedDigit())
                                .foregroundStyle(change >= 0 ? .green : .red)
                                .frame(width: 100, alignment: .trailing)
                        }
                    }
                    .padding(.vertical, 4)
                }
                .frame(height: 300)
            }
        }
    }
}

// MARK: - Preview

#Preview {
    StressTestingView()
        .frame(width: 1200, height: 800)
}
