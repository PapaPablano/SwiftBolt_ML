import Foundation

// MARK: - ML Dashboard Response

struct MLDashboardResponse: Decodable {
    let overview: DashboardOverview
    let recentForecasts: [ForecastSummary]
    let symbolPerformance: [SymbolPerformance]
    let featureStats: [FeatureStats]
    let confidenceDistribution: ConfidenceDistribution

    enum CodingKeys: String, CodingKey {
        case overview
        case recentForecasts = "recentForecasts"
        case symbolPerformance = "symbolPerformance"
        case featureStats = "featureStats"
        case confidenceDistribution = "confidenceDistribution"
    }
}

// MARK: - Dashboard Overview

struct DashboardOverview: Decodable {
    let totalForecasts: Int
    let totalSymbols: Int
    let signalDistribution: SignalDistribution
    let avgConfidence: Double
    let lastUpdated: String

    enum CodingKeys: String, CodingKey {
        case totalForecasts = "totalForecasts"
        case totalSymbols = "totalSymbols"
        case signalDistribution = "signalDistribution"
        case avgConfidence = "avgConfidence"
        case lastUpdated = "lastUpdated"
    }

    var lastUpdatedDate: Date? {
        ISO8601DateFormatter().date(from: lastUpdated)
    }
}

// MARK: - Signal Distribution

struct SignalDistribution: Decodable {
    let bullish: Int
    let neutral: Int
    let bearish: Int
    let total: Int

    var bullishPct: Double {
        total > 0 ? Double(bullish) / Double(total) : 0
    }

    var neutralPct: Double {
        total > 0 ? Double(neutral) / Double(total) : 0
    }

    var bearishPct: Double {
        total > 0 ? Double(bearish) / Double(total) : 0
    }
}

// MARK: - Forecast Summary

struct ForecastSummary: Decodable, Identifiable {
    let symbol: String
    let ticker: String
    let label: String
    let confidence: Double
    let runAt: String
    let horizon: String

    var id: String { "\(symbol)-\(horizon)-\(runAt)" }

    var runAtDate: Date? {
        ISO8601DateFormatter().date(from: runAt)
    }

    var labelColor: String {
        switch label.lowercased() {
        case "bullish": return "green"
        case "bearish": return "red"
        default: return "orange"
        }
    }
}

// MARK: - Symbol Performance

struct SymbolPerformance: Decodable, Identifiable {
    let symbol: String
    let ticker: String
    let totalForecasts: Int
    let avgConfidence: Double
    let signalDistribution: SymbolSignalDistribution
    let lastUpdated: String

    var id: String { symbol }

    var lastUpdatedDate: Date? {
        ISO8601DateFormatter().date(from: lastUpdated)
    }

    var dominantSignal: String {
        let dist = signalDistribution
        if dist.bullish > dist.bearish && dist.bullish > dist.neutral {
            return "Bullish"
        } else if dist.bearish > dist.bullish && dist.bearish > dist.neutral {
            return "Bearish"
        }
        return "Neutral"
    }
}

struct SymbolSignalDistribution: Decodable {
    let bullish: Int
    let neutral: Int
    let bearish: Int
}

// MARK: - Feature Stats

struct FeatureStats: Decodable, Identifiable {
    let name: String
    let avgValue: Double?
    let importance: Double
    let category: String

    var id: String { name }

    var displayName: String {
        switch name {
        case "rsi_14": return "RSI (14)"
        case "macd_hist": return "MACD Histogram"
        case "adx": return "ADX"
        case "supertrend_trend": return "SuperTrend"
        case "kdj_j": return "KDJ-J"
        case "mfi": return "MFI"
        case "bb_width": return "Bollinger Width"
        case "atr_14": return "ATR (14)"
        case "volume_ratio": return "Volume Ratio"
        default: return name.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }

    var categoryColor: String {
        switch category.lowercased() {
        case "momentum": return "purple"
        case "trend": return "blue"
        case "volume": return "green"
        case "volatility": return "orange"
        default: return "gray"
        }
    }

    var importancePct: Int {
        Int(importance * 100)
    }
}

// MARK: - Confidence Distribution

struct ConfidenceDistribution: Decodable {
    let high: Int
    let medium: Int
    let low: Int

    var total: Int { high + medium + low }

    var highPct: Double {
        total > 0 ? Double(high) / Double(total) : 0
    }

    var mediumPct: Double {
        total > 0 ? Double(medium) / Double(total) : 0
    }

    var lowPct: Double {
        total > 0 ? Double(low) / Double(total) : 0
    }
}
