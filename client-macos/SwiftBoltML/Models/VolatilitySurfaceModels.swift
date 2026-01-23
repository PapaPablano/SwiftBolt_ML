import Foundation

// MARK: - Volatility Surface Slice

struct VolatilitySurfaceSlice: Codable {
    let maturityDays: Double
    let strikes: [Double]
    let impliedVols: [Double]
    let forwardPrice: Double?
    
    init(
        maturityDays: Double,
        strikes: [Double],
        impliedVols: [Double],
        forwardPrice: Double? = nil
    ) {
        self.maturityDays = maturityDays
        self.strikes = strikes
        self.impliedVols = impliedVols
        self.forwardPrice = forwardPrice
    }
}

// MARK: - Volatility Surface Request

struct VolatilitySurfaceRequest: Codable {
    let symbol: String
    let slices: [VolatilitySurfaceSlice]
    let nStrikes: Int?
    let nMaturities: Int?
    
    init(
        symbol: String,
        slices: [VolatilitySurfaceSlice],
        nStrikes: Int = 50,
        nMaturities: Int = 30
    ) {
        self.symbol = symbol
        self.slices = slices
        self.nStrikes = nStrikes
        self.nMaturities = nMaturities
    }
}

// MARK: - Volatility Surface Response

struct VolatilitySurfaceResponse: Codable {
    let symbol: String
    let strikes: [Double]
    let maturities: [Double]
    let impliedVols: [[Double]]
    let strikeRange: [Double]
    let maturityRange: [Double]
}
