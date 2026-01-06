import Foundation

@MainActor
final class ChartViewModel: ObservableObject {
    static let availableTimeframes = ["m15", "h1", "h4", "d1", "w1"]

    @Published var selectedSymbol: Symbol? {
        didSet {
            print("[DEBUG] 🟢 ChartViewModel.selectedSymbol DIDSET TRIGGERED")
            print("[DEBUG] - Old value: \(oldValue?.ticker ?? "nil")")
            print("[DEBUG] - New value: \(selectedSymbol?.ticker ?? "nil")")
            if selectedSymbol?.id != oldValue?.id {
                liveQuote = nil
                stopLiveQuoteUpdates()
                if selectedSymbol != nil {
                    startLiveQuoteUpdates()
                }
            }
        }
    }
    @Published var timeframe: String = "d1"
    @Published private(set) var chartData: ChartResponse? {
        didSet {
            // Invalidate indicator cache when chart data changes
            invalidateIndicatorCache()
        }
    }
    @Published private(set) var chartDataV2: ChartDataV2Response?
    @Published private(set) var isLoading: Bool = false
    @Published var errorMessage: String?
    @Published var indicatorConfig = IndicatorConfig()
    @Published var useV2API: Bool = true

    // Refresh state
    @Published private(set) var isRefreshing: Bool = false
    @Published var refreshMessage: String?
    @Published var lastRefreshResult: RefreshDataResponse?
    @Published var lastUserRefreshResult: UserRefreshResponse?
    @Published private(set) var liveQuote: LiveQuote?
    @Published private(set) var marketState: String?

    // MARK: - Cached Indicator Storage

    private var _cachedSMA20: [IndicatorDataPoint]?
    private var _cachedSMA50: [IndicatorDataPoint]?
    private var _cachedSMA200: [IndicatorDataPoint]?
    private var _cachedEMA9: [IndicatorDataPoint]?
    private var _cachedEMA21: [IndicatorDataPoint]?
    private var _cachedRSI: [IndicatorDataPoint]?
    private var _cachedMACD: TechnicalIndicators.MACDResult?
    private var _cachedStochastic: TechnicalIndicators.StochasticResult?
    private var _cachedKDJ: TechnicalIndicators.KDJResult?
    private var _cachedADX: TechnicalIndicators.ADXResult?
    private var _cachedSuperTrend: TechnicalIndicators.SuperTrendResult?
    private var _cachedBollinger: TechnicalIndicators.BollingerBands?
    private var _cachedATR: [IndicatorDataPoint]?

    // MARK: - Support & Resistance Indicators

    /// BigBeluga multi-timeframe pivot levels indicator
    let pivotLevelsIndicator = PivotLevelsIndicator()

    /// Polynomial regression S&R indicator
    let polynomialSRIndicator = PolynomialRegressionIndicator()

    /// Logistic regression ML-based S&R indicator
    let logisticSRIndicator = LogisticRegressionIndicator()

    /// SuperTrend AI with K-Means clustering for adaptive factor selection
    let superTrendAIIndicator = SuperTrendAIIndicator()

    private var loadTask: Task<Void, Never>?
    private var liveQuoteTask: Task<Void, Never>?
    private let liveQuoteInterval: UInt64 = 60 * 1_000_000_000  // 60 seconds
    private let marketTimeZone = TimeZone(identifier: "America/New_York") ?? .current
    private let isoDateFormatter: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()

    var bars: [OHLCBar] {
        chartData?.bars ?? []
    }

    private func scheduleIndicatorRecalculation() {
        guard !bars.isEmpty else { return }
        Task { @MainActor [weak self] in
            guard let self else { return }
            self.recalculateSRIndicators()
            self.recalculateAIIndicators()
        }
    }

    deinit {
        liveQuoteTask?.cancel()
    }

    // MARK: - Cache Invalidation

    private func invalidateIndicatorCache() {
        _cachedSMA20 = nil
        _cachedSMA50 = nil
        _cachedSMA200 = nil
        _cachedEMA9 = nil
        _cachedEMA21 = nil
        _cachedRSI = nil
        _cachedMACD = nil
        _cachedStochastic = nil
        _cachedKDJ = nil
        _cachedADX = nil
        _cachedSuperTrend = nil
        _cachedBollinger = nil
        _cachedATR = nil
    }

    // MARK: - Cached Computed Indicators

