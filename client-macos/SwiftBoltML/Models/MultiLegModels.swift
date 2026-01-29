import Foundation
import SwiftUI

// MARK: - Strategy Types

enum StrategyType: String, Codable, CaseIterable {
    // Single-leg strategies
    case longCall = "long_call"
    case longPut = "long_put"
    case shortCall = "short_call"
    case shortPut = "short_put"
    case coveredCall = "covered_call"
    case cashSecuredPut = "cash_secured_put"
    // Multi-leg strategies
    case bullCallSpread = "bull_call_spread"
    case bearCallSpread = "bear_call_spread"
    case bullPutSpread = "bull_put_spread"
    case bearPutSpread = "bear_put_spread"
    case longStraddle = "long_straddle"
    case shortStraddle = "short_straddle"
    case longStrangle = "long_strangle"
    case shortStrangle = "short_strangle"
    case ironCondor = "iron_condor"
    case ironButterfly = "iron_butterfly"
    case callRatioBackspread = "call_ratio_backspread"
    case putRatioBackspread = "put_ratio_backspread"
    case calendarSpread = "calendar_spread"
    case diagonalSpread = "diagonal_spread"
    case butterflySpread = "butterfly_spread"
    case custom = "custom"

    var displayName: String {
        switch self {
        // Single-leg
        case .longCall: return "Long Call"
        case .longPut: return "Long Put"
        case .shortCall: return "Short Call (Naked)"
        case .shortPut: return "Short Put (Naked)"
        case .coveredCall: return "Covered Call"
        case .cashSecuredPut: return "Cash Secured Put"
        // Multi-leg
        case .bullCallSpread: return "Bull Call Spread"
        case .bearCallSpread: return "Bear Call Spread"
        case .bullPutSpread: return "Bull Put Spread"
        case .bearPutSpread: return "Bear Put Spread"
        case .longStraddle: return "Long Straddle"
        case .shortStraddle: return "Short Straddle"
        case .longStrangle: return "Long Strangle"
        case .shortStrangle: return "Short Strangle"
        case .ironCondor: return "Iron Condor"
        case .ironButterfly: return "Iron Butterfly"
        case .callRatioBackspread: return "Call Ratio Backspread"
        case .putRatioBackspread: return "Put Ratio Backspread"
        case .calendarSpread: return "Calendar Spread"
        case .diagonalSpread: return "Diagonal Spread"
        case .butterflySpread: return "Butterfly Spread"
        case .custom: return "Custom Strategy"
        }
    }

    var expectedLegCount: Int? {
        switch self {
        // Single-leg strategies
        case .longCall, .longPut, .shortCall, .shortPut, .coveredCall, .cashSecuredPut:
            return 1
        // Two-leg strategies
        case .bullCallSpread, .bearCallSpread, .bullPutSpread, .bearPutSpread,
             .longStraddle, .shortStraddle, .longStrangle, .shortStrangle,
             .calendarSpread, .diagonalSpread:
            return 2
        // Three-leg strategies
        case .callRatioBackspread, .putRatioBackspread, .butterflySpread:
            return 3
        // Four-leg strategies
        case .ironCondor, .ironButterfly:
            return 4
        case .custom:
            return nil
        }
    }

    var isSingleLeg: Bool {
        switch self {
        case .longCall, .longPut, .shortCall, .shortPut, .coveredCall, .cashSecuredPut:
            return true
        default:
            return false
        }
    }

    var isBullish: Bool {
        switch self {
        case .longCall, .cashSecuredPut, .bullCallSpread, .bullPutSpread, .longStraddle, .longStrangle, .callRatioBackspread:
            return true
        default:
            return false
        }
    }

    var isBearish: Bool {
        switch self {
        case .longPut, .bearCallSpread, .bearPutSpread, .putRatioBackspread:
            return true
        default:
            return false
        }
    }

    var isNeutral: Bool {
        switch self {
        case .shortStraddle, .shortStrangle, .ironCondor, .ironButterfly, .butterflySpread, .coveredCall:
            return true
        default:
            return false
        }
    }

    /// Default position type for single-leg strategies
    var defaultPositionType: PositionType? {
        switch self {
        case .longCall, .longPut: return .long
        case .shortCall, .shortPut, .coveredCall, .cashSecuredPut: return .short
        default: return nil
        }
    }

