import SwiftUI

// MARK: - Web-Style Strategy Builder with Full Indicator Support

struct StrategyBuilderWebStyle: View {
    @StateObject private var viewModel = StrategyBuilderViewModel()
    @State private var selectedStrategy: Strategy?
    @State private var selectedTab = 0 // 0 = Editor, 1 = Backtest
    
    var body: some View {
        VStack(spacing: 0) {
            // Header with strategy selector and tabs
            headerBar
            
            Divider()
            
            // Main content
            if let strategy = selectedStrategy {
                if selectedTab == 0 {
                    StrategyEditorWebStyle(strategy: $selectedStrategy, viewModel: viewModel)
                } else {
                    BacktestWebStyle(strategy: strategy, viewModel: viewModel)
                }
            } else {
                EmptyStrategyView(onCreate: { newStrategy in
                    selectedStrategy = newStrategy
                    viewModel.addStrategy(newStrategy)
                })
            }
        }
        .background(Color(.windowBackgroundColor))
    }
    
    private var headerBar: some View {
        HStack(spacing: 16) {
            // Strategy Picker
            Menu {
                ForEach(viewModel.strategies) { strategy in
                    Button(strategy.name) {
                        selectedStrategy = strategy
                    }
                }
                Divider()
                Button("+ New Strategy") {
                    let newStrategy = Strategy(name: "New Strategy")
                    viewModel.addStrategy(newStrategy)
                    selectedStrategy = newStrategy
                }
            } label: {
                HStack {
                    Text(selectedStrategy?.name ?? "Select Strategy")
                        .font(.headline)
                    Image(systemName: "chevron.down")
                        .font(.caption)
                }
            }
            .frame(minWidth: 180)
            
            Divider()
                .frame(height: 24)
            
            // Editor/Backtest Tabs
            Picker("", selection: $selectedTab) {
                Text("Editor").tag(0)
                Text("Backtest").tag(1)
            }
            .pickerStyle(.segmented)
            .frame(width: 180)
            
            Spacer()
            
            // Active Toggle
            if let strategy = selectedStrategy {
                Toggle("Active", isOn: Binding(
                    get: { strategy.isActive },
                    set: { newValue in
                        var updated = strategy
                        updated.isActive = newValue
                        selectedStrategy = updated
                        viewModel.saveStrategy(updated)
                    }
                ))
                .toggleStyle(.switch)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(Color(.controlBackgroundColor))
    }
}

// MARK: - Empty Strategy View

struct EmptyStrategyView: View {
    let onCreate: (Strategy) -> Void
    @State private var showingNew = false
    
    var body: some View {
        VStack(spacing: 24) {
            Spacer()
            
            Image(systemName: "chart.line.uptrend.xyaxis")
                .font(.system(size: 72))
                .foregroundColor(.accentColor)
            
            Text("Welcome to Strategy Builder")
                .font(.title2)
                .fontWeight(.bold)
            
            Text("Create and test custom trading strategies using technical indicators and conditions.")
                .font(.body)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 400)
            
            Button(action: { showingNew = true }) {
                Label("Create Your First Strategy", systemImage: "plus.circle.fill")
                    .font(.headline)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            
            Spacer()
        }
        .sheet(isPresented: $showingNew) {
            NewStrategyDialog { name, description in
                let strategy = Strategy(name: name, description: description)
                onCreate(strategy)
                showingNew = false
            }
            .frame(minWidth: 400, minHeight: 300)
        }
    }
}

// MARK: - Strategy Editor (Web Style)

struct StrategyEditorWebStyle: View {
    @Binding var strategy: Strategy?
    @ObservedObject var viewModel: StrategyBuilderViewModel
    @State private var showingAddEntry = false
    @State private var showingAddExit = false
    @State private var editingCondition: StrategyCondition?
    @State private var conditionEditType: ConditionType?
    
    enum ConditionType { case entry, exit }
    
    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                if let strategyBinding = Binding($strategy) {
                    let strategy = strategyBinding.wrappedValue
                    // Strategy Info Card
                    StrategyInfoCard(strategy: strategyBinding, onSave: {
                        viewModel.saveStrategy(strategyBinding.wrappedValue)
                    })
                    
                    // Entry Conditions
                    ConditionsCardWeb(
                        title: "Entry Conditions",
                        icon: "arrow.down.circle.fill",
                        color: .green,
                        conditions: strategy.entryConditions,
                        onAdd: { showingAddEntry = true },
                        onEdit: { condition in
                            editingCondition = condition
                            conditionEditType = .entry
                        },
                        onDelete: { index in
                            strategyBinding.wrappedValue.entryConditions.remove(at: index)
                            viewModel.saveStrategy(strategyBinding.wrappedValue)
                        }
                    )
                    
                    // Exit Conditions
                    ConditionsCardWeb(
                        title: "Exit Conditions",
                        icon: "arrow.up.circle.fill",
                        color: .red,
                        conditions: strategy.exitConditions,
                        onAdd: { showingAddExit = true },
                        onEdit: { condition in
                            editingCondition = condition
                            conditionEditType = .exit
                        },
                        onDelete: { index in
                            strategyBinding.wrappedValue.exitConditions.remove(at: index)
                            viewModel.saveStrategy(strategyBinding.wrappedValue)
                        }
                    )
                    
                    // Parameters
                    ParametersCardWeb(strategy: strategyBinding, onSave: {
                        viewModel.saveStrategy(strategyBinding.wrappedValue)
                    })
                    
                    // Visual Map
                    StrategyMapWeb(entryCount: strategy.entryConditions.count, exitCount: strategy.exitConditions.count)
                }
            }
            .padding(20)
        }
        .sheet(isPresented: $showingAddEntry) {
            ConditionEditorWeb { condition in
                if var strategy = strategy {
                    strategy.entryConditions.append(condition)
                    viewModel.saveStrategy(strategy)
                    self.strategy = strategy
                }
                showingAddEntry = false
            }
            .frame(minWidth: 500, minHeight: 400)
        }
        .sheet(isPresented: $showingAddExit) {
            ConditionEditorWeb { condition in
                if var strategy = strategy {
                    strategy.exitConditions.append(condition)
                    viewModel.saveStrategy(strategy)
                    self.strategy = strategy
                }
                showingAddExit = false
            }
            .frame(minWidth: 500, minHeight: 400)
        }
        .sheet(item: $editingCondition) { condition in
            ConditionEditorWeb(existingCondition: condition) { updated in
                if var strategy = strategy, let type = conditionEditType {
                    if type == .entry, let index = strategy.entryConditions.firstIndex(where: { $0.id == condition.id }) {
                        strategy.entryConditions[index] = updated
                    } else if type == .exit, let index = strategy.exitConditions.firstIndex(where: { $0.id == condition.id }) {
                        strategy.exitConditions[index] = updated
                    }
                    viewModel.saveStrategy(strategy)
                    self.strategy = strategy
                }
                editingCondition = nil
            }
            .frame(minWidth: 500, minHeight: 400)
        }
    }
}

