import Foundation

/// Technical indicators calculator for OHLC bar data
/// Supports SMA, EMA, RSI, and other common indicators
struct TechnicalIndicators {

    // MARK: - Simple Moving Average (SMA)

    /// Calculate Simple Moving Average using rolling sum - O(n) instead of O(n·period)
    /// - Parameters:
    ///   - data: Array of values (typically close prices)
    ///   - period: Number of periods for the average
    /// - Returns: Array of SMA values (nil for insufficient data points)
    static func sma(_ data: [Double], period: Int) -> [Double?] {
        guard period > 0, data.count >= period else {
            return Array(repeating: nil, count: data.count)
        }

        var result: [Double?] = Array(repeating: nil, count: period - 1)

        // Initialize rolling sum with first 'period' values
        var rollingSum = data[0..<period].reduce(0, +)
        result.append(rollingSum / Double(period))

        // Roll through remaining values: add new, subtract oldest
        for i in period..<data.count {
            rollingSum += data[i] - data[i - period]
            result.append(rollingSum / Double(period))
        }

        return result
    }

    /// Calculate SMA from OHLC bars
    static func sma(bars: [OHLCBar], period: Int, useClose: Bool = true) -> [Double?] {
        let prices = useClose ? bars.map(\.close) : bars.map(\.open)
        return sma(prices, period: period)
    }

    // MARK: - Exponential Moving Average (EMA)

    /// Calculate Exponential Moving Average
    /// - Parameters:
    ///   - data: Array of values (typically close prices)
    ///   - period: Number of periods for the average
    /// - Returns: Array of EMA values (nil for insufficient data points)
    static func ema(_ data: [Double], period: Int) -> [Double?] {
        guard period > 0, data.count >= period else {
            return Array(repeating: nil, count: data.count)
        }

        let multiplier = 2.0 / Double(period + 1)
        var result: [Double?] = Array(repeating: nil, count: period - 1)

        // First EMA is SMA of first period values
        let firstSlice = data[0..<period]
        var ema = firstSlice.reduce(0, +) / Double(period)
        result.append(ema)

        // Calculate remaining EMAs
        for i in period..<data.count {
            ema = (data[i] - ema) * multiplier + ema
            result.append(ema)
        }

        return result
    }

    static func rma(_ data: [Double], period: Int) -> [Double?] {
        guard period > 0, data.count >= period else {
            return Array(repeating: nil, count: data.count)
        }

        var result: [Double?] = Array(repeating: nil, count: period - 1)
        var prev = data[0..<period].reduce(0, +) / Double(period)
        result.append(prev)

        for i in period..<data.count {
            prev = (prev * Double(period - 1) + data[i]) / Double(period)
            result.append(prev)
        }

        return result
    }

    /// Calculate EMA from OHLC bars
    static func ema(bars: [OHLCBar], period: Int, useClose: Bool = true) -> [Double?] {
        let prices = useClose ? bars.map(\.close) : bars.map(\.open)
        return ema(prices, period: period)
    }

    // MARK: - Relative Strength Index (RSI)

    /// Calculate Relative Strength Index
    /// - Parameters:
    ///   - data: Array of values (typically close prices)
    ///   - period: Number of periods (typically 14)
    /// - Returns: Array of RSI values (0-100, nil for insufficient data)
    static func rsi(_ data: [Double], period: Int) -> [Double?] {
        guard period > 0, data.count > period else {
            return Array(repeating: nil, count: data.count)
        }

        var result: [Double?] = [nil] // First value has no previous price
        var gains: [Double] = []
        var losses: [Double] = []

        // Calculate initial gains and losses
        for i in 1..<data.count {
            let change = data[i] - data[i - 1]
            if change > 0 {
                gains.append(change)
                losses.append(0)
            } else {
                gains.append(0)
                losses.append(abs(change))
            }
        }

        // Calculate initial average gain/loss
        guard gains.count >= period else {
            return Array(repeating: nil, count: data.count)
        }

        var avgGain = gains[0..<period].reduce(0, +) / Double(period)
        var avgLoss = losses[0..<period].reduce(0, +) / Double(period)

        // Add nil for the warmup period
        result.append(contentsOf: Array(repeating: nil, count: period - 1))

        // Calculate first RSI
        let rs = avgLoss == 0 ? 100.0 : avgGain / avgLoss
        let rsiValue = 100.0 - (100.0 / (1.0 + rs))
        result.append(rsiValue)

        // Calculate subsequent RSI values using smoothed averages
        for i in period..<gains.count {
            avgGain = (avgGain * Double(period - 1) + gains[i]) / Double(period)
            avgLoss = (avgLoss * Double(period - 1) + losses[i]) / Double(period)

            let rs = avgLoss == 0 ? 100.0 : avgGain / avgLoss
            let rsiValue = 100.0 - (100.0 / (1.0 + rs))
            result.append(rsiValue)
        }

        return result
    }