    /// Default option type for single-leg strategies
    var defaultOptionType: MultiLegOptionType? {
        switch self {
        case .longCall, .shortCall, .coveredCall: return .call
        case .longPut, .shortPut, .cashSecuredPut: return .put
        default: return nil
        }
    }
}

enum StrategyStatus: String, Codable {
    case open
    case closed
    case expired
    case rolled

    var displayName: String {
        rawValue.capitalized
    }

    var color: Color {
        switch self {
        case .open: return .green
        case .closed: return .gray
        case .expired: return .orange
        case .rolled: return .blue
        }
    }
}

enum PositionType: String, Codable {
    case long
    case short

    var multiplier: Double {
        self == .long ? 1.0 : -1.0
    }
}

enum MultiLegOptionType: String, Codable {
    case call
    case put
}

enum LegRole: String, Codable {
    case primaryLeg = "primary_leg"
    case hedgeLeg = "hedge_leg"
    case upsideLeg = "upside_leg"
    case downsideLeg = "downside_leg"
    case incomeLeg = "income_leg"
    case protectionLeg = "protection_leg"
    case speculationLeg = "speculation_leg"
}

enum ForecastAlignment: String, Codable {
    case bullish
    case neutral
    case bearish
}

// MARK: - Alert Types

enum MultiLegAlertType: String, Codable {
    case expirationSoon = "expiration_soon"
    case strikeBreached = "strike_breached"
    case forecastFlip = "forecast_flip"
    case assignmentRisk = "assignment_risk"
    case profitTargetHit = "profit_target_hit"
    case stopLossHit = "stop_loss_hit"
    case vegaSqueeze = "vega_squeeze"
    case thetaDecayBenefit = "theta_decay_benefit"
    case volatilitySpike = "volatility_spike"
    case gammaRisk = "gamma_risk"
    case legClosed = "leg_closed"
    case strategyAutoAdjusted = "strategy_auto_adjusted"
    case custom = "custom"

    var displayName: String {
        switch self {
        case .expirationSoon: return "Expiration Soon"
        case .strikeBreached: return "Strike Breached"
        case .forecastFlip: return "Forecast Flip"
        case .assignmentRisk: return "Assignment Risk"
        case .profitTargetHit: return "Profit Target Hit"
        case .stopLossHit: return "Stop Loss Hit"
        case .vegaSqueeze: return "Vega Squeeze"
        case .thetaDecayBenefit: return "Theta Benefit"
        case .volatilitySpike: return "Volatility Spike"
        case .gammaRisk: return "Gamma Risk"
        case .legClosed: return "Leg Closed"
        case .strategyAutoAdjusted: return "Auto-Adjusted"
        case .custom: return "Custom"
        }
    }

    var icon: String {
        switch self {
        case .expirationSoon: return "clock.badge.exclamationmark"
        case .strikeBreached: return "arrow.up.arrow.down"
        case .forecastFlip: return "arrow.triangle.swap"
        case .assignmentRisk: return "exclamationmark.triangle"
        case .profitTargetHit: return "target"
        case .stopLossHit: return "xmark.octagon"
        case .vegaSqueeze: return "waveform.path.ecg"
        case .thetaDecayBenefit: return "hourglass"
        case .volatilitySpike: return "chart.line.uptrend.xyaxis"
        case .gammaRisk: return "gauge.with.needle"
        case .legClosed: return "checkmark.circle"
        case .strategyAutoAdjusted: return "wrench.and.screwdriver"
        case .custom: return "bell"
        }
    }
}

enum MultiLegAlertSeverity: String, Codable {
    case info
    case warning
    case critical

    var color: Color {
        switch self {
        case .info: return .blue
        case .warning: return .orange
        case .critical: return .red
        }
    }

    var priority: Int {
        switch self {
        case .critical: return 3
        case .warning: return 2
        case .info: return 1
        }
    }
}

// MARK: - Core Models

struct MultiLegStrategy: Codable, Identifiable {
    let id: String
    let userId: String
    let name: String
    let strategyType: StrategyType
    let underlyingSymbolId: String
    let underlyingTicker: String

