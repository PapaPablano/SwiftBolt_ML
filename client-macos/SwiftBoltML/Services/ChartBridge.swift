import Foundation
import WebKit
import Combine

// MARK: - Chart Commands

/// Type-safe commands for the Lightweight Charts JS API
enum ChartCommand: Encodable {
    case initialize(options: ChartOptions?)
    case setCandles(data: [LightweightCandle])
    case updateCandle(candle: LightweightCandle)
    case setLine(id: String, data: [LightweightDataPoint], options: LineOptions?)
    case setForecast(midData: [LightweightDataPoint], upperData: [LightweightDataPoint], lowerData: [LightweightDataPoint], options: ForecastOptions?)
    case setMarkers(seriesId: String, markers: [ChartMarker])
    case addPriceLine(seriesId: String, price: Double, options: PriceLineOptions?)
    case removeSeries(id: String)
    case clearIndicators
    case setVisibleRange(from: Int, to: Int)
    case scrollToRealTime
    case fitContent

    // Oscillator sub-panels
    case setRSI(data: [LightweightDataPoint])
    case setMACD(line: [LightweightDataPoint], signal: [LightweightDataPoint], histogram: [LightweightDataPoint])
    case setStochastic(kData: [LightweightDataPoint], dData: [LightweightDataPoint])
    case setKDJ(kData: [LightweightDataPoint], dData: [LightweightDataPoint], jData: [LightweightDataPoint])
    case setADX(adxData: [LightweightDataPoint], plusDI: [LightweightDataPoint], minusDI: [LightweightDataPoint])
    case setATR(data: [LightweightDataPoint])
    case setVolume(data: [VolumeDataPoint])
    case setSuperTrend(data: [LightweightDataPoint], trendData: [LightweightDataPoint], strengthData: [LightweightDataPoint])
    case hidePanel(panel: String)

    // Custom encoding to match JS API
    private enum CodingKeys: String, CodingKey {
        case type, options, data, candle, id, midData, upperData, lowerData
        case seriesId, markers, price, from, to
        case line, signal, histogram, kData, dData, jData, adxData, plusDI, minusDI, panel
        case trendData, strengthData
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)

