import Foundation

@MainActor
final class ChartViewModel: ObservableObject {
    static let availableTimeframes = ["m15", "h1", "h4", "d1", "w1"]

    @Published var selectedSymbol: Symbol? {
        didSet {
            print("[DEBUG] 🟢 ChartViewModel.selectedSymbol DIDSET TRIGGERED")
            print("[DEBUG] - Old value: \(oldValue?.ticker ?? "nil")")
            print("[DEBUG] - New value: \(selectedSymbol?.ticker ?? "nil")")
        }
    }
    @Published var timeframe: String = "d1"
    @Published private(set) var chartData: ChartResponse?
    @Published private(set) var isLoading: Bool = false
    @Published var errorMessage: String?
    @Published var indicatorConfig = IndicatorConfig()
    
    // Refresh state
    @Published private(set) var isRefreshing: Bool = false
    @Published var refreshMessage: String?
    @Published var lastRefreshResult: RefreshDataResponse?

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

    // MARK: - MACD Indicator

    var macdResult: TechnicalIndicators.MACDResult? {
        guard !bars.isEmpty else { return nil }
        return TechnicalIndicators.macd(bars: bars)
    }

    var macdLine: [IndicatorDataPoint] {
        guard let result = macdResult else { return [] }
        return zip(bars, result.macd).map { IndicatorDataPoint(bar: $0, value: $1) }
    }

    var macdSignal: [IndicatorDataPoint] {
        guard let result = macdResult else { return [] }
        return zip(bars, result.signal).map { IndicatorDataPoint(bar: $0, value: $1) }
    }

    var macdHistogram: [IndicatorDataPoint] {
        guard let result = macdResult else { return [] }
        return zip(bars, result.histogram).map { IndicatorDataPoint(bar: $0, value: $1) }
    }

    // MARK: - Stochastic Indicator

    var stochasticResult: TechnicalIndicators.StochasticResult? {
        guard !bars.isEmpty else { return nil }
        return TechnicalIndicators.stochastic(bars: bars)
    }

    var stochasticK: [IndicatorDataPoint] {
        guard let result = stochasticResult else { return [] }
        return zip(bars, result.k).map { IndicatorDataPoint(bar: $0, value: $1) }
    }

    var stochasticD: [IndicatorDataPoint] {
        guard let result = stochasticResult else { return [] }
        return zip(bars, result.d).map { IndicatorDataPoint(bar: $0, value: $1) }
    }

    // MARK: - KDJ Indicator

    var kdjResult: TechnicalIndicators.KDJResult? {
        guard !bars.isEmpty else { return nil }
        return TechnicalIndicators.kdj(bars: bars)
    }

    var kdjK: [IndicatorDataPoint] {
        guard let result = kdjResult else { return [] }
        return zip(bars, result.k).map { IndicatorDataPoint(bar: $0, value: $1) }
    }

    var kdjD: [IndicatorDataPoint] {
        guard let result = kdjResult else { return [] }
        return zip(bars, result.d).map { IndicatorDataPoint(bar: $0, value: $1) }
    }

    var kdjJ: [IndicatorDataPoint] {
        guard let result = kdjResult else { return [] }
        return zip(bars, result.j).map { IndicatorDataPoint(bar: $0, value: $1) }
    }

    // MARK: - ADX Indicator

    var adxResult: TechnicalIndicators.ADXResult? {
        guard !bars.isEmpty else { return nil }
        return TechnicalIndicators.adx(bars: bars)
    }

    var adxLine: [IndicatorDataPoint] {
        guard let result = adxResult else { return [] }
        return zip(bars, result.adx).map { IndicatorDataPoint(bar: $0, value: $1) }
    }

    var plusDI: [IndicatorDataPoint] {
        guard let result = adxResult else { return [] }
        return zip(bars, result.plusDI).map { IndicatorDataPoint(bar: $0, value: $1) }
    }