// MARK: - Strategy Info Card

struct StrategyInfoCard: View {
    @Binding var strategy: Strategy
    let onSave: () -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "doc.text")
                    .foregroundColor(.accentColor)
                Text("Strategy Details")
                    .font(.headline)
                Spacer()
            }
            
            VStack(alignment: .leading, spacing: 8) {
                Text("Name")
                    .font(.caption)
                    .foregroundColor(.secondary)
                TextField("Strategy Name", text: $strategy.name)
                    .textFieldStyle(.roundedBorder)
                    .onSubmit { onSave() }
            }
            
            VStack(alignment: .leading, spacing: 8) {
                Text("Description")
                    .font(.caption)
                    .foregroundColor(.secondary)
                TextEditor(text: Binding(
                    get: { strategy.description ?? "" },
                    set: { strategy.description = $0.isEmpty ? nil : $0 }
                ))
                .frame(height: 60)
                .background(Color(.textBackgroundColor))
                .cornerRadius(6)
                .onChange(of: strategy.description) { _ in onSave() }
            }
        }
        .padding()
        .background(Color(.controlBackgroundColor))
        .cornerRadius(12)
    }
}

// MARK: - Conditions Card (Web Style)

struct ConditionsCardWeb: View {
    let title: String
    let icon: String
    let color: Color
    let conditions: [StrategyCondition]
    let onAdd: () -> Void
    let onEdit: (StrategyCondition) -> Void
    let onDelete: (Int) -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label(title, systemImage: icon)
                    .font(.headline)
                    .foregroundColor(color)
                Spacer()
                Button(action: onAdd) {
                    Label("Add", systemImage: "plus")
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
            }
            