        switch self {
        case .initialize(let options):
            try container.encode("init", forKey: .type)
            try container.encodeIfPresent(options, forKey: .options)

        case .setCandles(let data):
            try container.encode("setCandles", forKey: .type)
            try container.encode(data, forKey: .data)

        case .updateCandle(let candle):
            try container.encode("updateCandle", forKey: .type)
            try container.encode(candle, forKey: .candle)

        case .setLine(let id, let data, let options):
            try container.encode("setLine", forKey: .type)
            try container.encode(id, forKey: .id)
            try container.encode(data, forKey: .data)
            try container.encodeIfPresent(options, forKey: .options)

        case .setForecast(let midData, let upperData, let lowerData, let options):
            try container.encode("setForecast", forKey: .type)
            try container.encode(midData, forKey: .midData)
            try container.encode(upperData, forKey: .upperData)
            try container.encode(lowerData, forKey: .lowerData)
            try container.encodeIfPresent(options, forKey: .options)

        case .setMarkers(let seriesId, let markers):
            try container.encode("setMarkers", forKey: .type)
            try container.encode(seriesId, forKey: .seriesId)
            try container.encode(markers, forKey: .markers)

        case .addPriceLine(let seriesId, let price, let options):
            try container.encode("addPriceLine", forKey: .type)
            try container.encode(seriesId, forKey: .seriesId)
            try container.encode(price, forKey: .price)
            try container.encodeIfPresent(options, forKey: .options)

        case .removeSeries(let id):
            try container.encode("removeSeries", forKey: .type)
            try container.encode(id, forKey: .id)

        case .clearIndicators:
            try container.encode("clearIndicators", forKey: .type)

        case .setVisibleRange(let from, let to):
            try container.encode("setVisibleRange", forKey: .type)
            try container.encode(from, forKey: .from)
            try container.encode(to, forKey: .to)

        case .scrollToRealTime:
            try container.encode("scrollToRealTime", forKey: .type)

        case .fitContent:
            try container.encode("fitContent", forKey: .type)

        case .setRSI(let data):
            try container.encode("setRSI", forKey: .type)
            try container.encode(data, forKey: .data)

        case .setMACD(let line, let signal, let histogram):
            try container.encode("setMACD", forKey: .type)
            try container.encode(line, forKey: .line)
            try container.encode(signal, forKey: .signal)
            try container.encode(histogram, forKey: .histogram)

        case .setStochastic(let kData, let dData):
            try container.encode("setStochastic", forKey: .type)
            try container.encode(kData, forKey: .kData)
            try container.encode(dData, forKey: .dData)

        case .setKDJ(let kData, let dData, let jData):
            try container.encode("setKDJ", forKey: .type)
            try container.encode(kData, forKey: .kData)
            try container.encode(dData, forKey: .dData)
            try container.encode(jData, forKey: .jData)

        case .setADX(let adxData, let plusDI, let minusDI):
            try container.encode("setADX", forKey: .type)
            try container.encode(adxData, forKey: .adxData)
            try container.encode(plusDI, forKey: .plusDI)
            try container.encode(minusDI, forKey: .minusDI)

        case .setATR(let data):
            try container.encode("setATR", forKey: .type)
            try container.encode(data, forKey: .data)

        case .setVolume(let data):
            try container.encode("setVolume", forKey: .type)
            try container.encode(data, forKey: .data)

        case .setSuperTrend(let data, let trendData, let strengthData):
            try container.encode("setSuperTrend", forKey: .type)
            try container.encode(data, forKey: .data)
            try container.encode(trendData, forKey: .trendData)
            try container.encode(strengthData, forKey: .strengthData)

        case .hidePanel(let panel):
            try container.encode("hidePanel", forKey: .type)
            try container.encode(panel, forKey: .panel)
        }
    }
}

// MARK: - Data Models for Lightweight Charts

/// Candle data in Lightweight Charts format
struct LightweightCandle: Encodable {
    let time: Int  // Unix timestamp in seconds
    let open: Double
    let high: Double
    let low: Double
    let close: Double
}

/// Generic data point for line series
struct LightweightDataPoint: Encodable {
    let time: Int  // Unix timestamp in seconds
    let value: Double
}

/// Volume data point with direction for coloring
struct VolumeDataPoint: Encodable {
    let time: Int  // Unix timestamp in seconds
    let value: Double
    let direction: String  // "up" or "down"
    let color: String?
}

/// Chart initialization options
struct ChartOptions: Encodable {
    var width: Int?
    var height: Int?
    var theme: String?  // "dark" or "light"
}

/// Line series options
struct LineOptions: Encodable {
    var color: String?
    var lineWidth: Int?
    var lineStyle: Int?  // 0=Solid, 1=Dotted, 2=Dashed, 3=LargeDashed, 4=SparseDotted
    var name: String?
}

/// Forecast overlay options
struct ForecastOptions: Encodable {
    var color: String?
    var bandColor: String?
}

/// Price line options
struct PriceLineOptions: Encodable {
    var color: String?
    var lineWidth: Int?
    var lineStyle: Int?
    var showLabel: Bool?
    var title: String?
}

/// Chart marker (buy/sell signals)
struct ChartMarker: Encodable {
    let time: Int
    let type: String  // "buy" or "sell"
    var text: String?
    var color: String?
    var position: String?  // "aboveBar", "belowBar", "inBar"
    var shape: String?     // "circle", "square", "arrowUp", "arrowDown"
    var size: Int?
}

// MARK: - Chart Events from JS

/// Events received from the JS chart
enum ChartEvent {
    case ready
    case crosshairMove(time: Int, price: Double, ohlc: OHLC?)
    case visibleRangeChange(from: Int, to: Int)
    case unknown(type: String, data: [String: Any])

    struct OHLC {
        let open: Double
        let high: Double
        let low: Double
        let close: Double
    }
}

// MARK: - Chart Bridge

