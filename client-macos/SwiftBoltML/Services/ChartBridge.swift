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
    case setForecastCandles(data: [LightweightCandle], direction: String?)
    case setForecast(midData: [LightweightDataPoint], upperData: [LightweightDataPoint], lowerData: [LightweightDataPoint], options: ForecastOptions?)
    case setMarkers(seriesId: String, markers: [ChartMarker])
    case addPriceLine(seriesId: String, price: Double, options: PriceLineOptions?)
    case removeSeries(id: String)
    case clearIndicators
    case clearAll
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
    case setPolynomialSR(resistance: [LightweightDataPoint], support: [LightweightDataPoint])
    case setPivotLevels(levels: [SRLevel])
    case setLogisticSR(levels: [SRLevel])
    case setIndicatorConfig(config: WebIndicatorConfig)
    case hidePanel(panel: String)
    case removeVolumeProfile
    case removePriceLines(category: String)
    case setTechnicalIndicatorsOverlay(indicators: [TechnicalIndicatorOverlay])

    // Custom encoding to match JS API
    private enum CodingKeys: String, CodingKey {
        case type, options, data, candle, id, midData, upperData, lowerData
        case direction
        case seriesId, markers, price, from, to
        case line, signal, histogram, kData, dData, jData, adxData, plusDI, minusDI, panel
        case trendData, strengthData, resistance, support, levels, category
        case config, indicators
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
        case .setForecastCandles(let data, let direction):
            try container.encode("setForecastCandles", forKey: .type)
            try container.encode(data, forKey: .data)
            try container.encodeIfPresent(direction, forKey: .direction)
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
        case .clearAll:
            try container.encode("clearAll", forKey: .type)
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
        case .setPolynomialSR(let resistance, let support):
            try container.encode("setPolynomialSR", forKey: .type)
            try container.encode(resistance, forKey: .resistance)
            try container.encode(support, forKey: .support)
        case .setPivotLevels(let levels):
            try container.encode("setPivotLevels", forKey: .type)
            try container.encode(levels, forKey: .levels)
        case .setLogisticSR(let levels):
            try container.encode("setLogisticSR", forKey: .type)
            try container.encode(levels, forKey: .levels)
        case .setIndicatorConfig(let config):
            try container.encode("setIndicatorConfig", forKey: .type)
            try container.encode(config, forKey: .config)
        case .hidePanel(let panel):
            try container.encode("hidePanel", forKey: .type)
            try container.encode(panel, forKey: .panel)
        case .removeVolumeProfile:
            try container.encode("removeVolumeProfile", forKey: .type)
        case .removePriceLines(let category):
            try container.encode("removePriceLines", forKey: .type)
            try container.encode(category, forKey: .category)
        case .setTechnicalIndicatorsOverlay(let indicators):
            try container.encode("setTechnicalIndicatorsOverlay", forKey: .type)
            try container.encode(indicators, forKey: .indicators)
        }
    }
}

/// S&R Level for WebChart
struct SRLevel: Encodable {
    let price: Double
    let color: String
    let title: String
    let lineWidth: Int
    let lineStyle: Int // 0=Solid, 1=Dotted, 2=Dashed
}

struct WebIndicatorConfig: Encodable {
    let showSuperTrend: Bool
    let useSuperTrendAI: Bool
    let showRSI: Bool
    let showMACD: Bool
    let showKDJ: Bool
    let showPivotLevels: Bool
    let showSignalMarkers: Bool
    let showConfidenceBadges: Bool
    let showAdaptiveMA: Bool
    let superTrendPeriod: Int
    let superTrendMultiplier: Double

    // SuperTrend AI (LuxAlgo-style)
    let superTrendAIFactorMin: Double
    let superTrendAIFactorMax: Double
    let superTrendAIFactorStep: Double
    let superTrendAIPerfAlpha: Double
    let superTrendAIFromCluster: String
    let superTrendAIMaxIterations: Int
    let superTrendAIHistoricalBars: Int
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
    var category: String?
}

/// Technical indicator overlay for chart display
struct TechnicalIndicatorOverlay: Encodable {
    let name: String
    let value: Double?
    let category: String
    let color: String?
    let position: String?  // "top", "bottom", "overlay"
    let format: String?    // "price", "percent", "ratio"
}

