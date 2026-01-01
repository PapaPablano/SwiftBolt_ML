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
    @State private var timeframe: Timeframe = .all
    @Environment(\.dismiss) private var dismiss

    private struct TradingDayPoint: Identifiable {
        let date: Date
        let mark: Double?
        let impliedVol: Double?

        var id: Date { date }
    }
    
    private enum Timeframe: String, CaseIterable, Identifiable {
        case all = "All"
        case days90 = "90d"
        case days30 = "30d"
        case days5 = "5d"
        
        var id: String { rawValue }
        
        var lookbackDays: Int {
            switch self {
            case .all:
                return 3650
            case .days90:
                return 90
            case .days30:
                return 30
            case .days5:
                return 5
            }
        }
        
        var statsTitle: String {
            switch self {
            case .all:
                return "Price Statistics (All Time)"
            case .days90:
                return "Price Statistics (Last 90 Days)"
            case .days30:
                return "Price Statistics (Last 30 Days)"
            case .days5:
                return "Price Statistics (Last 5 Days)"
            }
        }
    }
    
    private var displayedHistory: [OptionPricePoint] {
        switch timeframe {
        case .all:
            return viewModel.priceHistory
        default:
            let start = Calendar.current.date(
                byAdding: .day,
                value: -timeframe.lookbackDays,
                to: Date()
            ) ?? Date()
            return viewModel.priceHistory.filter { $0.date >= start }
        }
    }
    
    private var chartDomain: ClosedRange<Date> {
        switch timeframe {
        case .all:
            let start = displayedHistory.first?.date ?? Date()
            let end = displayedHistory.last?.date ?? Date()
            return start...end
        default:
            let start = Calendar.current.date(
                byAdding: .day,
                value: -timeframe.lookbackDays,
                to: Date()
            ) ?? Date()
            return start...Date()
        }
    }

    private var usesTradingDayAxis: Bool {
        switch timeframe {
        case .days30, .days90:
            return true
        default:
            return false
        }
    }

    private func buildTradingDayHistory() -> [TradingDayPoint] {
        let calendar = Calendar.current
        let start = calendar.startOfDay(for: chartDomain.lowerBound)
        let end = calendar.startOfDay(for: chartDomain.upperBound)

        var latestByDay: [Date: OptionPricePoint] = [:]
        for point in displayedHistory {
            let day = calendar.startOfDay(for: point.date)
            if let existing = latestByDay[day] {
                if point.date > existing.date {
                    latestByDay[day] = point
                }
            } else {
                latestByDay[day] = point
            }
        }

        var cursor = start
        var results: [TradingDayPoint] = []
        while cursor <= end {
            let weekday = calendar.component(.weekday, from: cursor)
            let isWeekend = weekday == 1 || weekday == 7
            if !isWeekend {
                if let point = latestByDay[cursor] {
                    results.append(
                        TradingDayPoint(
                            date: cursor,
                            mark: point.mark,
                            impliedVol: point.impliedVol
                        )
                    )
                } else {
                    results.append(
                        TradingDayPoint(
                            date: cursor,
                            mark: nil,
                            impliedVol: nil
                        )
                    )
                }
            }

            cursor = calendar.date(byAdding: .day, value: 1, to: cursor) ?? cursor.addingTimeInterval(86400)
        }

        return results
    }

    private var tradingDayHistory: [TradingDayPoint] {
        guard usesTradingDayAxis else { return [] }
        return buildTradingDayHistory()
    }

    private var tradingDayXDomain: ClosedRange<Int> {
        let count = tradingDayHistory.count
        if count <= 1 {
            return 0...1
        }
        return 0...(count - 1)
    }

    private var statsMarks: [Double] {
        if usesTradingDayAxis {
            return tradingDayHistory.compactMap { $0.mark }
        }
        return displayedHistory.compactMap { $0.mark }
    }

    private var statsFirstMark: Double? {
        if usesTradingDayAxis {
            return tradingDayHistory.compactMap { $0.mark }.first
        }
        return displayedHistory.first?.mark
    }

    private var statsLastMark: Double? {
        if usesTradingDayAxis {
            return tradingDayHistory.compactMap { $0.mark }.last
        }
        return displayedHistory.last?.mark
    }

    private var statsCountLabel: String {
        if usesTradingDayAxis {
            return "\(tradingDayHistory.count) trading days"
        }
        return "\(displayedHistory.count) data points"
    }
    
    private func paddedDomain(
        minValue: Double,
        maxValue: Double
    ) -> ClosedRange<Double> {
        if minValue == maxValue {
            let pad = Swift.max(0.01, abs(minValue) * 0.05)
            return (minValue - pad)...(maxValue + pad)
        }
        let range = maxValue - minValue
        let pad = Swift.max(0.01, range * 0.05)
        return (minValue - pad)...(maxValue + pad)
    }
    
    private var priceYDomain: ClosedRange<Double>? {
        guard let minV = statsMarks.min(), let maxV = statsMarks.max() else { return nil }
        return paddedDomain(minValue: minV, maxValue: maxV)
    }
    
    private var ivSeriesPct: [Double] {
        if usesTradingDayAxis {
            return tradingDayHistory.compactMap { point in
                guard let iv = point.impliedVol else { return nil }
                return iv <= 3 ? iv * 100 : iv
            }
        }

        return displayedHistory.compactMap { point in
            guard let iv = point.impliedVol else { return nil }
            return iv <= 3 ? iv * 100 : iv
        }
    }
    
    private var ivYDomain: ClosedRange<Double>? {
        guard let minV = ivSeriesPct.min(), let maxV = ivSeriesPct.max() else {
            return nil
        }
        return paddedDomain(minValue: minV, maxValue: maxV)
    }
    
    private var xAxisLabelFormat: Date.FormatStyle {
        switch timeframe {
        case .days5:
            return .dateTime.weekday(.abbreviated).hour(
                .defaultDigits(amPM: .abbreviated)
            )
        default:
            return .dateTime.month(.abbreviated).day()
        }
    }
    
    private var currentMark: Double? {
        statsLastMark
    }

    private var avgMark: Double? {
        guard !statsMarks.isEmpty else { return nil }
        return statsMarks.reduce(0, +) / Double(statsMarks.count)
    }

    private var minMark: Double? {
        statsMarks.min()
    }

    private var maxMark: Double? {
        statsMarks.max()
    }

    private var priceChange: Double? {
        guard let first = statsFirstMark,
              let last = statsLastMark,
              first > 0 else { return nil }
        return ((last - first) / first) * 100
    }

    private var hasIVData: Bool {
        if usesTradingDayAxis {
            return tradingDayHistory.contains { $0.impliedVol != nil }
        }
        return displayedHistory.contains { $0.impliedVol != nil }
    }
    
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
            } else if displayedHistory.isEmpty {
                emptyView
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {
                        // Stats summary
                        statsSection
                        
                        // Main price chart
                        priceChartSection
                        
                        // IV chart (if available)
                        if hasIVData {
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
                lookbackDays: timeframe.lookbackDays
            )
        }
        .onChange(of: timeframe) { _, newValue in
            Task {
                await viewModel.fetchHistory(
                    symbol: symbol,
                    strike: strike,
                    side: side,
                    lookbackDays: newValue.lookbackDays
                )
            }
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
            
            Picker("Timeframe", selection: $timeframe) {
                ForEach(Timeframe.allCases) { tf in
                    Text(tf.rawValue).tag(tf)
                }
            }
            .pickerStyle(.segmented)
            .frame(width: 220)
            
            // Refresh button
            Button {
                Task {
                    await viewModel.fetchHistory(
                        symbol: symbol,
                        strike: strike,
                        side: side,
                        lookbackDays: timeframe.lookbackDays
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
            Text(timeframe.statsTitle)
                .font(.headline)
            
            HStack(spacing: 24) {
                statItem(
                    label: "Current",
                    value: currentMark,
                    format: "$%.2f",
                    color: .primary
                )
                
                statItem(
                    label: "Average",
                    value: avgMark,
                    format: "$%.2f",
                    color: .blue
                )
                
                statItem(
                    label: "Low",
                    value: minMark,
                    format: "$%.2f",
                    color: .red
                )
                
                statItem(
                    label: "High",
                    value: maxMark,
                    format: "$%.2f",
                    color: .green
                )
                
                if let change = priceChange {
                    statItem(
                        label: "Change",
                        value: change,
                        format: "%+.1f%%",
                        color: change >= 0 ? .green : .red
                    )
                }
                
                Spacer()
                
                Text(statsCountLabel)
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
            
            let baseChart = Chart {
                if usesTradingDayAxis {
                    ForEach(Array(tradingDayHistory.enumerated()), id: \.element.id) { idx, point in
                        if let mark = point.mark {
                            LineMark(
                                x: .value("Day", idx),
                                y: .value("Price", mark)
                            )
                            .foregroundStyle(side == "call" ? Color.green : Color.red)
                            .lineStyle(StrokeStyle(lineWidth: 2))
                            .interpolationMethod(.catmullRom)
                        }
                    }

                    ForEach(Array(tradingDayHistory.enumerated()), id: \.element.id) { idx, point in
                        if let mark = point.mark {
                            AreaMark(
                                x: .value("Day", idx),
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
                } else {
                    // Price line
                    ForEach(displayedHistory) { point in
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
                    ForEach(displayedHistory) { point in
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
                }

                // Average line
                if let avg = avgMark {
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

            if let yDomain = priceYDomain {
                if usesTradingDayAxis {
                    baseChart
                        .chartXScale(domain: tradingDayXDomain)
                        .chartYScale(domain: yDomain)
                        .chartXAxis {
                            AxisMarks(values: .automatic(desiredCount: 6)) { value in
                                AxisGridLine()
                                AxisValueLabel {
                                    if let idx = value.as(Int.self),
                                       idx >= 0,
                                       idx < tradingDayHistory.count {
                                        Text(tradingDayHistory[idx].date, format: .dateTime.month(.abbreviated).day())
                                    }
                                }
                            }
                        }
                } else {
                    baseChart
                        .chartXScale(domain: chartDomain)
                        .chartYScale(domain: yDomain)
                        .chartXAxis {
                            AxisMarks(values: .automatic(desiredCount: 6)) { value in
                                AxisGridLine()
                                AxisValueLabel(format: xAxisLabelFormat)
                            }
                        }
                }
            } else {
                if usesTradingDayAxis {
                    baseChart
                        .chartXScale(domain: tradingDayXDomain)
                        .chartXAxis {
                            AxisMarks(values: .automatic(desiredCount: 6)) { value in
                                AxisGridLine()
                                AxisValueLabel {
                                    if let idx = value.as(Int.self),
                                       idx >= 0,
                                       idx < tradingDayHistory.count {
                                        Text(tradingDayHistory[idx].date, format: .dateTime.month(.abbreviated).day())
                                    }
                                }
                            }
                        }
                } else {
                    baseChart
                        .chartXScale(domain: chartDomain)
                        .chartXAxis {
                            AxisMarks(values: .automatic(desiredCount: 6)) { value in
                                AxisGridLine()
                                AxisValueLabel(format: xAxisLabelFormat)
                            }
                        }
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
            
            let baseChart = Chart {
                if usesTradingDayAxis {
                    ForEach(Array(tradingDayHistory.enumerated()), id: \.element.id) { idx, point in
                        if let iv = point.impliedVol {
                            LineMark(
                                x: .value("Day", idx),
                                y: .value("IV", iv <= 3 ? iv * 100 : iv)
                            )
                            .foregroundStyle(.purple)
                            .lineStyle(StrokeStyle(lineWidth: 2))
                            .interpolationMethod(.catmullRom)
                        }
                    }

                    ForEach(Array(tradingDayHistory.enumerated()), id: \.element.id) { idx, point in
                        if let iv = point.impliedVol {
                            AreaMark(
                                x: .value("Day", idx),
                                y: .value("IV", iv <= 3 ? iv * 100 : iv)
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
                } else {
                    ForEach(displayedHistory) { point in
                        if let iv = point.impliedVol {
                            LineMark(
                                x: .value("Date", point.date),
                                y: .value("IV", iv <= 3 ? iv * 100 : iv)
                            )
                            .foregroundStyle(.purple)
                            .lineStyle(StrokeStyle(lineWidth: 2))
                            .interpolationMethod(.catmullRom)
                        }
                    }
                    
                    ForEach(displayedHistory) { point in
                        if let iv = point.impliedVol {
                            AreaMark(
                                x: .value("Date", point.date),
                                y: .value("IV", iv <= 3 ? iv * 100 : iv)
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
            }
            .frame(height: 150)
            .chartYAxisLabel("IV (%)")

            if let yDomain = ivYDomain {
                if usesTradingDayAxis {
                    baseChart
                        .chartXScale(domain: tradingDayXDomain)
                        .chartYScale(domain: yDomain)
                        .chartXAxis {
                            AxisMarks(values: .automatic(desiredCount: 6)) { value in
                                AxisGridLine()
                                AxisValueLabel {
                                    if let idx = value.as(Int.self),
                                       idx >= 0,
                                       idx < tradingDayHistory.count {
                                        Text(tradingDayHistory[idx].date, format: .dateTime.month(.abbreviated).day())
                                    }
                                }
                            }
                        }
                } else {
                    baseChart
                        .chartXScale(domain: chartDomain)
                        .chartYScale(domain: yDomain)
                        .chartXAxis {
                            AxisMarks(values: .automatic(desiredCount: 6)) { value in
                                AxisGridLine()
                                AxisValueLabel(format: xAxisLabelFormat)
                            }
                        }
                }
            } else {
                if usesTradingDayAxis {
                    baseChart
                        .chartXScale(domain: tradingDayXDomain)
                        .chartXAxis {
                            AxisMarks(values: .automatic(desiredCount: 6)) { value in
                                AxisGridLine()
                                AxisValueLabel {
                                    if let idx = value.as(Int.self),
                                       idx >= 0,
                                       idx < tradingDayHistory.count {
                                        Text(tradingDayHistory[idx].date, format: .dateTime.month(.abbreviated).day())
                                    }
                                }
                            }
                        }
                } else {
                    baseChart
                        .chartXScale(domain: chartDomain)
                        .chartXAxis {
                            AxisMarks(values: .automatic(desiredCount: 6)) { value in
                                AxisGridLine()
                                AxisValueLabel(format: xAxisLabelFormat)
                            }
                        }
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
                        lookbackDays: timeframe.lookbackDays
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