    var sma20: [IndicatorDataPoint] {
        if let cached = _cachedSMA20 { return cached }
        guard !bars.isEmpty else { return [] }
        let values = TechnicalIndicators.sma(bars: bars, period: 20)
        let result = zip(bars, values).map { IndicatorDataPoint(bar: $0, value: $1) }
        _cachedSMA20 = result
        return result
    }

    var sma50: [IndicatorDataPoint] {
        if let cached = _cachedSMA50 { return cached }
        guard !bars.isEmpty else { return [] }
        let values = TechnicalIndicators.sma(bars: bars, period: 50)
        let result = zip(bars, values).map { IndicatorDataPoint(bar: $0, value: $1) }
        _cachedSMA50 = result
        return result
    }

    var sma200: [IndicatorDataPoint] {
        if let cached = _cachedSMA200 { return cached }
        guard !bars.isEmpty else { return [] }
        let values = TechnicalIndicators.sma(bars: bars, period: 200)
        let result = zip(bars, values).map { IndicatorDataPoint(bar: $0, value: $1) }
        _cachedSMA200 = result
        return result
    }

    var ema9: [IndicatorDataPoint] {
        if let cached = _cachedEMA9 { return cached }
        guard !bars.isEmpty else { return [] }
        let values = TechnicalIndicators.ema(bars: bars, period: 9)
        let result = zip(bars, values).map { IndicatorDataPoint(bar: $0, value: $1) }
        _cachedEMA9 = result
        return result
    }

    var ema21: [IndicatorDataPoint] {
        if let cached = _cachedEMA21 { return cached }
        guard !bars.isEmpty else { return [] }
        let values = TechnicalIndicators.ema(bars: bars, period: 21)
        let result = zip(bars, values).map { IndicatorDataPoint(bar: $0, value: $1) }
        _cachedEMA21 = result
        return result
    }

    var rsi: [IndicatorDataPoint] {
        if let cached = _cachedRSI { return cached }
        guard !bars.isEmpty else { return [] }
        let values = TechnicalIndicators.rsi(bars: bars)
        let result = zip(bars, values).map { IndicatorDataPoint(bar: $0, value: $1) }
        _cachedRSI = result
        return result
    }

    // MARK: - MACD Indicator (Cached)

