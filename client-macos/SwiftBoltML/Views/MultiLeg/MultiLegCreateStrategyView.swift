import SwiftUI

struct MultiLegCreateStrategyView: View {
    @ObservedObject var viewModel: MultiLegViewModel
    @Binding var isPresented: Bool

    @State private var currentStep: CreateStep = .selectType
    @State private var selectedType: StrategyType?
    @State private var strategyName: String = ""
    @State private var underlyingTicker: String = ""
    @State private var underlyingSymbolId: String = ""
    @State private var legs: [LegInput] = []
    @State private var notes: String = ""
    @State private var forecastAlignment: ForecastAlignment?
    @State private var isCreating = false
    @State private var errorMessage: String?

    enum CreateStep: Int, CaseIterable {
        case selectType
        case enterDetails
        case addLegs
        case review

        var title: String {
            switch self {
            case .selectType: return "Select Strategy"
            case .enterDetails: return "Strategy Details"
            case .addLegs: return "Add Legs"
            case .review: return "Review & Create"
            }
        }
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Progress indicator
                progressIndicator

                Divider()

                // Content based on step
                stepContent
            }
            .navigationTitle("Create Strategy")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        isPresented = false
                    }
                }

                ToolbarItem(placement: .primaryAction) {
                    if currentStep == .review {
                        Button("Create") {
                            Task { await createStrategy() }
                        }
                        .disabled(isCreating || !isValid)
                    }
                }
            }
        }
        .frame(minWidth: 600, minHeight: 500)
    }

    // MARK: - Progress Indicator

    private var progressIndicator: some View {
        HStack(spacing: 0) {
            ForEach(CreateStep.allCases, id: \.self) { step in
                HStack(spacing: 8) {
                    Circle()
                        .fill(stepColor(step))
                        .frame(width: 24, height: 24)
                        .overlay {
                            if step.rawValue < currentStep.rawValue {
                                Image(systemName: "checkmark")
                                    .font(.caption.bold())
                                    .foregroundColor(.white)
                            } else {
                                Text("\(step.rawValue + 1)")
                                    .font(.caption.bold())
                                    .foregroundColor(step == currentStep ? .white : .secondary)
                            }
                        }

                    Text(step.title)
                        .font(.subheadline)
                        .foregroundColor(step == currentStep ? .primary : .secondary)
                }

                if step != .review {
                    Rectangle()
                        .fill(step.rawValue < currentStep.rawValue ? Color.accentColor : Color.gray.opacity(0.3))
                        .frame(height: 2)
                        .frame(maxWidth: .infinity)
                }
            }
        }
        .padding()
    }

    private func stepColor(_ step: CreateStep) -> Color {
        if step.rawValue < currentStep.rawValue {
            return .accentColor
        } else if step == currentStep {
            return .accentColor
        }
        return .gray.opacity(0.3)
    }

    // MARK: - Step Content

    @ViewBuilder
    private var stepContent: some View {
        switch currentStep {
        case .selectType:
            selectTypeStep
        case .enterDetails:
            enterDetailsStep
        case .addLegs:
            addLegsStep
        case .review:
            reviewStep
        }
    }

    // MARK: - Step 1: Select Strategy Type

    private var selectTypeStep: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Choose a strategy type")
                    .font(.headline)
                    .padding(.horizontal)

                LazyVGrid(columns: [GridItem(.adaptive(minimum: 180))], spacing: 12) {
                    ForEach(strategyCategories, id: \.name) { category in
                        VStack(alignment: .leading, spacing: 8) {
                            Text(category.name)
                                .font(.subheadline.bold())
                                .foregroundColor(.secondary)

                            ForEach(category.types, id: \.self) { type in
                                StrategyTypeCard(
                                    type: type,
                                    isSelected: selectedType == type
                                ) {
                                    selectedType = type
                                    initializeLegsForType(type)
                                    withAnimation {
                                        currentStep = .enterDetails
                                    }
                                }
                            }
                        }
                    }
                }
                .padding()
            }
        }
    }

    private var strategyCategories: [(name: String, types: [StrategyType])] {
        [
            ("Vertical Spreads", [.bullCallSpread, .bearCallSpread, .bullPutSpread, .bearPutSpread]),
            ("Volatility Plays", [.longStraddle, .shortStraddle, .longStrangle, .shortStrangle]),
            ("Multi-Leg", [.ironCondor, .ironButterfly, .butterflySpread]),
            ("Time-Based", [.calendarSpread, .diagonalSpread]),
            ("Ratio", [.callRatioBackspread, .putRatioBackspread]),
            ("Other", [.custom])
        ]
    }

    // MARK: - Step 2: Enter Details

    private var enterDetailsStep: some View {
        Form {
            Section("Strategy Info") {
                TextField("Strategy Name", text: $strategyName)
                    .textFieldStyle(.roundedBorder)

                TextField("Underlying Symbol", text: $underlyingTicker)
                    .textFieldStyle(.roundedBorder)
                    .textCase(.uppercase)
                    .onChange(of: underlyingTicker) { _, newValue in
                        underlyingTicker = newValue.uppercased()
                    }
            }

            Section("Market View (Optional)") {
                Picker("Forecast Alignment", selection: $forecastAlignment) {
                    Text("None").tag(nil as ForecastAlignment?)
                    Text("Bullish").tag(ForecastAlignment.bullish as ForecastAlignment?)
                    Text("Neutral").tag(ForecastAlignment.neutral as ForecastAlignment?)
                    Text("Bearish").tag(ForecastAlignment.bearish as ForecastAlignment?)
                }
                .pickerStyle(.segmented)
            }

            Section("Notes (Optional)") {
                TextEditor(text: $notes)
                    .frame(height: 80)
            }

            Section {
                HStack {
                    Button("Back") {
                        withAnimation { currentStep = .selectType }
                    }
                    .buttonStyle(.bordered)

                    Spacer()

                    Button("Next: Add Legs") {
                        withAnimation { currentStep = .addLegs }
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(strategyName.isEmpty || underlyingTicker.isEmpty)
                }
            }
        }
        .padding()
    }

    // MARK: - Step 3: Add Legs

    private var addLegsStep: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(spacing: 16) {
                    if let type = selectedType {
                        HStack {
                            Text(type.displayName)
                                .font(.headline)

                            if let expected = type.expectedLegCount {
                                Text("(\(expected) legs)")
                                    .foregroundColor(.secondary)
                            }

                            Spacer()
                        }
                        .padding(.horizontal)
                    }

                    ForEach(legs.indices, id: \.self) { index in
                        LegInputCard(
                            legNumber: index + 1,
                            input: $legs[index],
                            onRemove: legs.count > 1 ? { legs.remove(at: index) } : nil
                        )
                    }

                    if selectedType == .custom || legs.count < (selectedType?.expectedLegCount ?? 10) {
                        Button {
                            legs.append(LegInput())
                        } label: {
                            Label("Add Leg", systemImage: "plus.circle")
                        }
                        .buttonStyle(.bordered)
                    }
                }
                .padding()
            }

            Divider()

            HStack {
                Button("Back") {
                    withAnimation { currentStep = .enterDetails }
                }
                .buttonStyle(.bordered)

                Spacer()

                Button("Next: Review") {
                    withAnimation { currentStep = .review }
                }
                .buttonStyle(.borderedProminent)
                .disabled(!legsValid)
            }
            .padding()
        }
    }

    private var legsValid: Bool {
        !legs.isEmpty && legs.allSatisfy { leg in
            leg.strike > 0 &&
            !leg.expiry.isEmpty &&
            leg.entryPrice > 0 &&
            leg.contracts > 0
        }
    }

    // MARK: - Step 4: Review

    private var reviewStep: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    // Strategy summary
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Strategy Summary")
                            .font(.headline)

                        LabeledContent("Name", value: strategyName)
                        LabeledContent("Type", value: selectedType?.displayName ?? "N/A")
                        LabeledContent("Underlying", value: underlyingTicker)
                        if let alignment = forecastAlignment {
                            LabeledContent("Forecast", value: alignment.rawValue.capitalized)
                        }
                    }
                    .padding()
                    .background(Color.gray.opacity(0.05))
                    .cornerRadius(8)

                    // Legs summary
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Legs (\(legs.count))")
                            .font(.headline)

                        ForEach(legs.indices, id: \.self) { index in
                            let leg = legs[index]
                            HStack {
                                Text("Leg \(index + 1)")
                                    .font(.subheadline.bold())

                                Text(leg.position == .long ? "Long" : "Short")
                                    .foregroundColor(leg.position == .long ? .green : .red)

                                Text("\(Int(leg.strike))")
                                Text(leg.optionType == .call ? "Call" : "Put")

                                Spacer()

                                Text(String(format: "%.2f", leg.entryPrice))
                                Text("x\(leg.contracts)")
                            }
                            .font(.subheadline)
                        }

                        Divider()

                        let netPremium = calculateNetPremium()
                        HStack {
                            Text("Net Premium")
                                .font(.subheadline.bold())
                            Spacer()
                            Text(netPremium >= 0 ? String(format: "+$%.2f credit", netPremium) : String(format: "$%.2f debit", abs(netPremium)))
                                .font(.subheadline.bold())
                                .foregroundColor(netPremium >= 0 ? .green : .red)
                        }
                    }
                    .padding()
                    .background(Color.gray.opacity(0.05))
                    .cornerRadius(8)

                    if !notes.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Notes")
                                .font(.headline)
                            Text(notes)
                                .foregroundColor(.secondary)
                        }
                        .padding()
                        .background(Color.gray.opacity(0.05))
                        .cornerRadius(8)
                    }

                    if let error = errorMessage {
                        Text(error)
                            .foregroundColor(.red)
                            .padding()
                            .background(Color.red.opacity(0.1))
                            .cornerRadius(8)
                    }
                }
                .padding()
            }

            Divider()

            HStack {
                Button("Back") {
                    withAnimation { currentStep = .addLegs }
                }
                .buttonStyle(.bordered)

                Spacer()

                Button {
                    Task { await createStrategy() }
                } label: {
                    if isCreating {
                        ProgressView()
                    } else {
                        Text("Create Strategy")
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(isCreating || !isValid)
            }
            .padding()
        }
    }

    // MARK: - Helpers

    private var isValid: Bool {
        !strategyName.isEmpty &&
        !underlyingTicker.isEmpty &&
        selectedType != nil &&
        legsValid
    }

    private func initializeLegsForType(_ type: StrategyType) {
        legs = []

        switch type {
        case .bullCallSpread:
            legs = [
                LegInput(position: .long, optionType: .call),
                LegInput(position: .short, optionType: .call)
            ]
        case .bearCallSpread:
            legs = [
                LegInput(position: .short, optionType: .call),
                LegInput(position: .long, optionType: .call)
            ]
        case .bullPutSpread:
            legs = [
                LegInput(position: .short, optionType: .put),
                LegInput(position: .long, optionType: .put)
            ]
        case .bearPutSpread:
            legs = [
                LegInput(position: .long, optionType: .put),
                LegInput(position: .short, optionType: .put)
            ]
        case .longStraddle:
            legs = [
                LegInput(position: .long, optionType: .call),
                LegInput(position: .long, optionType: .put)
            ]
        case .shortStraddle:
            legs = [
                LegInput(position: .short, optionType: .call),
                LegInput(position: .short, optionType: .put)
            ]
        case .longStrangle:
            legs = [
                LegInput(position: .long, optionType: .call),
                LegInput(position: .long, optionType: .put)
            ]
        case .shortStrangle:
            legs = [
                LegInput(position: .short, optionType: .call),
                LegInput(position: .short, optionType: .put)
            ]
        case .ironCondor:
            legs = [
                LegInput(position: .long, optionType: .put),
                LegInput(position: .short, optionType: .put),
                LegInput(position: .short, optionType: .call),
                LegInput(position: .long, optionType: .call)
            ]
        case .ironButterfly:
            legs = [
                LegInput(position: .long, optionType: .put),
                LegInput(position: .short, optionType: .put),
                LegInput(position: .short, optionType: .call),
                LegInput(position: .long, optionType: .call)
            ]
        case .butterflySpread:
            legs = [
                LegInput(position: .long, optionType: .call),
                LegInput(position: .short, optionType: .call),
                LegInput(position: .long, optionType: .call)
            ]
        default:
            legs = [LegInput()]
        }
    }

    private func calculateNetPremium() -> Double {
        legs.reduce(0) { total, leg in
            let multiplier = leg.position == .long ? -1.0 : 1.0
            return total + (leg.entryPrice * Double(leg.contracts) * 100 * multiplier)
        }
    }

    private func createStrategy() async {
        guard let type = selectedType else { return }

        isCreating = true
        errorMessage = nil

        let legInputs = legs.enumerated().map { index, leg in
            LegCreationInput(
                position: leg.position,
                optionType: leg.optionType,
                strike: leg.strike,
                expiry: leg.expiry,
                entryPrice: leg.entryPrice,
                contracts: leg.contracts,
                role: nil,
                delta: nil,
                gamma: nil,
                theta: nil,
                vega: nil,
                rho: nil,
                impliedVol: nil
            )
        }

        let request = StrategyCreationHelper.buildRequest(
            name: strategyName,
            strategyType: type,
            symbolId: underlyingSymbolId.isEmpty ? underlyingTicker : underlyingSymbolId,
            ticker: underlyingTicker,
            legs: legInputs,
            forecastAlignment: forecastAlignment,
            notes: notes.isEmpty ? nil : notes
        )

        let result = await viewModel.createStrategy(request)

        isCreating = false

        if result != nil {
            isPresented = false
        } else {
            errorMessage = viewModel.errorMessage ?? "Failed to create strategy"
        }
    }
}

