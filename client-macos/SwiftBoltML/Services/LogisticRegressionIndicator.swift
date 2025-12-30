import Foundation
import SwiftUI
import Combine

// MARK: - Logistic Regression Model

/// Logistic regression model for S&R classification
/// Matches the Flux Charts PineScript implementation
class LogisticRegressionModel {

    // MARK: - Constants

    static let learningRate: Double = 0.008

    // MARK: - Public Methods

    /// Predict probability that a level is valid S&R
    /// Trains on-the-fly using only pivots of the same type (support or resistance)
    /// - Parameters:
    ///   - isSupport: Whether we're predicting for a support or resistance level
    ///   - rsi: RSI value (binary: -1 or 1)
    ///   - bodySize: Body size (binary: -1 or 1)
    ///   - existingLevels: All existing levels to train from
    ///   - targetRespects: Number of respects needed to be considered "respected"
    /// - Returns: Probability (0-1)
    func predict(
        isSupport: Bool,
        rsi: Double,
        bodySize: Double,
        existingLevels: [LogisticSRLevel],
        targetRespects: Int
    ) -> Double {
        // Filter to only same-type pivots (matching PineScript behavior)
        let sameTypeLevels = existingLevels.filter { $0.isSupport == isSupport }

        guard !sameTypeLevels.isEmpty else {
            return 0.0
        }

        // Initialize weights fresh for each prediction (matching PineScript)
        let baseBias: Double = 1.0
        var rsiBias: Double = 1.0
        var bodySizeBias: Double = 1.0

        var logRes: Double = 0.0

        // Train on each same-type pivot and update weights
        for level in sameTypeLevels {
            let isRespected: Double = level.timesRespected >= targetRespects ? 1.0 : -1.0

            let p = logistic(
                x1: level.detectedRSI,
                x2: level.detectedBodySize,
                bias: baseBias,
                rsiWeight: rsiBias,
                bodySizeWeight: bodySizeBias
            )

            let lossVal = loss(y: isRespected, prediction: p)

            // Gradient descent update
            rsiBias -= Self.learningRate * (p + lossVal) * level.detectedRSI
            bodySizeBias -= Self.learningRate * (p + lossVal) * level.detectedBodySize

            // Calculate prediction with updated weights
            logRes = logistic(
                x1: rsi,
                x2: bodySize,
                bias: baseBias,
                rsiWeight: rsiBias,
                bodySizeWeight: bodySizeBias
            )
        }

        return logRes
    }

    // MARK: - Private Methods

    private func logistic(
        x1: Double,
        x2: Double,
        bias: Double,
        rsiWeight: Double,
        bodySizeWeight: Double
    ) -> Double {
        let exponent = exp(-(bias + rsiWeight * x1 + bodySizeWeight * x2))
        return 1.0 / (1.0 + exponent)
    }

    private func loss(y: Double, prediction: Double) -> Double {
        // Binary cross-entropy loss (clipped to avoid log(0))
        let clipped = max(min(prediction, 0.9999), 0.0001)
        return -y * log(clipped) - (1 - y) * log(1 - clipped)
    }
}

// MARK: - Support/Resistance Level (Logistic)

/// A detected S&R level with ML probability
struct LogisticSRLevel: Identifiable {
    let id = UUID()

    // Core properties
    let isSupport: Bool
    let level: Double
    let startDate: Date
    let startIndex: Int

    // Tracking
    var endDate: Date?
    var endIndex: Int?
    var timesRespected: Int = 0

    // ML Features
    let detectedRSI: Double       // Binary: -1 or 1
    let detectedBodySize: Double  // Binary: -1 or 1
    var detectedByRegression: Bool
    var detectedPrediction: Double  // 0-1

    // Retest tracking
    var latestRetestIndex: Int = 0

    /// Color based on support/resistance type
    var color: Color {
        isSupport ? .green : .red
    }
}

/// Signal from logistic regression indicator
enum LogisticSignal: String, CaseIterable {
    case supportRetest = "Support Retest"
    case supportBreak = "Support Break"
    case resistanceRetest = "Resistance Retest"
    case resistanceBreak = "Resistance Break"
}