private extension String {
    func asRGBA(alpha: Double) -> String {
        let hex = trimmingCharacters(in: CharacterSet(charactersIn: "#"))
        guard hex.count == 6, let intVal = Int(hex, radix: 16) else {
            return self
        }
        let r = (intVal >> 16) & 0xff
        let g = (intVal >> 8) & 0xff
        let b = intVal & 0xff
        let clampedAlpha = max(0.0, min(1.0, alpha))
        return "rgba(\(r),\(g),\(b),\(String(format: "%.2f", clampedAlpha)))"
    }
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
    // MARK: - Debug Configuration

    /// Debug flags to help isolate chart rendering issues
    struct DebugConfig {
        /// When true, skips sending overlay data (intraday, forecast layers)
        var disableOverlays: Bool = false
        /// When true, skips sending forecast candle data
        var disableForecasts: Bool = false
        /// When true, prevents Heikin-Ashi toggle commands
        var disableHeikinAshi: Bool = false
        /// When true, filters out bars with >X% price jumps (outliers)
        var filterOutliers: Bool = false
        /// Threshold for outlier filtering (default 50% = 0.5)
        var outlierThreshold: Double = 0.5
        /// When true, enables verbose logging of all data sent to chart
        var verboseLogging: Bool = false
    }

    /// Access this to enable/disable debug features at runtime
    var debug = DebugConfig()

    // MARK: - Published State

    @Published private(set) var isReady = false
    @Published private(set) var lastCrosshairData: ChartEvent.OHLC?
    @Published private(set) var visibleRange: (from: Int, to: Int)?
    @Published private(set) var lastJSError: String?

    // MARK: - Private State

    private weak var webView: WKWebView?
    private var pendingCommands: [String] = []
    private var commandQueue: [String] = []
    private var isExecutingJS: Bool = false
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
            enqueueJS(js)
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
        var sortedBars = bars.sorted { $0.ts < $1.ts }

        let times = sortedBars.map { Int($0.ts.timeIntervalSince1970) }

        // ═══════════════════════════════════════════════════════════════════════
        // DIAGNOSTIC 1: Year-span sanity check (detect ms vs s or bad timezone)
        // ═══════════════════════════════════════════════════════════════════════
        if !sortedBars.isEmpty {
            let calendar = Calendar.current
            let years = sortedBars.map { calendar.component(.year, from: $0.ts) }
            if let minYear = years.min(), let maxYear = years.max() {
                if maxYear - minYear > 5 {
                    print("[ChartBridge] ⚠️ YEAR SPAN ALERT: Data spans \(minYear)–\(maxYear) (\(maxYear - minYear) years)")
                    print("[ChartBridge]    This likely indicates ms vs s timestamp confusion or timezone issues!")

                    // Find where the year changes dramatically
                    for i in 1..<sortedBars.count {
                        let prevYear = calendar.component(.year, from: sortedBars[i-1].ts)
                        let curYear = calendar.component(.year, from: sortedBars[i].ts)
                        if abs(curYear - prevYear) > 2 {
                            print("[ChartBridge]    Year jump at [\(i)]: \(sortedBars[i-1].ts) (\(prevYear)) → \(sortedBars[i].ts) (\(curYear))")
                        }
                    }
                } else if debug.verboseLogging {
                    print("[ChartBridge] ✅ Year span OK: \(minYear)–\(maxYear)")
                }
            }
        }

        // ═══════════════════════════════════════════════════════════════════════
        // DIAGNOSTIC 2: Non-monotonic timestamp check
        // ═══════════════════════════════════════════════════════════════════════
        if times.count > 1 {
            var nonMonotonicIndices: [(index: Int, from: Date, to: Date)] = []
            for i in 1..<times.count where times[i] <= times[i-1] {
                nonMonotonicIndices.append((i, sortedBars[i-1].ts, sortedBars[i].ts))
            }
            if !nonMonotonicIndices.isEmpty {
                print("[ChartBridge] ⚠️ NON-MONOTONIC: \(nonMonotonicIndices.count) timestamp(s) not strictly increasing:")
                for item in nonMonotonicIndices.prefix(5) {
                    print("[ChartBridge]    [\(item.index)]: \(item.from) → \(item.to)")
                }
            } else if debug.verboseLogging {
                print("[ChartBridge] ✅ All timestamps strictly increasing")
            }
        }