    let createdAt: String
    let openedAt: String?
    let closedAt: String?
    let status: StrategyStatus

    let totalDebit: Double?
    let totalCredit: Double?
    let netPremium: Double?
    let numContracts: Int

    let maxRisk: Double?
    let maxReward: Double?
    let maxRiskPct: Double?

    let breakevenPoints: [Double]?
    let profitZones: [ProfitZone]?

    let currentValue: Double?
    let totalPL: Double?
    let totalPLPct: Double?
    let realizedPL: Double?

    let forecastId: String?
    let forecastAlignment: ForecastAlignment?
    let forecastConfidence: Double?
    let alignmentCheckAt: String?

    let combinedDelta: Double?
    let combinedGamma: Double?
    let combinedTheta: Double?
    let combinedVega: Double?
    let combinedRho: Double?
    let greeksUpdatedAt: String?

    let minDTE: Int?
    let maxDTE: Int?

    let tags: [String: String]?
    let notes: String?

    let lastAlertAt: String?
    let version: Int
    let updatedAt: String

    var legs: [OptionsLeg]?
    var alerts: [MultiLegAlert]?

    enum CodingKeys: String, CodingKey {
        case id
        case userId
        case name
        case strategyType
        case underlyingSymbolId
        case underlyingTicker
        case createdAt
        case openedAt
        case closedAt
        case status
        case totalDebit
        case totalCredit
        case netPremium
        case numContracts
        case maxRisk
        case maxReward
        case maxRiskPct
        case breakevenPoints
        case profitZones
        case currentValue
        case totalPL
        case totalPLPct
        case realizedPL
        case forecastId
        case forecastAlignment
        case forecastConfidence
        case alignmentCheckAt
        case combinedDelta
        case combinedGamma
        case combinedTheta
        case combinedVega
        case combinedRho
        case greeksUpdatedAt
        case minDTE
        case maxDTE
        case tags
        case notes
        case lastAlertAt
        case version
        case updatedAt
        case legs
        case alerts
    }

    // MARK: - Computed Properties

    var plColor: Color {
        guard let pl = totalPL else { return .gray }
        if pl > 0 { return .green }
        if pl < 0 { return .red }
        return .gray
    }

    var plPctFormatted: String {
        guard let pct = totalPLPct else { return "N/A" }
        return String(format: "%+.1f%%", pct)
    }

    var plFormatted: String {
        guard let pl = totalPL else { return "N/A" }
        return String(format: "%+.2f", pl)
    }

    var netPremiumFormatted: String {
        guard let premium = netPremium else { return "N/A" }
        if premium > 0 {
            return String(format: "+$%.2f credit", premium)
        } else if premium < 0 {
            return String(format: "$%.2f debit", abs(premium))
        }
        return "$0.00"
    }

    var maxRiskFormatted: String {
        guard let risk = maxRisk else { return "Unlimited" }
        return String(format: "$%.0f", risk)
    }

    var maxRewardFormatted: String {
        guard let reward = maxReward else { return "Unlimited" }
        return String(format: "$%.0f", reward)
    }

    var dteLabel: String {
        guard let min = minDTE else { return "N/A" }
        if let max = maxDTE, max != min {
            return "\(min)-\(max) DTE"
        }
        return "\(min) DTE"
    }

    var openLegsCount: Int {
        legs?.filter { !$0.isClosed }.count ?? 0
    }

    var closedLegsCount: Int {
        legs?.filter { $0.isClosed }.count ?? 0
    }

    var activeAlertCount: Int {
        alerts?.filter { $0.acknowledgedAt == nil }.count ?? 0
    }

    var criticalAlertCount: Int {
        alerts?.filter { $0.severity == .critical && $0.acknowledgedAt == nil }.count ?? 0
    }

    var createdAtDate: Date? {
        ISO8601DateFormatter().date(from: createdAt)
    }

    var greeksUpdatedAtDate: Date? {
        guard let ts = greeksUpdatedAt else { return nil }
        return ISO8601DateFormatter().date(from: ts)
    }

