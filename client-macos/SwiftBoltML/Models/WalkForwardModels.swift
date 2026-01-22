import Foundation

// MARK: - Walk-Forward Request

struct WalkForwardRequest {
    let symbol: String
    let horizon: String
    let forecaster: String?
    let timeframe: String?
    let windows: WindowConfig?
    
    struct WindowConfig {
        let trainWindow: Int?
        let testWindow: Int?
        let stepSize: Int?
    }
}

// MARK: - Walk-Forward Response

struct WalkForwardResponse: Decodable {
    let symbol: String
    let horizon: String
    let forecaster: String
    let timeframe: String
    let period: Period
    let windows: Windows
    let metrics: WalkForwardMetrics
    let barsUsed: Int
    let error: String?
    
    struct Period: Decodable {
        let start: String
        let end: String
    }
    
    struct Windows: Decodable {
        let trainWindow: Int
        let testWindow: Int
        let stepSize: Int
        let testPeriods: Int
    }
    
    struct WalkForwardMetrics: Decodable {
        let accuracy: Double
        let precision: Double
        let recall: Double
        let f1Score: Double
        let sharpeRatio: Double
        let sortinoRatio: Double
        let maxDrawdown: Double
        let winRate: Double
        let profitFactor: Double
        let totalTrades: Int
        let winningTrades: Int
        let losingTrades: Int
        let avgWinSize: Double
        let avgLossSize: Double
    }
}

// MARK: - Forecaster Type

enum ForecasterType: String, CaseIterable {
    case baseline = "baseline"
    case enhanced = "enhanced"
    
    var displayName: String {
        switch self {
        case .baseline: return "Baseline"
        case .enhanced: return "Enhanced"
        }
    }
    
    var description: String {
        switch self {
        case .baseline: return "Simple moving average baseline"
        case .enhanced: return "Enhanced with technical indicators"
        }
    }
    
    var icon: String {
        switch self {
        case .baseline: return "chart.line.uptrend.xyaxis"
        case .enhanced: return "sparkles"
        }
    }
}

// MARK: - Forecast Horizon

enum ForecastHorizon: String, CaseIterable {
    case oneDay = "1D"
    case oneWeek = "1W"
    case oneMonth = "1M"
    case twoMonths = "2M"
    case threeMonths = "3M"
    case fourMonths = "4M"
    case fiveMonths = "5M"
    case sixMonths = "6M"
    
    var displayName: String {
        switch self {
        case .oneDay: return "1 Day"
        case .oneWeek: return "1 Week"
        case .oneMonth: return "1 Month"
        case .twoMonths: return "2 Months"
        case .threeMonths: return "3 Months"
        case .fourMonths: return "4 Months"
        case .fiveMonths: return "5 Months"
        case .sixMonths: return "6 Months"
        }
    }
}
