import SwiftUI
import WebKit
import Combine

/// SwiftUI wrapper for Lightweight Charts via WKWebView
/// Provides TradingView-style charting with Swift↔JS bridge
struct WebChartView: NSViewRepresentable {
    @ObservedObject var viewModel: ChartViewModel
    @StateObject private var bridge = ChartBridge()

    /// Coordinator handles WKWebView lifecycle and data updates
    @MainActor
    class Coordinator: NSObject, WKNavigationDelegate {
        var parent: WebChartView
        var cancellables = Set<AnyCancellable>()
        var hasLoadedInitialData = false
        var hasAppliedInitialZoom = false
        var lastVisibleRange: (from: Int, to: Int)?

        init(_ parent: WebChartView) {
            self.parent = parent
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            print("[WebChartView] Navigation finished")
        }

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            print("[WebChartView] Navigation failed: \(error.localizedDescription)")
        }

        func setupDataBindings() {
            // Subscribe to V2 chart data changes (layered data)
            parent.viewModel.$chartDataV2
                .receive(on: DispatchQueue.main)
                .sink { [weak self] chartDataV2 in
                    guard let self = self,
                          self.parent.bridge.isReady,
                          let data = chartDataV2 else { return }

                    self.updateChartV2(with: data)
                }
                .store(in: &cancellables)

            // Track visible range emitted from JS so we can preserve it on indicator toggles
            parent.bridge.eventPublisher
                .receive(on: DispatchQueue.main)
                .sink { [weak self] event in
                    guard let self else { return }
                    if case let .visibleRangeChange(from, to) = event {
                        self.lastVisibleRange = (from, to)
                    }
                }
                .store(in: &cancellables)

            // Subscribe to legacy chart data changes (fallback)
            parent.viewModel.$chartData
                .receive(on: DispatchQueue.main)
                .sink { [weak self] chartData in
                    guard let self = self,
                          self.parent.bridge.isReady,
                          let data = chartData,
                          self.parent.viewModel.chartDataV2 == nil else { return }

                    self.updateChart(with: data)
                }
                .store(in: &cancellables)

            // Subscribe to bridge ready state
            parent.bridge.$isReady
                .receive(on: DispatchQueue.main)
                .sink { [weak self] isReady in
                    guard let self = self, isReady else { return }

                    // Sync chart settings when bridge becomes ready (before loading data)
                    // This ensures HA state matches Swift's default (true) vs JS default (false)
                    self.parent.bridge.toggleHeikinAshi(enabled: self.parent.viewModel.useHeikinAshi)

                    // Load initial data when bridge becomes ready
                    if !self.hasLoadedInitialData {
                        if let dataV2 = self.parent.viewModel.chartDataV2 {
                            self.updateChartV2(with: dataV2)
                            self.hasLoadedInitialData = true
                        } else if let data = self.parent.viewModel.chartData {
                            self.updateChart(with: data)
                            self.hasLoadedInitialData = true
                        }
                    }
                }
                .store(in: &cancellables)
            
            // Subscribe to Heikin-Ashi toggle
            parent.viewModel.$useHeikinAshi
                .receive(on: DispatchQueue.main)
                .sink { [weak self] enabled in
                    guard let self = self, self.parent.bridge.isReady else { return }
                    self.parent.bridge.toggleHeikinAshi(enabled: enabled)
                }
                .store(in: &cancellables)
            
            // Subscribe to volume profile changes
            parent.viewModel.$volumeProfile
                .receive(on: DispatchQueue.main)
                .sink { [weak self] profile in
                    guard let self = self, 
                          self.parent.bridge.isReady,
                          !profile.isEmpty else { return }
                    self.parent.bridge.setVolumeProfile(data: profile)
                }
                .store(in: &cancellables)

            // Subscribe to indicator config changes (re-apply overlays/subpanels)
            parent.viewModel.$indicatorConfig
                .removeDuplicates(by: { lhs, rhs in
                    lhs.showSMA20 == rhs.showSMA20 &&
                    lhs.showSMA50 == rhs.showSMA50 &&
                    lhs.showEMA9 == rhs.showEMA9 &&
                    lhs.showEMA21 == rhs.showEMA21 &&
                    lhs.showSMA200 == rhs.showSMA200 &&
                    lhs.showBollingerBands == rhs.showBollingerBands &&
                    lhs.showSuperTrend == rhs.showSuperTrend &&
                    lhs.showVolume == rhs.showVolume &&
                    lhs.showRSI == rhs.showRSI &&
                    lhs.showMACD == rhs.showMACD &&
                    lhs.showStochastic == rhs.showStochastic &&
                    lhs.showKDJ == rhs.showKDJ &&
                    lhs.showADX == rhs.showADX &&
                    lhs.showATR == rhs.showATR &&
                    lhs.showPolynomialSR == rhs.showPolynomialSR &&
                    lhs.showPivotLevels == rhs.showPivotLevels &&
                    lhs.showLogisticSR == rhs.showLogisticSR &&
                    lhs.showSignalMarkers == rhs.showSignalMarkers
                })
                .debounce(for: .milliseconds(150), scheduler: DispatchQueue.main)
                .sink { [weak self] _ in
                    guard let self = self, self.parent.bridge.isReady else { return }
                    if let dataV2 = self.parent.viewModel.chartDataV2 {
                        self.updateChartV2(with: dataV2)
                    } else if let data = self.parent.viewModel.chartData {
                        self.updateChart(with: data)
                    }
                }
                .store(in: &cancellables)

            // Subscribe to volume profile toggle to remove overlay when disabled
            parent.viewModel.$showVolumeProfile
                .receive(on: DispatchQueue.main)
                .sink { [weak self] enabled in
                    guard let self = self, self.parent.bridge.isReady else { return }
                    if !enabled {
                        self.parent.bridge.removeVolumeProfile()
                    } else if !self.parent.viewModel.volumeProfile.isEmpty {
                        self.parent.bridge.setVolumeProfile(data: self.parent.viewModel.volumeProfile)
                    }
                }
                .store(in: &cancellables)
        }