    var greeksAgeLabel: String {
        guard let date = greeksUpdatedAtDate else { return "N/A" }
        let seconds = Date().timeIntervalSince(date)
        if seconds < 60 { return "\(Int(seconds))s ago" }
        if seconds < 3600 { return "\(Int(seconds / 60))m ago" }
        if seconds < 86400 { return "\(Int(seconds / 3600))h ago" }
        return "\(Int(seconds / 86400))d ago"
    }
}

struct ProfitZone: Codable {
    let min: Double
    let max: Double
}

struct OptionsLeg: Codable, Identifiable {
    let id: String
    let strategyId: String

    let legNumber: Int
    let legRole: LegRole?
    let positionType: PositionType
    let optionType: MultiLegOptionType

    let strike: Double
    let expiry: String
    let dteAtEntry: Int?
    let currentDTE: Int?

    let entryTimestamp: String
    let entryPrice: Double
    let contracts: Int
    let totalEntryCost: Double?

    let currentPrice: Double?
    let currentValue: Double?
    let unrealizedPL: Double?
    let unrealizedPLPct: Double?

    let isClosed: Bool
    let exitPrice: Double?
    let exitTimestamp: String?
    let realizedPL: Double?

    let entryDelta: Double?
    let entryGamma: Double?
    let entryTheta: Double?
    let entryVega: Double?
    let entryRho: Double?

    let currentDelta: Double?
    let currentGamma: Double?
    let currentTheta: Double?
    let currentVega: Double?
    let currentRho: Double?
    let greeksUpdatedAt: String?

    let entryImpliedVol: Double?
    let currentImpliedVol: Double?
    let vegaExposure: Double?

    let isAssigned: Bool
    let assignmentTimestamp: String?
    let assignmentPrice: Double?

    let isExercised: Bool
    let exerciseTimestamp: String?
    let exercisePrice: Double?

    let isITM: Bool?
    let isDeepITM: Bool?
    let isBreachingStrike: Bool?
    let isNearExpiration: Bool?

    let notes: String?
    let updatedAt: String

    var entries: [OptionsLegEntry]?

    enum CodingKeys: String, CodingKey {
        case id
        case strategyId
        case legNumber
        case legRole
        case positionType
        case optionType
        case strike
        case expiry
        case dteAtEntry
        case currentDTE
        case entryTimestamp
        case entryPrice
        case contracts
        case totalEntryCost
        case currentPrice
        case currentValue
        case unrealizedPL
        case unrealizedPLPct
        case isClosed
        case exitPrice
        case exitTimestamp
        case realizedPL
        case entryDelta
        case entryGamma
        case entryTheta
        case entryVega
        case entryRho
        case currentDelta
        case currentGamma
        case currentTheta
        case currentVega
        case currentRho
        case greeksUpdatedAt
        case entryImpliedVol
        case currentImpliedVol
        case vegaExposure
        case isAssigned
        case assignmentTimestamp
        case assignmentPrice
        case isExercised
        case exerciseTimestamp
        case exercisePrice
        case isITM
        case isDeepITM
        case isBreachingStrike
        case isNearExpiration
        case notes
        case updatedAt
        case entries
    }

    // MARK: - Computed Properties

    var displayLabel: String {
        let side = positionType == .long ? "Long" : "Short"
        let type = optionType == .call ? "Call" : "Put"
        return "\(side) \(strike) \(type)"
    }

    var compactLabel: String {
        let prefix = positionType == .long ? "+" : "-"
        let suffix = optionType == .call ? "C" : "P"
        return "\(prefix)\(Int(strike))\(suffix)"
    }

    var expiryDate: Date? {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.date(from: expiry)
    }

    var expiryFormatted: String {
        guard let date = expiryDate else { return expiry }
        let formatter = DateFormatter()
        formatter.dateFormat = "MMM d"
        return formatter.string(from: date)
    }

    /// OCC option symbol for API (21 chars: 6 root + 6 YYMMDD + 1 C/P + 8 strike). e.g. MU    260726P00090000
    func occSymbol(underlying: String) -> String {
        let root = String(underlying.uppercased().prefix(6))
        let paddedRoot = root.padding(toLength: 6, withPad: " ", startingAt: 0)
        let parts = expiry.split(separator: "-")
        guard parts.count == 3 else { return "" }
        let yy = String(parts[0].suffix(2))
        let mm = String(parts[1])
        let dd = String(parts[2])
        let dateStr = "\(yy)\(mm)\(dd)"
        let typeChar = optionType == .call ? "C" : "P"
        let strikeCents = Int(round(strike * 1000))
        let strikeStr = String(format: "%08d", strikeCents)
        return paddedRoot + dateStr + typeChar + strikeStr
    }

