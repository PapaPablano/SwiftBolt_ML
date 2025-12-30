import Foundation
import SwiftUI
import Combine

// MARK: - Pivot Detector

/// Detects pivot highs and lows in price data
/// Matches PineScript ta.pivothigh() and ta.pivotlow() behavior
struct PivotDetector {

    /// Detect all pivot points for a specific period
    /// - Parameters:
    ///   - bars: OHLC bar data
    ///   - period: Number of bars on each side to confirm pivot (like ta.pivothigh(period, period))
    /// - Returns: Tuple of (pivotHighs, pivotLows) arrays
    static func detectPivots(
        bars: [OHLCBar],
        period: Int
    ) -> (highs: [DetectedPivot], lows: [DetectedPivot]) {
        var pivotHighs: [DetectedPivot] = []
        var pivotLows: [DetectedPivot] = []

        guard bars.count > period * 2 else { return ([], []) }

        // Iterate through bars where we have enough lookback AND lookforward
        // A pivot at index i requires checking i-period to i+period
        for i in period..<(bars.count - period) {
            let bar = bars[i]

            // Check pivot high: current high must be >= all surrounding highs
            var isHigh = true
            for j in (i - period)..<i {
                if bars[j].high > bar.high {
                    isHigh = false
                    break
                }
            }
            if isHigh {
                for j in (i + 1)...(i + period) {
                    if bars[j].high > bar.high {
                        isHigh = false
                        break
                    }
                }
            }
            if isHigh {
                pivotHighs.append(DetectedPivot(index: i, price: bar.high, date: bar.ts, type: .high))
            }

            // Check pivot low: current low must be <= all surrounding lows
            var isLow = true
            for j in (i - period)..<i {
                if bars[j].low < bar.low {
                    isLow = false
                    break
                }
            }
            if isLow {
                for j in (i + 1)...(i + period) {
                    if bars[j].low < bar.low {
                        isLow = false
                        break
                    }
                }
            }
            if isLow {
                pivotLows.append(DetectedPivot(index: i, price: bar.low, date: bar.ts, type: .low))
            }
        }

        return (pivotHighs, pivotLows)
    }

    /// Get the most recent pivot high and low for a period
    /// Equivalent to PineScript's ta.valuewhen(not na(ph), high[len], 0)
    static func getMostRecentPivots(
        bars: [OHLCBar],
        period: Int
    ) -> (high: Double?, highIndex: Int?, low: Double?, lowIndex: Int?) {
        let (highs, lows) = detectPivots(bars: bars, period: period)

        // Get the LAST (most recent) pivot of each type
        let recentHigh = highs.last
        let recentLow = lows.last

        return (
            high: recentHigh?.price,
            highIndex: recentHigh?.index,
            low: recentLow?.price,
            lowIndex: recentLow?.index
        )
    }
}

// MARK: - Multi-Timeframe Pivot Levels Indicator

/// BigBeluga-style multi-timeframe pivot levels with adaptive coloring
/// Matches the TradingView "Pivot Levels [BigBeluga]" indicator
@MainActor
class PivotLevelsIndicator: ObservableObject {

    // MARK: - Settings

    struct Settings {
        // Period 1 (5 bars - micro structure)
        var period1Enabled: Bool = true
        var period1Length: Int = 5
        var period1Style: PivotLineStyle = .dashed
        var period1Extend: PivotExtendMode = .both

        // Period 2 (25 bars - short-term)
        var period2Enabled: Bool = true
        var period2Length: Int = 25
        var period2Style: PivotLineStyle = .solid
        var period2Extend: PivotExtendMode = .both

        // Period 3 (50 bars - medium-term)
        var period3Enabled: Bool = true
        var period3Length: Int = 50
        var period3Style: PivotLineStyle = .solid
        var period3Extend: PivotExtendMode = .both

        // Period 4 (100 bars - long-term macro)
        var period4Enabled: Bool = true
        var period4Length: Int = 100
        var period4Style: PivotLineStyle = .solid
        var period4Extend: PivotExtendMode = .both