// MARK: - Logistic Regression S&R Indicator

/// Flux Charts style logistic regression S&R indicator
/// Processes bars sequentially to match PineScript streaming behavior
@MainActor
class LogisticRegressionIndicator: ObservableObject {

    // MARK: - Settings

    struct Settings {
        var pivotLength: Int = 14
        var targetRespects: Int = 3
        var probabilityThreshold: Double = 0.7
        var hideFarLines: Bool = true
        var showPredictionLabels: Bool = true
        var showRetests: Bool = false
        var showBreaks: Bool = false
        var retestCooldown: Int = 3

        // Colors
        var supportColor: Color = Color(red: 0.03, green: 0.60, blue: 0.51)   // #089981
        var resistanceColor: Color = Color(red: 0.95, green: 0.21, blue: 0.27) // #F23645
        var textColorSupport: Color = .white
        var textColorResistance: Color = .white
    }

    // MARK: - Published Properties

    @Published var allLevels: [LogisticSRLevel] = []
    @Published var regressionLevels: [LogisticSRLevel] = []
    @Published var respectedLevels: [LogisticSRLevel] = []
    @Published var currentSignals: [LogisticSignal] = []
    @Published var settings: Settings = Settings()
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?

    // MARK: - Private Properties

    private var bars: [OHLCBar] = []
    private var rsiValues: [Double] = []
    private var bodySizeValues: [Double] = []
    private var atrValues: [Double] = []
    private var logisticModel = LogisticRegressionModel()

    // MARK: - Public Methods

    /// Calculate logistic regression S&R levels
    /// Processes bars sequentially to match PineScript streaming behavior
    func calculate(bars: [OHLCBar]) {
        guard !bars.isEmpty else {
            allLevels = []
            regressionLevels = []
            respectedLevels = []
            currentSignals = []
            return
        }

        isLoading = true
        errorMessage = nil
        self.bars = bars

        // Pre-calculate indicators for all bars
        calculateRSI(bars: bars)
        calculateBodySize(bars: bars)
        calculateATR(bars: bars)

        // Process bars sequentially (streaming approach like PineScript)
        processSequentially(bars: bars)

        // Detect signals on the last bar
        detectSignals(bars: bars)

        // Filter levels for display
        filterLevels(bars: bars)

        isLoading = false
    }

    /// Get support levels that passed probability threshold
    var supportLevels: [LogisticSRLevel] {
        regressionLevels.filter { $0.isSupport }
    }

    /// Get resistance levels that passed probability threshold
    var resistanceLevels: [LogisticSRLevel] {
        regressionLevels.filter { !$0.isSupport }
    }

    // MARK: - Private Methods

    /// Process bars sequentially to match PineScript streaming behavior
    /// Order: 1) Update existing levels, 2) Detect new pivots, 3) Predict for new pivots
    private func processSequentially(bars: [OHLCBar]) {
        allLevels = []

        guard bars.count > settings.pivotLength * 2 else { return }

        // Process each bar sequentially
        for currentBarIndex in (settings.pivotLength * 2)..<bars.count {
            let currentBar = bars[currentBarIndex]

            // Step 1: Update all existing levels with current bar (retests/breaks)
            updateExistingLevels(currentBar: currentBar, currentIndex: currentBarIndex)

            // Step 2: Check if there's a pivot at (currentBarIndex - pivotLength)
            // Pivots are detected with a lookback of pivotLength
            let pivotIndex = currentBarIndex - settings.pivotLength

            if pivotIndex >= settings.pivotLength {
                detectAndPredictPivot(at: pivotIndex, bars: bars)
            }
        }
    }