        private func updateChartV2(with data: ChartDataV2Response) {
            let bridge = parent.bridge
            let preservedRange = lastVisibleRange ?? bridge.visibleRange
            
            print("[WebChartView] Updating chart with V2 layered data")
            print("[WebChartView] - Historical: \(data.layers.historical.count) bars")
            print("[WebChartView] - Intraday: \(data.layers.intraday.count) bars")
            print("[WebChartView] - Forecast: \(data.layers.forecast.count) bars")
            
            // Guard: only render if we have candles
            let allBars = data.allBars
            guard !allBars.isEmpty else {
                print("[WebChartView] ⚠️ No candles, clearing chart")
                bridge.send(.clearAll)
                return
            }
            
            // Choose base candles based on timeframe
            let baseCandles: [OHLCBar]
            if parent.viewModel.timeframe.isIntraday {
                // For intraday timeframes, render intraday as main candles (fallback to historical)
                let intradayBars = data.layers.intraday.data
                let historicalBars = data.layers.historical.data
                baseCandles = !intradayBars.isEmpty ? intradayBars : historicalBars
            } else {
                // For daily/weekly, combine historical + today's intraday
                baseCandles = data.layers.historical.data + data.layers.intraday.data
            }
            
            // Set candlestick data
            bridge.setCandles(from: baseCandles)
            
            // For non-intraday timeframes, overlay intraday as a line to highlight today
            if !parent.viewModel.timeframe.isIntraday, data.hasIntraday {
                bridge.setIntradayOverlay(from: data.layers.intraday.data)
            }
            
            // Clear previous overlays/indicators (keeps candles)
            bridge.send(.clearIndicators)

            // Add forecast data if present
            if data.hasForecast {
                if parent.viewModel.timeframe.isIntraday {
                    // For intraday, show forecast as translucent candlesticks overlay
                    bridge.setForecastCandles(from: data.layers.forecast.data)
                } else {
                    // For higher timeframes, show dashed line with confidence bands
                    bridge.setForecastLayer(from: data.layers.forecast.data)
                }
            }
            
            // Set indicators based on config (using combined historical + intraday data)
            let config = parent.viewModel.indicatorConfig
            
            if config.showSMA20 {
                bridge.setIndicator(
                    id: "sma20",
                    name: "SMA(20)",
                    data: parent.viewModel.sma20,
                    color: "#4db8ff"
                )
            }
            
            if config.showSMA50 {
                bridge.setIndicator(
                    id: "sma50",
                    name: "SMA(50)",
                    data: parent.viewModel.sma50,
                    color: "#ffa600"
                )
            }
            
            if config.showEMA9 {
                bridge.setIndicator(
                    id: "ema9",
                    name: "EMA(9)",
                    data: parent.viewModel.ema9,
                    color: "#00ffbf"
                )
            }
            
            if config.showEMA21 {
                bridge.setIndicator(
                    id: "ema21",
                    name: "EMA(21)",
                    data: parent.viewModel.ema21,
                    color: "#ff80b3"
                )
            }
            
            if config.showSMA200 {
                bridge.setIndicator(
                    id: "sma200",
                    name: "SMA(200)",
                    data: parent.viewModel.sma200,
                    color: "#ff5555"
                )
            }
            
            if config.showBollingerBands {
                bridge.setIndicator(
                    id: "bb_upper",
                    name: "BB Upper",
                    data: parent.viewModel.bollingerUpper,
                    color: "#9966ff"
                )
                bridge.setIndicator(
                    id: "bb_middle",
                    name: "BB Middle",
                    data: parent.viewModel.bollingerMiddle,
                    color: "#9966ff"
                )
                bridge.setIndicator(
                    id: "bb_lower",
                    name: "BB Lower",
                    data: parent.viewModel.bollingerLower,
                    color: "#9966ff"
                )
            }
            
            if config.showSuperTrend {
                let superTrendLine = parent.viewModel.superTrendLine
                let trendValues = parent.viewModel.superTrendTrend
                let aiFactorValues = parent.viewModel.superTrendAIFactor
                
                let minCount = min(superTrendLine.count, trendValues.count, allBars.count)
                if minCount > 0 {
                    let trendData = (0..<minCount).map { i in
                        IndicatorDataPoint(
                            bar: allBars[i],
                            value: Double(trendValues[i])
                        )
                    }
                    
                    let factorData = (0..<min(minCount, aiFactorValues.count)).map { i in
                        IndicatorDataPoint(
                            bar: allBars[i],
                            value: aiFactorValues[i]
                        )
                    }
                    
                    bridge.setSuperTrend(
                        data: Array(superTrendLine.prefix(minCount)),
                        trend: trendData,
                        strength: factorData
                    )

                    // Add inline markers at SuperTrend flips with AI factor badge
                    let markers = superTrendFlipMarkers(
                        bars: allBars,
                        superTrendLine: superTrendLine,
                        trendValues: trendValues,
                        factorValues: aiFactorValues
                    )
                    if !markers.isEmpty {
                        bridge.setMarkers(markers, seriesId: "supertrend")
                    }
                }
            }

            // Volume sub-panel
            if config.showVolume {
                bridge.setVolume(bars: allBars)
            } else {
                bridge.hidePanel("volume")
            }

            // Oscillator sub-panels
            if config.showRSI {
                bridge.setRSI(data: parent.viewModel.rsi)
            } else {
                bridge.hidePanel("rsi")
            }

            if config.showMACD {
                bridge.setMACD(
                    line: parent.viewModel.macdLine,
                    signal: parent.viewModel.macdSignal,
                    histogram: parent.viewModel.macdHistogram
                )
            } else {
                bridge.hidePanel("macd")
            }

            if config.showStochastic {
                bridge.setStochastic(
                    k: parent.viewModel.stochasticK,
                    d: parent.viewModel.stochasticD
                )
            } else {
                bridge.hidePanel("stochastic")
            }

            if config.showKDJ {
                bridge.setKDJ(
                    k: parent.viewModel.kdjK,
                    d: parent.viewModel.kdjD,
                    j: parent.viewModel.kdjJ
                )
            } else {
                bridge.hidePanel("kdj")
            }

            if config.showADX {
                bridge.setADX(
                    adx: parent.viewModel.adxLine,
                    plusDI: parent.viewModel.plusDI,
                    minusDI: parent.viewModel.minusDI
                )
            } else {
                bridge.hidePanel("adx")
            }

            if config.showATR {
                bridge.setATR(data: parent.viewModel.atr)
            } else {
                bridge.hidePanel("atr")
            }

            applyInitialZoomIfNeeded(bars: (data.layers.historical.data + data.layers.intraday.data))

            // Restore prior visible range after overlays are applied
            if let preservedRange {
                bridge.send(.setVisibleRange(from: preservedRange.from, to: preservedRange.to))
            }
            
            // Set Support & Resistance Indicators
            if config.showPolynomialSR {
                if let poly = parent.viewModel.polynomialSRIndicator.resistanceLine {
                    let resPoints: [LightweightDataPoint] = poly.predictedPoints.compactMap { pt in
                        let i = Int(pt.x)
                        guard i >= 0, i < allBars.count else { return nil }
                        return LightweightDataPoint(
                            time: Int(allBars[i].ts.timeIntervalSince1970),
                            value: Double(pt.y)
                        )
                    }
                    
                    let supPoints: [LightweightDataPoint] =
                        parent.viewModel.polynomialSRIndicator.supportLine?.predictedPoints.compactMap { pt in
                            let i = Int(pt.x)
                            guard i >= 0, i < allBars.count else { return nil }
                            return LightweightDataPoint(
                                time: Int(allBars[i].ts.timeIntervalSince1970),
                                value: Double(pt.y)
                            )
                        } ?? []
                    
                    bridge.send(.setPolynomialSR(resistance: resPoints, support: supPoints))
                }
            } else {
                bridge.send(.removeSeries(id: "poly-res"))
                bridge.send(.removeSeries(id: "poly-sup"))
            }
            
            if config.showPivotLevels {
                let levels = parent.viewModel.pivotLevelsIndicator.pivotLevels.map { level in
                    SRLevel(
                        price: level.levelHigh > 0 ? level.levelHigh : level.levelLow,
                        color: level.levelHigh > 0 ? "#FF5252" : "#4CAF50", // Red for Res, Green for Sup
                        title: "Pivot \(level.length)",
                        lineWidth: 1,
                        lineStyle: 2 // Dashed
                    )
                }
                bridge.send(.setPivotLevels(levels: levels))
            } else {
                bridge.send(.removePriceLines(category: "pivots"))
            }
            
            if config.showLogisticSR {
                var levels: [SRLevel] = []
                for level in parent.viewModel.logisticSRIndicator.supportLevels {
                    levels.append(SRLevel(
                        price: level.level,
                        color: "#089981", // Teal
                        title: "ML Sup",
                        lineWidth: 2,
                        lineStyle: 0 // Solid
                    ))
                }
                for level in parent.viewModel.logisticSRIndicator.resistanceLevels {
                    levels.append(SRLevel(
                        price: level.level,
                        color: "#F23645", // Red
                        title: "ML Res",
                        lineWidth: 2,
                        lineStyle: 0 // Solid
                    ))
                }
                bridge.send(.setLogisticSR(levels: levels))
            } else {
                bridge.send(.removePriceLines(category: "logistic"))
            }
        }