/// Bridge for Swift ↔ JavaScript communication with Lightweight Charts
@MainActor
final class ChartBridge: NSObject, ObservableObject {
    // MARK: - Published State

    @Published private(set) var isReady = false
    @Published private(set) var lastCrosshairData: ChartEvent.OHLC?
    @Published private(set) var visibleRange: (from: Int, to: Int)?

    // MARK: - Private State

    private weak var webView: WKWebView?
    private var pendingCommands: [String] = []
    private let encoder = JSONEncoder()

    // Event publisher for external subscribers
    let eventPublisher = PassthroughSubject<ChartEvent, Never>()

    // MARK: - Public API

    /// Attach to a WKWebView
    func attach(to webView: WKWebView) {
        self.webView = webView
    }

    /// Send a command to the chart
    func send(_ command: ChartCommand) {
        guard let jsonString = encodeCommand(command) else {
            print("[ChartBridge] Failed to encode command")
            return
        }

        let js = "window.chartApi.apply(\(jsonString))"

        if isReady {
            executeJS(js)
        } else {
            pendingCommands.append(js)
        }
    }

    /// Send multiple commands at once (more efficient)
    func sendBatch(_ commands: [ChartCommand]) {
        for command in commands {
            send(command)
        }
    }

    // MARK: - Convenience Methods

    /// Set candlestick data
    func setCandles(from bars: [OHLCBar]) {
        // CRITICAL: Sort bars by timestamp to ensure chronological order
        let sortedBars = bars.sorted { $0.ts < $1.ts }
        
        let candleData = sortedBars.map { bar in
            LightweightCandle(
                time: Int(bar.ts.timeIntervalSince1970 * 1000),  // Convert to milliseconds
                open: bar.open,
                high: bar.high,
                low: bar.low,
                close: bar.close
            )
        }
        
        // Debug: Log first and last candles to verify data
        if let first = sortedBars.first, let last = sortedBars.last {
            print("[ChartBridge] Candles: \(sortedBars.count) bars")
            print("[ChartBridge] First: \(first.ts) O:\(first.open) H:\(first.high) L:\(first.low) C:\(first.close)")
            print("[ChartBridge] Last: \(last.ts) O:\(last.open) H:\(last.high) L:\(last.low) C:\(last.close)")
        }
        
        // Debug: Check for duplicate timestamps
        let timestamps = candleData.map { $0.time }
        let uniqueTimestamps = Set(timestamps)
        if timestamps.count != uniqueTimestamps.count {
            print("[ChartBridge] ⚠️ WARNING: Found \(timestamps.count - uniqueTimestamps.count) duplicate timestamps!")
        }
        
        send(.setCandles(data: candleData))
    }

    /// Set line indicator data
    func setIndicator(id: String, name: String, data: [IndicatorDataPoint], color: String) {
        let points = data.compactMap { point -> LightweightDataPoint? in
            guard let value = point.value else { return nil }
            return LightweightDataPoint(
                time: Int(point.date.timeIntervalSince1970 * 1000),
                value: value
            )
        }

        let options = LineOptions(color: color, lineWidth: 2, name: name)
        send(.setLine(id: id, data: points, options: options))
    }

    /// Set ML forecast overlay
    func setForecast(from series: ForecastSeries, direction: String) {
        let color: String
        switch direction.lowercased() {
        case "bullish": color = "#4de680"
        case "bearish": color = "#ff5959"
        default: color = "#ffbf00"
        }

        let midData = series.points.map { point in
            LightweightDataPoint(time: point.ts, value: point.value)
        }

        let upperData = series.points.map { point in
            LightweightDataPoint(time: point.ts, value: point.upper)
        }

        let lowerData = series.points.map { point in
            LightweightDataPoint(time: point.ts, value: point.lower)
        }

        let options = ForecastOptions(color: color)
        send(.setForecast(midData: midData, upperData: upperData, lowerData: lowerData, options: options))
    }