    var macdResult: TechnicalIndicators.MACDResult? {
        if let cached = _cachedMACD { return cached }
        guard !bars.isEmpty else { return nil }
        let result = TechnicalIndicators.macd(bars: bars)
        _cachedMACD = result
        return result
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

    // MARK: - Stochastic Indicator (Cached)

    var stochasticResult: TechnicalIndicators.StochasticResult? {
        if let cached = _cachedStochastic { return cached }
        guard !bars.isEmpty else { return nil }
        let result = TechnicalIndicators.stochastic(bars: bars)
        _cachedStochastic = result
        return result
    }

    var stochasticK: [IndicatorDataPoint] {
        guard let result = stochasticResult else { return [] }
        return zip(bars, result.k).map { IndicatorDataPoint(bar: $0, value: $1) }
    }

    var stochasticD: [IndicatorDataPoint] {
        guard let result = stochasticResult else { return [] }
        return zip(bars, result.d).map { IndicatorDataPoint(bar: $0, value: $1) }
    }

    // MARK: - KDJ Indicator (Cached)

    var kdjResult: TechnicalIndicators.KDJResult? {
        if let cached = _cachedKDJ { return cached }
        guard !bars.isEmpty else { return nil }
        let result = TechnicalIndicators.kdj(bars: bars)
        _cachedKDJ = result
        return result
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

    // MARK: - ADX Indicator (Cached)

    var adxResult: TechnicalIndicators.ADXResult? {
        if let cached = _cachedADX { return cached }
        guard !bars.isEmpty else { return nil }
        let result = TechnicalIndicators.adx(bars: bars)
        _cachedADX = result
        return result
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
        if let cached = _cachedSuperTrend { return cached }
        guard !bars.isEmpty else { return nil }
        let params = superTrendParams
        let result = TechnicalIndicators.superTrend(bars: bars, period: params.period, multiplier: params.multiplier)
        _cachedSuperTrend = result
        return result
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

    // MARK: - SuperTrend AI (K-Means Clustering)

    /// SuperTrend AI result with adaptive factor selection
    var superTrendAIResult: SuperTrendAIResult? {
        superTrendAIIndicator.result
    }

    /// SuperTrend AI line (adaptive)
    var superTrendAILine: [IndicatorDataPoint] {
        guard let result = superTrendAIResult else { return [] }
        return zip(bars, result.supertrend).map { IndicatorDataPoint(bar: $0, value: $1) }
    }

    /// SuperTrend AI trend direction
    var superTrendAITrend: [Int] {
        superTrendAIResult?.trend ?? []
    }

    /// SuperTrend AI adaptive factor at each bar
    var superTrendAIFactor: [Double] {
        superTrendAIResult?.adaptiveFactor ?? []
    }

    /// SuperTrend AI performance metrics
    var superTrendAIPerformance: [IndicatorDataPoint] {
        guard let result = superTrendAIResult else { return [] }
        return zip(bars, result.performanceMetrics).map { IndicatorDataPoint(bar: $0, value: $1) }
    }

    /// SuperTrend AI adaptive moving average
    var superTrendAIAdaptiveMA: [IndicatorDataPoint] {
        guard let result = superTrendAIResult else { return [] }
        return zip(bars, result.adaptiveMA).map { IndicatorDataPoint(bar: $0, value: $1) }
    }

    /// SuperTrend AI detected signals
    var superTrendAISignals: [SuperTrendSignal] {
        superTrendAIIndicator.detectSignals()
    }

    /// Calculate SuperTrend AI indicator
    func calculateSuperTrendAI() {
        guard !bars.isEmpty else { return }
        superTrendAIIndicator.calculate(bars: bars)
    }

    // MARK: - Bollinger Bands (Cached)

    var bollingerBands: TechnicalIndicators.BollingerBands? {
        if let cached = _cachedBollinger { return cached }
        guard !bars.isEmpty else { return nil }
        let result = TechnicalIndicators.bollingerBands(bars: bars)
        _cachedBollinger = result
        return result
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

    // MARK: - ATR Indicator (Cached)

    var atr: [IndicatorDataPoint] {
        if let cached = _cachedATR { return cached }
        guard !bars.isEmpty else { return [] }
        let values = TechnicalIndicators.atr(bars: bars)
        let result = zip(bars, values).map { IndicatorDataPoint(bar: $0, value: $1) }
        _cachedATR = result
        return result
    }

    // MARK: - S&R Indicator Recalculation

    /// Recalculate all S&R indicators when chart data changes
    /// Always calculates all indicators so they're ready when toggled on
    func recalculateSRIndicators() {
        guard !bars.isEmpty else { return }

        // Always calculate all indicators so they're ready when user enables them
        pivotLevelsIndicator.calculate(bars: bars)
        polynomialSRIndicator.calculate(bars: bars)
        logisticSRIndicator.calculate(bars: bars)
    }

    /// Recalculate all AI indicators (SuperTrend AI, etc.)
    func recalculateAIIndicators() {
        guard !bars.isEmpty else { return }
        superTrendAIIndicator.calculate(bars: bars)
    }

    /// Recalculate a specific S&R indicator
    func recalculateSRIndicator(_ type: SRIndicatorType) {
        guard !bars.isEmpty else { return }

        switch type {
        case .pivotLevels:
            pivotLevelsIndicator.calculate(bars: bars)
        case .polynomialSR:
            polynomialSRIndicator.calculate(bars: bars)
        case .logisticSR:
            logisticSRIndicator.calculate(bars: bars)
        case .superTrendAI:
            superTrendAIIndicator.calculate(bars: bars)
        }
    }

    enum SRIndicatorType {
        case pivotLevels
        case polynomialSR
        case logisticSR
        case superTrendAI
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
                if useV2API {
                    // Use new V2 API with layered data
                    let response = try await APIClient.shared.fetchChartV2(
                        symbol: symbol.ticker,
                        days: 365,  // Request 1 year of data
                        includeForecast: true,
                        forecastDays: 10
                    )

                    // Check if task was cancelled
                    guard !Task.isCancelled else {
                        print("[DEBUG] ChartViewModel.loadChart() - CANCELLED")
                        isLoading = false
                        return
                    }

                    print("[DEBUG] ChartViewModel.loadChart() V2 - SUCCESS!")
                    print("[DEBUG] - Historical: \(response.layers.historical.count) bars")
                    print("[DEBUG] - Intraday: \(response.layers.intraday.count) bars")
                    print("[DEBUG] - Forecast: \(response.layers.forecast.count) bars")

                    // If V2 returns too little historical data, fall back to V1 API
                    if response.layers.historical.count < 100 {
                        print("[DEBUG] V2 API returned insufficient data (\(response.layers.historical.count) bars), falling back to V1 API")
                        let legacyResponse = try await APIClient.shared.fetchChart(
                            symbol: symbol.ticker,
                            timeframe: timeframe
                        )

                        guard !Task.isCancelled else {
                            print("[DEBUG] ChartViewModel.loadChart() - CANCELLED (fallback)")
                            isLoading = false
                            return
                        }

                        print("[DEBUG] ChartViewModel.loadChart() V1 fallback - \(legacyResponse.bars.count) bars")
                        chartData = legacyResponse
                        chartDataV2 = nil  // Clear V2 data so WebChartView uses V1
                    } else {
                        chartDataV2 = response

                        // Also populate legacy chartData for backward compatibility
                        chartData = ChartResponse(
                            symbol: response.symbol,
                            assetType: "stock",
                            timeframe: response.timeframe,
                            bars: response.allBars,
                            mlSummary: nil,
                            indicators: nil,
                            superTrendAI: nil
                        )
                    }
                } else {
                    // Use legacy API
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
                }
                
                errorMessage = nil

                // Recalculate S&R indicators with new data
                scheduleIndicatorRecalculation()
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
                chartDataV2 = nil
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
        liveQuote = nil
        stopLiveQuoteUpdates()
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
    
    /// Comprehensive user-triggered refresh - orchestrates backfill, bars, ML, options, and S/R
    /// Use this when the user explicitly presses a refresh button
    func userRefresh() async {
        guard let symbol = selectedSymbol else {
            refreshMessage = "No symbol selected"
            return
        }
        
        isRefreshing = true
        refreshMessage = "Refreshing all data..."
        
        do {
            let response = try await APIClient.shared.userRefresh(symbol: symbol.ticker)
            
            lastUserRefreshResult = response
            refreshMessage = response.message
            
            // Clear existing chart data to force fresh display
            chartData = nil
            
            // After successful refresh, reload chart data to show new bars
            if response.success {
                // Clear URL cache to ensure fresh data
                URLCache.shared.removeAllCachedResponses()
                await loadChart()
            }
            
        } catch {
            refreshMessage = "Refresh failed: \(error.localizedDescription)"
        }
        
        isRefreshing = false
    }

    // MARK: - Live Quote Updates

    private func startLiveQuoteUpdates() {
        liveQuoteTask?.cancel()
        liveQuoteTask = Task { [weak self] in
            await self?.runLiveQuoteLoop()
        }
    }

    private func stopLiveQuoteUpdates() {
        liveQuoteTask?.cancel()
        liveQuoteTask = nil
    }

    @MainActor
    private func runLiveQuoteLoop() async {
        while !Task.isCancelled {
            guard selectedSymbol != nil else {
                liveQuote = nil
                try? await Task.sleep(nanoseconds: liveQuoteInterval)
                continue
            }

            if isMarketHours() {
                await fetchLiveQuote()
            } else {
                liveQuote = nil
            }

            try? await Task.sleep(nanoseconds: liveQuoteInterval)
        }
    }

    private func fetchLiveQuote() async {
        guard let symbol = selectedSymbol else { return }
        do {
            let response = try await APIClient.shared.fetchQuotes(symbols: [symbol.ticker])
            marketState = response.marketState
            if let quote = response.quotes.first {
                liveQuote = LiveQuote(
                    symbol: quote.symbol,
                    last: quote.last,
                    change: quote.change,
                    changePercent: quote.changePercentage,
                    timestamp: quote.lastTradeTime
                )
            }
        } catch {
            print("[DEBUG] ChartViewModel.fetchLiveQuote() - ERROR: \(error)")
        }
    }

    private func isMarketHours(date: Date = Date()) -> Bool {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = marketTimeZone
        let components = calendar.dateComponents([.weekday, .hour, .minute], from: date)

        guard let weekday = components.weekday,
              (2...6).contains(weekday), // Monday-Friday
              let hour = components.hour,
              let minute = components.minute else {
            return false
        }

        let minutes = hour * 60 + minute
        let openMinutes = 9 * 60 + 30
        let closeMinutes = 16 * 60

        return minutes >= openMinutes && minutes <= closeMinutes
    }
}