    var plColor: Color {
        guard let pl = isClosed ? realizedPL : unrealizedPL else { return .gray }
        if pl > 0 { return .green }
        if pl < 0 { return .red }
        return .gray
    }

    var plFormatted: String {
        let pl = isClosed ? realizedPL : unrealizedPL
        guard let value = pl else { return "N/A" }
        return String(format: "%+.2f", value)
    }

    var plPctFormatted: String {
        guard let pct = unrealizedPLPct else { return "N/A" }
        return String(format: "%+.1f%%", pct)
    }

    var statusBadge: (text: String, color: Color) {
        if isClosed {
            return ("Closed", .gray)
        }
        if isAssigned {
            return ("Assigned", .purple)
        }
        if isExercised {
            return ("Exercised", .blue)
        }
        if isNearExpiration == true {
            return ("Expiring", .orange)
        }
        if isBreachingStrike == true {
            return ("At Strike", .yellow)
        }
        if isDeepITM == true {
            return ("Deep ITM", .green)
        }
        if isITM == true {
            return ("ITM", .green.opacity(0.7))
        }
        return ("Open", .green)
    }

    var deltaColor: Color {
        guard let delta = currentDelta else { return .gray }
        let absDelta = abs(delta)
        if absDelta > 0.7 { return .green }
        if absDelta > 0.3 { return .orange }
        return .gray
    }
}

struct OptionsLegEntry: Codable, Identifiable {
    let id: String
    let legId: String
    let entryPrice: Double
    let contracts: Int
    let entryTimestamp: String
    let notes: String?
}

struct MultiLegAlert: Codable, Identifiable {
    let id: String
    let strategyId: String
    let legId: String?

    let alertType: MultiLegAlertType
    let severity: MultiLegAlertSeverity

    let title: String
    let reason: String?
    let details: [String: AnyCodable]?
    let suggestedAction: String?

    let createdAt: String
    let acknowledgedAt: String?
    let resolvedAt: String?
    let resolutionAction: String?

    let actionRequired: Bool

    enum CodingKeys: String, CodingKey {
        case id
        case strategyId
        case legId
        case alertType
        case severity
        case title
        case reason
        case details
        case suggestedAction
        case createdAt
        case acknowledgedAt
        case resolvedAt
        case resolutionAction
        case actionRequired
    }

    var isActive: Bool {
        acknowledgedAt == nil && resolvedAt == nil
    }

    var createdAtDate: Date? {
        ISO8601DateFormatter().date(from: createdAt)
    }

    var ageLabel: String {
        guard let date = createdAtDate else { return "Unknown" }
        let seconds = Date().timeIntervalSince(date)
        if seconds < 60 { return "\(Int(seconds))s ago" }
        if seconds < 3600 { return "\(Int(seconds / 60))m ago" }
        if seconds < 86400 { return "\(Int(seconds / 3600))h ago" }
        return "\(Int(seconds / 86400))d ago"
    }
}

struct StrategyTemplate: Codable, Identifiable {
    let id: String
    let name: String
    let strategyType: StrategyType
    let legConfig: [TemplateLegConfig]
    let typicalMaxRisk: Double?
    let typicalMaxReward: Double?
    let typicalCostPct: Double?
    let description: String?
    let bestFor: String?
    let marketCondition: String?
    let createdBy: String?
    let createdAt: String
    let updatedAt: String
    let isSystemTemplate: Bool
    let isPublic: Bool
}

struct TemplateLegConfig: Codable {
    let leg: Int
    let type: PositionType
    let optionType: MultiLegOptionType
    let strikeOffset: Double
    let dte: Int
    let role: LegRole?
}

// MARK: - API Request/Response Types

