import SwiftUI
import Charts

struct BacktestingView: View {
    @StateObject private var viewModel = BacktestingViewModel()
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
        .navigationTitle("Backtesting: \(symbol)")
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
                
                // Strategy Selector
                VStack(alignment: .leading, spacing: 8) {
                    Text("Strategy")
                        .font(.headline)
                    
                    Picker("", selection: $viewModel.selectedStrategy) {
                        ForEach(TradingStrategy.allCases, id: \.self) { strategy in
                            HStack {
                                Image(systemName: strategy.icon)
                                Text(strategy.displayName)
                            }
                            .tag(strategy)
                        }
                    }
                    .pickerStyle(.menu)
                    
                    Text(viewModel.selectedStrategy.description)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                
                Divider()
                
                // Date Range
                VStack(alignment: .leading, spacing: 8) {
                    Text("Date Range")
                        .font(.headline)
                    
                    DatePicker("Start Date", selection: $viewModel.startDate, displayedComponents: .date)
                    DatePicker("End Date", selection: $viewModel.endDate, displayedComponents: .date)
                }
                
                Divider()
                
                // Initial Capital
                VStack(alignment: .leading, spacing: 8) {
                    Text("Initial Capital")
                        .font(.headline)
                    
                    HStack {
                        Text("$")
                        TextField("10000", value: $viewModel.initialCapital, format: .number)
                            .textFieldStyle(.roundedBorder)
                    }
                }
                
                Divider()
                
                // Strategy Parameters
                if !viewModel.selectedStrategy.defaultParams.isEmpty {
                    strategyParametersView
                }
                
                Spacer()
                
                // Run Button
                Button(action: {
                    Task {
                        await viewModel.runBacktest(symbol: symbol, timeframe: timeframe)
                    }
                }) {
                    HStack {
                        if viewModel.isLoading {
                            ProgressView()
                                .scaleEffect(0.7)
                        } else {
                            Image(systemName: "play.fill")
                        }
                        Text(viewModel.isLoading ? "Running..." : "Run Backtest")
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
    
    // MARK: - Strategy Parameters View
    
    @ViewBuilder
    private var strategyParametersView: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Strategy Parameters")
                .font(.headline)
            
            switch viewModel.selectedStrategy {
            case .supertrendAI:
                supertrendAIParams
            case .smaCrossover:
                smaCrossoverParams
            case .buyAndHold:
                EmptyView()
            }
        }
    }
    
    private var supertrendAIParams: some View {
        VStack(alignment: .leading, spacing: 8) {
            parameterSlider(
                label: "ATR Length",
                value: Binding(
                    get: { viewModel.strategyParams["atr_length"] as? Int ?? 10 },
                    set: { viewModel.updateStrategyParam(key: "atr_length", value: $0) }
                ),
                range: 5...20
            )
            
            parameterSlider(
                label: "Min Multiplier",
                value: Binding(
                    get: { viewModel.strategyParams["min_mult"] as? Double ?? 1.0 },
                    set: { viewModel.updateStrategyParam(key: "min_mult", value: $0) }
                ),
                range: 0.5...3.0,
                step: 0.1
            )
            
            parameterSlider(
                label: "Max Multiplier",
                value: Binding(
                    get: { viewModel.strategyParams["max_mult"] as? Double ?? 5.0 },
                    set: { viewModel.updateStrategyParam(key: "max_mult", value: $0) }
                ),
                range: 2.0...10.0,
                step: 0.1
            )
        }
    }
    
    private var smaCrossoverParams: some View {
        VStack(alignment: .leading, spacing: 8) {
            parameterSlider(
                label: "Fast Period",
                value: Binding(
                    get: { viewModel.strategyParams["fast_period"] as? Int ?? 20 },
                    set: { viewModel.updateStrategyParam(key: "fast_period", value: $0) }
                ),
                range: 5...50
            )
            
            parameterSlider(
                label: "Slow Period",
                value: Binding(
                    get: { viewModel.strategyParams["slow_period"] as? Int ?? 50 },
                    set: { viewModel.updateStrategyParam(key: "slow_period", value: $0) }
                ),
                range: 20...200
            )
        }
    }
    
    private func parameterSlider(label: String, value: Binding<Int>, range: ClosedRange<Int>) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(label)
                    .font(.caption)
                Spacer()
                Text("\(value.wrappedValue)")
                    .font(.caption.bold().monospacedDigit())
            }
            Slider(value: Binding(
                get: { Double(value.wrappedValue) },
                set: { value.wrappedValue = Int($0) }
            ), in: Double(range.lowerBound)...Double(range.upperBound))
        }
    }
    
    private func parameterSlider(label: String, value: Binding<Double>, range: ClosedRange<Double>, step: Double = 0.1) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(label)
                    .font(.caption)
                Spacer()
                Text("\(value.wrappedValue, specifier: "%.1f")")
                    .font(.caption.bold().monospacedDigit())
            }
            Slider(value: value, in: range, step: step)
        }
    }
    
    // MARK: - Results Panel
    
    private var resultsPanel: some View {
        ScrollView {
            VStack(spacing: 20) {
                if viewModel.isLoading {
                    loadingView
                } else if let error = viewModel.error {
                    errorView(error)
                } else if let result = viewModel.backtestResult {
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
            Text("Running backtest...")
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
            Text("Backtest Failed")
                .font(.headline)
            Text(error)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
            
            Button("Retry") {
                Task {
                    await viewModel.runBacktest(symbol: symbol, timeframe: timeframe)
                }
            }
            .buttonStyle(.borderedProminent)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 40)
    }
    
    private var emptyStateView: some View {
        VStack(spacing: 16) {
            Image(systemName: "chart.line.uptrend.xyaxis")
                .font(.largeTitle)
                .foregroundStyle(.secondary)
            Text("No Backtest Results")
                .font(.headline)
            Text("Configure your strategy and click 'Run Backtest' to see results")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 40)
    }
    
    private func resultsView(_ result: BacktestResponse) -> some View {
        VStack(spacing: 20) {
            // Performance Summary
            performanceSummaryCard(result)
            
            // Equity Curve Chart
            equityCurveChart(result)
            
            // Metrics Cards
            metricsCards(result)
            
            // Trade History
            tradeHistoryTable(result)
        }
    }
    
    // MARK: - Performance Summary
    
    private func performanceSummaryCard(_ result: BacktestResponse) -> some View {
        DashboardCard(title: "Performance Summary", icon: "chart.bar", iconColor: .blue) {
            VStack(spacing: 16) {
                HStack(spacing: 30) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Initial Capital")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text("$\(result.initialCapital, specifier: "%.2f")")
                            .font(.title3.bold())
                    }
                    
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Final Value")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text("$\(result.finalValue, specifier: "%.2f")")
                            .font(.title3.bold())
                    }
                    
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Total Return")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text("\(result.totalReturn >= 0 ? "+" : "")\(result.totalReturn * 100, specifier: "%.2f")%")
                            .font(.title2.bold())
                            .foregroundStyle(result.totalReturn >= 0 ? .green : .red)
                    }
                }
                .frame(maxWidth: .infinity)
            }
        }
    }
    
    // MARK: - Equity Curve Chart
    
    private func equityCurveChart(_ result: BacktestResponse) -> some View {
        DashboardCard(title: "Equity Curve", icon: "chart.line.uptrend.xyaxis", iconColor: .green) {
            if #available(macOS 13.0, *) {
                Chart {
                    ForEach(result.equityCurve) { point in
                        LineMark(
                            x: .value("Date", point.dateValue ?? Date()),
                            y: .value("Value", point.value)
                        )
                        .foregroundStyle(.blue)
                        .interpolationMethod(.catmullRom)
                    }
                }
                .chartXAxis {
                    AxisMarks(values: .stride(by: .month, count: 3)) { _ in
                        AxisGridLine()
                        AxisValueLabel(format: .dateTime.month().year())
                    }
                }
                .chartYAxis {
                    AxisMarks { value in
                        AxisGridLine()
                        AxisValueLabel {
                            if let doubleValue = value.as(Double.self) {
                                Text("$\(doubleValue, specifier: "%.0f")")
                            }
                        }
                    }
                }
                .frame(height: 300)
            } else {
                // Fallback for older macOS
                Text("Equity curve visualization requires macOS 13.0+")
                    .foregroundStyle(.secondary)
                    .frame(height: 300)
            }
        }
    }
    
    // MARK: - Metrics Cards
    
    private func metricsCards(_ result: BacktestResponse) -> some View {
        LazyVGrid(columns: [
            GridItem(.flexible()),
            GridItem(.flexible()),
            GridItem(.flexible()),
            GridItem(.flexible())
        ], spacing: 16) {
            if let sharpe = result.metrics.sharpeRatio {
                MetricCard(
                    title: "Sharpe Ratio",
                    value: String(format: "%.2f", sharpe),
                    icon: "chart.line.uptrend.xyaxis",
                    color: sharpe > 1.0 ? .green : sharpe > 0.5 ? .orange : .red
                )
            }
            
            if let drawdown = result.metrics.maxDrawdown {
                MetricCard(
                    title: "Max Drawdown",
                    value: "\(String(format: "%.2f", drawdown * 100))%",
                    icon: "arrow.down",
                    color: abs(drawdown) < 0.1 ? .green : abs(drawdown) < 0.2 ? .orange : .red
                )
            }
            
            if let winRate = result.metrics.winRate {
                MetricCard(
                    title: "Win Rate",
                    value: "\(String(format: "%.1f", winRate * 100))%",
                    icon: "checkmark.circle",
                    color: winRate > 0.5 ? .green : winRate > 0.4 ? .orange : .red
                )
            }
            
            MetricCard(
                title: "Total Trades",
                value: "\(result.metrics.totalTrades)",
                icon: "arrow.left.arrow.right",
                color: .blue
            )
        }
    }
    
    // MARK: - Trade History Table
    
    private func tradeHistoryTable(_ result: BacktestResponse) -> some View {
        DashboardCard(title: "Trade History", icon: "list.bullet", iconColor: .purple) {
            if result.trades.isEmpty {
                Text("No trades executed")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity)
                    .padding()
            } else {
                Table(result.trades) {
                    TableColumn("Date") { trade in
                        Text(trade.date)
                            .font(.caption)
                    }
                    .width(min: 100)
                    
                    TableColumn("Action") { trade in
                        HStack(spacing: 4) {
                            Image(systemName: trade.isBuy ? "arrow.up" : "arrow.down")
                                .font(.caption2)
                                .foregroundStyle(trade.isBuy ? .green : .red)
                            Text(trade.formattedAction)
                                .font(.caption)
                        }
                    }
                    .width(min: 80)
                    
                    TableColumn("Quantity") { trade in
                        Text("\(trade.quantity)")
                            .font(.caption.monospacedDigit())
                    }
                    .width(min: 80)
                    
                    TableColumn("Price") { trade in
                        Text("$\(trade.price, specifier: "%.2f")")
                            .font(.caption.monospacedDigit())
                    }
                    .width(min: 80)
                    
                    TableColumn("P&L") { trade in
                        Text(trade.formattedPnl)
                            .font(.caption.bold().monospacedDigit())
                            .foregroundStyle(trade.pnl ?? 0 >= 0 ? .green : .red)
                    }
                    .width(min: 80)
                }
                .frame(height: 300)
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
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: icon)
                    .font(.caption)
                    .foregroundStyle(color)
                Text(title)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            
            Text(value)
                .font(.title3.bold())
                .foregroundStyle(color)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

// MARK: - Preview

#Preview {
    BacktestingView(symbol: "AAPL", timeframe: "d1")
        .frame(width: 1200, height: 800)
}
