import Foundation

/// Technical indicators calculator for OHLC bar data
/// Supports SMA, EMA, RSI, and other common indicators
struct TechnicalIndicators {

    // MARK: - Simple Moving Average (SMA)

    /// Calculate Simple Moving Average
    /// - Parameters:
    ///   - data: Array of values (typically close prices)
    ///   - period: Number of periods for the average
    /// - Returns: Array of SMA values (nil for insufficient data points)
    static func sma(_ data: [Double], period: Int) -> [Double?] {
        guard period > 0, data.count >= period else {
            return Array(repeating: nil, count: data.count)
        }

        var result: [Double?] = Array(repeating: nil, count: period - 1)

        for i in (period - 1)..<data.count {
            let slice = data[(i - period + 1)...i]
            let average = slice.reduce(0, +) / Double(period)
            result.append(average)
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

    /// Calculate Bollinger Bands
    /// - Parameters:
    ///   - data: Array of values (typically close prices)
    ///   - period: SMA period (typically 20)
    ///   - stdDevMultiplier: Standard deviation multiplier (typically 2)
    /// - Returns: Bollinger Bands (upper, middle, lower)
    static func bollingerBands(_ data: [Double], period: Int, stdDevMultiplier: Double = 2.0) -> BollingerBands {
        let middle = sma(data, period: period)
        var upper: [Double?] = []
        var lower: [Double?] = []

        for i in 0..<data.count {
            guard let smaValue = middle[i], i >= period - 1 else {
                upper.append(nil)
                lower.append(nil)
                continue
            }

            // Calculate standard deviation for the period
            let slice = data[(i - period + 1)...i]
            let variance = slice.map { pow($0 - smaValue, 2) }.reduce(0, +) / Double(period)
            let stdDev = sqrt(variance)

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
    /// - Parameters:
    ///   - bars: OHLC bars
    ///   - period: Lookback period for RSV (typically 9)
    ///   - kSmooth: Smoothing period for K (typically 3)
    ///   - dSmooth: Smoothing period for D (typically 3)
    /// - Returns: KDJResult with K, D, and J lines
    static func kdj(
        bars: [OHLCBar],
        period: Int = 9,
        kSmooth: Int = 3,
        dSmooth: Int = 3
    ) -> KDJResult {
        // Calculate RSV (Raw Stochastic Value)
        var rsvValues: [Double?] = []

        for i in 0..<bars.count {
            if i < period - 1 {
                rsvValues.append(nil)
            } else {
                let periodBars = Array(bars[(i - period + 1)...i])
                let highestHigh = periodBars.map(\.high).max() ?? 0
                let lowestLow = periodBars.map(\.low).min() ?? 0
                let close = bars[i].close

                let range = highestHigh - lowestLow
                let rsv = range == 0 ? 50 : ((close - lowestLow) / range) * 100
                rsvValues.append(rsv)
            }
        }

        // K = SMA of RSV
        let rsvFiltered = rsvValues.compactMap { $0 }
        let kSMA = sma(rsvFiltered, period: kSmooth)

        var kValues: [Double?] = []
        var kIdx = 0
        for rsv in rsvValues {
            if rsv != nil {
                kValues.append(kIdx < kSMA.count ? kSMA[kIdx] : nil)
                kIdx += 1
            } else {
                kValues.append(nil)
            }
        }

        // D = SMA of K
        let kFiltered = kValues.compactMap { $0 }
        let dSMA = sma(kFiltered, period: dSmooth)

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

        // J = 3*K - 2*D
        var jValues: [Double?] = []
        for i in 0..<kValues.count {
            if let k = kValues[i], let d = dValues[i] {
                jValues.append(3 * k - 2 * d)
            } else {
                jValues.append(nil)
            }
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

        // Smooth with EMA
        let plusDIEMA = ema(plusDM, period: period)
        let minusDIEMA = ema(minusDM, period: period)
        let trEMA = ema(tr, period: period)

        var plusDI: [Double?] = []
        var minusDI: [Double?] = []
        var dx: [Double] = []

        for i in 0..<bars.count {
            if let pdi = plusDIEMA[i], let mdi = minusDIEMA[i], let atr = trEMA[i], atr > 0 {
                let pdiVal = (pdi / atr) * 100
                let mdiVal = (mdi / atr) * 100
                plusDI.append(pdiVal)
                minusDI.append(mdiVal)

                let sum = pdiVal + mdiVal
                if sum > 0 {
                    dx.append(abs(pdiVal - mdiVal) / sum * 100)
                }
            } else {
                plusDI.append(nil)
                minusDI.append(nil)
            }
        }

        // ADX = SMA of DX
        let adxSMA = sma(dx, period: period)

        // Align ADX with original data
        var adxValues: [Double?] = Array(repeating: nil, count: bars.count - dx.count)
        for val in adxSMA {
            adxValues.append(val)
        }

        // Pad to match length
        while adxValues.count < bars.count {
            adxValues.append(nil)
        }

        return ADXResult(adx: adxValues, plusDI: plusDI, minusDI: minusDI)
    }

    // MARK: - SuperTrend

    struct SuperTrendResult {
        let supertrend: [Double?]  // SuperTrend line
        let trend: [Int]           // 1 = bullish, -1 = bearish, 0 = neutral
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
                trend: Array(repeating: 0, count: bars.count)
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

        // ATR using EMA
        let atrEMA = ema(tr, period: period)

        var supertrend: [Double?] = []
        var trend: [Int] = []
        var finalUpper: [Double] = []
        var finalLower: [Double] = []

        for i in 0..<bars.count {
            let hl2 = (bars[i].high + bars[i].low) / 2

            guard let atr = atrEMA[i] else {
                supertrend.append(nil)
                trend.append(0)
                finalUpper.append(hl2)
                finalLower.append(hl2)
                continue
            }

            let upperBand = hl2 + multiplier * atr
            let lowerBand = hl2 - multiplier * atr

            if i == 0 {
                finalUpper.append(upperBand)
                finalLower.append(lowerBand)
                trend.append(1)
                supertrend.append(lowerBand)
            } else {
                // Adjust bands based on previous values
                let prevClose = bars[i - 1].close
                let newUpper = upperBand < finalUpper[i - 1] || prevClose > finalUpper[i - 1]
                    ? upperBand : finalUpper[i - 1]
                let newLower = lowerBand > finalLower[i - 1] || prevClose < finalLower[i - 1]
                    ? lowerBand : finalLower[i - 1]

                finalUpper.append(newUpper)
                finalLower.append(newLower)

                // Determine trend
                let close = bars[i].close
                if close > newUpper {
                    trend.append(1)
                } else if close < newLower {
                    trend.append(-1)
                } else {
                    trend.append(trend[i - 1])
                }

                supertrend.append(trend[i] == 1 ? newLower : newUpper)
            }
        }

        return SuperTrendResult(supertrend: supertrend, trend: trend)
    }

    // MARK: - ATR (Average True Range)

    /// Calculate Average True Range
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

        return sma(tr, period: period)
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

struct IndicatorConfig {
    // Moving Averages
    var showSMA20: Bool = false
    var showSMA50: Bool = false
    var showSMA200: Bool = false
    var showEMA9: Bool = false
    var showEMA21: Bool = false

    // Volume
    var showVolume: Bool = true

    // Oscillators
    var showRSI: Bool = false
    var showMACD: Bool = false
    var showStochastic: Bool = false
    var showKDJ: Bool = false

    // Volatility/Trend
    var showBollingerBands: Bool = false
    var showADX: Bool = false
    var showSuperTrend: Bool = false
    var showATR: Bool = false

    // SuperTrend AI Enhanced Options
    var showTrendZones: Bool = true
    var showSignalMarkers: Bool = true
    var showConfidenceBadges: Bool = true
}
