import SwiftUI
import Charts

/// View displaying historical mark price chart for a specific option contract
struct OptionHistoryChartView: View {
    let symbol: String
    let strike: Double
    let side: String
    let expiry: String?
    let contractSymbol: String?
    
    @StateObject private var viewModel = OptionHistoryChartViewModel()
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        VStack(spacing: 0) {
            // Header
            headerSection
            
            Divider()
            
            // Content
            if viewModel.isLoading {
                loadingView
            } else if let error = viewModel.errorMessage {
                errorView(error)
            } else if viewModel.priceHistory.isEmpty {
                emptyView
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {
                        // Stats summary
                        statsSection
                        
                        // Main price chart
                        priceChartSection
                        
                        // IV chart (if available)
                        if viewModel.hasIVData {
                            ivChartSection
                        }
                    }
                    .padding()
                }
            }
        }
        .frame(minWidth: 500, minHeight: 400)
        .task {
            await viewModel.fetchHistory(
                symbol: symbol,
                strike: strike,
                side: side,
                lookbackDays: 60
            )
        }
    }
    
    // MARK: - Header
    
    private var headerSection: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 8) {
                    Text(symbol)
                        .font(.title2.bold())
                    
                    Text("$\(strike, specifier: "%.2f")")
                        .font(.title3)
                    
                    Text(side.uppercased())
                        .font(.caption.bold())
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(side == "call" ? Color.green.opacity(0.2) : Color.red.opacity(0.2))
                        .foregroundStyle(side == "call" ? .green : .red)
                        .clipShape(RoundedRectangle(cornerRadius: 4))
                }
                
                if let expiry = expiry {
                    Text("Expires: \(formatExpiry(expiry))")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            
            Spacer()
            
            // Refresh button
            Button {
                Task {
                    await viewModel.fetchHistory(
                        symbol: symbol,
                        strike: strike,
                        side: side,
                        lookbackDays: 60
                    )
                }
            } label: {
                Image(systemName: "arrow.clockwise")
            }
            .buttonStyle(.borderless)
            .help("Refresh data")
            
            // Close button
            Button {
                dismiss()
            } label: {
                Image(systemName: "xmark.circle.fill")
                    .foregroundStyle(.secondary)
            }
            .buttonStyle(.borderless)
        }
        .padding()
    }
    
    // MARK: - Stats Section
    
    private var statsSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Price Statistics (Last 60 Days)")
                .font(.headline)
            
            HStack(spacing: 24) {
                statItem(
                    label: "Current",
                    value: viewModel.currentMark,
                    format: "$%.2f",
                    color: .primary
                )
                
                statItem(
                    label: "Average",
                    value: viewModel.avgMark,
                    format: "$%.2f",
                    color: .blue
                )
                
                statItem(
                    label: "Low",
                    value: viewModel.minMark,
                    format: "$%.2f",
                    color: .red
                )
                
                statItem(
                    label: "High",
                    value: viewModel.maxMark,
                    format: "$%.2f",
                    color: .green
                )
                
                if let change = viewModel.priceChange {
                    statItem(
                        label: "Change",
                        value: change,
                        format: "%+.1f%%",
                        color: change >= 0 ? .green : .red
                    )
                }
                
                Spacer()
                
                Text("\(viewModel.priceHistory.count) data points")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
            }
        }
        .padding()
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
    
    private func statItem(label: String, value: Double?, format: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.caption)
                .foregroundStyle(.secondary)
            
            if let value = value {
                Text(String(format: format, value))
                    .font(.title3.bold())
                    .foregroundStyle(color)
            } else {
                Text("N/A")
                    .font(.title3)
                    .foregroundStyle(.tertiary)
            }
        }
    }
    
    // MARK: - Price Chart
    
    private var priceChartSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Mark Price History")
                .font(.headline)
            
            Chart {
                // Price line
                ForEach(viewModel.priceHistory) { point in
                    if let mark = point.mark {
                        LineMark(
                            x: .value("Date", point.date),
                            y: .value("Price", mark)
                        )
                        .foregroundStyle(side == "call" ? Color.green : Color.red)
                        .lineStyle(StrokeStyle(lineWidth: 2))
                        .interpolationMethod(.catmullRom)
                    }
                }
                
                // Area fill
                ForEach(viewModel.priceHistory) { point in
                    if let mark = point.mark {
                        AreaMark(
                            x: .value("Date", point.date),
                            y: .value("Price", mark)
                        )
                        .foregroundStyle(
                            LinearGradient(
                                colors: [
                                    (side == "call" ? Color.green : Color.red).opacity(0.3),
                                    (side == "call" ? Color.green : Color.red).opacity(0.05)
                                ],
                                startPoint: .top,
                                endPoint: .bottom
                            )
                        )
                        .interpolationMethod(.catmullRom)
                    }
                }
                
                // Average line
                if let avg = viewModel.avgMark {
                    RuleMark(y: .value("Average", avg))
                        .foregroundStyle(.blue.opacity(0.5))
                        .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))
                        .annotation(position: .top, alignment: .trailing) {
                            Text("Avg: $\(avg, specifier: "%.2f")")
                                .font(.caption2)
                                .foregroundStyle(.blue)
                        }
                }
            }
            .frame(height: 250)
            .chartYAxisLabel("Mark Price ($)")
            .chartXAxis {
                AxisMarks(values: .automatic(desiredCount: 6)) { value in
                    AxisGridLine()
                    AxisValueLabel(format: .dateTime.month(.abbreviated).day())
                }
            }
        }
        .padding()
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
    
    // MARK: - IV Chart
    
    private var ivChartSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Implied Volatility History")
                .font(.headline)
            
            Chart {
                ForEach(viewModel.priceHistory) { point in
                    if let iv = point.impliedVol {
                        LineMark(
                            x: .value("Date", point.date),
                            y: .value("IV", iv * 100)
                        )
                        .foregroundStyle(.purple)
                        .lineStyle(StrokeStyle(lineWidth: 2))
                        .interpolationMethod(.catmullRom)
                    }
                }
                
                ForEach(viewModel.priceHistory) { point in
                    if let iv = point.impliedVol {
                        AreaMark(
                            x: .value("Date", point.date),
                            y: .value("IV", iv * 100)
                        )
                        .foregroundStyle(
                            LinearGradient(
                                colors: [Color.purple.opacity(0.3), Color.purple.opacity(0.05)],
                                startPoint: .top,
                                endPoint: .bottom
                            )
                        )
                        .interpolationMethod(.catmullRom)
                    }
                }
            }
            .frame(height: 150)
            .chartYAxisLabel("IV (%)")
            .chartXAxis {
                AxisMarks(values: .automatic(desiredCount: 6)) { value in
                    AxisGridLine()
                    AxisValueLabel(format: .dateTime.month(.abbreviated).day())
                }
            }
        }
        .padding()
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
    
    // MARK: - Loading/Error/Empty Views
    
    private var loadingView: some View {
        VStack(spacing: 12) {
            ProgressView()
            Text("Loading price history...")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
    
    private func errorView(_ message: String) -> some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 48))
                .foregroundStyle(.orange)
            
            Text("Failed to load history")
                .font(.headline)
            
            Text(message)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
            
            Button("Retry") {
                Task {
                    await viewModel.fetchHistory(
                        symbol: symbol,
                        strike: strike,
                        side: side,
                        lookbackDays: 60
                    )
                }
            }
            .buttonStyle(.borderedProminent)
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
    
    private var emptyView: some View {
        VStack(spacing: 16) {
            Image(systemName: "chart.line.downtrend.xyaxis")
                .font(.system(size: 48))
                .foregroundStyle(.secondary)
            
            Text("No Historical Data")
                .font(.headline)
            
            Text("No price history available for this option contract yet.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
    
    // MARK: - Helpers
    
    private func formatExpiry(_ expiry: String) -> String {
        guard let date = ISO8601DateFormatter().date(from: expiry) else {
            return expiry
        }
        let formatter = DateFormatter()
        formatter.dateFormat = "MMM d, yyyy"
        return formatter.string(from: date)
    }
}

// MARK: - Data Point Model

struct OptionPricePoint: Identifiable {
    let id = UUID()
    let date: Date
    let mark: Double?
    let impliedVol: Double?
}

// MARK: - ViewModel

@MainActor
final class OptionHistoryChartViewModel: ObservableObject {
    @Published var priceHistory: [OptionPricePoint] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    private let apiClient = APIClient.shared
    
    // Computed stats
    var currentMark: Double? {
        priceHistory.last?.mark
    }
    
    var avgMark: Double? {
        let marks = priceHistory.compactMap { $0.mark }
        guard !marks.isEmpty else { return nil }
        return marks.reduce(0, +) / Double(marks.count)
    }
    
    var minMark: Double? {
        priceHistory.compactMap { $0.mark }.min()
    }
    
    var maxMark: Double? {
        priceHistory.compactMap { $0.mark }.max()
    }
    
    var priceChange: Double? {
        guard let first = priceHistory.first?.mark,
              let last = priceHistory.last?.mark,
              first > 0 else { return nil }
        return ((last - first) / first) * 100
    }
    
    var hasIVData: Bool {
        priceHistory.contains { $0.impliedVol != nil }
    }
    
    func fetchHistory(symbol: String, strike: Double, side: String, lookbackDays: Int) async {
        isLoading = true
        errorMessage = nil
        
        do {
            let response: StrikeAnalysisResponse = try await apiClient.fetchStrikeAnalysis(
                symbol: symbol,
                strike: strike,
                side: side,
                lookbackDays: lookbackDays
            )
            
            // Convert response to price points
            priceHistory = response.priceHistory.compactMap { point -> OptionPricePoint? in
                guard let date = point.date else { return nil }
                return OptionPricePoint(
                    date: date,
                    mark: point.mark,
                    impliedVol: point.impliedVol
                )
            }.sorted { $0.date < $1.date }
            
            print("[OptionHistoryChart] ✅ Loaded \(priceHistory.count) price points for \(symbol) $\(strike) \(side)")
            
        } catch {
            errorMessage = error.localizedDescription
            print("[OptionHistoryChart] ❌ Error: \(error)")
        }
        
        isLoading = false
    }
}

// MARK: - Preview

#Preview {
    OptionHistoryChartView(
        symbol: "AMZN",
        strike: 160.0,
        side: "put",
        expiry: "2025-01-17",
        contractSymbol: "AMZN250117P00160000"
    )
}