        private func updateChart(with data: ChartResponse) {
            let bridge = parent.bridge
            // Preserve current visible range to avoid reset when toggling indicators
            let preservedRange = lastVisibleRange ?? bridge.visibleRange

            // Clear previous overlays/indicators (keeps candles)
            bridge.send(.clearIndicators)

            // Set candlestick data
            bridge.setCandles(from: data.bars)

            // Set ML forecast if available
            if let mlSummary = data.mlSummary,
               let firstHorizon = mlSummary.horizons.first {
                bridge.setForecast(
                    from: firstHorizon,
                    direction: mlSummary.overallLabel ?? "neutral"
                )

                // Add S/R levels if available
                if let srLevels = mlSummary.srLevels {
                    bridge.setSRLevels(
                        support: srLevels.nearestSupport,
                        resistance: srLevels.nearestResistance
                    )
                }
            }

            // Set indicators based on config
            let config = parent.viewModel.indicatorConfig

            if config.showSMA20 {
                bridge.setIndicator(
                    id: "sma20",
                    name: "SMA(20)",
                    data: parent.viewModel.sma20,
                    color: "#4db8ff"
                )
            }

            if config.showSMA50 {
                bridge.setIndicator(
                    id: "sma50",
                    name: "SMA(50)",
                    data: parent.viewModel.sma50,
                    color: "#ffa600"
                )
            }

            if config.showEMA9 {
                bridge.setIndicator(
                    id: "ema9",
                    name: "EMA(9)",
                    data: parent.viewModel.ema9,
                    color: "#00ffbf"
                )
            }

            if config.showEMA21 {
                bridge.setIndicator(
                    id: "ema21",
                    name: "EMA(21)",
                    data: parent.viewModel.ema21,
                    color: "#ff80b3"
                )
            }

            if config.showSMA200 {
                bridge.setIndicator(
                    id: "sma200",
                    name: "SMA(200)",
                    data: parent.viewModel.sma200,
                    color: "#ff5555"
                )
            }

            // Bollinger Bands
            if config.showBollingerBands {
                bridge.setIndicator(
                    id: "bb_upper",
                    name: "BB Upper",
                    data: parent.viewModel.bollingerUpper,
                    color: "#9966ff"
                )
                bridge.setIndicator(
                    id: "bb_middle",
                    name: "BB Middle",
                    data: parent.viewModel.bollingerMiddle,
                    color: "#9966ff"
                )
                bridge.setIndicator(
                    id: "bb_lower",
                    name: "BB Lower",
                    data: parent.viewModel.bollingerLower,
                    color: "#9966ff"
                )
            }

            // SuperTrend with trend-based coloring and AI factor
            if config.showSuperTrend {
                let superTrendLine = parent.viewModel.superTrendLine
                let trendValues = parent.viewModel.superTrendTrend
                let aiFactorValues = parent.viewModel.superTrendAIFactor  // Use AI adaptive factor
                    
                // Ensure arrays are same length
                let minCount = min(superTrendLine.count, trendValues.count)
                if minCount > 0 {
                    let trendData = (0..<minCount).map { i in
                        IndicatorDataPoint(
                            bar: data.bars[i],
                            value: Double(trendValues[i])
                        )
                    }
                    
                    // Convert AI factor array to IndicatorDataPoint
                    let factorData = (0..<min(minCount, aiFactorValues.count)).map { i in
                        IndicatorDataPoint(
                            bar: data.bars[i],
                            value: aiFactorValues[i]
                        )
                    }
                    
                    print("[WebChartView] SuperTrend: \(minCount) points, AI factors: \(aiFactorValues.prefix(5))")
                    
                    bridge.setSuperTrend(
                        data: Array(superTrendLine.prefix(minCount)),
                        trend: trendData,
                        strength: factorData
                    )

                    // Add inline markers at SuperTrend flips with AI factor badge
                    let markers = superTrendFlipMarkers(
                        bars: data.bars,
                        superTrendLine: superTrendLine,
                        trendValues: trendValues,
                        factorValues: aiFactorValues
                    )
                    if !markers.isEmpty {
                        bridge.setMarkers(markers, seriesId: "supertrend")
                    }
                }
            }

            // Add SuperTrend AI signals if enabled (filtered to match visual segments)
            if config.showSignalMarkers {
                let allSignals = parent.viewModel.superTrendAISignals
                let trendValues = parent.viewModel.superTrendTrend
                
                // Filter signals to only show when visual line segment changes
                // (not every minor trend oscillation)
                var filteredSignals: [SuperTrendSignal] = []
                var lastVisualTrend: Int? = nil
                
                for signal in allSignals {
                    let idx = signal.barIndex
                    guard idx < trendValues.count else { continue }
                    
                    let currentTrend = trendValues[idx]
                    let visualTrendChanged = lastVisualTrend == nil || 
                                            (lastVisualTrend == 1 && currentTrend != 1) ||
                                            (lastVisualTrend != 1 && currentTrend == 1)
                    
                    if visualTrendChanged {
                        filteredSignals.append(signal)
                        lastVisualTrend = currentTrend
                    }
                }
                
                if !filteredSignals.isEmpty {
                    bridge.setSignals(filteredSignals)
                }
            }

            // Volume sub-panel
            if config.showVolume {
                bridge.setVolume(bars: data.bars)
            } else {
                bridge.hidePanel("volume")
            }

            // Oscillator sub-panels
            if config.showRSI {
                bridge.setRSI(data: parent.viewModel.rsi)
            } else {
                bridge.hidePanel("rsi")
            }

            if config.showMACD {
                bridge.setMACD(
                    line: parent.viewModel.macdLine,
                    signal: parent.viewModel.macdSignal,
                    histogram: parent.viewModel.macdHistogram
                )
            } else {
                bridge.hidePanel("macd")
            }

            if config.showStochastic {
                bridge.setStochastic(
                    k: parent.viewModel.stochasticK,
                    d: parent.viewModel.stochasticD
                )
            } else {
                bridge.hidePanel("stochastic")
            }

            if config.showKDJ {
                bridge.setKDJ(
                    k: parent.viewModel.kdjK,
                    d: parent.viewModel.kdjD,
                    j: parent.viewModel.kdjJ
                )
            } else {
                bridge.hidePanel("kdj")
            }

            if config.showADX {
                bridge.setADX(
                    adx: parent.viewModel.adxLine,
                    plusDI: parent.viewModel.plusDI,
                    minusDI: parent.viewModel.minusDI
                )
            } else {
                bridge.hidePanel("adx")
            }

            if config.showATR {
                bridge.setATR(data: parent.viewModel.atr)
            } else {
                bridge.hidePanel("atr")
            }

            print("[WebChartView] Chart updated with \(data.bars.count) bars")

            applyInitialZoomIfNeeded(bars: data.bars)

            // Restore prior visible range after overlays are applied
            if let preservedRange {
                bridge.send(.setVisibleRange(from: preservedRange.from, to: preservedRange.to))
            }
        }

