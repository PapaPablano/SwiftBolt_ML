import Foundation

// MARK: - Backtest date parsing (date-only and datetime strings)

private func parseBacktestDate(_ dateString: String) -> Date? {
    // 1) Date-only: "2024-01-15"
    let dateOnly = ISO8601DateFormatter()
    dateOnly.formatOptions = [.withFullDate, .withDashSeparatorInDate]
    if let d = dateOnly.date(from: dateString) { return d }
    // 2) ISO8601 datetime: "2024-01-15T00:00:00", "2024-01-15T10:30:00Z", "2024-01-15T10:30:00.000Z"
    let iso = ISO8601DateFormatter()
    iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    if let d = iso.date(from: dateString) { return d }
    iso.formatOptions = [.withInternetDateTime]
    if let d = iso.date(from: dateString) { return d }
    // 3) Space-separated: "2024-01-15 10:30:00"
    let space = DateFormatter()
    space.locale = Locale(identifier: "en_US_POSIX")
    space.timeZone = TimeZone(secondsFromGMT: 0)
    space.dateFormat = "yyyy-MM-dd HH:mm:ss"
    if let d = space.date(from: dateString) { return d }
    space.dateFormat = "yyyy-MM-dd"
    return space.date(from: dateString)
}

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
    /// Inline strategy configuration (entry/exit conditions, SL/TP).
    /// Sent as `strategy_config` so the worker evaluates the user's custom conditions.
    let strategyConfig: [String: Any]?

    init(
        symbol: String,
        strategy: String,
        startDate: String,
        endDate: String,
        timeframe: String? = nil,
        initialCapital: Double? = nil,
        params: [String: Any]? = nil,
        strategyConfig: [String: Any]? = nil
    ) {
        self.symbol = symbol
        self.strategy = strategy
        self.startDate = startDate
        self.endDate = endDate
        self.timeframe = timeframe
        self.initialCapital = initialCapital
        self.params = params
        self.strategyConfig = strategyConfig
    }
}

// MARK: - Backtest Job Status (polling state)

enum BacktestJobStatus: String, Equatable {
    case idle
    case pending
    case running
    case completed
    case failed

    init(apiStatus: String) {
        switch apiStatus.lowercased() {
        case "pending", "queued": self = .pending
        case "running", "processing": self = .running
        case "completed", "complete", "success": self = .completed
        case "failed", "error": self = .failed
        default: self = .idle
        }
    }

    var displayLabel: String {
        switch self {
        case .idle: return "Idle"
        case .pending: return "Pending"
        case .running: return "Running…"
        case .completed: return "Completed"
        case .failed: return "Failed"
        }
    }

    var isTerminal: Bool { self == .completed || self == .failed }
    var isPolling: Bool { self == .pending || self == .running }
}

// MARK: - Job Queue Responses (unified backtest API)

struct BacktestJobQueuedResponse: Decodable {
    let jobId: String
    let status: String
    let createdAt: String?

    enum CodingKeys: String, CodingKey {
        case jobId = "job_id"
        case status
        case createdAt = "created_at"
    }
}

struct BacktestJobStatusResponse: Decodable {
    let jobId: String
    let status: String
    let createdAt: String?
    let startedAt: String?
    let completedAt: String?
    let error: String?
    let result: BacktestResultPayload?

    enum CodingKeys: String, CodingKey {
        case jobId = "job_id"
        case status
        case createdAt = "created_at"
        case startedAt = "started_at"
        case completedAt = "completed_at"
        case error
        case result
    }
}

struct BacktestResultPayload: Decodable {
    let metrics: BacktestResultMetrics
    let trades: [BacktestResultTrade]
    let equityCurve: [BacktestResultEquityPoint]
    let validation: BacktestValidation?
    let monthlyReturns: [BacktestMonthlyReturn]?
    let rollingMetrics: [BacktestRollingMetric]?
    let drawdownSeries: [BacktestDrawdownPoint]?

