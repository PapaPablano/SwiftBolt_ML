import SwiftUI
import Charts

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
                        groups: strategy.entryGroups,
                        onAdd: { showingAddEntry = true },
                        onAddORGroup: {
                            strategyBinding.wrappedValue.entryGroups.append(ConditionGroup())
                            viewModel.saveStrategy(strategyBinding.wrappedValue)
                        },
                        onEdit: { condition in
                            editingCondition = condition
                            conditionEditType = .entry
                        },
                        onDelete: { groupIdx, condIdx in
                            strategyBinding.wrappedValue.entryGroups[groupIdx].conditions.remove(at: condIdx)
                            // Remove empty groups
                            if strategyBinding.wrappedValue.entryGroups[groupIdx].conditions.isEmpty {
                                strategyBinding.wrappedValue.entryGroups.remove(at: groupIdx)
                            }
                            viewModel.saveStrategy(strategyBinding.wrappedValue)
                        }
                    )

                    // Exit Conditions
                    ConditionsCardWeb(
                        title: "Exit Conditions",
                        icon: "arrow.up.circle.fill",
                        color: .red,
                        groups: strategy.exitGroups,
                        onAdd: { showingAddExit = true },
                        onAddORGroup: {
                            strategyBinding.wrappedValue.exitGroups.append(ConditionGroup())
                            viewModel.saveStrategy(strategyBinding.wrappedValue)
                        },
                        onEdit: { condition in
                            editingCondition = condition
                            conditionEditType = .exit
                        },
                        onDelete: { groupIdx, condIdx in
                            strategyBinding.wrappedValue.exitGroups[groupIdx].conditions.remove(at: condIdx)
                            if strategyBinding.wrappedValue.exitGroups[groupIdx].conditions.isEmpty {
                                strategyBinding.wrappedValue.exitGroups.remove(at: groupIdx)
                            }
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
                    if strategy.entryGroups.isEmpty {
                        strategy.entryGroups.append(ConditionGroup(conditions: [condition]))
                    } else {
                        strategy.entryGroups[strategy.entryGroups.count - 1].conditions.append(condition)
                    }
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
                    if strategy.exitGroups.isEmpty {
                        strategy.exitGroups.append(ConditionGroup(conditions: [condition]))
                    } else {
                        strategy.exitGroups[strategy.exitGroups.count - 1].conditions.append(condition)
                    }
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
                    let groups = type == .entry ? strategy.entryGroups : strategy.exitGroups
                    for (gi, group) in groups.enumerated() {
                        if let ci = group.conditions.firstIndex(where: { $0.id == condition.id }) {
                            if type == .entry {
                                strategy.entryGroups[gi].conditions[ci] = updated
                            } else {
                                strategy.exitGroups[gi].conditions[ci] = updated
                            }
                            break
                        }
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
                .onChange(of: strategy.description) { onSave() }
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
    let groups: [ConditionGroup]
    let onAdd: () -> Void
    let onAddORGroup: () -> Void
    let onEdit: (StrategyCondition) -> Void
    /// Delete a condition at (groupIndex, conditionIndex).
    let onDelete: (Int, Int) -> Void

    private var allConditions: [StrategyCondition] { ConditionGroup.flatten(groups) }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label(title, systemImage: icon)
                    .font(.headline)
                    .foregroundColor(color)
                Spacer()
                Button(action: onAddORGroup) {
                    Label("OR Group", systemImage: "plus.rectangle.on.rectangle")
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
                Button(action: onAdd) {
                    Label("Add", systemImage: "plus")
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
            }

            if allConditions.isEmpty {
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
                LazyVStack(spacing: 4) {
                    ForEach(Array(groups.enumerated()), id: \.element.id) { groupIndex, group in
                        // OR divider between groups
                        if groupIndex > 0 {
                            HStack {
                                VStack { Divider() }
                                Text("OR")
                                    .font(.caption2.weight(.bold))
                                    .foregroundColor(.orange)
                                    .padding(.horizontal, 8)
                                    .padding(.vertical, 2)
                                    .background(Color.orange.opacity(0.15))
                                    .cornerRadius(4)
                                VStack { Divider() }
                            }
                            .padding(.vertical, 4)
                        }

                        // Group box
                        VStack(spacing: 6) {
                            ForEach(Array(group.conditions.enumerated()), id: \.element.id) { condIndex, condition in
                                // AND divider within group
                                if condIndex > 0 {
                                    Text("AND")
                                        .font(.caption2)
                                        .foregroundColor(.secondary)
                                        .frame(maxWidth: .infinity, alignment: .center)
                                }
                                ConditionRowWeb(condition: condition, color: color)
                                    .contentShape(Rectangle())
                                    .onTapGesture { onEdit(condition) }
                                    .contextMenu {
                                        Button("Edit") { onEdit(condition) }
                                        Divider()
                                        Button(role: .destructive) {
                                            onDelete(groupIndex, condIndex)
                                        } label: {
                                            Label("Delete", systemImage: "trash")
                                        }
                                    }
                            }
                        }
                        .padding(8)
                        .background(Color(.controlBackgroundColor).opacity(0.5))
                        .overlay(
                            RoundedRectangle(cornerRadius: 8)
                                .stroke(color.opacity(0.2), lineWidth: 1)
                        )
                        .cornerRadius(8)
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

    private let directionOptions = [("long_only", "Long"), ("short_only", "Short"), ("long_short", "Both")]
    private let sizingOptions = [
        ("percent_of_equity", "% Equity"),
        ("fixed_dollar", "Fixed $"),
        ("half_kelly", "Kelly")
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Image(systemName: "slider.horizontal.3")
                    .foregroundColor(.accentColor)
                Text("Parameters")
                    .font(.headline)
                Spacer()
            }

            // Direction + position sizing row
            HStack(spacing: 16) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Direction")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Picker("", selection: $strategy.direction) {
                        ForEach(directionOptions, id: \.0) { opt in
                            Text(opt.1).tag(opt.0)
                        }
                    }
                    .pickerStyle(.segmented)
                    .frame(width: 180)
                    .onChange(of: strategy.direction) { _ in onSave() }
                }

                VStack(alignment: .leading, spacing: 6) {
                    Text("Position Sizing")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Picker("", selection: $strategy.positionSizing) {
                        ForEach(sizingOptions, id: \.0) { opt in
                            Text(opt.1).tag(opt.0)
                        }
                    }
                    .pickerStyle(.segmented)
                    .frame(width: 210)
                    .onChange(of: strategy.positionSizing) { _ in onSave() }
                }

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
                    .onChange(of: selectedCategory) {
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
    @State private var timeframe = "d1"
    @State private var startDate = Calendar.current.date(byAdding: .year, value: -1, to: Date()) ?? Date()
    @State private var endDate = Date()
    @State private var isRunning = false
    @State private var result: BacktestResult?
    @State private var errorMessage: String?
    @State private var jobStatus: String?
    @State private var currentJobId: String?

    let symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "SPY", "QQQ", "IWM"]
    let timeframes = [("d1", "1D"), ("4h", "4H"), ("1h", "1H"), ("30m", "30m"), ("15m", "15m")]

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
                    ForEach(timeframes, id: \.0) { tf in
                        Text(tf.1).tag(tf.0)
                    }
                }
                .frame(width: 120)

                DatePicker("From", selection: $startDate, displayedComponents: .date)
                    .labelsHidden()

                DatePicker("To", selection: $endDate, displayedComponents: .date)
                    .labelsHidden()

                Spacer()

                if let status = jobStatus, isRunning {
                    Text(status)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                if isRunning {
                    Button(action: {
                        Task {
                            if let jobId = currentJobId {
                                await APIClient.shared.cancelBacktestJob(jobId: jobId)
                            }
                            isRunning = false
                            jobStatus = nil
                            currentJobId = nil
                        }
                    }) {
                        Label("Cancel", systemImage: "xmark.circle")
                    }
                    .buttonStyle(.bordered)
                    .tint(.red)
                }

                Button(action: { Task { await runBacktest() } }) {
                    if isRunning {
                        ProgressView()
                            .scaleEffect(0.8)
                    } else {
                        Label("Run Backtest", systemImage: "play.fill")
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(isRunning || strategy.entryConditions.isEmpty)
            }
            .padding()

            Divider()

            if let error = errorMessage {
                VStack(spacing: 12) {
                    Spacer()
                    Image(systemName: "exclamationmark.triangle")
                        .font(.system(size: 40))
                        .foregroundStyle(.orange)
                    Text(error)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                    Button("Dismiss") { errorMessage = nil }
                        .buttonStyle(.bordered)
                    Spacer()
                }
            } else if let result = result {
                BacktestResultsWeb(result: result)
            } else {
                VStack(spacing: 16) {
                    Spacer()
                    Image(systemName: "chart.bar.xaxis")
                        .font(.system(size: 60))
                        .foregroundColor(.secondary)
                    if strategy.entryConditions.isEmpty {
                        Text("Add entry conditions to run a backtest")
                            .font(.headline)
                            .foregroundColor(.secondary)
                    } else {
                        Text("Run a backtest to see results")
                            .font(.headline)
                            .foregroundColor(.secondary)
                    }
                    Spacer()
                }
            }
        }
    }

    /// Convert Swift Strategy conditions to the worker's expected JSON format.
    private func buildStrategyConfig() -> [String: Any] {
        var config: [String: Any] = [:]

        // Serialize condition groups for OR logic support
        // Worker expects: entry_condition_groups: [{ conditions: [...] }, ...]
        config["entry_condition_groups"] = strategy.entryGroups.map { group in
            ["conditions": group.conditions.map { conditionToDict($0) }] as [String: Any]
        }
        config["exit_condition_groups"] = strategy.exitGroups.map { group in
            ["conditions": group.conditions.map { conditionToDict($0) }] as [String: Any]
        }

        // Also send flat arrays for backward compatibility
        config["entry_conditions"] = strategy.entryConditions.map { conditionToDict($0) }
        config["exit_conditions"] = strategy.exitConditions.map { conditionToDict($0) }

        // Direction and position sizing
        config["direction"] = strategy.direction
        config["position_sizing"] = [
            "type": strategy.positionSizing,
            "value": strategy.positionSize
        ]

        // Risk management
        config["riskManagement"] = [
            "stopLoss": ["type": "percent", "value": strategy.stopLoss],
            "takeProfit": ["type": "percent", "value": strategy.takeProfit],
        ]

        return config
    }

    private func conditionToDict(_ c: StrategyCondition) -> [String: Any] {
        var dict: [String: Any] = [
            "type": "indicator",
            "name": c.indicator.lowercased().replacingOccurrences(of: " ", with: "_"),
            "operator": mapOperator(c.operator),
            "value": c.value,
        ]
        if let params = c.parameters {
            dict["params"] = params
        }
        return dict
    }

    /// Map display operators to worker text operators.
    private func mapOperator(_ op: String) -> String {
        switch op.lowercased() {
        case ">", "above": return "above"
        case ">=", "above_equal": return "above_equal"
        case "<", "below": return "below"
        case "<=", "below_equal": return "below_equal"
        case "==", "equals": return "equals"
        case "crosses_above", "cross_up": return "cross_up"
        case "crosses_below", "cross_down": return "cross_down"
        default: return op.lowercased()
        }
    }

    private func runBacktest() async {
        isRunning = true
        errorMessage = nil
        result = nil
        jobStatus = "Queuing…"

        let df = DateFormatter()
        df.dateFormat = "yyyy-MM-dd"

        let request = BacktestRequest(
            symbol: symbol,
            strategy: "custom",
            startDate: df.string(from: startDate),
            endDate: df.string(from: endDate),
            timeframe: timeframe,
            initialCapital: 10000,
            strategyConfig: buildStrategyConfig()
        )

        do {
            let queued = try await APIClient.shared.queueBacktestJob(request: request)
            currentJobId = queued.jobId
            jobStatus = "Running…"

            // Poll for completion (max 120 × 1.5s = 180s)
            for i in 0..<120 {
                try await Task.sleep(nanoseconds: 1_500_000_000)
                // Check if cancelled by the user
                guard isRunning else { return }

                let status = try await APIClient.shared.getBacktestJobStatus(jobId: queued.jobId)

                if status.status == "failed" {
                    errorMessage = status.error ?? "Backtest failed"
                    isRunning = false
                    jobStatus = nil
                    currentJobId = nil
                    return
                }

                if status.status == "cancelled" {
                    isRunning = false
                    jobStatus = nil
                    currentJobId = nil
                    return
                }

                if status.status == "completed", let payload = status.result {
                    result = BacktestResult.from(
                        metrics: payload.metrics,
                        trades: payload.trades,
                        equityCurve: payload.equityCurve,
                        parseDate: parseDate,
                        validation: payload.validation,
                        monthlyReturns: payload.monthlyReturns,
                        rollingMetrics: payload.rollingMetrics,
                        drawdownSeries: payload.drawdownSeries
                    )
                    isRunning = false
                    jobStatus = nil
                    currentJobId = nil
                    return
                }

                jobStatus = "Running… (\(i + 1)s)"
            }

            errorMessage = "Backtest timed out — try again"
        } catch {
            errorMessage = "Error: \(error.localizedDescription)"
        }

        isRunning = false
        jobStatus = nil
        currentJobId = nil
    }

    private func parseDate(_ str: String) -> Date {
        let df = DateFormatter()
        df.locale = Locale(identifier: "en_US_POSIX")
        df.timeZone = TimeZone(secondsFromGMT: 0)
        for fmt in ["yyyy-MM-dd'T'HH:mm:ss.SSSZ", "yyyy-MM-dd'T'HH:mm:ssZ", "yyyy-MM-dd"] {
            df.dateFormat = fmt
            if let d = df.date(from: str) { return d }
        }
        return Date()
    }
}

struct BacktestResultsWeb: View {
    let result: BacktestResult

    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // 1. Metrics Grid
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

                // 2. Equity Curve Chart with Trade Markers
                if !result.equityCurve.isEmpty {
                    EquityCurveChartWeb(equityCurve: result.equityCurve, trades: result.trades)
                        .padding(.horizontal)
                }

                // 3. Statistical Validation Card
                ValidationCardWeb(validation: result.validation, totalTrades: result.totalTrades)
                    .padding(.horizontal)

                // 4. Monthly Returns Heatmap
                if let monthly = result.monthlyReturns, !monthly.isEmpty {
                    MonthlyHeatmapChart(monthlyReturns: monthly)
                        .padding(.horizontal)
                }

                // 5. Drawdown Chart
                if let drawdown = result.drawdownSeries, !drawdown.isEmpty {
                    DrawdownChart(drawdownSeries: drawdown)
                        .padding(.horizontal)
                }

                // 6. Rolling Sharpe
                if let rolling = result.rollingMetrics, !rolling.isEmpty {
                    RollingSharpeChart(rollingMetrics: rolling)
                        .padding(.horizontal)
                }

                // 7. P&L Distribution
                if !result.trades.isEmpty {
                    PnLHistogramChart(trades: result.trades)
                        .padding(.horizontal)
                }

                // 8. Trade History Table
                TradesTableWeb(trades: result.trades)
                    .padding(.horizontal)
            }
            .padding(.vertical)
        }
    }
}

