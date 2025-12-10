import Foundation

@MainActor
final class ChartViewModel: ObservableObject {
    static let availableTimeframes = ["m15", "h1", "h4", "d1", "w1"]

    @Published var selectedSymbol: Symbol?
    @Published var timeframe: String = "d1"
    @Published private(set) var chartData: ChartResponse?
    @Published private(set) var isLoading: Bool = false
    @Published var errorMessage: String?
    @Published var indicatorConfig = IndicatorConfig()

    private var loadTask: Task<Void, Never>?

    var bars: [OHLCBar] {
        chartData?.bars ?? []
    }

    // MARK: - Computed Indicators

    var sma20: [IndicatorDataPoint] {
        guard !bars.isEmpty else { return [] }
        let values = TechnicalIndicators.sma(bars: bars, period: 20)
        return zip(bars, values).map { IndicatorDataPoint(bar: $0, value: $1) }
    }

    var sma50: [IndicatorDataPoint] {
        guard !bars.isEmpty else { return [] }
        let values = TechnicalIndicators.sma(bars: bars, period: 50)
        return zip(bars, values).map { IndicatorDataPoint(bar: $0, value: $1) }
    }

    var sma200: [IndicatorDataPoint] {
        guard !bars.isEmpty else { return [] }
        let values = TechnicalIndicators.sma(bars: bars, period: 200)
        return zip(bars, values).map { IndicatorDataPoint(bar: $0, value: $1) }
    }

    var ema9: [IndicatorDataPoint] {
        guard !bars.isEmpty else { return [] }
        let values = TechnicalIndicators.ema(bars: bars, period: 9)
        return zip(bars, values).map { IndicatorDataPoint(bar: $0, value: $1) }
    }

    var ema21: [IndicatorDataPoint] {
        guard !bars.isEmpty else { return [] }
        let values = TechnicalIndicators.ema(bars: bars, period: 21)
        return zip(bars, values).map { IndicatorDataPoint(bar: $0, value: $1) }
    }

    var rsi: [IndicatorDataPoint] {
        guard !bars.isEmpty else { return [] }
        let values = TechnicalIndicators.rsi(bars: bars)
        return zip(bars, values).map { IndicatorDataPoint(bar: $0, value: $1) }
    }

    func loadChart() async {
        // Cancel any existing load operation
        loadTask?.cancel()

        // Prevent concurrent calls
        guard !isLoading else {
            print("[DEBUG] ChartViewModel.loadChart() - ALREADY LOADING, skipping duplicate call")
            return
        }

        print("[DEBUG] ========================================")
        print("[DEBUG] ChartViewModel.loadChart() CALLED")
        print("[DEBUG] ========================================")

        guard let symbol = selectedSymbol else {
            print("[DEBUG] ChartViewModel.loadChart() - NO SYMBOL SELECTED, returning")
            chartData = nil
            loadTask = nil
            return
        }

        print("[DEBUG] - Symbol: \(symbol.ticker)")
        print("[DEBUG] - Asset Type: \(symbol.assetType)")
        print("[DEBUG] - Timeframe: \(timeframe)")
        print("[DEBUG] - Starting chart data fetch...")
        isLoading = true
        errorMessage = nil

        // Create new task
        loadTask = Task {
            do {
                let response = try await APIClient.shared.fetchChart(
                    symbol: symbol.ticker,
                    timeframe: timeframe
                )

                // Check if task was cancelled
                guard !Task.isCancelled else {
                    print("[DEBUG] ChartViewModel.loadChart() - CANCELLED")
                    isLoading = false
                    return
                }

                print("[DEBUG] ChartViewModel.loadChart() - SUCCESS!")
                print("[DEBUG] - Received \(response.bars.count) bars")
                print("[DEBUG] - Setting chartData property...")
                chartData = response
                print("[DEBUG] - chartData is now: \(chartData == nil ? "nil" : "non-nil with \(chartData!.bars.count) bars")")
                errorMessage = nil
            } catch {
                guard !Task.isCancelled else {
                    print("[DEBUG] ChartViewModel.loadChart() - CANCELLED (error path)")
                    isLoading = false
                    return
                }

                print("[DEBUG] ChartViewModel.loadChart() - ERROR: \(error)")
                print("[DEBUG] - Error message: \(error.localizedDescription)")
                errorMessage = error.localizedDescription
                chartData = nil
            }

            isLoading = false
            print("[DEBUG] ChartViewModel.loadChart() COMPLETED")
            print("[DEBUG] - Final state: chartData=\(chartData == nil ? "nil" : "non-nil"), isLoading=\(isLoading), errorMessage=\(errorMessage ?? "nil")")
            print("[DEBUG] ========================================")
        }

        await loadTask?.value
    }

    func setTimeframe(_ newTimeframe: String) async {
        guard Self.availableTimeframes.contains(newTimeframe) else { return }
        timeframe = newTimeframe
        await loadChart()
    }

    func setSymbol(_ symbol: Symbol?) async {
        selectedSymbol = symbol
        await loadChart()
    }

    func clearData() {
        loadTask?.cancel()
        loadTask = nil
        chartData = nil
        errorMessage = nil
        isLoading = false
    }
}