            if conditions.isEmpty {
                VStack(spacing: 8) {
                    Image(systemName: "plus.circle")
                        .font(.system(size: 32))
                        .foregroundColor(.secondary)
                    Text("No \(title.lowercased()) yet")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    Button("Add First Condition", action: onAdd)
                        .buttonStyle(.borderedProminent)
                        .controlSize(.small)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 30)
            } else {
                LazyVStack(spacing: 8) {
                    ForEach(Array(conditions.enumerated()), id: \.element.id) { index, condition in
                        ConditionRowWeb(condition: condition, color: color)
                            .contentShape(Rectangle())
                            .onTapGesture {
                                onEdit(condition)
                            }
                            .contextMenu {
                                Button("Edit") {
                                    onEdit(condition)
                                }
                                Divider()
                                Button(role: .destructive) {
                                    onDelete(index)
                                } label: {
                                    Label("Delete", systemImage: "trash")
                                }
                            }
                    }
                }
            }
        }
        .padding()
        .background(Color(.controlBackgroundColor))
        .cornerRadius(12)
    }
}

struct ConditionRowWeb: View {
    let condition: StrategyCondition
    let color: Color
    
    var body: some View {
        HStack(spacing: 12) {
            // Indicator badge
            HStack(spacing: 4) {
                Image(systemName: "function")
                    .font(.caption)
                Text(condition.indicator)
                    .font(.system(size: 13, weight: .medium))
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(color.opacity(0.15))
            .foregroundColor(color)
            .cornerRadius(6)
            
            // Operator
            Text(condition.operator.replacingOccurrences(of: "_", with: " ").uppercased())
                .font(.caption)
                .foregroundColor(.secondary)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(Color.secondary.opacity(0.1))
                .cornerRadius(4)
            
            // Value
            Text(String(format: "%.2f", condition.value))
                .font(.system(size: 13, weight: .semibold))
            
            Spacer()
            
            // Parameters indicator
            if let params = condition.parameters, !params.isEmpty {
                Image(systemName: "gearshape.fill")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Image(systemName: "chevron.right")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding()
        .background(Color(.windowBackgroundColor))
        .cornerRadius(8)
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(color.opacity(0.2), lineWidth: 1)
        )
    }
}

// MARK: - Parameters Card (Web Style)

struct ParametersCardWeb: View {
    @Binding var strategy: Strategy
    let onSave: () -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "slider.horizontal.3")
                    .foregroundColor(.accentColor)
                Text("Parameters")
                    .font(.headline)
                Spacer()
            }
            
            HStack(spacing: 16) {
                ParameterFieldWeb(
                    label: "Position Size",
                    value: $strategy.positionSize,
                    suffix: "%",
                    range: 1...100,
                    onChange: onSave
                )
                
                ParameterFieldWeb(
                    label: "Stop Loss",
                    value: $strategy.stopLoss,
                    suffix: "%",
                    range: 0.1...50,
                    onChange: onSave
                )
                
                ParameterFieldWeb(
                    label: "Take Profit",
                    value: $strategy.takeProfit,
                    suffix: "%",
                    range: 0.1...100,
                    onChange: onSave
                )
            }
        }
        .padding()
        .background(Color(.controlBackgroundColor))
        .cornerRadius(12)
    }
}

