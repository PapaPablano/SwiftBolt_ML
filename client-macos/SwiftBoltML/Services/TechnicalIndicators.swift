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
    var showSMA20: Bool = false
    var showSMA50: Bool = false
    var showSMA200: Bool = false
    var showEMA9: Bool = false
    var showEMA21: Bool = false
    var showRSI: Bool = false
    var showVolume: Bool = true
    var showBollingerBands: Bool = false
}
