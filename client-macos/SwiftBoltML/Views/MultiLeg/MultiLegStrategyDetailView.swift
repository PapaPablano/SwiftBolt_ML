import SwiftUI

struct MultiLegStrategyDetailView: View {
    @ObservedObject var viewModel: MultiLegViewModel
    let strategy: MultiLegStrategy
    @Environment(\.dismiss) private var dismiss

    @State private var showCloseStrategySheet = false
    @State private var showEditSheet = false
    @State private var selectedLegToClose: OptionsLeg?
    @State private var showDeleteConfirmation = false
    @State private var isDeleting = false
    @State private var deleteErrorMessage: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    // Header card
                    headerCard

                    // P&L and Risk card
                    plRiskCard

                    // Greeks card
                    greeksCard

                    // Legs section
                    legsSection

                    // Alerts section
                    if !activeAlerts.isEmpty {
                        alertsSection
                    }

                    // Notes section
                    if let notes = strategy.notes, !notes.isEmpty {
                        notesSection(notes)
                    }
                }
                .padding()
            }
            .navigationTitle(strategy.name)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") {
                        dismiss()
                    }
                }

                ToolbarItemGroup(placement: .primaryAction) {
                    Button {
                        showEditSheet = true
                    } label: {
                        Image(systemName: "pencil")
                    }

                    if strategy.status == .open {
                        Button {
                            showCloseStrategySheet = true
                        } label: {
                            Label("Close", systemImage: "xmark.circle")
                        }
                        .tint(.orange)
                    }

                    Button {
                        showDeleteConfirmation = true
                    } label: {
                        Image(systemName: "trash")
                    }
                    .tint(.red)
                }
            }
            .alert("Delete Strategy", isPresented: $showDeleteConfirmation) {
                Button("Cancel", role: .cancel) { }
                Button("Delete", role: .destructive) {
                    Task {
                        isDeleting = true
                        let success = await viewModel.deleteStrategy(strategyId: strategy.id)
                        isDeleting = false
                        if success {
                            dismiss()
                        } else {
                            deleteErrorMessage = viewModel.errorMessage ?? "Delete failed."
                        }
                    }
                }
            } message: {
                Text("Are you sure you want to permanently delete '\(strategy.name)'? This action cannot be undone.")
            }
            .alert("Delete Failed", isPresented: Binding(
                get: { deleteErrorMessage != nil },
                set: { if !$0 { deleteErrorMessage = nil } }
            )) {
                Button("OK") { deleteErrorMessage = nil }
            } message: {
                if let msg = deleteErrorMessage { Text(msg) }
            }
        }
        .sheet(isPresented: $showCloseStrategySheet) {
            CloseStrategySheet(viewModel: viewModel, strategy: strategy)
        }
        .sheet(item: $selectedLegToClose) { leg in
            CloseLegSheet(viewModel: viewModel, strategy: strategy, leg: leg)
        }
        .task {
            if viewModel.strategyDetail?.strategy.id != strategy.id {
                await viewModel.loadStrategyDetail(strategyId: strategy.id)
            }
        }
    }

    private var legs: [OptionsLeg] {
        viewModel.strategyDetail?.legs ?? strategy.legs ?? []
    }

    private var activeAlerts: [MultiLegAlert] {
        (viewModel.strategyDetail?.alerts ?? strategy.alerts ?? [])
            .filter { $0.isActive }
            .sorted { $0.severity.priority > $1.severity.priority }
    }

    // MARK: - Header Card

    private var headerCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text(strategy.underlyingTicker)
                            .font(.title.bold())

                        StatusBadge(status: strategy.status)
                    }

                    Text(strategy.strategyType.displayName)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }

                Spacer()

                VStack(alignment: .trailing, spacing: 4) {
                    Text(strategy.plFormatted)
                        .font(.title2.bold())
                        .foregroundColor(strategy.plColor)

                    Text(strategy.plPctFormatted)
                        .font(.subheadline)
                        .foregroundColor(strategy.plColor)
                }
            }

            Divider()

            HStack(spacing: 20) {
                InfoItem(label: "Contracts", value: "\(strategy.numContracts)")
                InfoItem(label: "DTE", value: strategy.dteLabel)
                InfoItem(label: "Net Premium", value: strategy.netPremiumFormatted)

                if let alignment = strategy.forecastAlignment {
                    InfoItem(
                        label: "Forecast",
                        value: alignment.rawValue.capitalized,
                        color: alignmentColor(alignment)
                    )
                }
            }
        }
        .padding()
        .background(Color.gray.opacity(0.05))
        .cornerRadius(12)
    }

    // MARK: - P&L and Risk Card

    private var plRiskCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("P&L & Risk")
                .font(.headline)

            HStack(spacing: 20) {
                VStack(alignment: .leading, spacing: 8) {
                    RiskRewardItem(label: "Current Value", value: formatCurrency(strategy.currentValue))
                    RiskRewardItem(label: "Unrealized P&L", value: strategy.plFormatted, color: strategy.plColor)
                    RiskRewardItem(label: "Realized P&L", value: formatCurrency(strategy.realizedPL))
                }

                Divider()

                VStack(alignment: .leading, spacing: 8) {
                    RiskRewardItem(label: "Max Risk", value: strategy.maxRiskFormatted, color: .red)
                    RiskRewardItem(label: "Max Reward", value: strategy.maxRewardFormatted, color: .green)

                    if let breakevens = strategy.breakevenPoints, !breakevens.isEmpty {
                        RiskRewardItem(
                            label: "Breakeven",
                            value: breakevens.map { String(format: "%.2f", $0) }.joined(separator: ", ")
                        )
                    }
                }
            }
        }
        .padding()
        .background(Color.gray.opacity(0.05))
        .cornerRadius(12)
    }

    // MARK: - Greeks Card

    private var greeksCard: some View {
        let live = viewModel.liveGreeksByStrategyId[strategy.id]
        return VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Greeks")
                    .font(.headline)

                Spacer()

                Text(live != nil ? "Live" : strategy.greeksAgeLabel)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            HStack(spacing: 0) {
                GreekDisplay(name: "Delta", value: live?.combinedDelta ?? strategy.combinedDelta, format: "%.2f")
                Spacer()
                GreekDisplay(name: "Gamma", value: live?.combinedGamma ?? strategy.combinedGamma, format: "%.3f")
                Spacer()
                GreekDisplay(name: "Theta", value: live?.combinedTheta ?? strategy.combinedTheta, format: "%.2f", negativeIsGood: false)
                Spacer()
                GreekDisplay(name: "Vega", value: live?.combinedVega ?? strategy.combinedVega, format: "%.2f")
                Spacer()
                GreekDisplay(name: "Rho", value: live?.combinedRho ?? strategy.combinedRho, format: "%.3f")
            }
        }
        .padding()
        .background(Color.gray.opacity(0.05))
        .cornerRadius(12)
    }

    // MARK: - Legs Section

    private var legsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Legs")
                    .font(.headline)

                Spacer()

                Text("\(legs.filter { !$0.isClosed }.count) open / \(legs.count) total")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            ForEach(legs.sorted { $0.legNumber < $1.legNumber }) { leg in
                LegRow(
                    leg: leg,
                    liveDelta: viewModel.liveGreeksByStrategyId[strategy.id]?.perLeg[leg.id]?.delta
                ) {
                    selectedLegToClose = leg
                }
            }
        }
        .padding()
        .background(Color.gray.opacity(0.05))
        .cornerRadius(12)
    }

    // MARK: - Alerts Section

    private var alertsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Active Alerts")
                    .font(.headline)

                Spacer()

                if activeAlerts.contains(where: { $0.severity == .critical }) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(.red)
                }
            }

            ForEach(activeAlerts) { alert in
                MultiLegAlertRow(alert: alert)
            }
        }
        .padding()
        .background(Color.gray.opacity(0.05))
        .cornerRadius(12)
    }

    // MARK: - Notes Section

    private func notesSection(_ notes: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Notes")
                .font(.headline)

            Text(notes)
                .font(.body)
                .foregroundColor(.secondary)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.gray.opacity(0.05))
        .cornerRadius(12)
    }

    // MARK: - Helpers

    private func formatCurrency(_ value: Double?) -> String {
        guard let v = value else { return "N/A" }
        return String(format: "$%.2f", v)
    }

    private func alignmentColor(_ alignment: ForecastAlignment) -> Color {
        switch alignment {
        case .bullish: return .green
        case .bearish: return .red
        case .neutral: return .gray
        }
    }
}

