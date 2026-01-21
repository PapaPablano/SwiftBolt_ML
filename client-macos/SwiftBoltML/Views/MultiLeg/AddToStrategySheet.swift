import SwiftUI

struct AddToStrategySheet: View {
    let optionRank: OptionRank
    let symbol: String
    let symbolId: String
    @Environment(\.dismiss) private var dismiss
    @StateObject private var viewModel = MultiLegViewModel()

    @State private var mode: AddMode = .new
    @State private var selectedStrategyId: String?
    @State private var positionType: PositionType = .long
    @State private var contracts: Int = 1
    @State private var entryPrice: Double = 0
    @State private var newStrategyName: String = ""
    @State private var newStrategyType: StrategyType = .longCall
    @State private var isSubmitting = false
    @State private var errorMessage: String?

    enum AddMode: String, CaseIterable {
        case new = "Create New Strategy"
        case existing = "Add to Existing"
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Option summary
                optionSummaryCard

                Divider()

                // Mode picker
                Picker("Mode", selection: $mode) {
                    ForEach(AddMode.allCases, id: \.self) { m in
                        Text(m.rawValue).tag(m)
                    }
                }
                .pickerStyle(.segmented)
                .padding()

                Divider()

                // Content based on mode
                ScrollView {
                    VStack(spacing: 16) {
                        switch mode {
                        case .new:
                            newStrategyForm
                        case .existing:
                            existingStrategyList
                        }
                    }
                    .padding()
                }

                Divider()

                // Error message
                if let error = errorMessage {
                    Text(error)
                        .foregroundColor(.red)
                        .font(.caption)
                        .padding(.horizontal)
                }

                // Action buttons
                HStack {
                    Button("Cancel") {
                        dismiss()
                    }
                    .buttonStyle(.bordered)

                    Spacer()

                    Button {
                        Task { await submit() }
                    } label: {
                        if isSubmitting {
                            ProgressView()
                        } else {
                            Text(mode == .new ? "Create Strategy" : "Add Leg")
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(!isValid || isSubmitting)
                }
                .padding()
            }
            .navigationTitle("Add to Strategy")
            .frame(minWidth: 450, minHeight: 500)
            .onAppear {
                setupDefaults()
            }
            .task {
                await viewModel.loadStrategies(reset: true)
            }
        }
    }

    // MARK: - Option Summary

