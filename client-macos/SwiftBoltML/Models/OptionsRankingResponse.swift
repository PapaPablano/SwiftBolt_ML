import Foundation
import SwiftUI

// MARK: - Options Rankings Response

struct OptionsRankingsResponse: Codable {
    let symbol: String
    let totalRanks: Int
    let ranks: [OptionRank]
    let filters: RankingFilters
}

struct RankingFilters: Codable {
    let expiry: String?
    let side: OptionSide?

    enum CodingKeys: String, CodingKey {
        case expiry
        case side
    }
}

enum OptionSide: String, Codable {
    case call
    case put
}

// MARK: - Option Rank (Momentum Framework scored contract)

struct OptionRank: Codable, Identifiable {
    let id: String
    let contractSymbol: String
    let expiry: String
    let strike: Double
    let side: OptionSide

    // Primary score: Momentum Framework composite rank (0-100)
    // Optional for backwards compatibility with old records that only have mlScore
    let compositeRank: Double?

    // Momentum Framework component scores (0-100)
    let momentumScore: Double?
    let valueScore: Double?
    let greeksScore: Double?

    // Legacy field (ml_score from old ranking system, 0-1 scale)
    let mlScore: Double?

    // Effective composite rank with fallback to mlScore * 100
    var effectiveCompositeRank: Double {
        if let rank = compositeRank {
            return rank
        } else if let score = mlScore {
            return score * 100  // Convert 0-1 scale to 0-100
        }
        return 0
    }

    // IV Metrics
    let impliedVol: Double?
    let ivRank: Double?
    let spreadPct: Double?

    // Greeks
    let delta: Double?
    let gamma: Double?
    let theta: Double?
    let vega: Double?
    let rho: Double?

    // Volume/Liquidity
    let openInterest: Int?
    let volume: Int?
    let volOiRatio: Double?
    let liquidityConfidence: Double?

    // Pricing
    let bid: Double?
    let ask: Double?
    let mark: Double?
    let lastPrice: Double?

    // Signals
    let signalDiscount: Bool?
    let signalRunner: Bool?
    let signalGreeks: Bool?
    let signalBuy: Bool?
    let signals: String?

    let runAt: String

    // Computed properties
    var expiryDate: Date? {
        ISO8601DateFormatter().date(from: expiry)
    }

    var daysToExpiry: Int? {
        guard let expiryDate = expiryDate else { return nil }
        return Calendar.current.dateComponents([.day], from: Date(), to: expiryDate).day
    }

    // Composite score display (0-100 scale)
    var compositeScoreDisplay: Int {
        Int(effectiveCompositeRank)
    }

    var compositeColor: Color {
        if effectiveCompositeRank >= 70 {
            return .green
        } else if effectiveCompositeRank >= 50 {
            return .orange
        } else {
            return .red
        }
    }

    var scoreLabel: String {
        if effectiveCompositeRank >= 75 {
            return "Strong Buy"
        } else if effectiveCompositeRank >= 60 {
            return "Buy"
        } else if effectiveCompositeRank >= 45 {
            return "Hold"
        } else {
            return "Weak"
        }
    }

    // Active signals as array
    var activeSignals: [String] {
        var result: [String] = []
        if signalBuy == true { result.append("BUY") }
        if signalDiscount == true { result.append("DISCOUNT") }
        if signalRunner == true { result.append("RUNNER") }
        if signalGreeks == true { result.append("GREEKS") }
        return result
    }

    var hasSignals: Bool {
        !activeSignals.isEmpty
    }
    
    // Liquidity confidence indicator
    var liquidityLabel: String {
        guard let conf = liquidityConfidence else { return "N/A" }
        if conf >= 0.8 { return "High" }
        if conf >= 0.5 { return "Medium" }
        if conf >= 0.3 { return "Low" }
        return "Very Low"
    }
    
    var liquidityColor: Color {
        guard let conf = liquidityConfidence else { return .gray }
        if conf >= 0.8 { return .green }
        if conf >= 0.5 { return .orange }
        return .red
    }
    
    var isLowLiquidity: Bool {
        (liquidityConfidence ?? 1.0) < 0.5
    }

    var derivedMark: Double? {
        if let bid, let ask {
            return (bid + ask) / 2
        }
        return mark ?? lastPrice
    }

    var spread: Double? {
        guard let bid, let ask else { return nil }
        return ask - bid
    }

    var spreadPctComputed: Double? {
        guard let spread, let mid = derivedMark, mid > 0 else { return nil }
        return spread / mid
    }

    var spreadPctDisplay: Double? {
        if let sp = spreadPct { return sp }
        guard let frac = spreadPctComputed else { return nil }
        return frac * 100
    }

    var liquidityScore: Double? {
        guard let sp = spreadPctComputed else { return nil }
        return 1.0 / (1.0 + sp)
    }

    var runAtDate: Date? {
        let isoFormatter = ISO8601DateFormatter()
        isoFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = isoFormatter.date(from: runAt) {
            return date
        }
        isoFormatter.formatOptions = [.withInternetDateTime]
        return isoFormatter.date(from: runAt)
    }

    var markAgeSeconds: TimeInterval? {
        guard let date = runAtDate else { return nil }
        return Date().timeIntervalSince(date)
    }

    var markAgeLabel: String {
        guard let seconds = markAgeSeconds, seconds >= 0 else { return "—" }
        if seconds < 60 {
            return "\(Int(seconds))s"
        }
        let minutes = Int(seconds / 60)
        if minutes < 60 {
            return "\(minutes)m"
        }
        let hours = Int(seconds / 3600)
        if hours < 24 {
            return "\(hours)h"
        }
        let days = Int(seconds / 86400)
        return "\(days)d"
    }
}

// Extension for easy preview/testing
extension OptionRank {
    static let example = OptionRank(
        id: UUID().uuidString,
        contractSymbol: "AAPL240119C00150000",
        expiry: "2024-01-19",
        strike: 150.0,
        side: .call,
        compositeRank: 78.5,
        momentumScore: 82.0,
        valueScore: 75.0,
        greeksScore: 80.0,
        mlScore: 0.785,
        impliedVol: 0.32,
        ivRank: 45.0,
        spreadPct: 1.5,
        delta: 0.65,
        gamma: 0.03,
        theta: -0.05,
        vega: 0.12,
        rho: 0.08,
        openInterest: 5000,
        volume: 1200,
        volOiRatio: 0.24,
        liquidityConfidence: 0.85,
        bid: 5.20,
        ask: 5.30,
        mark: 5.25,
        lastPrice: 5.28,
        signalDiscount: true,
        signalRunner: false,
        signalGreeks: true,
        signalBuy: true,
        signals: "DISCOUNT,GREEKS,BUY",
        runAt: ISO8601DateFormatter().string(from: Date())
    )
}