struct CreateStrategyRequest: Encodable {
    let name: String
    let strategyType: StrategyType
    let underlyingSymbolId: String
    let underlyingTicker: String
    let legs: [CreateLegInput]
    let forecastId: String?
    let forecastAlignment: ForecastAlignment?
    let notes: String?
    let tags: [String: String]?
}

struct CreateLegInput: Encodable {
    let legNumber: Int
    let legRole: LegRole?
    let positionType: PositionType
    let optionType: MultiLegOptionType
    let strike: Double
    let expiry: String
    let entryPrice: Double
    let contracts: Int
    let delta: Double?
    let gamma: Double?
    let theta: Double?
    let vega: Double?
    let rho: Double?
    let impliedVol: Double?
}

struct UpdateStrategyRequest: Encodable {
    let name: String?
    let notes: String?
    let tags: [String: String]?
    let forecastId: String?
    let forecastAlignment: ForecastAlignment?
}

struct CloseLegRequest: Encodable {
    let legId: String
    let exitPrice: Double
    let notes: String?
}

struct CloseStrategyRequest: Encodable {
    let strategyId: String
    let exitPrices: [LegExitPrice]
    let notes: String?

    struct LegExitPrice: Encodable {
        let legId: String
        let exitPrice: Double
    }
}

struct ListStrategiesResponse: Codable {
    let strategies: [MultiLegStrategy]
    let total: Int
    let hasMore: Bool
}

struct StrategyDetailResponse: Codable {
    let strategy: MultiLegStrategy
    let legs: [OptionsLeg]
    let alerts: [MultiLegAlert]
    let metrics: [StrategyMetrics]?
}

struct StrategyMetrics: Codable, Identifiable {
    let id: String
    let strategyId: String
    let recordedAt: String
    let recordedTimestamp: String

    let underlyingPrice: Double?
    let totalValue: Double?
    let totalPL: Double?
    let totalPLPct: Double?

    let deltaSnapshot: Double?
    let gammaSnapshot: Double?
    let thetaSnapshot: Double?
    let vegaSnapshot: Double?

    let minDTE: Int?
    let alertCount: Int
    let criticalAlertCount: Int
}

struct CreateStrategyResponse: Codable {
    let strategy: MultiLegStrategy
    let legs: [OptionsLeg]
}

struct CloseLegResponse: Codable {
    let leg: OptionsLeg
    let strategy: MultiLegStrategy
}

struct CloseStrategyResponse: Codable {
    let strategy: MultiLegStrategy
    let legs: [OptionsLeg]
}

struct TemplatesResponse: Codable {
    let templates: [StrategyTemplate]
}

struct DeleteStrategyResponse: Codable {
    let success: Bool
    let deletedId: String
    let deletedName: String
}

// MARK: - Helpers
// Note: AnyCodable is defined in ScannerResponse.swift

// MARK: - Preview Helpers

extension MultiLegStrategy {
    static let example = MultiLegStrategy(
        id: UUID().uuidString,
        userId: "user-1",
        name: "AAPL Bull Call Spread",
        strategyType: .bullCallSpread,
        underlyingSymbolId: "sym-1",
        underlyingTicker: "AAPL",
        createdAt: ISO8601DateFormatter().string(from: Date()),
        openedAt: ISO8601DateFormatter().string(from: Date()),
        closedAt: nil,
        status: .open,
        totalDebit: 250,
        totalCredit: nil,
        netPremium: -250,
        numContracts: 1,
        maxRisk: 250,
        maxReward: 750,
        maxRiskPct: 25,
        breakevenPoints: [152.50],
        profitZones: [ProfitZone(min: 152.50, max: 160)],
        currentValue: 350,
        totalPL: 100,
        totalPLPct: 40,
        realizedPL: nil,
        forecastId: nil,
        forecastAlignment: .bullish,
        forecastConfidence: 0.75,
        alignmentCheckAt: nil,
        combinedDelta: 0.35,
        combinedGamma: 0.02,
        combinedTheta: -5.50,
        combinedVega: 0.15,
        combinedRho: 0.05,
        greeksUpdatedAt: ISO8601DateFormatter().string(from: Date()),
        minDTE: 14,
        maxDTE: 14,
        tags: ["sector": "tech"],
        notes: "Q1 earnings play",
        lastAlertAt: nil,
        version: 1,
        updatedAt: ISO8601DateFormatter().string(from: Date()),
        legs: [OptionsLeg.exampleLong, OptionsLeg.exampleShort],
        alerts: []
    )
}

