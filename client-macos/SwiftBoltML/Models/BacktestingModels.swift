import Foundation

// MARK: - Backtest Request

// BacktestRequest is not Encodable directly due to [String: Any] params
// Use JSONSerialization in APIClient instead
struct BacktestRequest {
    let symbol: String
    let strategy: String
    let startDate: String
    let endDate: String
    let timeframe: String?
    let initialCapital: Double?
    let params: [String: Any]?
}

// MARK: - Backtest Response

struct BacktestResponse: Decodable {
    let symbol: String
    let strategy: String
    let period: Period
    let initialCapital: Double
    let finalValue: Double
    let totalReturn: Double
    let metrics: BacktestMetrics
    let equityCurve: [EquityPoint]
    let trades: [Trade]
    let barsUsed: Int
    let error: String?
    
    struct Period: Decodable {
        let start: String
        let end: String
    }
    
    struct BacktestMetrics: Decodable {
        let sharpeRatio: Double?
        let maxDrawdown: Double?
        let winRate: Double?
        let totalTrades: Int
    }
    
    struct EquityPoint: Decodable, Identifiable {
        let id = UUID()
        let date: String
        let value: Double
        
        enum CodingKeys: String, CodingKey {
            case date, value
        }
        
        var dateValue: Date? {
            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withFullDate, .withDashSeparatorInDate]
            return formatter.date(from: date)
        }
    }
    
    struct Trade: Decodable, Identifiable {
        let id = UUID()
        let date: String
        let symbol: String
        let action: String
        let quantity: Int
        let price: Double
        let pnl: Double?
        
        enum CodingKeys: String, CodingKey {
            case date, symbol, action, quantity, price, pnl
        }
        
        var dateValue: Date? {
            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withFullDate, .withDashSeparatorInDate]
            return formatter.date(from: date)
        }
        
        var isBuy: Bool {
            action.uppercased() == "BUY"
        }
        
        var isSell: Bool {
            action.uppercased() == "SELL"
        }
        
        var formattedAction: String {
            isBuy ? "Buy" : "Sell"
        }
        
        var formattedPnl: String {
            if let pnl = pnl {
                let sign = pnl >= 0 ? "+" : ""
                return "\(sign)\(String(format: "%.2f", pnl))"
            }
            return "—"
        }
    }
}

// MARK: - Trading Strategy

enum TradingStrategy: String, CaseIterable {
    case supertrendAI = "supertrend_ai"
    case smaCrossover = "sma_crossover"
    case buyAndHold = "buy_and_hold"
    
    var displayName: String {
        switch self {
        case .supertrendAI: return "SuperTrend AI"
        case .smaCrossover: return "SMA Crossover"
        case .buyAndHold: return "Buy & Hold"
        }
    }
    
    var description: String {
        switch self {
        case .supertrendAI: return "Adaptive SuperTrend with ML-optimized factor selection"
        case .smaCrossover: return "Simple moving average crossover (fast/slow)"
        case .buyAndHold: return "Buy and hold baseline strategy"
        }
    }
    
    var icon: String {
        switch self {
        case .supertrendAI: return "sparkles"
        case .smaCrossover: return "arrow.left.arrow.right"
        case .buyAndHold: return "chart.line.uptrend.xyaxis"
        }
    }
    
    var defaultParams: [String: Any] {
        switch self {
        case .supertrendAI:
            return [
                "atr_length": 10,
                "min_mult": 1.0,
                "max_mult": 5.0,
                "step": 0.5
            ]
        case .smaCrossover:
            return [
                "fast_period": 20,
                "slow_period": 50
            ]
        case .buyAndHold:
            return [:]
        }
    }
}