    /// Calculate RSI from OHLC bars
    static func rsi(bars: [OHLCBar], period: Int = 14) -> [Double?] {
        let closePrices = bars.map(\.close)
        return rsi(closePrices, period: period)
    }

    // MARK: - Volume Analysis

    /// Calculate volume-weighted average price (VWAP)
    static func vwap(bars: [OHLCBar]) -> [Double?] {
        guard !bars.isEmpty else { return [] }

        var result: [Double?] = []
        var cumulativePV: Double = 0
        var cumulativeVolume: Double = 0

        for bar in bars {
            let typicalPrice = (bar.high + bar.low + bar.close) / 3.0
            cumulativePV += typicalPrice * bar.volume
            cumulativeVolume += bar.volume

            if cumulativeVolume > 0 {
                result.append(cumulativePV / cumulativeVolume)
            } else {
                result.append(nil)
            }
        }

        return result
    }

    // MARK: - Bollinger Bands

    struct BollingerBands {
        let upper: [Double?]
        let middle: [Double?]
        let lower: [Double?]
    }

    /// Calculate Bollinger Bands using rolling statistics - O(n) instead of O(n·period)
    /// Uses rolling sum and sum of squares for online variance calculation
    /// - Parameters:
    ///   - data: Array of values (typically close prices)
    ///   - period: SMA period (typically 20)
    ///   - stdDevMultiplier: Standard deviation multiplier (typically 2)
    /// - Returns: Bollinger Bands (upper, middle, lower)
    static func bollingerBands(_ data: [Double], period: Int, stdDevMultiplier: Double = 2.0) -> BollingerBands {
        guard period > 0, data.count >= period else {
            return BollingerBands(
                upper: Array(repeating: nil, count: data.count),
                middle: Array(repeating: nil, count: data.count),
                lower: Array(repeating: nil, count: data.count)
            )
        }

        var upper: [Double?] = Array(repeating: nil, count: period - 1)
        var middle: [Double?] = Array(repeating: nil, count: period - 1)
        var lower: [Double?] = Array(repeating: nil, count: period - 1)

        // Initialize rolling sum and sum of squares for first window
        var rollingSum: Double = 0
        var rollingSumSq: Double = 0
        for i in 0..<period {
            rollingSum += data[i]
            rollingSumSq += data[i] * data[i]
        }

        // Calculate first values
        let periodD = Double(period)
        var smaValue = rollingSum / periodD
        var variance = (rollingSumSq / periodD) - (smaValue * smaValue)
        var stdDev = sqrt(max(0, variance))  // Protect against floating point errors

        middle.append(smaValue)
        upper.append(smaValue + stdDevMultiplier * stdDev)
        lower.append(smaValue - stdDevMultiplier * stdDev)

        // Roll through remaining values
        for i in period..<data.count {
            let oldValue = data[i - period]
            let newValue = data[i]

            // Update rolling sums
            rollingSum += newValue - oldValue
            rollingSumSq += (newValue * newValue) - (oldValue * oldValue)

            // Calculate new SMA and StdDev
            smaValue = rollingSum / periodD
            variance = (rollingSumSq / periodD) - (smaValue * smaValue)
            stdDev = sqrt(max(0, variance))

            middle.append(smaValue)
            upper.append(smaValue + stdDevMultiplier * stdDev)
            lower.append(smaValue - stdDevMultiplier * stdDev)
        }

        return BollingerBands(upper: upper, middle: middle, lower: lower)
    }

    /// Calculate Bollinger Bands from OHLC bars
    static func bollingerBands(bars: [OHLCBar], period: Int = 20, stdDevMultiplier: Double = 2.0) -> BollingerBands {
        let closePrices = bars.map(\.close)
        return bollingerBands(closePrices, period: period, stdDevMultiplier: stdDevMultiplier)
    }

    // MARK: - MACD (Moving Average Convergence Divergence)

    struct MACDResult {
        let macd: [Double?]      // MACD line (fast EMA - slow EMA)
        let signal: [Double?]    // Signal line (EMA of MACD)
        let histogram: [Double?] // MACD - Signal
    }