    /// Add buy/sell signal markers with AI factor positioned on SuperTrend line
    func setSignals(_ signals: [SuperTrendSignal], on seriesId: String = "candles") {
        let markers = signals.map { signal in
            let factorText = String(format: " %.1fx", signal.factor)
            let labelText = (signal.type == .buy ? "BUY" : "SELL") + factorText
            
            // BUY signals: green line is BELOW price (support), so label goes below
            // SELL signals: red line is ABOVE price (resistance), so label goes above
            return ChartMarker(
                time: Int(signal.date.timeIntervalSince1970 * 1000),
                type: signal.type == .buy ? "buy" : "sell",
                text: labelText,
                color: signal.type == .buy ? "#26a69a" : "#ef5350",
                position: signal.type == .buy ? "belowBar" : "aboveBar",  // BUY below, SELL above
                shape: signal.type == .buy ? "arrowUp" : "arrowDown",
                size: 2
            )
        }
        send(.setMarkers(seriesId: seriesId, markers: markers))
    }

    /// Add support/resistance price lines
    func setSRLevels(support: Double?, resistance: Double?) {
        if let support = support {
            let options = PriceLineOptions(color: "#4de680", lineStyle: 2, title: "S")
            send(.addPriceLine(seriesId: "candles", price: support, options: options))
        }

        if let resistance = resistance {
            let options = PriceLineOptions(color: "#ff5959", lineStyle: 2, title: "R")
            send(.addPriceLine(seriesId: "candles", price: resistance, options: options))
        }
    }

    // MARK: - Oscillator Panel Methods

    /// Set RSI indicator data
    func setRSI(data: [IndicatorDataPoint]) {
        let points = data.compactMap { point -> LightweightDataPoint? in
            guard let value = point.value else { return nil }
            return LightweightDataPoint(
                time: Int(point.date.timeIntervalSince1970),
                value: value
            )
        }
        send(.setRSI(data: points))
    }

    /// Set MACD indicator data
    func setMACD(line: [IndicatorDataPoint], signal: [IndicatorDataPoint], histogram: [IndicatorDataPoint]) {
        let linePoints = line.compactMap { point -> LightweightDataPoint? in
            guard let value = point.value else { return nil }
            return LightweightDataPoint(time: Int(point.date.timeIntervalSince1970 * 1000), value: value)
        }
        let signalPoints = signal.compactMap { point -> LightweightDataPoint? in
            guard let value = point.value else { return nil }
            return LightweightDataPoint(time: Int(point.date.timeIntervalSince1970 * 1000), value: value)
        }
        let histPoints = histogram.compactMap { point -> LightweightDataPoint? in
            guard let value = point.value else { return nil }
            return LightweightDataPoint(time: Int(point.date.timeIntervalSince1970 * 1000), value: value)
        }
        send(.setMACD(line: linePoints, signal: signalPoints, histogram: histPoints))
    }

    /// Set Stochastic indicator data
    func setStochastic(k: [IndicatorDataPoint], d: [IndicatorDataPoint]) {
        let kPoints = k.compactMap { point -> LightweightDataPoint? in
            guard let value = point.value else { return nil }
            return LightweightDataPoint(time: Int(point.date.timeIntervalSince1970 * 1000), value: value)
        }
        let dPoints = d.compactMap { point -> LightweightDataPoint? in
            guard let value = point.value else { return nil }
            return LightweightDataPoint(time: Int(point.date.timeIntervalSince1970 * 1000), value: value)
        }
        send(.setStochastic(kData: kPoints, dData: dPoints))
    }

    /// Set KDJ indicator data
    func setKDJ(k: [IndicatorDataPoint], d: [IndicatorDataPoint], j: [IndicatorDataPoint]) {
        let kPoints = k.compactMap { point -> LightweightDataPoint? in
            guard let value = point.value else { return nil }
            return LightweightDataPoint(time: Int(point.date.timeIntervalSince1970 * 1000), value: value)
        }
        let dPoints = d.compactMap { point -> LightweightDataPoint? in
            guard let value = point.value else { return nil }
            return LightweightDataPoint(time: Int(point.date.timeIntervalSince1970 * 1000), value: value)
        }
        let jPoints = j.compactMap { point -> LightweightDataPoint? in
            guard let value = point.value else { return nil }
            return LightweightDataPoint(time: Int(point.date.timeIntervalSince1970 * 1000), value: value)
        }
        send(.setKDJ(kData: kPoints, dData: dPoints, jData: jPoints))
    }

