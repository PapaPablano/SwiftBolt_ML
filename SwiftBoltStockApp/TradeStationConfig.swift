import Foundation

enum TradeStationEnvironment {
    case live
    case sim
    
    var apiBaseURL: String {
        switch self {
        case .live:
            return "https://api.tradestation.com/v3"
        case .sim:
            return "https://sim-api.tradestation.com/v3"
        }
    }
}

struct TradeStationConfig {
    // From TradeStation developer portal
    static let clientID: String = "<YOUR_CLIENT_ID>"
    static let clientSecret: String = "<YOUR_CLIENT_SECRET>"
    
    // Must exactly match the callback URL registered in the portal
    static let redirectURI: String = "swiftbolt://oauth/callback"
    
    // Scopes you actually need
    static let scope: String = "openid offline_access profile MarketData ReadAccount Trade"
    
    // Use this to toggle SIM vs LIVE
    static var environment: TradeStationEnvironment = .sim
    
    // Guard rail to prevent connecting to live accounts in dev environment
    static let allowLiveTrading: Bool = false
}