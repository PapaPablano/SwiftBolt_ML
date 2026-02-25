import SwiftUI

// MARK: - Integrated Strategy Builder
/// Combines Technical Indicators display with Strategy Builder functionality
struct IntegratedStrategyBuilder: View {
    @StateObject private var indicatorsService = UnifiedIndicatorsService.shared
    @StateObject private var strategyViewModel = StrategyBuilderViewModel()
    
    @State private var selectedStrategy: Strategy?
    @State private var selectedTab = 0 // 0 = Editor, 1 = Live Indicators, 2 = Backtest
    @State private var showingNewStrategy = false
    
    var body: some View {
        VStack(spacing: 0) {
            // Header
            headerBar
            
            Divider()
            
            // Tab Bar
            HStack(spacing: 0) {
                TabButton(title: "Strategy Editor", icon: "slider.horizontal.3", isSelected: selectedTab == 0) {
                    selectedTab = 0
                }
                TabButton(title: "Live Indicators", icon: "waveform.path.ecg", isSelected: selectedTab == 1) {
                    selectedTab = 1
                }
                TabButton(title: "Backtest", icon: "chart.line.uptrend.xyaxis", isSelected: selectedTab == 2) {
                    selectedTab = 2
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(Color(.controlBackgroundColor))
            
            // Content
            switch selectedTab {
            case 0:
                StrategyEditorIntegrated(
                    strategy: $selectedStrategy,
                    viewModel: strategyViewModel,
                    indicatorsService: indicatorsService
                )
            case 1:
                LiveIndicatorsPanel(service: indicatorsService) { condition in
                    // Add condition to current strategy
                    if var strategy = selectedStrategy {
                        strategy.entryConditions.append(condition)
                        strategyViewModel.saveStrategy(strategy)
                        selectedStrategy = strategy
                        selectedTab = 0 // Switch to editor
                    }
                }
            case 2:
                if let strategy = selectedStrategy {
                    BacktestWebStyle(strategy: strategy, viewModel: strategyViewModel)
                } else {
                    SBEmptyStateView(message: "Select or create a strategy to backtest")
                }
            default:
                EmptyView()
            }
        }
        .task {
            // Load initial indicators
            try? await indicatorsService.fetchIndicators(
                symbol: indicatorsService.selectedSymbol,
                timeframe: indicatorsService.selectedTimeframe
            )
        }
        .sheet(isPresented: $showingNewStrategy) {
            NewStrategyDialog { name, description in
                let strategy = Strategy(name: name, description: description)
                strategyViewModel.addStrategy(strategy)
                selectedStrategy = strategy
                showingNewStrategy = false
            }
            .frame(minWidth: 400, minHeight: 300)
        }
    }
    
    private var headerBar: some View {
        HStack(spacing: 16) {
            // Strategy Selector
            Menu {
                ForEach(strategyViewModel.strategies) { strategy in
                    Button(strategy.name) {
                        selectedStrategy = strategy
                    }
                }
                Divider()
                Button("+ New Strategy") {
                    showingNewStrategy = true
                }
            } label: {
                HStack {
                    Text(selectedStrategy?.name ?? "Select Strategy")
                        .font(.headline)
                    Image(systemName: "chevron.down")
                        .font(.caption)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(Color(.controlBackgroundColor))
                .cornerRadius(8)
            }
            
            Spacer()
            
            // Symbol/Timeframe for Indicators
            HStack(spacing: 8) {
                TextField("Symbol", text: $indicatorsService.selectedSymbol)
                    .textFieldStyle(.roundedBorder)
                    .frame(width: 80)
                    .onSubmit {
                        Task {
                            try? await indicatorsService.fetchIndicators(
                                symbol: indicatorsService.selectedSymbol,
                                timeframe: indicatorsService.selectedTimeframe
                            )
                        }
                    }
                
                Picker("", selection: $indicatorsService.selectedTimeframe) {
                    ForEach(["1D", "4H", "1H", "30m", "15m", "5m"], id: \.self) { tf in
                        Text(tf).tag(tf)
                    }
                }
                .frame(width: 80)
                .onChange(of: indicatorsService.selectedTimeframe) { _ in
                    Task {
                        try? await indicatorsService.fetchIndicators(
                            symbol: indicatorsService.selectedSymbol,
                            timeframe: indicatorsService.selectedTimeframe
                        )
                    }
                }
            }
            
            // Refresh Button
            Button {
                Task {
                    try? await indicatorsService.fetchIndicators(
                        symbol: indicatorsService.selectedSymbol,
                        timeframe: indicatorsService.selectedTimeframe
                    )
                }
            } label: {
                Image(systemName: "arrow.clockwise")
            }
            .buttonStyle(.bordered)
            
            // Active Toggle
            if let strategy = selectedStrategy {
                Toggle("Active", isOn: Binding(
                    get: { strategy.isActive },
                    set: { newValue in
                        var updated = strategy
                        updated.isActive = newValue
                        selectedStrategy = updated
                        strategyViewModel.saveStrategy(updated)
                    }
                ))
                .toggleStyle(.switch)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(Color(.windowBackgroundColor))
    }
}

// MARK: - Live Indicators Panel

struct LiveIndicatorsPanel: View {
    @ObservedObject var service: UnifiedIndicatorsService
    let onAddCondition: (StrategyCondition) -> Void
    @State private var selectedCategory: StrategyIndicatorCategory = .momentum
    @State private var showingConditionPicker = false
    @State private var selectedRegistryItem: IndicatorRegistryItem?
    
    var body: some View {
        VStack(spacing: 0) {
            // Category Selector
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 12) {
                    ForEach(StrategyIndicatorCategory.allCases) { category in
                        CategoryButton(
                            title: category.rawValue,
                            icon: category.icon,
                            isSelected: selectedCategory == category
                        ) {
                            selectedCategory = category
                        }
                    }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
            }
            
            Divider()
            
            // Indicators Grid
            ScrollView {
                if let indicators = service.currentIndicators?.indicatorsByCategory[IndicatorCategory.from(strategyCategory: selectedCategory)] {
                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 200))], spacing: 12) {
                        ForEach(indicators) { indicator in
                            LiveIndicatorCard(
                                indicator: indicator,
                                registryItem: service.indicatorRegistry.first { $0.technicalKey == indicator.name }
                            ) { registryItem in
                                selectedRegistryItem = registryItem
                                showingConditionPicker = true
                            }
                        }
                    }
                    .padding(16)
                } else {
                    VStack(spacing: 16) {
                        ProgressView()
                        Text("Loading indicators...")
                            .foregroundColor(.secondary)
                    }
                    .padding(40)
                }
            }
        }
        .sheet(isPresented: $showingConditionPicker) {
            if let registryItem = selectedRegistryItem {
                ConditionFromIndicatorSheet(
                    registryItem: registryItem,
                    currentValue: service.currentIndicators?.indicators[registryItem.technicalKey] ?? 0
                ) { condition in
                    onAddCondition(condition)
                    showingConditionPicker = false
                }
                .frame(minWidth: 450, minHeight: 400)
            }
        }
    }
}

