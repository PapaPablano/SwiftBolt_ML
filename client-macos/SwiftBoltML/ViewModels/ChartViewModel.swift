import Foundation

@MainActor
final class ChartViewModel: ObservableObject {
    static let availableTimeframes = Timeframe.allCases

    @Published var selectedSymbol: Symbol? {
        didSet {
            print("[DEBUG] 🟢 ChartViewModel.selectedSymbol DIDSET TRIGGERED")
            print("[DEBUG] - Old value: \(oldValue?.ticker ?? "nil")")
            print("[DEBUG] - New value: \(selectedSymbol?.ticker ?? "nil")")
            if selectedSymbol?.id != oldValue?.id {
                liveQuote = nil
                stopLiveQuoteUpdates()
                stopRealtimeSubscription()
                hydrationBanner = nil
                // Trigger chart load on symbol change
                Task { await loadChart() }
            }
        }
    }
    @Published var timeframe: Timeframe = .d1 {
        didSet {
            print("[DEBUG] 🕒 timeframe changed to \(timeframe.rawValue) (apiToken=\(timeframe.apiToken))")
            Task { await loadChart() }
        }
    }
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
    
    // WebChart Advanced Features
    @Published var useHeikinAshi: Bool = true
    @Published var showVolumeProfile: Bool = false {
        didSet {
            guard showVolumeProfile != oldValue else { return }
            if showVolumeProfile {
                calculateVolumeProfile()
            } else {
                volumeProfile = []
            }
        }
    }
    @Published private(set) var volumeProfile: [[String: Any]] = []

    // Refresh state
    @Published private(set) var isRefreshing: Bool = false
    @Published var refreshMessage: String?
    @Published var lastRefreshResult: RefreshDataResponse?
    @Published var lastUserRefreshResult: UserRefreshResponse?
    @Published private(set) var liveQuote: LiveQuote?
    @Published private(set) var marketState: String?
    
