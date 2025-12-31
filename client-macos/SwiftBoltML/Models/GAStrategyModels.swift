import Foundation
import SwiftUI

// MARK: - GA Strategy Response

struct GAStrategyResponse: Codable {
    let symbol: String
    let hasStrategy: Bool
    let strategy: GAStrategy?
    let recommendation: GARecommendation?
}

// MARK: - GA Strategy

struct GAStrategy: Codable, Identifiable {
    let id: String
    let genes: StrategyGenes
    let fitness: StrategyFitness
    let createdAt: String
    let trainingDays: Int
    let trainingSamples: Int
    let generationsRun: Int

    var createdDate: Date? {
        ISO8601DateFormatter().date(from: createdAt)
    }

    var ageDescription: String {
        guard let date = createdDate else { return "Unknown" }
        let days = Calendar.current.dateComponents([.day], from: date, to: Date()).day ?? 0
        if days == 0 {
            return "Today"
        } else if days == 1 {
            return "Yesterday"
        } else {
            return "\(days) days ago"
        }
    }
}

// MARK: - Strategy Genes (GA-Optimized Parameters)

struct StrategyGenes: Codable {
    // Ranking thresholds
    let minCompositeRank: Double
    let minMomentumScore: Double
    let minValueScore: Double
    let signalFilter: String  // "buy", "discount", "runner", "greeks", "any"

    // Entry timing
    let entryHourMin: Int
    let entryHourMax: Int
    let minBarAgeMinutes: Int

    // Greeks thresholds
    let deltaExit: Double
    let gammaExit: Double
    let vegaExit: Double
    let thetaMin: Double
    let ivRankMin: Double
    let ivRankMax: Double

    // Hold timing
    let minHoldMinutes: Int
    let maxHoldMinutes: Int
    let profitTargetPct: Double
    let stopLossPct: Double

    // Position sizing
    let positionSizePct: Double
    let maxConcurrentTrades: Int

    // Trade frequency
    let minTradesPerDay: Int
    let maxTradesPerSymbol: Int

    // Computed properties for display
    var signalFilterDisplay: String {
        signalFilter.uppercased()
    }

    var entryHoursDisplay: String {
        "\(entryHourMin):00 - \(entryHourMax):00 EST"
    }

    var ivRankRangeDisplay: String {
        "\(Int(ivRankMin))-\(Int(ivRankMax))"
    }

    var profitTargetDisplay: String {
        "+\(String(format: "%.1f", profitTargetPct))%"
    }

    var stopLossDisplay: String {
        "\(String(format: "%.1f", stopLossPct))%"
    }

    var holdTimeDisplay: String {
        "\(minHoldMinutes)-\(maxHoldMinutes) min"
    }
}

// MARK: - Strategy Fitness (Backtest Results)

struct StrategyFitness: Codable {
    let totalPnl: Double
    let pnlPct: Double
    let winRate: Double
    let profitFactor: Double
    let sharpeRatio: Double
    let maxDrawdown: Double
    let numTrades: Int
    let avgTradeDuration: Int
    let tradesClosed: Int

    // Computed properties for display
    var winRateDisplay: String {
        "\(String(format: "%.1f", winRate * 100))%"
    }

    var profitFactorDisplay: String {
        String(format: "%.2f", profitFactor)
    }

    var sharpeDisplay: String {
        String(format: "%.2f", sharpeRatio)
    }

    var maxDrawdownDisplay: String {
        "\(String(format: "%.1f", maxDrawdown * 100))%"
    }

    var avgDurationDisplay: String {
        if avgTradeDuration < 60 {
            return "\(avgTradeDuration) min"
        } else {
            return String(format: "%.1f hrs", Double(avgTradeDuration) / 60.0)
        }
    }

    // Quality assessment
    var qualityScore: Int {
        var score = 0

        // Win rate contribution (0-30)
        score += Int(min(winRate, 0.70) / 0.70 * 30)

        // Profit factor contribution (0-30)
        score += Int(min(profitFactor, 2.5) / 2.5 * 30)

        // Sharpe contribution (0-20)
        score += Int(min(max(sharpeRatio, 0), 2.0) / 2.0 * 20)

        // Drawdown penalty (0-20)
        score += Int((1.0 - min(maxDrawdown, 0.30) / 0.30) * 20)

        return min(score, 100)
    }

    var qualityLabel: String {
        if qualityScore >= 80 { return "Excellent" }
        if qualityScore >= 65 { return "Good" }
        if qualityScore >= 50 { return "Fair" }
        return "Poor"
    }

    var qualityColor: Color {
        if qualityScore >= 80 { return .green }
        if qualityScore >= 65 { return .blue }
        if qualityScore >= 50 { return .orange }
        return .red
    }
}

