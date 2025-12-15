import Foundation

enum OptionType: String, Codable {
    case call
    case put
}

struct OptionContract: Codable, Identifiable {
    let id: String
    let symbol: String
    let underlying: String
    let strike: Double
    let expiration: TimeInterval
    let type: OptionType

    // Pricing
    let bid: Double
    let ask: Double
    let last: Double
    let mark: Double

    // Volume & Open Interest
    let volume: Double
    let openInterest: Double

    // Greeks
    let delta: Double?
    let gamma: Double?
    let theta: Double?
    let vega: Double?
    let rho: Double?

    // Implied Volatility
    let impliedVolatility: Double?

    // Additional data
    let lastTradeTime: TimeInterval?
    let changePercent: Double?
    let change: Double?

    enum CodingKeys: String, CodingKey {
        case symbol, underlying, strike, expiration, type
        case bid, ask, last, mark
        case volume, openInterest
        case delta, gamma, theta, vega, rho
        case impliedVolatility, lastTradeTime
        case changePercent, change
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        self.symbol = try container.decode(String.self, forKey: .symbol)
        self.id = symbol // Use symbol as ID
        self.underlying = try container.decode(String.self, forKey: .underlying)
        self.strike = try container.decode(Double.self, forKey: .strike)
        self.expiration = try container.decode(TimeInterval.self, forKey: .expiration)
        self.type = try container.decode(OptionType.self, forKey: .type)

        self.bid = try container.decode(Double.self, forKey: .bid)
        self.ask = try container.decode(Double.self, forKey: .ask)
        self.last = try container.decode(Double.self, forKey: .last)
        self.mark = try container.decode(Double.self, forKey: .mark)

        self.volume = try container.decode(Double.self, forKey: .volume)
        self.openInterest = try container.decode(Double.self, forKey: .openInterest)

        self.delta = try container.decodeIfPresent(Double.self, forKey: .delta)
        self.gamma = try container.decodeIfPresent(Double.self, forKey: .gamma)
        self.theta = try container.decodeIfPresent(Double.self, forKey: .theta)
        self.vega = try container.decodeIfPresent(Double.self, forKey: .vega)
        self.rho = try container.decodeIfPresent(Double.self, forKey: .rho)

        self.impliedVolatility = try container.decodeIfPresent(Double.self, forKey: .impliedVolatility)
        self.lastTradeTime = try container.decodeIfPresent(TimeInterval.self, forKey: .lastTradeTime)
        self.changePercent = try container.decodeIfPresent(Double.self, forKey: .changePercent)
        self.change = try container.decodeIfPresent(Double.self, forKey: .change)
    }

    var expirationDate: Date {
        Date(timeIntervalSince1970: expiration)
    }

    var lastTradeDate: Date? {
        guard let lastTradeTime = lastTradeTime else { return nil }
        return Date(timeIntervalSince1970: lastTradeTime / 1000) // Convert from milliseconds
    }

    var isInTheMoney: Bool {
        // Would need underlying price to determine this accurately
        // For now, this is a placeholder
        false
    }
}