// MARK: - Supporting Views

struct StatusBadge: View {
    let status: StrategyStatus

    var body: some View {
        Text(status.displayName)
            .font(.caption.bold())
            .foregroundColor(.white)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(status.color)
            .cornerRadius(6)
    }
}

struct InfoItem: View {
    let label: String
    let value: String
    var color: Color = .primary

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label)
                .font(.caption)
                .foregroundColor(.secondary)
            Text(value)
                .font(.subheadline.bold())
                .foregroundColor(color)
        }
    }
}

struct RiskRewardItem: View {
    let label: String
    let value: String
    var color: Color = .primary

    var body: some View {
        HStack {
            Text(label)
                .font(.subheadline)
                .foregroundColor(.secondary)
            Spacer()
            Text(value)
                .font(.subheadline.bold())
                .foregroundColor(color)
        }
    }
}

struct GreekDisplay: View {
    let name: String
    let value: Double?
    let format: String
    var negativeIsGood: Bool = true

    var body: some View {
        VStack(spacing: 4) {
            Text(name)
                .font(.caption)
                .foregroundColor(.secondary)

            if let v = value {
                Text(String(format: format, v))
                    .font(.headline.monospacedDigit())
                    .foregroundColor(valueColor(v))
            } else {
                Text("N/A")
                    .font(.headline)
                    .foregroundColor(.gray)
            }
        }
        .frame(minWidth: 60)
    }