// MARK: - Equity Curve Chart with Trade Markers

struct EquityCurveChartWeb: View {
    let equityCurve: [EquityPointLocal]
    let trades: [Trade]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "chart.line.uptrend.xyaxis")
                    .foregroundColor(.blue)
                Text("Equity Curve")
                    .font(.headline)
                Spacer()
                // Legend
                HStack(spacing: 12) {
                    HStack(spacing: 4) {
                        Circle().fill(.green).frame(width: 8, height: 8)
                        Text("Entry").font(.caption2).foregroundColor(.secondary)
                    }
                    HStack(spacing: 4) {
                        Circle().fill(.red).frame(width: 8, height: 8)
                        Text("Exit").font(.caption2).foregroundColor(.secondary)
                    }
                }
            }

            Chart {
                // Equity curve line
                ForEach(equityCurve) { point in
                    LineMark(
                        x: .value("Date", point.date),
                        y: .value("Value", point.value)
                    )
                    .foregroundStyle(.blue)
                    .interpolationMethod(.catmullRom)

                    AreaMark(
                        x: .value("Date", point.date),
                        y: .value("Value", point.value)
                    )
                    .foregroundStyle(
                        .linearGradient(
                            colors: [.blue.opacity(0.15), .blue.opacity(0.02)],
                            startPoint: .top,
                            endPoint: .bottom
                        )
                    )
                    .interpolationMethod(.catmullRom)
                }

                // Trade entry markers (green triangles)
                ForEach(trades) { trade in
                    if let eqValue = equityValueNear(date: trade.entryDate) {
                        PointMark(
                            x: .value("Date", trade.entryDate),
                            y: .value("Value", eqValue)
                        )
                        .foregroundStyle(.green)
                        .symbolSize(40)
                        .symbol(.triangle)
                    }
                }

                // Trade exit markers (red inverted triangles)
                ForEach(trades) { trade in
                    if let eqValue = equityValueNear(date: trade.exitDate) {
                        PointMark(
                            x: .value("Date", trade.exitDate),
                            y: .value("Value", eqValue)
                        )
                        .foregroundStyle(trade.pnl >= 0 ? .green : .red)
                        .symbolSize(40)
                        .symbol(.diamond)
                    }
                }
            }
            .chartXAxis {
                AxisMarks(values: .stride(by: .month, count: 3)) { _ in
                    AxisGridLine(stroke: StrokeStyle(lineWidth: 0.3))
                    AxisValueLabel(format: .dateTime.month(.abbreviated).year(.twoDigits))
                        .font(.caption2)
                }
            }
            .chartYAxis {
                AxisMarks { value in
                    AxisGridLine(stroke: StrokeStyle(lineWidth: 0.3))
                    AxisValueLabel {
                        if let v = value.as(Double.self) {
                            Text("$\(v, specifier: "%.0f")")
                                .font(.caption2)
                        }
                    }
                }
            }
            .frame(height: 280)
        }
        .padding()
        .background(Color(.controlBackgroundColor))
        .cornerRadius(12)
    }

    /// Find the closest equity curve value for a given trade date
    private func equityValueNear(date: Date) -> Double? {
        guard !equityCurve.isEmpty else { return nil }
        let sorted = equityCurve.sorted { $0.date < $1.date }
        // Find the closest point by date
        var best = sorted[0]
        var bestDiff = abs(date.timeIntervalSince(best.date))
        for pt in sorted {
            let diff = abs(date.timeIntervalSince(pt.date))
            if diff < bestDiff {
                bestDiff = diff
                best = pt
            }
        }
        return best.value
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
                HStack(spacing: 4) {
                    Text("Dir").font(.caption).bold().frame(width: 28, alignment: .center)
                    Text("Entry").font(.caption).bold()
                    Spacer()
                    Text("Exit").font(.caption).bold()
                    Spacer()
                    Text("Entry $").font(.caption).bold()
                    Spacer()
                    Text("Exit $").font(.caption).bold()
                    Spacer()
                    Text("Rtn%").font(.caption).bold()
                    Spacer()
                    Text("P&L").font(.caption).bold()
                    Spacer()
                    Text("Reason").font(.caption).bold()
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .background(Color.secondary.opacity(0.1))

                Divider()

                // Rows
                ForEach(trades) { trade in
                    HStack(spacing: 4) {
                        Image(systemName: trade.direction == "short"
                            ? "arrow.down.circle.fill"
                            : "arrow.up.circle.fill")
                            .font(.caption)
                            .foregroundColor(trade.direction == "short" ? .red : .green)
                            .frame(width: 28, alignment: .center)
                        Text(trade.entryDate, format: .dateTime.month(.abbreviated).day())
                            .font(.caption)
                        Spacer()
                        Text(trade.exitDate, format: .dateTime.month(.abbreviated).day())
                            .font(.caption)
                        Spacer()
                        Text(String(format: "%.2f", trade.entryPrice))
                            .font(.caption)
                        Spacer()
                        Text(String(format: "%.2f", trade.exitPrice))
                            .font(.caption)
                        Spacer()
                        Text(String(format: "%+.1f%%", trade.returnPct))
                            .font(.caption)
                            .foregroundColor(trade.returnPct >= 0 ? .green : .red)
                        Spacer()
                        Text(String(format: "%+.2f", trade.pnl))
                            .font(.caption)
                            .foregroundColor(trade.pnl >= 0 ? .green : .red)
                        Spacer()
                        Text(closeReasonLabel(trade.closeReason))
                            .font(.caption2)
                            .foregroundColor(.secondary)
                            .frame(minWidth: 30, alignment: .trailing)
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

    private func closeReasonLabel(_ reason: String?) -> String {
        switch reason {
        case "stop_loss": return "SL"
        case "take_profit": return "TP"
        case "exit_condition": return "Exit"
        case "manual": return "Manual"
        default: return "—"
        }
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
    var id: String = UUID().uuidString
    var userId: String? = nil
    var name: String
    var description: String?
    var entryGroups: [ConditionGroup] = []
    var exitGroups: [ConditionGroup] = []
    var positionSize: Double = 10.0
    var stopLoss: Double = 2.0
    var takeProfit: Double = 4.0
    var direction: String = "long_only"              // "long_only" | "short_only" | "long_short"
    var positionSizing: String = "percent_of_equity"  // "percent_of_equity" | "fixed_dollar" | "half_kelly"
    var isActive: Bool = true
    var createdAt: Date = Date()
    var updatedAt: Date = Date()

    /// All entry conditions flattened across groups (convenience for counts/checks).
    var entryConditions: [StrategyCondition] { ConditionGroup.flatten(entryGroups) }
    /// All exit conditions flattened across groups.
    var exitConditions: [StrategyCondition] { ConditionGroup.flatten(exitGroups) }
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

/// A group of conditions that are AND'd together.
/// Multiple groups are OR'd: if ANY group passes, the signal fires.
struct ConditionGroup: Identifiable, Hashable {
    let id: UUID
    var conditions: [StrategyCondition]

    init(id: UUID = UUID(), conditions: [StrategyCondition] = []) {
        self.id = id
        self.conditions = conditions
    }

    /// Convenience: wrap a flat array of conditions into a single AND group.
    static func single(_ conditions: [StrategyCondition]) -> [ConditionGroup] {
        conditions.isEmpty ? [] : [ConditionGroup(conditions: conditions)]
    }

    /// Flatten all conditions from all groups.
    static func flatten(_ groups: [ConditionGroup]) -> [StrategyCondition] {
        groups.flatMap(\.conditions)
    }
}

struct EquityPointLocal: Identifiable {
    let id = UUID()
    let date: Date
    let value: Double
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
    let equityCurve: [EquityPointLocal]
    // Statistical validation (optional — present when trade count >= 10)
    let validation: BacktestValidation?
    let monthlyReturns: [BacktestMonthlyReturn]?
    let rollingMetrics: [BacktestRollingMetric]?
    let drawdownSeries: [BacktestDrawdownPoint]?

    /// Build from worker payload, mapping all new fields (direction, closeReason, quantity, returnPct).
    static func from(
        metrics m: BacktestResultMetrics,
        trades rawTrades: [BacktestResultTrade],
        equityCurve rawCurve: [BacktestResultEquityPoint],
        parseDate: (String) -> Date,
        validation: BacktestValidation? = nil,
        monthlyReturns: [BacktestMonthlyReturn]? = nil,
        rollingMetrics: [BacktestRollingMetric]? = nil,
        drawdownSeries: [BacktestDrawdownPoint]? = nil
    ) -> BacktestResult {
        let trades = rawTrades.map { t -> Trade in
            let retPct = t.pnlPct ?? (t.entryPrice > 0 ? ((t.exitPrice - t.entryPrice) / t.entryPrice) * 100.0 : 0)
            return Trade(
                entryDate: parseDate(t.entryDate),
                exitDate: parseDate(t.exitDate),
                entryPrice: t.entryPrice,
                exitPrice: t.exitPrice,
                pnl: t.pnl ?? 0,
                direction: t.direction,
                closeReason: t.closeReason,
                quantity: t.quantity ?? 1,
                returnPct: retPct
            )
        }

        let wins = trades.filter { $0.pnl > 0 }
        let losses = trades.filter { $0.pnl < 0 }
        let avgWin = wins.isEmpty ? 0 : wins.map(\.pnl).reduce(0, +) / Double(wins.count)
        let avgLoss = losses.isEmpty ? 0 : losses.map(\.pnl).reduce(0, +) / Double(losses.count)

        let curve = rawCurve.map {
            EquityPointLocal(date: parseDate($0.date), value: $0.value)
        }

        return BacktestResult(
            totalTrades: m.totalTrades,
            winRate: (m.winRate ?? 0) / 100.0,
            totalReturn: (m.totalReturnPct ?? 0) / 100.0,
            maxDrawdown: (m.maxDrawdownPct ?? 0) / 100.0,
            profitFactor: m.profitFactor ?? 0,
            sharpeRatio: m.sharpeRatio ?? 0,
            avgWin: avgWin,
            avgLoss: avgLoss,
            trades: trades,
            equityCurve: curve,
            validation: validation,
            monthlyReturns: monthlyReturns,
            rollingMetrics: rollingMetrics,
            drawdownSeries: drawdownSeries
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
    let direction: String      // "long" or "short"
    let closeReason: String?   // "stop_loss" | "take_profit" | "exit_condition" | "manual"
    let quantity: Double
    let returnPct: Double      // percentage return on this trade
}

// Reuse existing StrategyBuilderViewModel but with enhanced features
@MainActor
class StrategyBuilderViewModel: ObservableObject {
    @Published var strategies: [Strategy] = []
    private var saveTask: Task<Void, Never>?

    init() {
        loadMockStrategies()
        Task { await fetchFromSupabase() }
    }

    private func loadMockStrategies() {
        strategies = [
            Strategy(
                name: "RSI Oversold",
                description: "Buy when RSI below 30",
                entryGroups: ConditionGroup.single([
                    StrategyCondition(indicator: "RSI", operator: "below", value: 30, parameters: ["period": "14"])
                ]),
                exitGroups: ConditionGroup.single([
                    StrategyCondition(indicator: "RSI", operator: "above", value: 70, parameters: ["period": "14"])
                ])
            ),
            Strategy(
                name: "MACD Crossover",
                description: "Trend following with MACD",
                entryGroups: ConditionGroup.single([
                    StrategyCondition(indicator: "MACD", operator: "crosses_above", value: 0, parameters: nil)
                ]),
                exitGroups: ConditionGroup.single([
                    StrategyCondition(indicator: "MACD", operator: "crosses_below", value: 0, parameters: nil)
                ]),
                isActive: false
            ),
            Strategy(
                name: "Supertrend",
                description: "Supertrend with MACD",
                entryGroups: ConditionGroup.single([
                    StrategyCondition(indicator: "SuperTrend AI", operator: "above", value: 1, parameters: ["atr_length": "10"])
                ]),
                exitGroups: [],
                isActive: true
            )
        ]
    }

    private func fetchFromSupabase() async {
        let fetched = await APIClient.shared.fetchStrategies()
        if !fetched.isEmpty {
            strategies = fetched
        }
    }

    func addStrategy(_ strategy: Strategy) {
        strategies.append(strategy)
        Task { await APIClient.shared.upsertStrategy(strategy) }
    }

    func deleteStrategy(_ strategy: Strategy) {
        strategies.removeAll { $0.id == strategy.id }
        Task { await APIClient.shared.deleteStrategy(id: strategy.id) }
    }

    func saveStrategy(_ strategy: Strategy) {
        if let index = strategies.firstIndex(where: { $0.id == strategy.id }) {
            var updated = strategy
            updated.updatedAt = Date()
            strategies[index] = updated
            scheduleSave(updated)
        }
    }

    private func scheduleSave(_ strategy: Strategy) {
        saveTask?.cancel()
        saveTask = Task {
            do {
                try await Task.sleep(nanoseconds: 2_000_000_000)
            } catch {
                return // cancelled
            }
            await APIClient.shared.upsertStrategy(strategy)
        }
    }
}

// MARK: - Monthly Returns Heatmap

struct MonthlyHeatmapChart: View {
    let monthlyReturns: [BacktestMonthlyReturn]

    private let monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    private var years: [Int] {
        Array(Set(monthlyReturns.map(\.year))).sorted()
    }

    private func returnFor(year: Int, month: Int) -> BacktestMonthlyReturn? {
        monthlyReturns.first { $0.year == year && $0.month == month }
    }

    private func cellColor(for returnPct: Double) -> Color {
        let intensity = min(abs(returnPct) / 10.0, 1.0)
        return returnPct >= 0
            ? Color.green.opacity(0.15 + intensity * 0.65)
            : Color.red.opacity(0.15 + intensity * 0.65)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "calendar.badge.clock")
                    .foregroundColor(.orange)
                Text("Monthly Returns")
                    .font(.headline)
                Spacer()
            }

            // Month column headers
            HStack(spacing: 4) {
                Text("").frame(width: 38)
                ForEach(monthNames, id: \.self) { m in
                    Text(m)
                        .font(.caption2)
                        .foregroundColor(.secondary)
                        .frame(maxWidth: .infinity, alignment: .center)
                }
            }

            // Year rows
            ForEach(years, id: \.self) { year in
                HStack(spacing: 4) {
                    Text(String(year))
                        .font(.caption2)
                        .foregroundColor(.secondary)
                        .frame(width: 38, alignment: .leading)

                    ForEach(1...12, id: \.self) { month in
                        if let r = returnFor(year: year, month: month) {
                            Text(String(format: "%.1f", r.returnPct))
                                .font(.system(size: 9, weight: .medium))
                                .foregroundColor(r.returnPct >= 0 ? .green : .red)
                                .frame(maxWidth: .infinity, minHeight: 22)
                                .background(cellColor(for: r.returnPct))
                                .cornerRadius(3)
                                .opacity(r.isPartial ? 0.55 : 1.0)
                        } else {
                            Color.secondary.opacity(0.08)
                                .frame(maxWidth: .infinity, minHeight: 22)
                                .cornerRadius(3)
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

// MARK: - Rolling Sharpe Chart

struct RollingSharpeChart: View {
    let rollingMetrics: [BacktestRollingMetric]

    private struct MetricPoint: Identifiable {
        let id = UUID()
        let date: Date
        let sharpe: Double
    }

    private var points: [MetricPoint] {
        let df = DateFormatter()
        df.locale = Locale(identifier: "en_US_POSIX")
        df.timeZone = TimeZone(secondsFromGMT: 0)
        df.dateFormat = "yyyy-MM-dd"
        return rollingMetrics.compactMap { m in
            guard let s = m.sharpe63, let date = df.date(from: m.date) else { return nil }
            return MetricPoint(date: date, sharpe: s)
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "waveform.path.ecg")
                    .foregroundColor(.purple)
                Text("Rolling Sharpe (63-bar)")
                    .font(.headline)
                Spacer()
            }

            if points.isEmpty {
                Text("Insufficient data for rolling metrics")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .frame(height: 160)
            } else {
                Chart {
                    RuleMark(y: .value("Target", 1.0))
                        .foregroundStyle(Color.green.opacity(0.5))
                        .lineStyle(StrokeStyle(lineWidth: 1, dash: [4]))
                        .annotation(position: .trailing, alignment: .leading) {
                            Text("1.0").font(.caption2).foregroundColor(.green)
                        }

                    RuleMark(y: .value("Zero", 0.0))
                        .foregroundStyle(Color.secondary.opacity(0.4))
                        .lineStyle(StrokeStyle(lineWidth: 1, dash: [2]))

                    ForEach(points) { pt in
                        LineMark(
                            x: .value("Date", pt.date),
                            y: .value("Sharpe", pt.sharpe)
                        )
                        .foregroundStyle(
                            pt.sharpe >= 1.0 ? Color.green
                            : pt.sharpe >= 0 ? Color.yellow
                            : Color.red
                        )
                        .interpolationMethod(.catmullRom)
                    }
                }
                .chartXAxis {
                    AxisMarks(values: .stride(by: .month, count: 3)) { _ in
                        AxisGridLine(stroke: StrokeStyle(lineWidth: 0.3))
                        AxisValueLabel(format: .dateTime.month(.abbreviated).year(.twoDigits))
                            .font(.caption2)
                    }
                }
                .chartYAxis {
                    AxisMarks { value in
                        AxisGridLine(stroke: StrokeStyle(lineWidth: 0.3))
                        AxisValueLabel {
                            if let v = value.as(Double.self) {
                                Text(String(format: "%.1f", v)).font(.caption2)
                            }
                        }
                    }
                }
                .frame(height: 160)
            }
        }
        .padding()
        .background(Color(.controlBackgroundColor))
        .cornerRadius(12)
    }
}

// MARK: - Drawdown Chart

struct DrawdownChart: View {
    let drawdownSeries: [BacktestDrawdownPoint]

    private struct DDPoint: Identifiable {
        let id = UUID()
        let date: Date
        let drawdown: Double
    }

    private var points: [DDPoint] {
        let df = DateFormatter()
        df.locale = Locale(identifier: "en_US_POSIX")
        df.timeZone = TimeZone(secondsFromGMT: 0)
        df.dateFormat = "yyyy-MM-dd"
        return drawdownSeries.compactMap { p in
            guard let date = df.date(from: p.date) else { return nil }
            return DDPoint(date: date, drawdown: p.drawdownPct)
        }
    }

    private var maxDrawdownPoint: DDPoint? {
        points.min(by: { $0.drawdown < $1.drawdown })
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "arrow.down.to.line")
                    .foregroundColor(.red)
                Text("Drawdown")
                    .font(.headline)
                Spacer()
                if let maxDD = maxDrawdownPoint {
                    Text(String(format: "Max: %.1f%%", maxDD.drawdown))
                        .font(.caption)
                        .foregroundColor(.red)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(Color.red.opacity(0.1))
                        .cornerRadius(6)
                }
            }

            if points.isEmpty {
                Text("No drawdown data")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .frame(height: 160)
            } else {
                Chart {
                    ForEach(points) { pt in
                        AreaMark(
                            x: .value("Date", pt.date),
                            yStart: .value("Zero", 0.0),
                            yEnd: .value("Drawdown", pt.drawdown)
                        )
                        .foregroundStyle(
                            .linearGradient(
                                colors: [Color.red.opacity(0.55), Color.red.opacity(0.1)],
                                startPoint: .top,
                                endPoint: .bottom
                            )
                        )
                        .interpolationMethod(.catmullRom)

                        LineMark(
                            x: .value("Date", pt.date),
                            y: .value("Drawdown", pt.drawdown)
                        )
                        .foregroundStyle(.red)
                        .interpolationMethod(.catmullRom)
                    }

                    if let maxDD = maxDrawdownPoint {
                        PointMark(
                            x: .value("Date", maxDD.date),
                            y: .value("Max DD", maxDD.drawdown)
                        )
                        .foregroundStyle(.red)
                        .symbolSize(60)
                        .annotation(position: .bottom) {
                            Text(String(format: "%.1f%%", maxDD.drawdown))
                                .font(.caption2)
                                .foregroundColor(.red)
                        }
                    }
                }
                .chartXAxis {
                    AxisMarks(values: .stride(by: .month, count: 3)) { _ in
                        AxisGridLine(stroke: StrokeStyle(lineWidth: 0.3))
                        AxisValueLabel(format: .dateTime.month(.abbreviated).year(.twoDigits))
                            .font(.caption2)
                    }
                }
                .chartYAxis {
                    AxisMarks { value in
                        AxisGridLine(stroke: StrokeStyle(lineWidth: 0.3))
                        AxisValueLabel {
                            if let v = value.as(Double.self) {
                                Text("\(String(format: "%.0f", v))%").font(.caption2)
                            }
                        }
                    }
                }
                .frame(height: 160)
            }
        }
        .padding()
        .background(Color(.controlBackgroundColor))
        .cornerRadius(12)
    }
}

// MARK: - P&L Distribution Histogram

struct PnLHistogramChart: View {
    let trades: [Trade]

    private struct HistoBin: Identifiable {
        let id = UUID()
        let midpoint: Double
        let count: Int
        let isPositive: Bool
    }

    private var bins: [HistoBin] {
        guard !trades.isEmpty else { return [] }
        let returns = trades.map(\.returnPct)
        guard let minR = returns.min(), let maxR = returns.max(), maxR > minR else { return [] }
        let binCount = 20
        let span = maxR - minR + 0.002
        let binWidth = span / Double(binCount)
        return (0..<binCount).compactMap { i in
            let lo = minR - 0.001 + Double(i) * binWidth
            let hi = lo + binWidth
            let mid = (lo + hi) / 2
            let count = returns.filter { $0 >= lo && $0 < hi }.count
            guard count > 0 else { return nil }
            return HistoBin(midpoint: mid, count: count, isPositive: mid >= 0)
        }
    }

    private var meanReturn: Double {
        guard !trades.isEmpty else { return 0 }
        return trades.map(\.returnPct).reduce(0, +) / Double(trades.count)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "chart.bar.fill")
                    .foregroundColor(.orange)
                Text("P&L Distribution")
                    .font(.headline)
                Spacer()
                Text(String(format: "Mean: %+.1f%%", meanReturn))
                    .font(.caption)
                    .foregroundColor(meanReturn >= 0 ? .green : .red)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background((meanReturn >= 0 ? Color.green : Color.red).opacity(0.1))
                    .cornerRadius(6)
            }

            if trades.isEmpty || bins.isEmpty {
                Text("No trades to display")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .frame(height: 160)
            } else {
                Chart {
                    ForEach(bins) { bin in
                        BarMark(
                            x: .value("Return %", bin.midpoint),
                            y: .value("Count", bin.count)
                        )
                        .foregroundStyle(bin.isPositive ? Color.green.opacity(0.7) : Color.red.opacity(0.7))
                    }

                    RuleMark(x: .value("Mean", meanReturn))
                        .foregroundStyle(.orange)
                        .lineStyle(StrokeStyle(lineWidth: 1.5, dash: [4]))
                        .annotation(position: .top) {
                            Text("μ").font(.caption2).foregroundColor(.orange)
                        }
                }
                .chartXAxis {
                    AxisMarks { value in
                        AxisGridLine(stroke: StrokeStyle(lineWidth: 0.3))
                        AxisValueLabel {
                            if let v = value.as(Double.self) {
                                Text("\(String(format: "%.0f", v))%").font(.caption2)
                            }
                        }
                    }
                }
                .chartYAxis {
                    AxisMarks { value in
                        AxisGridLine(stroke: StrokeStyle(lineWidth: 0.3))
                        AxisValueLabel {
                            if let v = value.as(Int.self) {
                                Text("\(v)").font(.caption2)
                            }
                        }
                    }
                }
                .frame(height: 160)
            }
        }
        .padding()
        .background(Color(.controlBackgroundColor))
        .cornerRadius(12)
    }
}

// MARK: - Statistical Validation Card

struct ValidationCardWeb: View {
    let validation: BacktestValidation?
    let totalTrades: Int

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Image(systemName: "checkmark.shield.fill")
                    .foregroundColor(.cyan)
                Text("Statistical Validation")
                    .font(.headline)
                Spacer()
                if let pVal = validation?.pValue {
                    Text(pVal < 0.05 ? "Significant ✓" : "Not Significant")
                        .font(.caption)
                        .foregroundColor(pVal < 0.05 ? .green : .orange)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background((pVal < 0.05 ? Color.green : Color.orange).opacity(0.15))
                        .cornerRadius(6)
                }
            }

            if totalTrades < 10 {
                HStack {
                    Image(systemName: "info.circle")
                        .foregroundColor(.secondary)
                    Text("Insufficient data — need at least 10 trades for statistical validation.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            } else if let v = validation {
                // Confidence Intervals
                if let ci = v.confidenceIntervals {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("95% Confidence Intervals (bootstrap, 1000 iterations)")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        HStack(spacing: 12) {
                            if let sCI = ci.sharpeRatio {
                                BacktestCIBadge(label: "Sharpe", lower: sCI.lower, upper: sCI.upper, format: "%.2f")
                            }
                            if let ddCI = ci.maxDrawdownPct {
                                BacktestCIBadge(label: "Max DD%", lower: ddCI.lower, upper: ddCI.upper, format: "%.1f")
                            }
                            if let wrCI = ci.winRate {
                                BacktestCIBadge(label: "Win Rate", lower: wrCI.lower, upper: wrCI.upper, format: "%.1f%%")
                            }
                            Spacer()
                        }
                    }
                }

                // P-value row
                if let pVal = v.pValue {
                    HStack(spacing: 8) {
                        Text("p-value:")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Text(String(format: "%.4f", pVal))
                            .font(.caption)
                            .fontWeight(.semibold)
                            .foregroundColor(pVal < 0.05 ? .green : .orange)
                        Text(pVal < 0.01 ? "(***)" : pVal < 0.05 ? "(**)" : pVal < 0.10 ? "(*)" : "(ns)")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                        Spacer()
                        if let n = v.sampleSize {
                            Text("n = \(n) trades")
                                .font(.caption2)
                                .foregroundColor(.secondary)
                        }
                        if let b = v.bootstrapIterations {
                            Text("· \(b) bootstrap iters")
                                .font(.caption2)
                                .foregroundColor(.secondary)
                        }
                    }
                }

                // IS vs OOS comparison
                if let inS = v.inSample, let outS = v.outOfSample {
                    Divider()
                    HStack(spacing: 0) {
                        BacktestSplitMetricsColumn(label: "In-Sample (70%)", metrics: inS, color: .blue)
                        Divider().frame(maxHeight: 80)
                        BacktestSplitMetricsColumn(label: "Out-of-Sample (30%)", metrics: outS, color: .cyan)
                    }
                    .background(Color(.windowBackgroundColor))
                    .cornerRadius(8)
                }
            } else {
                Text("Validation data not available.")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .padding()
        .background(Color(.controlBackgroundColor))
        .cornerRadius(12)
    }
}

private struct BacktestCIBadge: View {
    let label: String
    let lower: Double
    let upper: Double
    var format: String = "%.2f"

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(label)
                .font(.caption2)
                .foregroundColor(.secondary)
            Text("[\(String(format: format, lower)), \(String(format: format, upper))]")
                .font(.caption)
                .fontWeight(.medium)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 6)
        .background(Color.secondary.opacity(0.1))
        .cornerRadius(6)
    }
}

private struct BacktestSplitMetricsColumn: View {
    let label: String
    let metrics: BacktestSplitMetrics
    let color: Color

    var body: some View {
        VStack(alignment: .center, spacing: 6) {
            Text(label)
                .font(.caption2)
                .foregroundColor(color)
                .fontWeight(.semibold)
            HStack(spacing: 16) {
                if let sharpe = metrics.sharpeRatio {
                    VStack(spacing: 2) {
                        Text(String(format: "%.2f", sharpe)).font(.caption).fontWeight(.semibold)
                        Text("Sharpe").font(.caption2).foregroundColor(.secondary)
                    }
                }
                if let ret = metrics.totalReturnPct {
                    VStack(spacing: 2) {
                        Text(String(format: "%+.1f%%", ret))
                            .font(.caption).fontWeight(.semibold)
                            .foregroundColor(ret >= 0 ? .green : .red)
                        Text("Return").font(.caption2).foregroundColor(.secondary)
                    }
                }
                if let wr = metrics.winRate {
                    VStack(spacing: 2) {
                        Text(String(format: "%.0f%%", wr)).font(.caption).fontWeight(.semibold)
                        Text("Win Rate").font(.caption2).foregroundColor(.secondary)
                    }
                }
                if let dd = metrics.maxDrawdownPct {
                    VStack(spacing: 2) {
                        Text(String(format: "%.1f%%", dd))
                            .font(.caption).fontWeight(.semibold)
                            .foregroundColor(.orange)
                        Text("Max DD").font(.caption2).foregroundColor(.secondary)
                    }
                }
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 10)
    }
}