    /// Update existing levels with current bar data (retests and breaks)
    private func updateExistingLevels(currentBar: OHLCBar, currentIndex: Int) {
        for i in 0..<allLevels.count {
            var level = allLevels[i]

            // Skip if already ended (broken)
            guard level.endIndex == nil else { continue }

            // Skip if current bar is before/at the level's start
            guard currentIndex > level.startIndex + settings.pivotLength else { continue }

            if level.isSupport {
                // Support level logic
                if currentBar.low < level.level {
                    // Price touched below support
                    if currentBar.close > level.level {
                        // Bounced back above - this is a retest
                        // ALWAYS increment timesRespected (PineScript behavior)
                        level.timesRespected += 1

                        // Only update latestRetestIndex if cooldown passed
                        if currentIndex > level.latestRetestIndex + settings.retestCooldown {
                            level.latestRetestIndex = currentIndex
                        }
                    } else {
                        // Closed below support - BREAK
                        level.endIndex = currentIndex
                        level.endDate = currentBar.ts
                    }
                }
            } else {
                // Resistance level logic
                if currentBar.high > level.level {
                    // Price touched above resistance
                    if currentBar.close < level.level {
                        // Bounced back below - this is a retest
                        // ALWAYS increment timesRespected (PineScript behavior)
                        level.timesRespected += 1

                        // Only update latestRetestIndex if cooldown passed
                        if currentIndex > level.latestRetestIndex + settings.retestCooldown {
                            level.latestRetestIndex = currentIndex
                        }
                    } else {
                        // Closed above resistance - BREAK
                        level.endIndex = currentIndex
                        level.endDate = currentBar.ts
                    }
                }
            }

            allLevels[i] = level
        }
    }

    /// Detect pivot at a specific index and run prediction
    private func detectAndPredictPivot(at pivotIndex: Int, bars: [OHLCBar]) {
        let bar = bars[pivotIndex]

        // Check pivot high (resistance)
        var isHigh = true
        for offset in 1...settings.pivotLength {
            let leftIdx = pivotIndex - offset
            let rightIdx = pivotIndex + offset

            if leftIdx >= 0 && bars[leftIdx].high > bar.high {
                isHigh = false
                break
            }
            if rightIdx < bars.count && bars[rightIdx].high > bar.high {
                isHigh = false
                break
            }
        }

        if isHigh {
            createAndPredictLevel(
                isSupport: false,
                level: bar.high,
                pivotIndex: pivotIndex,
                bar: bar
            )
        }

        // Check pivot low (support)
        var isLow = true
        for offset in 1...settings.pivotLength {
            let leftIdx = pivotIndex - offset
            let rightIdx = pivotIndex + offset

            if leftIdx >= 0 && bars[leftIdx].low < bar.low {
                isLow = false
                break
            }
            if rightIdx < bars.count && bars[rightIdx].low < bar.low {
                isLow = false
                break
            }
        }

        if isLow {
            createAndPredictLevel(
                isSupport: true,
                level: bar.low,
                pivotIndex: pivotIndex,
                bar: bar
            )
        }
    }

    /// Create a new level and run prediction using existing levels
    private func createAndPredictLevel(
        isSupport: Bool,
        level: Double,
        pivotIndex: Int,
        bar: OHLCBar
    ) {
        let rsi = rsiValues[pivotIndex]
        let bodySize = bodySizeValues[pivotIndex]
        let atr = atrValues[pivotIndex]

        let rsiSigned = rsi > 50 ? 1.0 : -1.0
        let bodySizeSigned = atr > 0 && bodySize > atr ? 1.0 : -1.0

        // Create new level (initially not detected by regression)
        var newLevel = LogisticSRLevel(
            isSupport: isSupport,
            level: level,
            startDate: bar.ts,
            startIndex: pivotIndex,
            detectedRSI: rsiSigned,
            detectedBodySize: bodySizeSigned,
            detectedByRegression: false,
            detectedPrediction: 0
        )

        // Add to allLevels first (PineScript adds before predict)
        allLevels.append(newLevel)

        // Run prediction using ALL existing levels (including the one just added)
        // This matches PineScript behavior where predict iterates over allPivots
        let prediction = logisticModel.predict(
            isSupport: isSupport,
            rsi: rsiSigned,
            bodySize: bodySizeSigned,
            existingLevels: allLevels,
            targetRespects: settings.targetRespects
        )

        // Update the level if prediction meets threshold
        if prediction >= settings.probabilityThreshold {
            newLevel.detectedByRegression = true
            newLevel.detectedPrediction = prediction
            allLevels[allLevels.count - 1] = newLevel
        }
    }