    private func valueColor(_ v: Double) -> Color {
        if name == "Delta" {
            return abs(v) > 0.5 ? .green : .primary
        }
        if name == "Theta" {
            return v < 0 ? .red : .green
        }
        return .primary
    }
}

struct LegRow: View {
    let leg: OptionsLeg
    var liveDelta: Double? = nil
    let onClose: () -> Void

    private var displayDelta: Double? { liveDelta ?? leg.currentDelta }

    var body: some View {
        HStack(spacing: 12) {
            // Position indicator
            Circle()
                .fill(leg.positionType == .long ? Color.green : Color.red)
                .frame(width: 8, height: 8)

            // Leg info
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(leg.displayLabel)
                        .font(.subheadline.bold())

                    Text(leg.expiryFormatted)
                        .font(.caption)
                        .foregroundColor(.secondary)

                    let (badgeText, badgeColor) = leg.statusBadge
                    Text(badgeText)
                        .font(.caption2)
                        .foregroundColor(.white)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(badgeColor)
                        .cornerRadius(4)
                }

                HStack(spacing: 8) {
                    Text("Entry: \(String(format: "%.2f", leg.entryPrice))")
                        .font(.caption)
                        .foregroundColor(.secondary)

                    if let current = leg.currentPrice {
                        Text("Current: \(String(format: "%.2f", current))")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }

                    if let dte = leg.currentDTE {
                        Text("\(dte) DTE")
                            .font(.caption)
                            .foregroundColor(dte <= 3 ? .red : .secondary)
                    }
                }
            }

            Spacer()

            // Greeks
            if let delta = displayDelta {
                VStack(spacing: 0) {
                    Text("Delta")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Text(String(format: "%.2f", delta))
                        .font(.caption.monospacedDigit())
                }
                .frame(width: 50)
            }

            // P&L
            VStack(alignment: .trailing, spacing: 2) {
                Text(leg.plFormatted)
                    .font(.subheadline.bold())
                    .foregroundColor(leg.plColor)

                Text(leg.plPctFormatted)
                    .font(.caption)
                    .foregroundColor(leg.plColor)
            }
            .frame(minWidth: 70, alignment: .trailing)

            // Close button
            if !leg.isClosed {
                Button {
                    onClose()
                } label: {
                    Image(systemName: "xmark.circle")
                        .foregroundColor(.orange)
                }
                .buttonStyle(.borderless)
            }
        }
        .padding()
        .background(leg.isClosed ? Color.gray.opacity(0.1) : Color.clear)
        .cornerRadius(8)
    }
}

struct MultiLegAlertRow: View {
    let alert: MultiLegAlert

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: alert.alertType.icon)
                .foregroundColor(alert.severity.color)
                .frame(width: 24)

            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(alert.title)
                        .font(.subheadline.bold())

                    Text(alert.alertType.displayName)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(alert.severity.color.opacity(0.2))
                        .cornerRadius(4)
                }

                if let reason = alert.reason {
                    Text(reason)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                if let action = alert.suggestedAction {
                    Text(action)
                        .font(.caption)
                        .foregroundColor(.accentColor)
                }
            }

            Spacer()

            Text(alert.ageLabel)
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding()
        .background(alert.severity.color.opacity(0.05))
        .cornerRadius(8)
    }
}

// MARK: - Close Strategy Sheet

struct CloseStrategySheet: View {
    @ObservedObject var viewModel: MultiLegViewModel
    let strategy: MultiLegStrategy
    @Environment(\.dismiss) private var dismiss

