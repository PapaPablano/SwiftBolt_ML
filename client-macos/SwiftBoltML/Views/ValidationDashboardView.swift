import SwiftUI

struct ValidationDashboardView: View {
    @ObservedObject var viewModel: ValidationViewModel
    @State private var showSettings = false

    private var symbolTitle: String {
        viewModel.symbol ?? "No Symbol Selected"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            header

            if viewModel.isLoading && viewModel.validator == nil {
                loadingState
            } else if let error = viewModel.error, viewModel.validator == nil {
                errorState(error)
            } else if let validator = viewModel.validator {
                dashboardContent(validator)
            } else {
                emptyState
            }
        }
        .padding(24)
        .background(Color(nsColor: .windowBackgroundColor))
        .sheet(isPresented: $showSettings) {
            ValidationSettingsView(viewModel: viewModel)
        }
    }

    private var header: some View {
        HStack(spacing: 16) {
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 10) {
                    Text("Unified Validation")
                        .font(.title.bold())
                    if viewModel.isOffline {
                        Label("Offline", systemImage: "bolt.horizontal.circle")
                            .font(.subheadline)
                            .foregroundStyle(.orange)
                    }
                }
                Text(symbolTitle)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                if let lastSync = viewModel.lastSyncTime {
                    Text("Last sync: \(lastSync.formatted(.dateTime.hour().minute()))")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()

            Button {
                viewModel.manualRefresh()
            } label: {
                Label("Refresh", systemImage: "arrow.clockwise")
            }
            .buttonStyle(.bordered)
            .disabled(viewModel.isLoading || viewModel.symbol == nil)

            Button {
                showSettings = true
            } label: {
                Label("Weights", systemImage: "slider.horizontal.3")
            }
            .buttonStyle(.borderedProminent)
            .disabled(viewModel.symbol == nil)
        }
    }

    private var loadingState: some View {
        VStack(spacing: 16) {
            Spacer()
            ProgressView("Loading validation metrics...")
            Spacer()
        }
        .frame(maxWidth: .infinity)
    }

    private func errorState(_ message: String) -> some View {
        VStack(spacing: 16) {
            Spacer()
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 42))
                .foregroundStyle(.orange)
            Text("Unable to fetch validation")
                .font(.headline)
            Text(message)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
            Button("Retry") {
                viewModel.manualRefresh()
            }
            .buttonStyle(.bordered)
            Spacer()
        }
        .frame(maxWidth: .infinity)
    }

    private var emptyState: some View {
        VStack(spacing: 16) {
            Spacer()
            Image(systemName: "chart.line.uptrend.xyaxis")
                .font(.system(size: 42))
                .foregroundStyle(.secondary)
            Text("Select a symbol to view validation")
                .font(.headline)
                .foregroundStyle(.secondary)
            Spacer()
        }
        .frame(maxWidth: .infinity)
    }

    private func dashboardContent(_ validator: UnifiedValidator) -> some View {
        VStack(spacing: 20) {
            HStack(spacing: 20) {
                ConfidenceCard(confidence: validator.confidence, drift: validator.hasDrift)
                ScoreBreakdownCard(validator: validator)
                ConsensusCard(validator: validator, weights: viewModel.weights)
            }
            .frame(height: 180)

            MultiTimeframeView(validator: validator)

            if let note = statusNote(for: validator) {
                Label(note, systemImage: "info.circle")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .padding(.top, 4)
            }
        }
    }

    private func statusNote(for validator: UnifiedValidator) -> String? {
        if viewModel.isOffline {
            if Date().timeIntervalSince(validator.timestamp) > 600 {
                return "Showing cached data (older than 10 minutes)."
            }
            return "Offline: displaying cached metrics."
        }
        return nil
    }
}

// MARK: - Card Components

private struct ConfidenceCard: View {
    let confidence: Double
    let drift: Bool

    private var confidenceColor: Color {
        switch confidence {
        case ..<0.4: return .red
        case ..<0.7: return .orange
        default: return .green
        }
    }

    var body: some View {
        DashboardCard(title: "Confidence", icon: "gauge", iconColor: confidenceColor) {
            VStack(alignment: .leading, spacing: 16) {
                Gauge(value: confidence, in: 0...1) {
                    Text("Confidence")
                } currentValueLabel: {
                    Text("\(Int(confidence * 100))%")
                        .font(.title3.bold())
                }
                .tint(confidenceColor)
                .gaugeStyle(.accessoryCircular)
                .scaleEffect(1.1)

                HStack(spacing: 12) {
                    Label("Composite Score", systemImage: "target")
                        .foregroundStyle(.secondary)
                    Spacer()
                    Text(confidence, format: .number.precision(.fractionLength(2)))
                        .font(.title3.bold())
                }

                HStack {
                    Image(systemName: drift ? "exclamationmark.triangle" : "checkmark.circle")
                        .foregroundStyle(drift ? Color.orange : Color.green)
                    Text(drift ? "Live performance deviates from backtest" : "Within drift threshold")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }
            .padding(.vertical, 4)
        }
    }
}

private struct ScoreBreakdownCard: View {
    let validator: UnifiedValidator

    var body: some View {
        DashboardCard(title: "Score Breakdown", icon: "slider.horizontal.3", iconColor: .blue) {
            VStack(spacing: 12) {
                ScoreRow(label: "Backtest", value: validator.backtestScore, weight: validator.weights.backtest)
                Divider()
                ScoreRow(label: "Walkforward", value: validator.walkforwardScore, weight: validator.weights.walkforward)
                Divider()
                ScoreRow(label: "Live", value: validator.liveScore, weight: validator.weights.live)
            }
        }
    }
}

private struct ScoreRow: View {
    let label: String
    let value: Double
    let weight: Double

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(label)
                    .font(.headline)
                Text("Weight: \(Int(weight * 100))%")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 4) {
                Text(value, format: .number.precision(.fractionLength(3)))
                    .font(.title3.bold())
                ProgressView(value: value)
                    .tint(color(for: value))
                    .frame(width: 140)
            }
        }
    }

    private func color(for score: Double) -> Color {
        switch score {
        case ..<0.4: return .red
        case ..<0.7: return .orange
        default: return .green
        }
    }
}

