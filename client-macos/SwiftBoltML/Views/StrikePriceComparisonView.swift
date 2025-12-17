import SwiftUI
import Charts

struct StrikePriceComparisonView: View {
    let symbol: String
    let strike: Double
    let side: String

    @StateObject private var viewModel = StrikePriceComparisonViewModel()

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header
            headerSection

            if viewModel.isLoading {
                ProgressView("Loading strike analysis...")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if let error = viewModel.errorMessage {
                errorView(error)
            } else if let analysis = viewModel.analysis {
                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {
                        // Overall stats
                        overallStatsSection(analysis.overallStats)

                        Divider()

                        // Price history chart
                        if !analysis.priceHistory.isEmpty {
                            priceHistoryChart(analysis.priceHistory)
                            Divider()
                        }

                        // Expirations comparison
                        expirationsSection(analysis.expirations)
                    }
                    .padding()
                }
            }
        }
        .frame(minWidth: 600, minHeight: 500)
        .task {
            await viewModel.fetchAnalysis(symbol: symbol, strike: strike, side: side)
        }
    }

    // MARK: - Header

    private var headerSection: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text("\(symbol) $\(strike, specifier: "%.2f") \(side.uppercased())")
                    .font(.title2)
                    .fontWeight(.bold)

                Spacer()

                Button("Refresh") {
                    Task {
                        await viewModel.fetchAnalysis(symbol: symbol, strike: strike, side: side)
                    }
                }
            }

            if let metadata = viewModel.analysis?.metadata {
                Text("\(metadata.expirationsFound) expirations • \(metadata.hasHistoricalData ? "Has" : "No") historical data")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .padding()
    }

    // MARK: - Overall Stats

    private func overallStatsSection(_ stats: StrikeOverallStats) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Overall Statistics (Last 30 Days)")
                .font(.headline)

            HStack(spacing: 30) {
                statItem(label: "Average", value: stats.avgMark, format: "%.2f")
                statItem(label: "Min", value: stats.minMark, format: "%.2f")
                statItem(label: "Max", value: stats.maxMark, format: "%.2f")
                statItem(label: "Samples", value: Double(stats.sampleCount), format: "%.0f")
            }
        }
    }

    private func statItem(label: String, value: Double?, format: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(value.map { String(format: format, $0) } ?? "N/A")
                .font(.title3)
                .fontWeight(.semibold)
        }
    }

    // MARK: - Price History Chart

    private func priceHistoryChart(_ history: [StrikePriceHistoryPoint]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Price History")
                .font(.headline)

            Chart {
                ForEach(history.filter { $0.mark != nil }) { point in
                    if let date = point.date, let mark = point.mark {
                        LineMark(
                            x: .value("Date", date),
                            y: .value("Price", mark)
                        )
                        .foregroundStyle(.blue)

                        PointMark(
                            x: .value("Date", date),
                            y: .value("Price", mark)
                        )
                        .foregroundStyle(.blue)
                    }
                }
            }
            .frame(height: 200)
            .chartYAxisLabel("Mark Price ($)")
            .chartXAxisLabel("Date")
        }
    }

    // MARK: - Expirations Section

    private func expirationsSection(_ expirations: [StrikeExpiryData]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Price by Expiration")
                .font(.headline)

            if expirations.isEmpty {
                Text("No expiration data available")
                    .foregroundStyle(.secondary)
            } else {
                VStack(spacing: 8) {
                    ForEach(expirations) { expiry in
                        expiryRow(expiry)
                    }
                }
            }
        }
    }

    private func expiryRow(_ expiry: StrikeExpiryData) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                // Expiry date and DTE
                VStack(alignment: .leading, spacing: 2) {
                    Text(expiry.expiry)
                        .font(.system(.body, design: .monospaced))
                        .fontWeight(.medium)

                    if let dte = expiry.daysToExpiry {
                        Text("\(dte) days")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                Spacer()

                // Current price and discount indicator
                if let currentMark = expiry.currentMark {
                    VStack(alignment: .trailing, spacing: 2) {
                        Text("$\(currentMark, specifier: "%.2f")")
                            .font(.title3)
                            .fontWeight(.bold)
                            .foregroundStyle(expiry.isDiscount ? .green : .primary)

                        if let _ = expiry.avgMark, let pct = expiry.pctDiffFromAvg {
                            HStack(spacing: 4) {
                                Image(systemName: pct < 0 ? "arrow.down" : "arrow.up")
                                    .font(.caption)
                                Text(String(format: "%.1f%%", abs(pct)))
                                    .font(.caption)
                            }
                            .foregroundStyle(pct < 0 ? .green : .red)
                        }
                    }
                }
            }

            // Detailed stats row
            if expiry.avgMark != nil || expiry.currentIv != nil {
                HStack(spacing: 20) {
                    if let avgMark = expiry.avgMark {
                        detailStat(label: "Avg", value: String(format: "$%.2f", avgMark))
                    }

                    if let minMark = expiry.minMark, let maxMark = expiry.maxMark {
                        detailStat(label: "Range", value: String(format: "$%.2f - $%.2f", minMark, maxMark))
                    }

                    if let currentIv = expiry.currentIv {
                        detailStat(label: "IV", value: String(format: "%.1f%%", currentIv * 100))
                    }

                    if expiry.sampleCount > 0 {
                        detailStat(label: "Samples", value: "\(expiry.sampleCount)")
                    }
                }
                .font(.caption)
                .foregroundStyle(.secondary)
            }

            // Discount badge
            if expiry.isDiscount, let discountPct = expiry.discountPct {
                HStack(spacing: 4) {
                    Image(systemName: "tag.fill")
                        .font(.caption)
                    Text("\(discountPct, specifier: "%.1f")% Below Average")
                        .font(.caption)
                        .fontWeight(.medium)
                }
                .foregroundStyle(.white)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(Color.green.gradient)
                .clipShape(Capsule())
            }
        }
        .padding()
        .background(Color(.windowBackgroundColor).opacity(0.5))
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(expiry.isDiscount ? Color.green : Color.clear, lineWidth: 2)
        )
    }

    private func detailStat(label: String, value: String) -> some View {
        HStack(spacing: 4) {
            Text(label + ":")
            Text(value)
                .fontWeight(.medium)
        }
    }

    // MARK: - Error View

    private func errorView(_ message: String) -> some View {
        VStack(spacing: 12) {
            Image(systemName: "exclamationmark.triangle")
                .font(.largeTitle)
                .foregroundStyle(.red)

            Text("Error Loading Analysis")
                .font(.headline)

            Text(message)
                .font(.body)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)

            Button("Retry") {
                Task {
                    await viewModel.fetchAnalysis(symbol: symbol, strike: strike, side: side)
                }
            }
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

// MARK: - ViewModel

@MainActor
final class StrikePriceComparisonViewModel: ObservableObject {
    @Published var analysis: StrikeAnalysisResponse?
    @Published var isLoading = false
    @Published var errorMessage: String?

    private let apiClient = APIClient.shared

    func fetchAnalysis(symbol: String, strike: Double, side: String, lookbackDays: Int = 30) async {
        isLoading = true
        errorMessage = nil

        do {
            let queryParams = [
                "symbol": symbol,
                "strike": String(strike),
                "side": side,
                "lookbackDays": String(lookbackDays)
            ]

            analysis = try await apiClient.get(
                endpoint: "strike-analysis",
                queryParams: queryParams
            )

            print("[StrikePriceComparison] ✅ Loaded analysis for \(symbol) $\(strike) \(side)")
        } catch {
            errorMessage = error.localizedDescription
            print("[StrikePriceComparison] ❌ Error: \(error)")
        }

        isLoading = false
    }
}

// MARK: - Preview

#Preview {
    StrikePriceComparisonView(
        symbol: "AAPL",
        strike: 150.0,
        side: "call"
    )
}