    enum CodingKeys: String, CodingKey {
        case metrics
        case trades
        case equity_curve
        case validation
        case monthly_returns
        case rolling_metrics
        case drawdown_series
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        metrics = try c.decode(BacktestResultMetrics.self, forKey: .metrics)
        trades = try c.decode([BacktestResultTrade].self, forKey: .trades)
        equityCurve = try c.decode([BacktestResultEquityPoint].self, forKey: .equity_curve)
        validation = try c.decodeIfPresent(BacktestValidation.self, forKey: .validation)
        monthlyReturns = try c.decodeIfPresent([BacktestMonthlyReturn].self, forKey: .monthly_returns)
        rollingMetrics = try c.decodeIfPresent([BacktestRollingMetric].self, forKey: .rolling_metrics)
        drawdownSeries = try c.decodeIfPresent([BacktestDrawdownPoint].self, forKey: .drawdown_series)
    }
}

struct BacktestResultMetrics: Decodable {
    let totalTrades: Int
    let totalReturnPct: Double?
    let finalValue: Double?
    let maxDrawdownPct: Double?
    let sharpeRatio: Double?
    let winRate: Double?
    let profitFactor: Double?
    let averageTrade: Double?
    let cagr: Double?

    enum CodingKeys: String, CodingKey {
        case total_trades
        case total_return_pct
        case final_value
        case max_drawdown_pct
        case sharpe_ratio
        case win_rate
        case profit_factor
        case average_trade
        case cagr
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        totalTrades = try c.decode(Int.self, forKey: .total_trades)
        totalReturnPct = try c.decodeIfPresent(Double.self, forKey: .total_return_pct)
        finalValue = try c.decodeIfPresent(Double.self, forKey: .final_value)
        maxDrawdownPct = try c.decodeIfPresent(Double.self, forKey: .max_drawdown_pct)
        sharpeRatio = try c.decodeIfPresent(Double.self, forKey: .sharpe_ratio)
        winRate = try c.decodeIfPresent(Double.self, forKey: .win_rate)
        profitFactor = try c.decodeIfPresent(Double.self, forKey: .profit_factor)
        averageTrade = try c.decodeIfPresent(Double.self, forKey: .average_trade)
        cagr = try c.decodeIfPresent(Double.self, forKey: .cagr)
    }
}

/// Trade from the strategy-backtest-worker.
/// Worker returns: entry_date, exit_date, entry_price, exit_price, direction, close_reason, pnl, quantity, pnl_pct.
struct BacktestResultTrade: Decodable {
    let entryDate: String
    let exitDate: String
    let entryPrice: Double
    let exitPrice: Double
    let direction: String
    let closeReason: String?
    let pnl: Double?
    let quantity: Double?
    let pnlPct: Double?

    enum CodingKeys: String, CodingKey {
        case entryDate = "entry_date"
        case exitDate = "exit_date"
        case entryPrice = "entry_price"
        case exitPrice = "exit_price"
        case direction
        case closeReason = "close_reason"
        case pnl
        case quantity
        case pnlPct = "pnl_pct"
    }
}

struct BacktestResultEquityPoint: Decodable {
    let date: String
    let value: Double

    enum CodingKeys: String, CodingKey {
        case date, value
    }
}

// MARK: - Statistical Validation (mirrors validation.ts output)

struct BacktestConfidenceInterval: Decodable {
    let lower: Double
    let upper: Double
    let confidence: Double
}

struct BacktestConfidenceIntervals: Decodable {
    let sharpeRatio: BacktestConfidenceInterval?
    let maxDrawdownPct: BacktestConfidenceInterval?
    let winRate: BacktestConfidenceInterval?

    enum CodingKeys: String, CodingKey {
        case sharpeRatio = "sharpe_ratio"
        case maxDrawdownPct = "max_drawdown_pct"
        case winRate = "win_rate"
    }
}

struct BacktestSplitMetrics: Decodable {
    let sharpeRatio: Double?
    let totalReturnPct: Double?
    let winRate: Double?
    let totalTrades: Int?
    let maxDrawdownPct: Double?

    enum CodingKeys: String, CodingKey {
        case sharpeRatio = "sharpe_ratio"
        case totalReturnPct = "total_return_pct"
        case winRate = "win_rate"
        case totalTrades = "total_trades"
        case maxDrawdownPct = "max_drawdown_pct"
    }
}

