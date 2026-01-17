import Foundation
import SwiftUI

// MARK: - Options Rankings Response

struct OptionsRankingsResponse: Codable {
    let symbol: String
    let totalRanks: Int
    let ranks: [OptionRank]
    let filters: RankingFilters
}

struct OptionsQuotesResponse: Codable {
    let symbol: String
    let timestamp: String
    let chainTimestamp: String
    let totalRequested: Int
    let totalReturned: Int
    let quotes: [OptionContractQuote]

    enum CodingKeys: String, CodingKey {
        case symbol
        case timestamp
        case chainTimestamp = "chain_timestamp"
        case totalRequested = "total_requested"
        case totalReturned = "total_returned"
        case quotes
    }
}

struct OptionContractQuote: Codable {
    let contractSymbol: String
    let bid: Double?
    let ask: Double?
    let mark: Double?
    let last: Double?
    let volume: Double?
    let openInterest: Double?
    let impliedVol: Double?
    let updatedAt: String

    enum CodingKeys: String, CodingKey {
        case contractSymbol = "contract_symbol"
        case bid
        case ask
        case mark
        case last
        case volume
        case openInterest = "open_interest"
        case impliedVol = "implied_vol"
        case updatedAt = "updated_at"
    }
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
    let priceProvider: String?
    let oiProvider: String?
    let historySamples: Int?
    let historyAvgMark: Double?
    let historyWindowDays: Int?

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

    // 7-Day Underlying Metrics (from options ranking enhancement)
    let underlying7dReturn: Double?
    let underlying7dVolatility: Double?
    let underlying7dDrawdown: Double?
    let underlying7dGapCount: Int?

    let runAt: String

    enum CodingKeys: String, CodingKey {
        case id
        case contractSymbol = "contract_symbol"
        case expiry
        case strike
        case side
        case compositeRank = "composite_rank"
        case momentumScore = "momentum_score"
        case valueScore = "value_score"
        case greeksScore = "greeks_score"
        case mlScore = "ml_score"
        case impliedVol = "implied_vol"
        case ivRank = "iv_rank"
        case spreadPct = "spread_pct"
        case delta
        case gamma
        case theta
        case vega
        case rho
        case openInterest = "open_interest"
        case volume
        case volOiRatio = "vol_oi_ratio"
        case liquidityConfidence = "liquidity_confidence"
        case priceProvider = "price_provider"
        case oiProvider = "oi_provider"
        case historySamples = "history_samples"
        case historyAvgMark = "history_avg_mark"
        case historyWindowDays = "history_window_days"
        case bid
        case ask
        case mark
        case lastPrice = "last_price"
        case signalDiscount = "signal_discount"
        case signalRunner = "signal_runner"
        case signalGreeks = "signal_greeks"
        case signalBuy = "signal_buy"
        case signals
        case underlying7dReturn = "underlying_ret_7d"
        case underlying7dVolatility = "underlying_vol_7d"
        case underlying7dDrawdown = "underlying_drawdown_7d"
        case underlying7dGapCount = "underlying_gap_count"
        case runAt = "run_at"
    }

    // Computed properties
    var expiryDate: Date? {
        if let isoDate = ISO8601DateFormatter().date(from: expiry) {
            return isoDate
        }

        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.date(from: expiry)
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

    var historyCoverageLabel: String? {
        guard let samples = historySamples, samples > 0 else { return nil }
        if let window = historyWindowDays {
            return "\(samples) samples / \(window)d"
        }
        return "\(samples) samples"
    }

    // MARK: - 7-Day Underlying Metrics Helpers

    var has7DayMetrics: Bool {
        underlying7dReturn != nil || underlying7dVolatility != nil
    }

    var underlying7dReturnFormatted: String {
        guard let ret = underlying7dReturn else { return "N/A" }
        return String(format: "%+.1f%%", ret)
    }

    var underlying7dVolatilityFormatted: String {
        guard let vol = underlying7dVolatility else { return "N/A" }
        return String(format: "%.1f%%", vol)
    }

    var underlying7dDrawdownFormatted: String {
        guard let dd = underlying7dDrawdown else { return "N/A" }
        return String(format: "%.1f%%", abs(dd))
    }

    var underlying7dReturnColor: Color {
        guard let ret = underlying7dReturn else { return .gray }
        if ret > 5.0 { return .green }
        if ret > 0.0 { return .green.opacity(0.7) }
        if ret > -5.0 { return .orange }
        return .red
    }

    var underlying7dVolatilityColor: Color {
        guard let vol = underlying7dVolatility else { return .gray }
        if vol < 20.0 { return .green }
        if vol < 35.0 { return .orange }
        return .red
    }

    var underlying7dDrawdownColor: Color {
        guard let dd = underlying7dDrawdown else { return .gray }
        let absDd = abs(dd)
        if absDd < 3.0 { return .green }
        if absDd < 7.0 { return .orange }
        return .red
    }

    var underlying7dGapCountColor: Color {
        guard let gaps = underlying7dGapCount else { return .gray }
        if gaps <= 1 { return .green }
        if gaps <= 3 { return .orange }
        return .red
    }

    var underlyingMomentumLabel: String {
        guard let ret = underlying7dReturn else { return "Unknown" }
        if ret > 5.0 { return "Strong" }
        if ret > 0.0 { return "Positive" }
        if ret > -5.0 { return "Weak" }
        return "Negative"
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
        priceProvider: "alpaca",
        oiProvider: "tradier",
        historySamples: 30,
        historyAvgMark: 5.1,
        historyWindowDays: 30,
        bid: 5.20,
        ask: 5.30,
        mark: 5.25,
        lastPrice: 5.28,
        signalDiscount: true,
        signalRunner: false,
        signalGreeks: true,
        signalBuy: true,
        signals: "DISCOUNT,GREEKS,BUY",
        underlying7dReturn: 3.5,
        underlying7dVolatility: 25.0,
        underlying7dDrawdown: -2.1,
        underlying7dGapCount: 1,
        runAt: ISO8601DateFormatter().string(from: Date())
    )
}
