import Foundation

struct UnifiedValidator: Codable {
    let symbol: String
    let backtestScore: Double
    let walkforwardScore: Double
    let liveScore: Double
    let m15Signal: Signal
    let h1Signal: Signal
    let d1Signal: Signal
    let timestamp: Date
    let weights: ValidationWeights

    enum CodingKeys: String, CodingKey {
        case symbol
        case backtestScore = "backtest_score"
        case walkforwardScore = "walkforward_score"
        case liveScore = "live_score"
        case m15Signal = "m15_signal"
        case h1Signal = "h1_signal"
        case d1Signal = "d1_signal"
        case timestamp
        case weights
    }

    init(
        symbol: String,
        backtestScore: Double,
        walkforwardScore: Double,
        liveScore: Double,
        m15Signal: Signal,
        h1Signal: Signal,
        d1Signal: Signal,
        timestamp: Date,
        weights: ValidationWeights
    ) {
        self.symbol = symbol
        self.backtestScore = backtestScore
        self.walkforwardScore = walkforwardScore
        self.liveScore = liveScore
        self.m15Signal = m15Signal
        self.h1Signal = h1Signal
        self.d1Signal = d1Signal
        self.timestamp = timestamp
        self.weights = weights
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        symbol = try container.decode(String.self, forKey: .symbol)
        backtestScore = try container.decode(Double.self, forKey: .backtestScore)
        walkforwardScore = try container.decode(Double.self, forKey: .walkforwardScore)
        liveScore = try container.decode(Double.self, forKey: .liveScore)
        m15Signal = try container.decode(Signal.self, forKey: .m15Signal)
        h1Signal = try container.decode(Signal.self, forKey: .h1Signal)
        d1Signal = try container.decode(Signal.self, forKey: .d1Signal)
        let epochMillis = try container.decode(Double.self, forKey: .timestamp)
        timestamp = Date(timeIntervalSince1970: epochMillis / 1_000)
        weights = try container.decodeIfPresent(ValidationWeights.self, forKey: .weights) ?? .load()
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(symbol, forKey: .symbol)
        try container.encode(backtestScore, forKey: .backtestScore)
        try container.encode(walkforwardScore, forKey: .walkforwardScore)
        try container.encode(liveScore, forKey: .liveScore)
        try container.encode(m15Signal, forKey: .m15Signal)
        try container.encode(h1Signal, forKey: .h1Signal)
        try container.encode(d1Signal, forKey: .d1Signal)
        try container.encode(timestamp.timeIntervalSince1970 * 1_000, forKey: .timestamp)
        try container.encode(weights, forKey: .weights)
    }

    var confidence: Double {
        (backtestScore * weights.backtest) +
        (walkforwardScore * weights.walkforward) +
        (liveScore * weights.live)
    }

    var hasDrift: Bool {
        abs(liveScore - backtestScore) > weights.driftThreshold
    }

    var timeframeConsensus: Signal {
        reconcileTimeframes()
    }

    var lastUpdatedAgo: String {
        let interval = Date().timeIntervalSince(timestamp)
        if interval < 60 {
            return "Just now"
        } else if interval < 3600 {
            return "\(Int(interval / 60)) min ago"
        } else if interval < 86400 {
            return "\(Int(interval / 3600)) hour ago"
        } else {
            return "\(Int(interval / 86400)) day ago"
        }
    }

    func updatingWeights(_ newWeights: ValidationWeights) -> UnifiedValidator {
        UnifiedValidator(
            symbol: symbol,
            backtestScore: backtestScore,
            walkforwardScore: walkforwardScore,
            liveScore: liveScore,
            m15Signal: m15Signal,
            h1Signal: h1Signal,
            d1Signal: d1Signal,
            timestamp: timestamp,
            weights: newWeights
        )
    }

    private func reconcileTimeframes() -> Signal {
        switch weights.timeframeWeight {
        case .durationBased:
            let weighted = (d1Signal.bullishValue * 0.5) +
                           (h1Signal.bullishValue * 0.3) +
                           (m15Signal.bullishValue * 0.2)
            if weighted > 0.5 { return .bullish }
            if weighted < -0.5 { return .bearish }
            return .neutral
        case .equal:
            let bullishVotes = [m15Signal, h1Signal, d1Signal].filter { $0 == .bullish }.count
            let bearishVotes = [m15Signal, h1Signal, d1Signal].filter { $0 == .bearish }.count
            if bullishVotes >= 2 { return .bullish }
            if bearishVotes >= 2 { return .bearish }
            return .neutral
        case .recentPerformance:
            switch liveScore {
            case let score where score > 0.7:
                return m15Signal
            case let score where score > 0.5:
                return h1Signal
            default:
                return d1Signal
            }
        }
    }
}

enum Signal: String, Codable, CaseIterable {
    case bullish = "BULLISH"
    case bearish = "BEARISH"
    case neutral = "NEUTRAL"

    var bullishValue: Double {
        switch self {
        case .bullish: return 1.0
        case .neutral: return 0.0
        case .bearish: return -1.0
        }
    }
}

struct ValidationWeights: Codable, Equatable {
    var backtest: Double
    var walkforward: Double
    var live: Double
    var driftThreshold: Double
    var timeframeWeight: TimeframeWeight

    static let `default` = ValidationWeights(
        backtest: 0.40,
        walkforward: 0.35,
        live: 0.25,
        driftThreshold: 0.15,
        timeframeWeight: .durationBased
    )

    enum TimeframeWeight: String, Codable, CaseIterable, Identifiable {
        case durationBased
        case recentPerformance
        case equal

        var id: String { rawValue }

        var label: String {
            switch self {
            case .durationBased: return "Favor Higher Timeframes"
            case .recentPerformance: return "Favor Recent Performance"
            case .equal: return "Equal Weight"
            }
        }
    }

    func save() {
        do {
            let data = try JSONEncoder().encode(self)
            UserDefaults.standard.set(data, forKey: Self.storageKey)
        } catch {
            print("[ValidationWeights] Failed to save weights: \(error)")
        }
    }

    static func load() -> ValidationWeights {
        guard let data = UserDefaults.standard.data(forKey: storageKey) else {
            return .default
        }
        do {
            return try JSONDecoder().decode(ValidationWeights.self, from: data)
        } catch {
            print("[ValidationWeights] Failed to load weights: \(error)")
            return .default
        }
    }

    private static let storageKey = "validationWeights"
}