        private func applyInitialZoomIfNeeded(bars: [OHLCBar]) {
            guard !hasAppliedInitialZoom else { return }
            guard parent.bridge.isReady else { return }

            let sorted = bars.sorted { $0.ts < $1.ts }
            guard let last = sorted.last else { return }

            // Timeframe-aware lookback - optimized for barSpacing of 12px
            let lookbackSeconds: TimeInterval
            switch parent.viewModel.timeframe {
            case .m15:
                lookbackSeconds = 5 * 24 * 60 * 60   // last 5 days for 15m (~320 bars)
            case .h1:
                lookbackSeconds = 10 * 24 * 60 * 60  // last 10 days for 1h (~160 bars)
            case .h4:
                lookbackSeconds = 60 * 24 * 60 * 60  // last 60 days for 4h (~360 bars)
            case .d1:
                lookbackSeconds = 180 * 24 * 60 * 60 // last ~6 months for daily (~126 bars)
            case .w1:
                lookbackSeconds = 2 * 365 * 24 * 60 * 60 // last 2 years for weekly (~104 bars)
            }

            let endDate = last.ts
            let startTarget = endDate.addingTimeInterval(-lookbackSeconds)
            let startBar = sorted.first(where: { $0.ts >= startTarget }) ?? sorted.first
            guard let start = startBar else { return }

            parent.bridge.send(
                .setVisibleRange(
                    from: Int(start.ts.timeIntervalSince1970),
                    to: Int(endDate.timeIntervalSince1970)
                )
            )

            hasAppliedInitialZoom = true
        }

