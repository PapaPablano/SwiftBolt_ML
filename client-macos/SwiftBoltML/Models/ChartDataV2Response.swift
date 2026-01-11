import Foundation

struct ChartDataV2Response: Codable, Equatable {
    let symbol: String
    let timeframe: String
    let layers: ChartLayers
    let metadata: ChartMetadata
    let dataQuality: DataQuality?
    let mlSummary: MLSummary?
    let indicators: IndicatorData?
    let superTrendAI: SuperTrendAIData?
}

struct ChartLayers: Codable, Equatable {
    let historical: LayerData
    let intraday: LayerData
    let forecast: LayerData
}

struct LayerData: Codable, Equatable {
    let count: Int
    let provider: String
    let data: [OHLCBar]
    let oldestBar: String?
    let newestBar: String?
}

struct ChartMetadata: Codable, Equatable {
    let totalBars: Int
    let startDate: String
    let endDate: String
    
    enum CodingKeys: String, CodingKey {
        case totalBars = "total_bars"
        case startDate = "start_date"
        case endDate = "end_date"
    }
}

struct DataQuality: Codable, Equatable {
    let dataAgeHours: Int?
    let isStale: Bool
    let hasRecentData: Bool
    let historicalDepthDays: Int
    let sufficientForML: Bool
    let barCount: Int
    
    var statusDescription: String {
        if isStale {
            return "⚠️ Data is stale (> 24 hours old)"
        } else if hasRecentData {
            return "✅ Fresh data (< 4 hours old)"
        } else {
            return "🔄 Recent data (< 24 hours old)"
        }
    }
    
    var mlTrainingStatus: String {
        if sufficientForML {
            return "✅ Sufficient for ML (\(barCount) bars)"
        } else {
            return "⚠️ Insufficient for ML (need 250+ bars, have \(barCount))"
        }
    }
}

extension ChartDataV2Response {
    var allBars: [OHLCBar] {
        layers.historical.data + layers.intraday.data
    }
    
    var allBarsWithForecast: [OHLCBar] {
        layers.historical.data + layers.intraday.data + layers.forecast.data
    }
    
    var hasIntraday: Bool {
        layers.intraday.count > 0
    }
    
    var hasForecast: Bool {
        layers.forecast.count > 0
    }
    
    var isDataFresh: Bool {
        dataQuality?.hasRecentData ?? false
    }
    
    var isDataStale: Bool {
        dataQuality?.isStale ?? true
    }
    
    var dataAgeDescription: String {
        guard let ageHours = dataQuality?.dataAgeHours else {
            return "Unknown age"
        }
        if ageHours < 1 {
            return "< 1 hour old"
        } else if ageHours < 24 {
            return "\(ageHours) hours old"
        } else {
            let days = ageHours / 24
            return "\(days) days old"
        }
    }
}
