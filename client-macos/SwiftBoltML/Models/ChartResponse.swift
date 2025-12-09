import Foundation

struct ChartResponse: Codable {
    let symbol: String
    let assetType: String
    let timeframe: String
    let bars: [OHLCBar]

    enum CodingKeys: String, CodingKey {
        case symbol
        case assetType = "asset_type"
        case timeframe
        case bars
    }
}