// MARK: - Live Indicator Card

struct LiveIndicatorCard: View {
    let indicator: IndicatorItem
    let registryItem: IndicatorRegistryItem?
    let onTap: (IndicatorRegistryItem) -> Void
    
    var body: some View {
        Button {
            if let registryItem = registryItem {
                onTap(registryItem)
            }
        } label: {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text(indicator.formattedName)
                        .font(.system(size: 13, weight: .medium))
                        .lineLimit(1)
                    Spacer()
                    
                    // Signal badge
                    SBSignalBadge(interpretation: indicator.interpretation)
                }
                
                HStack(alignment: .lastTextBaseline) {
                    Text(indicator.displayValue)
                        .font(.system(size: 24, weight: .bold, design: .rounded))
                        .foregroundColor(indicator.interpretation.swiftUIColor)
                    
                    Spacer()
                    
                    if registryItem != nil {
                        Image(systemName: "plus.circle.fill")
                            .foregroundColor(.accentColor)
                            .font(.title3)
                    }
                }
                
                // Interpretation text
                Text(indicator.interpretation.displayName)
                    .font(.caption)
                    .foregroundColor(indicator.interpretation.swiftUIColor)
            }
            .padding()
            .background(Color(.controlBackgroundColor))
            .cornerRadius(12)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(indicator.interpretation.swiftUIColor.opacity(0.3), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .disabled(registryItem == nil)
    }
}