    /// Calculate MACD indicator
    /// - Parameters:
    ///   - data: Array of values (typically close prices)
    ///   - fastPeriod: Fast EMA period (typically 12)
    ///   - slowPeriod: Slow EMA period (typically 26)
    ///   - signalPeriod: Signal line EMA period (typically 9)
    /// - Returns: MACDResult containing MACD line, signal line, and histogram
    static func macd(
        _ data: [Double],
        fastPeriod: Int = 12,
        slowPeriod: Int = 26,
        signalPeriod: Int = 9
    ) -> MACDResult {
        let fastEMA = ema(data, period: fastPeriod)
        let slowEMA = ema(data, period: slowPeriod)

        // MACD line = Fast EMA - Slow EMA
        var macdLine: [Double?] = []
        for i in 0..<data.count {
            if let fast = fastEMA[i], let slow = slowEMA[i] {
                macdLine.append(fast - slow)
            } else {
                macdLine.append(nil)
            }
        }

        // Signal line = EMA of MACD values
        let macdValues = macdLine.compactMap { $0 }
        let signalEMA = ema(macdValues, period: signalPeriod)

        // Align signal with MACD
        var signalLine: [Double?] = []
        var signalIdx = 0
        for macdVal in macdLine {
            if macdVal != nil {
                signalLine.append(signalIdx < signalEMA.count ? signalEMA[signalIdx] : nil)
                signalIdx += 1
            } else {
                signalLine.append(nil)
            }
        }

        // Histogram = MACD - Signal
        var histogram: [Double?] = []
        for i in 0..<macdLine.count {
            if let m = macdLine[i], let s = signalLine[i] {
                histogram.append(m - s)
            } else {
                histogram.append(nil)
            }
        }

        return MACDResult(macd: macdLine, signal: signalLine, histogram: histogram)
    }

    /// Calculate MACD from OHLC bars
    static func macd(
        bars: [OHLCBar],
        fastPeriod: Int = 12,
        slowPeriod: Int = 26,
        signalPeriod: Int = 9
    ) -> MACDResult {
        let closePrices = bars.map(\.close)
        return macd(closePrices, fastPeriod: fastPeriod, slowPeriod: slowPeriod, signalPeriod: signalPeriod)
    }

    // MARK: - Stochastic Oscillator

    struct StochasticResult {
        let k: [Double?]  // %K line (fast stochastic)
        let d: [Double?]  // %D line (SMA of %K)
    }

    /// Calculate Stochastic Oscillator
    /// - Parameters:
    ///   - bars: OHLC bars
    ///   - kPeriod: Lookback period for %K (typically 14)
    ///   - dPeriod: Smoothing period for %D (typically 3)
    /// - Returns: StochasticResult with %K and %D lines
    static func stochastic(
        bars: [OHLCBar],
        kPeriod: Int = 14,
        dPeriod: Int = 3
    ) -> StochasticResult {
        var kValues: [Double?] = []

        for i in 0..<bars.count {
            if i < kPeriod - 1 {
                kValues.append(nil)
            } else {
                let periodBars = Array(bars[(i - kPeriod + 1)...i])
                let highestHigh = periodBars.map(\.high).max() ?? 0
                let lowestLow = periodBars.map(\.low).min() ?? 0
                let close = bars[i].close

                let range = highestHigh - lowestLow
                let k = range == 0 ? 50 : ((close - lowestLow) / range) * 100
                kValues.append(k)
            }
        }

        // %D = SMA of %K
        let kFiltered = kValues.compactMap { $0 }
        let dSMA = sma(kFiltered, period: dPeriod)

        // Align D with K
        var dValues: [Double?] = []
        var dIdx = 0
        for kVal in kValues {
            if kVal != nil {
                dValues.append(dIdx < dSMA.count ? dSMA[dIdx] : nil)
                dIdx += 1
            } else {
                dValues.append(nil)
            }
        }

        return StochasticResult(k: kValues, d: dValues)
    }

    // MARK: - KDJ Indicator

    struct KDJResult {
        let k: [Double?]  // K line
        let d: [Double?]  // D line
        let j: [Double?]  // J line (3*K - 2*D, more sensitive)
    }