    /// Set ADX indicator data
    func setADX(adx: [IndicatorDataPoint], plusDI: [IndicatorDataPoint], minusDI: [IndicatorDataPoint]) {
        let adxPoints = adx.compactMap { point -> LightweightDataPoint? in
            guard let value = point.value else { return nil }
            return LightweightDataPoint(time: Int(point.date.timeIntervalSince1970 * 1000), value: value)
        }
        let plusPoints = plusDI.compactMap { point -> LightweightDataPoint? in
            guard let value = point.value else { return nil }
            return LightweightDataPoint(time: Int(point.date.timeIntervalSince1970 * 1000), value: value)
        }
        let minusPoints = minusDI.compactMap { point -> LightweightDataPoint? in
            guard let value = point.value else { return nil }
            return LightweightDataPoint(time: Int(point.date.timeIntervalSince1970 * 1000), value: value)
        }
        send(.setADX(adxData: adxPoints, plusDI: plusPoints, minusDI: minusPoints))
    }

    /// Set ATR indicator data
    func setATR(data: [IndicatorDataPoint]) {
        let points = data.compactMap { point -> LightweightDataPoint? in
            guard let value = point.value else { return nil }
            return LightweightDataPoint(time: Int(point.date.timeIntervalSince1970 * 1000), value: value)
        }
        send(.setATR(data: points))
    }

    /// Hide an oscillator panel
    func hidePanel(_ panel: String) {
        send(.hidePanel(panel: panel))
    }

    /// Set Volume data with color based on price direction
    func setVolume(bars: [OHLCBar]) {
        let volumeData = bars.enumerated().map { index, bar -> VolumeDataPoint in
            // Determine direction by comparing close to open
            let direction = bar.close >= bar.open ? "up" : "down"
            return VolumeDataPoint(
                time: Int(bar.ts.timeIntervalSince1970 * 1000),
                value: bar.volume,
                direction: direction,
                color: nil  // Let JS apply default colors
            )
        }
        send(.setVolume(data: volumeData))
    }

    /// Set intraday overlay (highlighted bars for today's data)
    func setIntradayOverlay(from bars: [OHLCBar]) {
        guard !bars.isEmpty else { return }
        
        let candles = bars.map { bar in
            LightweightCandle(
                time: Int(bar.ts.timeIntervalSince1970 * 1000),
                open: bar.open,
                high: bar.high,
                low: bar.low,
                close: bar.close
            )
        }
        
        // Use a special series for intraday with different styling
        send(.setLine(id: "intraday_overlay", data: candles.map { candle in
            LightweightDataPoint(time: candle.time, value: candle.close)
        }, options: LineOptions(
            color: "#4a90e2",
            lineWidth: 2,
            lineStyle: 0,
            name: "Intraday"
        )))
    }
    
    /// Set forecast layer (dashed line with confidence bands)
    func setForecastLayer(from bars: [OHLCBar]) {
        guard !bars.isEmpty else { return }
        
        let midPoints = bars.map { bar in
            LightweightDataPoint(time: Int(bar.ts.timeIntervalSince1970 * 1000), value: bar.close)
        }
        
        let upperPoints = bars.compactMap { bar -> LightweightDataPoint? in
            guard let upper = bar.upperBand else { return nil }
            return LightweightDataPoint(time: Int(bar.ts.timeIntervalSince1970 * 1000), value: upper)
        }
        
        let lowerPoints = bars.compactMap { bar -> LightweightDataPoint? in
            guard let lower = bar.lowerBand else { return nil }
            return LightweightDataPoint(time: Int(bar.ts.timeIntervalSince1970 * 1000), value: lower)
        }
        
        send(.setForecast(
            midData: midPoints,
            upperData: upperPoints,
            lowerData: lowerPoints,
            options: ForecastOptions(
                color: "#9c27b0",
                bandColor: "rgba(156, 39, 176, 0.2)"
            )
        ))
    }
    