        /// Build markers for SuperTrend flips with AI factor badges
        private func superTrendFlipMarkers(
            bars: [OHLCBar],
            superTrendLine: [IndicatorDataPoint],
            trendValues: [Int],
            factorValues: [Double]
        ) -> [ChartMarker] {
            let count = min(bars.count, superTrendLine.count, trendValues.count)
            guard count > 1 else { return [] }

            var markers: [ChartMarker] = []
            for i in 1..<count {
                let prevTrend = trendValues[i - 1]
                let currTrend = trendValues[i]
                guard prevTrend != currTrend else { continue }

                let factor = i < factorValues.count ? factorValues[i] : 1.0
                let labelText = String(format: "%.0f", factor)
                let isBullish = currTrend == 1
                let color = isBullish ? "#26a69a" : "#ef5350"

                let marker = ChartMarker(
                    time: Int(bars[i].ts.timeIntervalSince1970),
                    type: isBullish ? "buy" : "sell",
                    text: labelText,
                    color: color,
                    position: isBullish ? "belowBar" : "aboveBar",
                    shape: isBullish ? "arrowUp" : "arrowDown",
                    size: 2
                )
                markers.append(marker)
            }
            return markers
        }
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    func makeNSView(context: Context) -> WKWebView {
        // Configure WKWebView
        let config = WKWebViewConfiguration()
        config.defaultWebpagePreferences.allowsContentJavaScript = true

        // Enable developer extras for debugging (optional, remove in production)
        config.preferences.setValue(true, forKey: "developerExtrasEnabled")

        // Register message handler for JS → Swift communication
        config.userContentController.add(bridge, name: "bridge")

        // Create webview
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = context.coordinator

        // Attach bridge to webview
        bridge.attach(to: webView)

        // Allow file:// URL access for local resources
        if #available(macOS 13.3, *) {
            webView.isInspectable = true  // Enable Web Inspector
        }

