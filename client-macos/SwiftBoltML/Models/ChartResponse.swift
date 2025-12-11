import Foundation

struct ChartResponse: Codable, Equatable {
    let symbol: String
    let assetType: String
    let timeframe: String
    let bars: [OHLCBar]

    enum CodingKeys: String, CodingKey {
        case symbol
        case assetType = "assetType"
        case timeframe
        case bars
    }
}
