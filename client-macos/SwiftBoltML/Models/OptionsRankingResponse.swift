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

// MARK: - Option Rank (ML-scored contract)

struct OptionRank: Codable, Identifiable {
    let id: String
    let contractSymbol: String
    let expiry: String
    let strike: Double
    let side: OptionSide
    let mlScore: Double
    let impliedVol: Double?
    let delta: Double?
    let gamma: Double?
    let theta: Double?
    let vega: Double?
    let rho: Double?
    let openInterest: Int?
    let volume: Int?
    let bid: Double?
    let ask: Double?
    let mark: Double?
    let lastPrice: Double?
    let runAt: String

    // Computed properties
    var expiryDate: Date? {
        ISO8601DateFormatter().date(from: expiry)
    }

    var daysToExpiry: Int? {
        guard let expiryDate = expiryDate else { return nil }
        return Calendar.current.dateComponents([.day], from: Date(), to: expiryDate).day
    }

    var scorePercentage: Double {
        mlScore * 100
    }

    var scoreColor: Color {
        if mlScore >= 0.7 {
            return .green
        } else if mlScore >= 0.4 {
            return .orange
        } else {
            return .red
        }
    }

    var scoreLabel: String {
        if mlScore >= 0.7 {
            return "Strong"
        } else if mlScore >= 0.4 {
            return "Moderate"
        } else {
            return "Weak"
        }
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
        mlScore: 0.85,
        impliedVol: 0.32,
        delta: 0.65,
        gamma: 0.03,
        theta: -0.05,
        vega: 0.12,
        rho: 0.08,
        openInterest: 5000,
        volume: 1200,
        bid: 5.20,
        ask: 5.30,
        mark: 5.25,
        lastPrice: 5.28,
        runAt: ISO8601DateFormatter().string(from: Date())
    )
}

import SwiftUI
