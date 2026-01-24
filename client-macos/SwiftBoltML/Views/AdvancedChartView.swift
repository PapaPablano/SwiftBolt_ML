import SwiftUI
import Charts
import Combine

// MARK: - Chart Color Palette
/// Professional, high-contrast colors for chart elements - optimized for dark mode visibility
struct ChartColors {
    // Moving Averages - distinct, easily differentiable colors with high contrast
    static let sma20 = Color(red: 0.3, green: 0.7, blue: 1.0)      // Bright sky blue
    static let sma50 = Color(red: 1.0, green: 0.65, blue: 0.0)     // Bright orange
    static let sma200 = Color(red: 0.85, green: 0.4, blue: 0.95)   // Bright purple
    static let ema9 = Color(red: 0.0, green: 1.0, blue: 0.75)      // Bright teal/cyan
    static let ema21 = Color(red: 1.0, green: 0.5, blue: 0.7)      // Bright pink/magenta

    // Bollinger Bands - lighter for visibility
    static let bollingerBand = Color(red: 0.7, green: 0.7, blue: 0.85)  // Light purple-gray
    static let bollingerFill = Color(red: 0.6, green: 0.6, blue: 0.75).opacity(0.12)

    // Candlesticks
    static let bullish = Color(red: 0.2, green: 0.85, blue: 0.4)   // Bright green
    static let bearish = Color(red: 1.0, green: 0.3, blue: 0.25)   // Bright red

    // Forecast
    static let forecastBullish = Color(red: 0.3, green: 0.9, blue: 0.5)
    static let forecastBearish = Color(red: 1.0, green: 0.35, blue: 0.3)
    static let forecastNeutral = Color(red: 1.0, green: 0.75, blue: 0.0)

    // SuperTrend - brighter to stand out from candlesticks
    static let superTrendBull = Color(red: 0.0, green: 1.0, blue: 0.5)     // Neon green
    static let superTrendBear = Color(red: 1.0, green: 0.25, blue: 0.5)    // Hot pink/red

    // Oscillators - MACD (high contrast pair)
    static let macdLine = Color(red: 0.2, green: 0.85, blue: 1.0)    // Bright cyan
    static let macdSignal = Color(red: 1.0, green: 0.6, blue: 0.1)   // Bright orange
    static let macdHistogramPos = Color(red: 0.25, green: 0.85, blue: 0.45)
    static let macdHistogramNeg = Color(red: 1.0, green: 0.35, blue: 0.3)

    // Stochastic (very distinct pair)
    static let stochasticK = Color(red: 0.2, green: 0.85, blue: 1.0)   // Bright cyan
    static let stochasticD = Color(red: 1.0, green: 0.6, blue: 0.1)    // Bright orange

    // KDJ - MAXIMUM CONTRAST - three completely different colors
    static let kdjK = Color(red: 0.3, green: 1.0, blue: 0.3)       // BRIGHT GREEN
    static let kdjD = Color(red: 1.0, green: 0.3, blue: 0.3)       // BRIGHT RED
    static let kdjJ = Color(red: 0.3, green: 0.5, blue: 1.0)       // BRIGHT BLUE

    // ADX - three distinct colors
    static let adx = Color(red: 1.0, green: 0.9, blue: 0.1)         // Bright yellow/gold
    static let plusDI = Color(red: 0.3, green: 1.0, blue: 0.5)      // Bright green
    static let minusDI = Color(red: 1.0, green: 0.4, blue: 0.3)     // Bright red

    // RSI - brighter purple for better visibility
    static let rsi = Color(red: 0.8, green: 0.5, blue: 1.0)         // Bright purple/magenta

    // ATR - bright cyan
    static let atr = Color(red: 0.2, green: 0.9, blue: 1.0)         // Bright cyan

    // Reference lines
    static let overbought = Color.red.opacity(0.5)
    static let oversold = Color.green.opacity(0.5)
    static let midline = Color.gray.opacity(0.4)
}

struct AdvancedChartView: View {
    let bars: [OHLCBar]
    let sma20: [IndicatorDataPoint]
    let sma50: [IndicatorDataPoint]
    let ema9: [IndicatorDataPoint]
    let ema21: [IndicatorDataPoint]
    let rsi: [IndicatorDataPoint]
    let config: IndicatorConfig
    let mlSummary: MLSummary?

    // New Phase 7 indicators
    let macdLine: [IndicatorDataPoint]
    let macdSignal: [IndicatorDataPoint]
    let macdHistogram: [IndicatorDataPoint]
    let stochasticK: [IndicatorDataPoint]
    let stochasticD: [IndicatorDataPoint]
    let kdjK: [IndicatorDataPoint]
    let kdjD: [IndicatorDataPoint]
    let kdjJ: [IndicatorDataPoint]
    let adxLine: [IndicatorDataPoint]
    let plusDI: [IndicatorDataPoint]
    let minusDI: [IndicatorDataPoint]
    let superTrendLine: [IndicatorDataPoint]
    let superTrendTrend: [Int]
    let superTrendStrength: [IndicatorDataPoint]
    let bollingerUpper: [IndicatorDataPoint]
    let bollingerMiddle: [IndicatorDataPoint]
    let bollingerLower: [IndicatorDataPoint]
    let atr: [IndicatorDataPoint]
    let selectedForecastHorizon: String?

    // Support & Resistance Indicators
    var pivotIndicator: PivotLevelsIndicator?
    var polyIndicator: PolynomialRegressionIndicator?
    var logisticIndicator: LogisticRegressionIndicator?

    // SuperTrend AI Properties
    var superTrendAIIndicator: SuperTrendAIIndicator?
    var superTrendAISignals: [SuperTrendSignal] = []

    @State private var selectedBar: OHLCBar?
    @State private var selectedIndex: Int?

    @State private var superTrendAIUpdateTick: Int = 0
    @State private var savedVisibleRange: ClosedRange<Int>?
    /// Tokenized indicator config to detect toggle changes
    private var configToken: String {
        "\(config.showRSI)-\(config.showMACD)-\(config.showStochastic)-\(config.showKDJ)-\(config.showADX)-\(config.showATR)-\(config.showVolume)-\(config.showSuperTrend)-\(config.showSuperTrendAIPanel)"
    }

    // Chart pan/zoom state
    @State private var visibleRange: ClosedRange<Int>
    @State private var barsToShow: Int = 100 // Default visible bars

    // Native scroll position binding (synced with visibleRange)
    @State private var scrollPosition: Int = 0

    init(
        bars: [OHLCBar],
        sma20: [IndicatorDataPoint],
        sma50: [IndicatorDataPoint],
        ema9: [IndicatorDataPoint],
        ema21: [IndicatorDataPoint],
        rsi: [IndicatorDataPoint],
        config: IndicatorConfig,
        mlSummary: MLSummary? = nil,
        macdLine: [IndicatorDataPoint] = [],
        macdSignal: [IndicatorDataPoint] = [],
        macdHistogram: [IndicatorDataPoint] = [],
        stochasticK: [IndicatorDataPoint] = [],
        stochasticD: [IndicatorDataPoint] = [],
        kdjK: [IndicatorDataPoint] = [],
        kdjD: [IndicatorDataPoint] = [],
        kdjJ: [IndicatorDataPoint] = [],
        adxLine: [IndicatorDataPoint] = [],
        plusDI: [IndicatorDataPoint] = [],
        minusDI: [IndicatorDataPoint] = [],
        superTrendLine: [IndicatorDataPoint] = [],
        superTrendTrend: [Int] = [],
        superTrendStrength: [IndicatorDataPoint] = [],
        bollingerUpper: [IndicatorDataPoint] = [],
        bollingerMiddle: [IndicatorDataPoint] = [],
        bollingerLower: [IndicatorDataPoint] = [],
        atr: [IndicatorDataPoint] = [],
        selectedForecastHorizon: String? = nil,
        pivotIndicator: PivotLevelsIndicator? = nil,
        polyIndicator: PolynomialRegressionIndicator? = nil,
        logisticIndicator: LogisticRegressionIndicator? = nil,
        superTrendAIIndicator: SuperTrendAIIndicator? = nil,
        superTrendAISignals: [SuperTrendSignal] = []
    ) {
        self.bars = bars
        self.sma20 = sma20
        self.sma50 = sma50
        self.ema9 = ema9
        self.ema21 = ema21
        self.rsi = rsi
        self.config = config
        self.mlSummary = mlSummary
        self.macdLine = macdLine
        self.macdSignal = macdSignal
        self.macdHistogram = macdHistogram
        self.stochasticK = stochasticK
        self.stochasticD = stochasticD
        self.kdjK = kdjK
        self.kdjD = kdjD
        self.kdjJ = kdjJ
        self.adxLine = adxLine
        self.plusDI = plusDI
        self.minusDI = minusDI
        self.superTrendLine = superTrendLine
        self.superTrendTrend = superTrendTrend
        self.superTrendStrength = superTrendStrength
        self.bollingerUpper = bollingerUpper
        self.bollingerMiddle = bollingerMiddle
        self.bollingerLower = bollingerLower
        self.atr = atr
        self.selectedForecastHorizon = selectedForecastHorizon
        self.pivotIndicator = pivotIndicator
        self.polyIndicator = polyIndicator
        self.logisticIndicator = logisticIndicator
        self.superTrendAIIndicator = superTrendAIIndicator
        self.superTrendAISignals = superTrendAISignals

        // Initialize visible range to show most recent bars
        let count = bars.count
        let endIndex = max(0, count - 1)
        let ninetyDaysAgo = bars.last?.ts.addingTimeInterval(-90 * 24 * 60 * 60)
        let startIndex: Int
        if let ninetyDaysAgo {
            startIndex = bars.firstIndex(where: { $0.ts >= ninetyDaysAgo }) ?? max(0, endIndex - 100 + 1)
        } else {
            startIndex = max(0, endIndex - 100 + 1)
        }
        let initialBarsToShow = max(10, min(count, endIndex - startIndex + 1))
        _visibleRange = State(initialValue: startIndex...endIndex)
        _barsToShow = State(initialValue: initialBarsToShow)
        _scrollPosition = State(initialValue: startIndex)
    }

    // Create indexed versionsx for even spacing (TradingView style)
    private var indexedBars: [(index: Int, bar: OHLCBar)] {
        bars.enumerated().map { (index: $0.offset, bar: $0.element) }
    }

    // Visible bars based on scroll position - optimized to avoid O(N) mapping
    private var visibleBars: [(index: Int, bar: OHLCBar)] {
        let startIdx = max(0, visibleRange.lowerBound - 20) // 20 bar buffer
        let endIdx = min(bars.count - 1, visibleRange.upperBound + 20)
        guard startIdx <= endIdx else { return [] }
        
        var result: [(index: Int, bar: OHLCBar)] = []
        result.reserveCapacity(endIdx - startIdx + 1)
        for i in startIdx...endIdx {
            result.append((index: i, bar: bars[i]))
        }
        return result
    }

    // Calculate dynamic height for price chart based on active panels
    private var priceChartHeight: CGFloat {
        var height: CGFloat = 500
        var activePanels = 0

        if config.showRSI { activePanels += 1 }
        if config.showMACD { activePanels += 1 }
        if config.showStochastic { activePanels += 1 }
        if config.showKDJ { activePanels += 1 }
        if config.showADX { activePanels += 1 }
        if config.showATR { activePanels += 1 }
        if config.showVolume { activePanels += 1 }

        // Reduce price chart height based on active panels
        height -= CGFloat(min(activePanels, 4)) * 50
        return max(250, height)
    }