struct ParameterFieldWeb: View {
    let label: String
    @Binding var value: Double
    let suffix: String
    let range: ClosedRange<Double>
    let onChange: () -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label)
                .font(.caption)
                .foregroundColor(.secondary)
            
            HStack(spacing: 4) {
                TextField("", value: $value, format: .number)
                    .textFieldStyle(.roundedBorder)
                    .frame(width: 60)
                    .onSubmit { onChange() }
                
                Text(suffix)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Slider(value: $value, in: range, step: 0.5) { _ in
                onChange()
            }
            .frame(width: 100)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Strategy Map (Web Style)

struct StrategyMapWeb: View {
    let entryCount: Int
    let exitCount: Int
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "map")
                    .foregroundColor(.accentColor)
                Text("Visual Strategy Map")
                    .font(.headline)
                Spacer()
                
                HStack(spacing: 12) {
                    HStack(spacing: 4) {
                        Circle().fill(Color.green).frame(width: 8, height: 8)
                        Text("Entry")
                            .font(.caption)
                    }
                    HStack(spacing: 4) {
                        Circle().fill(Color.red).frame(width: 8, height: 8)
                        Text("Exit")
                            .font(.caption)
                    }
                }
                .foregroundColor(.secondary)
            }
            
            // Visual flow diagram
            HStack(spacing: 24) {
                Spacer()
                
                // Entry column
                VStack(spacing: 10) {
                    Text("ENTRY")
                        .font(.caption2)
                        .foregroundColor(.green)
                    
                    if entryCount == 0 {
                        PlaceholderNode(color: .green)
                    } else {
                        ForEach(0..<min(entryCount, 3), id: \.self) { _ in
                            ConditionNode(color: .green, icon: "arrow.down")
                        }
                        if entryCount > 3 {
                            Text("+\(entryCount - 3) more")
                                .font(.caption2)
                                .foregroundColor(.secondary)
                        }
                    }
                }
                
                // Arrow
                VStack {
                    Rectangle()
                        .fill(Color.secondary.opacity(0.3))
                        .frame(width: 40, height: 2)
                    Image(systemName: "arrow.right")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                // Strategy center
                ZStack {
                    Circle()
                        .fill(Color.accentColor.opacity(0.2))
                        .frame(width: 60, height: 60)
                    VStack(spacing: 2) {
                        Image(systemName: "brain.head.profile")
                            .font(.title3)
                        Text("STRATEGY")
                            .font(.caption2)
                    }
                    .foregroundColor(.accentColor)
                }
                
                // Arrow
                VStack {
                    Rectangle()
                        .fill(Color.secondary.opacity(0.3))
                        .frame(width: 40, height: 2)
                    Image(systemName: "arrow.right")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                // Exit column
                VStack(spacing: 10) {
                    Text("EXIT")
                        .font(.caption2)
                        .foregroundColor(.red)
                    
                    if exitCount == 0 {
                        PlaceholderNode(color: .red)
                    } else {
                        ForEach(0..<min(exitCount, 3), id: \.self) { _ in
                            ConditionNode(color: .red, icon: "arrow.up")
                        }
                        if exitCount > 3 {
                            Text("+\(exitCount - 3) more")
                                .font(.caption2)
                                .foregroundColor(.secondary)
                        }
                    }
                }
                
                Spacer()
            }
            .padding(.vertical, 20)
            .background(Color(.windowBackgroundColor))
            .cornerRadius(8)
        }
        .padding()
        .background(Color(.controlBackgroundColor))
        .cornerRadius(12)
    }
}

struct ConditionNode: View {
    let color: Color
    let icon: String
    
    var body: some View {
        ZStack {
            Circle()
                .fill(color.opacity(0.2))
                .frame(width: 36, height: 36)
            Image(systemName: icon)
                .font(.system(size: 14))
                .foregroundColor(color)
        }
    }
}

struct PlaceholderNode: View {
    let color: Color
    
    var body: some View {
        ZStack {
            Circle()
                .stroke(color.opacity(0.3), lineWidth: 1)
                .frame(width: 36, height: 36)
            Image(systemName: "plus")
                .font(.system(size: 14))
                .foregroundColor(color.opacity(0.5))
        }
    }
}

// MARK: - Condition Editor (Full Web-Style)

struct ConditionEditorWeb: View {
    var existingCondition: StrategyCondition?
    let onSave: (StrategyCondition) -> Void
    @Environment(\.dismiss) private var dismiss
    
    @State private var selectedCategory: StrategyIndicatorCategory = .momentum
    @State private var selectedIndicator: String = "RSI"
    @State private var selectedOperator: String = "below"
    @State private var value: Double = 30.0
    @State private var params: [String: String] = ["period": "14"]
    