private struct ConsensusCard: View {
    let validator: UnifiedValidator
    let weights: ValidationWeights

    var body: some View {
        DashboardCard(title: "Consensus", icon: "person.3.sequence", iconColor: .purple) {
            VStack(alignment: .leading, spacing: 12) {
                Text(validator.timeframeConsensus.rawValue.capitalized)
                    .font(.largeTitle.bold())
                    .foregroundStyle(color(for: validator.timeframeConsensus))
                Text("Timeframe weighting: \(weights.timeframeWeight.label)")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                HStack(spacing: 8) {
                    SignalBadge(label: "M15", signal: validator.m15Signal)
                    SignalBadge(label: "H1", signal: validator.h1Signal)
                    SignalBadge(label: "D1", signal: validator.d1Signal)
                }
            }
        }
    }

    private func color(for signal: Signal) -> Color {
        switch signal {
        case .bullish: return .green
        case .bearish: return .red
        case .neutral: return .orange
        }
    }
}

private struct SignalBadge: View {
    let label: String
    let signal: Signal

    private var color: Color {
        switch signal {
        case .bullish: return .green
        case .bearish: return .red
        case .neutral: return .orange
        }
    }

    var body: some View {
        VStack(spacing: 4) {
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
            Text(signal.rawValue.capitalized)
                .font(.subheadline.bold())
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(color.opacity(0.12))
                .clipShape(Capsule())
                .foregroundStyle(color)
        }
    }
}

private struct MultiTimeframeView: View {
    let validator: UnifiedValidator

    var body: some View {
        DashboardCard(title: "Multi-Timeframe Signals", icon: "clock.arrow.circlepath", iconColor: .teal) {
            HStack(spacing: 16) {
                timeframeStack(label: "M15", signal: validator.m15Signal, score: validator.liveScore)
                timeframeStack(label: "H1", signal: validator.h1Signal, score: validator.walkforwardScore)
                timeframeStack(label: "D1", signal: validator.d1Signal, score: validator.backtestScore)
            }
        }
    }

    private func timeframeStack(label: String, signal: Signal, score: Double) -> some View {
        VStack(spacing: 8) {
            Text(label)
                .font(.headline)
            Text(signal.rawValue.capitalized)
                .font(.subheadline.bold())
                .foregroundStyle(color(for: signal))
            Text(score, format: .number.precision(.fractionLength(3)))
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
    }

    private func color(for signal: Signal) -> Color {
        switch signal {
        case .bullish: return .green
        case .bearish: return .red
        case .neutral: return .orange
        }
    }
}

// MARK: - Settings View

struct ValidationSettingsView: View {
    @ObservedObject var viewModel: ValidationViewModel
    @Environment(\.dismiss) private var dismiss
    @State private var draftWeights: ValidationWeights

    init(viewModel: ValidationViewModel) {
        self.viewModel = viewModel
        _draftWeights = State(initialValue: viewModel.weights)
    }

    var body: some View {
        NavigationView {
            Form {
                Section(header: Text("Weight Allocation")) {
                    weightSlider(title: "Backtest", value: $draftWeights.backtest)
                    weightSlider(title: "Walkforward", value: $draftWeights.walkforward)
                    weightSlider(title: "Live", value: $draftWeights.live)
                    Text("Total: \(Int(totalWeight * 100))%")
                        .font(.caption)
                        .foregroundStyle(totalWeight.approxEquals(1) ? .secondary : .orange)
                }

                Section(header: Text("Timeframe Consensus")) {
                    Picker("Preference", selection: $draftWeights.timeframeWeight) {
                        ForEach(ValidationWeights.TimeframeWeight.allCases) { option in
                            Text(option.label).tag(option)
                        }
                    }
                    .pickerStyle(.segmented)
                }

                Section(header: Text("Anomaly Detection")) {
                    Slider(value: $draftWeights.driftThreshold, in: 0.05...0.30, step: 0.01) {
                        Text("Drift Threshold")
                    }
                    Text("Alert when live diverges by more than \(Int(draftWeights.driftThreshold * 100))%")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .formStyle(.grouped)
            .navigationTitle("Validation Settings")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        saveWeights()
                        dismiss()
                    }
                }
            }
        }
        .frame(minWidth: 480, minHeight: 420)
    }

    private var totalWeight: Double {
        draftWeights.backtest + draftWeights.walkforward + draftWeights.live
    }

    private func weightSlider(title: String, value: Binding<Double>) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(title)
                    .font(.headline)
                Spacer()
                Text("\(Int(value.wrappedValue * 100))%")
                    .font(.subheadline)
            }
            Slider(value: value, in: 0...1, step: 0.05)
        }
    }

    private func saveWeights() {
        var normalized = draftWeights
        let total = max(totalWeight, 0.01)
        normalized.backtest = (normalized.backtest / total).clamped()
        normalized.walkforward = (normalized.walkforward / total).clamped()
        normalized.live = max(0, 1 - normalized.backtest - normalized.walkforward)
        viewModel.weights = normalized
    }
}

private extension Double {
    func approxEquals(_ other: Double, tolerance: Double = 0.02) -> Bool {
        abs(self - other) <= tolerance
    }

    func clamped() -> Double {
        min(max(self, 0), 1)
    }
}
