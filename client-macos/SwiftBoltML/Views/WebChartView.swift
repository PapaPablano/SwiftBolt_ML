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
        var lastCandleSignature: (count: Int, lastTs: Int)?

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

            parent.viewModel.$selectedSymbol
                .receive(on: DispatchQueue.main)
                .sink { [weak self] _ in
                    guard let self else { return }
                    self.lastVisibleRange = nil
                    self.hasAppliedInitialZoom = false
                }
                .store(in: &cancellables)

            parent.viewModel.$timeframe
                .receive(on: DispatchQueue.main)
                .sink { [weak self] _ in
                    guard let self else { return }
                    self.lastVisibleRange = nil
                    self.hasAppliedInitialZoom = false
                }
                .store(in: &cancellables)

            // Track visible range emitted from JS so we can preserve it on indicator toggles
            parent.bridge.eventPublisher
                .receive(on: DispatchQueue.main)
                .sink { [weak self] event in
                    guard let self else { return }
                    if case let .visibleRangeChange(from, to) = event {
                        self.lastVisibleRange = (from, to)
                        self.parent.viewModel.maybeLoadMoreHistory(visibleFrom: from)
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

            parent.viewModel.$selectedForecastHorizon
                .removeDuplicates()
                .receive(on: DispatchQueue.main)
                .sink { [weak self] _ in
                    guard let self = self else { return }
                    let performUpdate = {
                        if self.parent.viewModel.chartDataV2 != nil {
                            self.applyForecastOverlay()
                        } else if let data = self.parent.viewModel.chartData {
                            self.applyLegacyForecastOverlay(with: data)
                        }
                    }

                    if self.parent.bridge.isReady {
                        performUpdate()
                    } else {
                        self.parent.bridge.$isReady
                            .filter { $0 }
                            .first()
                            .sink { _ in
                                performUpdate()
                            }
                            .store(in: &self.cancellables)
                    }
                }
                .store(in: &cancellables)


            // Subscribe to real-time forecast data changes and re-render chart with overlays
            // Debounce to prevent rapid duplicate renders
            parent.viewModel.$realtimeChartData
                .debounce(for: .milliseconds(300), scheduler: DispatchQueue.main)
                .receive(on: DispatchQueue.main)
                .sink { [weak self] realtimeData in
                    guard let self = self,
                          self.parent.bridge.isReady,
                          realtimeData != nil else { return }

                    print("[WebChartView] Real-time data updated, re-rendering chart with overlays")

                    // Trigger chart update with real-time overlays
                    if let dataV2 = self.parent.viewModel.chartDataV2 {
                        self.updateChartV2(with: dataV2)
                    } else if let data = self.parent.viewModel.chartData {
                        self.updateChart(with: data)
                    }
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
            let forecastBars = data.layers.forecast.data
            
            print("[WebChartView] Updating chart with V2 layered data")
            print("[WebChartView] - Historical: \(data.layers.historical.count) bars")
            print("[WebChartView] - Intraday: \(data.layers.intraday.count) bars")
            print("[WebChartView] - Forecast: \(forecastBars.count) bars")
            
            // Guard: only render if we have candles
            let allBars = data.allBars
            guard !allBars.isEmpty else {
                print("[WebChartView] ⚠️ No candles, clearing chart")
                bridge.send(.clearAll)
                return
            }
            
            // Choose base candles based on timeframe
            let baseCandles: [OHLCBar]
            // For intraday timeframes (15m/1h/4h), merge historical + today's intraday for continuity
            // This ensures the web chart shows a continuous series across backfilled history and live bars
            if parent.viewModel.timeframe.isIntraday {
                baseCandles = (data.layers.historical.data + data.layers.intraday.data)
            } else {
                // For daily/weekly, combine historical + today's intraday
                baseCandles = data.layers.historical.data + data.layers.intraday.data
            }
            
            // Sanitize candles: sort and enforce strictly increasing timestamps to avoid time jumps
            let sortedBase = baseCandles.sorted { $0.ts < $1.ts }
            var uniqueCandles: [OHLCBar] = []
            uniqueCandles.reserveCapacity(sortedBase.count)
            var lastTs: Date? = nil
            for bar in sortedBase {
                if let lt = lastTs, bar.ts <= lt {
                    continue // drop non-increasing timestamps
                }
                uniqueCandles.append(bar)
                lastTs = bar.ts
            }

            // Debug first/last for diagnostics
            if let first = uniqueCandles.first, let last = uniqueCandles.last {
                print("[WebChartView] Base candles sanitized: count=\(uniqueCandles.count), first=\(first.ts), last=\(last.ts)")
            }

            // Set candlestick data using sanitized candles
            let candleSignature = (
                count: uniqueCandles.count,
                lastTs: Int((uniqueCandles.last?.ts.timeIntervalSince1970 ?? 0))
            )
            if lastCandleSignature?.count != candleSignature.count || lastCandleSignature?.lastTs != candleSignature.lastTs {
                lastCandleSignature = candleSignature
                hasAppliedInitialZoom = false
            }

            bridge.setCandles(from: uniqueCandles)

            // Only apply ML forecast overlays if we DON'T have real-time data
            // (real-time overlays are more current and will be applied separately)
            if parent.viewModel.realtimeChartData == nil {
                // Forecast confidence badge/overlay for all timeframes (Fix E: removed intraday-only constraint)
                if let ml = data.mlSummary, let lastBar = uniqueCandles.last {
                    // Remove previous confidence lines to avoid duplicates
                    bridge.send(.removePriceLines(category: "forecast-confidence"))

                    // Derive a label and color from overall prediction
                    let label = (ml.overallLabel ?? "neutral").lowercased()
                    let color = forecastColorHex(for: label)

                    // Add a labeled price line as a badge at the last close
                    let price = lastBar.close
                    let title = "AI: \(label.uppercased()) \(Int((ml.confidence) * 100))%"
                    let options = PriceLineOptions(
                        color: color,
                        lineWidth: 2,
                        lineStyle: 1,
                        showLabel: true,
                        title: title,
                        category: "forecast-confidence"
                    )
                    bridge.send(.addPriceLine(seriesId: "candles", price: price, options: options))
                }

                // Add forecast data if present
                if !forecastBars.isEmpty {
                    applyForecastOverlay(using: forecastBars)
                } else {
                    applyForecastTargetLine(
                        currentPrice: uniqueCandles.last?.close,
                        label: data.mlSummary?.overallLabel
                    )
                }
            } else {
                print("[WebChartView] Skipping ML forecast overlay - real-time data available")
            }

            // Clear previous overlays/indicators (keeps candles and markers)
            // Note: this clears SMA, EMA, Bollinger Bands, etc., but NOT markers
            bridge.send(.clearIndicators)

            // Push indicator configuration down to bridge (drives JS-side panel layout)
            let config = parent.viewModel.indicatorConfig
            bridge.setIndicatorConfig(config, timeframe: parent.viewModel.timeframe)
            
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

            // Apply real-time forecast overlays if available (integrated into main chart flow)
            if let realtimeData = parent.viewModel.realtimeChartData, !realtimeData.forecasts.isEmpty {
                print("[WebChartView] updateChartV2: Applying \(realtimeData.forecasts.count) real-time forecast overlays")
                applyRealtimeForecastOverlays(realtimeData)
            }

            applyInitialZoomIfNeeded(bars: uniqueCandles)

            // Restore prior visible range after overlays are applied
            if let preservedRange,
               let first = uniqueCandles.first,
               let last = uniqueCandles.last {
                let firstTs = Int(first.ts.timeIntervalSince1970)
                let lastTs = Int(last.ts.timeIntervalSince1970)
                if preservedRange.to >= firstTs && preservedRange.from <= lastTs {
                    bridge.send(.setVisibleRange(from: preservedRange.from, to: preservedRange.to))
                } else {
                    bridge.send(.scrollToRealTime)
                }
            }
            
            // Set Support & Resistance Indicators (for both WebChart and legacy)
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

        private func applyForecastOverlay(using bars: [OHLCBar]? = nil) {
            let forecastBars = bars ?? parent.viewModel.chartDataV2?.layers.forecast.data ?? []
            guard !forecastBars.isEmpty else { return }
            let summary = parent.viewModel.chartDataV2?.mlSummary ?? parent.viewModel.chartData?.mlSummary
            if let summary,
               let lastBar = parent.viewModel.bars.last,
               applyHorizonTargetLines(summary: summary, currentBar: lastBar) {
                // Skip standard forecast bands for daily multi-horizon targets
                return
            }

            parent.bridge.send(.removeSeries(id: "forecast-1d"))
            parent.bridge.send(.removeSeries(id: "forecast-1w"))
            parent.bridge.send(.removeSeries(id: "forecast-1m"))

            // Use simplified forecast visualization: dots + line + horizontal price line
            let currentPrice = parent.viewModel.bars.last?.close
            parent.bridge.setSimpleForecast(from: forecastBars, currentPrice: currentPrice)
        }

        private func applyLegacyForecastOverlay(with data: ChartResponse) {
            guard let mlSummary = data.mlSummary,
                  let selectedSeries = parent.viewModel.selectedForecastSeries ?? mlSummary.horizons.first else {
                return
            }

            if let lastBar = parent.viewModel.bars.last,
               applyHorizonTargetLines(summary: mlSummary, currentBar: lastBar) {
                return
            }

            parent.bridge.send(.removeSeries(id: "forecast-1d"))
            parent.bridge.send(.removeSeries(id: "forecast-1w"))
            parent.bridge.send(.removeSeries(id: "forecast-1m"))

            // Convert ForecastSeries points to OHLCBar for simplified visualization
            let forecastBars = selectedSeries.points.map { point in
                OHLCBar(
                    ts: Date(timeIntervalSince1970: TimeInterval(point.ts)),
                    open: point.value,
                    high: max(point.value, point.upper, point.lower),
                    low: min(point.value, point.upper, point.lower),
                    close: point.value,
                    volume: 0,
                    upperBand: point.upper,
                    lowerBand: point.lower,
                    confidenceScore: nil
                )
            }

            let currentPrice = data.bars.last?.close
            parent.bridge.setSimpleForecast(from: forecastBars, currentPrice: currentPrice)

            if let srLevels = mlSummary.srLevels {
                parent.bridge.setSRLevels(
                    support: srLevels.nearestSupport,
                    resistance: srLevels.nearestResistance
                )
            }
        }

        /// Apply real-time forecast overlays from the real-time API
        private func applyRealtimeForecastOverlays(_ realtimeData: RealtimeChartData) {
            guard !realtimeData.forecasts.isEmpty else { return }

            print("[WebChartView] Processing \(realtimeData.forecasts.count) forecasts for display")

            // Deduplicate markers by price level (within $0.50 tolerance)
            // This prevents multiple markers from clustering too close together
            var uniqueMarkers: [ChartMarker] = []
            var seenPrices: Set<String> = []

            for forecast in realtimeData.forecasts {
                // Round price to nearest 0.50 for deduplication
                let roundedPrice = (forecast.price * 2).rounded() / 2
                let priceKey = String(format: "%.2f", roundedPrice)

                guard !seenPrices.contains(priceKey) else { continue }
                seenPrices.insert(priceKey)

                var marker = forecast.toChartMarker()
                marker.size = 1  // Smaller, cleaner markers
                uniqueMarkers.append(marker)
            }

            print("[WebChartView] After deduplication: \(uniqueMarkers.count) unique markers")

            // Sample markers to show every Nth marker for better spacing
            // For intraday (many forecasts), sample more aggressively
            let sampleRate = realtimeData.forecasts.count > 100 ? 5 : 2
            let sampledMarkers = stride(from: 0, to: uniqueMarkers.count, by: sampleRate)
                .map { uniqueMarkers[$0] }

            print("[WebChartView] After sampling (every \(sampleRate)): \(sampledMarkers.count) markers to render")

            // Set markers on the candles series
            if !sampledMarkers.isEmpty {
                parent.bridge.setMarkers(sampledMarkers, seriesId: "candles")
            }

            // Apply price line for the latest forecast with distinctive styling
            if let latestForecast = realtimeData.latestForecast {
                let (price, color, label) = latestForecast.toPriceLine()
                let options = PriceLineOptions(
                    color: color,
                    lineWidth: 3,  // Thicker for visibility
                    lineStyle: 3,  // Dotted line
                    showLabel: true,
                    title: "RT: " + label  // Prefix to distinguish from ML targets
                )
                parent.bridge.send(.addPriceLine(seriesId: "candles", price: price, options: options))
            }
        }

        private func updateChart(with data: ChartResponse) {
            let bridge = parent.bridge
            // Preserve current visible range to avoid reset when toggling indicators
            let preservedRange = lastVisibleRange ?? bridge.visibleRange

            // Clear previous overlays/indicators (keeps candles)
            bridge.send(.clearIndicators)
            bridge.send(.removePriceLines(category: "forecast-target"))
            bridge.send(.removePriceLines(category: "forecast-targets"))
            bridge.send(.removePriceLines(category: "forecast-confidence"))

            // Set candlestick data
            let candleSignature = (
                count: data.bars.count,
                lastTs: Int((data.bars.last?.ts.timeIntervalSince1970 ?? 0))
            )
            if lastCandleSignature?.count != candleSignature.count || lastCandleSignature?.lastTs != candleSignature.lastTs {
                lastCandleSignature = candleSignature
                hasAppliedInitialZoom = false
            }

            bridge.setCandles(from: data.bars)

            // Only apply legacy overlays if real-time data is NOT available
            if parent.viewModel.realtimeChartData == nil {
                applyLegacyForecastOverlay(with: data)
            } else {
                print("[WebChartView] Skipping legacy forecast overlay - real-time data available")
            }

            // Push indicator configuration down to bridge (drives JS-side panel layout)
            let config = parent.viewModel.indicatorConfig
            bridge.setIndicatorConfig(config, timeframe: parent.viewModel.timeframe)

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

            // Apply real-time forecast overlays if available (integrated into main chart flow)
            if let realtimeData = parent.viewModel.realtimeChartData, !realtimeData.forecasts.isEmpty {
                print("[WebChartView] updateChart: Applying \(realtimeData.forecasts.count) real-time forecast overlays")
                applyRealtimeForecastOverlays(realtimeData)
            }

            print("[WebChartView] Chart updated with \(data.bars.count) bars")

            applyInitialZoomIfNeeded(bars: data.bars)

            // Restore prior visible range after overlays are applied
            if let preservedRange {
                let sorted = data.bars.sorted { $0.ts < $1.ts }
                if let first = sorted.first, let last = sorted.last {
                    let firstTs = Int(first.ts.timeIntervalSince1970)
                    let lastTs = Int(last.ts.timeIntervalSince1970)
                    if preservedRange.to >= firstTs && preservedRange.from <= lastTs {
                        bridge.send(.setVisibleRange(from: preservedRange.from, to: preservedRange.to))
                    } else {
                        bridge.send(.scrollToRealTime)
                    }
                }
            }
        }

        private func forecastColorHex(for label: String?) -> String {
            switch (label ?? "neutral").lowercased() {
            case "bullish": return "#4de680" // green
            case "bearish": return "#ff5959" // red
            default: return "#ffbf00" // amber
            }
        }

        private func rgbaColor(hex: String, alpha: Double) -> String {
            let cleaned = hex.trimmingCharacters(in: CharacterSet(charactersIn: "#"))
            guard cleaned.count == 6, let intVal = Int(cleaned, radix: 16) else {
                return hex
            }
            let r = (intVal >> 16) & 0xff
            let g = (intVal >> 8) & 0xff
            let b = intVal & 0xff
            let clamped = max(0.0, min(1.0, alpha))
            return String(format: "rgba(%d,%d,%d,%.2f)", r, g, b, clamped)
        }

        private func isDailyMultiHorizon(_ summary: MLSummary) -> Bool {
            let dailySet: Set<String> = ["1D", "1W", "1M"]
            let labels = summary.horizons.map { $0.horizon.uppercased() }
            return labels.count >= 2 && labels.allSatisfy { dailySet.contains($0) }
        }

        private func applyHorizonTargetLines(summary: MLSummary, currentBar: OHLCBar) -> Bool {
            let dailySet: Set<String> = ["1D", "1W", "1M"]
            let horizons = summary.horizons.filter { dailySet.contains($0.horizon.uppercased()) }
            guard !horizons.isEmpty else { return false }

            let lastTime = Int(currentBar.ts.timeIntervalSince1970)
            let currentPrice = currentBar.close
            let baseColor = forecastColorHex(for: summary.overallLabel)

            let lineSpecs: [(String, String, String, Int)] = [
                ("1D", "forecast-1d", "1D Target", 0),
                ("1W", "forecast-1w", "1W Target", 1),
                ("1M", "forecast-1m", "1M Target", 2),
            ]

            for (_, seriesId, _, _) in lineSpecs {
                parent.bridge.send(.removeSeries(id: seriesId))
            }
            parent.bridge.send(.removeSeries(id: "forecast-mid"))
            parent.bridge.send(.removeSeries(id: "forecast-upper"))
            parent.bridge.send(.removeSeries(id: "forecast-lower"))
            parent.bridge.send(.removeSeries(id: "forecast-band"))

            for (label, seriesId, title, style) in lineSpecs {
                guard let series = horizons.first(where: { $0.horizon.uppercased() == label }) else { continue }
                guard let targetPoint = series.points.max(by: { $0.ts < $1.ts }) else { continue }
                let targetValue = series.targets?.tp1 ?? targetPoint.value
                let targetTime = targetPoint.ts
                guard targetTime > 0 else { continue }

                let lineData = [
                    LightweightDataPoint(time: lastTime, value: currentPrice),
                    LightweightDataPoint(time: targetTime, value: targetValue),
                ]

                let options = LineOptions(
                    color: rgbaColor(hex: baseColor, alpha: style == 0 ? 0.95 : style == 1 ? 0.7 : 0.5),
                    lineWidth: style == 0 ? 2 : 1,
                    lineStyle: style == 0 ? 2 : 1,
                    name: title
                )
                parent.bridge.send(.setLine(id: seriesId, data: lineData, options: options))
            }

            return true
        }

        private func applyForecastTargetLine(
            currentPrice: Double?,
            label: String?,
            series: ForecastSeries? = nil
        ) {
            parent.bridge.send(.removePriceLines(category: "forecast-target"))
            parent.bridge.send(.removePriceLines(category: "forecast-targets"))
        }

        private func applyInitialZoomIfNeeded(bars: [OHLCBar]) {
            guard !hasAppliedInitialZoom else { return }
            guard parent.bridge.isReady else { return }

            let sorted = bars.sorted { $0.ts < $1.ts }
            guard let last = sorted.last else { return }

            let targetVisibleBars: Int
            switch parent.viewModel.timeframe {
            case .m15:
                targetVisibleBars = 180
            case .h1:
                targetVisibleBars = 195
            case .h4:
                targetVisibleBars = 120
            case .d1:
                targetVisibleBars = 180
            case .w1:
                targetVisibleBars = 200
            }

            let startIndex = max(0, sorted.count - targetVisibleBars)
            let start = sorted[startIndex]
            let endDate = last.ts

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

#if DEBUG
struct WebChartView_Previews: PreviewProvider {
    static var previews: some View {
        WebChartView(viewModel: ChartViewModel())
            .frame(width: 800, height: 500)
    }
}
#endif

// MARK: - Convenience Modifiers

extension WebChartView {
    /// Add a custom event handler
    func onChartEvent(_ handler: @escaping (ChartEvent) -> Void) -> some View {
        self.onReceive(bridge.eventPublisher) { event in
            handler(event)
        }
    }
}

#if DEBUG
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

struct WebChartPreviewContainer_Previews: PreviewProvider {
    static var previews: some View {
        WebChartPreviewContainer()
    }
}
#endif