    // Full indicator list matching web app
    let indicators: [StrategyIndicatorCategory: [String]] = [
        .supertrend: ["SuperTrend AI", "SuperTrend Trend", "SuperTrend Signal", "SuperTrend Factor", "SuperTrend Strength"],
        .momentum: ["RSI", "Stochastic", "Stochastic %K", "Stochastic %D", "KDJ K", "KDJ D", "KDJ J", "Williams %R", "CCI", "Momentum", "ROC", "MFI", "Volume ROC"],
        .trend: ["MACD", "MACD Signal", "MACD Histogram", "SMA", "EMA", "ADX", "DI+", "DI-", "Parabolic SAR", "ZigZag"],
        .volatility: ["Bollinger Bands", "ATR", "BB Width", "BB %B", "Keltner Upper", "Keltner Lower", "ATR %"],
        .volume: ["Volume", "Volume SMA", "VWAP", "OBV", "VWAP (Session)"],
        .price: ["Price", "Price vs SMA", "Price vs EMA", "High", "Low", "Close", "Open"],
        .divergence: ["RSI Divergence", "MACD Divergence", "Price Divergence"]
    ]
    
    let operators = ["above", "below", "crosses_above", "crosses_below"]
    
    init(existingCondition: StrategyCondition? = nil, onSave: @escaping (StrategyCondition) -> Void) {
        self.existingCondition = existingCondition
        self.onSave = onSave
        
        if let condition = existingCondition {
            _selectedIndicator = State(initialValue: condition.indicator)
            _selectedOperator = State(initialValue: condition.operator)
            _value = State(initialValue: condition.value)
            if let p = condition.parameters {
                _params = State(initialValue: p)
            }
        }
    }
    
    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text(existingCondition == nil ? "Add Condition" : "Edit Condition")
                    .font(.headline)
                Spacer()
                Button("Cancel") { dismiss() }
                    .buttonStyle(.bordered)
            }
            .padding()
            .background(Color(.controlBackgroundColor))
            
            Divider()
            
            // Form
            Form {
                // Category Picker
                Section("Category") {
                    Picker("Category", selection: $selectedCategory) {
                        ForEach(StrategyIndicatorCategory.allCases) { category in
                            Text(category.rawValue).tag(category)
                        }
                    }
                    .pickerStyle(.segmented)
                    .onChange(of: selectedCategory) { _ in
                        // Auto-select first indicator in category
                        if let first = indicators[selectedCategory]?.first {
                            selectedIndicator = first
                        }
                    }
                }
                
                // Indicator Picker
                Section("Indicator") {
                    Picker("Indicator", selection: $selectedIndicator) {
                        ForEach(indicators[selectedCategory] ?? [], id: \.self) { ind in
                            Text(ind).tag(ind)
                        }
                    }
                    .pickerStyle(.menu)
                }
                
                // Operator
                Section("Condition") {
                    Picker("Operator", selection: $selectedOperator) {
                        ForEach(operators, id: \.self) { op in
                            Text(op.replacingOccurrences(of: "_", with: " ").capitalized)
                                .tag(op)
                        }
                    }
                    .pickerStyle(.segmented)
                    
                    HStack {
                        Text("Value")
                        Spacer()
                        TextField("30", value: $value, format: .number)
                            .textFieldStyle(.roundedBorder)
                            .frame(width: 80)
                    }
                }
                
                // Parameters
                Section("Parameters") {
                    ForEach(Array(params.keys.sorted()), id: \.self) { key in
                        HStack {
                            Text(key.capitalized)
                            Spacer()
                            TextField("Value", text: Binding(
                                get: { params[key] ?? "" },
                                set: { params[key] = $0 }
                            ))
                            .textFieldStyle(.roundedBorder)
                            .frame(width: 100)
                        }
                    }
                    
                    Button("+ Add Parameter") {
                        params["param\(params.count + 1)"] = ""
                    }
                    .buttonStyle(.borderless)
                }
                
                // Preview
                Section("Preview") {
                    HStack {
                        Spacer()
                        VStack(spacing: 8) {
                            Text("\(selectedIndicator)")
                                .font(.headline)
                            Text("\(selectedOperator.replacingOccurrences(of: "_", with: " ").uppercased()) \(String(format: "%.2f", value))")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                        }
                        Spacer()
                    }
                    .padding(.vertical, 8)
                }
            }
            .formStyle(.grouped)
            
            Divider()
            
            // Footer buttons
            HStack {
                Spacer()
                Button("Cancel") { dismiss() }
                    .buttonStyle(.bordered)
                Button("Save Condition") {
                    let condition = StrategyCondition(
                        id: existingCondition?.id ?? UUID(),
                        indicator: selectedIndicator,
                        operator: selectedOperator,
                        value: value,
                        parameters: params.isEmpty ? nil : params
                    )
                    onSave(condition)
                }
                .buttonStyle(.borderedProminent)
            }
            .padding()
            .background(Color(.controlBackgroundColor))
        }
        .frame(width: 500, height: 550)
    }
}

