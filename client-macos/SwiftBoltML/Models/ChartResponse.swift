import Foundation

struct ChartResponse: Codable, Equatable {
    let symbol: String
    let assetType: String
    let timeframe: String
    let bars: [OHLCBar]
    let mlSummary: MLSummary?

    enum CodingKeys: String, CodingKey {
        case symbol
        case assetType = "assetType"
        case timeframe
        case bars
        case mlSummary
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