    // Clamp visible range to real bars only (excludes forecast bars)
    // Prevents sub-panels from rendering in forecast-only space
    private var visibleBarsOnlyRange: ClosedRange<Int> {
        let lastBar = max(0, bars.count - 1)
        guard lastBar >= 0 else { return 0...0 }
        let start = max(0, min(visibleRange.lowerBound, lastBar))
        let end = max(start, min(visibleRange.upperBound, lastBar))
        return start...end
    }

    var body: some View {
        ScrollView(.vertical, showsIndicators: true) {
            VStack(spacing: 0) {
                // Chart controls
                chartControls
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color(nsColor: .controlBackgroundColor))

                Divider()

                // Main price chart with indicators
                priceChartView
                    .frame(height: priceChartHeight)

                // RSI Panel
                if config.showRSI {
                    Divider()
                    rsiChartView
                        .frame(height: 100)
                        .id("rsi-\(visibleBarsOnlyRange.lowerBound)-\(visibleBarsOnlyRange.upperBound)-\(rsi.count)-\(bars.count)")
                        .allowsHitTesting(false)
                }

                // MACD Panel
                if config.showMACD {
                    Divider()
                    MACDPanelView(
                        bars: bars,
                        macdLine: macdLine,
                        signalLine: macdSignal,
                        histogram: macdHistogram,
                        visibleRange: visibleBarsOnlyRange
                    )
                    .frame(height: 100)
                    .id("macd-\(visibleBarsOnlyRange.lowerBound)-\(visibleBarsOnlyRange.upperBound)-\(macdLine.count)-\(macdSignal.count)-\(macdHistogram.count)")
                    .allowsHitTesting(false)
                }

                // Stochastic Panel
                if config.showStochastic {
                    Divider()
                    StochasticPanelView(
                        bars: bars,
                        kLine: stochasticK,
                        dLine: stochasticD,
                        visibleRange: visibleBarsOnlyRange
                    )
                    .frame(height: 100)
                    .id("stoch-\(visibleBarsOnlyRange.lowerBound)-\(visibleBarsOnlyRange.upperBound)-\(stochasticK.count)-\(stochasticD.count)")
                    .allowsHitTesting(false)
                }

                // KDJ Panel
                if config.showKDJ {
                    Divider()
                    KDJPanelView(
                        bars: bars,
                        kLine: kdjK,
                        dLine: kdjD,
                        jLine: kdjJ,
                        visibleRange: visibleBarsOnlyRange
                    )
                    .frame(height: 100)
                    .id("kdj-\(visibleBarsOnlyRange.lowerBound)-\(visibleBarsOnlyRange.upperBound)-\(kdjK.count)-\(kdjD.count)-\(kdjJ.count)")
                    .allowsHitTesting(false)
                }

                // ADX Panel
                if config.showADX {
                    Divider()
                    ADXPanelView(
                        bars: bars,
                        adxLine: adxLine,
                        plusDI: plusDI,
                        minusDI: minusDI,
                        visibleRange: visibleBarsOnlyRange
                    )
                    .frame(height: 100)
                    .id("adx-\(visibleBarsOnlyRange.lowerBound)-\(visibleBarsOnlyRange.upperBound)-\(adxLine.count)-\(plusDI.count)-\(minusDI.count)")
                    .allowsHitTesting(false)
                }

                // ATR Panel
                if config.showATR {
                    Divider()
                    ATRPanelView(
                        bars: bars,
                        atrLine: atr,
                        visibleRange: visibleBarsOnlyRange
                    )
                    .frame(height: 80)
                    .id("atr-\(visibleBarsOnlyRange.lowerBound)-\(visibleBarsOnlyRange.upperBound)-\(atr.count)")
                    .allowsHitTesting(false)
                }

                // SuperTrend Strength Panel (shown when SuperTrend is enabled)
                if config.showSuperTrend {
                    Divider()
                    superTrendStrengthPanel
                        .frame(height: 80)
                }

                // SuperTrend AI Panel (dedicated panel with AI line and signals)
                if config.showSuperTrendAIPanel {
                    Divider()
                    SuperTrendChartView(
                        bars: bars,
                        superTrendAIIndicator: superTrendAIIndicator,
                        signals: superTrendAISignals,
                        visibleRange: visibleRange,
                        scrollPosition: $scrollPosition,
                        barsToShow: barsToShow
                    )
                    .frame(height: 150)
                }

                // Volume Panel
                if config.showVolume {
                    Divider()
                    volumeChartView
                        .frame(height: 80)
                        .id("vol-\(visibleBarsOnlyRange.lowerBound)-\(visibleBarsOnlyRange.upperBound)-\(bars.count)")
                        .allowsHitTesting(false)
                }
            }
            .id(configToken) // Force VStack rebuild when any panel visibility changes
        }
        .onChange(of: bars.count) { oldCount, newCount in
            // Reset to latest bars when data changes
            if oldCount != newCount && newCount > 0 {
                resetToLatest()
                // Clear selection to avoid stale overlays
                selectedBar = nil
                selectedIndex = nil
            }
        }
        .onReceive(superTrendAIIndicator?.objectWillChange.eraseToAnyPublisher() ?? Empty().eraseToAnyPublisher()) { _ in
            superTrendAIUpdateTick += 1
        }
        // Preserve visible range when indicator config toggles
        .onChange(of: configToken, initial: false) { _, _ in
            let saved = visibleRange
            DispatchQueue.main.async {
                let clampedStart = max(0, min(saved.lowerBound, maxChartIndex))
                let clampedEnd = min(maxChartIndex, max(saved.upperBound, clampedStart))
                visibleRange = clampedStart...clampedEnd
                barsToShow = clampedEnd - clampedStart + 1
                scrollPosition = clampedStart
            }
        }
    }

    // MARK: - Chart Controls

    private var chartControls: some View {
        HStack(spacing: 12) {
            // Data range info
            let startIdx = max(0, min(scrollPosition, max(0, bars.count - 1)))
            let endIdx = max(0, min(scrollPosition + barsToShow - 1, max(0, bars.count - 1)))
            let visibleCount = bars.isEmpty ? 0 : (endIdx - startIdx + 1)

            Text("Visible \(visibleCount) / Total \(bars.count)")
                .font(.caption.monospacedDigit())
                .foregroundStyle(.secondary)

            if bars.count > 0 {
                Text("•")
                    .foregroundStyle(.tertiary)
                Text("\(formatDate(bars[startIdx].ts)) - \(formatDate(bars[endIdx].ts))")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            // Zoom controls
            Button(action: zoomOut) {
                Image(systemName: "minus.magnifyingglass")
                    .font(.caption)
            }
            .buttonStyle(.borderless)
            .disabled(barsToShow >= bars.count)
            .help("Zoom out (show more bars)")

            Button(action: zoomIn) {
                Image(systemName: "plus.magnifyingglass")
                    .font(.caption)
            }
            .buttonStyle(.borderless)
            .disabled(barsToShow <= 10)
            .help("Zoom in (show fewer bars)")

            // Pan controls (complement native scroll)
            Button(action: panLeft) {
                Image(systemName: "chevron.left")
                    .font(.caption)
            }
            .buttonStyle(.borderless)
            .disabled(scrollPosition <= 0)
            .help("Pan left")

            Button(action: panRight) {
                Image(systemName: "chevron.right")
                    .font(.caption)
            }
            .buttonStyle(.borderless)
            .disabled(scrollPosition >= maxChartIndex - barsToShow + 1)
            .help("Pan right")

            // Reset to most recent
            Button("Latest") {
                resetToLatest()
            }
            .buttonStyle(.borderless)
            .font(.caption)
            .help("Jump to most recent data")

            Divider()
                .frame(height: 16)

            // Scroll hint
            Text("⌘ Scroll to pan")
                .font(.caption2)
                .foregroundStyle(.tertiary)
        }
    }

    // MARK: - Price Chart

    private var priceChartView: some View {
        ZStack {
            // Main chart
            priceChart

            // S&R Canvas Overlay (Polynomial & Logistic regression curves)
            // NOTE: Pivot Levels are now drawn using native Chart RuleMarks inside the Chart
            if config.showPolynomialSR || config.showLogisticSR {
                GeometryReader { geometry in
                    srOverlay(size: geometry.size)
                }
            }
        }
    }

    // S&R Canvas Overlay (for Polynomial and Logistic S&R - Pivot Levels now use native Chart marks)
    private func srOverlay(size: CGSize) -> some View {
        Canvas { context, _ in
            let priceRange = visiblePriceRange
            let priceMin = priceRange.lowerBound
            let priceMax = priceRange.upperBound

            // NOTE: Pivot Levels are now drawn using native Chart RuleMarks
            // See pivotLevelMarks(indicator:) for the implementation

            // Draw Polynomial Regression S&R curves
            if config.showPolynomialSR, let indicator = polyIndicator {
                // Helper to convert bar index to screen X
                // Uses scrollPosition for accurate coordinate mapping with native scrolling
                // Chart uses chartXVisibleDomain(length: barsToShow), so domain spans barsToShow units
                func indexToX(_ index: Int) -> CGFloat {
                    let domainMin = CGFloat(scrollPosition)
                    let domainMax = CGFloat(scrollPosition + barsToShow)
                    let domainSpan = domainMax - domainMin
                    guard domainSpan > 0 else { return size.width / 2 }
                    return ((CGFloat(index) - domainMin) / domainSpan) * size.width
                }

                // Helper to convert price to screen Y
                func priceToY(_ price: Double) -> CGFloat {
                    let range = priceMax - priceMin
                    guard range > 0 else { return size.height / 2 }
                    return size.height * (1 - (price - priceMin) / range)
                }

                #if DEBUG
                // Debug: Print first/last point info for support line
                if let supLine = indicator.supportLine,
                   let firstPt = supLine.predictedPoints.first,
                   let lastPt = supLine.predictedPoints.last {
                    let firstX = indexToX(Int(firstPt.x))
                    let lastX = indexToX(Int(lastPt.x))
                    print("[Canvas] Support: \(supLine.predictedPoints.count) pts, price[\(String(format: "%.1f", firstPt.y))->\(String(format: "%.1f", lastPt.y))], screenX[\(String(format: "%.0f", firstX))->\(String(format: "%.0f", lastX))]")
                }
                if let resLine = indicator.resistanceLine,
                   let firstPt = resLine.predictedPoints.first,
                   let lastPt = resLine.predictedPoints.last {
                    let firstX = indexToX(Int(firstPt.x))
                    let lastX = indexToX(Int(lastPt.x))
                    print("[Canvas] Resistance: \(resLine.predictedPoints.count) pts, price[\(String(format: "%.1f", firstPt.y))->\(String(format: "%.1f", lastPt.y))], screenX[\(String(format: "%.0f", firstX))->\(String(format: "%.0f", lastX))]")
                }
                #endif

                // Draw resistance curve
                if let resLine = indicator.resistanceLine {
                    var path = Path()
                    var started = false
                    let priceRange = priceMax - priceMin

                    for point in resLine.predictedPoints {
                        let barIndex = Int(point.x)
                        let price = point.y
                        let x = indexToX(barIndex)
                        let y = priceToY(price)

                        // Clamp Y to reasonable screen bounds
                        let clampedY = max(-50, min(size.height + 50, y))

                        // Only draw points within reasonable X bounds (allow some overflow for edge continuity)
                        guard x >= -50 && x <= size.width + 100 else { continue }

                        // Skip points with extreme Y values (regression extrapolation gone wild)
                        guard price >= priceMin - priceRange * 2 &&
                              price <= priceMax + priceRange * 2 else { continue }

                        let currentPoint = CGPoint(x: x, y: clampedY)

                        if !started {
                            path.move(to: currentPoint)
                            started = true
                        } else {
                            path.addLine(to: currentPoint)
                        }
                    }

                    if started {
                        // Draw with glow effect for better visibility
                        context.stroke(path, with: .color(indicator.settings.resistanceColor.opacity(0.3)), lineWidth: 6)
                        context.stroke(path, with: .color(indicator.settings.resistanceColor), lineWidth: 2)
                    }
                }

                // Draw support curve
                if let supLine = indicator.supportLine {
                    var path = Path()
                    var started = false

                    for point in supLine.predictedPoints {
                        let barIndex = Int(point.x)
                        let price = point.y
                        let x = indexToX(barIndex)
                        let y = priceToY(price)

                        // Clamp Y to reasonable screen bounds
                        let clampedY = max(-50, min(size.height + 50, y))

                        // Only draw points within reasonable X bounds
                        guard x >= -50 && x <= size.width + 100 else { continue }

                        // Skip points with extreme Y values (regression gone wild)
                        let priceRange = priceMax - priceMin
                        guard price >= priceMin - priceRange * 2 &&
                              price <= priceMax + priceRange * 2 else { continue }

                        let currentPoint = CGPoint(x: x, y: clampedY)

                        if !started {
                            path.move(to: currentPoint)
                            started = true
                        } else {
                            path.addLine(to: currentPoint)
                        }
                    }

                    if started {
                        // Draw with glow effect for better visibility
                        context.stroke(path, with: .color(indicator.settings.supportColor.opacity(0.3)), lineWidth: 6)
                        context.stroke(path, with: .color(indicator.settings.supportColor), lineWidth: 2)
                    }
                }

                // Draw pivot point markers if enabled (hollow circles like TradingView)
                // Use activePivots to only show pivots used in current regression (TradingView style)
                if indicator.settings.showPivots {
                    let circleRadius: CGFloat = 6  // Slightly smaller for cleaner look
                    let strokeWidth: CGFloat = 2   // Ring stroke width

                    // Resistance pivots (red hollow circles at highs)
                    // Use activePivots.highs for TradingView-style display (only pivots in current regression)
                    for pivot in indicator.activePivots.highs {
                        let x = indexToX(pivot.index)
                        let y = priceToY(pivot.price)

                        guard x >= 0 && x <= size.width else { continue }
                        guard pivot.price >= priceMin && pivot.price <= priceMax else { continue }

                        // Draw hollow circle (ring)
                        let circle = Path(ellipseIn: CGRect(
                            x: x - circleRadius,
                            y: y - circleRadius,
                            width: circleRadius * 2,
                            height: circleRadius * 2
                        ))
                        context.stroke(circle, with: .color(indicator.settings.resistanceColor), lineWidth: strokeWidth)
                    }

                    // Support pivots (green hollow circles at lows)
                    // Use activePivots.lows for TradingView-style display (only pivots in current regression)
                    for pivot in indicator.activePivots.lows {
                        let x = indexToX(pivot.index)
                        let y = priceToY(pivot.price)

                        guard x >= 0 && x <= size.width else { continue }
                        guard pivot.price >= priceMin && pivot.price <= priceMax else { continue }

                        // Draw hollow circle (ring)
                        let circle = Path(ellipseIn: CGRect(
                            x: x - circleRadius,
                            y: y - circleRadius,
                            width: circleRadius * 2,
                            height: circleRadius * 2
                        ))
                        context.stroke(circle, with: .color(indicator.settings.supportColor), lineWidth: strokeWidth)
                    }
                }
            }

            // Draw Logistic Regression S&R
            if config.showLogisticSR, let indicator = logisticIndicator {
                for level in indicator.regressionLevels {
                    guard level.level >= priceMin && level.level <= priceMax else { continue }
                    let y = size.height * (1 - (level.level - priceMin) / (priceMax - priceMin))
                    var path = Path()
                    path.move(to: CGPoint(x: 0, y: y))
                    path.addLine(to: CGPoint(x: size.width, y: y))
                    let color = level.isSupport ? indicator.settings.supportColor : indicator.settings.resistanceColor
                    context.stroke(path, with: .color(color), lineWidth: 3)

                    // Draw probability label
                    if indicator.settings.showPredictionLabels {
                        let text = Text(String(format: "%.0f%%", level.detectedPrediction * 100))
                            .font(.caption2)
                            .foregroundColor(color)
                        context.draw(text, at: CGPoint(x: size.width - 40, y: y - 10))
                    }
                }
            }
        }
        .id(srOverlayChangeId)  // Force Canvas recreation when indicator data changes
        .allowsHitTesting(false) // Allow mouse events to pass through to chart
    }

    /// Unique identifier to force Canvas redraw when S&R indicator data changes
    private var srOverlayChangeId: String {
        // Polynomial S&R state
        let polyRes = polyIndicator?.currentResistance ?? 0
        let polySup = polyIndicator?.currentSupport ?? 0
        let polyResPoints = polyIndicator?.resistanceLine?.predictedPoints.count ?? 0
        let polySupPoints = polyIndicator?.supportLine?.predictedPoints.count ?? 0
        let polyHighPivots = polyIndicator?.pivots.highs.count ?? 0
        let polyLowPivots = polyIndicator?.pivots.lows.count ?? 0

        // Pivot Levels state
        let pivotCount = pivotIndicator?.pivotLevels.count ?? 0
        let pivotHighSum = pivotIndicator?.pivotLevels.reduce(0.0) { $0 + $1.levelHigh } ?? 0
        let pivotLowSum = pivotIndicator?.pivotLevels.reduce(0.0) { $0 + $1.levelLow } ?? 0

        // Logistic S&R state
        let logisticCount = logisticIndicator?.regressionLevels.count ?? 0
        let logisticLevelSum = logisticIndicator?.regressionLevels.reduce(0.0) { $0 + $1.level } ?? 0

        // Include visible range, bar count, and config state
        let barCount = bars.count
        let configState = "\(config.showPolynomialSR)-\(config.showPivotLevels)-\(config.showLogisticSR)"

        return "sr-\(polyRes.rounded())-\(polySup.rounded())-\(polyResPoints)-\(polySupPoints)-\(polyHighPivots)-\(polyLowPivots)-\(pivotCount)-\(pivotHighSum.rounded())-\(pivotLowSum.rounded())-\(logisticCount)-\(logisticLevelSum.rounded())-\(visibleRange.lowerBound)-\(visibleRange.upperBound)-\(barCount)-\(configState)"
    }

    private var priceChart: some View {
        Chart {
            // Candlesticks - using index for even spacing
            // Native scrolling handles visibility, so iterate visible bars with buffer
            ForEach(visibleBars, id: \.bar.id) { item in
                candlestickMarks(index: item.index, bar: item.bar)
            }

            // Moving Average Overlays - using distinct high-contrast colors
            if config.showSMA20 {
                indicatorLine(sma20, color: ChartColors.sma20, label: "SMA(20)")
            }
            if config.showSMA50 {
                indicatorLine(sma50, color: ChartColors.sma50, label: "SMA(50)")
            }
            if config.showEMA9 {
                indicatorLine(ema9, color: ChartColors.ema9, label: "EMA(9)")
            }
            if config.showEMA21 {
                indicatorLine(ema21, color: ChartColors.ema21, label: "EMA(21)")
            }

            // Bollinger Bands Overlay
            if config.showBollingerBands {
                bollingerBandsOverlay
            }

            // SuperTrend Overlay
            if config.showSuperTrend {
                superTrendOverlay
                superTrendFlipAnnotations
            }

            // SuperTrend AI Buy/Sell Signals
            if config.showSuperTrend && config.showSignalMarkers {
                superTrendSignalMarkers
            }

            // Pivot Levels (native Chart marks instead of Canvas)
            if config.showPivotLevels, let indicator = pivotIndicator {
                pivotLevelMarks(indicator: indicator)
            }

            // ML Forecast Overlays
            if let mlSummary = mlSummary {
                forecastOverlay(mlSummary)
            }

            // Crosshair selection indicator (vertical + horizontal lines with price badge)
            if let selectedIdx = selectedIndex, let bar = selectedBar {
                // Vertical crosshair line
                RuleMark(x: .value("Index", selectedIdx))
                    .foregroundStyle(.blue.opacity(0.4))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))

                // Horizontal crosshair line at close price
                RuleMark(y: .value("Price", bar.close))
                    .foregroundStyle(.blue.opacity(0.4))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))
                    .annotation(position: .trailing, alignment: .trailing, spacing: 4) {
                        // Price badge
                        Text(formatPrice(bar.close))
                            .font(.system(size: 10, weight: .medium).monospacedDigit())
                            .foregroundStyle(.white)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 3)
                            .background(
                                RoundedRectangle(cornerRadius: 4)
                                    .fill(bar.close >= bar.open ? Color.green : Color.red)
                            )
                    }
            }
        }
        .chartXScale(domain: 0...maxChartIndex)
        .chartYScale(domain: visiblePriceRange)
        // Native horizontal scrolling with trackpad/gesture support
        .chartScrollableAxes(.horizontal)
        .chartXVisibleDomain(length: barsToShow)
        .chartScrollPosition(x: $scrollPosition)
        .chartXAxis {
            AxisMarks(values: .automatic(desiredCount: 6)) { value in
                if let index = value.as(Int.self), index >= 0 && index < bars.count {
                    AxisGridLine()
                    AxisTick()
                    AxisValueLabel {
                        Text(formatDate(bars[index].ts))
                            .font(.caption)
                    }
                }
            }
        }
        .chartYAxis {
            AxisMarks(position: .trailing, values: .automatic(desiredCount: 8)) { value in
                AxisGridLine()
                AxisTick()
                AxisValueLabel {
                    if let price = value.as(Double.self) {
                        Text(formatPrice(price))
                            .font(.caption.monospacedDigit())
                    }
                }
            }
        }
        .chartLegend(position: .top, alignment: .leading) {
            legendView
        }
        .chartOverlay { proxy in
            GeometryReader { geometry in
                Rectangle()
                    .fill(.clear)
                    .contentShape(Rectangle())
                    .onContinuousHover { phase in
                        switch phase {
                        case .active(let location):
                            updateSelection(at: location, proxy: proxy, geometry: geometry)
                        case .ended:
                            selectedBar = nil
                        }
                    }
            }
        }
        .overlay(alignment: .topLeading) {
            if let bar = selectedBar {
                CandlestickTooltip(bar: bar)
                    .padding(8)
            }
        }
        // Sync scrollPosition changes back to visibleRange
        .onChange(of: scrollPosition) { _, newPosition in
            let clampedStart = max(0, min(newPosition, bars.count - barsToShow))
            let newEnd = min(bars.count - 1, clampedStart + barsToShow - 1)
            visibleRange = clampedStart...newEnd
        }
    }

    // MARK: - RSI Chart

    private var rsiChartView: some View {
        Chart {
            // RSI overbought zone shading (80-100)
            RectangleMark(
                xStart: .value("Start", visibleBarsOnlyRange.lowerBound),
                xEnd: .value("End", visibleBarsOnlyRange.upperBound),
                yStart: .value("Low", 80),
                yEnd: .value("High", 100)
            )
            .foregroundStyle(Color.red.opacity(0.08))

            // RSI oversold zone shading (0-20)
            RectangleMark(
                xStart: .value("Start", visibleBarsOnlyRange.lowerBound),
                xEnd: .value("End", visibleBarsOnlyRange.upperBound),
                yStart: .value("Low", 0),
                yEnd: .value("High", 20)
            )
            .foregroundStyle(Color.green.opacity(0.08))

            // RSI line
            indicatorLine(rsi, color: ChartColors.rsi, label: "RSI")

            // Overbought line (80)
            RuleMark(y: .value("Overbought", 80))
                .foregroundStyle(ChartColors.overbought)
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))

            // Oversold line (20)
            RuleMark(y: .value("Oversold", 20))
                .foregroundStyle(ChartColors.oversold)
                .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))

            // Midline (50)
            RuleMark(y: .value("Midline", 50))
                .foregroundStyle(ChartColors.midline)

            // Selection indicator
            if let selectedIdx = selectedIndex {
                RuleMark(x: .value("Index", selectedIdx))
                    .foregroundStyle(.blue.opacity(0.3))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 3]))
            }
        }
        .chartXScale(domain: visibleBarsOnlyRange)
        .chartYScale(domain: 0...100)  // Full range with adjusted reference lines
        .chartXAxis(.hidden)
        .chartYAxis {
            AxisMarks(position: .trailing, values: [20, 50, 80]) { value in
                AxisGridLine()
                AxisValueLabel()
            }
        }
        .chartLegend(position: .top, alignment: .leading) {
            HStack(spacing: 8) {
                Circle()
                    .fill(ChartColors.rsi)
                    .frame(width: 8, height: 8)
                Text("RSI(14)")
                    .font(.caption.bold())
                    .foregroundStyle(.primary)
                Spacer()
                if let latestRSI = rsi.last?.value {
                    Text(String(format: "%.1f", latestRSI))
                        .font(.caption.bold().monospacedDigit())
                        .foregroundStyle(rsiColor(latestRSI))
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(rsiColor(latestRSI).opacity(0.15))
                        .clipShape(Capsule())
                }
            }
            .padding(.horizontal, 8)
        }
    }

    // MARK: - Volume Chart

    private var volumeChartView: some View {
        Chart {
            ForEach(Array(visibleBarsOnlyRange), id: \.self) { index in
                if index < bars.count {
                    let bar = bars[index]
                    BarMark(
                        x: .value("Index", index),
                        y: .value("Volume", bar.volume)
                    )
                    .foregroundStyle(bar.close >= bar.open ? Color.green.opacity(0.5) : Color.red.opacity(0.5))
                }
            }
        }
        .chartXScale(domain: visibleBarsOnlyRange)
        .chartXAxis(.hidden)
        .chartYAxis {
            AxisMarks(position: .trailing, values: .automatic(desiredCount: 3)) { value in
                AxisGridLine()
                AxisValueLabel {
                    if let volume = value.as(Double.self) {
                        Text(formatVolume(volume))
                            .font(.caption2)
                    }
                }
            }
        }
        .chartLegend(position: .top, alignment: .leading) {
            Label("Volume", systemImage: "chart.bar.fill")
                .font(.caption)
                .foregroundStyle(.secondary)
                .padding(.horizontal, 8)
        }
    }

    // MARK: - Helper Views

    // Downsamples data for better performance on large datasets
    private func downsampled(_ data: [IndicatorDataPoint]) -> [CGPoint] {
        let pixelWidth = 1200.0 // Target width
        let threshold = Int(pixelWidth * 2) 
        
        let start = max(0, visibleRange.lowerBound)
        let end = min(data.count - 1, visibleRange.upperBound)
        guard start <= end else { return [] }
        
        // If count is small, return all points directly
        if (end - start + 1) <= threshold {
            var points: [CGPoint] = []
            points.reserveCapacity(end - start + 1)
            for i in start...end {
                if let val = data[i].value {
                    points.append(CGPoint(x: Double(i), y: val))
                }
            }
            return points
        }
        
        // Collect points for downsampling
        var validPoints: [CGPoint] = []
        validPoints.reserveCapacity(end - start + 1)
        for i in start...end {
            if let val = data[i].value {
                validPoints.append(CGPoint(x: Double(i), y: val))
            }
        }
        
        return lttbDownsample(validPoints, threshold: threshold)
    }
    
    @inline(__always)
    private func lttbDownsample(_ points: [CGPoint], threshold: Int) -> [CGPoint] {
        let n = points.count
        if threshold >= n || threshold < 3 { return points }

        var sampled: [CGPoint] = []
        sampled.reserveCapacity(threshold)
        sampled.append(points[0])

        let bucketSize = Double(n - 2) / Double(threshold - 2)
        var aIndex = 0

        for i in 0..<(threshold - 2) {
            let start = Int(floor(Double(i) * bucketSize)) + 1
            let end   = Int(floor(Double(i + 1) * bucketSize)) + 1
            let rangeEnd = min(end, n - 1)

            // Average of this bucket (excluding edges)
            var avgX = 0.0, avgY = 0.0, count = 0.0
            if rangeEnd > start {
                for j in start..<rangeEnd {
                    avgX += Double(points[j].x)
                    avgY += Double(points[j].y)
                    count += 1.0
                }
                avgX /= max(count, 1.0)
                avgY /= max(count, 1.0)
            } else {
                // Fallback: use A if this bucket is empty
                let fallback = points[min(max(rangeEnd, 0), n - 1)]
                avgX = Double(fallback.x)
                avgY = Double(fallback.y)
            }

            // Pick point maximizing triangle area with A and avg
            let a = points[aIndex]
            var maxArea = -Double.greatestFiniteMagnitude
            var maxIdx = start

            for j in start..<rangeEnd {
                let p = points[j]
                let area = abs(
                    (Double(a.x) - avgX) * (Double(p.y) - Double(a.y)) -
                    (Double(a.x) - Double(p.x)) * (avgY - Double(a.y))
                )
                if area > maxArea {
                    maxArea = area
                    maxIdx = j
                }
            }

            sampled.append(points[maxIdx])
            aIndex = maxIdx
        }

        sampled.append(points[n - 1])
        return sampled
    }

    @ChartContentBuilder
    private func candlestickMarks(index: Int, bar: OHLCBar) -> some ChartContent {
        let isBullish = bar.close >= bar.open
        let candleColor = isBullish ? ChartColors.bullish : ChartColors.bearish

        // Candlestick body
        RectangleMark(
            x: .value("Index", index),
            yStart: .value("Open", min(bar.open, bar.close)),
            yEnd: .value("Close", max(bar.open, bar.close)),
            width: .ratio(0.6)
        )
        .foregroundStyle(candleColor)
        .opacity(selectedIndex == index ? 1.0 : 0.85)

        // Candlestick wick
        RuleMark(
            x: .value("Index", index),
            yStart: .value("Low", bar.low),
            yEnd: .value("High", bar.high)
        )
        .foregroundStyle(candleColor.opacity(0.9))
        .lineStyle(StrokeStyle(lineWidth: 1.5))
    }

    @ChartContentBuilder
    private func indicatorLine(_ data: [IndicatorDataPoint], color: Color, label: String) -> some ChartContent {
        let points = downsampled(data)
        ForEach(Array(points.enumerated()), id: \.offset) { pair in
            let pt = pair.element
            LineMark(
                x: .value("Index", Int(pt.x.rounded())),
                y: .value(label, Double(pt.y))
            )
            .foregroundStyle(color)
            .lineStyle(StrokeStyle(lineWidth: 2))
        }
    }

    private var legendView: some View {
        HStack(spacing: 12) {
            if config.showSMA20 {
                LegendItem(color: ChartColors.sma20, label: "SMA(20)", value: sma20.last?.value)
            }
            if config.showSMA50 {
                LegendItem(color: ChartColors.sma50, label: "SMA(50)", value: sma50.last?.value)
            }
            if config.showEMA9 {
                LegendItem(color: ChartColors.ema9, label: "EMA(9)", value: ema9.last?.value)
            }
            if config.showEMA21 {
                LegendItem(color: ChartColors.ema21, label: "EMA(21)", value: ema21.last?.value)
            }
            if config.showBollingerBands {
                LegendItem(color: ChartColors.bollingerBand, label: "BB(20,2)", value: nil)
            }
            if config.showSuperTrend {
                superTrendLegendItem
            }
        }
        .padding(.horizontal, 8)
    }

    // SuperTrend legend with trend strength indicator
    // Uses SuperTrend AI data when available
    private var superTrendLegendItem: some View {
        // Use AI data if available
        let trendData = !aiSuperTrendTrend.isEmpty ? aiSuperTrendTrend : superTrendTrend
        let lastTrend = trendData.last ?? 0
        let lastStrength = superTrendStrength.last?.value ?? 0
        let isBullish = lastTrend == 1
        let trendColor: Color = isBullish ? .green : .red
        let trendLabel = isBullish ? "BULL" : "BEAR"

        // Strength as percentage (0-100)
        let strengthPercent = Int(lastStrength)

        // Show "AI" indicator when using AI data
        let isAI = !aiSuperTrendTrend.isEmpty

        let startIdx = max(0, scrollPosition)
        let endIdx = min(bars.count - 1, scrollPosition + barsToShow - 1)

        let segmentStartIdx: Int = {
            guard startIdx <= endIdx, endIdx < trendData.count else { return startIdx }
            if endIdx == startIdx { return startIdx }
            var start = startIdx
            if startIdx + 1 <= endIdx {
                for i in stride(from: endIdx, through: startIdx + 1, by: -1) {
                    if i < trendData.count, (i - 1) < trendData.count, trendData[i] != trendData[i - 1] {
                        start = i
                        break
                    }
                }
            }
            return start
        }()

        let startLevel: Double? = {
            guard startIdx <= endIdx else { return nil }
            if isAI {
                guard !aiSuperTrendLine.isEmpty else { return nil }
                for i in segmentStartIdx...endIdx {
                    if i < aiSuperTrendLine.count, let v = aiSuperTrendLine[i] {
                        return v
                    }
                }
                return nil
            }
            for i in segmentStartIdx...endIdx {
                if i < superTrendLine.count, let v = superTrendLine[i].value {
                    return v
                }
            }
            return nil
        }()

        let currentLevel: Double? = {
            guard startIdx <= endIdx else { return nil }
            if isAI {
                guard !aiSuperTrendLine.isEmpty else { return nil }
                for i in stride(from: endIdx, through: startIdx, by: -1) {
                    if i < aiSuperTrendLine.count, let v = aiSuperTrendLine[i] {
                        return v
                    }
                }
                return nil
            }
            for i in stride(from: endIdx, through: startIdx, by: -1) {
                if i < superTrendLine.count, let v = superTrendLine[i].value {
                    return v
                }
            }
            return nil
        }()

        let levelDelta: Double? = {
            guard let s = startLevel, let c = currentLevel else { return nil }
            return c - s
        }()

        let levelDeltaPct: Double? = {
            guard let s = startLevel, let d = levelDelta, abs(s) > 1e-9 else { return nil }
            return (d / s) * 100.0
        }()

        let factorText: String? = {
            guard isAI else { return nil }
            if let factors = superTrendAIIndicator?.result?.adaptiveFactor,
               endIdx >= 0,
               endIdx < factors.count {
                return String(format: "F%.2f", factors[endIdx])
            }
            if let currentFactor = superTrendAIIndicator?.currentFactor {
                return String(format: "F%.2f", currentFactor)
            }
            return nil
        }()

        let deltaText: String? = {
            guard let d = levelDelta else { return nil }
            return String(format: "%+.2f", d)
        }()

        let deltaPctText: String? = {
            guard let p = levelDeltaPct else { return nil }
            return String(format: "(%+.2f%%)", p)
        }()

        return HStack(spacing: 4) {
            Circle()
                .fill(trendColor)
                .frame(width: 8, height: 8)
            Text(isAI ? "ST-AI" : "ST")
                .font(.caption2)
                .foregroundColor(.secondary)
            if let factorText {
                Text(factorText)
                    .font(.caption2.monospacedDigit())
                    .foregroundColor(.secondary)
            }
            Text(trendLabel)
                .font(.caption2.bold())
                .foregroundColor(trendColor)
            Text("(\(strengthPercent)%)")
                .font(.caption2)
                .foregroundColor(.secondary)
            if let startLevel, let currentLevel {
                Text("\(formatPrice(startLevel))→\(formatPrice(currentLevel))")
                    .font(.caption2.monospacedDigit())
                    .foregroundColor(.secondary)
            }
            if let deltaText {
                Text(deltaText)
                    .font(.caption2.bold().monospacedDigit())
                    .foregroundColor((levelDelta ?? 0) >= 0 ? .green : .red)
            }
            if let deltaPctText {
                Text(deltaPctText)
                    .font(.caption2.monospacedDigit())
                    .foregroundColor(.secondary)
            }
        }
    }

    // MARK: - SuperTrend Strength Panel

    // Uses SuperTrend AI data when available
    private var superTrendStrengthPanel: some View {
        // Use AI data if available
        let trendData = !aiSuperTrendTrend.isEmpty ? aiSuperTrendTrend : superTrendTrend
        let lastTrend = trendData.last ?? 0
        let isBullish = lastTrend == 1
        let bgColor = isBullish ? ChartColors.superTrendBull : ChartColors.superTrendBear

        return VStack(spacing: 0) {
            // Header with current trend info
            HStack {
                Label("SuperTrend", systemImage: "waveform.path.ecg")
                    .font(.caption.bold())
                    .foregroundStyle(.secondary)

                // Show current parameters
                Text(superTrendParamsLabel)
                    .font(.caption2)
                    .foregroundStyle(.tertiary)

                Spacer()

                // Current trend badge
                Text(isBullish ? "BULLISH" : "BEARISH")
                    .font(.caption.bold())
                    .foregroundColor(isBullish ? ChartColors.superTrendBull : ChartColors.superTrendBear)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background((isBullish ? ChartColors.superTrendBull : ChartColors.superTrendBear).opacity(0.15))
                    .clipShape(Capsule())

                // Current strength value
                if let lastStrength = superTrendStrength.last?.value {
                    Text("\(Int(lastStrength))%")
                        .font(.caption.bold().monospacedDigit())
                        .foregroundColor(strengthColor(lastStrength))
                }
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 4)

            // Strength chart
            Chart {
                ForEach(visibleStrengthData, id: \.index) { item in
                    AreaMark(
                        x: .value("Index", item.index),
                        y: .value("Strength", item.strength)
                    )
                    .foregroundStyle(
                        LinearGradient(
                            colors: [item.isBullish ? ChartColors.superTrendBull.opacity(0.3) : ChartColors.superTrendBear.opacity(0.3), .clear],
                            startPoint: .top,
                            endPoint: .bottom
                        )
                    )

                    LineMark(
                        x: .value("Index", item.index),
                        y: .value("Strength", item.strength)
                    )
                    .foregroundStyle(item.isBullish ? ChartColors.superTrendBull : ChartColors.superTrendBear)
                    .lineStyle(StrokeStyle(lineWidth: 1.5))
                }

                // Reference lines
                RuleMark(y: .value("Strong", 50))
                    .foregroundStyle(.orange.opacity(0.3))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 2]))

                RuleMark(y: .value("VeryStrong", 75))
                    .foregroundStyle(.green.opacity(0.3))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 2]))
            }
            .chartXScale(domain: visibleRange.lowerBound...visibleRange.upperBound)
            .chartYScale(domain: 0...100)
            .chartXAxis(.hidden)
            .chartYAxis {
                AxisMarks(position: .trailing, values: [25, 50, 75]) { value in
                    AxisGridLine()
                    AxisValueLabel {
                        if let v = value.as(Int.self) {
                            Text("\(v)")
                                .font(.caption2)
                        }
                    }
                }
            }
        }
        .background(bgColor.opacity(0.05))  // Subtle background color matching trend
    }

    // Helper for strength panel data
    // Uses SuperTrend AI data when available
    private var visibleStrengthData: [(index: Int, strength: Double, isBullish: Bool)] {
        var data: [(index: Int, strength: Double, isBullish: Bool)] = []

        let maxBarIndex = bars.count - 1
        guard maxBarIndex >= 0 else { return [] }

        let rangeStart = max(0, visibleRange.lowerBound)
        let rangeEnd = min(maxBarIndex, visibleRange.upperBound)

        guard rangeStart <= rangeEnd else { return [] }

        // Use AI data if available
        let trendData = !aiSuperTrendTrend.isEmpty ? aiSuperTrendTrend : superTrendTrend

        for i in rangeStart...rangeEnd {
            guard i < superTrendStrength.count,
                  i < trendData.count,
                  let strength = superTrendStrength[i].value else {
                continue
            }

            let isBullish = trendData[i] == 1
            data.append((index: i, strength: strength, isBullish: isBullish))
        }

        return data
    }

    // Color based on strength value
    private func strengthColor(_ strength: Double) -> Color {
        if strength >= 75 {
            return .green
        } else if strength >= 50 {
            return .orange
        } else if strength >= 25 {
            return .yellow
        } else {
            return .red
        }
    }

    // MARK: - Helper Functions

    /// Collect all visible indicator values for proper Y-axis scaling
    private func visibleIndicatorValues(from data: [IndicatorDataPoint]) -> [Double] {
        let startIdx = max(0, scrollPosition)
        let endIdx = min(bars.count - 1, scrollPosition + barsToShow - 1)
        
        var values: [Double] = []
        if startIdx <= endIdx {
            for i in startIdx...endIdx {
                if i < data.count, let value = data[i].value {
                    values.append(value)
                }
            }
        }
        return values
    }

    private var visibleMinPrice: Double {
        var minValue = visibleBars.map(\.bar.low).min() ?? 0

        // Include all enabled indicator minimums
        if config.showSMA20, let min = visibleIndicatorValues(from: sma20).min() {
            minValue = Swift.min(minValue, min)
        }
        if config.showSMA50, let min = visibleIndicatorValues(from: sma50).min() {
            minValue = Swift.min(minValue, min)
        }
        if config.showEMA9, let min = visibleIndicatorValues(from: ema9).min() {
            minValue = Swift.min(minValue, min)
        }
        if config.showEMA21, let min = visibleIndicatorValues(from: ema21).min() {
            minValue = Swift.min(minValue, min)
        }
        if config.showBollingerBands, let min = visibleIndicatorValues(from: bollingerLower).min() {
            minValue = Swift.min(minValue, min)
        }
        if config.showSuperTrend {
            // Prioritize AI SuperTrend line values if available
            if !aiSuperTrendLine.isEmpty {
                let startIdx = max(0, scrollPosition)
                let endIdx = min(bars.count - 1, scrollPosition + barsToShow - 1)
                for i in startIdx...endIdx {
                    if i < aiSuperTrendLine.count, let value = aiSuperTrendLine[i] {
                        minValue = Swift.min(minValue, value)
                    }
                }
            } else if let min = visibleIndicatorValues(from: superTrendLine).min() {
                minValue = Swift.min(minValue, min)
            }
        }

        // Include Polynomial S&R regression lines in visible range
        if config.showPolynomialSR, let indicator = polyIndicator {
            // Include visible regression line points
            if let resLine = indicator.resistanceLine {
                let visibleResPoints = resLine.predictedPoints.filter { point in
                    let idx = Int(point.x)
                    return idx >= visibleRange.lowerBound && idx <= visibleRange.upperBound + 20
                }
                if let min = visibleResPoints.map({ $0.y }).min() {
                    minValue = Swift.min(minValue, min)
                }
            }
            if let supLine = indicator.supportLine {
                let visibleSupPoints = supLine.predictedPoints.filter { point in
                    let idx = Int(point.x)
                    return idx >= visibleRange.lowerBound && idx <= visibleRange.upperBound + 20
                }
                if let min = visibleSupPoints.map({ $0.y }).min() {
                    minValue = Swift.min(minValue, min)
                }
            }
        }

        // Include Pivot Levels in visible range
        if config.showPivotLevels, let indicator = pivotIndicator {
            for level in indicator.pivotLevels where level.display {
                if level.levelHigh > 0 {
                    minValue = Swift.min(minValue, level.levelHigh)
                }
                if level.levelLow > 0 {
                    minValue = Swift.min(minValue, level.levelLow)
                }
            }
        }

        // Include Logistic S&R levels in visible range
        if config.showLogisticSR, let indicator = logisticIndicator {
            for level in indicator.regressionLevels {
                minValue = Swift.min(minValue, level.level)
            }
        }

        // Include forecast lower bounds
        if let mlSummary = mlSummary {
            for horizon in mlSummary.horizons {
                if let forecastMin = horizon.points.map({ $0.lower }).min() {
                    minValue = Swift.min(minValue, forecastMin)
                }
            }
        }

        return minValue
    }

    private var visibleMaxPrice: Double {
        var maxValue = visibleBars.map(\.bar.high).max() ?? 0

        // Include all enabled indicator maximums
        if config.showSMA20, let max = visibleIndicatorValues(from: sma20).max() {
            maxValue = Swift.max(maxValue, max)
        }
        if config.showSMA50, let max = visibleIndicatorValues(from: sma50).max() {
            maxValue = Swift.max(maxValue, max)
        }
        if config.showEMA9, let max = visibleIndicatorValues(from: ema9).max() {
            maxValue = Swift.max(maxValue, max)
        }
        if config.showEMA21, let max = visibleIndicatorValues(from: ema21).max() {
            maxValue = Swift.max(maxValue, max)
        }
        if config.showBollingerBands, let max = visibleIndicatorValues(from: bollingerUpper).max() {
            maxValue = Swift.max(maxValue, max)
        }
        if config.showSuperTrend {
            // Prioritize AI SuperTrend line values if available
            if !aiSuperTrendLine.isEmpty {
                let startIdx = max(0, scrollPosition)
                let endIdx = min(bars.count - 1, scrollPosition + barsToShow - 1)
                for i in startIdx...endIdx {
                    if i < aiSuperTrendLine.count, let value = aiSuperTrendLine[i] {
                        maxValue = Swift.max(maxValue, value)
                    }
                }
            } else if let max = visibleIndicatorValues(from: superTrendLine).max() {
                maxValue = Swift.max(maxValue, max)
            }
        }

        // Include Polynomial S&R regression lines in visible range
        if config.showPolynomialSR, let indicator = polyIndicator {
            // Include visible regression line points
            if let resLine = indicator.resistanceLine {
                let visibleResPoints = resLine.predictedPoints.filter { point in
                    let idx = Int(point.x)
                    return idx >= visibleRange.lowerBound && idx <= visibleRange.upperBound + 20
                }
                if let max = visibleResPoints.map({ $0.y }).max() {
                    maxValue = Swift.max(maxValue, max)
                }
            }
            if let supLine = indicator.supportLine {
                let visibleSupPoints = supLine.predictedPoints.filter { point in
                    let idx = Int(point.x)
                    return idx >= visibleRange.lowerBound && idx <= visibleRange.upperBound + 20
                }
                if let max = visibleSupPoints.map({ $0.y }).max() {
                    maxValue = Swift.max(maxValue, max)
                }
            }
        }

        // Include Pivot Levels in visible range
        if config.showPivotLevels, let indicator = pivotIndicator {
            for level in indicator.pivotLevels where level.display {
                if level.levelHigh > 0 {
                    maxValue = Swift.max(maxValue, level.levelHigh)
                }
                if level.levelLow > 0 {
                    maxValue = Swift.max(maxValue, level.levelLow)
                }
            }
        }

        // Include Logistic S&R levels in visible range
        if config.showLogisticSR, let indicator = logisticIndicator {
            for level in indicator.regressionLevels {
                maxValue = Swift.max(maxValue, level.level)
            }
        }

        // Include forecast upper bounds
        if let mlSummary = mlSummary {
            for horizon in mlSummary.horizons {
                if let forecastMax = horizon.points.map({ $0.upper }).max() {
                    maxValue = Swift.max(maxValue, forecastMax)
                }
            }
        }

        return maxValue
    }

    private var visiblePriceRange: ClosedRange<Double> {
        let range = visibleMaxPrice - visibleMinPrice
        // Use 8% padding for better visual margins
        let padding = range * 0.08
        return (visibleMinPrice - padding)...(visibleMaxPrice + padding)
    }

    /// Maximum X-axis index including forecast points
    private var maxChartIndex: Int {
        var maxIndex = max(0, bars.count - 1)

        // Extend domain to include forecast points
        if let mlSummary = mlSummary {
            let lastBarIndex = bars.count - 1
            let lastTs = bars.last?.ts.timeIntervalSince1970 ?? 0
            let interval = max(1, estimatedBarIntervalSeconds())
            for horizon in mlSummary.horizons {
                let forecastEndIndex = lastBarIndex + horizon.points.count
                var timeOffset = 0
                if let target = horizon.points.max(by: { $0.ts < $1.ts }) {
                    let delta = Double(target.ts) - lastTs
                    if delta > 0 {
                        timeOffset = max(1, Int(round(delta / interval)))
                    }
                }
                let extendedIndex = lastBarIndex + max(forecastEndIndex - lastBarIndex, timeOffset)
                maxIndex = max(maxIndex, extendedIndex)
            }
        }

        return maxIndex
    }

    // Pan/Zoom functions - work with native scrolling
    private func zoomIn() {
        let newWidth = max(10, barsToShow / 2)
        // Keep centered on current view
        let currentCenter = scrollPosition + barsToShow / 2
        let newStart = max(0, currentCenter - newWidth / 2)
        barsToShow = newWidth
        scrollPosition = newStart
    }

    private func zoomOut() {
        let newWidth = min(bars.count, barsToShow * 2)
        // Keep centered on current view
        let currentCenter = scrollPosition + barsToShow / 2
        let newStart = max(0, currentCenter - newWidth / 2)
        barsToShow = newWidth
        scrollPosition = min(newStart, max(0, bars.count - newWidth))
    }

    private func panLeft() {
        let shift = max(1, barsToShow / 4)
        scrollPosition = max(0, scrollPosition - shift)
    }

    private func panRight() {
        let shift = max(1, barsToShow / 4)
        // Allow panning to see forecasts (use maxChartIndex instead of bars.count)
        let maxPosition = max(0, maxChartIndex - barsToShow + 1)
        scrollPosition = min(maxPosition, scrollPosition + shift)
    }

    private func resetToLatest() {
        barsToShow = min(100, bars.count)
        // Position to show latest bars plus any forecast
        let forecastOffset = maxChartIndex - (bars.count - 1)
        scrollPosition = max(0, bars.count - barsToShow + forecastOffset)
    }

    private func updateSelection(at location: CGPoint, proxy: ChartProxy, geometry: GeometryProxy) {
        guard let plotFrame = proxy.plotFrame else { return }
        let xPosition = location.x - geometry[plotFrame].origin.x
        guard let index: Int = proxy.value(atX: xPosition) else { return }

        // Clamp index to valid range
        let clampedIndex = max(0, min(index, bars.count - 1))
        selectedIndex = clampedIndex
        selectedBar = bars[clampedIndex]
    }

    private func formatDate(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "M/d"
        return formatter.string(from: date)
    }

    private func formatPrice(_ price: Double) -> String {
        String(format: "$%.2f", price)
    }

    private func formatVolume(_ volume: Double) -> String {
        if volume >= 1_000_000 {
            return String(format: "%.1fM", volume / 1_000_000)
        } else if volume >= 1_000 {
            return String(format: "%.1fK", volume / 1_000)
        }
        return String(format: "%.0f", volume)
    }

    private func rsiColor(_ value: Double) -> Color {
        if value >= 70 {
            return .red
        } else if value <= 30 {
            return .green
        } else {
            return .purple
        }
    }

    // SuperTrend parameters label based on bar timeframe
    // Note: This is a display-only approximation since we don't have direct access to timeframe
    // The actual params are set in ChartViewModel based on timeframe
    private var superTrendParamsLabel: String {
        // Estimate timeframe from bar spacing
        if bars.count >= 2 {
            let interval = bars[1].ts.timeIntervalSince(bars[0].ts)
            if interval < 3600 {  // < 1 hour
                return "(7, 2.0)"
            } else if interval < 14400 {  // < 4 hours
                return "(8, 2.5)"
            } else if interval < 86400 {  // < 1 day
                return "(10, 3.0)"
            } else if interval < 604800 {  // < 1 week
                return "(10, 3.0)"
            } else {
                return "(14, 4.0)"
            }
        }
        return "(10, 3.0)"
    }

    // MARK: - Bollinger Bands Overlay

    @ChartContentBuilder
    private var bollingerBandsOverlay: some ChartContent {
        // Upper band
        ForEach(Array(visibleRange), id: \.self) { index in
            if index < bollingerUpper.count, let value = bollingerUpper[index].value {
                LineMark(
                    x: .value("Index", index),
                    y: .value("BB Upper", value)
                )
                .foregroundStyle(ChartColors.bollingerBand.opacity(0.7))
                .lineStyle(StrokeStyle(lineWidth: 1.5, dash: [5, 3]))
                .interpolationMethod(.catmullRom)
            }
        }

        // Middle band (SMA)
        ForEach(Array(visibleRange), id: \.self) { index in
            if index < bollingerMiddle.count, let value = bollingerMiddle[index].value {
                LineMark(
                    x: .value("Index", index),
                    y: .value("BB Middle", value)
                )
                .foregroundStyle(ChartColors.bollingerBand.opacity(0.5))
                .lineStyle(StrokeStyle(lineWidth: 1))
                .interpolationMethod(.catmullRom)
            }
        }

        // Lower band
        ForEach(Array(visibleRange), id: \.self) { index in
            if index < bollingerLower.count, let value = bollingerLower[index].value {
                LineMark(
                    x: .value("Index", index),
                    y: .value("BB Lower", value)
                )
                .foregroundStyle(ChartColors.bollingerBand.opacity(0.7))
                .lineStyle(StrokeStyle(lineWidth: 1.5, dash: [5, 3]))
                .interpolationMethod(.catmullRom)
            }
        }

        // Fill area between upper and lower bands
        ForEach(Array(visibleRange), id: \.self) { index in
            if index < bollingerUpper.count, index < bollingerLower.count,
               let upperVal = bollingerUpper[index].value,
               let lowerVal = bollingerLower[index].value {
                AreaMark(
                    x: .value("Index", index),
                    yStart: .value("Lower", lowerVal),
                    yEnd: .value("Upper", upperVal)
                )
                .foregroundStyle(ChartColors.bollingerFill)
            }
        }
    }

    // MARK: - SuperTrend Overlay

    @ChartContentBuilder
    private var superTrendOverlay: some ChartContent {
        // Trend zone backgrounds (when enabled)
        if config.showTrendZones {
            let minPrice = visibleBars.map(\.bar.low).min() ?? 0
            let maxPrice = visibleBars.map(\.bar.high).max() ?? 0

            ForEach(superTrendZones, id: \.startIndex) { zone in
                RectangleMark(
                    xStart: .value("Start", zone.startIndex),
                    xEnd: .value("End", zone.endIndex),
                    yStart: .value("Low", minPrice),
                    yEnd: .value("High", maxPrice)
                )
                .foregroundStyle(
                    zone.isBullish
                        ? Color.green.opacity(0.05)
                        : Color.red.opacity(0.05)
                )
            }
        }

        // SuperTrend line - render each point with series grouping by trend
        // Using series modifier to connect points within same trend direction
        ForEach(superTrendPoints, id: \.id) { point in
            LineMark(
                x: .value("Index", point.index),
                y: .value("SuperTrend", point.value),
                series: .value("Trend", point.seriesKey)
            )
            .foregroundStyle(point.isBullish ? Color.green : Color.red)
            .lineStyle(StrokeStyle(lineWidth: 2.5))
        }
    }

    // MARK: - SuperTrend Flip Annotations

    @ChartContentBuilder
    private var superTrendFlipAnnotations: some ChartContent {
        ForEach(findSuperTrendFlips(), id: \.index) { flip in
            // Dot on the line
            PointMark(
                x: .value("Index", flip.index),
                y: .value("SuperTrend", flip.price)
            )
            .symbol {
                Circle()
                    .fill(flip.isBullish ? ChartColors.superTrendBull : ChartColors.superTrendBear)
                    .frame(width: 6, height: 6)
                    .overlay(
                        Circle()
                            .stroke(Color.white, lineWidth: 1)
                    )
            }
            
            // Factor Label Tag
            PointMark(
                x: .value("Index", flip.index),
                y: .value("SuperTrend", flip.price)
            )
            .symbol {
                Color.clear
                    .frame(width: 1, height: 1)
            }
            .annotation(position: flip.isBullish ? .bottom : .top, spacing: 4) {
                factorTag(
                    value: flip.factor,
                    color: flip.isBullish ? ChartColors.superTrendBull : ChartColors.superTrendBear,
                    pointingUp: flip.isBullish,
                    horizontalOffset: flip.isBullish ? 0 : 18,
                    verticalOffset: flip.isBullish ? 0 : -4
                )
            }
        }
    }

    private struct SuperTrendFlip {
        let index: Int
        let price: Double
        let isBullish: Bool
        let factor: Double
    }

    private func findSuperTrendFlips() -> [SuperTrendFlip] {
        var flips: [SuperTrendFlip] = []
        let rangeStart = max(1, visibleRange.lowerBound)
        let rangeEnd = min(bars.count - 1, visibleRange.upperBound)
        
        guard rangeStart <= rangeEnd else { return [] }

        // Use AI data if available
        let useAI = !aiSuperTrendLine.isEmpty && !aiSuperTrendTrend.isEmpty
        let aiFactors = superTrendAIIndicator?.result?.adaptiveFactor ?? []
        
        for i in rangeStart...rangeEnd {
            let currTrend: Int
            let prevTrend: Int
            let currValue: Double
            let factor: Double
            
            if useAI {
                guard i < aiSuperTrendTrend.count, i-1 >= 0, i-1 < aiSuperTrendTrend.count,
                      i < aiSuperTrendLine.count, let val = aiSuperTrendLine[i] else { continue }
                currTrend = aiSuperTrendTrend[i]
                prevTrend = aiSuperTrendTrend[i-1]
                currValue = val
                factor = (i < aiFactors.count) ? aiFactors[i] : 1.0
            } else {
                guard i < superTrendTrend.count, i-1 >= 0, i-1 < superTrendTrend.count,
                      i < superTrendLine.count, let val = superTrendLine[i].value else { continue }
                currTrend = superTrendTrend[i]
                prevTrend = superTrendTrend[i-1]
                currValue = val
                factor = 3.0 // Default for standard SuperTrend
            }
            
            if currTrend != prevTrend {
                flips.append(SuperTrendFlip(
                    index: i,
                    price: currValue,
                    isBullish: currTrend == 1,
                    factor: factor
                ))
            }
        }
        
        return flips
    }
    
    private func factorTag(
        value: Double,
        color: Color,
        pointingUp: Bool,
        horizontalOffset: CGFloat = 0,
        verticalOffset: CGFloat = 0
    ) -> some View {
        Text(String(format: "%.0f", value))
            .font(.system(size: 10, weight: .bold))
            .foregroundStyle(.white)
            .padding(.horizontal, 6)
            .padding(.vertical, 4)
            .background(
                GeometryReader { geo in
                    Path { path in
                        let w = geo.size.width
                        let h = geo.size.height
                        
                        if pointingUp {
                            // Point at top (for annotation below point)
                            path.move(to: CGPoint(x: w/2, y: 0)) // Point
                            path.addLine(to: CGPoint(x: w/2 + 5, y: 5))
                            path.addLine(to: CGPoint(x: w, y: 5))
                            path.addLine(to: CGPoint(x: w, y: h))
                            path.addLine(to: CGPoint(x: 0, y: h))
                            path.addLine(to: CGPoint(x: 0, y: 5))
                            path.addLine(to: CGPoint(x: w/2 - 5, y: 5))
                        } else {
                            // Point at bottom (for annotation above point)
                            path.move(to: CGPoint(x: 0, y: 0))
                            path.addLine(to: CGPoint(x: w, y: 0))
                            path.addLine(to: CGPoint(x: w, y: h - 5))
                            path.addLine(to: CGPoint(x: w/2 + 5, y: h - 5))
                            path.addLine(to: CGPoint(x: w/2, y: h)) // Point
                            path.addLine(to: CGPoint(x: w/2 - 5, y: h - 5))
                            path.addLine(to: CGPoint(x: 0, y: h - 5))
                        }
                        path.closeSubpath()
                    }
                    .fill(color)
                }
            )
            .offset(x: horizontalOffset, y: (pointingUp ? 5 : -5) + verticalOffset)
    }

    // MARK: - SuperTrend AI Signal Markers
    
    @ChartContentBuilder
    private var superTrendSignalMarkers: some ChartContent {
        ForEach(superTrendAISignals) { signal in
            // Only show signals in visible range
            let startIdx = max(0, scrollPosition)
            let endIdx = min(bars.count - 1, scrollPosition + barsToShow - 1)

            if signal.barIndex >= startIdx && signal.barIndex <= endIdx {
                // Get SuperTrend line value at this bar for positioning
                let stValue: Double = {
                    if signal.barIndex < aiSuperTrendLine.count,
                       let aiValue = aiSuperTrendLine[signal.barIndex] {
                        return aiValue
                    }
                    if signal.barIndex < superTrendLine.count,
                       let value = superTrendLine[signal.barIndex].value {
                        return value
                    }
                    return signal.price
                }()

                // Signal marker point
                PointMark(
                    x: .value("Index", signal.barIndex),
                    y: .value("Price", stValue)
                )
                .symbol {
                    signalSymbol(for: signal)
                }
                .symbolSize(180)

                // Signal annotation with label
                PointMark(
                    x: .value("Index", signal.barIndex),
                    y: .value("Price", stValue)
                )
                .annotation(position: signal.type == .buy ? .bottom : .top, spacing: 4) {
                    signalAnnotation(for: signal)
                }
                .opacity(0)
            }
        }
    }

    /// Create signal symbol (triangle up for buy, down for sell)
    private func signalSymbol(for signal: SuperTrendSignal) -> some View {
        let color: Color = signal.type == .buy ? ChartColors.superTrendBull : ChartColors.superTrendBear

        return Group {
            if signal.type == .buy {
                Image(systemName: "arrowtriangle.up.fill")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundStyle(color)
            } else {
                Image(systemName: "arrowtriangle.down.fill")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundStyle(color)
            }
        }
    }

    /// Create signal annotation label
    private func signalAnnotation(for signal: SuperTrendSignal) -> some View {
        let color: Color = signal.type == .buy ? ChartColors.superTrendBull : ChartColors.superTrendBear
        let factorAtSignal: Double? = {
            if let factors = superTrendAIIndicator?.result?.adaptiveFactor,
               signal.barIndex >= 0,
               signal.barIndex < factors.count {
                return factors[signal.barIndex]
            }
            return signal.factor
        }()
        
        let displayValue = factorAtSignal ?? 0.0
        let isBuy = signal.type == .buy
        
        // Buy signal -> Position .bottom -> Point Up
        // Sell signal -> Position .top -> Point Down
        return factorTag(value: displayValue, color: color, pointingUp: isBuy)
    }

    // MARK: - Pivot Level Chart Marks (Native Swift Charts)

    @ChartContentBuilder
    private func pivotLevelMarks(indicator: PivotLevelsIndicator) -> some ChartContent {
        let priceRange = visiblePriceRange

        ForEach(Array(indicator.pivotLevels.enumerated()), id: \.offset) { _, level in
            if level.display {
                // High pivot level (resistance)
                if level.levelHigh > 0 &&
                    level.levelHigh >= priceRange.lowerBound &&
                    level.levelHigh <= priceRange.upperBound {
                    RuleMark(y: .value("Pivot High", level.levelHigh))
                        .foregroundStyle(level.highColor.opacity(0.8))
                        .lineStyle(StrokeStyle(
                            lineWidth: indicator.lineWidth(for: level.length),
                            dash: [8, 4]
                        ))
                        .annotation(position: .trailing, alignment: .trailing, spacing: 4) {
                            Text(String(format: "%.2f", level.levelHigh))
                                .font(.system(size: 8, weight: .medium).monospacedDigit())
                                .foregroundStyle(level.highColor)
                                .padding(.horizontal, 3)
                                .padding(.vertical, 1)
                                .background(level.highColor.opacity(0.1))
                                .clipShape(RoundedRectangle(cornerRadius: 2))
                        }
                }

                // Low pivot level (support)
                if level.levelLow > 0 &&
                    level.levelLow >= priceRange.lowerBound &&
                    level.levelLow <= priceRange.upperBound {
                    RuleMark(y: .value("Pivot Low", level.levelLow))
                        .foregroundStyle(level.lowColor.opacity(0.8))
                        .lineStyle(StrokeStyle(
                            lineWidth: indicator.lineWidth(for: level.length),
                            dash: [8, 4]
                        ))
                        .annotation(position: .trailing, alignment: .trailing, spacing: 4) {
                            Text(String(format: "%.2f", level.levelLow))
                                .font(.system(size: 8, weight: .medium).monospacedDigit())
                                .foregroundStyle(level.lowColor)
                                .padding(.horizontal, 3)
                                .padding(.vertical, 1)
                                .background(level.lowColor.opacity(0.1))
                                .clipShape(RoundedRectangle(cornerRadius: 2))
                        }
                }
            }
        }
    }

    // Helper struct for SuperTrend points with series key for proper line connection
    private struct SuperTrendPoint: Identifiable {
        let id: String
        let index: Int
        let value: Double
        let isBullish: Bool
        let seriesKey: String  // Groups points into connected line segments
    }

    // Get SuperTrend AI line values (prioritize AI over regular SuperTrend)
    private var aiSuperTrendLine: [Double?] {
        superTrendAIIndicator?.result?.supertrend ?? []
    }

    // Get SuperTrend AI trend values (prioritize AI over regular SuperTrend)
    private var aiSuperTrendTrend: [Int] {
        superTrendAIIndicator?.result?.trend ?? []
    }

    // Build SuperTrend points with series keys for connected line rendering
    // Uses SuperTrend AI data when available, falls back to regular SuperTrend
    private var superTrendPoints: [SuperTrendPoint] {
        var points: [SuperTrendPoint] = []
        var segmentId = 0
        var lastTrend: Int? = nil

        let maxBarIndex = bars.count - 1
        guard maxBarIndex >= 0 else { return [] }

        let rangeStart = max(0, visibleRange.lowerBound)
        let rangeEnd = min(maxBarIndex, visibleRange.upperBound)

        guard rangeStart <= rangeEnd else { return [] }

        // Use AI data if available, otherwise fall back to regular SuperTrend
        let useAI = !aiSuperTrendLine.isEmpty && !aiSuperTrendTrend.isEmpty

        for i in rangeStart...rangeEnd {
            let stValue: Double?
            let trend: Int

            if useAI {
                guard i < aiSuperTrendLine.count,
                      i < aiSuperTrendTrend.count else { continue }
                stValue = aiSuperTrendLine[i]
                trend = aiSuperTrendTrend[i]
            } else {
                guard i < superTrendLine.count,
                      i < superTrendTrend.count else { continue }
                stValue = superTrendLine[i].value
                trend = superTrendTrend[i]
            }

            guard let value = stValue else { continue }

            // Start new segment when trend changes
            if let prev = lastTrend, prev != trend {
                segmentId += 1
            }
            lastTrend = trend

            let isBullish = trend == 1
            points.append(SuperTrendPoint(
                id: "\(i)-\(segmentId)",
                index: i,
                value: value,
                isBullish: isBullish,
                seriesKey: "ST-\(segmentId)"
            ))
        }

        return points
    }

    // Helper struct for continuous SuperTrend line segments (grouped by trend)
    private struct SuperTrendLineSegment: Identifiable {
        let id: Int
        let isBullish: Bool
        let points: [(index: Int, value: Double)]
    }

    // Build continuous line segments grouped by trend direction
    // Uses SuperTrend AI data when available
    private var superTrendLineSegments: [SuperTrendLineSegment] {
        var lineSegments: [SuperTrendLineSegment] = []
        var currentPoints: [(index: Int, value: Double)] = []
        var currentTrend: Int? = nil
        var segmentId = 0

        let maxBarIndex = bars.count - 1
        let rangeStart = max(0, visibleRange.lowerBound)
        let rangeEnd = min(maxBarIndex, visibleRange.upperBound)

        guard rangeStart <= rangeEnd else { return [] }

        // Use AI data if available
        let useAI = !aiSuperTrendLine.isEmpty && !aiSuperTrendTrend.isEmpty

        for i in rangeStart...rangeEnd {
            let stValue: Double?
            let trend: Int

            if useAI {
                guard i < aiSuperTrendLine.count,
                      i < aiSuperTrendTrend.count,
                      i < bars.count else { continue }
                stValue = aiSuperTrendLine[i]
                trend = aiSuperTrendTrend[i]
            } else {
                guard i < superTrendLine.count,
                      i < superTrendTrend.count,
                      i < bars.count else { continue }
                stValue = superTrendLine[i].value
                trend = superTrendTrend[i]
            }

            guard let value = stValue else { continue }

            // If trend changed, save current segment and start new one
            if let prevTrend = currentTrend, prevTrend != trend, !currentPoints.isEmpty {
                lineSegments.append(SuperTrendLineSegment(
                    id: segmentId,
                    isBullish: prevTrend == 1,
                    points: currentPoints
                ))
                segmentId += 1
                currentPoints = []
            }

            currentPoints.append((index: i, value: value))
            currentTrend = trend
        }

        // Add final segment
        if !currentPoints.isEmpty, let trend = currentTrend {
            lineSegments.append(SuperTrendLineSegment(
                id: segmentId,
                isBullish: trend == 1,
                points: currentPoints
            ))
        }

        return lineSegments
    }

    // Helper struct for SuperTrend line segments
    private struct SuperTrendSegment: Identifiable {
        let id: Int
        let index: Int
        let value: Double
        let isBullish: Bool
    }

    // Build SuperTrend segments with proper color based on trend direction
    // Uses SuperTrend AI data when available
    private var superTrendSegments: [SuperTrendSegment] {
        var segments: [SuperTrendSegment] = []

        // Only process bars within visible range AND within actual data bounds
        let maxBarIndex = bars.count - 1
        let rangeStart = max(0, visibleRange.lowerBound)
        let rangeEnd = min(maxBarIndex, visibleRange.upperBound)

        guard rangeStart <= rangeEnd else { return [] }

        // Use AI data if available
        let useAI = !aiSuperTrendLine.isEmpty && !aiSuperTrendTrend.isEmpty

        for i in rangeStart...rangeEnd {
            let stValue: Double?
            let trend: Int

            if useAI {
                guard i < aiSuperTrendLine.count,
                      i < aiSuperTrendTrend.count,
                      i < bars.count else { continue }
                stValue = aiSuperTrendLine[i]
                trend = aiSuperTrendTrend[i]
            } else {
                guard i < superTrendLine.count,
                      i < superTrendTrend.count,
                      i < bars.count else { continue }
                stValue = superTrendLine[i].value
                trend = superTrendTrend[i]
            }

            guard let value = stValue else { continue }

            // Bullish when trend is 1 (close > supertrend line)
            let isBullish = trend == 1

            segments.append(SuperTrendSegment(
                id: i,
                index: i,
                value: value,
                isBullish: isBullish
            ))
        }

        return segments
    }

    // MARK: - SuperTrend Zones

    // Uses SuperTrend AI data when available
    private var superTrendZones: [SuperTrendZone] {
        // Use AI data if available
        let trendData = !aiSuperTrendTrend.isEmpty ? aiSuperTrendTrend : superTrendTrend
        guard !trendData.isEmpty else { return [] }

        var zones: [SuperTrendZone] = []
        // Limit to actual bar data - don't extend into forecast area
        let maxBarIndex = bars.count - 1
        let rangeStart = max(0, visibleRange.lowerBound)
        let rangeEnd = min(min(trendData.count - 1, maxBarIndex), visibleRange.upperBound)

        guard rangeStart <= rangeEnd else { return [] }

        var currentZoneStart = rangeStart
        var currentTrendValue = trendData[rangeStart]

        for i in rangeStart...rangeEnd {
            let trend = trendData[i]
            if trend != currentTrendValue && i > currentZoneStart {
                zones.append(SuperTrendZone(
                    startIndex: currentZoneStart,
                    endIndex: i - 1,
                    isBullish: currentTrendValue == 1
                ))
                currentZoneStart = i
                currentTrendValue = trend
            }
        }

        // Close final zone
        zones.append(SuperTrendZone(
            startIndex: currentZoneStart,
            endIndex: rangeEnd,
            isBullish: currentTrendValue == 1
        ))

        return zones
    }

    // MARK: - ML Forecast Overlay

    private func estimatedBarIntervalSeconds() -> Double {
        guard bars.count >= 2 else { return 60 }
        let recent = bars.suffix(30)
        var diffs: [Double] = []
        diffs.reserveCapacity(max(0, recent.count - 1))
        for pair in zip(recent, recent.dropFirst()) {
            let diff = pair.1.ts.timeIntervalSince(pair.0.ts)
            if diff > 0 {
                diffs.append(diff)
            }
        }
        guard !diffs.isEmpty else { return 60 }
        return diffs.reduce(0, +) / Double(diffs.count)
    }

    private func forecastIndexOffset(for targetTimestamp: Int) -> Int {
        let lastTs = bars.last?.ts.timeIntervalSince1970 ?? 0
        let interval = max(1, estimatedBarIntervalSeconds())
        let delta = Double(targetTimestamp) - lastTs
        if delta <= 0 {
            return 1
        }
        return max(1, Int(round(delta / interval)))
    }

    @ChartContentBuilder
    private func forecastOverlay(_ mlSummary: MLSummary) -> some ChartContent {
        // Get the forecast color based on overall label - using ChartColors
        let forecastColor: Color = {
            let label = (mlSummary.overallLabel ?? "unknown").lowercased()
            switch label {
            case "bullish": return ChartColors.forecastBullish
            case "bearish": return ChartColors.forecastBearish
            case "neutral": return ChartColors.forecastNeutral
            default: return .gray
            }
        }()

        let dailySet: Set<String> = ["1D", "1W", "1M"]
        let dailyTargets = mlSummary.horizons.filter { dailySet.contains($0.horizon.uppercased()) }

        let targetSeries = mlSummary.horizons.first(where: { $0.horizon == selectedForecastHorizon })
            ?? mlSummary.horizons.first
        let targetPoint = targetSeries?.points.max(by: { $0.ts < $1.ts })
        let targetLadder = targetSeries?.targets
        let primaryTargetValue = targetLadder?.tp1 ?? targetPoint?.value

        // Get the last bar's close price as the starting point for the forecast
        let lastClose = bars.last?.close ?? 0

        // Calculate the starting index (after the last bar)
        let lastBarIndex = bars.count - 1

        if !dailyTargets.isEmpty {
            ForEach(dailyTargets, id: \.horizon) { series in
                if let target = series.points.max(by: { $0.ts < $1.ts }) {
                    let targetValue = series.targets?.tp1 ?? target.value
                    let offset = forecastIndexOffset(for: target.ts)
                    let targetIndex = lastBarIndex + offset

                    let linePoints = [
                        (index: lastBarIndex, value: lastClose),
                        (index: targetIndex, value: targetValue),
                    ]

                    ForEach(linePoints.indices, id: \.self) { idx in
                        LineMark(
                            x: .value("Index", linePoints[idx].index),
                            y: .value("Target", linePoints[idx].value),
                            series: .value("Horizon", series.horizon)
                        )
                        .foregroundStyle(forecastColor)
                        .lineStyle(StrokeStyle(lineWidth: 2, dash: [6, 4]))
                        .opacity(0.9)
                    }

                    PointMark(
                        x: .value("Index", targetIndex),
                        y: .value("Target", targetValue)
                    )
                    .foregroundStyle(forecastColor)
                    .symbolSize(40)
                    .annotation(position: .trailing, alignment: .leading) {
                        Text("\(series.horizon.uppercased()) $\(String(format: "%.2f", targetValue))")
                            .font(.caption2.monospacedDigit())
                            .foregroundStyle(forecastColor)
                    }
                }
            }
        } else {
            // Draw a connection line from last bar to first forecast point
            if let firstHorizon = mlSummary.horizons.first,
               let firstPoint = firstHorizon.points.first {
                // Connection from last bar to forecast start
                LineMark(
                    x: .value("Index", lastBarIndex),
                    y: .value("Price", lastClose)
                )
                .foregroundStyle(forecastColor)
                .lineStyle(StrokeStyle(lineWidth: 2.5, dash: [6, 4]))
                .opacity(0.9)

                LineMark(
                    x: .value("Index", lastBarIndex + 1),
                    y: .value("Price", firstPoint.value)
                )
                .foregroundStyle(forecastColor)
                .lineStyle(StrokeStyle(lineWidth: 2.5, dash: [6, 4]))
                .opacity(0.9)
            }

            // Render forecast for each horizon
            ForEach(mlSummary.horizons, id: \.horizon) { series in
                // Convert forecast points to chart-compatible data
                ForEach(Array(series.points.enumerated()), id: \.offset) { offset, point in
                    let forecastIndex = lastBarIndex + offset + 1

                    // Forecast line (main prediction) - thicker and more visible
                    LineMark(
                        x: .value("Index", forecastIndex),
                        y: .value("Forecast", point.value)
                    )
                    .foregroundStyle(forecastColor)
                    .lineStyle(StrokeStyle(lineWidth: 2.5, dash: [6, 4]))
                    .opacity(0.9)

                    // Upper confidence band
                    LineMark(
                        x: .value("Index", forecastIndex),
                        y: .value("Upper", point.upper)
                    )
                    .foregroundStyle(forecastColor.opacity(0.4))
                    .lineStyle(StrokeStyle(lineWidth: 1.5, dash: [3, 3]))

                    // Lower confidence band
                    LineMark(
                        x: .value("Index", forecastIndex),
                        y: .value("Lower", point.lower)
                    )
                    .foregroundStyle(forecastColor.opacity(0.4))
                    .lineStyle(StrokeStyle(lineWidth: 1.5, dash: [3, 3]))

                    // Shaded area between confidence bands
                    AreaMark(
                        x: .value("Index", forecastIndex),
                        yStart: .value("Lower", point.lower),
                        yEnd: .value("Upper", point.upper)
                    )
                    .foregroundStyle(forecastColor.opacity(0.15))
                }
            }

            if let targetValue = primaryTargetValue, targetValue > 0 {
                RuleMark(
                    y: .value("Target", targetValue)
                )
                .foregroundStyle(forecastColor.opacity(0.9))
                .lineStyle(StrokeStyle(lineWidth: 1.5, dash: [4, 4]))
                .annotation(position: .trailing, alignment: .leading) {
                    Text(String(format: "TP1 $%.2f", targetValue))
                        .font(.caption2.monospacedDigit())
                        .foregroundStyle(forecastColor)
                }
            }

            // Add forecast endpoint marker
            if let lastHorizon = mlSummary.horizons.last,
               let lastPoint = lastHorizon.points.last {
                let endIndex = lastBarIndex + lastHorizon.points.count
                PointMark(
                    x: .value("Index", endIndex),
                    y: .value("Forecast", lastPoint.value)
                )
                .foregroundStyle(forecastColor)
                .symbolSize(60)
            }
        }
    }
}

struct LegendItem: View {
    let color: Color
    let label: String
    let value: Double?

    var body: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
            Text(label)
                .font(.caption)
            if let value = value {
                Text(String(format: "%.2f", value))
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
            }
        }
    }
}

// MARK: - SuperTrend Zone

struct SuperTrendZone: Equatable {
    let startIndex: Int
    let endIndex: Int
    let isBullish: Bool
}