        // ATR-based color sensitivity
        // PineScript: atr = ta.atr(200) * 1.5
        var atrPeriod: Int = 200
        var atrMultiplier: Double = 1.5

        // Display options
        var showPriceLabels: Bool = true
        var labelOffset: Int = 15  // Bars to the right for price labels
    }

    // MARK: - Published Properties

    @Published var pivotLevels: [PivotLevel] = []
    @Published var settings: Settings = Settings()
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?

    // MARK: - Private Properties

    private var bars: [OHLCBar] = []
    private var currentATR: Double = 0  // ATR * multiplier (ready to use as threshold)

    // MARK: - Public Methods

    /// Calculate pivot levels for given OHLC data
    func calculate(bars: [OHLCBar]) {
        guard !bars.isEmpty else {
            pivotLevels = []
            return
        }

        isLoading = true
        errorMessage = nil
        self.bars = bars

        // Calculate ATR threshold (ATR * multiplier, matching PineScript)
        calculateATRThreshold(bars: bars)

        // Detect pivots for each enabled period
        detectAllPivots(bars: bars)

        // Update colors based on current price vs pivot levels
        updatePivotColors(bars: bars)

        isLoading = false
    }

    /// Get enabled periods
    var enabledPeriods: [Int] {
        var periods: [Int] = []
        if settings.period1Enabled { periods.append(settings.period1Length) }
        if settings.period2Enabled { periods.append(settings.period2Length) }
        if settings.period3Enabled { periods.append(settings.period3Length) }
        if settings.period4Enabled { periods.append(settings.period4Length) }
        return periods
    }

    /// Get line width for a period (1-4 based on period size)
    func lineWidth(for period: Int) -> CGFloat {
        // PineScript: width1 = len == len1 ? 1 : len == len2 ? 2 : len == len3 ? 3 : 4
        switch period {
        case settings.period1Length: return 1
        case settings.period2Length: return 2
        case settings.period3Length: return 3
        case settings.period4Length: return 4
        default: return 1
        }
    }

    /// Get glow width for a period (larger for larger periods)
    func glowWidth(for period: Int) -> CGFloat {
        // PineScript: width2 = len == len1 ? 3 : len == len2 ? 7 : len == len3 ? 10 : 15
        switch period {
        case settings.period1Length: return 3
        case settings.period2Length: return 7
        case settings.period3Length: return 10
        case settings.period4Length: return 15
        default: return 3
        }
    }

    // MARK: - Private Methods

    /// Calculate ATR threshold = ATR(200) * 1.5
    /// PineScript: atr = ta.atr(200) * 1.5
    private func calculateATRThreshold(bars: [OHLCBar]) {
        guard bars.count > settings.atrPeriod else {
            currentATR = 0
            return
        }

        // Calculate true range for each bar
        var trueRanges: [Double] = []
        for i in 0..<bars.count {
            if i == 0 {
                trueRanges.append(bars[i].high - bars[i].low)
            } else {
                let prev = bars[i - 1]
                let tr = max(
                    bars[i].high - bars[i].low,
                    abs(bars[i].high - prev.close),
                    abs(bars[i].low - prev.close)
                )
                trueRanges.append(tr)
            }
        }

        // Calculate ATR using Wilder's smoothing (EMA)
        var atr = trueRanges.prefix(settings.atrPeriod).reduce(0, +) / Double(settings.atrPeriod)

        for i in settings.atrPeriod..<bars.count {
            atr = (atr * Double(settings.atrPeriod - 1) + trueRanges[i]) / Double(settings.atrPeriod)
        }

        // Apply multiplier (this is the threshold used for color detection)
        currentATR = atr * settings.atrMultiplier
    }