// MARK: - Supporting Views

struct StrategyTypeCard: View {
    let type: StrategyType
    let isSelected: Bool
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(type.displayName)
                        .font(.subheadline.bold())

                    HStack(spacing: 4) {
                        if let legs = type.expectedLegCount {
                            Text("\(legs) legs")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }

                        if type.isBullish {
                            Text("Bullish")
                                .font(.caption)
                                .foregroundColor(.green)
                        } else if type.isBearish {
                            Text("Bearish")
                                .font(.caption)
                                .foregroundColor(.red)
                        } else if type.isNeutral {
                            Text("Neutral")
                                .font(.caption)
                                .foregroundColor(.gray)
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

struct LegInput: Identifiable {
    let id = UUID()
    var position: PositionType = .long
    var optionType: MultiLegOptionType = .call
    var strike: Double = 0
    var expiry: String = ""
    var entryPrice: Double = 0
    var contracts: Int = 1
}

struct LegInputCard: View {
    let legNumber: Int
    @Binding var input: LegInput
    let onRemove: (() -> Void)?

    @State private var strikeText: String = ""
    @State private var priceText: String = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Leg \(legNumber)")
                    .font(.headline)

                Spacer()

                if let onRemove = onRemove {
                    Button(action: onRemove) {
                        Image(systemName: "trash")
                            .foregroundColor(.red)
                    }
                    .buttonStyle(.borderless)
                }
            }

            HStack(spacing: 12) {
                // Position
                VStack(alignment: .leading, spacing: 4) {
                    Text("Position")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Picker("Position", selection: $input.position) {
                        Text("Long").tag(PositionType.long)
                        Text("Short").tag(PositionType.short)
                    }
                    .pickerStyle(.segmented)
                }
                .frame(width: 120)

                // Option Type
                VStack(alignment: .leading, spacing: 4) {
                    Text("Type")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Picker("Type", selection: $input.optionType) {
                        Text("Call").tag(MultiLegOptionType.call)
                        Text("Put").tag(MultiLegOptionType.put)
                    }
                    .pickerStyle(.segmented)
                }
                .frame(width: 100)

                // Strike
                VStack(alignment: .leading, spacing: 4) {
                    Text("Strike")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    TextField("Strike", text: $strikeText)
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 80)
                        .onChange(of: strikeText) { _, newValue in
                            input.strike = Double(newValue) ?? 0
                        }
                }

                // Expiry
                VStack(alignment: .leading, spacing: 4) {
                    Text("Expiry")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    TextField("YYYY-MM-DD", text: $input.expiry)
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 120)
                }

                // Entry Price
                VStack(alignment: .leading, spacing: 4) {
                    Text("Entry Price")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    TextField("Price", text: $priceText)
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 80)
                        .onChange(of: priceText) { _, newValue in
                            input.entryPrice = Double(newValue) ?? 0
                        }
                }

                // Contracts
                VStack(alignment: .leading, spacing: 4) {
                    Text("Qty")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Stepper("\(input.contracts)", value: $input.contracts, in: 1...100)
                }
            }
        }
        .padding()
        .background(Color.gray.opacity(0.05))
        .cornerRadius(8)
        .onAppear {
            if input.strike > 0 {
                strikeText = String(format: "%.0f", input.strike)
            }
            if input.entryPrice > 0 {
                priceText = String(format: "%.2f", input.entryPrice)
            }
        }
    }
}

// MARK: - Preview

#Preview {
    MultiLegCreateStrategyView(
        viewModel: MultiLegViewModel(),
        isPresented: .constant(true)
    )
}