    /// Calculate KDJ Indicator with J line for early reversal detection
    /// CORRECTED: Uses exponential smoothing (2/3 weight on prior) instead of SMA
    /// - Parameters:
    ///   - bars: OHLC bars
    ///   - period: Lookback period for RSV (typically 9)
    ///   - kSmooth: Smoothing period for K (typically 3, used for EMA alpha)
    ///   - dSmooth: Smoothing period for D (typically 3, used for EMA alpha)
    /// - Returns: KDJResult with K, D, and J lines
    static func kdj(
        bars: [OHLCBar],
        period: Int = 9,
        kSmooth: Int = 3,
        dSmooth: Int = 3
    ) -> KDJResult {
        guard bars.count >= period else {
            return KDJResult(
                k: Array(repeating: nil, count: bars.count),
                d: Array(repeating: nil, count: bars.count),
                j: Array(repeating: nil, count: bars.count)
            )
        }

        var kValues: [Double?] = Array(repeating: nil, count: period - 1)
        var dValues: [Double?] = Array(repeating: nil, count: period - 1)
        var jValues: [Double?] = Array(repeating: nil, count: period - 1)

        // Initialize K and D at neutral (50)
        var prevK: Double = 50.0
        var prevD: Double = 50.0

        for i in (period - 1)..<bars.count {
            // Calculate RSV (Raw Stochastic Value)
            let periodBars = Array(bars[(i - period + 1)...i])
            let highestHigh = periodBars.map(\.high).max() ?? 0
            let lowestLow = periodBars.map(\.low).min() ?? 0
            let close = bars[i].close

            let range = highestHigh - lowestLow
            let rsv = range == 0 ? 50.0 : ((close - lowestLow) / range) * 100.0

            // CORRECTED: K = (2/3)*K_prev + (1/3)*RSV (exponential smoothing)
            let currentK = (2.0 / 3.0) * prevK + (1.0 / 3.0) * rsv

            // CORRECTED: D = (2/3)*D_prev + (1/3)*K (exponential smoothing)
            let currentD = (2.0 / 3.0) * prevD + (1.0 / 3.0) * currentK

            // J = 3*K - 2*D (extreme sensitivity indicator)
            let currentJ = 3.0 * currentK - 2.0 * currentD

            kValues.append(currentK)
            dValues.append(currentD)
            jValues.append(currentJ)

            prevK = currentK
            prevD = currentD
        }

        return KDJResult(k: kValues, d: dValues, j: jValues)
    }

    // MARK: - ADX (Average Directional Index)

    struct ADXResult {
        let adx: [Double?]     // ADX line (trend strength 0-100)
        let plusDI: [Double?]  // +DI line (bullish direction)
        let minusDI: [Double?] // -DI line (bearish direction)
    }

    /// Calculate Average Directional Index for trend strength
    /// CORRECTED: Uses Wilder's smoothing (EMA) throughout, not SMA for ADX
    /// - Parameters:
    ///   - bars: OHLC bars
    ///   - period: Smoothing period (typically 14)
    /// - Returns: ADXResult with ADX, +DI, and -DI lines
    static func adx(bars: [OHLCBar], period: Int = 14) -> ADXResult {
        guard bars.count > period else {
            return ADXResult(
                adx: Array(repeating: nil, count: bars.count),
                plusDI: Array(repeating: nil, count: bars.count),
                minusDI: Array(repeating: nil, count: bars.count)
            )
        }

        // Calculate +DM, -DM, and True Range
        var plusDM: [Double] = [0]
        var minusDM: [Double] = [0]
        var tr: [Double] = [bars[0].high - bars[0].low]

        for i in 1..<bars.count {
            let highDiff = bars[i].high - bars[i - 1].high
            let lowDiff = bars[i - 1].low - bars[i].low

            plusDM.append(highDiff > lowDiff && highDiff > 0 ? highDiff : 0)
            minusDM.append(lowDiff > highDiff && lowDiff > 0 ? lowDiff : 0)

            let trueRange = max(
                bars[i].high - bars[i].low,
                abs(bars[i].high - bars[i - 1].close),
                abs(bars[i].low - bars[i - 1].close)
            )
            tr.append(trueRange)
        }

        // CORRECTED: Smooth with Wilder's EMA (span = period)
        let plusDMSmooth = ema(plusDM, period: period)
        let minusDMSmooth = ema(minusDM, period: period)
        let trSmooth = ema(tr, period: period)

        var plusDI: [Double?] = []
        var minusDI: [Double?] = []
        var dxValues: [Double] = []
        var dxStartIdx = 0

        for i in 0..<bars.count {
            if let pdi = plusDMSmooth[i], let mdi = minusDMSmooth[i], let atr = trSmooth[i], atr > 0 {
                let pdiVal = (pdi / atr) * 100
                let mdiVal = (mdi / atr) * 100
                plusDI.append(pdiVal)
                minusDI.append(mdiVal)

                let sum = pdiVal + mdiVal
                if sum > 0 {
                    if dxValues.isEmpty {
                        dxStartIdx = i
                    }
                    dxValues.append(abs(pdiVal - mdiVal) / sum * 100)
                }
            } else {
                plusDI.append(nil)
                minusDI.append(nil)
            }
        }

        // CORRECTED: ADX = Wilder's EMA of DX (not SMA!)
        let adxSmooth = ema(dxValues, period: period)

        // Align ADX with original data
        var adxValues: [Double?] = Array(repeating: nil, count: dxStartIdx)
        for val in adxSmooth {
            adxValues.append(val)
        }

        // Pad to match length if needed
        while adxValues.count < bars.count {
            adxValues.append(nil)
        }

        return ADXResult(adx: adxValues, plusDI: plusDI, minusDI: minusDI)
    }