        // ═══════════════════════════════════════════════════════════════════════
        // DIAGNOSTIC 3: Large price jump detection (>25% between consecutive bars)
        // ═══════════════════════════════════════════════════════════════════════
        if sortedBars.count > 5 {
            var suspiciousJumps: [(index: Int, date: Date, prevClose: Double, curClose: Double, pctChange: Double)] = []
            for i in 1..<sortedBars.count {
                let prevClose = sortedBars[i-1].close
                let curClose = sortedBars[i].close
                guard prevClose > 0.0001 else { continue } // Skip near-zero prices
                let pctChange = abs((curClose - prevClose) / prevClose)
                if pctChange > 0.25 { // >25% jump
                    suspiciousJumps.append((i, sortedBars[i].ts, prevClose, curClose, pctChange))
                }
            }
            if !suspiciousJumps.isEmpty {
                print("[ChartBridge] ⚠️ LARGE PRICE JUMPS: \(suspiciousJumps.count) bars with >25% change:")
                for jump in suspiciousJumps.prefix(10) {
                    let pctStr = String(format: "%.1f%%", jump.pctChange * 100)
                    print("[ChartBridge]    [\(jump.index)] \(jump.date): \(jump.prevClose) → \(jump.curClose) (\(pctStr))")
                }

                // Check if jumps are OHLC consistency issues (high < low, etc.)
                var malformedBars: [(index: Int, bar: OHLCBar)] = []
                for jump in suspiciousJumps {
                    let bar = sortedBars[jump.index]
                    let maxOC = max(bar.open, bar.close)
                    let minOC = min(bar.open, bar.close)
                    if bar.high < maxOC || bar.low > minOC || bar.high < bar.low {
                        malformedBars.append((jump.index, bar))
                    }
                }
                if !malformedBars.isEmpty {
                    print("[ChartBridge] ⚠️ MALFORMED OHLC: \(malformedBars.count) bars have invalid high/low:")
                    for (idx, bar) in malformedBars.prefix(5) {
                        print("[ChartBridge]    [\(idx)] O:\(bar.open) H:\(bar.high) L:\(bar.low) C:\(bar.close)")
                    }
                }
            } else {
                print("[ChartBridge] ✅ No large price jumps (>25%) detected")
            }
        }

        // ═══════════════════════════════════════════════════════════════════════
        // DIAGNOSTIC 4: Time gap analysis
        // ═══════════════════════════════════════════════════════════════════════
        if times.count > 1 {
            var intervals: [Int] = []
            intervals.reserveCapacity(times.count - 1)
            for i in 1..<times.count {
                intervals.append(times[i] - times[i - 1])
            }
            let sortedIntervals = intervals.sorted()
            let medianInterval = sortedIntervals[sortedIntervals.count / 2]
            // Consider a gap suspicious if it's > 10x median interval, with a floor of 1 day
            let threshold = max(medianInterval * 10, 24 * 60 * 60)
            var largeGaps: [(index: Int, seconds: Int)] = []
            for i in 0..<intervals.count {
                if intervals[i] > threshold {
                    largeGaps.append((index: i, seconds: intervals[i]))
                }
            }
            if !largeGaps.isEmpty {
                print("[ChartBridge] ⚠️ Detected \(largeGaps.count) large time gaps (> \(threshold)s). Top gaps:")
                for gap in largeGaps.prefix(3) {
                    let fromDate = sortedBars[gap.index].ts
                    let toDate = sortedBars[gap.index + 1].ts
                    let days = Double(gap.seconds) / 86400.0
                    print("[ChartBridge]   Gap \(String(format: "%.1f", days)) days between \(fromDate) and \(toDate)")
                }
            } else if debug.verboseLogging {
                print("[ChartBridge] ✅ No large time gaps detected (median interval: \(medianInterval)s)")
            }
        }