    // SPEC-8: Backfill orchestration state
    @Published private(set) var isHydrating: Bool = false
    @Published private(set) var backfillProgress: Double = 0
    @Published private(set) var backfillJobId: String?
    @Published var hydrationBanner: String?

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
    private var realtimeTask: Task<Void, Never>?
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
    private var superTrendParams: (period: Int, multiplier: Double) {
        timeframe.superTrendParams
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
        print("[DEBUG] - Timeframe: \(timeframe.rawValue) (sending: \(timeframe.apiToken))")
        print("[DEBUG] - Is Intraday: \(timeframe.isIntraday)")
        print("[DEBUG] - Starting chart data fetch...")
        isLoading = true
        errorMessage = nil
        
        // SPEC-8: Trigger non-blocking coverage check for intraday timeframes
        if timeframe.isIntraday && Config.ensureCoverageEnabled {
            Task.detached { [weak self] in
                await self?.ensureCoverageAsync(symbol: symbol.ticker)
            }
        }

        // Create new task
        loadTask = Task {
            do {
                if useV2API {
                    // Use V2 API with strict data layer separation:
                    // - Historical: Polygon (verified, dates < today)
                    // - Intraday: Tradier (live, today only)
                    // - Forecast: ML predictions (future dates)
                    print("[DEBUG] Requesting chart-data-v2 symbol=\(symbol.ticker) timeframe=\(timeframe.apiToken)")
                    let response = try await APIClient.shared.fetchChartV2(
                        symbol: symbol.ticker,
                        timeframe: timeframe.apiToken,
                        days: 730,  // Request 2 years of historical data
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
                    print("[DEBUG] - Historical (Polygon): \(response.layers.historical.count) bars")
                    print("[DEBUG] - Intraday (Tradier): \(response.layers.intraday.count) bars")
                    print("[DEBUG] - Forecast (ML): \(response.layers.forecast.count) bars")

                    chartDataV2 = response

                    // Build bars from correct layer based on timeframe
                    let bars = buildBars(from: response, for: timeframe)
                    print("[DEBUG] - Built \(bars.count) bars from \(timeframe.isIntraday ? "intraday" : "historical") layer")

                    // Also populate legacy chartData for indicator calculations
                    // This triggers didSet -> invalidateIndicatorCache
                    chartData = ChartResponse(
                        symbol: response.symbol,
                        assetType: "stock",
                        timeframe: response.timeframe,
                        bars: bars,
                        mlSummary: nil,
                        indicators: nil,
                        superTrendAI: nil
                    )
                    
                    // Explicitly recalculate indicators with new data
                    scheduleIndicatorRecalculation()
                    
                    // Start live quotes after first successful chart load
                    if liveQuoteTask == nil || liveQuoteTask?.isCancelled == true {
                        startLiveQuoteUpdates()
                    }
                } else {
                    // Use legacy API
                    let response = try await APIClient.shared.fetchChart(
                        symbol: symbol.ticker,
                        timeframe: timeframe.apiToken
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
                    
                    // Explicitly recalculate indicators with new data
                    scheduleIndicatorRecalculation()
                    
                    // Start live quotes after first successful chart load
                    if liveQuoteTask == nil || liveQuoteTask?.isCancelled == true {
                        startLiveQuoteUpdates()
                    }
                }
                
                errorMessage = nil
            } catch {
                guard !Task.isCancelled else {
                    print("[DEBUG] ChartViewModel.loadChart() - CANCELLED (error path)")
                    isLoading = false
                    return
                }

                print("[DEBUG] ChartViewModel.loadChart() - ERROR: \(error)")
                print("[DEBUG] - Error message: \(error.localizedDescription)")
                
                // Graceful fallback for intraday failures
                if case APIError.httpError(let status, _) = error, timeframe.isIntraday, status >= 500 {
                    print("[DEBUG] Intraday failed (\(status)), keeping previous bars and showing notice")
                    errorMessage = "Intraday data unavailable — showing daily data"
                    // Keep existing chartData; optionally trigger daily fallback
                    // Task { await self.loadDailyFallback(symbol: symbol.ticker) }
                } else {
                    errorMessage = error.localizedDescription
                    // Only clear data for non-recoverable errors
                    if !timeframe.isIntraday || chartData == nil {
                        chartData = nil
                        chartDataV2 = nil
                    }
                }
            }

            isLoading = false
            print("[DEBUG] ChartViewModel.loadChart() COMPLETED")
            print("[DEBUG] - Final state: chartData=\(chartData == nil ? "nil" : "non-nil"), isLoading=\(isLoading), errorMessage=\(errorMessage ?? "nil")")
            print("[DEBUG] ========================================")
        }

        await loadTask?.value
    }

    func setTimeframe(_ newTimeframe: Timeframe) async {
        timeframe = newTimeframe
        // loadChart() will be called automatically by didSet
    }
    
    /// Helper to build bars from correct data layer based on timeframe
    private func buildBars(from response: ChartDataV2Response, for timeframe: Timeframe) -> [OHLCBar] {
        // Prefer correct layer, but fall back if empty
        let intraday = response.layers.intraday.data
        let historical = response.layers.historical.data
        
        let src: [OHLCBar]
        switch timeframe {
        case .m15, .h1, .h4:
            src = !intraday.isEmpty ? intraday : historical
        case .d1, .w1:
            src = !historical.isEmpty ? historical : intraday
        }
        
        print("[DEBUG] buildBars → hist: \(historical.count) | intraday: \(intraday.count) | selected: \(src.count) for \(timeframe.apiToken)")
        
        return src
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
        liveQuoteTask = Task(priority: .utility) { [weak self] in
            await self?.runLiveQuoteLoop()
        }
    }

    private func stopLiveQuoteUpdates() {
        liveQuoteTask?.cancel()
        liveQuoteTask = nil
    }

    private func runLiveQuoteLoop() async {
        while !Task.isCancelled {
            let hasSymbol = await MainActor.run { selectedSymbol != nil }
            guard hasSymbol else {
                await MainActor.run { self.liveQuote = nil }
                do {
                    try await Task.sleep(nanoseconds: liveQuoteInterval)
                } catch { break }
                continue
            }

            let marketOpen = await MainActor.run { isMarketHours() }
            if marketOpen {
                await fetchLiveQuote()
            } else {
                await MainActor.run { self.liveQuote = nil }
            }

            do {
                try await Task.sleep(nanoseconds: liveQuoteInterval)
            } catch { break }
        }
    }

    private func fetchLiveQuote() async {
        let symbol = await MainActor.run { selectedSymbol }
        guard let symbol = symbol else { return }
        do {
            let response = try await APIClient.shared.fetchQuotes(symbols: [symbol.ticker])
            await MainActor.run {
                self.marketState = response.marketState
                if let quote = response.quotes.first {
                    self.liveQuote = LiveQuote(
                        symbol: quote.symbol,
                        last: quote.last,
                        change: quote.change,
                        changePercent: quote.changePercentage,
                        timestamp: quote.lastTradeTime
                    )
                }
            }
        } catch {
            // Log but don't spam
            print("[DEBUG] fetchLiveQuote error: \(error)")
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
    
    // MARK: - SPEC-8: Backfill Orchestration
    
    /// Non-blocking coverage check for intraday data
    /// Triggers server-side backfill if needed without blocking UI
    private func ensureCoverageAsync(symbol: String) async {
        let windowDays = timeframe.isIntraday ? 5 : 7
        
        do {
            let response = try await APIClient.shared.ensureCoverage(
                symbol: symbol,
                timeframe: timeframe.apiToken,
                windowDays: windowDays
            )
            
            await MainActor.run {
                self.backfillJobId = response.jobDefId
                self.isHydrating = (response.status == "gaps_detected")
                
                if response.status == "coverage_complete" {
                    print("[DEBUG] ✅ Coverage complete for \(symbol) \(timeframe.apiToken)")
                    self.hydrationBanner = nil
                } else {
                    print("[DEBUG] 🔄 Gaps detected for \(symbol) \(timeframe.apiToken), orchestrator will hydrate")
                    print("[DEBUG] - Job def ID: \(response.jobDefId)")
                    print("[DEBUG] - Gaps found: \(response.coverageStatus.gapsFound)")
                    
                    // Subscribe to Realtime updates for progress
                    self.subscribeToJobProgress(symbol: symbol, timeframe: timeframe.apiToken)
                }
            }
        } catch {
            print("[DEBUG] ⚠️ ensureCoverage failed (non-fatal): \(error)")
        }
    }
    
    // MARK: - SPEC-8: Realtime Progress Subscription
    
    /// Subscribe to job_runs table for real-time progress updates
    private func subscribeToJobProgress(symbol: String, timeframe: String) {
        // Cancel existing subscription
        realtimeTask?.cancel()
        
        realtimeTask = Task {
            do {
                let url = URL(string: "\(Config.supabaseURL.absoluteString)/realtime/v1/websocket?apikey=\(Config.supabaseAnonKey)&vsn=1.0.0")!
                let session = URLSession(configuration: .default)
                let (asyncBytes, response) = try await session.bytes(from: url)
                
                guard let httpResponse = response as? HTTPURLResponse,
                      httpResponse.statusCode == 200 else {
                    print("[DEBUG] ⚠️ Realtime connection failed")
                    return
                }
                
                print("[DEBUG] 🔌 Realtime connected for \(symbol)/\(timeframe)")
                
                // Listen for progress updates
                for try await line in asyncBytes.lines {
                    guard !Task.isCancelled else { break }
                    
                    // Parse Realtime message and extract progress
                    if let data = line.data(using: .utf8),
                       let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                       let payload = json["payload"] as? [String: Any],
                       let record = payload["record"] as? [String: Any],
                       let recordSymbol = record["symbol"] as? String,
                       let recordTimeframe = record["timeframe"] as? String,
                       recordSymbol == symbol && recordTimeframe == timeframe {
                        
                        let progress = record["progress_percent"] as? Double ?? 0
                        let status = record["status"] as? String ?? "queued"
                        
                        await MainActor.run {
                            self.backfillProgress = progress
                            
                            if progress >= 100 || status == "success" {
                                self.isHydrating = false
                                self.hydrationBanner = nil
                                print("[DEBUG] ✅ Hydration complete for \(symbol)/\(timeframe)")
                                // Reload chart to show new data
                                Task { await self.loadChart() }
                            } else if status == "running" {
                                let pct = Int(progress)
                                self.hydrationBanner = "Hydrating \(symbol) \(timeframe)… \(pct)%"
                                print("[DEBUG] 🔄 Progress: \(pct)%")
                            } else if status == "failed" {
                                self.isHydrating = false
                                self.hydrationBanner = "Hydration failed"
                                print("[DEBUG] ❌ Hydration failed for \(symbol)/\(timeframe)")
                            }
                        }
                    }
                }
            } catch {
                if !Task.isCancelled {
                    print("[DEBUG] ⚠️ Realtime subscription error: \(error)")
                }
            }
        }
    }
    
    /// Stop Realtime subscription
    private func stopRealtimeSubscription() {
        realtimeTask?.cancel()
        realtimeTask = nil
    }
    
    // MARK: - Volume Profile Calculator
    
    /// Calculate volume profile from OHLC bars
    /// Groups volume by price levels to identify support/resistance zones
    func calculateVolumeProfile(bucketSize: Double = 0.50) {
        guard let chartData = chartDataV2 else {
            volumeProfile = []
            return
        }
        
        let bars = chartData.allBars
        guard !bars.isEmpty else {
            volumeProfile = []
            return
        }
        
        var volumeByPrice: [Double: Double] = [:]
        
        // Distribute volume across price levels
        for bar in bars {
            let priceRange = bar.high - bar.low
            guard priceRange > 0 else { continue }
            
            let numLevels = max(1, Int(ceil(priceRange / bucketSize)))
            let volumePerLevel = bar.volume / Double(numLevels)
            
            var price = floor(bar.low / bucketSize) * bucketSize
            while price <= bar.high {
                let bucket = round(price / bucketSize) * bucketSize
                volumeByPrice[bucket, default: 0] += volumePerLevel
                price += bucketSize
            }
        }
        
        // Calculate total volume and find POC
        let totalVolume = volumeByPrice.values.reduce(0, +)
        let maxVolume = volumeByPrice.values.max() ?? 0
        
        // Convert to profile data format
        volumeProfile = volumeByPrice.map { price, volume in
            [
                "price": price,
                "volume": volume,
                "volumePercentage": (volume / totalVolume) * 100,
                "pointOfControl": abs(volume - maxVolume) < 0.01
            ]
        }.sorted { ($0["price"] as? Double ?? 0) < ($1["price"] as? Double ?? 0) }
        
        print("[ChartViewModel] Volume profile calculated: \(volumeProfile.count) levels, POC at \(volumeByPrice.first(where: { $0.value == maxVolume })?.key ?? 0)")
    }
}