    // MARK: - SuperTrend

    struct SuperTrendResult {
        let supertrend: [Double?]  // SuperTrend line
        let trend: [Int]           // 1 = bullish, -1 = bearish, 0 = neutral
        let strength: [Double?]    // Trend strength 0-100 (distance from ST as % of ATR)
    }

    /// Calculate SuperTrend indicator
    /// - Parameters:
    ///   - bars: OHLC bars
    ///   - period: ATR period (typically 10)
    ///   - multiplier: ATR multiplier (typically 3.0)
    /// - Returns: SuperTrendResult with SuperTrend line and trend direction
    static func superTrend(
        bars: [OHLCBar],
        period: Int = 10,
        multiplier: Double = 3.0
    ) -> SuperTrendResult {
        guard bars.count > period else {
            return SuperTrendResult(
                supertrend: Array(repeating: nil, count: bars.count),
                trend: Array(repeating: 0, count: bars.count),
                strength: Array(repeating: nil, count: bars.count)
            )
        }

        // Calculate True Range
        var tr: [Double] = []
        for i in 0..<bars.count {
            if i == 0 {
                tr.append(bars[i].high - bars[i].low)
            } else {
                let trueRange = max(
                    bars[i].high - bars[i].low,
                    abs(bars[i].high - bars[i - 1].close),
                    abs(bars[i].low - bars[i - 1].close)
                )
                tr.append(trueRange)
            }
        }

        let atrRMA = rma(tr, period: period)

        var supertrend: [Double?] = []
        var trend: [Int] = []
        var finalUpper: [Double] = []
        var finalLower: [Double] = []

        for i in 0..<bars.count {
            let hl2 = (bars[i].high + bars[i].low) / 2

            guard let atr = atrRMA[i] else {
                supertrend.append(nil)
                trend.append(0)
                finalUpper.append(hl2)
                finalLower.append(hl2)
                continue
            }

            let basicUpperBand = hl2 + multiplier * atr
            let basicLowerBand = hl2 - multiplier * atr

            if i == 0 {
                finalUpper.append(basicUpperBand)
                finalLower.append(basicLowerBand)
                trend.append(1)  // Start bullish
                supertrend.append(basicLowerBand)
            } else {
                let close = bars[i].close
                let prevClose = bars[i - 1].close
                let prevTrend = trend[i - 1]
                
                // Calculate final upper band
                // Upper band can only move DOWN (never up) - acts as resistance
                var newUpper: Double
                if basicUpperBand < finalUpper[i - 1] || prevClose > finalUpper[i - 1] {
                    newUpper = basicUpperBand
                } else {
                    newUpper = finalUpper[i - 1]
                }
                
                // Calculate final lower band  
                // Lower band can only move UP (never down) - acts as support
                var newLower: Double
                if basicLowerBand > finalLower[i - 1] || prevClose < finalLower[i - 1] {
                    newLower = basicLowerBand
                } else {
                    newLower = finalLower[i - 1]
                }

                finalUpper.append(newUpper)
                finalLower.append(newLower)

                // Determine trend direction based on price vs previous SuperTrend
                var currentTrend: Int
                
                if prevTrend == 1 || prevTrend == 0 {
                    // Was bullish - check if price broke below lower band
                    if close < newLower {
                        currentTrend = -1  // Flip to bearish
                    } else {
                        currentTrend = 1   // Stay bullish
                    }
                } else {
                    // Was bearish - check if price broke above upper band
                    if close > newUpper {
                        currentTrend = 1   // Flip to bullish
                    } else {
                        currentTrend = -1  // Stay bearish
                    }
                }
                
                trend.append(currentTrend)
                
                // SuperTrend line value
                // When bullish: use lower band (trailing stop below price)
                // When bearish: use upper band (trailing stop above price)
                supertrend.append(currentTrend == 1 ? newLower : newUpper)
            }
        }

        // Calculate trend strength: distance from SuperTrend as percentage of ATR
        // Capped at 100 (when price is 2x ATR away from SuperTrend)
        var strength: [Double?] = []
        for i in 0..<bars.count {
            guard let stValue = supertrend[i], let atr = atrRMA[i], atr > 0 else {
                strength.append(nil)
                continue
            }

            let close = bars[i].close
            let distance = abs(close - stValue)
            // Normalize: 0 = at SuperTrend, 100 = 2x ATR away
            let normalizedStrength = min(100.0, (distance / atr) * 50.0)
            strength.append(normalizedStrength)
        }

        return SuperTrendResult(supertrend: supertrend, trend: trend, strength: strength)
    }

