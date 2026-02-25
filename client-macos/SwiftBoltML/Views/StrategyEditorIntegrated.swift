import SwiftUI

// MARK: - Strategy Editor (Integrated with Indicators)
struct StrategyEditorIntegrated: View {
    @Binding var strategy: Strategy?
    @ObservedObject var viewModel: StrategyBuilderViewModel
    @ObservedObject var indicatorsService: UnifiedIndicatorsService
    
    @State private var showingAddEntry = false
    @State private var showingAddExit = false
    @State private var editingCondition: StrategyCondition?
    @State private var conditionEditType: ConditionType?
    @State private var showingSuggestions = false
    
    enum ConditionType { case entry, exit }
    
    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                if let strategy = strategy {
                    // Strategy Info
                    StrategyInfoCard(
                        strategy: Binding(
                            get: { strategy },
                            set: { 
                                self.strategy = $0
                                viewModel.saveStrategy($0)
                            }
                        ),
                        onSave: {}
                    )
                    
                    // Quick Add from Live Indicators
                    if let indicators = indicatorsService.currentIndicators {
                        QuickAddSection(
                            indicators: indicators,
                            registry: indicatorsService.indicatorRegistry,
                            onAddEntry: { condition in
                                var updated = strategy
                                updated.entryConditions.append(condition)
                                viewModel.saveStrategy(updated)
                                self.strategy = updated
                            },
                            onAddExit: { condition in
                                var updated = strategy
                                updated.exitConditions.append(condition)
                                viewModel.saveStrategy(updated)
                                self.strategy = updated
                            }
                        )
                    }
                    
                    // Entry Conditions
                    ConditionsSectionIntegrated(
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
                            var updated = strategy
                            updated.entryConditions.remove(at: index)
                            viewModel.saveStrategy(updated)
                            self.strategy = updated
                        }
                    )
                    
                    // Exit Conditions
                    ConditionsSectionIntegrated(
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
                            var updated = strategy
                            updated.exitConditions.remove(at: index)
                            viewModel.saveStrategy(updated)
                            self.strategy = updated
                        }
                    )
                    
                    // Parameters
                    ParametersSectionIntegrated(strategy: Binding(
                        get: { strategy },
                        set: {
                            self.strategy = $0
                            viewModel.saveStrategy($0)
                        }
                    ))
                    
                    // Visual Map
                    StrategyMapIntegrated(
                        entryCount: strategy.entryConditions.count,
                        exitCount: strategy.exitConditions.count
                    )
                } else {
                    SBEmptyStateView(message: "Select or create a strategy to edit")
                }
            }
            .padding(16)
        }
        .sheet(isPresented: $showingAddEntry) {
            ConditionPickerIntegrated(
                service: indicatorsService,
                title: "Add Entry Condition"
            ) { condition in
                if var strategy = strategy {
                    strategy.entryConditions.append(condition)
                    viewModel.saveStrategy(strategy)
                    self.strategy = strategy
                }
                showingAddEntry = false
            }
            .frame(minWidth: 550, minHeight: 500)
        }
        .sheet(isPresented: $showingAddExit) {
            ConditionPickerIntegrated(
                service: indicatorsService,
                title: "Add Exit Condition"
            ) { condition in
                if var strategy = strategy {
                    strategy.exitConditions.append(condition)
                    viewModel.saveStrategy(strategy)
                    self.strategy = strategy
                }
                showingAddExit = false
            }
            .frame(minWidth: 550, minHeight: 500)
        }
    }
}

