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

    // Custom encoding to match JS API
    private enum CodingKeys: String, CodingKey {
        case type, options, data, candle, id, midData, upperData, lowerData
        case seriesId, markers, price, from, to
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

    /// Set candlestick data from OHLCBar array
    func setCandles(from bars: [OHLCBar]) {
        let candles = bars.map { bar in
            LightweightCandle(
                time: Int(bar.ts.timeIntervalSince1970),
                open: bar.open,
                high: bar.high,
                low: bar.low,
                close: bar.close
            )
        }
        send(.setCandles(data: candles))
    }

    /// Set line indicator data
    func setIndicator(id: String, name: String, data: [IndicatorDataPoint], color: String) {
        let points = data.compactMap { point -> LightweightDataPoint? in
            guard let value = point.value else { return nil }
            return LightweightDataPoint(
                time: Int(point.date.timeIntervalSince1970),
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

    /// Add buy/sell signal markers
    func setSignals(_ signals: [SuperTrendSignal], on seriesId: String = "candles") {
        let markers = signals.map { signal in
            ChartMarker(
                time: Int(signal.date.timeIntervalSince1970),
                type: signal.type == .buy ? "buy" : "sell",
                text: signal.type == .buy ? "BUY" : "SELL"
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
        guard let dict = message.body as? [String: Any],
              let type = dict["type"] as? String else {
            return
        }

        Task { @MainActor in
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