enum StrategyIndicatorCategory: String, CaseIterable, Identifiable {
    case supertrend = "SuperTrend AI"
    case momentum = "Momentum"
    case trend = "Trend"
    case volatility = "Volatility"
    case volume = "Volume"
    case price = "Price"
    case divergence = "Divergence"
    
    var id: String { rawValue }
}

// MARK: - Backtest (Web Style)

struct BacktestWebStyle: View {
    let strategy: Strategy
    @ObservedObject var viewModel: StrategyBuilderViewModel
    
    @State private var symbol = "AAPL"
    @State private var timeframe = "1D"
    @State private var isRunning = false
    @State private var result: BacktestResult?
    
    let symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "SPY", "QQQ", "IWM"]
    let timeframes = ["1D", "4H", "1H", "30m", "15m", "5m"]
    
    var body: some View {
        VStack(spacing: 0) {
            // Controls
            HStack(spacing: 16) {
                Picker("Symbol:", selection: $symbol) {
                    ForEach(symbols, id: \.self) { s in
                        Text(s).tag(s)
                    }
                }
                .frame(width: 100)
                
                Picker("Timeframe:", selection: $timeframe) {
                    ForEach(timeframes, id: \.self) { tf in
                        Text(tf).tag(tf)
                    }
                }
                .frame(width: 120)
                
                DatePicker("From", selection: .constant(Date().addingTimeInterval(-30*24*60*60)), displayedComponents: .date)
                    .labelsHidden()
                
                DatePicker("To", selection: .constant(Date()), displayedComponents: .date)
                    .labelsHidden()
                
                Spacer()
                
                Button(action: runBacktest) {
                    if isRunning {
                        ProgressView()
                            .scaleEffect(0.8)
                    } else {
                        Label("Run Backtest", systemImage: "play.fill")
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(isRunning)
            }
            .padding()
            
            Divider()
            
            if let result = result {
                BacktestResultsWeb(result: result)
            } else {
                VStack(spacing: 16) {
                    Spacer()
                    Image(systemName: "chart.bar.xaxis")
                        .font(.system(size: 60))
                        .foregroundColor(.secondary)
                    Text("Run a backtest to see results")
                        .font(.headline)
                        .foregroundColor(.secondary)
                    Spacer()
                }
            }
        }
    }
    
    private func runBacktest() {
        isRunning = true
        // Simulate API call
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) {
            result = BacktestResult.mock()
            isRunning = false
        }
    }
}

struct BacktestResultsWeb: View {
    let result: BacktestResult
    
    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Metrics Grid
                LazyVGrid(columns: [
                    GridItem(.flexible()),
                    GridItem(.flexible()),
                    GridItem(.flexible()),
                    GridItem(.flexible())
                ], spacing: 12) {
                    MetricCardWeb(title: "Total Trades", value: "\(result.totalTrades)", color: .blue, icon: "number")
                    MetricCardWeb(title: "Win Rate", value: String(format: "%.1f%%", result.winRate * 100), color: .green, icon: "percent")
                    MetricCardWeb(title: "Total Return", value: String(format: "%.2f%%", result.totalReturn * 100), color: result.totalReturn >= 0 ? .green : .red, icon: "arrow.up.forward")
                    MetricCardWeb(title: "Max Drawdown", value: String(format: "%.2f%%", result.maxDrawdown * 100), color: .orange, icon: "arrow.down")
                    MetricCardWeb(title: "Profit Factor", value: String(format: "%.2f", result.profitFactor), color: .purple, icon: "function")
                    MetricCardWeb(title: "Sharpe", value: String(format: "%.2f", result.sharpeRatio), color: .cyan, icon: "chart.line.uptrend.xyaxis")
                    MetricCardWeb(title: "Avg Win", value: String(format: "$%.2f", result.avgWin), color: .green, icon: "dollarsign")
                    MetricCardWeb(title: "Avg Loss", value: String(format: "$%.2f", result.avgLoss), color: .red, icon: "dollarsign")
                }
                .padding(.horizontal)
                