    /// Detect pivots for all enabled periods
    private func detectAllPivots(bars: [OHLCBar]) {
        var levels: [PivotLevel] = []

        // Period 1
        if settings.period1Enabled {
            if let level = createPivotLevel(
                bars: bars,
                period: settings.period1Length,
                style: settings.period1Style,
                extend: settings.period1Extend
            ) {
                levels.append(level)
            }
        }

        // Period 2
        if settings.period2Enabled {
            if let level = createPivotLevel(
                bars: bars,
                period: settings.period2Length,
                style: settings.period2Style,
                extend: settings.period2Extend
            ) {
                levels.append(level)
            }
        }

        // Period 3
        if settings.period3Enabled {
            if let level = createPivotLevel(
                bars: bars,
                period: settings.period3Length,
                style: settings.period3Style,
                extend: settings.period3Extend
            ) {
                levels.append(level)
            }
        }

        // Period 4
        if settings.period4Enabled {
            if let level = createPivotLevel(
                bars: bars,
                period: settings.period4Length,
                style: settings.period4Style,
                extend: settings.period4Extend
            ) {
                levels.append(level)
            }
        }

        pivotLevels = levels
    }

    /// Create a PivotLevel for a specific period
    private func createPivotLevel(
        bars: [OHLCBar],
        period: Int,
        style: PivotLineStyle,
        extend: PivotExtendMode
    ) -> PivotLevel? {
        let pivotData = PivotDetector.getMostRecentPivots(bars: bars, period: period)

        // Need at least one pivot (high or low)
        guard pivotData.high != nil || pivotData.low != nil else {
            return nil
        }

        return PivotLevel(
            length: period,
            display: true,
            style: style,
            extend: extend,
            levelHigh: pivotData.high ?? 0,
            startIndexHigh: pivotData.highIndex ?? bars.count - 1,
            levelLow: pivotData.low ?? 0,
            startIndexLow: pivotData.lowIndex ?? bars.count - 1,
            highStatus: .inactive,
            lowStatus: .inactive
        )
    }

    /// Update pivot colors based on current price position
    /// PineScript:
    ///   color1 = low > H+atr ? colorSup : high < H-atr ? colorRes : colorActive
    ///   color2 = low > L+atr ? colorSup : high < L-atr ? colorRes : colorActive
    private func updatePivotColors(bars: [OHLCBar]) {
        guard let lastBar = bars.last else { return }

        for i in 0..<pivotLevels.count {
            var level = pivotLevels[i]

            // HIGH pivot color logic
            // If current bar's low > pivot high + ATR threshold → Support (price above)
            // If current bar's high < pivot high - ATR threshold → Resistance (price below)
            // Otherwise → Active (being tested)
            if level.levelHigh > 0 {
                if lastBar.low > level.levelHigh + currentATR {
                    level.highStatus = .support
                } else if lastBar.high < level.levelHigh - currentATR {
                    level.highStatus = .resistance
                } else {
                    level.highStatus = .active
                }
            }

            // LOW pivot color logic (same logic applies)
            if level.levelLow > 0 {
                if lastBar.low > level.levelLow + currentATR {
                    level.lowStatus = .support
                } else if lastBar.high < level.levelLow - currentATR {
                    level.lowStatus = .resistance
                } else {
                    level.lowStatus = .active
                }
            }

            pivotLevels[i] = level
        }
    }

    // MARK: - Helper Methods for Period Configuration

    private func isEnabledForPeriod(_ period: Int) -> Bool {
        switch period {
        case settings.period1Length: return settings.period1Enabled
        case settings.period2Length: return settings.period2Enabled
        case settings.period3Length: return settings.period3Enabled
        case settings.period4Length: return settings.period4Enabled
        default: return false
        }
    }

    private func styleForPeriod(_ period: Int) -> PivotLineStyle {
        switch period {
        case settings.period1Length: return settings.period1Style
        case settings.period2Length: return settings.period2Style
        case settings.period3Length: return settings.period3Style
        case settings.period4Length: return settings.period4Style
        default: return .solid
        }
    }

    private func extendModeForPeriod(_ period: Int) -> PivotExtendMode {
        switch period {
        case settings.period1Length: return settings.period1Extend
        case settings.period2Length: return settings.period2Extend
        case settings.period3Length: return settings.period3Extend
        case settings.period4Length: return settings.period4Extend
        default: return .both
        }
    }
}