    // MARK: - ATR (Average True Range)

    /// Calculate Average True Range
    /// CORRECTED: Uses Wilder's EMA smoothing instead of SMA
    /// - Parameters:
    ///   - bars: OHLC bars
    ///   - period: ATR period (typically 14)
    /// - Returns: Array of ATR values
    static func atr(bars: [OHLCBar], period: Int = 14) -> [Double?] {
        guard bars.count > 1 else {
            return Array(repeating: nil, count: bars.count)
        }

        var tr: [Double] = []
        for i in 0..<bars.count {
            if i == 0 {
                tr.append(bars[i].high - bars[i].low)
            } else {
                let trueRange = max(
                    bars[i].high - bars[i].low,
                    abs(bars[i].high - bars[i - 1].close),
                    abs(bars[i].low - bars[i - 1].close)
                )
                tr.append(trueRange)
            }
        }

        // CORRECTED: Use Wilder's EMA (not SMA) for smoothing
        return rma(tr, period: period)
    }
}

// MARK: - Data Point for Chart Overlay

struct IndicatorDataPoint: Identifiable {
    let id = UUID()
    let date: Date
    let value: Double?

    init(bar: OHLCBar, value: Double?) {
        self.date = bar.ts
        self.value = value
    }
}

// MARK: - Indicator Configuration

enum SuperTrendAIClusterSelection: String, Equatable, Codable {
    case best
    case average
    case worst
}

struct IndicatorConfig: Equatable {
    // Moving Averages
    var showSMA20: Bool = false
    var showSMA50: Bool = false
    var showSMA200: Bool = false
    var showEMA9: Bool = false
    var showEMA21: Bool = false

    // Volume
    var showVolume: Bool = false

    // Oscillators
    var showRSI: Bool = false
    var showMACD: Bool = false
    var showStochastic: Bool = false
    var showKDJ: Bool = false

    // Volatility/Trend
    var showBollingerBands: Bool = false
    var showADX: Bool = false
    var showSuperTrend: Bool = true  // Enabled - rendered as overlay on main chart (note: Lightweight Charts limitation means separate color segments)
    var showATR: Bool = false

    // SuperTrend Mode
    var useSuperTrendAI: Bool = true  // Use K-Means adaptive version vs basic

    // SuperTrend AI Enhanced Options
    var showTrendZones: Bool = true
    var showSignalMarkers: Bool = true
    var showConfidenceBadges: Bool = true
    var showAdaptiveMA: Bool = false  // Show adaptive moving average of SuperTrend
    var showSuperTrendAIPanel: Bool = false  // Disabled - SuperTrend now integrated into main chart

    // SuperTrend AI Parameters (LuxAlgo parity)
    var superTrendAIFactorMin: Double = 1.0
    var superTrendAIFactorMax: Double = 5.0
    var superTrendAIFactorStep: Double = 0.5
    var superTrendAIPerfAlpha: Double = 10.0
    var superTrendAIFromCluster: SuperTrendAIClusterSelection = .best
    var superTrendAIMaxIterations: Int = 1_000
    var superTrendAIHistoricalBars: Int = 10_000

    // Support & Resistance Indicators
    var showPivotLevels: Bool = false        // BigBeluga multi-timeframe pivots
    var showPolynomialSR: Bool = false       // Polynomial regression S&R
    var showLogisticSR: Bool = false         // Logistic regression ML S&R

    // Chart Renderer
    var useWebChart: Bool = true             // Use Lightweight Charts (WKWebView) - default for TradingView UX
}