        // Load bundled HTML
        loadChart(in: webView)

        // Setup data bindings
        context.coordinator.setupDataBindings()

        return webView
    }

    func updateNSView(_ webView: WKWebView, context: Context) {
        // Updates are handled via Combine subscriptions in Coordinator
    }

    private func loadChart(in webView: WKWebView) {
        // First try to find the resources in the app bundle (may be in WebChart subdirectory or at root)
        if let htmlURL = Bundle.main.url(
            forResource: "index",
            withExtension: "html",
            subdirectory: "WebChart"
        ) {
            let directoryURL = htmlURL.deletingLastPathComponent()
            webView.loadFileURL(htmlURL, allowingReadAccessTo: directoryURL)
            print("[WebChartView] Loading chart from bundle subdirectory: \(htmlURL)")
            return
        }

        // Try finding at bundle root (when resources are not in subdirectory)
        if let htmlURL = Bundle.main.url(forResource: "index", withExtension: "html"),
           let resourcesURL = Bundle.main.resourceURL {
            webView.loadFileURL(htmlURL, allowingReadAccessTo: resourcesURL)
            print("[WebChartView] Loading chart from bundle root: \(htmlURL)")
            return
        }

        // Fallback: try to find in Resources folder (for development)
        #if DEBUG
        if let devRoot = ProcessInfo.processInfo.environment["WEBCHART_DEV_ROOT"] {
            let htmlURL = URL(fileURLWithPath: devRoot).appendingPathComponent("index.html")
            if FileManager.default.fileExists(atPath: htmlURL.path) {
                webView.loadFileURL(htmlURL, allowingReadAccessTo: htmlURL.deletingLastPathComponent())
                print("[WebChartView] Loading chart from env WEBCHART_DEV_ROOT: \(htmlURL)")
                return
            }
        }

        let resourcesPath = "/Users/ericpeterson/SwiftBolt_ML/client-macos/SwiftBoltML/Resources/WebChart"
        let htmlPath = "\(resourcesPath)/index.html"

        if FileManager.default.fileExists(atPath: htmlPath) {
            let htmlURL = URL(fileURLWithPath: htmlPath)
            let directoryURL = htmlURL.deletingLastPathComponent()
            webView.loadFileURL(htmlURL, allowingReadAccessTo: directoryURL)
            print("[WebChartView] Loading chart from development path: \(htmlURL)")
            return
        }
        #endif

        print("[WebChartView] ERROR: Could not find chart HTML file")
    }

    /// Cleanup when view is dismantled
    static func dismantleNSView(_ nsView: WKWebView, coordinator: Coordinator) {
        // Remove message handler to prevent memory leaks
        nsView.configuration.userContentController.removeScriptMessageHandler(forName: "bridge")
        nsView.navigationDelegate = nil
        coordinator.cancellables.removeAll()
    }
}

