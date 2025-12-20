import Foundation

struct ChartResponse: Codable, Equatable {
    let symbol: String
    let assetType: String
    let timeframe: String
    let bars: [OHLCBar]
    let mlSummary: MLSummary?
    let indicators: IndicatorData?

    enum CodingKeys: String, CodingKey {
        case symbol
        case assetType = "assetType"
        case timeframe
        case bars
        case mlSummary
        case indicators
    }
}

/// Pre-computed indicator data from backend (optional)
struct IndicatorData: Codable, Equatable {
    // SuperTrend AI results
    let supertrendFactor: Double?
    let supertrendPerformance: Double?
    let supertrendSignal: Int?  // 1 = bullish, -1 = bearish

    // Trend analysis
    let trendLabel: String?  // bullish, neutral, bearish
    let trendConfidence: Double?

    // Key indicator values (latest)
    let rsi: Double?
    let adx: Double?
    let macdHistogram: Double?
    let kdjJ: Double?

    enum CodingKeys: String, CodingKey {
        case supertrendFactor = "supertrend_factor"
        case supertrendPerformance = "supertrend_performance"
        case supertrendSignal = "supertrend_signal"
        case trendLabel = "trend_label"
        case trendConfidence = "trend_confidence"
        case rsi
        case adx
        case macdHistogram = "macd_histogram"
        case kdjJ = "kdj_j"
    }
}

struct MLSummary: Codable, Equatable {
    let overallLabel: String
    let confidence: Double
    let horizons: [ForecastSeries]
}

struct ForecastSeries: Codable, Equatable {
    let horizon: String
    let points: [ForecastPoint]
}

struct ForecastPoint: Codable, Equatable {
    let ts: Int
    let value: Double
    let lower: Double
    let upper: Double
}
