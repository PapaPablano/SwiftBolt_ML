import Foundation

// MARK: - Greeks Surface Request

struct GreeksSurfaceRequest: Codable {
    let symbol: String
    let underlyingPrice: Double
    let riskFreeRate: Double?
    let volatility: Double
    let optionType: String?
    let strikeRange: [Double]?
    let timeRange: [Double]?
    let nStrikes: Int?
    let nTimes: Int?
    let greek: String?
    
    init(
        symbol: String,
        underlyingPrice: Double,
        riskFreeRate: Double = 0.05,
        volatility: Double,
        optionType: String = "call",
        strikeRange: [Double]? = nil,
        timeRange: [Double]? = nil,
        nStrikes: Int = 50,
        nTimes: Int = 50,
        greek: String? = nil
    ) {
        self.symbol = symbol
        self.underlyingPrice = underlyingPrice
        self.riskFreeRate = riskFreeRate
        self.volatility = volatility
        self.optionType = optionType
        self.strikeRange = strikeRange
        self.timeRange = timeRange
        self.nStrikes = nStrikes
        self.nTimes = nTimes
        self.greek = greek
    }
}

// MARK: - Greeks Surface Response

struct GreeksSurfaceResponse: Codable {
    let symbol: String
    let underlyingPrice: Double
    let riskFreeRate: Double
    let volatility: Double
    let optionType: String
    let strikes: [Double]
    let times: [Double]
    let delta: [[Double]]
    let gamma: [[Double]]
    let theta: [[Double]]
    let vega: [[Double]]
    let rho: [[Double]]
}

// MARK: - Greeks Surface Data Point

struct GreeksSurfacePoint {
    let strike: Double
    let timeToMaturity: Double
    let delta: Double
    let gamma: Double
    let theta: Double
    let vega: Double
    let rho: Double
}
