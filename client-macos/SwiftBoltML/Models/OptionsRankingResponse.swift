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
    let compositeRank: Double

    // Momentum Framework component scores (0-100)
    let momentumScore: Double?
    let valueScore: Double?
    let greeksScore: Double?

    // Legacy field (derived from compositeRank/100 for backwards compat)
    let mlScore: Double?

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
        Int(compositeRank)
    }

    var compositeColor: Color {
        if compositeRank >= 70 {
            return .green
        } else if compositeRank >= 50 {
            return .orange
        } else {
            return .red
        }
    }

    var scoreLabel: String {
        if compositeRank >= 75 {
            return "Strong Buy"
        } else if compositeRank >= 60 {
            return "Buy"
        } else if compositeRank >= 45 {
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