// MARK: - Preview

#Preview {
    WebChartView(viewModel: ChartViewModel())
        .frame(width: 800, height: 500)
}

// MARK: - Convenience Modifiers

extension WebChartView {
    /// Add a custom event handler
    func onChartEvent(_ handler: @escaping (ChartEvent) -> Void) -> some View {
        self.onReceive(bridge.eventPublisher) { event in
            handler(event)
        }
    }
}

// MARK: - Optional: Standalone Preview Container

/// For testing the web chart in isolation
struct WebChartPreviewContainer: View {
    @StateObject private var viewModel = ChartViewModel()

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text("Lightweight Charts Preview")
                    .font(.headline)
                Spacer()
                Button("Load Sample Data") {
                    loadSampleData()
                }
                .buttonStyle(.borderedProminent)
            }
            .padding()

            Divider()

            // Chart
            WebChartView(viewModel: viewModel)
        }
        .frame(minWidth: 600, minHeight: 400)
    }

    private func loadSampleData() {
        // Generate sample candlestick data
        var bars: [OHLCBar] = []
        var price: Double = 100.0
        let baseDate = Date().addingTimeInterval(-86400 * 100)  // 100 days ago

        for i in 0..<100 {
            let date = baseDate.addingTimeInterval(Double(i) * 86400)
            let change = Double.random(in: -3...3)
            let open = price
            price += change
            let close = price
            let high = max(open, close) + Double.random(in: 0...2)
            let low = min(open, close) - Double.random(in: 0...2)
            let volume = Double.random(in: 1_000_000...10_000_000)

            bars.append(OHLCBar(
                ts: date,
                open: open,
                high: high,
                low: low,
                close: close,
                volume: volume
            ))
        }

        // For preview, just print the sample bar count
        print("[Preview] Would load \(bars.count) sample bars")
    }
}

#Preview("Standalone Container") {
    WebChartPreviewContainer()
}

