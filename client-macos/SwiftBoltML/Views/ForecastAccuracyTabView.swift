import SwiftUI

// MARK: - Forecast Accuracy Tab View

struct ForecastAccuracyTabView: View {
    @StateObject private var viewModel = ForecastAccuracyViewModel()

    var body: some View {
        VStack(spacing: 20) {
            if viewModel.isLoading && viewModel.horizonData == nil {
                ProgressView("Loading accuracy data...")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if let error = viewModel.error {
                ErrorPlaceholderView(message: error) {
                    Task { await viewModel.loadData() }
                }
            } else {
                // Horizon Accuracy Cards
                HStack(spacing: 20) {
                    HorizonAccuracyCard(
                        title: "Daily (1D)",
                        data: viewModel.horizonData?.daily,
                        icon: "clock.fill",
                        accentColor: .blue
                    )

                    HorizonAccuracyCard(
                        title: "Weekly (1W)",
                        data: viewModel.horizonData?.weekly,
                        icon: "calendar",
                        accentColor: .purple
                    )
                }
                .frame(height: 200)

                // Model Weights Section
                ModelWeightsSection(weights: viewModel.modelWeights)

                // Recent Evaluations
                RecentEvaluationsSection(evaluations: viewModel.recentEvaluations)
            }
        }
        .onAppear {
            Task { await viewModel.loadData() }
        }
    }
}

// MARK: - Forecast Accuracy ViewModel

@MainActor
class ForecastAccuracyViewModel: ObservableObject {
    @Published var horizonData: HorizonAccuracyResponse?
    @Published var modelWeights: [ModelWeightInfo] = []
    @Published var recentEvaluations: [ForecastEvaluation] = []
    @Published var isLoading = false
    @Published var error: String?

    func loadData() async {
        isLoading = true
        error = nil

        do {
            async let horizonTask = APIClient.shared.fetchHorizonAccuracy()
            async let weightsTask = APIClient.shared.fetchModelWeights()
            async let evalsTask = APIClient.shared.fetchEvaluations(limit: 20)

            let (horizon, weights, evals) = try await (horizonTask, weightsTask, evalsTask)

            horizonData = horizon
            modelWeights = weights
            recentEvaluations = evals

            print("[AccuracyVM] Loaded: horizon=\(horizon.daily != nil), weights=\(weights.count), evals=\(evals.count)")
        } catch {
            self.error = error.localizedDescription
            print("[AccuracyVM] Error: \(error)")
        }

        isLoading = false
    }
}

// MARK: - Horizon Accuracy Card

struct HorizonAccuracyCard: View {
    let title: String
    let data: HorizonAccuracyDetail?
    let icon: String
    let accentColor: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header
            HStack {
                Image(systemName: icon)
                    .font(.title2)
                    .foregroundStyle(accentColor)
                Text(title)
                    .font(.headline)
                Spacer()
            }

            if let data = data {
                // Main accuracy
                HStack(alignment: .bottom, spacing: 8) {
                    Text("\(Int(data.accuracyPct))%")
                        .font(.system(size: 48, weight: .bold, design: .rounded))
                        .foregroundStyle(accuracyColor(data.accuracyPct))

                    Text("accuracy")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .padding(.bottom, 8)
                }

                Divider()

                // Stats grid
                HStack(spacing: 16) {
                    StatItem(label: "Total", value: "\(data.totalForecasts)")
                    StatItem(label: "Correct", value: "\(data.correctForecasts ?? 0)")
                    if let avgError = data.avgErrorPct {
                        StatItem(label: "Avg Error", value: String(format: "%.1f%%", avgError))
                    }
                }

                // Direction breakdown
                if let bullish = data.bullishAccuracyPct, let bearish = data.bearishAccuracyPct {
                    HStack(spacing: 12) {
                        DirectionAccuracyBadge(direction: "Bull", accuracy: bullish, color: .green)
                        DirectionAccuracyBadge(direction: "Bear", accuracy: bearish, color: .red)
                        if let neutral = data.neutralAccuracyPct {
                            DirectionAccuracyBadge(direction: "Neut", accuracy: neutral, color: .orange)
                        }
                    }
                }
            } else {
                VStack(spacing: 12) {
                    Image(systemName: "chart.bar.xaxis")
                        .font(.system(size: 32))
                        .foregroundStyle(.secondary)
                    Text("No evaluation data yet")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    Text("Accuracy will appear after forecasts are evaluated")
                        .font(.caption)
                        .foregroundStyle(.tertiary)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }

    private func accuracyColor(_ pct: Double) -> Color {
        if pct >= 60 { return .green }
        if pct >= 45 { return .orange }
        return .red
    }
}

struct StatItem: View {
    let label: String
    let value: String

