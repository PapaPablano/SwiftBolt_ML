import Foundation

struct QuotesResponse: Decodable {
    let success: Bool
    let marketState: String
    let marketDescription: String?
    let timestamp: String
    let count: Int
    let quotes: [QuoteData]

    enum CodingKeys: String, CodingKey {
        case success
        case marketState = "market_state"
        case marketDescription = "market_description"
        case timestamp
        case count
        case quotes
    }
}

struct QuoteData: Decodable, Equatable {
    let symbol: String
    let last: Double
    let bid: Double
    let ask: Double
    let open: Double
    let high: Double
    let low: Double
    let close: Double
    let volume: Double
    let change: Double
    let changePercentage: Double
    let averageVolume: Double
    let week52High: Double
    let week52Low: Double
    let lastTradeTime: String

    enum CodingKeys: String, CodingKey {
        case symbol
        case last
        case bid
        case ask
        case open
        case high
        case low
        case close
        case volume
        case change
        case changePercentage = "change_percentage"
        case averageVolume = "average_volume"
        case week52High = "week_52_high"
        case week52Low = "week_52_low"
        case lastTradeTime = "last_trade_time"
    }
}

struct LiveQuote: Equatable {
    let symbol: String
    let last: Double
    let change: Double
    let changePercent: Double
    let timestamp: Date

    var isPositive: Bool { change >= 0 }
}