// MARK: - Quick Add Section
struct QuickAddSection: View {
    let indicators: TechnicalIndicatorsResponse
    let registry: [IndicatorRegistryItem]
    let onAddEntry: (StrategyCondition) -> Void
    let onAddExit: (StrategyCondition) -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "bolt.fill")
                    .foregroundColor(.yellow)
                Text("Quick Add from Live Indicators")
                    .font(.headline)
                Spacer()
            }
            
            // Show top 3 bullish and bearish signals
            let bullishSignals = getSignals(of: .bullish, .strongBullish)
            let bearishSignals = getSignals(of: .bearish, .strongBearish)
            
            HStack(spacing: 16) {
                // Bullish Signals
                VStack(alignment: .leading, spacing: 8) {
                    Label("Bullish Signals", systemImage: "arrow.up")
                        .font(.caption)
                        .foregroundColor(.green)
                    
                    ForEach(bullishSignals.prefix(3)) { signal in
                        QuickAddButton(
                            signal: signal,
                            color: .green
                        ) {
                            onAddEntry(signal.suggestedCondition)
                        }
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                
                Divider()
                    .frame(height: 100)
                
                // Bearish Signals
                VStack(alignment: .leading, spacing: 8) {
                    Label("Bearish Signals", systemImage: "arrow.down")
                        .font(.caption)
                        .foregroundColor(.red)
                    
                    ForEach(bearishSignals.prefix(3)) { signal in
                        QuickAddButton(
                            signal: signal,
                            color: .red
                        ) {
                            onAddExit(signal.suggestedCondition)
                        }
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding()
        .background(Color(.controlBackgroundColor))
        .cornerRadius(12)
    }
    
    private func getSignals(of interpretations: IndicatorInterpretation...) -> [IndicatorSignal] {
        var signals: [IndicatorSignal] = []
        
        for indicator in indicators.allIndicators {
            if let registryItem = registry.first(where: { $0.technicalKey == indicator.name }),
               interpretations.contains(indicator.interpretation) {
                
                let condition = StrategyCondition(
                    id: UUID(),
                    indicator: registryItem.name,
                    operator: indicator.interpretation == .bullish || indicator.interpretation == .strongBullish ? ">" : "<",
                    value: indicator.value,
                    parameters: ["source_key": registryItem.technicalKey]
                )
                
                signals.append(IndicatorSignal(
                    indicator: indicator,
                    registryItem: registryItem,
                    interpretation: indicator.interpretation,
                    suggestedCondition: condition
                ))
            }
        }
        
        return signals.sorted { $0.interpretation.priority > $1.interpretation.priority }
    }
}

struct IndicatorSignal: Identifiable {
    let id = UUID()
    let indicator: IndicatorItem
    let registryItem: IndicatorRegistryItem
    let interpretation: IndicatorInterpretation
    let suggestedCondition: StrategyCondition
}

struct QuickAddButton: View {
    let signal: IndicatorSignal
    let color: Color
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(signal.registryItem.name)
                        .font(.system(size: 13, weight: .medium))
                    Text(signal.indicator.displayValue)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                Image(systemName: "plus.circle")
                    .foregroundColor(color)
            }
            .padding(8)
            .background(color.opacity(0.1))
            .cornerRadius(6)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Condition Picker (Integrated)
struct ConditionPickerIntegrated: View {
    @ObservedObject var service: UnifiedIndicatorsService
    let title: String
    let onSelect: (StrategyCondition) -> Void
    @Environment(\.dismiss) private var dismiss
    
    @State private var selectedCategory: StrategyIndicatorCategory = .momentum
    @State private var selectedIndicator: IndicatorRegistryItem?
    @State private var selectedPreset: ConditionPreset?
    @State private var customValue: Double = 0
    @State private var useCustomValue = false
    
    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text(title)
                    .font(.system(size: 17, weight: .semibold))
                Spacer()
                Button("Cancel") { dismiss() }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 16)
            .background(Color(.controlBackgroundColor))
            
            Divider()
            
            HStack(spacing: 0) {
                // Left sidebar - Categories
                VStack(alignment: .leading, spacing: 0) {
                    Text("Category")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 12)
                    
                    ScrollView {
                        LazyVStack(spacing: 4) {
                            ForEach(StrategyIndicatorCategory.allCases) { category in
                                CategoryRow(
                                    category: category,
                                    isSelected: selectedCategory == category
                                ) {
                                    selectedCategory = category
                                    selectedIndicator = nil
                                    selectedPreset = nil
                                }
                            }
                        }
                        .padding(.horizontal, 12)
                    }
                }
                .frame(width: 160)
                .background(Color(.controlBackgroundColor).opacity(0.5))
                
                Divider()
                
                // Middle - Indicators
                VStack(alignment: .leading, spacing: 0) {
                    Text("Indicator")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 12)
                    
                        let filteredIndicators = service.indicatorRegistry.filter { $0.category == selectedCategory }
                    
                    ScrollView {
                        LazyVStack(spacing: 6) {
                            ForEach(filteredIndicators) { item in
                                let rawValue = service.currentIndicators?.indicators[item.technicalKey]
                                let currentValue: Double? = rawValue?.flatMap { $0 }
                                EnhancedIndicatorRow(
                                    item: item,
                                    currentValue: currentValue,
                                    isSelected: selectedIndicator?.id == item.id
                                ) {
                                    selectedIndicator = item
                                    selectedPreset = nil
                                    if let val = currentValue {
                                        customValue = val
                                    } else {
                                        customValue = item.defaultCondition.value
                                    }
                                }
                            }
                        }
                        .padding(.horizontal, 12)
                        .padding(.bottom, 12)
                    }
                }
                .frame(width: 240)
                
                Divider()
                
                // Right - Condition presets
                VStack(alignment: .leading, spacing: 0) {
                    if let selectedIndicator = selectedIndicator {
                        Text("Select Condition")
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .padding(.horizontal, 20)
                            .padding(.vertical, 12)
                        
                        ScrollView {
                            VStack(spacing: 10) {
                                // Current value card
                                if let currentValue = service.currentIndicators?.indicators[selectedIndicator.technicalKey],
                                   let value = currentValue {
                                    CurrentValueCard(value: value, indicatorName: selectedIndicator.name)
                                }
                                
                                // Condition presets
                                LazyVStack(spacing: 8) {
                                    ForEach(selectedIndicator.allConditions) { preset in
                                        EnhancedConditionPresetCard(
                                            preset: preset,
                                            isSelected: selectedPreset?.label == preset.label
                                        ) {
                                            selectedPreset = preset
                                            if !useCustomValue {
                                                customValue = preset.value
                                            }
                                        }
                                    }
                                }
                                
                                // Custom value section
                                VStack(alignment: .leading, spacing: 12) {
                                    Toggle("Use Custom Value", isOn: $useCustomValue)
                                        .font(.system(size: 13))
                                    
                                    if useCustomValue {
                                        VStack(spacing: 8) {
                                            HStack {
                                                Text("Value")
                                                    .font(.caption)
                                                    .foregroundColor(.secondary)
                                                Spacer()
                                                TextField("", value: $customValue, format: .number)
                                                    .textFieldStyle(.roundedBorder)
                                                    .frame(width: 80)
                                                    .multilineTextAlignment(.trailing)
                                            }
                                            
                                            Slider(value: $customValue, in: (customValue * 0.5)...(customValue * 1.5))
                                                .controlSize(.small)
                                        }
                                        .padding()
                                        .background(Color(.windowBackgroundColor))
                                        .cornerRadius(8)
                                    }
                                }
                                .padding(.top, 8)
                            }
                            .padding(.horizontal, 16)
                            .padding(.bottom, 16)
                        }
                        
                        Spacer()
                        
                        // Add button
                        VStack(spacing: 0) {
                            Divider()
                            Button {
                                if let preset = selectedPreset {
                                    let condition = StrategyCondition(
                                        id: UUID(),
                                        indicator: selectedIndicator.name,
                                        operator: preset.op,
                                        value: customValue,
                                        parameters: [
                                            "source_key": selectedIndicator.technicalKey,
                                            "preset": preset.label
                                        ]
                                    )
                                    onSelect(condition)
                                }
                            } label: {
                                HStack {
                                    Image(systemName: "plus.circle.fill")
                                    Text("Add Condition")
                                }
                                .font(.system(size: 15, weight: .medium))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 12)
                            }
                            .buttonStyle(.borderedProminent)
                            .disabled(selectedPreset == nil)
                            .padding(20)
                        }
                    } else {
                        VStack(spacing: 16) {
                            Spacer()
                            Image(systemName: "arrow.left")
                                .font(.system(size: 32))
                                .foregroundColor(.secondary.opacity(0.5))
                            Text("Select an indicator")
                                .font(.system(size: 15))
                                .foregroundColor(.secondary)
                            Spacer()
                        }
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .frame(width: 750, height: 520)
    }
}

struct CategoryRow: View {
    let category: StrategyIndicatorCategory
    let isSelected: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            HStack(spacing: 10) {
                Image(systemName: category.icon)
                    .font(.system(size: 14))
                    .frame(width: 20)
                Text(category.rawValue)
                    .font(.system(size: 13, weight: isSelected ? .semibold : .regular))
                Spacer()
            }
            .foregroundColor(isSelected ? .accentColor : .primary)
            .padding(.horizontal, 10)
            .padding(.vertical, 8)
            .background(isSelected ? Color.accentColor.opacity(0.12) : Color.clear)
            .cornerRadius(6)
        }
        .buttonStyle(.plain)
    }
}