    var body: some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.system(size: 16, weight: .semibold, design: .rounded))
            Text(label)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
}

struct DirectionAccuracyBadge: View {
    let direction: String
    let accuracy: Double
    let color: Color

    var body: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
            Text("\(direction): \(Int(accuracy))%")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
}

// MARK: - Model Weights Section

struct ModelWeightsSection: View {
    let weights: [ModelWeightInfo]

    var body: some View {
        DashboardCard(
            title: "Model Weights",
            icon: "slider.horizontal.3",
            iconColor: .indigo,
            trailing: AnyView(
                Text("Auto-adjusted based on performance")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            )
        ) {
            if weights.isEmpty {
                Text("Weights will update after evaluations are recorded")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 20)
            } else {
                VStack(spacing: 16) {
                    ForEach(weights) { weight in
                        ModelWeightRow(weight: weight)
                    }
                }
                .padding(.top, 8)
            }
        }
    }
}

struct ModelWeightRow: View {
    let weight: ModelWeightInfo

    var body: some View {
        VStack(spacing: 12) {
            HStack {
                Text(weight.horizon)
                    .font(.headline)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 4)
                    .background(Color.gray.opacity(0.15))
                    .clipShape(RoundedRectangle(cornerRadius: 6))

                Spacer()

                if let reason = reasonBadge {
                    Text(reason)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 2)
                        .background(Color.gray.opacity(0.1))
                        .clipShape(Capsule())
                }
            }

            // Weight bars
            HStack(spacing: 20) {
                WeightBar(
                    label: "Random Forest",
                    shortLabel: "RF",
                    weightPct: weight.rfWeightPct,
                    accuracyPct: weight.rfAccuracy30dPct,
                    color: .blue
                )

                WeightBar(
                    label: "Gradient Boosting",
                    shortLabel: "GB",
                    weightPct: weight.gbWeightPct,
                    accuracyPct: weight.gbAccuracy30dPct,
                    color: .green
                )
            }
        }
        .padding(.vertical, 8)
    }

    private var reasonBadge: String? {
        switch weight.updateReason.lowercased() {
        case "initial": return "Default"
        case "performance_adjustment": return "Auto-tuned"
        case "manual_override": return "Manual"
        default: return nil
        }
    }
}

struct WeightBar: View {
    let label: String
    let shortLabel: String
    let weightPct: Double
    let accuracyPct: Double?
    let color: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(shortLabel)
                    .font(.caption.bold())
                    .foregroundStyle(color)
                Spacer()
                Text("\(Int(weightPct))%")
                    .font(.system(size: 18, weight: .bold, design: .rounded))
            }

            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(color.opacity(0.15))
                    RoundedRectangle(cornerRadius: 4)
                        .fill(color)
                        .frame(width: geo.size.width * (weightPct / 100))
                }
            }
            .frame(height: 12)

            if let acc = accuracyPct {
                Text("30d accuracy: \(Int(acc))%")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } else {
                Text("Evaluating...")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
            }
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - Recent Evaluations Section

struct RecentEvaluationsSection: View {
    let evaluations: [ForecastEvaluation]