        // ═══════════════════════════════════════════════════════════════════════
        // OPTIONAL: Filter outliers if debug.filterOutliers is enabled
        // ═══════════════════════════════════════════════════════════════════════
        if debug.filterOutliers && sortedBars.count > 2 {
            var filteredBars: [OHLCBar] = [sortedBars[0]]
            var droppedCount = 0
            for i in 1..<sortedBars.count {
                let prevClose = filteredBars.last?.close ?? sortedBars[i-1].close
                let curClose = sortedBars[i].close
                guard prevClose > 0.0001 else {
                    filteredBars.append(sortedBars[i])
                    continue
                }
                let pctChange = abs((curClose - prevClose) / prevClose)
                if pctChange > debug.outlierThreshold {
                    droppedCount += 1
                    print("[ChartBridge] 🚫 FILTERED outlier bar at \(sortedBars[i].ts): \(prevClose) → \(curClose)")
                } else {
                    filteredBars.append(sortedBars[i])
                }
            }
            if droppedCount > 0 {
                print("[ChartBridge] 🚫 Filtered \(droppedCount) outlier bars (threshold: \(debug.outlierThreshold * 100)%)")
                sortedBars = filteredBars
            }
        }

        let candleData = sortedBars.map { bar in
            LightweightCandle(
                time: Int(bar.ts.timeIntervalSince1970),  // Unix timestamp in seconds
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

            // Log sample bars throughout dataset to check for gaps/jumps
            if debug.verboseLogging {
                let sampleIndices = [0, sortedBars.count/4, sortedBars.count/2, sortedBars.count*3/4, sortedBars.count-1]
                print("[ChartBridge] Sample bars:")
                for idx in sampleIndices where idx < sortedBars.count {
                    let bar = sortedBars[idx]
                    print("  [\(idx)]: \(bar.ts) C:\(bar.close)")
                }
            }
        }

        // Debug: Check for duplicate timestamps
        let timestamps = candleData.map { $0.time }
        let uniqueTimestamps = Set(timestamps)
        if timestamps.count != uniqueTimestamps.count {
            print("[ChartBridge] ⚠️ WARNING: Found \(timestamps.count - uniqueTimestamps.count) duplicate timestamps!")

            // Find and log the duplicates
            var seenTimes = Set<Int>()
            var duplicates: [(Int, Date)] = []
            for (idx, bar) in sortedBars.enumerated() {
                let time = Int(bar.ts.timeIntervalSince1970)
                if seenTimes.contains(time) {
                    duplicates.append((idx, bar.ts))
                }
                seenTimes.insert(time)
            }
            print("[ChartBridge] Duplicate timestamps: \(duplicates.map { "[\($0.0)]: \($0.1)" }.joined(separator: ", "))")
        } else if debug.verboseLogging {
            print("[ChartBridge] ✅ No duplicate timestamps detected")
        }

        send(.setCandles(data: candleData))
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
        let baseColor: String
        switch direction.lowercased() {
        case "bullish": baseColor = "#4de680"
        case "bearish": baseColor = "#ff5959"
        default: baseColor = "#ffbf00"
        }

        let midData = series.points.map { point in
            LightweightDataPoint(time: point.ts, value: point.value)
        }

        let upperData = series.points.map { point in
            let clampedUpper = max(point.upper, point.lower, point.value)
            return LightweightDataPoint(time: point.ts, value: clampedUpper)
        }

        let lowerData = series.points.map { point in
            let clampedLower = min(point.upper, point.lower, point.value)
            return LightweightDataPoint(time: point.ts, value: clampedLower)
        }

        let options = ForecastOptions(color: baseColor, bandColor: baseColor.asRGBA(alpha: 0.2))
        send(.setForecast(midData: midData, upperData: upperData, lowerData: lowerData, options: options))
    }

    /// Add buy/sell signal markers with AI factor positioned on SuperTrend line
    func setSignals(_ signals: [SuperTrendSignal], on seriesId: String = "candles") {
        let markers = signals.map { signal in
            let factorText = String(format: " %.1fx", signal.factor)
            let labelText = (signal.type == .buy ? "BUY" : "SELL") + factorText

            return ChartMarker(
                time: Int(signal.date.timeIntervalSince1970),
                type: signal.type == .buy ? "buy" : "sell",
                text: labelText,
                color: signal.type == .buy ? "#26a69a" : "#ef5350",
                position: signal.type == .buy ? "belowBar" : "aboveBar",
                shape: signal.type == .buy ? "arrowUp" : "arrowDown",
                size: 2
            )
        }
        setMarkers(markers, seriesId: seriesId)
    }