struct BacktestValidation: Decodable {
    let confidenceIntervals: BacktestConfidenceIntervals?
    let pValue: Double?
    let bootstrapIterations: Int?
    let sampleSize: Int?
    let inSample: BacktestSplitMetrics?
    let outOfSample: BacktestSplitMetrics?

    enum CodingKeys: String, CodingKey {
        case confidenceIntervals = "confidence_intervals"
        case pValue = "p_value"
        case bootstrapIterations = "bootstrap_iterations"
        case sampleSize = "sample_size"
        case inSample = "in_sample"
        case outOfSample = "out_of_sample"
    }
}

struct BacktestMonthlyReturn: Decodable, Identifiable {
    var id: String { "\(year)-\(month)" }
    let year: Int
    let month: Int
    let returnPct: Double
    let isPartial: Bool

    enum CodingKeys: String, CodingKey {
        case year, month
        case returnPct = "return_pct"
        case isPartial = "is_partial"
    }
}

struct BacktestRollingMetric: Decodable {
    let date: String
    let sharpe63: Double?
    let winRate63: Double?

    enum CodingKeys: String, CodingKey {
        case date
        case sharpe63 = "sharpe_63"
        case winRate63 = "win_rate_63"
    }
}

struct BacktestDrawdownPoint: Decodable {
    let date: String
    let drawdownPct: Double

    enum CodingKeys: String, CodingKey {
        case date
        case drawdownPct = "drawdown_pct"
    }
}

// MARK: - Backtest Response (display format)

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
        let profitFactor: Double?
        let averageTrade: Double?
        let cagr: Double?
    }
    
    struct EquityPoint: Decodable, Identifiable {
        let id = UUID()
        let date: String
        let value: Double
        
        enum CodingKeys: String, CodingKey {
            case date, value
        }
        
        var dateValue: Date? {
            parseBacktestDate(date)
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
        let entryPrice: Double?
        let exitPrice: Double?
        let duration: Double?
        let fees: Double?

        enum CodingKeys: String, CodingKey {
            case date, symbol, action, quantity, price, pnl
            case entryPrice, exitPrice, duration, fees
        }
        
        var dateValue: Date? {
            parseBacktestDate(date)
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

// MARK: - Convert job result to display format

extension BacktestResponse {
    /// Build BacktestResponse from job result payload (strategy_backtest_results format)
    static func from(
        result: BacktestResultPayload,
        symbol: String,
        strategy: String,
        startDate: String,
        endDate: String,
        initialCapital: Double
    ) -> BacktestResponse {
        let m = result.metrics
        let totalReturn = (m.totalReturnPct ?? 0) / 100.0
        let finalValue = m.finalValue ?? initialCapital * (1 + totalReturn)
        let winRateFraction: Double? = m.winRate.map { $0 / 100.0 }

        return BacktestResponse(
            symbol: symbol,
            strategy: strategy,
            period: BacktestResponse.Period(start: startDate, end: endDate),
            initialCapital: initialCapital,
            finalValue: finalValue,
            totalReturn: totalReturn,
            metrics: BacktestResponse.BacktestMetrics(
                sharpeRatio: m.sharpeRatio,
                maxDrawdown: m.maxDrawdownPct.map { $0 / 100.0 },
                winRate: winRateFraction,
                totalTrades: m.totalTrades,
                profitFactor: m.profitFactor,
                averageTrade: m.averageTrade,
                cagr: m.cagr
            ),
            equityCurve: result.equityCurve.map {
                BacktestResponse.EquityPoint(date: $0.date, value: $0.value)
            },
            trades: result.trades.map {
                BacktestResponse.Trade(
                    date: $0.entryDate,
                    symbol: symbol,
                    action: $0.direction == "short" ? "SELL" : "BUY",
                    quantity: Int($0.quantity ?? 1),
                    price: $0.entryPrice,
                    pnl: $0.pnl,
                    entryPrice: $0.entryPrice,
                    exitPrice: $0.exitPrice,
                    duration: nil,
                    fees: nil
                )
            },
            barsUsed: 0,
            error: nil
        )
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