    /// Set SuperTrend with trend-based coloring and strength data
    func setSuperTrend(data: [IndicatorDataPoint], trend: [IndicatorDataPoint], strength: [IndicatorDataPoint] = []) {
        // IMPORTANT: Keep arrays aligned by index - only include points where SuperTrend value is valid
        var stPoints: [LightweightDataPoint] = []
        var trendPoints: [LightweightDataPoint] = []
        var strengthPoints: [LightweightDataPoint] = []
        
        let count = min(data.count, trend.count)
        for i in 0..<count {
            // Only include if SuperTrend value is valid (not nil)
            guard let stValue = data[i].value else { continue }
            
            // Use trend value (should always be 0 or 1)
            let trendValue = trend[i].value ?? 0
            
            // Get strength value if available
            let strengthValue = i < strength.count ? (strength[i].value ?? 0) : 0
            
            stPoints.append(LightweightDataPoint(
                time: Int(data[i].date.timeIntervalSince1970 * 1000),
                value: stValue
            ))
            trendPoints.append(LightweightDataPoint(
                time: Int(trend[i].date.timeIntervalSince1970 * 1000),
                value: trendValue
            ))
            strengthPoints.append(LightweightDataPoint(
                time: Int(data[i].date.timeIntervalSince1970 * 1000),
                value: strengthValue
            ))
        }
        
        print("[ChartBridge] SuperTrend: \(stPoints.count) aligned points")
        send(.setSuperTrend(data: stPoints, trendData: trendPoints, strengthData: strengthPoints))
    }

    // MARK: - Private Helpers

    private func encodeCommand(_ command: ChartCommand) -> String? {
        do {
            let data = try encoder.encode(command)
            return String(data: data, encoding: .utf8)
        } catch {
            print("[ChartBridge] Encoding error: \(error)")
            return nil
        }
    }

    private func executeJS(_ js: String) {
        webView?.evaluateJavaScript(js) { result, error in
            if let error = error {
                print("[ChartBridge] JS error: \(error.localizedDescription)")
            }
        }
    }

    private func flushPendingCommands() {
        for js in pendingCommands {
            executeJS(js)
        }
        pendingCommands.removeAll()
        print("[ChartBridge] Flushed \(pendingCommands.count) pending commands")
    }
}

// MARK: - WKScriptMessageHandler

extension ChartBridge: WKScriptMessageHandler {
    nonisolated func userContentController(
        _ userContentController: WKUserContentController,
        didReceive message: WKScriptMessage
    ) {
        // Capture the body on the main actor since WKScriptMessage.body is MainActor-isolated
        Task { @MainActor in
            guard let dict = message.body as? [String: Any],
                  let type = dict["type"] as? String else {
                return
            }
            handleMessage(type: type, data: dict)
        }
    }

    @MainActor
    private func handleMessage(type: String, data: [String: Any]) {
        switch type {
        case "ready":
            isReady = true
            flushPendingCommands()
            eventPublisher.send(.ready)
            print("[ChartBridge] Chart ready")

        case "crosshair":
            if let time = data["time"] as? Int,
               let price = data["price"] as? Double {
                var ohlc: ChartEvent.OHLC?
                if let open = data["open"] as? Double,
                   let high = data["high"] as? Double,
                   let low = data["low"] as? Double,
                   let close = data["close"] as? Double {
                    ohlc = ChartEvent.OHLC(open: open, high: high, low: low, close: close)
                    lastCrosshairData = ohlc
                }
                eventPublisher.send(.crosshairMove(time: time, price: price, ohlc: ohlc))
            }

        case "visibleRange":
            if let from = data["from"] as? Int,
               let to = data["to"] as? Int {
                visibleRange = (from, to)
                eventPublisher.send(.visibleRangeChange(from: from, to: to))
            }

        default:
            eventPublisher.send(.unknown(type: type, data: data))
        }
    }
}