struct EnhancedIndicatorRow: View {
    let item: IndicatorRegistryItem
    let currentValue: Double?
    let isSelected: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(item.name)
                        .font(.system(size: 14, weight: isSelected ? .semibold : .medium))
                        .foregroundColor(isSelected ? .accentColor : .primary)
                    
                    if let value = currentValue {
                        Text(String(format: "%.4f", value))
                            .font(.system(size: 12, design: .rounded))
                            .foregroundColor(.secondary)
                    } else {
                        Text("—")
                            .font(.system(size: 12))
                            .foregroundColor(.secondary.opacity(0.5))
                    }
                }
                
                Spacer()
                
                if isSelected {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 18))
                        .foregroundColor(.accentColor)
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(
                RoundedRectangle(cornerRadius: 8)
                    .fill(isSelected ? Color.accentColor.opacity(0.1) : Color(.windowBackgroundColor))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(isSelected ? Color.accentColor.opacity(0.3) : Color.clear, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }
}

struct CurrentValueCard: View {
    let value: Double
    let indicatorName: String
    
    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Current Value")
                    .font(.caption)
                    .foregroundColor(.secondary)
                Text(String(format: "%.4f", value))
                    .font(.system(size: 24, weight: .bold, design: .rounded))
                    .foregroundColor(.accentColor)
            }
            
            Spacer()
            
            VStack(alignment: .trailing, spacing: 4) {
                Text(indicatorName)
                    .font(.caption2)
                    .foregroundColor(.secondary)
                    .textCase(.uppercase)
                Image(systemName: "waveform.path.ecg")
                    .font(.system(size: 20))
                    .foregroundColor(.accentColor.opacity(0.3))
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color.accentColor.opacity(0.08))
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(Color.accentColor.opacity(0.15), lineWidth: 1)
                )
        )
    }
}