    private var optionSummaryCard: some View {
        VStack(spacing: 8) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(symbol)
                        .font(.headline)
                    HStack {
                        Text("$\(String(format: "%.2f", optionRank.strike))")
                            .font(.title2.bold())
                        Text(optionRank.side == .call ? "CALL" : "PUT")
                            .font(.caption.bold())
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(optionRank.side == .call ? Color.green.opacity(0.2) : Color.red.opacity(0.2))
                            .foregroundColor(optionRank.side == .call ? .green : .red)
                            .cornerRadius(4)
                    }
                    if let dte = optionRank.daysToExpiry {
                        Text("\(dte) DTE • \(optionRank.expiry)")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }

                Spacer()

                // Composite score
                VStack {
                    Text("\(optionRank.compositeScoreDisplay)")
                        .font(.title.bold())
                        .foregroundColor(optionRank.compositeColor)
                    Text("RANK")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
                .padding(12)
                .background(optionRank.compositeColor.opacity(0.1))
                .cornerRadius(8)
            }

            // Greeks row
            if let delta = optionRank.delta {
                HStack(spacing: 16) {
                    greekLabel("Delta", value: String(format: "%.2f", delta))
                    if let gamma = optionRank.gamma {
                        greekLabel("Gamma", value: String(format: "%.3f", gamma))
                    }
                    if let theta = optionRank.theta {
                        greekLabel("Theta", value: String(format: "%.2f", theta))
                    }
                    if let vega = optionRank.vega {
                        greekLabel("Vega", value: String(format: "%.2f", vega))
                    }
                    if let iv = optionRank.impliedVol {
                        greekLabel("IV", value: String(format: "%.0f%%", iv * 100))
                    }
                    Spacer()
                }
                .font(.caption)
            }
        }
        .padding()
        .background(Color.gray.opacity(0.05))
    }

    private func greekLabel(_ name: String, value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(name)
                .foregroundColor(.secondary)
            Text(value)
                .fontWeight(.medium)
        }
    }

    // MARK: - New Strategy Form

    private var newStrategyForm: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Strategy name
            VStack(alignment: .leading, spacing: 4) {
                Text("Strategy Name")
                    .font(.caption)
                    .foregroundColor(.secondary)
                TextField("e.g., \(symbol) Long Call", text: $newStrategyName)
                    .textFieldStyle(.roundedBorder)
            }

            // Strategy type (filter to single-leg types)
            VStack(alignment: .leading, spacing: 4) {
                Text("Strategy Type")
                    .font(.caption)
                    .foregroundColor(.secondary)
                Picker("Type", selection: $newStrategyType) {
                    ForEach(singleLegTypes, id: \.self) { type in
                        Text(type.displayName).tag(type)
                    }
                }
                .labelsHidden()
            }

            // Position
            VStack(alignment: .leading, spacing: 4) {
                Text("Position")
                    .font(.caption)
                    .foregroundColor(.secondary)
                Picker("Position", selection: $positionType) {
                    Text("Long (Buy)").tag(PositionType.long)
                    Text("Short (Sell)").tag(PositionType.short)
                }
                .pickerStyle(.segmented)
            }

            // Entry details
            HStack(spacing: 16) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Entry Price")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    TextField("Price", value: $entryPrice, format: .number)
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 100)
                }

                VStack(alignment: .leading, spacing: 4) {
                    Text("Contracts")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Stepper("\(contracts)", value: $contracts, in: 1...100)
                }
            }

            // Cost summary
            costSummary
        }
    }

    private var singleLegTypes: [StrategyType] {
        if optionRank.side == .call {
            return [.longCall, .shortCall, .coveredCall, .custom]
        } else {
            return [.longPut, .shortPut, .cashSecuredPut, .custom]
        }
    }

    private var costSummary: some View {
        VStack(alignment: .leading, spacing: 8) {
            Divider()

            let cost = entryPrice * Double(contracts) * 100
            let isDebit = positionType == .long

            HStack {
                Text(isDebit ? "Total Cost (Debit)" : "Total Credit")
                    .font(.subheadline)
                Spacer()
                Text(String(format: "$%.2f", cost))
                    .font(.subheadline.bold())
                    .foregroundColor(isDebit ? .red : .green)
            }
        }
    }

    // MARK: - Existing Strategy List

    private var existingStrategyList: some View {
        VStack(alignment: .leading, spacing: 16) {
            if viewModel.isLoading {
                ProgressView("Loading strategies...")
                    .frame(maxWidth: .infinity)
            } else if openStrategies.isEmpty {
                VStack(spacing: 12) {
                    Image(systemName: "folder.badge.plus")
                        .font(.largeTitle)
                        .foregroundColor(.secondary)
                    Text("No open strategies")
                        .font(.headline)
                    Text("Create a new strategy to get started")
                        .font(.caption)
                        .foregroundColor(.secondary)

                    Button("Switch to Create New") {
                        mode = .new
                    }
                    .buttonStyle(.bordered)
                }
                .frame(maxWidth: .infinity)
                .padding()
            } else {
                // Position selector
                VStack(alignment: .leading, spacing: 4) {
                    Text("Position for this leg")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Picker("Position", selection: $positionType) {
                        Text("Long (Buy)").tag(PositionType.long)
                        Text("Short (Sell)").tag(PositionType.short)
                    }
                    .pickerStyle(.segmented)
                }

                // Entry details
                HStack(spacing: 16) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Entry Price")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        TextField("Price", value: $entryPrice, format: .number)
                            .textFieldStyle(.roundedBorder)
                            .frame(width: 100)
                    }

                    VStack(alignment: .leading, spacing: 4) {
                        Text("Contracts")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Stepper("\(contracts)", value: $contracts, in: 1...100)
                    }
                }

                Divider()

                Text("Select a strategy")
                    .font(.caption)
                    .foregroundColor(.secondary)

                ForEach(openStrategies) { strategy in
                    StrategySelectionRow(
                        strategy: strategy,
                        isSelected: selectedStrategyId == strategy.id
                    ) {
                        selectedStrategyId = strategy.id
                    }
                }
            }
        }
    }

    private var openStrategies: [MultiLegStrategy] {
        viewModel.strategies.filter { $0.status == .open }
    }

    // MARK: - Helpers

    private var isValid: Bool {
        switch mode {
        case .new:
            return !newStrategyName.isEmpty && entryPrice > 0 && contracts > 0
        case .existing:
            return selectedStrategyId != nil && entryPrice > 0 && contracts > 0
        }
    }

    private func setupDefaults() {
        // Set entry price from mark price
        entryPrice = optionRank.derivedMark ?? optionRank.bid ?? 0

        // Set default strategy name
        let sideLabel = optionRank.side == .call ? "Call" : "Put"
        newStrategyName = "\(symbol) \(Int(optionRank.strike)) \(sideLabel)"

        // Set default strategy type based on option side
        newStrategyType = optionRank.side == .call ? .longCall : .longPut
    }

    private func submit() async {
        isSubmitting = true
        errorMessage = nil

        do {
            switch mode {
            case .new:
                try await createNewStrategy()
            case .existing:
                try await addToExistingStrategy()
            }
            dismiss()
        } catch {
            errorMessage = error.localizedDescription
        }

        isSubmitting = false
    }

    private func createNewStrategy() async throws {
        let legInput = LegCreationInput(
            position: positionType,
            optionType: optionRank.side == .call ? .call : .put,
            strike: optionRank.strike,
            expiry: optionRank.expiry,
            entryPrice: entryPrice,
            contracts: contracts,
            role: .primaryLeg,
            delta: optionRank.delta,
            gamma: optionRank.gamma,
            theta: optionRank.theta,
            vega: optionRank.vega,
            rho: optionRank.rho,
            impliedVol: optionRank.impliedVol
        )

        let request = StrategyCreationHelper.buildRequest(
            name: newStrategyName,
            strategyType: newStrategyType,
            symbolId: symbolId.isEmpty ? symbol : symbolId,
            ticker: symbol,
            legs: [legInput],
            forecastAlignment: nil,
            notes: "Created from Options Ranker",
            tags: ["source": "ranker"]
        )

        let result = await viewModel.createStrategy(request)
        if result == nil {
            throw NSError(domain: "AddToStrategy", code: 1, userInfo: [
                NSLocalizedDescriptionKey: viewModel.errorMessage ?? "Failed to create strategy"
            ])
        }
    }

    private func addToExistingStrategy() async throws {
        // TODO: Implement adding leg to existing strategy
        // This would require a new API endpoint: multi-leg-add-leg
        throw NSError(domain: "AddToStrategy", code: 2, userInfo: [
            NSLocalizedDescriptionKey: "Adding to existing strategy is not yet implemented. Please create a new strategy."
        ])
    }
}

// MARK: - Strategy Selection Row

struct StrategySelectionRow: View {
    let strategy: MultiLegStrategy
    let isSelected: Bool
    let onSelect: () -> Void

    var body: some View {
        Button(action: onSelect) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(strategy.name)
                        .font(.subheadline.bold())
                    HStack(spacing: 8) {
                        Text(strategy.strategyType.displayName)
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Text(strategy.underlyingTicker)
                            .font(.caption)
                            .padding(.horizontal, 4)
                            .padding(.vertical, 2)
                            .background(Color.gray.opacity(0.1))
                            .cornerRadius(4)
                        if let legs = strategy.legs {
                            Text("\(legs.count) legs")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                }

                Spacer()

                if isSelected {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.accentColor)
                }
            }
            .padding()
            .background(isSelected ? Color.accentColor.opacity(0.1) : Color.gray.opacity(0.05))
            .cornerRadius(8)
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(isSelected ? Color.accentColor : Color.clear, lineWidth: 2)
            )
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Preview

#Preview {
    AddToStrategySheet(
        optionRank: .example,
        symbol: "AAPL",
        symbolId: "sym-1"
    )
}
