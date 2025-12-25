import Foundation

struct ChartResponse: Codable, Equatable {
    let symbol: String
    let assetType: String
    let timeframe: String
    let bars: [OHLCBar]
    let mlSummary: MLSummary?
    let indicators: IndicatorData?
    let superTrendAI: SuperTrendAIData?

    enum CodingKeys: String, CodingKey {
        case symbol
        case assetType = "assetType"
        case timeframe
        case bars
        case mlSummary
        case indicators
        case superTrendAI = "supertrend_ai"
    }
}

// MARK: - SuperTrend AI Data

/// Full SuperTrend AI data from backend with signals and metadata
struct SuperTrendAIData: Codable, Equatable {
    let factor: Double
    let performanceIndex: Double
    let signalStrength: Int  // 0-10
    let currentTrend: String  // "BULLISH" or "BEARISH"
    let currentStopLevel: Double
    let trendDurationBars: Int
    let signals: [SignalMetadata]

    enum CodingKeys: String, CodingKey {
        case factor
        case performanceIndex = "performance_index"
        case signalStrength = "signal_strength"
        case currentTrend = "current_trend"
        case currentStopLevel = "current_stop_level"
        case trendDurationBars = "trend_duration_bars"
        case signals
    }
}

/// Metadata for individual SuperTrend signals
struct SignalMetadata: Codable, Equatable, Identifiable {
    var id: String { "\(date)-\(type)" }

    let date: String
    let type: String  // "BUY" or "SELL"
    let price: Double
    let confidence: Int  // 0-10
    let stopLevel: Double
    let targetPrice: Double
    let atrAtSignal: Double

    enum CodingKeys: String, CodingKey {
        case date
        case type
        case price
        case confidence
        case stopLevel = "stop_level"
        case targetPrice = "target_price"
        case atrAtSignal = "atr_at_signal"
    }
}

// MARK: - Indicator Data

/// Pre-computed indicator data from backend (optional)
struct IndicatorData: Codable, Equatable {
    // SuperTrend AI results (legacy - use SuperTrendAIData for full data)
    let supertrendFactor: Double?
    let supertrendPerformance: Double?
    let supertrendSignal: Int?  // 1 = bullish, -1 = bearish

    // Trend analysis
    let trendLabel: String?  // bullish, neutral, bearish
    let trendConfidence: Int?
    let stopLevel: Double?
    let trendDurationBars: Int?

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
        case stopLevel = "stop_level"
        case trendDurationBars = "trend_duration_bars"
        case rsi
        case adx
        case macdHistogram = "macd_histogram"
        case kdjJ = "kdj_j"
    }
}

struct MLSummary: Codable, Equatable {
    let overallLabel: String?
    let confidence: Double
    let horizons: [ForecastSeries]
    let srLevels: SRLevels?
    let srDensity: Int?

    enum CodingKeys: String, CodingKey {
        case overallLabel = "overall_label"
        case confidence
        case horizons
        case srLevels = "sr_levels"
        case srDensity = "sr_density"
    }
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