    /// Detect signals on the current (last) bar
    private func detectSignals(bars: [OHLCBar]) {
        var signals: [LogisticSignal] = []

        guard bars.count >= 2 else {
            currentSignals = []
            return
        }

        let currentBar = bars[bars.count - 1]
        let currentIndex = bars.count - 1

        for level in allLevels {
            // Only check regression-detected levels
            guard level.detectedByRegression else { continue }
            // Skip broken levels
            guard level.endIndex == nil else { continue }

            if level.isSupport {
                // Must touch the level first (low < level)
                if currentBar.low < level.level {
                    if currentBar.close > level.level {
                        // Retest signal (only with cooldown)
                        if currentIndex > level.latestRetestIndex + settings.retestCooldown {
                            signals.append(.supportRetest)
                        }
                    } else {
                        // Break signal
                        signals.append(.supportBreak)
                    }
                }
            } else {
                // Must touch the level first (high > level)
                if currentBar.high > level.level {
                    if currentBar.close < level.level {
                        // Retest signal (only with cooldown)
                        if currentIndex > level.latestRetestIndex + settings.retestCooldown {
                            signals.append(.resistanceRetest)
                        }
                    } else {
                        // Break signal
                        signals.append(.resistanceBreak)
                    }
                }
            }
        }

        currentSignals = signals
    }

    private func filterLevels(bars: [OHLCBar]) {
        // Filter by regression prediction
        regressionLevels = allLevels.filter { $0.detectedByRegression }

        // Filter far lines if enabled
        if settings.hideFarLines, let lastBar = bars.last, let atr = atrValues.last, atr > 0 {
            regressionLevels = regressionLevels.filter { level in
                level.endIndex != nil || abs(lastBar.close - level.level) <= atr * 7
            }
        }

        // Track respected levels
        respectedLevels = allLevels.filter { $0.timesRespected >= settings.targetRespects }
    }

    // MARK: - Indicator Calculations

    private func calculateRSI(bars: [OHLCBar]) {
        rsiValues = Array(repeating: 0, count: bars.count)

        guard bars.count > settings.pivotLength else { return }

        // Calculate price changes
        var gains: [Double] = [0]
        var losses: [Double] = [0]

        for i in 1..<bars.count {
            let change = bars[i].close - bars[i - 1].close
            gains.append(max(change, 0))
            losses.append(max(-change, 0))
        }

        // Initial averages
        var avgGain = gains.prefix(settings.pivotLength + 1).reduce(0, +) / Double(settings.pivotLength)
        var avgLoss = losses.prefix(settings.pivotLength + 1).reduce(0, +) / Double(settings.pivotLength)

        for i in settings.pivotLength..<bars.count {
            avgGain = (avgGain * Double(settings.pivotLength - 1) + gains[i]) / Double(settings.pivotLength)
            avgLoss = (avgLoss * Double(settings.pivotLength - 1) + losses[i]) / Double(settings.pivotLength)

            let rs = avgLoss == 0 ? 100 : avgGain / avgLoss
            rsiValues[i] = 100 - (100 / (1 + rs))
        }
    }

    private func calculateBodySize(bars: [OHLCBar]) {
        bodySizeValues = bars.map { abs($0.close - $0.open) }
    }

    private func calculateATR(bars: [OHLCBar]) {
        atrValues = Array(repeating: 0, count: bars.count)

        guard bars.count > settings.pivotLength else { return }

        let trueRanges = bars.enumerated().map { i, bar -> Double in
            if i == 0 { return bar.high - bar.low }
            let prev = bars[i - 1]
            return max(
                bar.high - bar.low,
                abs(bar.high - prev.close),
                abs(bar.low - prev.close)
            )
        }

        var atr = trueRanges.prefix(settings.pivotLength).reduce(0, +) / Double(settings.pivotLength)

        for i in settings.pivotLength..<bars.count {
            atr = (atr * Double(settings.pivotLength - 1) + trueRanges[i]) / Double(settings.pivotLength)
            atrValues[i] = atr
        }
    }
}