extension OptionsLeg {
    static let exampleLong = OptionsLeg(
        id: UUID().uuidString,
        strategyId: "strat-1",
        legNumber: 1,
        legRole: .primaryLeg,
        positionType: .long,
        optionType: .call,
        strike: 150,
        expiry: "2026-02-15",
        dteAtEntry: 30,
        currentDTE: 14,
        entryTimestamp: ISO8601DateFormatter().string(from: Date()),
        entryPrice: 5.50,
        contracts: 1,
        totalEntryCost: 550,
        currentPrice: 7.00,
        currentValue: 700,
        unrealizedPL: 150,
        unrealizedPLPct: 27.27,
        isClosed: false,
        exitPrice: nil,
        exitTimestamp: nil,
        realizedPL: nil,
        entryDelta: 0.55,
        entryGamma: 0.03,
        entryTheta: -0.08,
        entryVega: 0.15,
        entryRho: 0.06,
        currentDelta: 0.65,
        currentGamma: 0.02,
        currentTheta: -0.12,
        currentVega: 0.12,
        currentRho: 0.05,
        greeksUpdatedAt: ISO8601DateFormatter().string(from: Date()),
        entryImpliedVol: 0.28,
        currentImpliedVol: 0.32,
        vegaExposure: 12,
        isAssigned: false,
        assignmentTimestamp: nil,
        assignmentPrice: nil,
        isExercised: false,
        exerciseTimestamp: nil,
        exercisePrice: nil,
        isITM: true,
        isDeepITM: false,
        isBreachingStrike: false,
        isNearExpiration: false,
        notes: nil,
        updatedAt: ISO8601DateFormatter().string(from: Date()),
        entries: nil
    )

    static let exampleShort = OptionsLeg(
        id: UUID().uuidString,
        strategyId: "strat-1",
        legNumber: 2,
        legRole: .hedgeLeg,
        positionType: .short,
        optionType: .call,
        strike: 160,
        expiry: "2026-02-15",
        dteAtEntry: 30,
        currentDTE: 14,
        entryTimestamp: ISO8601DateFormatter().string(from: Date()),
        entryPrice: 3.00,
        contracts: 1,
        totalEntryCost: -300,
        currentPrice: 3.50,
        currentValue: -350,
        unrealizedPL: -50,
        unrealizedPLPct: -16.67,
        isClosed: false,
        exitPrice: nil,
        exitTimestamp: nil,
        realizedPL: nil,
        entryDelta: -0.30,
        entryGamma: -0.02,
        entryTheta: 0.05,
        entryVega: -0.10,
        entryRho: -0.03,
        currentDelta: -0.30,
        currentGamma: -0.015,
        currentTheta: 0.065,
        currentVega: -0.08,
        currentRho: -0.025,
        greeksUpdatedAt: ISO8601DateFormatter().string(from: Date()),
        entryImpliedVol: 0.25,
        currentImpliedVol: 0.28,
        vegaExposure: -8,
        isAssigned: false,
        assignmentTimestamp: nil,
        assignmentPrice: nil,
        isExercised: false,
        exerciseTimestamp: nil,
        exercisePrice: nil,
        isITM: false,
        isDeepITM: false,
        isBreachingStrike: false,
        isNearExpiration: false,
        notes: nil,
        updatedAt: ISO8601DateFormatter().string(from: Date()),
        entries: nil
    )
}

extension MultiLegAlert {
    static let example = MultiLegAlert(
        id: UUID().uuidString,
        strategyId: "strat-1",
        legId: nil,
        alertType: .expirationSoon,
        severity: .warning,
        title: "Strategy expiring in 3 days",
        reason: "The nearest expiration leg has 3 DTE remaining",
        details: nil,
        suggestedAction: "Consider closing or rolling the position",
        createdAt: ISO8601DateFormatter().string(from: Date()),
        acknowledgedAt: nil,
        resolvedAt: nil,
        resolutionAction: nil,
        actionRequired: true
    )
}