                // Trades Table
                TradesTableWeb(trades: result.trades)
                    .padding(.horizontal)
            }
            .padding(.vertical)
        }
    }
}

struct MetricCardWeb: View {
    let title: String
    let value: String
    let color: Color
    let icon: String
    
    var body: some View {
        VStack(spacing: 8) {
            HStack {
                Image(systemName: icon)
                    .font(.caption)
                    .foregroundColor(color)
                Spacer()
            }
            
            Text(value)
                .font(.system(size: 20, weight: .bold, design: .rounded))
                .foregroundColor(color)
            
            Text(title)
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12)
        .padding(.horizontal, 8)
        .background(Color(.controlBackgroundColor))
        .cornerRadius(10)
    }
}

struct TradesTableWeb: View {
    let trades: [Trade]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Trade History")
                .font(.headline)
            
            VStack(spacing: 0) {
                // Header
                HStack {
                    Text("Entry Date").font(.caption).bold()
                    Spacer()
                    Text("Exit Date").font(.caption).bold()
                    Spacer()
                    Text("Entry $").font(.caption).bold()
                    Spacer()
                    Text("Exit $").font(.caption).bold()
                    Spacer()
                    Text("P&L").font(.caption).bold()
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .background(Color.secondary.opacity(0.1))
                
                Divider()
                
                // Rows
                ForEach(trades) { trade in
                    HStack {
                        Text(trade.entryDate, format: .dateTime.month().day())
                            .font(.caption)
                        Spacer()
                        Text(trade.exitDate, format: .dateTime.month().day())
                            .font(.caption)
                        Spacer()
                        Text(String(format: "%.2f", trade.entryPrice))
                            .font(.caption)
                        Spacer()
                        Text(String(format: "%.2f", trade.exitPrice))
                            .font(.caption)
                        Spacer()
                        Text(String(format: "%.2f", trade.pnl))
                            .font(.caption)
                            .foregroundColor(trade.pnl >= 0 ? .green : .red)
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
                    .background(trade.pnl >= 0 ? Color.green.opacity(0.05) : Color.red.opacity(0.05))
                    
                    Divider()
                }
            }
            .background(Color(.windowBackgroundColor))
            .cornerRadius(8)
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(Color.secondary.opacity(0.1), lineWidth: 1)
            )
        }
        .padding()
        .background(Color(.controlBackgroundColor))
        .cornerRadius(12)
    }
}

// MARK: - New Strategy Dialog

struct NewStrategyDialog: View {
    let onCreate: (String, String?) -> Void
    @Environment(\.dismiss) private var dismiss
    
    @State private var name = ""
    @State private var description = ""
    
    var body: some View {
        VStack(spacing: 24) {
            Text("Create New Strategy")
                .font(.title2)
                .fontWeight(.bold)
            
            VStack(alignment: .leading, spacing: 8) {
                Text("Strategy Name *")
                    .font(.caption)
                    .foregroundColor(.secondary)
                TextField("My Strategy", text: $name)
                    .textFieldStyle(.roundedBorder)
            }
            
            VStack(alignment: .leading, spacing: 8) {
                Text("Description")
                    .font(.caption)
                    .foregroundColor(.secondary)
                TextField("Optional description...", text: $description)
                    .textFieldStyle(.roundedBorder)
            }
            
            HStack(spacing: 16) {
                Button("Cancel") { dismiss() }
                    .buttonStyle(.bordered)
                
                Button("Create Strategy") {
                    onCreate(name, description.isEmpty ? nil : description)
                }
                .buttonStyle(.borderedProminent)
                .disabled(name.isEmpty)
            }
        }
        .padding(32)
        .frame(width: 400)
    }
}

// MARK: - Models

struct Strategy: Identifiable, Hashable {
    let id = UUID()
    var name: String
    var description: String?
    var entryConditions: [StrategyCondition] = []
    var exitConditions: [StrategyCondition] = []
    var positionSize: Double = 10.0
    var stopLoss: Double = 2.0
    var takeProfit: Double = 4.0
    var isActive: Bool = true
    var createdAt: Date = Date()
    var updatedAt: Date = Date()
}