    @State private var exitPrices: [String: String] = [:]
    @State private var notes: String = ""
    @State private var isClosing = false

    private var openLegs: [OptionsLeg] {
        (viewModel.strategyDetail?.legs ?? strategy.legs ?? [])
            .filter { !$0.isClosed }
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Exit Prices") {
                    ForEach(openLegs) { leg in
                        HStack {
                            Text(leg.displayLabel)
                            Spacer()
                            TextField("Price", text: binding(for: leg.id))
                                .multilineTextAlignment(.trailing)
                                .frame(width: 100)
                        }
                    }
                }

                Section("Notes (Optional)") {
                    TextEditor(text: $notes)
                        .frame(height: 80)
                }

                Section {
                    Button {
                        Task { await closeStrategy() }
                    } label: {
                        HStack {
                            Spacer()
                            if isClosing {
                                ProgressView()
                            } else {
                                Text("Close Strategy")
                            }
                            Spacer()
                        }
                    }
                    .disabled(isClosing || !allPricesValid)
                }
            }
            .navigationTitle("Close Strategy")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
    }

    private func binding(for legId: String) -> Binding<String> {
        Binding(
            get: { exitPrices[legId] ?? "" },
            set: { exitPrices[legId] = $0 }
        )
    }

    private var allPricesValid: Bool {
        openLegs.allSatisfy { leg in
            if let price = exitPrices[leg.id], let _ = Double(price) {
                return true
            }
            return false
        }
    }

    private func closeStrategy() async {
        isClosing = true

        let prices = openLegs.compactMap { leg -> (String, Double)? in
            guard let priceStr = exitPrices[leg.id], let price = Double(priceStr) else { return nil }
            return (leg.id, price)
        }

        let success = await viewModel.closeStrategy(
            strategyId: strategy.id,
            exitPrices: prices,
            notes: notes.isEmpty ? nil : notes
        )

        isClosing = false

        if success {
            dismiss()
        }
    }
}

// MARK: - Close Leg Sheet

struct CloseLegSheet: View {
    @ObservedObject var viewModel: MultiLegViewModel
    let strategy: MultiLegStrategy
    let leg: OptionsLeg
    @Environment(\.dismiss) private var dismiss

    @State private var exitPrice: String = ""
    @State private var notes: String = ""
    @State private var isClosing = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Leg Details") {
                    LabeledContent("Position", value: leg.displayLabel)
                    LabeledContent("Expiry", value: leg.expiryFormatted)
                    LabeledContent("Entry Price", value: String(format: "%.2f", leg.entryPrice))
                    if let current = leg.currentPrice {
                        LabeledContent("Current Price", value: String(format: "%.2f", current))
                    }
                }

                Section("Exit Price") {
                    TextField("Exit Price", text: $exitPrice)
                }

                Section("Notes (Optional)") {
                    TextEditor(text: $notes)
                        .frame(height: 80)
                }

                if let exitVal = Double(exitPrice) {
                    Section("Estimated P&L") {
                        let pl = calculatePL(exitPrice: exitVal)
                        LabeledContent("P&L", value: String(format: "%+.2f", pl))
                            .foregroundColor(pl >= 0 ? .green : .red)
                    }
                }

                Section {
                    Button {
                        Task { await closeLeg() }
                    } label: {
                        HStack {
                            Spacer()
                            if isClosing {
                                ProgressView()
                            } else {
                                Text("Close Leg")
                            }
                            Spacer()
                        }
                    }
                    .disabled(isClosing || Double(exitPrice) == nil)
                }
            }
            .navigationTitle("Close Leg")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
        .onAppear {
            if let current = leg.currentPrice {
                exitPrice = String(format: "%.2f", current)
            }
        }
    }

    private func calculatePL(exitPrice: Double) -> Double {
        let multiplier = leg.positionType == .long ? 1.0 : -1.0
        return (exitPrice - leg.entryPrice) * Double(leg.contracts) * 100 * multiplier
    }

    private func closeLeg() async {
        guard let price = Double(exitPrice) else { return }

        isClosing = true

        let success = await viewModel.closeLeg(
            strategyId: strategy.id,
            legId: leg.id,
            exitPrice: price,
            notes: notes.isEmpty ? nil : notes
        )

        isClosing = false

        if success {
            dismiss()
        }
    }
}

// MARK: - Preview

#Preview {
    MultiLegStrategyDetailView(
        viewModel: MultiLegViewModel(),
        strategy: MultiLegStrategy.example
    )
}
