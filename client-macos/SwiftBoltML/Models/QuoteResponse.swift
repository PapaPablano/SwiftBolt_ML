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
    let lastTradeTime: Date

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

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        symbol = try container.decode(String.self, forKey: .symbol)
        last = try container.decode(Double.self, forKey: .last)
        bid = try container.decode(Double.self, forKey: .bid)
        ask = try container.decode(Double.self, forKey: .ask)
        open = try container.decode(Double.self, forKey: .open)
        high = try container.decode(Double.self, forKey: .high)
        low = try container.decode(Double.self, forKey: .low)
        close = try container.decode(Double.self, forKey: .close)
        volume = try container.decode(Double.self, forKey: .volume)
        change = try container.decode(Double.self, forKey: .change)
        changePercentage = try container.decode(Double.self, forKey: .changePercentage)
        averageVolume = try container.decode(Double.self, forKey: .averageVolume)
        week52High = try container.decode(Double.self, forKey: .week52High)
        week52Low = try container.decode(Double.self, forKey: .week52Low)

        // Handle last_trade_time as either number (ms timestamp) or string
        if let timestamp = try? container.decode(Double.self, forKey: .lastTradeTime) {
            lastTradeTime = Date(timeIntervalSince1970: timestamp / 1000)
        } else if let dateString = try? container.decode(String.self, forKey: .lastTradeTime) {
            let formatter = ISO8601DateFormatter()
            lastTradeTime = formatter.date(from: dateString) ?? Date()
        } else {
            lastTradeTime = Date()
        }
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