struct EnhancedConditionPresetCard: View {
    let preset: ConditionPreset
    let isSelected: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            HStack(spacing: 12) {
                // Selection indicator
                ZStack {
                    Circle()
                        .stroke(isSelected ? Color.accentColor : Color.secondary.opacity(0.3), lineWidth: 2)
                        .frame(width: 20, height: 20)
                    
                    if isSelected {
                        Circle()
                            .fill(Color.accentColor)
                            .frame(width: 12, height: 12)
                    }
                }
                
                VStack(alignment: .leading, spacing: 4) {
                    Text(preset.label)
                        .font(.system(size: 14, weight: isSelected ? .semibold : .medium))
                        .foregroundColor(isSelected ? .primary : .primary)
                    
                    HStack(spacing: 6) {
                        Text(preset.op)
                            .font(.system(size: 12, weight: .medium))
                            .foregroundColor(.accentColor)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.accentColor.opacity(0.12))
                            .cornerRadius(4)
                        
                        Text(String(format: "%.2f", preset.value))
                            .font(.system(size: 12, design: .rounded))
                            .foregroundColor(.secondary)
                    }
                }
                
                Spacer()
                
                if isSelected {
                    Image(systemName: "checkmark")
                        .font(.system(size: 12, weight: .bold))
                        .foregroundColor(.accentColor)
                }
            }
            .padding()
            .background(
                RoundedRectangle(cornerRadius: 10)
                    .fill(isSelected ? Color.accentColor.opacity(0.08) : Color(.windowBackgroundColor))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .stroke(isSelected ? Color.accentColor.opacity(0.4) : Color.clear, lineWidth: 2)
            )
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Supporting Views (Integrated versions)