struct SBSignalBadge: View {
    let interpretation: IndicatorInterpretation
    
    var body: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(interpretation.swiftUIColor)
                .frame(width: 6, height: 6)
        }
        .padding(.horizontal, 6)
        .padding(.vertical, 2)
        .background(interpretation.swiftUIColor.opacity(0.15))
        .cornerRadius(4)
    }
}

// MARK: - Condition From Indicator Sheet

struct ConditionFromIndicatorSheet: View {
    let registryItem: IndicatorRegistryItem
    let currentValue: Double?
    let onSave: (StrategyCondition) -> Void
    @Environment(\.dismiss) private var dismiss
    
    @State private var selectedConditionIndex = 0
    @State private var customValue: Double
    @State private var useCustomValue = false
    
    init(registryItem: IndicatorRegistryItem, currentValue: Double?, onSave: @escaping (StrategyCondition) -> Void) {
        self.registryItem = registryItem
        self.currentValue = currentValue
        self.onSave = onSave
        _customValue = State(initialValue: currentValue ?? registryItem.defaultCondition.value)
    }
    
    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text("Add Condition from \(registryItem.name)")
                    .font(.headline)
                Spacer()
                Button("Cancel") { dismiss() }
                    .buttonStyle(.bordered)
            }
            .padding()
            .background(Color(.controlBackgroundColor))
            
            Divider()
            
            ScrollView {
                VStack(spacing: 20) {
                    // Current Value Display
                    if let currentValue = currentValue {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Current Value")
                                .font(.caption)
                                .foregroundColor(.secondary)
                            
                            HStack {
                                Text(String(format: "%.4f", currentValue))
                                    .font(.system(size: 32, weight: .bold, design: .rounded))
                                    .foregroundColor(.accentColor)
                                
                                Spacer()
                                
                                Toggle("Use Custom", isOn: $useCustomValue)
                            }
                        }
                        .padding()
                        .background(Color(.windowBackgroundColor))
                        .cornerRadius(8)
                    }
                    
                    // Preset Conditions
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Select Condition")
                            .font(.headline)
                        
                        ForEach(Array(registryItem.allConditions.enumerated()), id: \.offset) { index, condition in
                            ConditionPresetButton(
                                condition: condition,
                                isSelected: selectedConditionIndex == index
                            ) {
                                selectedConditionIndex = index
                                if !useCustomValue {
                                    customValue = condition.value
                                }
                            }
                        }
                    }
                    
                    // Custom Value (if enabled)
                    if useCustomValue {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Custom Value")
                                .font(.caption)
                                .foregroundColor(.secondary)
                            
                            HStack {
                                TextField("Value", value: $customValue, format: .number)
                                    .textFieldStyle(.roundedBorder)
                                
                                Slider(value: $customValue, in: (customValue * 0.5)...(customValue * 1.5))
                                    .frame(width: 150)
                            }
                        }
                        .padding()
                        .background(Color(.windowBackgroundColor))
                        .cornerRadius(8)
                    }
                    
                    // Preview
                    let selectedCondition = registryItem.allConditions[selectedConditionIndex]
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Condition Preview")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        
                        HStack(spacing: 8) {
                            Text(registryItem.name)
                                .font(.system(size: 16, weight: .medium))
                            
                            Text(selectedCondition.op)
                                .font(.system(size: 16, weight: .bold))
                                .foregroundColor(.accentColor)
                            
                            Text(String(format: "%.2f", customValue))
                                .font(.system(size: 16, weight: .bold))
                        }
                        .padding()
                        .frame(maxWidth: .infinity, alignment: .center)
                        .background(Color.accentColor.opacity(0.1))
                        .cornerRadius(8)
                    }
                }
                .padding()
            }
            
            Divider()
            
            // Footer
            HStack {
                Spacer()
                Button("Cancel") { dismiss() }
                    .buttonStyle(.bordered)
                Button("Add Condition") {
                    let selectedCondition = registryItem.allConditions[selectedConditionIndex]
                    let condition = StrategyCondition(
                        id: UUID(),
                        indicator: registryItem.name,
                        operator: selectedCondition.op,
                        value: customValue,
                        parameters: ["source_key": registryItem.technicalKey, "preset": selectedCondition.label]
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

struct ConditionPresetButton: View {
    let condition: ConditionPreset
    let isSelected: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(condition.label)
                        .font(.system(size: 14, weight: .medium))
                    
                    HStack(spacing: 4) {
                        Text(condition.op)
                            .foregroundColor(.accentColor)
                        Text(String(format: "%.2f", condition.value))
                            .foregroundColor(.secondary)
                    }
                    .font(.caption)
                }
                
                Spacer()
                
                if isSelected {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.accentColor)
                }
            }
            .padding()
            .background(isSelected ? Color.accentColor.opacity(0.1) : Color(.windowBackgroundColor))
            .cornerRadius(8)
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(isSelected ? Color.accentColor : Color.clear, lineWidth: 2)
            )
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Supporting Views