    /// Set arbitrary markers on a series
    func setMarkers(_ markers: [ChartMarker], seriesId: String = "candles") {
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
            return LightweightDataPoint(time: Int(point.date.timeIntervalSince1970), value: value)
        }
        let signalPoints = signal.compactMap { point -> LightweightDataPoint? in
            guard let value = point.value else { return nil }
            return LightweightDataPoint(time: Int(point.date.timeIntervalSince1970), value: value)
        }
        let histPoints = histogram.compactMap { point -> LightweightDataPoint? in
            guard let value = point.value else { return nil }
            return LightweightDataPoint(time: Int(point.date.timeIntervalSince1970), value: value)
        }
        send(.setMACD(line: linePoints, signal: signalPoints, histogram: histPoints))
    }

    /// Set Stochastic indicator data
    func setStochastic(k: [IndicatorDataPoint], d: [IndicatorDataPoint]) {
        let kPoints = k.compactMap { point -> LightweightDataPoint? in
            guard let value = point.value else { return nil }
            return LightweightDataPoint(time: Int(point.date.timeIntervalSince1970), value: value)
        }
        let dPoints = d.compactMap { point -> LightweightDataPoint? in
            guard let value = point.value else { return nil }
            return LightweightDataPoint(time: Int(point.date.timeIntervalSince1970), value: value)
        }
        send(.setStochastic(kData: kPoints, dData: dPoints))
    }

    /// Set KDJ indicator data
    func setKDJ(k: [IndicatorDataPoint], d: [IndicatorDataPoint], j: [IndicatorDataPoint]) {
        let kPoints = k.compactMap { point -> LightweightDataPoint? in
            guard let value = point.value else { return nil }
            return LightweightDataPoint(time: Int(point.date.timeIntervalSince1970), value: value)
        }
        let dPoints = d.compactMap { point -> LightweightDataPoint? in
            guard let value = point.value else { return nil }
            return LightweightDataPoint(time: Int(point.date.timeIntervalSince1970), value: value)
        }
        let jPoints = j.compactMap { point -> LightweightDataPoint? in
            guard let value = point.value else { return nil }
            return LightweightDataPoint(time: Int(point.date.timeIntervalSince1970), value: value)
        }
        send(.setKDJ(kData: kPoints, dData: dPoints, jData: jPoints))
    }

    /// Set ADX indicator data
    func setADX(adx: [IndicatorDataPoint], plusDI: [IndicatorDataPoint], minusDI: [IndicatorDataPoint]) {
        let adxPoints = adx.compactMap { point -> LightweightDataPoint? in
            guard let value = point.value else { return nil }
            return LightweightDataPoint(time: Int(point.date.timeIntervalSince1970), value: value)
        }
        let plusPoints = plusDI.compactMap { point -> LightweightDataPoint? in
            guard let value = point.value else { return nil }
            return LightweightDataPoint(time: Int(point.date.timeIntervalSince1970), value: value)
        }
        let minusPoints = minusDI.compactMap { point -> LightweightDataPoint? in
            guard let value = point.value else { return nil }
            return LightweightDataPoint(time: Int(point.date.timeIntervalSince1970), value: value)
        }
        send(.setADX(adxData: adxPoints, plusDI: plusPoints, minusDI: minusPoints))
    }

    /// Set ATR indicator data
    func setATR(data: [IndicatorDataPoint]) {
        let points = data.compactMap { point -> LightweightDataPoint? in
            guard let value = point.value else { return nil }
            return LightweightDataPoint(time: Int(point.date.timeIntervalSince1970), value: value)
        }
        send(.setATR(data: points))
    }

    /// Hide an oscillator panel
    func hidePanel(_ panel: String) {
        send(.hidePanel(panel: panel))
    }

    /// Set Volume data with color based on price direction
    func setVolume(bars: [OHLCBar]) {
        let sortedBars = bars.sorted { $0.ts < $1.ts }
        let volumeData = sortedBars.map { bar -> VolumeDataPoint in
            let direction = bar.close >= bar.open ? "up" : "down"
            return VolumeDataPoint(
                time: Int(bar.ts.timeIntervalSince1970),
                value: bar.volume,
                direction: direction,
                color: nil
            )
        }
        send(.setVolume(data: volumeData))
    }

    /// Set intraday overlay (highlighted bars for today's data)
    func setIntradayOverlay(from bars: [OHLCBar]) {
        if debug.disableOverlays {
            print("[ChartBridge] 🚫 Skipping intraday overlay (debug.disableOverlays=true)")
            return
        }

        let sortedBars = bars.sorted { $0.ts < $1.ts }
        guard !sortedBars.isEmpty else { return }

        let candles = sortedBars.map { bar in
            LightweightCandle(
                time: Int(bar.ts.timeIntervalSince1970),
                open: bar.open,
                high: bar.high,
                low: bar.low,
                close: bar.close
            )
        }

        send(.setLine(id: "intraday_overlay", data: candles.map { candle in
            LightweightDataPoint(time: candle.time, value: candle.close)
        }, options: LineOptions(
            color: "#4a90e2",
            lineWidth: 2,
            lineStyle: 0,
            name: "Intraday"
        )))
    }
    
    /// Set forecast as an overlay candlestick series (for intraday)
    func setForecastCandles(from bars: [OHLCBar]) {
        let sortedBars = bars.sorted { $0.ts < $1.ts }
        guard !sortedBars.isEmpty else { return }
        
        let candles = sortedBars.map { bar in
            LightweightCandle(
                time: Int(bar.ts.timeIntervalSince1970),
                open: bar.open,
                high: bar.high,
                low: bar.low,
                close: bar.close
            )
        }
        
        let firstClose = sortedBars.first?.close ?? 0
        let lastClose = sortedBars.last?.close ?? 0
        let direction = lastClose >= firstClose ? "bullish" : "bearish"
        send(.setForecastCandles(data: candles, direction: direction))
    }
    
    /// Set forecast layer (dashed line with confidence bands)
    func setForecastLayer(from bars: [OHLCBar]) {
        guard !bars.isEmpty else { return }

        let midPoints = bars.map { bar in
            LightweightDataPoint(time: Int(bar.ts.timeIntervalSince1970), value: bar.close)
        }

        let upperPoints = bars.compactMap { bar -> LightweightDataPoint? in
            guard let upper = bar.upperBand else { return nil }
            return LightweightDataPoint(time: Int(bar.ts.timeIntervalSince1970), value: upper)
        }

        let lowerPoints = bars.compactMap { bar -> LightweightDataPoint? in
            guard let lower = bar.lowerBand else { return nil }
            return LightweightDataPoint(time: Int(bar.ts.timeIntervalSince1970), value: lower)
        }

        // Direction-aware color based on forecast slope
        let firstClose = bars.first?.close ?? 0
        let lastClose = bars.last?.close ?? 0
        let isUp = lastClose >= firstClose
        let color = isUp ? "#4de680" : "#ff5959"
        let bandColor = isUp ? "rgba(77, 230, 128, 0.2)" : "rgba(255, 89, 89, 0.2)"

        send(.setForecast(
            midData: midPoints,
            upperData: upperPoints,
            lowerData: lowerPoints,
            options: ForecastOptions(
                color: color,
                bandColor: bandColor
            )
        ))
    }

    /// Set simple forecast visualization: dots at target price + connecting line + horizontal price line
    func setSimpleForecast(from bars: [OHLCBar], currentPrice: Double?) {
        guard !bars.isEmpty else { return }

        let sortedBars = bars.sorted { $0.ts < $1.ts }
        let lastForecastPrice = sortedBars.last?.close ?? 0
        let currentPriceValue = currentPrice ?? sortedBars.first?.close ?? 0

        // Determine color based on target price vs current price
        let isAboveCurrentPrice = lastForecastPrice >= currentPriceValue
        let color = isAboveCurrentPrice ? "#4de680" : "#ff5959"  // Green if above, red if below

        // Create markers (dots) at each forecast point
        let markers = sortedBars.enumerated().map { (index, bar) -> ChartMarker in
            return ChartMarker(
                time: Int(bar.ts.timeIntervalSince1970),
                type: "circle",
                text: "",
                color: color,
                position: "inBar",
                shape: "circle",
                size: index == sortedBars.count - 1 ? 2 : 1  // Larger dot at final target
            )
        }
        setMarkers(markers, seriesId: "candles")

        // Create line connecting all forecast points
        let forecastLine = sortedBars.map { bar in
            LightweightDataPoint(time: Int(bar.ts.timeIntervalSince1970), value: bar.close)
        }

        send(.setLine(
            id: "forecast-line",
            data: forecastLine,
            options: LineOptions(
                color: color,
                lineWidth: 1,
                lineStyle: 2,  // Dashed line
                name: "Forecast"
            )
        ))

        // Create horizontal price line at the target price
        let options = PriceLineOptions(
            color: color,
            lineStyle: 0,  // Solid line
            title: String(format: "Target: %.2f", lastForecastPrice)
        )
        send(.addPriceLine(seriesId: "candles", price: lastForecastPrice, options: options))
    }
    
    /// Toggle Heikin-Ashi candlestick display
    func toggleHeikinAshi(enabled: Bool) {
        let command = """
        window.chartApi.toggleHeikinAshi(\(enabled));
        """
        executeJS(command)
        print("[ChartBridge] Heikin-Ashi toggled: \(enabled)")
    }

    func setIndicatorConfig(_ config: IndicatorConfig, timeframe: Timeframe) {
        let stParams = timeframe.superTrendParams
        let payload = WebIndicatorConfig(
            showSuperTrend: config.showSuperTrend,
            useSuperTrendAI: config.useSuperTrendAI,
            showRSI: config.showRSI,
            showMACD: config.showMACD,
            showKDJ: config.showKDJ,
            showPivotLevels: config.showPivotLevels,
            showSignalMarkers: config.showSignalMarkers,
            showConfidenceBadges: config.showConfidenceBadges,
            showAdaptiveMA: config.showAdaptiveMA,
            superTrendPeriod: stParams.period,
            superTrendMultiplier: stParams.multiplier,
            superTrendAIFactorMin: config.superTrendAIFactorMin,
            superTrendAIFactorMax: config.superTrendAIFactorMax,
            superTrendAIFactorStep: config.superTrendAIFactorStep,
            superTrendAIPerfAlpha: config.superTrendAIPerfAlpha,
            superTrendAIFromCluster: config.superTrendAIFromCluster.rawValue.capitalized,
            superTrendAIMaxIterations: config.superTrendAIMaxIterations,
            superTrendAIHistoricalBars: config.superTrendAIHistoricalBars
        )
        send(.setIndicatorConfig(config: payload))
    }
    
    /// Set volume profile data
    func setVolumeProfile(data: [[String: Any]]) {
        guard let jsonData = try? JSONSerialization.data(withJSONObject: data),
              let jsonString = String(data: jsonData, encoding: .utf8) else {
            print("[ChartBridge] Failed to encode volume profile data")
            return
        }
        
        let command = """
        window.chartApi.setVolumeProfile(\(jsonString));
        """
        executeJS(command)
        print("[ChartBridge] Volume profile set: \(data.count) levels")
    }
    
    /// Remove volume profile overlay
    func removeVolumeProfile() {
        send(.removeVolumeProfile)
        print("[ChartBridge] Volume profile removed")
    }
    
    /// Update live bar with animation
    func updateLiveBar(bar: OHLCBar, duration: Int = 500) {
        let barData: [String: Any] = [
            "time": Int(bar.ts.timeIntervalSince1970),
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close
        ]
        
        guard let jsonData = try? JSONSerialization.data(withJSONObject: barData),
              let jsonString = String(data: jsonData, encoding: .utf8) else {
            print("[ChartBridge] Failed to encode bar data")
            return
        }
        
        let command = """
        window.chartApi.updateLiveBar(\(jsonString), \(duration));
        """
        executeJS(command)
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
                time: Int(data[i].date.timeIntervalSince1970),
                value: stValue
            ))
            trendPoints.append(LightweightDataPoint(
                time: Int(trend[i].date.timeIntervalSince1970),
                value: trendValue
            ))
            strengthPoints.append(LightweightDataPoint(
                time: Int(data[i].date.timeIntervalSince1970),
                value: strengthValue
            ))
        }
        
        print("[ChartBridge] SuperTrend: \(stPoints.count) aligned points")
        send(.setSuperTrend(data: stPoints, trendData: trendPoints, strengthData: strengthPoints))
    }
    
    /// Set technical indicators overlay from API response
    func setTechnicalIndicatorsOverlay(from response: TechnicalIndicatorsResponse) {
        var overlays: [TechnicalIndicatorOverlay] = []
        
        // Helper to get category color
        func categoryColor(_ category: IndicatorCategory) -> String {
            switch category {
            case .momentum: return "#4de680"
            case .trend: return "#5b9bd5"
            case .volatility: return "#ff9800"
            case .volume: return "#9c27b0"
            case .price: return "#2196f3"
            case .other: return "#757575"
            }
        }
        
        // Helper to determine format
        func indicatorFormat(_ name: String) -> String {
            let lower = name.lowercased()
            if lower.contains("ratio") || lower.contains("rsi") || lower.contains("stochastic") {
                return "ratio"
            } else if lower.contains("percent") || lower.contains("pct") || lower.contains("change") {
                return "percent"
            } else {
                return "price"
            }
        }
        
        // Convert indicators to overlays
        for (name, value) in response.indicators {
            guard let value = value else { continue }
            
            // Determine category
            let category = IndicatorCategory.category(for: name) ?? .other
            
            // Create overlay
            let overlay = TechnicalIndicatorOverlay(
                name: name,
                value: value,
                category: category.rawValue,
                color: categoryColor(category),
                position: (category == .momentum || category == .volume) ? "bottom" : "overlay",
                format: indicatorFormat(name)
            )
            overlays.append(overlay)
        }
        
        if !overlays.isEmpty {
            send(.setTechnicalIndicatorsOverlay(indicators: overlays))
            print("[ChartBridge] Technical indicators overlay: \(overlays.count) indicators")
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
        webView?.evaluateJavaScript(js) { [weak self] _, error in
            guard let self else { return }
            if let error = error {
                self.lastJSError = error.localizedDescription
                print("[ChartBridge] JS error: \(error.localizedDescription)")
            }
            self.isExecutingJS = false
            self.drainJSQueue()
        }
    }

    private func enqueueJS(_ js: String) {
        commandQueue.append(js)
        drainJSQueue()
    }

    private func drainJSQueue() {
        guard isReady else { return }
        guard !isExecutingJS else { return }
        guard let _ = webView else { return }
        guard !commandQueue.isEmpty else { return }

        isExecutingJS = true
        let js = commandQueue.removeFirst()
        executeJS(js)
    }

    private func flushPendingCommands() {
        let count = pendingCommands.count
        for js in pendingCommands {
            enqueueJS(js)
        }
        pendingCommands.removeAll()
        print("[ChartBridge] Flushed \(count) pending commands")
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
            if let from = intValue(data["from"]),
               let to = intValue(data["to"]) {
                visibleRange = (from, to)
                eventPublisher.send(.visibleRangeChange(from: from, to: to))
            }

        case "jsError":
            let message = data["message"] as? String ?? "Unknown JS error"
            let cmdType = data["type"] as? String ?? "unknown"
            let stack = data["stack"] as? String ?? ""
            lastJSError = message
            print("[ChartBridge] JS error for command '\(cmdType)': \(message)")
            if !stack.isEmpty {
                print("[ChartBridge] JS stack: \(stack)")
            }

        default:
            eventPublisher.send(.unknown(type: type, data: data))
        }
    }

    private func intValue(_ value: Any?) -> Int? {
        if let int = value as? Int {
            return int
        }
        if let double = value as? Double {
            return Int(double)
        }
        if let number = value as? NSNumber {
            return number.intValue
        }
        if let string = value as? String, let parsed = Double(string) {
            return Int(parsed)
        }
        return nil
    }
}