// MARK: - GA Recommendation

struct GARecommendation: Codable {
    let entryConditions: [String]
    let exitConditions: [String]
    let riskManagement: [String]
}

// MARK: - Trigger Optimization Response

struct TriggerOptimizationResponse: Codable {
    let success: Bool
    let message: String
    let runId: String?
    let estimatedMinutes: Int?
}

// MARK: - Filter Options Based on GA Strategy

extension OptionRank {
    /// Check if this option passes GA strategy entry filters
    func passesGAFilters(_ genes: StrategyGenes) -> Bool {
        // Check composite rank
        guard effectiveCompositeRank >= genes.minCompositeRank else { return false }

        // Check component scores if available
        if let momentum = momentumScore, momentum < genes.minMomentumScore * 100 {
            return false
        }
        if let value = valueScore, value < genes.minValueScore * 100 {
            return false
        }

        // Check signal filter
        if genes.signalFilter != "any" {
            switch genes.signalFilter {
            case "buy": if signalBuy != true { return false }
            case "discount": if signalDiscount != true { return false }
            case "runner": if signalRunner != true { return false }
            case "greeks": if signalGreeks != true { return false }
            default: break
            }
        }

        // Check IV rank
        if let ivr = ivRank {
            if ivr < genes.ivRankMin || ivr > genes.ivRankMax {
                return false
            }
        }

        // Check theta
        if let t = theta, t < genes.thetaMin {
            return false
        }

        return true
    }

    /// GA confidence score based on how well it matches optimized criteria
    func gaConfidence(_ genes: StrategyGenes) -> Double {
        var score = 0.0
        var factors = 0.0

        // Rank factor
        let rankRatio = effectiveCompositeRank / max(genes.minCompositeRank, 1)
        score += min(rankRatio, 1.5)
        factors += 1.0

        // IV Rank factor (closer to middle of range = better)
        if let ivr = ivRank {
            let mid = (genes.ivRankMin + genes.ivRankMax) / 2
            let distance = abs(ivr - mid) / ((genes.ivRankMax - genes.ivRankMin) / 2)
            score += max(0, 1.0 - distance)
            factors += 1.0
        }

        // Signal bonus
        if signalBuy == true { score += 0.2 }
        if signalDiscount == true { score += 0.15 }
        if signalRunner == true { score += 0.1 }
        if signalGreeks == true { score += 0.1 }

        return factors > 0 ? (score / factors) : 0.5
    }
}

// MARK: - Preview Examples

extension GAStrategy {
    static let example = GAStrategy(
        id: UUID().uuidString,
        genes: StrategyGenes.example,
        fitness: StrategyFitness.example,
        createdAt: ISO8601DateFormatter().string(from: Date()),
        trainingDays: 30,
        trainingSamples: 1500,
        generationsRun: 50
    )
}

extension StrategyGenes {
    static let example = StrategyGenes(
        minCompositeRank: 72.5,
        minMomentumScore: 0.55,
        minValueScore: 0.45,
        signalFilter: "discount",
        entryHourMin: 10,
        entryHourMax: 14,
        minBarAgeMinutes: 15,
        deltaExit: 0.25,
        gammaExit: 0.06,
        vegaExit: 0.04,
        thetaMin: -0.15,
        ivRankMin: 25,
        ivRankMax: 70,
        minHoldMinutes: 20,
        maxHoldMinutes: 180,
        profitTargetPct: 18.5,
        stopLossPct: -6.5,
        positionSizePct: 2.5,
        maxConcurrentTrades: 3,
        minTradesPerDay: 2,
        maxTradesPerSymbol: 5
    )
}

extension StrategyFitness {
    static let example = StrategyFitness(
        totalPnl: 15420.0,
        pnlPct: 15.42,
        winRate: 0.58,
        profitFactor: 1.85,
        sharpeRatio: 1.12,
        maxDrawdown: 0.12,
        numTrades: 45,
        avgTradeDuration: 95,
        tradesClosed: 42
    )
}

extension GARecommendation {
    static let example = GARecommendation(
        entryConditions: [
            "Require composite rank ≥ 73",
            "Trade only between 10:00 - 14:00 EST",
            "Filter for DISCOUNT signal only",
            "IV Rank between 25-70"
        ],
        exitConditions: [
            "Take profit at +18.5%",
            "Stop loss at -6.5%",
            "Exit if |delta| < 0.25",
            "Max hold time: 180 minutes"
        ],
        riskManagement: [
            "Position size: 2.5% per trade",
            "Max 3 concurrent positions",
            "Max 5 trades per symbol"
        ]
    )
}
