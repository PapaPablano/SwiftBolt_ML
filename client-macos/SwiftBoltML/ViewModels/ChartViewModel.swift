import Foundation
import WebKit
import Supabase
import SwiftUI

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
                stopChartAutoRefresh()
                stopRealtimeSubscription()
                stopHydrationPoller()
                stopCoverageCheck()
                hydrationBanner = nil
                
                // Cancel any pending load task
                loadTask?.cancel()
                
                // Defer to next run loop and add debounce to prevent duplicate loads
                loadTask = Task { @MainActor in
                    // Small debounce to prevent rapid successive calls
                    try? await Task.sleep(nanoseconds: 100_000_000) // 0.1s
                    if !Task.isCancelled {
                        await loadChart()
                    }
                }
            }
        }
    }
    @Published var timeframe: Timeframe = .d1 {
        didSet {
            guard timeframe != oldValue else { return }
            stopHydrationPoller()
            stopCoverageCheck()
            stopChartAutoRefresh()  // Restart refresh timer with new timeframe interval
            print("[DEBUG] 🕒 timeframe changed to \(timeframe.rawValue) (apiToken=\(timeframe.apiToken))")
            
            // Cancel any pending load task
            loadTask?.cancel()
            
            // Defer to next run loop to avoid publishing changes during view updates
            loadTask = Task { @MainActor in
                try? await Task.sleep(nanoseconds: 100_000_000) // 0.1s debounce
                if !Task.isCancelled {
                    await loadChart()
                }
            }
        }
    }
    @Published private(set) var chartData: ChartResponse? {
        didSet {
            // Invalidate indicator cache when chart data changes
            invalidateIndicatorCache()
            if oldValue?.mlSummary?.horizons != chartData?.mlSummary?.horizons {
                _cachedSelectedForecastBars = nil
                rebuildSelectedForecastBars()
            }
        }
    }
    @Published private(set) var chartDataV2: ChartDataV2Response? {
        didSet {
            if oldValue?.mlSummary?.horizons != chartDataV2?.mlSummary?.horizons {
                _cachedSelectedForecastBars = nil
                rebuildSelectedForecastBars()
            }
            invalidateIndicatorCache()
        }
    }
    @Published var selectedForecastHorizon: String? {
        didSet {
            if oldValue != selectedForecastHorizon {
                rebuildSelectedForecastBars()
            }
        }
    }
    @Published private(set) var isLoading: Bool = false
    @Published var errorMessage: String?
    @Published var indicatorConfig = IndicatorConfig()
    @Published var useV2API: Bool = true
    private var v2UnsupportedSymbols: Set<String> = []
    
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

    // Real-Time Forecast Chart Data
    @Published var realtimeChartData: RealtimeChartData?
    @Published var isRealtimeConnected: Bool = false
    var realtimeWebSocket: RealtimeForecastWebSocket?

    // Binary forecast overlay (from POST /api/v1/forecast/binary or Supabase ml_binary_forecasts)
    @Published private(set) var binaryForecastOverlay: BinaryForecastResponse?

    // Multi-Timeframe Forecasts (Fix F)
    @Published var isMultiTimeframeMode: Bool = false
    @Published private(set) var isLoadingMultiTimeframe: Bool = false
    @Published private(set) var multiTimeframeForecasts: [String: ChartResponse] = [:]
    static let multiTimeframes: [Timeframe] = [.m15, .h1, .h4, .d1, .w1]

    // Cross-Timeframe Trend Alignment (Fix G)
    struct TrendAlignment {
        let bullishCount: Int
        let bearishCount: Int
        let neutralCount: Int
        let totalTimeframes: Int
        let contributingTimeframes: [String]

        var alignmentScore: Double {
            guard totalTimeframes > 0 else { return 0 }
            let maxAgreement = Double(max(bullishCount, bearishCount, neutralCount))
            return maxAgreement / Double(totalTimeframes)
        }

        enum Status {
            case aligned    // 80%+ agreement
            case mixed      // 60-80% agreement
            case conflicting // <60% agreement

            var color: Color {
                switch self {
                case .aligned: return .green
                case .mixed: return .yellow
                case .conflicting: return .red
                }
            }

            var label: String {
                switch self {
                case .aligned: return "ALIGNED"
                case .mixed: return "MIXED"
                case .conflicting: return "CONFLICTING"
                }
            }
        }

        var status: Status {
            if alignmentScore >= 0.8 { return .aligned }
            if alignmentScore >= 0.6 { return .mixed }
            return .conflicting
        }

        var dominantDirection: String {
            if bullishCount >= bearishCount && bullishCount >= neutralCount { return "bullish" }
            if bearishCount >= bullishCount && bearishCount >= neutralCount { return "bearish" }
            return "neutral"
        }

        var summaryText: String {
            let dominant = dominantDirection.capitalized
            return "\(max(bullishCount, bearishCount, neutralCount))/\(totalTimeframes) \(dominant)"
        }
    }

    /// Computed trend alignment based on multi-timeframe forecasts (Fix G)
    var trendAlignment: TrendAlignment? {
        guard !multiTimeframeForecasts.isEmpty else { return nil }

        var bullish = 0
        var bearish = 0
        var neutral = 0
        var contributing: [String] = []

        for (timeframe, response) in multiTimeframeForecasts {
            guard let label = response.mlSummary?.overallLabel?.lowercased() else { continue }
            contributing.append(timeframe)

            switch label {
            case "bullish": bullish += 1
            case "bearish": bearish += 1
            default: neutral += 1
            }
        }

        guard !contributing.isEmpty else { return nil }

        return TrendAlignment(
            bullishCount: bullish,
            bearishCount: bearish,
            neutralCount: neutral,
            totalTimeframes: contributing.count,
            contributingTimeframes: contributing
        )
    }

    // Refresh state
    @Published private(set) var isRefreshing: Bool = false
    @Published var refreshMessage: String?
    @Published var lastRefreshResult: RefreshDataResponse?
    @Published var lastUserRefreshResult: UserRefreshResponse?
    @Published private(set) var liveQuote: LiveQuote?
    @Published private(set) var marketState: String?
    
    // SPEC-8: Backfill orchestration state
    @Published private(set) var isHydrating: Bool = false
    @Published private(set) var backfillProgress: EnsureCoverageResponse.BackfillProgress?
    @Published private(set) var backfillJobId: String?
    @Published var hydrationBanner: String?

    // SPEC: Data recency/staleness report for debugging
    @Published private(set) var dataRecencyReport: StalenessReport?

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
    private var _cachedSelectedForecastBars: [OHLCBar]?

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
    private var hydrationPollTask: Task<Void, Never>?
    private var coverageCheckTask: Task<Void, Never>?
    private var chartRefreshTask: Task<Void, Never>?

    private var isLoadingHistoryPage: Bool = false
    private var lastHistoryRequestBefore: Int?
    private var hasReachedHistoryStart: Bool = false
    private var lastHistoryFetchTime: Date = .distantPast
    private var currentLoadId: UUID = UUID()
    private let liveQuoteInterval: UInt64 = 5 * 1_000_000_000  // 5 seconds for streaming price updates
    private var lastChartRefreshTime: Date = .distantPast
    private let marketTimeZone = TimeZone(identifier: "America/New_York") ?? .current
    private let supabase: SupabaseClient
    private var symbolIdCache: [String: UUID] = [:]
    private let isoDateFormatter: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()

    init(
        supabase: SupabaseClient = SupabaseClient(
            supabaseURL: Config.supabaseURL,
            supabaseKey: Config.supabaseAnonKey,
            options: SupabaseClientOptions(
                auth: .init(emitLocalSessionAsInitialSession: true)
            )
        )
    ) {
        self.supabase = supabase
    }

    var bars: [OHLCBar] {
        if let v2 = chartDataV2 {
            return v2.allBars
        }
        return chartData?.bars ?? []
    }

    private func barIntervalSeconds(for timeframe: Timeframe) -> Int {
        switch timeframe {
        case .m15:
            return 15 * 60
        case .h1:
            return 60 * 60
        case .h4:
            return 4 * 60 * 60
        case .d1:
            return 24 * 60 * 60
        case .w1:
            return 7 * 24 * 60 * 60
        }
    }

    func maybeLoadMoreHistory(visibleFrom: Int) {
        guard useV2API else { return }
        guard chartDataV2 == nil else { return }
        guard let current = chartData else { return }
        guard !current.bars.isEmpty else { return }
        guard !hasReachedHistoryStart else { return }
        guard !isLoadingHistoryPage else { return }

        let now = Date()
        if now.timeIntervalSince(lastHistoryFetchTime) < 1.0 {
            return
        }

        let sorted = current.bars.sorted { $0.ts < $1.ts }
        guard let first = sorted.first else { return }

        let earliestTs = Int(first.ts.timeIntervalSince1970)
        let thresholdBars = 25
        let thresholdSec = thresholdBars * barIntervalSeconds(for: timeframe)

        if visibleFrom > earliestTs + thresholdSec {
            return
        }

        if lastHistoryRequestBefore == earliestTs {
            return
        }

        isLoadingHistoryPage = true
        lastHistoryRequestBefore = earliestTs
        lastHistoryFetchTime = now

        let symbol = current.symbol
        let tf = timeframe.apiToken
        let pageSize = 400

        Task {
            do {
                let page = try await APIClient.shared.fetchChartReadPage(
                    symbol: symbol,
                    timeframe: tf,
                    before: earliestTs,
                    pageSize: pageSize
                )

                let olderBars = page.bars
                if olderBars.isEmpty {
                    hasReachedHistoryStart = true
                    isLoadingHistoryPage = false
                    return
                }

                var combined = current.bars
                combined.append(contentsOf: olderBars)

                var uniqueByTs: [Int: OHLCBar] = [:]
                uniqueByTs.reserveCapacity(combined.count)
                for bar in combined {
                    let key = Int(bar.ts.timeIntervalSince1970)
                    uniqueByTs[key] = bar
                }

                let mergedBars = uniqueByTs.values.sorted { $0.ts < $1.ts }

                chartData = ChartResponse(
                    symbol: current.symbol,
                    assetType: current.assetType,
                    timeframe: current.timeframe,
                    bars: mergedBars,
                    mlSummary: current.mlSummary,
                    indicators: current.indicators,
                    superTrendAI: current.superTrendAI,
                    dataQuality: current.dataQuality,
                    refresh: current.refresh
                )

                ChartCache.saveBars(symbol: current.symbol, timeframe: timeframe, bars: mergedBars)
                scheduleIndicatorRecalculation()
                isLoadingHistoryPage = false
            } catch {
                isLoadingHistoryPage = false
            }
        }
    }

    var selectedForecastSeries: ForecastSeries? {
        guard let horizons = chartDataV2?.mlSummary?.horizons ?? chartData?.mlSummary?.horizons else { return nil }
        if let selected = selectedForecastHorizon,
           let series = horizons.first(where: { $0.horizon == selected }) {
            return series
        }
        return horizons.first
    }

    var selectedForecastBars: [OHLCBar] {
        if let cached = _cachedSelectedForecastBars { return cached }

        let built = buildSelectedForecastBars()
        _cachedSelectedForecastBars = built
        return built
    }

    private func scheduleIndicatorRecalculation() {
        guard !bars.isEmpty else { return }
        Task { @MainActor [weak self] in
            guard let self else { return }
            self.recalculateSRIndicators()
            self.recalculateAIIndicators()
        }
    }

    private func updateSelectedForecastHorizon(from summary: MLSummary?) {
        guard let horizons = summary?.horizons, !horizons.isEmpty else {
            selectedForecastHorizon = nil
            _cachedSelectedForecastBars = nil
            return
        }

        if let current = selectedForecastHorizon,
           horizons.contains(where: { $0.horizon == current }) {
            rebuildSelectedForecastBars()
            return
        }

        selectedForecastHorizon = horizons.first?.horizon
        rebuildSelectedForecastBars()
    }

    private func buildSelectedForecastBars() -> [OHLCBar] {
        guard let summary = chartDataV2?.mlSummary ?? chartData?.mlSummary else { return [] }

        let horizons = summary.horizons
        guard !horizons.isEmpty else { return [] }

        let dailyHorizonSet: Set<String> = ["1D", "1W", "1M", "2M", "3M", "4M", "5M", "6M"]
        let isDailyMultiHorizon = horizons.count > 1
            && horizons.allSatisfy { dailyHorizonSet.contains($0.horizon.uppercased()) }

        if isDailyMultiHorizon {
            var bars: [OHLCBar] = []
            bars.reserveCapacity(horizons.count)

            for series in horizons {
                guard let targetPoint = series.points.max(by: { $0.ts < $1.ts }) else { continue }
                let date = Date(timeIntervalSince1970: TimeInterval(targetPoint.ts))
                let clampedLower = min(targetPoint.lower, targetPoint.upper)
                let clampedUpper = max(targetPoint.lower, targetPoint.upper)
                let value = targetPoint.value
                bars.append(OHLCBar(
                    ts: date,
                    open: value,
                    high: clampedUpper,
                    low: clampedLower,
                    close: value,
                    volume: 0,
                    upperBand: clampedUpper,
                    lowerBand: clampedLower,
                    confidenceScore: summary.confidence
                ))
            }

            return bars.sorted { $0.ts < $1.ts }
        }

        guard let series = selectedForecastSeries else { return [] }

        return series.points
            .map { point in
                let date = Date(timeIntervalSince1970: TimeInterval(point.ts))
                let clampedLower = min(point.lower, point.upper)
                let clampedUpper = max(point.lower, point.upper)
                let value = point.value
                return OHLCBar(
                    ts: date,
                    open: value,
                    high: clampedUpper,
                    low: clampedLower,
                    close: value,
                    volume: 0,
                    upperBand: clampedUpper,
                    lowerBand: clampedLower,
                    confidenceScore: summary.confidence
                )
            }
            .sorted { $0.ts < $1.ts }
    }

    private func rebuildSelectedForecastBars() {
        _cachedSelectedForecastBars = buildSelectedForecastBars()

        // Update chartDataV2 forecast layer when horizon changes (Fix A continuation)
        // Skip when symbol mismatch (mid–symbol switch) or chartData has no ML (cache warm-load):
        // otherwise we overwrite chartDataV2 with a hybrid that has mlSummary nil and trigger 0-forecast flicker.
        if let existingV2 = chartDataV2,
           let chartResponse = chartData,
           existingV2.symbol == chartResponse.symbol,
           chartResponse.mlSummary != nil,
           indicatorConfig.useWebChart {
            let forecastBars = _cachedSelectedForecastBars ?? []
            let newForecastLayer = LayerData(
                count: forecastBars.count,
                provider: "ml-forecast",
                data: forecastBars,
                oldestBar: forecastBars.first?.ts.ISO8601Format(),
                newestBar: forecastBars.last?.ts.ISO8601Format()
            )
            let newLayers = ChartLayers(
                historical: existingV2.layers.historical,
                intraday: existingV2.layers.intraday,
                forecast: newForecastLayer
            )
            chartDataV2 = ChartDataV2Response(
                symbol: chartResponse.symbol,
                timeframe: chartResponse.timeframe,
                layers: newLayers,
                metadata: existingV2.metadata,
                dataQuality: chartResponse.dataQuality,
                mlSummary: chartResponse.mlSummary,
                indicators: chartResponse.indicators,
                superTrendAI: chartResponse.superTrendAI
            )
        }
    }

    deinit {
        liveQuoteTask?.cancel()
        chartRefreshTask?.cancel()
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
        // Adapt AI responsiveness: higher alpha on intraday for faster adaptation
        var s = superTrendAIIndicator.settings
        s.performanceMemory = timeframe.isIntraday ? 0.25 : 0.10
        superTrendAIIndicator.settings = s
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
        calculateSuperTrendAI()
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

    func loadChart(retryOnCancel: Bool = true) async {
        // Cancel any existing load operation AND its coverage check
        loadTask?.cancel()
        coverageCheckTask?.cancel()

        let loadId = UUID()
        currentLoadId = loadId

        print("[DEBUG] ========================================")
        print("[DEBUG] ChartViewModel.loadChart() CALLED")
        print("[DEBUG] ========================================")

        guard let symbol = selectedSymbol else {
            print("[DEBUG] ChartViewModel.loadChart() - NO SYMBOL SELECTED, returning")
            chartData = nil
            loadTask = nil
            isLoading = false
            return
        }

        print("[DEBUG] - Symbol: \(symbol.ticker)")
        print("[DEBUG] - Asset Type: \(symbol.assetType)")
        print("[DEBUG] - Timeframe: \(timeframe.rawValue) (sending: \(timeframe.apiToken))")
        print("[DEBUG] - Is Intraday: \(timeframe.isIntraday)")
        print("[DEBUG] - Fetching real-time forecast overlays...")
        isLoading = true
        errorMessage = nil
        binaryForecastOverlay = nil

        // Fetch real-time forecast data asynchronously (don't block on this)
        Task {
            do {
                let isHealthy = await APIClient.shared.checkRealtimeAPIHealth()
                if isHealthy {
                    let horizon = timeframe.toHorizonString()
                    let realtimeData = try await APIClient.shared.fetchRealtimeChartData(
                        symbol: symbol.ticker,
                        horizon: horizon,
                        daysBack: 30
                    )

                    // Store the forecast overlays (not the bars, since we're using the standard API bars)
                    await MainActor.run {
                        self.realtimeChartData = realtimeData
                        print("[DEBUG] ChartViewModel.loadChart() - Real-time forecast overlays loaded: \(realtimeData.forecasts.count) forecasts")
                        // Auto-start WebSocket for live updates
                        self.startRealtimeForecastUpdates()
                    }
                }
            } catch {
                print("[DEBUG] ChartViewModel.loadChart() - Real-time forecast fetch failed: \(error.localizedDescription), continuing with standard chart...")
            }
        }

        // Try to warm-load from cache for immediate display
        if let cached = ChartCache.loadBars(symbol: symbol.ticker, timeframe: timeframe), !cached.isEmpty {
            let newestBar = cached.max(by: { $0.ts < $1.ts })
            let barAge = newestBar.map { Date().timeIntervalSince($0.ts) / 3600 } ?? 0
            print("[DEBUG] ChartViewModel.loadChart() - Using cached bars: \(cached.count), newest bar age: \(Int(barAge))h")

            // Populate legacy chartData so indicators can render quickly
            self.chartData = ChartResponse(
                symbol: symbol.ticker,
                assetType: symbol.assetType,
                timeframe: timeframe.apiToken,
                bars: cached,
                mlSummary: nil,
                indicators: nil,
                superTrendAI: nil,
                dataQuality: nil,
                refresh: nil
            )
        }

        print("[DEBUG] - Starting standard chart data fetch (fallback)...")

        
        // Sync symbol to backend for multi-timeframe backfill
        SymbolSyncService.shared.syncSymbolInBackground(symbol.ticker, source: .chartView)
        
        // SPEC-8: Trigger non-blocking coverage check for intraday timeframes
        if timeframe.isIntraday && Config.ensureCoverageEnabled {
            // Cancel any existing coverage check
            coverageCheckTask?.cancel()
            
            // Use structured concurrency (not detached) so it respects cancellation
            coverageCheckTask = Task { [weak self] in
                await self?.ensureCoverageAsync(symbol: symbol.ticker)
            }
        }

        // Create new task
        loadTask = Task {
            defer {
                if currentLoadId == loadId {
                    isLoading = false
                }
            }
            
            do {
                if useV2API && !v2UnsupportedSymbols.contains(symbol.ticker) {
                    let response: ChartDataV2Response
                    do {
                        // Backend automatically separates today's bars into intraday layer
                        // Just fetch the timeframe data and trust the layer separation
                        response = try await APIClient.shared.fetchChartV2(
                            symbol: symbol.ticker,
                            timeframe: timeframe.apiToken,
                            includeForecast: true
                        )
                    } catch {
                        print("[DEBUG] chart-data-v2 failed: \(error). Falling back to chart-read.")
                        // Track that v2 doesn't support this symbol
                        if error.localizedDescription.contains("404") || error.localizedDescription.contains("not found") {
                            v2UnsupportedSymbols.insert(symbol.ticker)
                            print("[DEBUG] Marked \(symbol.ticker) as v2-unsupported, will skip v2 on next load")
                        }
                        let fallback = try await APIClient.shared.fetchChartRead(
                            symbol: symbol.ticker,
                            timeframe: timeframe.apiToken,
                            includeMLData: true
                        )
                        let fallbackBars = fallback.bars
                        guard !Task.isCancelled else {
                            print("[DEBUG] Load cancelled after fallback fetch")
                            return
                        }

                        print("[DEBUG] ChartViewModel.loadChart() - chart-read fallback SUCCESS!")
                        print("[DEBUG] - Bars: \(fallbackBars.count)")
                        print("[DEBUG] - ML: \(fallback.mlSummary != nil ? "✓" : "✗")")

                        guard currentLoadId == loadId else { return }
                        chartData = fallback
                        updateSelectedForecastHorizon(from: fallback.mlSummary)

                        if indicatorConfig.useWebChart {
                            chartDataV2 = convertToV2Response(fallback)
                        } else {
                            chartDataV2 = nil
                        }

                        ChartCache.saveBars(symbol: symbol.ticker, timeframe: timeframe, bars: fallbackBars)
                        scheduleIndicatorRecalculation()

                        Task { await loadBinaryForecastWhenCandlesPresent(symbol: symbol.ticker) }

                        if liveQuoteTask == nil || liveQuoteTask?.isCancelled == true {
                            startLiveQuoteUpdates()
                        }

                        if chartRefreshTask == nil || chartRefreshTask?.isCancelled == true {
                            startChartAutoRefresh()
                        }
                        return
                    }

                    guard !Task.isCancelled else {
                        print("[DEBUG] Load cancelled after fetch")
                        return
                    }

                    let bars = buildBars(from: response, for: timeframe)
                    print("[DEBUG] ChartViewModel.loadChart() - chart-data-v2 SUCCESS!")
                    print("[DEBUG] - Bars: \(bars.count)")
                    print("[DEBUG] - ML: \(response.mlSummary != nil ? "✓" : "✗")")

                    guard currentLoadId == loadId else { return }
                    chartData = ChartResponse(
                        symbol: symbol.ticker,
                        assetType: symbol.assetType,
                        timeframe: timeframe.apiToken,
                        bars: bars,
                        mlSummary: response.mlSummary,
                        indicators: response.indicators,
                        superTrendAI: response.superTrendAI,
                        dataQuality: response.dataQuality,
                        refresh: nil
                    )
                    updateSelectedForecastHorizon(from: response.mlSummary)

                    if indicatorConfig.useWebChart {
                        // For d1 timeframe, create a new response with aggregated bars instead of raw h1 bars
                        if timeframe == .d1 {
                            // Create new layers with aggregated bars in historical, empty intraday
                            let aggregatedLayers = ChartLayers(
                                historical: LayerData(
                                    count: bars.count,
                                    provider: response.layers.historical.provider,
                                    data: bars,
                                    oldestBar: bars.first?.ts.ISO8601Format(),
                                    newestBar: bars.last?.ts.ISO8601Format()
                                ),
                                intraday: LayerData(
                                    count: 0,
                                    provider: "",
                                    data: [],
                                    oldestBar: nil,
                                    newestBar: nil
                                ),
                                forecast: response.layers.forecast
                            )

                            // Create new response with aggregated layers
                            chartDataV2 = ChartDataV2Response(
                                symbol: response.symbol,
                                timeframe: response.timeframe,
                                layers: aggregatedLayers,
                                metadata: response.metadata,
                                dataQuality: response.dataQuality,
                                mlSummary: response.mlSummary,
                                indicators: response.indicators,
                                superTrendAI: response.superTrendAI
                            )
                        } else {
                            chartDataV2 = response
                        }
                    } else {
                        chartDataV2 = nil
                    }

                    // Save bars to cache for instant subsequent loads
                    ChartCache.saveBars(symbol: symbol.ticker, timeframe: timeframe, bars: bars)

                    // Explicitly recalculate indicators with new data
                    scheduleIndicatorRecalculation()

                    Task { await loadBinaryForecastWhenCandlesPresent(symbol: symbol.ticker) }

                    // Start live quotes (streaming price updates every 5s during market hours)
                    if liveQuoteTask == nil || liveQuoteTask?.isCancelled == true {
                        startLiveQuoteUpdates()
                    }

                    // Start chart auto-refresh based on timeframe (15m/1h/4h/daily)
                    if chartRefreshTask == nil || chartRefreshTask?.isCancelled == true {
                        startChartAutoRefresh()
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
                        return
                    }

                    print("[DEBUG] ChartViewModel.loadChart() - SUCCESS!")
                    print("[DEBUG] - Received \(response.bars.count) bars")
                    print("[DEBUG] - Setting chartData property...")
                    guard currentLoadId == loadId else { return }
                    chartData = response
                    updateSelectedForecastHorizon(from: response.mlSummary)
                    print("[DEBUG] - chartData is now: \(chartData == nil ? "nil" : "non-nil with \(chartData!.bars.count) bars")")

                    // Save bars to cache
                    ChartCache.saveBars(symbol: symbol.ticker, timeframe: timeframe, bars: response.bars)

                    // Explicitly recalculate indicators with new data
                    scheduleIndicatorRecalculation()

                    Task { await loadBinaryForecastWhenCandlesPresent(symbol: symbol.ticker) }

                    // Start live quotes (streaming price updates every 5s during market hours)
                    if liveQuoteTask == nil || liveQuoteTask?.isCancelled == true {
                        startLiveQuoteUpdates()
                    }

                    // Start chart auto-refresh based on timeframe
                    if chartRefreshTask == nil || chartRefreshTask?.isCancelled == true {
                        startChartAutoRefresh()
                    }
                }
            
            if currentLoadId == loadId {
                errorMessage = nil
            }
        } catch is CancellationError {
            // Swallow - new request superseded this one
            print("[DEBUG] Load cancelled (CancellationError)")
            if currentLoadId == loadId {
                isLoading = false
            }
        } catch {
            guard !Task.isCancelled else {
                print("[DEBUG] Load cancelled in error handler")
                if currentLoadId == loadId {
                    isLoading = false
                }
                return
            }

            print("[DEBUG] ChartViewModel.loadChart() - ERROR: \(error)")
            if currentLoadId == loadId {
                if APIError.isSupabaseUnreachable(error),
                   let cached = ChartCache.loadBars(symbol: symbol.ticker, timeframe: timeframe), !cached.isEmpty {
                    print("[DEBUG] ChartViewModel.loadChart() - Supabase unreachable, using cached bars: \(cached.count)")
                    chartData = ChartResponse(
                        symbol: symbol.ticker,
                        assetType: symbol.assetType,
                        timeframe: timeframe.apiToken,
                        bars: cached,
                        mlSummary: nil,
                        indicators: nil,
                        superTrendAI: nil,
                        dataQuality: nil,
                        refresh: nil
                    )
                    updateSelectedForecastHorizon(from: nil)
                    if indicatorConfig.useWebChart {
                        chartDataV2 = convertToV2Response(chartData!)
                    } else {
                        chartDataV2 = nil
                    }
                    scheduleIndicatorRecalculation()
                    errorMessage = nil
                } else {
                    errorMessage = error.localizedDescription
                }
            }
        }
        print("[DEBUG] ChartViewModel.loadChart() COMPLETED")
        print("[DEBUG] - Final state: chartData=\(chartData == nil ? "nil" : "non-nil"), isLoading=\(isLoading), errorMessage=\(errorMessage ?? "nil")")
        print("[DEBUG] ========================================")
    }

    }

    /// Trigger when candles are present: call POST /api/v1/forecast/binary and set binaryForecastOverlay; on failure fall back to Supabase ml_binary_forecasts.
    private func loadBinaryForecastWhenCandlesPresent(symbol: String) async {
        do {
            try await loadBinaryForecast(symbol: symbol, horizons: [1, 5, 10])
        } catch {
            await fetchBinaryForecast(symbol: symbol)
        }
    }

    /// Fetches latest binary forecast for the symbol from Supabase ml_binary_forecasts and maps to BinaryForecastResponse.
    private func fetchBinaryForecast(symbol: String) async {
        do {
            let response = try await supabase
                .from("ml_binary_forecasts")
                .select()
                .eq("symbol", value: symbol.uppercased())
                .order("forecast_date", ascending: false)
                .limit(10)
                .execute()

            let decoder = JSONDecoder()
            decoder.dateDecodingStrategy = .iso8601
            let rows = try decoder.decode([BinaryForecastOverlay].self, from: response.data)
            if !rows.isEmpty {
                let horizons = rows.map { row in
                    BinaryForecastResponse.Horizon(
                        horizon_days: row.horizonDays,
                        label: row.label,
                        confidence: row.confidence,
                        probabilities: ["up": row.probUp, "down": row.probDown]
                    )
                }
                let resp = BinaryForecastResponse(symbol: symbol, horizons: horizons)
                await MainActor.run { self.binaryForecastOverlay = resp }
                print("[DEBUG] Binary forecast loaded for \(symbol) from Supabase: \(horizons.count) horizons")
            }
        } catch {
            print("[DEBUG] Binary forecast fetch failed for \(symbol): \(error.localizedDescription)")
        }
    }

    /// Calls POST /api/v1/forecast/binary and assigns the response to binaryForecastOverlay. Trigger when candles are present (e.g. after chartDataV2 set or symbol/horizon change).
    func loadBinaryForecast(symbol: String, horizons: [Int] = [1, 5, 10]) async throws {
        let url = Config.fastAPIURL.appendingPathComponent("api/v1/forecast/binary")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONSerialization.data(withJSONObject: ["symbol": symbol, "horizons": horizons])
        let (data, _) = try await URLSession.shared.data(for: req)
        let decoded = try JSONDecoder().decode(BinaryForecastResponse.self, from: data)
        await MainActor.run { self.binaryForecastOverlay = decoded }
    }

    func setTimeframe(_ newTimeframe: Timeframe) async {
        timeframe = newTimeframe
        // loadChart() will be called automatically by didSet
    }

    func setSymbol(_ symbol: Symbol?) async {
        // Setting selectedSymbol triggers didSet which calls loadChart() automatically
        // Do NOT call loadChart() explicitly here to avoid duplicate/cancelled requests
        selectedSymbol = symbol
    }

    /// Calls FastAPI POST /api/v1/forecast/binary for current symbol, then reloads chart so ml_forecasts overlay updates.
    func refreshBinaryForecast() async {
        guard let symbol = selectedSymbol else { return }
        do {
            try await APIClient.shared.refreshBinaryForecast(symbol: symbol.ticker, horizons: [1, 5, 10])
        } catch {
            print("[DEBUG] Refresh binary forecast failed: \(error.localizedDescription)")
        }
        await loadChart()
    }

    // MARK: - Multi-Timeframe Forecasts (Fix F)

    /// Loads forecasts for all multi-timeframe periods (m15/h1/h4/d1/w1) in parallel
    func loadMultiTimeframeForecasts() async {
        guard let symbol = selectedSymbol else { return }

        isLoadingMultiTimeframe = true
        var results: [String: ChartResponse] = [:]

        await withTaskGroup(of: (String, ChartResponse?).self) { group in
            for tf in Self.multiTimeframes {
                group.addTask {
                    do {
                        let response = try await APIClient.shared.fetchChartRead(
                            symbol: symbol.ticker,
                            timeframe: tf.apiToken,
                            includeMLData: true
                        )
                        return (tf.apiToken, response)
                    } catch {
                        print("[MultiTF] Failed to load \(tf.apiToken): \(error.localizedDescription)")
                        return (tf.apiToken, nil)
                    }
                }
            }

            for await (timeframe, response) in group {
                if let response = response {
                    results[timeframe] = response
                }
            }
        }

        multiTimeframeForecasts = results
        isLoadingMultiTimeframe = false
        print("[MultiTF] Loaded \(results.count)/\(Self.multiTimeframes.count) timeframes")
    }

    /// Toggle multi-timeframe mode and load data if needed
    func toggleMultiTimeframeMode() async {
        isMultiTimeframeMode.toggle()
        if isMultiTimeframeMode && multiTimeframeForecasts.isEmpty {
            await loadMultiTimeframeForecasts()
        }
    }

    /// Helper to build bars from response - merges all layers and sorts by timestamp
    /// For daily timeframe: aggregates today's intraday (hourly) bars into ONE daily bar
    /// For other timeframes: just concatenates the layers
    private func buildBars(from response: ChartDataV2Response, for timeframe: Timeframe) -> [OHLCBar] {
        let intraday = response.layers.intraday.data
        let historical = response.layers.historical.data

        print("[DEBUG] buildBars for \(timeframe.apiToken): hist=\(historical.count), intraday=\(intraday.count)")

        // For daily timeframe, aggregate today's intraday data into ONE daily bar
        if timeframe == .d1 {
            print("[DEBUG] ✓ Daily timeframe - aggregating intraday bars into daily bar")
            let bars = mergeHourlyIntoDailyBars(historical: historical, intraday: intraday)
            print("[DEBUG] ✓ Daily merge result: \(bars.count) bars")
            if let last = bars.last {
                print("[DEBUG]   Last bar: \(last.ts.ISO8601Format()) O:\(String(format: "%.2f", last.open)) C:\(String(format: "%.2f", last.close))")
            }
            return bars
        }

        // For other timeframes, just combine historical + intraday
        let allBars = (historical + intraday).sorted(by: { $0.ts < $1.ts })

        let histLast = historical.last?.ts.ISO8601Format() ?? "none"
        let intradayLast = intraday.last?.ts.ISO8601Format() ?? "none"
        let mergedLast = allBars.last?.ts.ISO8601Format() ?? "none"

        print("[DEBUG] 📊 buildBars(\(timeframe.apiToken)): hist=\(historical.count) (last: \(histLast)) + intraday=\(intraday.count) (last: \(intradayLast)) → merged=\(allBars.count) (last: \(mergedLast))")

        return allBars
    }

    /// Merge hourly bars into single daily bar for today
    /// - Historical bars: all past completed days
    /// - Today's bar: ONE aggregated bar from all hourly data
    /// - Today's bar updates throughout the day as hourly data changes
    private func mergeHourlyIntoDailyBars(historical: [OHLCBar], intraday: [OHLCBar]) -> [OHLCBar] {
        let now = Date()
        let calendar = Calendar.current
        let todayStart = calendar.startOfDay(for: now)

        guard !historical.isEmpty else {
            // No historical bars - aggregate intraday into single today bar
            guard !intraday.isEmpty else { return [] }
            let todayBar = aggregateIntradayToday(intraday, date: todayStart)
            return [todayBar]
        }

        let lastHistorical = historical.last!
        let lastHistIsToday = calendar.startOfDay(for: lastHistorical.ts) == todayStart

        if lastHistIsToday && !intraday.isEmpty {
            // Check if there are any intraday bars specifically for today
            let todayBars = intraday.filter { bar in
                calendar.startOfDay(for: bar.ts) == todayStart
            }

            if !todayBars.isEmpty {
                // Remove today's historical bar and replace with aggregated intraday bar
                let historicalWithoutToday = Array(historical.dropLast())
                let todayBar = aggregateIntradayToday(intraday, date: todayStart)

                let result = (historicalWithoutToday + [todayBar]).sorted(by: { $0.ts < $1.ts })
                print("[DEBUG] 📊 Daily timeframe: \(historicalWithoutToday.count) past days + 1 updated bar for today")
                return result
            } else {
                // Intraday data exists but not for today - keep historical
                return historical.sorted(by: { $0.ts < $1.ts })
            }
        } else if lastHistIsToday {
            // Today's bar exists but no hourly data - just keep historical
            return historical.sorted(by: { $0.ts < $1.ts })
        } else if !intraday.isEmpty {
            // Check if there are any intraday bars specifically for today
            let todayBars = intraday.filter { bar in
                calendar.startOfDay(for: bar.ts) == todayStart
            }

            if !todayBars.isEmpty {
                // Last bar is from past, but we have intraday data from today - append aggregated today bar
                let todayBar = aggregateIntradayToday(intraday, date: todayStart)
                let result = (historical + [todayBar]).sorted(by: { $0.ts < $1.ts })
                print("[DEBUG] 📊 Daily timeframe: \(historical.count) past days + 1 new bar for today")
                return result
            } else {
                // Intraday data exists but not for today - just return historical
                return historical.sorted(by: { $0.ts < $1.ts })
            }
        } else {
            // Last bar is from past and no hourly data - just return historical
            return historical.sorted(by: { $0.ts < $1.ts })
        }
    }

    /// Aggregate intraday hourly bars into a single daily OHLC bar for today
    /// - Open: first hour's open
    /// - High: highest hour's high
    /// - Low: lowest hour's low
    /// - Close: latest hour's close
    private func aggregateIntradayToday(_ intraday: [OHLCBar], date: Date) -> OHLCBar {
        let calendar = Calendar.current
        let todayStart = calendar.startOfDay(for: date)
        let tomorrowStart = calendar.date(byAdding: .day, value: 1, to: todayStart)!

        // Filter to ONLY today's bars (not past days from the 30-day fetch)
        let todayBars = intraday.filter { bar in
            bar.ts >= todayStart && bar.ts < tomorrowStart
        }

        let sorted = todayBars.sorted(by: { $0.ts < $1.ts })

        // When no intraday data exists for today, all OHLC values should default to 0 (not infinity)
        let open = sorted.first?.open ?? 0
        let high = sorted.map { $0.high }.max() ?? 0
        let low = sorted.map { $0.low }.min() ?? 0
        let close = sorted.last?.close ?? 0
        let volume = sorted.map { $0.volume }.reduce(0, +)

        print("[DEBUG] aggregateIntradayToday: Found \(todayBars.count) bars for \(date.ISO8601Format()), O:\(open) H:\(high) L:\(low) C:\(close)")

        return OHLCBar(
            ts: date,
            open: open,
            high: high,
            low: low,
            close: close,
            volume: volume
        )
    }

    /// Converts a ChartResponse to ChartDataV2Response format for WebChartView layered rendering
    private func convertToV2Response(_ response: ChartResponse) -> ChartDataV2Response {
        let bars = response.bars.sorted(by: { $0.ts < $1.ts })

        // Build forecast bars from ML summary horizons if available
        let forecastBars = buildSelectedForecastBars()

        let historicalLayer = LayerData(
            count: bars.count,
            provider: "chart-read",
            data: bars,
            oldestBar: bars.first?.ts.ISO8601Format(),
            newestBar: bars.last?.ts.ISO8601Format()
        )

        let intradayLayer = LayerData(
            count: 0,
            provider: "chart-read",
            data: [],
            oldestBar: nil,
            newestBar: nil
        )

        let forecastLayer = LayerData(
            count: forecastBars.count,
            provider: "ml-forecast",
            data: forecastBars,
            oldestBar: forecastBars.first?.ts.ISO8601Format(),
            newestBar: forecastBars.last?.ts.ISO8601Format()
        )

        let layers = ChartLayers(
            historical: historicalLayer,
            intraday: intradayLayer,
            forecast: forecastLayer
        )

        let metadata = ChartMetadata(
            totalBars: bars.count + forecastBars.count,
            startDate: bars.first?.ts.ISO8601Format() ?? "",
            endDate: forecastBars.last?.ts.ISO8601Format() ?? bars.last?.ts.ISO8601Format() ?? ""
        )

        return ChartDataV2Response(
            symbol: response.symbol,
            timeframe: response.timeframe,
            layers: layers,
            metadata: metadata,
            dataQuality: response.dataQuality,
            mlSummary: response.mlSummary,
            indicators: response.indicators,
            superTrendAI: response.superTrendAI
        )
    }

    private func resolveSymbolId(for ticker: String) async throws -> UUID {
        let upper = ticker.uppercased()
        if let cached = symbolIdCache[upper] {
            return cached
        }

        let results = try await APIClient.shared.searchSymbols(query: upper)
        guard let match = results.first(where: { $0.ticker.uppercased() == upper }) else {
            throw APIError.invalidSymbol(symbol: upper)
        }

        symbolIdCache[upper] = match.id
        return match.id
    }

    private func fetchChartV2ViaRPC(
        ticker: String,
        symbolId: UUID,
        timeframe: String
    ) async throws -> ChartDataV2Response {
        struct Params: Encodable {
            let p_symbol_id: UUID
            let p_timeframe: String
            let p_start_date: String
            let p_end_date: String
        }

        let start = Date(timeIntervalSince1970: 0).ISO8601Format()
        let end = Date().ISO8601Format()

        let result = try await supabase
            .rpc(
                "get_chart_data_v2",
                params: Params(
                    p_symbol_id: symbolId,
                    p_timeframe: timeframe,
                    p_start_date: start,
                    p_end_date: end
                )
            )
            .execute()

        let rows = try JSONDecoder().decode([ChartDataV2Row].self, from: result.data)

        let intradayRows = rows.filter { $0.isIntraday && !$0.isForecast }
        let forecastRows = rows.filter { $0.isForecast }
        let historicalRows = rows.filter { !$0.isIntraday && !$0.isForecast }

        let historicalBars = historicalRows.compactMap { $0.toOHLCBar() }
        let intradayBars = intradayRows.compactMap { $0.toOHLCBar() }
        let forecastBars = forecastRows.compactMap { $0.toOHLCBar() }

        let allBars = (historicalBars + intradayBars + forecastBars).sorted(by: { $0.ts < $1.ts })
        let startDate = allBars.first?.ts.ISO8601Format() ?? start
        let endDate = allBars.last?.ts.ISO8601Format() ?? end

        func layerProvider(_ rows: [ChartDataV2Row]) -> String {
            guard let first = rows.first else { return "" }
            let provider = first.provider
            if rows.allSatisfy({ $0.provider == provider }) {
                return provider
            }
            return "mixed"
        }

        let layers = ChartLayers(
            historical: LayerData(
                count: historicalBars.count,
                provider: layerProvider(historicalRows),
                data: historicalBars.sorted(by: { $0.ts < $1.ts }),
                oldestBar: historicalBars.first?.ts.ISO8601Format(),
                newestBar: historicalBars.last?.ts.ISO8601Format()
            ),
            intraday: LayerData(
                count: intradayBars.count,
                provider: layerProvider(intradayRows),
                data: intradayBars.sorted(by: { $0.ts < $1.ts }),
                oldestBar: intradayBars.first?.ts.ISO8601Format(),
                newestBar: intradayBars.last?.ts.ISO8601Format()
            ),
            forecast: LayerData(
                count: forecastBars.count,
                provider: layerProvider(forecastRows),
                data: forecastBars.sorted(by: { $0.ts < $1.ts }),
                oldestBar: forecastBars.first?.ts.ISO8601Format(),
                newestBar: forecastBars.last?.ts.ISO8601Format()
            )
        )

        let metadata = ChartMetadata(
            totalBars: historicalBars.count + intradayBars.count + forecastBars.count,
            startDate: startDate,
            endDate: endDate
        )

        return ChartDataV2Response(
            symbol: ticker,
            timeframe: timeframe,
            layers: layers,
            metadata: metadata,
            dataQuality: nil,
            mlSummary: nil,
            indicators: nil,
            superTrendAI: nil
        )
    }

    private struct ChartDataV2Row: Decodable {
        let ts: String
        let open: Double?
        let high: Double?
        let low: Double?
        let close: Double?
        let volume: Double?
        let provider: String
        let isIntraday: Bool
        let isForecast: Bool
        let dataStatus: String?
        let confidenceScore: Double?
        let upperBand: Double?
        let lowerBand: Double?

        enum CodingKeys: String, CodingKey {
            case ts, open, high, low, close, volume, provider
            case isIntraday = "is_intraday"
            case isForecast = "is_forecast"
            case dataStatus = "data_status"
            case confidenceScore = "confidence_score"
            case upperBand = "upper_band"
            case lowerBand = "lower_band"
        }

        init(from decoder: Decoder) throws {
            let container = try decoder.container(keyedBy: CodingKeys.self)

            ts = try container.decode(String.self, forKey: .ts)
            provider = try container.decode(String.self, forKey: .provider)
            isIntraday = try container.decodeIfPresent(Bool.self, forKey: .isIntraday) ?? false
            isForecast = try container.decodeIfPresent(Bool.self, forKey: .isForecast) ?? false
            dataStatus = try container.decodeIfPresent(String.self, forKey: .dataStatus)

            func decodeDouble(_ key: CodingKeys) -> Double? {
                if let v = try? container.decodeIfPresent(Double.self, forKey: key) {
                    return v
                }
                if let v = try? container.decodeIfPresent(Int64.self, forKey: key) {
                    return Double(v)
                }
                if let v = try? container.decodeIfPresent(String.self, forKey: key) {
                    return Double(v)
                }
                return nil
            }

            open = decodeDouble(.open)
            high = decodeDouble(.high)
            low = decodeDouble(.low)
            close = decodeDouble(.close)
            volume = decodeDouble(.volume)
            confidenceScore = decodeDouble(.confidenceScore)
            upperBand = decodeDouble(.upperBand)
            lowerBand = decodeDouble(.lowerBand)
        }

        func toOHLCBar() -> OHLCBar? {
            let formatters: [ISO8601DateFormatter] = {
                let f1 = ISO8601DateFormatter()
                f1.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
                let f2 = ISO8601DateFormatter()
                f2.formatOptions = [.withInternetDateTime]
                let f3 = ISO8601DateFormatter()
                f3.formatOptions = [.withInternetDateTime, .withColonSeparatorInTimeZone]
                let f4 = ISO8601DateFormatter()
                f4.formatOptions = [.withInternetDateTime, .withFractionalSeconds, .withColonSeparatorInTimeZone]
                return [f1, f2, f3, f4]
            }()

            let parsedDate: Date? = formatters.compactMap { $0.date(from: ts) }.first
            guard let date = parsedDate else { return nil }

            let c = close ?? open ?? high ?? low ?? 0
            return OHLCBar(
                ts: date,
                open: open ?? c,
                high: high ?? c,
                low: low ?? c,
                close: c,
                volume: volume ?? 0,
                upperBand: upperBand,
                lowerBand: lowerBand,
                confidenceScore: confidenceScore
            )
        }
    }

    func clearData() {
        loadTask?.cancel()
        loadTask = nil
        chartData = nil
        chartDataV2 = nil
        selectedForecastHorizon = nil
        errorMessage = nil
        isLoading = false
        liveQuote = nil
        stopLiveQuoteUpdates()
        stopChartAutoRefresh()
    }
    
    /// Force clear all caches and reload fresh data
    func forceFreshReload() async {
        guard let symbol = selectedSymbol else { return }
        
        print("[DEBUG] 🔄 Force fresh reload for \(symbol.ticker)")

        let previousChartData = chartData
        let previousChartDataV2 = chartDataV2
        
        // Clear file-based cache
        ChartCache.clear(symbol: symbol.ticker, timeframe: timeframe)
        print("[DEBUG] ✓ Cleared ChartCache for \(symbol.ticker)")
        
        // Clear URL cache
        URLCache.shared.removeAllCachedResponses()
        print("[DEBUG] ✓ Cleared URLCache")
        
        // Clear WKWebView cache (critical for WebChart)
        await clearWebViewCache()
        print("[DEBUG] ✓ Cleared WKWebView cache")
        
        // Reload from server (keep current data until new data arrives)
        print("[DEBUG] 🌐 Fetching fresh data from server...")
        await loadChart()

        // If reload was cancelled or failed and left us blank, restore previous data
        if chartData == nil {
            chartData = previousChartData
        }
        if chartDataV2 == nil {
            chartDataV2 = previousChartDataV2
        }
    }
    
    /// Clear WKWebView cache and cookies
    private func clearWebViewCache() async {
        let dataStore = WKWebsiteDataStore.default()
        let dataTypes = WKWebsiteDataStore.allWebsiteDataTypes()
        let date = Date(timeIntervalSince1970: 0)
        
        await dataStore.removeData(ofTypes: dataTypes, modifiedSince: date)
        print("[DEBUG] WKWebView cache cleared")
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
                // Clear all caches to ensure fresh data
                URLCache.shared.removeAllCachedResponses()
                ChartCache.clear(symbol: symbol.ticker, timeframe: timeframe)
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
    
    // MARK: - Chart Auto-Refresh (Timeframe-Based)
    
    /// Start automatic chart refresh based on selected timeframe
    /// Refreshes chart data at intervals matching the timeframe (15m, 1h, 4h, etc.)
    private func startChartAutoRefresh() {
        chartRefreshTask?.cancel()
        chartRefreshTask = Task(priority: .utility) { [weak self] in
            await self?.runChartRefreshLoop()
        }
    }
    
    /// Stop the automatic chart refresh timer
    private func stopChartAutoRefresh() {
        chartRefreshTask?.cancel()
        chartRefreshTask = nil
    }
    
    /// Run the chart auto-refresh loop based on timeframe interval
    private func runChartRefreshLoop() async {
        while !Task.isCancelled {
            // Get current state
            let (hasSymbol, currentTimeframe, marketOpen) = await MainActor.run {
                (selectedSymbol != nil, timeframe, isMarketHours())
            }
            
            guard hasSymbol else {
                do {
                    try await Task.sleep(nanoseconds: 60 * 1_000_000_000) // Check every minute when no symbol
                } catch { break }
                continue
            }
            
            // Only auto-refresh during market hours for intraday timeframes
            let shouldRefresh: Bool
            if currentTimeframe.isIntraday {
                shouldRefresh = marketOpen
            } else {
                // For daily/weekly, refresh less frequently (check once per hour)
                shouldRefresh = true
            }
            
            if shouldRefresh {
                // Check if enough time has passed since last refresh
                // Only calculate if lastChartRefreshTime has been set (not .distantPast)
                let timeSinceLastRefresh: TimeInterval
                if lastChartRefreshTime == .distantPast {
                    // First refresh - allow it immediately
                    timeSinceLastRefresh = currentTimeframe.minRefreshSeconds
                } else {
                    timeSinceLastRefresh = Date().timeIntervalSince(lastChartRefreshTime)
                }
                
                if timeSinceLastRefresh >= currentTimeframe.minRefreshSeconds {
                    // Update timestamp BEFORE calling loadChart to prevent concurrent refresh calls
                    lastChartRefreshTime = Date()
                    print("[DEBUG] 🔄 Auto-refreshing chart for \(currentTimeframe.displayName) (last refresh: \(Int(timeSinceLastRefresh))s ago)")
                    await loadChart()
                }
            }
            
            // Sleep for the timeframe interval
            let sleepInterval = currentTimeframe.chartRefreshInterval
            do {
                try await Task.sleep(nanoseconds: sleepInterval)
            } catch { break }
        }
    }
    
    // MARK: - SPEC-8: Backfill Orchestration
    
    /// Non-blocking coverage check for intraday data
    /// Triggers server-side backfill if needed without blocking UI
    private func ensureCoverageAsync(symbol: String) async {
        // Check for cancellation early
        guard !Task.isCancelled else {
            print("[DEBUG] 🛑 Coverage check cancelled before starting")
            return
        }
        
        // Use 730 days (2 years) for intraday backfill
        let windowDays = timeframe.isIntraday ? 730 : 365

        do {
            let response = try await APIClient.shared.ensureCoverage(
                symbol: symbol,
                timeframe: timeframe.apiToken,
                windowDays: windowDays
            )
            
            // Check for cancellation after network call
            guard !Task.isCancelled else {
                print("[DEBUG] 🛑 Coverage check cancelled after API call")
                return
            }

            await MainActor.run {
                // Determine if we already have bars displayed; if so, avoid showing banner
                let hasBars = !(self.chartData?.bars.isEmpty ?? true)

                self.backfillJobId = response.jobDefId
                self.backfillProgress = response.backfillProgress
                // Only show hydrating state if gaps detected AND we don't already have bars
                self.isHydrating = (response.status == "gaps_detected") && !hasBars

                if response.status == "coverage_complete" || response.coverageStatus.gapsFound == 0 {
                    print("[DEBUG] ✅ Coverage complete for \(symbol) \(timeframe.apiToken)")
                    self.hydrationBanner = nil
                    self.backfillProgress = nil
                    self.stopHydrationPoller()
                } else {
                    print("[DEBUG] 🔄 Gaps detected for \(symbol) \(timeframe.apiToken), orchestrator will hydrate")
                    print("[DEBUG] - Job def ID: \(response.jobDefId)")
                    print("[DEBUG] - Gaps found: \(response.coverageStatus.gapsFound)")

                    // Update banner only if chart is empty (to avoid confusing the user)
                    if !hasBars {
                        if let progress = response.backfillProgress {
                            self.hydrationBanner = "Backfilling 2 years... \(progress.progressPercent)% (\(progress.barsWritten) bars)"
                            print("[DEBUG] - Backfill progress: \(progress.progressPercent)% (\(progress.completedSlices)/\(progress.totalSlices) slices)")
                        } else {
                            self.hydrationBanner = "Backfill starting..."
                        }
                    } else {
                        self.hydrationBanner = nil
                    }

                    // Subscribe/poll for progress (non-blocking)
                    self.subscribeToJobProgress(symbol: symbol, timeframe: timeframe.apiToken)
                    self.startHydrationPoller(symbol: symbol)
                }
            }
        } catch {
            print("[DEBUG] ⚠️ ensureCoverage failed (non-fatal): \(error)")
        }
    }
    
    // MARK: - SPEC-8: Realtime Progress Subscription

    /// Subscribe to job_runs table for real-time progress updates
    /// Note: Currently using polling approach in startHydrationPoller() instead
    /// Realtime WebSocket updates are unreliable, polling every 15s works better
    private func subscribeToJobProgress(symbol: String, timeframe: String) {
        // No-op: Using polling approach instead
        // See startHydrationPoller() for actual progress tracking
        print("[DEBUG] Realtime subscription skipped, using polling instead")
    }

    /// Stop Realtime subscription
    private func stopRealtimeSubscription() {
        realtimeTask?.cancel()
        realtimeTask = nil
    }
    
    // MARK: - Hydration Poller (fallback when Realtime is unavailable)
    private func startHydrationPoller(symbol: String) {
        hydrationPollTask?.cancel()
        hydrationPollTask = Task { [weak self] in
            guard let self else { return }
            // Increase to 40 attempts (~10 minutes) for 2-year backfills
            let maxAttempts = 40
            for attempt in 0..<maxAttempts {
                try? await Task.sleep(nanoseconds: 15 * 1_000_000_000)
                guard !Task.isCancelled else {
                    print("[DEBUG] 🛑 Hydration poller cancelled")
                    break
                }
                do {
                    // Poll ensure-coverage for progress updates
                    let windowDays = self.timeframe.isIntraday ? 730 : 365
                    let coverageResponse = try await APIClient.shared.ensureCoverage(
                        symbol: symbol,
                        timeframe: self.timeframe.apiToken,
                        windowDays: windowDays
                    )

                    var shouldBreak = false
                    // Update progress on main thread
                    await MainActor.run {
                        // Clear immediately if coverage is complete (progress may be nil)
                        if coverageResponse.status == "coverage_complete" || coverageResponse.coverageStatus.gapsFound == 0 {
                            self.isHydrating = false
                            self.hydrationBanner = nil
                            self.backfillProgress = nil
                            print("[DEBUG] ✅ Coverage complete (poll), clearing banner")
                            shouldBreak = true
                            return
                        }

                        // Update progress
                        self.backfillProgress = coverageResponse.backfillProgress

                        // Only show banner if the chart is empty
                        let hasBars = !(self.chartData?.bars.isEmpty ?? true)

                        if let progress = coverageResponse.backfillProgress {
                            if !hasBars {
                                self.hydrationBanner = "Backfilling 2 years... \(progress.progressPercent)% (\(progress.barsWritten) bars)"
                                print("[DEBUG] 📊 Backfill progress: \(progress.progressPercent)% (\(progress.completedSlices)/\(progress.totalSlices) slices, \(progress.barsWritten) bars)")
                            } else {
                                self.hydrationBanner = nil
                                self.isHydrating = false
                            }

                            // Complete
                            if progress.progressPercent >= 100 {
                                self.isHydrating = false
                                self.hydrationBanner = nil
                                self.backfillProgress = nil
                                print("[DEBUG] ✅ Backfill complete!")
                                shouldBreak = true
                            }
                        } else {
                            // No progress payload, don't show banner if we already have bars
                            if hasBars {
                                self.hydrationBanner = nil
                                self.isHydrating = false
                            }
                        }
                    }
                    if shouldBreak {
                        print("[DEBUG] ✅ Hydration poll complete at attempt \(attempt + 1)")
                        break
                    }

                    // Fetch updated chart data via chart-read (refresh-on-read)
                    let peek = try await APIClient.shared.fetchChartRead(
                        symbol: symbol,
                        timeframe: self.timeframe.apiToken,
                        includeMLData: true
                    )

                    // Always update chart data (progressive refresh)
                    await MainActor.run {
                        self.chartDataV2 = nil
                        self.chartData = peek
                    }

                    // Save to cache
                    ChartCache.saveBars(symbol: symbol, timeframe: self.timeframe, bars: peek.bars)

                } catch {
                    print("[DEBUG] Hydration poll error: \(error)")
                }
            }
        }
    }

    private func stopHydrationPoller() {
        hydrationPollTask?.cancel()
        hydrationPollTask = nil
    }
    
    /// Stop coverage check task
    private func stopCoverageCheck() {
        coverageCheckTask?.cancel()
        coverageCheckTask = nil
    }
    
    // MARK: - Volume Profile Calculator
    
    /// Calculate volume profile from OHLC bars
    /// Groups volume by price levels to identify support/resistance zones
    func calculateVolumeProfile(bucketSize: Double = 0.50) {
        let bars: [OHLCBar]
        if let chartData = chartDataV2 {
            bars = chartData.allBars
        } else if let chartData = chartData {
            bars = chartData.bars
        } else {
            volumeProfile = []
            return
        }
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

    // MARK: - Stale Data Detection

    /// Validate data recency for intraday timeframes
    private func validateDataRecency(bars: [OHLCBar], timeframe: Timeframe) -> (isStale: Bool, age: TimeInterval, recommendation: String) {
        guard let lastBar = bars.last else {
            return (isStale: true, age: 0, recommendation: "No data available")
        }

        let age = Date().timeIntervalSince(lastBar.ts)
        let marketOpen = MarketHours.isMarketOpen()

        let maxAge: TimeInterval = {
            if timeframe.isIntraday {
                if marketOpen {
                    switch timeframe {
                    case .m15: return 25 * 60
                    case .h1: return 2 * 60 * 60
                    case .h4: return 5 * 60 * 60
                    case .d1, .w1: return 48 * 60 * 60
                    }
                } else {
                    switch timeframe {
                    case .m15: return 2 * 60 * 60
                    case .h1: return 6 * 60 * 60
                    case .h4: return 12 * 60 * 60
                    case .d1, .w1: return 72 * 60 * 60
                    }
                }
            }

            switch timeframe {
            case .d1:
                return 48 * 60 * 60
            case .w1:
                return 14 * 24 * 60 * 60
            case .m15, .h1, .h4:
                // Shouldn't happen because these are intraday, but keep a safe default
                return 6 * 60 * 60
            }
        }()

        let isStale = age > maxAge

        let recommendation: String
        if isStale {
            if timeframe.isIntraday {
                if marketOpen {
                    recommendation = "Data is \(Int(age))s old during market hours - TRIGGER BACKFILL"
                } else {
                    recommendation = "Market closed, \(Int(age))s old exceeds threshold"
                }
            } else {
                recommendation = "Daily/weekly data is \(Int(age))s old - TRIGGER BACKFILL"
            }
        } else {
            recommendation = "Data is fresh (\(Int(age))s old)"
        }

        return (isStale: isStale, age: age, recommendation: recommendation)
    }

    /// Build bars from response and check for staleness
    func buildBarsWithStalenessCheck(from response: ChartDataV2Response, for timeframe: Timeframe) -> (bars: [OHLCBar], report: StalenessReport) {
        let bars = buildBars(from: response, for: timeframe)
        let recency = validateDataRecency(bars: bars, timeframe: timeframe)

        let report = StalenessReport(
            barCount: bars.count,
            lastBarTimestamp: bars.last?.ts,
            dataAge: recency.age,
            isStale: recency.isStale,
            timeframe: timeframe,
            marketOpen: MarketHours.isMarketOpen(),
            recommendation: recency.recommendation
        )

        print("[DEBUG] 📊 Staleness Check")
        print("[DEBUG] - Bar count: \(bars.count)")
        print("[DEBUG] - Last timestamp: \(bars.last?.ts.ISO8601Format() ?? "none")")
        print("[DEBUG] - Data age: \(String(format: "%.0f", recency.age))s")
        print("[DEBUG] - Is stale: \(recency.isStale)")
        print("[DEBUG] - Recommendation: \(recency.recommendation)")

        if recency.isStale && timeframe.isIntraday {
            print("[DEBUG] ⚠️ STALE INTRADAY DATA: age=\(String(format: "%.0f", recency.age))s, max=\(MarketHours.isMarketOpen() ? 300 : 3600)s")
        }

        return (bars: bars, report: report)
    }
}

// MARK: - Staleness Report

struct StalenessReport {
    let barCount: Int
    let lastBarTimestamp: Date?
    let dataAge: TimeInterval
    let isStale: Bool
    let timeframe: Timeframe
    let marketOpen: Bool
    let recommendation: String

    var summary: String {
        """
        📊 Data Recency Report
        ├─ Bars: \(barCount)
        ├─ Last: \(lastBarTimestamp?.ISO8601Format() ?? "none")
        ├─ Age: \(Int(dataAge))s
        ├─ Stale: \(isStale ? "⚠️ YES" : "✅ NO")
        ├─ Market: \(marketOpen ? "OPEN" : "CLOSED")
        └─ Action: \(recommendation)
        """
    }
}

// MARK: - Market Hours Detection

struct MarketHours {
    private static let marketTimeZone = TimeZone(identifier: "America/New_York") ?? .current

    static func isMarketOpen(at date: Date = Date()) -> Bool {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = marketTimeZone
        let components = calendar.dateComponents([.hour, .minute, .weekday], from: date)

        guard let hour = components.hour,
              let minute = components.minute,
              let weekday = components.weekday else {
            return false
        }

        // Monday-Friday (2-6 in Calendar weekday)
        let isWeekday = (2...6).contains(weekday)
        let minutes = hour * 60 + minute
        let openMinutes = 9 * 60 + 30  // 9:30 AM ET
        let closeMinutes = 16 * 60      // 4:00 PM ET

        return isWeekday && minutes >= openMinutes && minutes <= closeMinutes
    }
}