struct StrategyCondition: Identifiable, Hashable {
    let id: UUID
    var indicator: String
    var `operator`: String
    var value: Double
    var parameters: [String: String]?
    
    init(id: UUID = UUID(), indicator: String, operator: String, value: Double, parameters: [String: String]? = nil) {
        self.id = id
        self.indicator = indicator
        self.operator = `operator`
        self.value = value
        self.parameters = parameters
    }
}

struct BacktestResult {
    let totalTrades: Int
    let winRate: Double
    let totalReturn: Double
    let maxDrawdown: Double
    let profitFactor: Double
    let sharpeRatio: Double
    let avgWin: Double
    let avgLoss: Double
    let trades: [Trade]
    
    static func mock() -> BacktestResult {
        let trades: [Trade] = [
            Trade(entryDate: Date().addingTimeInterval(-5*24*60*60), exitDate: Date().addingTimeInterval(-4*24*60*60), entryPrice: 150, exitPrice: 155, pnl: 5.0),
            Trade(entryDate: Date().addingTimeInterval(-4*24*60*60), exitDate: Date().addingTimeInterval(-3*24*60*60), entryPrice: 155, exitPrice: 152, pnl: -3.0),
            Trade(entryDate: Date().addingTimeInterval(-3*24*60*60), exitDate: Date().addingTimeInterval(-2*24*60*60), entryPrice: 160, exitPrice: 165, pnl: 5.0),
            Trade(entryDate: Date().addingTimeInterval(-2*24*60*60), exitDate: Date().addingTimeInterval(-1*24*60*60), entryPrice: 165, exitPrice: 162, pnl: -3.0),
            Trade(entryDate: Date().addingTimeInterval(-1*24*60*60), exitDate: Date(), entryPrice: 170, exitPrice: 175, pnl: 5.0)
        ]
        return BacktestResult(
            totalTrades: 24,
            winRate: 0.625,
            totalReturn: 0.1847,
            maxDrawdown: 0.0823,
            profitFactor: 2.34,
            sharpeRatio: 1.56,
            avgWin: 245.50,
            avgLoss: -98.30,
            trades: trades
        )
    }
}

struct Trade: Identifiable {
    let id = UUID()
    let entryDate: Date
    let exitDate: Date
    let entryPrice: Double
    let exitPrice: Double
    let pnl: Double
}

// Reuse existing StrategyBuilderViewModel but with enhanced features
class StrategyBuilderViewModel: ObservableObject {
    @Published var strategies: [Strategy] = []
    
    init() {
        loadMockStrategies()
    }
    
    private func loadMockStrategies() {
        strategies = [
            Strategy(
                name: "RSI Oversold",
                description: "Buy when RSI below 30",
                entryConditions: [
                    StrategyCondition(indicator: "RSI", operator: "below", value: 30, parameters: ["period": "14"])
                ],
                exitConditions: [
                    StrategyCondition(indicator: "RSI", operator: "above", value: 70, parameters: ["period": "14"])
                ]
            ),
            Strategy(
                name: "MACD Crossover",
                description: "Trend following with MACD",
                entryConditions: [
                    StrategyCondition(indicator: "MACD", operator: "crosses_above", value: 0, parameters: nil)
                ],
                exitConditions: [
                    StrategyCondition(indicator: "MACD", operator: "crosses_below", value: 0, parameters: nil)
                ],
                isActive: false
            ),
            Strategy(
                name: "Supertrend",
                description: "Supertrend with MACD",
                entryConditions: [
                    StrategyCondition(indicator: "SuperTrend AI", operator: "above", value: 1, parameters: ["atr_length": "10"])
                ],
                exitConditions: [],
                isActive: true
            )
        ]
    }
    
    func addStrategy(_ strategy: Strategy) {
        strategies.append(strategy)
    }
    
    func deleteStrategy(_ strategy: Strategy) {
        strategies.removeAll { $0.id == strategy.id }
    }
    
    func saveStrategy(_ strategy: Strategy) {
        if let index = strategies.firstIndex(where: { $0.id == strategy.id }) {
            var updated = strategy
            updated.updatedAt = Date()
            strategies[index] = updated
        }
    }
}
