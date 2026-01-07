import Foundation

struct ChartDataV2Response: Codable, Equatable {
    let symbol: String
    let timeframe: String
    let layers: ChartLayers
    let metadata: ChartMetadata
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
}