    var minusDI: [IndicatorDataPoint] {
        guard let result = adxResult else { return [] }
        return zip(bars, result.minusDI).map { IndicatorDataPoint(bar: $0, value: $1) }
    }

    // MARK: - SuperTrend Indicator

    /// Adaptive SuperTrend parameters based on timeframe
    /// - Intraday (15M, 1H): Tighter settings for faster signals
    /// - Swing (4H, D): Standard settings
    /// - Position (W): Wider settings for less noise
    private var superTrendParams: (period: Int, multiplier: Double) {
        switch timeframe {
        case "m15":
            return (period: 7, multiplier: 2.0)   // Fast, tight stops
        case "h1":
            return (period: 8, multiplier: 2.5)   // Slightly wider
        case "h4":
            return (period: 10, multiplier: 3.0)  // Standard
        case "d1":
            return (period: 10, multiplier: 3.0)  // Standard
        case "w1":
            return (period: 14, multiplier: 4.0)  // Wide, less noise
        default:
            return (period: 10, multiplier: 3.0)  // Default
        }
    }

    var superTrendResult: TechnicalIndicators.SuperTrendResult? {
        guard !bars.isEmpty else { return nil }
        let params = superTrendParams
        return TechnicalIndicators.superTrend(bars: bars, period: params.period, multiplier: params.multiplier)
    }

    var superTrendLine: [IndicatorDataPoint] {
        guard let result = superTrendResult else { return [] }
        return zip(bars, result.supertrend).map { IndicatorDataPoint(bar: $0, value: $1) }
    }

    var superTrendTrend: [Int] {
        superTrendResult?.trend ?? []
    }

    var superTrendStrength: [IndicatorDataPoint] {
        guard let result = superTrendResult else { return [] }
        return zip(bars, result.strength).map { IndicatorDataPoint(bar: $0, value: $1) }
    }

    // MARK: - Bollinger Bands

    var bollingerBands: TechnicalIndicators.BollingerBands? {
        guard !bars.isEmpty else { return nil }
        return TechnicalIndicators.bollingerBands(bars: bars)
    }

    var bollingerUpper: [IndicatorDataPoint] {
        guard let bb = bollingerBands else { return [] }
        return zip(bars, bb.upper).map { IndicatorDataPoint(bar: $0, value: $1) }
    }

    var bollingerMiddle: [IndicatorDataPoint] {
        guard let bb = bollingerBands else { return [] }
        return zip(bars, bb.middle).map { IndicatorDataPoint(bar: $0, value: $1) }
    }

    var bollingerLower: [IndicatorDataPoint] {
        guard let bb = bollingerBands else { return [] }
        return zip(bars, bb.lower).map { IndicatorDataPoint(bar: $0, value: $1) }
    }

    // MARK: - ATR Indicator

    var atr: [IndicatorDataPoint] {
        guard !bars.isEmpty else { return [] }
        let values = TechnicalIndicators.atr(bars: bars)
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
    
    // MARK: - Coordinated Refresh
    
    /// Refresh data for the current symbol - fetches new bars and queues ML/options jobs
    /// - Parameters:
    ///   - refreshML: Queue ML forecast job after data refresh (default: true)
    ///   - refreshOptions: Queue options ranking job after data refresh (default: false)
    func refreshData(refreshML: Bool = true, refreshOptions: Bool = false) async {
        guard let symbol = selectedSymbol else {
            refreshMessage = "No symbol selected"
            return
        }
        
        isRefreshing = true
        refreshMessage = nil
        
        do {
            let response = try await APIClient.shared.refreshData(
                symbol: symbol.ticker,
                refreshML: refreshML,
                refreshOptions: refreshOptions
            )
            
            lastRefreshResult = response
            refreshMessage = response.message
            
            // After successful refresh, reload chart data to show new bars
            if response.success {
                await loadChart()
            }
            
        } catch {
            refreshMessage = "Refresh failed: \(error.localizedDescription)"
        }
        
        isRefreshing = false
    }
}