    var body: some View {
        DashboardCard(
            title: "Recent Evaluations",
            icon: "checkmark.circle.fill",
            iconColor: .green,
            trailing: AnyView(
                Text("\(evaluations.count) shown")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            )
        ) {
            if evaluations.isEmpty {
                VStack(spacing: 12) {
                    Image(systemName: "clock.badge.questionmark")
                        .font(.system(size: 32))
                        .foregroundStyle(.secondary)
                    Text("No evaluations yet")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    Text("Forecasts are evaluated after their horizon period ends")
                        .font(.caption)
                        .foregroundStyle(.tertiary)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 30)
            } else {
                VStack(spacing: 0) {
                    // Header
                    EvaluationRowHeader()

                    ForEach(evaluations) { eval in
                        EvaluationRow(evaluation: eval)
                        if eval.id != evaluations.last?.id {
                            Divider()
                        }
                    }
                }
                .padding(.top, 8)
            }
        }
    }
}

struct EvaluationRowHeader: View {
    var body: some View {
        HStack(spacing: 0) {
            Text("Symbol")
                .frame(width: 70, alignment: .leading)
            Text("Horizon")
                .frame(width: 60, alignment: .center)
            Text("Predicted")
                .frame(width: 80, alignment: .center)
            Text("Actual")
                .frame(width: 80, alignment: .center)
            Text("Result")
                .frame(width: 70, alignment: .center)
            Spacer()
            Text("Error")
                .frame(width: 60, alignment: .trailing)
        }
        .font(.caption.bold())
        .foregroundStyle(.secondary)
        .padding(.vertical, 8)
        .padding(.horizontal, 12)
        .background(Color.gray.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 6))
    }
}

struct EvaluationRow: View {
    let evaluation: ForecastEvaluation

    var body: some View {
        HStack(spacing: 0) {
            Text(evaluation.symbol)
                .font(.system(size: 13, weight: .semibold, design: .rounded))
                .frame(width: 70, alignment: .leading)

            Text(evaluation.horizon)
                .font(.caption)
                .foregroundStyle(.secondary)
                .frame(width: 60, alignment: .center)

            // Predicted
            Text(evaluation.predictedLabel.capitalized)
                .font(.caption.bold())
                .foregroundStyle(.white)
                .padding(.horizontal, 8)
                .padding(.vertical, 2)
                .background(predictionColor)
                .clipShape(Capsule())
                .frame(width: 80, alignment: .center)

            // Actual
            Text(evaluation.realizedLabel.capitalized)
                .font(.caption.bold())
                .foregroundStyle(.white)
                .padding(.horizontal, 8)
                .padding(.vertical, 2)
                .background(actualColor)
                .clipShape(Capsule())
                .frame(width: 80, alignment: .center)

            // Result
            HStack(spacing: 4) {
                Image(systemName: evaluation.directionCorrect ? "checkmark.circle.fill" : "xmark.circle.fill")
                    .foregroundStyle(evaluation.directionCorrect ? .green : .red)
                Text(evaluation.directionCorrect ? "Correct" : "Wrong")
                    .font(.caption)
            }
            .frame(width: 70, alignment: .center)

            Spacer()

            // Error
            Text(String(format: "%.1f%%", evaluation.priceErrorPct * 100))
                .font(.system(size: 12, weight: .medium, design: .rounded))
                .foregroundStyle(.secondary)
                .frame(width: 60, alignment: .trailing)
        }
        .padding(.vertical, 10)
        .padding(.horizontal, 12)
    }

    private var predictionColor: Color {
        switch evaluation.predictedLabel.lowercased() {
        case "bullish": return .green
        case "bearish": return .red
        default: return .orange
        }
    }

    private var actualColor: Color {
        switch evaluation.realizedLabel.lowercased() {
        case "bullish": return .green
        case "bearish": return .red
        default: return .orange
        }
    }
}

// MARK: - Error Placeholder

struct ErrorPlaceholderView: View {
    let message: String
    let retryAction: () -> Void

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 48))
                .foregroundStyle(.orange)
            Text("Failed to load accuracy data")
                .font(.title3.bold())
            Text(message)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
            Button("Try Again", action: retryAction)
                .buttonStyle(.bordered)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

// MARK: - Preview

#Preview {
    ForecastAccuracyTabView()
        .frame(width: 800, height: 700)
        .padding()
}
