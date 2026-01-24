import Foundation

// MARK: - Portfolio Optimization Request

struct PortfolioOptimizeRequest {
    let symbols: [String]
    let method: OptimizationMethod
    let timeframe: String?
    let lookbackDays: Int?
    let riskFreeRate: Double?
    let targetReturn: Double?
    let minWeight: Double?
    let maxWeight: Double?
}

// MARK: - Portfolio Optimization Response

struct PortfolioOptimizeResponse: Decodable {
    let symbols: [String]
    let method: String
    let timeframe: String
    let lookbackDays: Int
    let allocation: PortfolioAllocation
    let parameters: OptimizationParameters
    let error: String?
    
    struct PortfolioAllocation: Decodable {
        let weights: [String: Double]
        let expectedReturn: Double
        let volatility: Double
        let sharpeRatio: Double
    }
    
    struct OptimizationParameters: Decodable {
        let riskFreeRate: Double
        let minWeight: Double
        let maxWeight: Double
        let targetReturn: Double?
    }
}

// MARK: - Optimization Method

enum OptimizationMethod: String, CaseIterable {
    case maxSharpe = "max_sharpe"
    case minVariance = "min_variance"
    case riskParity = "risk_parity"
    case efficient = "efficient"
    
    var displayName: String {
        switch self {
        case .maxSharpe: return "Max Sharpe Ratio"
        case .minVariance: return "Min Variance"
        case .riskParity: return "Risk Parity"
        case .efficient: return "Efficient (Target Return)"
        }
    }
    
    var description: String {
        switch self {
        case .maxSharpe: return "Maximize risk-adjusted returns"
        case .minVariance: return "Minimize portfolio volatility"
        case .riskParity: return "Equal risk contribution from each asset"
        case .efficient: return "Optimize for target return with minimum variance"
        }
    }
    
    var icon: String {
        switch self {
        case .maxSharpe: return "chart.line.uptrend.xyaxis"
        case .minVariance: return "shield"
        case .riskParity: return "equal.circle"
        case .efficient: return "target"
        }
    }
}