struct ConditionsSectionIntegrated: View {
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
                EmptyConditionsPlaceholder(color: color, onTap: onAdd)
            } else {
                LazyVStack(spacing: 8) {
                    ForEach(Array(conditions.enumerated()), id: \.element.id) { index, condition in
                        ConditionRowIntegrated(condition: condition, color: color)
                            .contentShape(Rectangle())
                            .onTapGesture { onEdit(condition) }
                            .contextMenu {
                                Button("Edit") { onEdit(condition) }
                                Divider()
                                Button(role: .destructive) { onDelete(index) } label: {
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

struct EmptyConditionsPlaceholder: View {
    let color: Color
    let onTap: () -> Void
    
    var body: some View {
        Button(action: onTap) {
            VStack(spacing: 8) {
                Image(systemName: "plus.circle")
                    .font(.system(size: 32))
                    .foregroundColor(color.opacity(0.5))
                Text("Tap to add conditions")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 30)
        }
        .buttonStyle(.plain)
    }
}

struct ConditionRowIntegrated: View {
    let condition: StrategyCondition
    let color: Color
    
    var body: some View {
        HStack(spacing: 12) {
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
            
            Text(condition.operator.uppercased())
                .font(.caption)
                .foregroundColor(.secondary)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(Color.secondary.opacity(0.1))
                .cornerRadius(4)
            
            Text(String(format: "%.2f", condition.value))
                .font(.system(size: 13, weight: .semibold))
            
            Spacer()
            
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

struct ParametersSectionIntegrated: View {
    @Binding var strategy: Strategy
    
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
                ParameterFieldIntegrated(label: "Position Size", value: $strategy.positionSize, suffix: "%", range: 1...100)
                ParameterFieldIntegrated(label: "Stop Loss", value: $strategy.stopLoss, suffix: "%", range: 0.1...50)
                ParameterFieldIntegrated(label: "Take Profit", value: $strategy.takeProfit, suffix: "%", range: 0.1...100)
            }
        }
        .padding()
        .background(Color(.controlBackgroundColor))
        .cornerRadius(12)
    }
}

struct ParameterFieldIntegrated: View {
    let label: String
    @Binding var value: Double
    let suffix: String
    let range: ClosedRange<Double>
    
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label)
                .font(.caption)
                .foregroundColor(.secondary)
            
            HStack(spacing: 4) {
                TextField("", value: $value, format: .number)
                    .textFieldStyle(.roundedBorder)
                    .frame(width: 60)
                Text(suffix)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Slider(value: $value, in: range, step: 0.5)
                .frame(width: 100)
        }
    }
}

struct StrategyMapIntegrated: View {
    let entryCount: Int
    let exitCount: Int
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "map")
                    .foregroundColor(.accentColor)
                Text("Strategy Flow")
                    .font(.headline)
                Spacer()
            }
            
            HStack(spacing: 24) {
                Spacer()
                
                VStack(spacing: 10) {
                    Text("ENTRY")
                        .font(.caption2)
                        .foregroundColor(.green)
                    ForEach(0..<max(entryCount, 1), id: \.self) { i in
                        Group {
                            if i < entryCount {
                                Circle().fill(Color.green).frame(width: 16, height: 16)
                            } else {
                                Circle().stroke(Color.green.opacity(0.3), lineWidth: 1).frame(width: 12, height: 12)
                            }
                        }
                    }
                }
                
                Rectangle().fill(Color.secondary.opacity(0.3)).frame(width: 40, height: 2)
                
                ZStack {
                    Circle().fill(Color.accentColor.opacity(0.2)).frame(width: 50, height: 50)
                    Image(systemName: "brain.head.profile").font(.title3).foregroundColor(.accentColor)
                }
                
                Rectangle().fill(Color.secondary.opacity(0.3)).frame(width: 40, height: 2)
                
                VStack(spacing: 10) {
                    Text("EXIT")
                        .font(.caption2)
                        .foregroundColor(.red)
                    ForEach(0..<max(exitCount, 1), id: \.self) { i in
                        Group {
                            if i < exitCount {
                                Circle().fill(Color.red).frame(width: 16, height: 16)
                            } else {
                                Circle().stroke(Color.red.opacity(0.3), lineWidth: 1).frame(width: 12, height: 12)
                            }
                        }
                    }
                }
                
                Spacer()
            }
            .padding(.vertical, 20)
        }
        .padding()
        .background(Color(.controlBackgroundColor))
        .cornerRadius(12)
    }
}

// MARK: - Extensions

extension IndicatorInterpretation {
    var priority: Int {
        switch self {
        case .strongBullish: return 5
        case .bullish: return 4
        case .overbought: return 4
        case .neutral: return 3
        case .bearish: return 2
        case .oversold: return 2
        case .strongBearish: return 1
        }
    }
}

extension ConditionPreset: Identifiable {
    var id: String { label }
}