struct TabButton: View {
    let title: String
    let icon: String
    let isSelected: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            VStack(spacing: 4) {
                Image(systemName: icon)
                    .font(.system(size: 16))
                Text(title)
                    .font(.caption)
            }
            .foregroundColor(isSelected ? .accentColor : .secondary)
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .background(isSelected ? Color.accentColor.opacity(0.1) : Color.clear)
            .cornerRadius(8)
        }
        .buttonStyle(.plain)
    }
}

struct CategoryButton: View {
    let title: String
    let icon: String
    let isSelected: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            HStack(spacing: 6) {
                Image(systemName: icon)
                    .font(.caption)
                Text(title)
                    .font(.system(size: 13, weight: .medium))
            }
            .foregroundColor(isSelected ? .white : .primary)
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(isSelected ? Color.accentColor : Color(.controlBackgroundColor))
            .cornerRadius(6)
        }
        .buttonStyle(.plain)
    }
}

struct SBEmptyStateView: View {
    let message: String
    
    var body: some View {
        VStack(spacing: 16) {
            Spacer()
            Image(systemName: "chart.line.uptrend.xyaxis")
                .font(.system(size: 48))
                .foregroundColor(.secondary)
            Text(message)
                .font(.headline)
                .foregroundColor(.secondary)
            Spacer()
        }
    }
}

// MARK: - Extensions

extension StrategyIndicatorCategory {
    var icon: String {
        switch self {
        case .supertrend: return "brain.head.profile"
        case .momentum: return "arrow.up.arrow.down"
        case .trend: return "chart.line.uptrend.xyaxis"
        case .volatility: return "waveform.path"
        case .volume: return "chart.bar"
        case .price: return "dollarsign.circle"
        case .divergence: return "arrow.left.arrow.right"
        }
    }
}

extension IndicatorCategory {
    static func from(strategyCategory: StrategyIndicatorCategory) -> IndicatorCategory {
        switch strategyCategory {
        case .supertrend: return .volatility
        case .momentum: return .momentum
        case .trend: return .trend
        case .volatility: return .volatility
        case .volume: return .volume
        case .price: return .price
        case .divergence: return .momentum
        }
    }
}
