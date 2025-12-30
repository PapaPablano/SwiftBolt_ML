import Foundation

// MARK: - Support/Resistance Models

struct SRLevels: Codable, Equatable {
    let nearestSupport: Double?
    let nearestResistance: Double?
    let supportDistancePct: Double?
    let resistanceDistancePct: Double?
    let allSupports: [Double]?
    let allResistances: [Double]?

    enum CodingKeys: String, CodingKey {
        case nearestSupport = "nearest_support"
        case nearestResistance = "nearest_resistance"
        case supportDistancePct = "support_distance_pct"
        case resistanceDistancePct = "resistance_distance_pct"
        case allSupports = "all_supports"
        case allResistances = "all_resistances"
    }

    init(nearestSupport: Double? = nil, nearestResistance: Double? = nil, supportDistancePct: Double? = nil, resistanceDistancePct: Double? = nil, allSupports: [Double]? = nil, allResistances: [Double]? = nil) {
        self.nearestSupport = nearestSupport
        self.nearestResistance = nearestResistance
        self.supportDistancePct = supportDistancePct
        self.resistanceDistancePct = resistanceDistancePct
        self.allSupports = allSupports
        self.allResistances = allResistances
    }

    var hasSupport: Bool {
        nearestSupport != nil
    }

    var hasResistance: Bool {
        nearestResistance != nil
    }

    var isNearSupport: Bool {
        guard let dist = supportDistancePct else { return false }
        return dist < 2.0  // Within 2%
    }

    var isNearResistance: Bool {
        guard let dist = resistanceDistancePct else { return false }
        return dist < 2.0  // Within 2%
    }

    /// Get the top N support levels
    func topSupports(_ count: Int = 3) -> [Double] {
        Array((allSupports ?? []).prefix(count))
    }

    /// Get the top N resistance levels
    func topResistances(_ count: Int = 3) -> [Double] {
        Array((allResistances ?? []).prefix(count))
    }
}

struct SRDensityInfo: Codable {
    let density: Int?
    let description: String

    enum CodingKeys: String, CodingKey {
        case density = "sr_density"
        case description
    }

    init(density: Int?) {
        self.density = density
        self.description = Self.getDescription(for: density)
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        density = try container.decodeIfPresent(Int.self, forKey: .density)
        description = Self.getDescription(for: density)
    }

    var congestionLevel: CongestionLevel {
        guard let density = density else { return .low }
        if density >= 5 {
            return .high
        } else if density >= 3 {
            return .medium
        } else {
            return .low
        }
    }

    var color: String {
        congestionLevel.color
    }

    private static func getDescription(for density: Int?) -> String {
        guard let density = density else { return "No S/R data" }
        if density >= 5 {
            return "High congestion zone (\(density) levels)"
        } else if density >= 3 {
            return "Moderate congestion (\(density) levels)"
        } else if density > 0 {
            return "Light S/R presence (\(density) levels)"
        } else {
            return "Clear trading zone"
        }
    }
}

enum CongestionLevel {
    case low
    case medium
    case high

    var displayName: String {
        switch self {
        case .low: return "Low"
        case .medium: return "Moderate"
        case .high: return "High"
        }
    }

    var color: String {
        switch self {
        case .low: return "green"
        case .medium: return "orange"
        case .high: return "red"
        }
    }

    var icon: String {
        switch self {
        case .low: return "checkmark.circle.fill"
        case .medium: return "exclamationmark.triangle.fill"
        case .high: return "xmark.octagon.fill"
        }
    }
}

// MARK: - S/R Chart Overlay Models

struct SRChartOverlay {
    let supportLevels: [SRLevel]
    let resistanceLevels: [SRLevel]
    let currentPrice: Double

    init(srLevels: SRLevels, currentPrice: Double) {
        self.currentPrice = currentPrice

        // Create support levels
        self.supportLevels = (srLevels.allSupports ?? []).enumerated().map { index, price in
            SRLevel(
                price: price,
                type: .support,
                isNearest: index == 0,
                distancePercent: ((currentPrice - price) / currentPrice) * 100
            )
        }

        // Create resistance levels
        self.resistanceLevels = (srLevels.allResistances ?? []).enumerated().map { index, price in
            SRLevel(
                price: price,
                type: .resistance,
                isNearest: index == 0,
                distancePercent: ((price - currentPrice) / currentPrice) * 100
            )
        }
    }

    var allLevels: [SRLevel] {
        supportLevels + resistanceLevels
    }

    var significantLevels: [SRLevel] {
        allLevels.filter { $0.distancePercent < 5.0 }  // Within 5% of current price
    }
}

struct SRLevel: Identifiable {
    let id = UUID()
    let price: Double
    let type: SRLevelType
    let isNearest: Bool
    let distancePercent: Double

    var color: String {
        type.color
    }

    var opacity: Double {
        if isNearest {
            return 0.8
        } else if distancePercent < 2.0 {
            return 0.6
        } else {
            return 0.3
        }
    }

    var lineWidth: Double {
        isNearest ? 2.0 : 1.0
    }
}

enum SRLevelType {
    case support
    case resistance

    var displayName: String {
        switch self {
        case .support: return "Support"
        case .resistance: return "Resistance"
        }
    }

    var color: String {
        switch self {
        case .support: return "green"
        case .resistance: return "red"
        }
    }

    var shortName: String {
        switch self {
        case .support: return "S"
        case .resistance: return "R"
        }
    }
}

// MARK: - New Indicator Response Models

/// Single pivot level period response (5, 25, 50, or 100 bars)
struct PivotLevelPeriodResponse: Codable {
    let high: Double?
    let low: Double?
    let highStatus: String?
    let lowStatus: String?

    var highStatusEnum: PivotStatus {
        switch highStatus?.lowercased() {
        case "support": return .support
        case "resistance": return .resistance
        case "active": return .active
        default: return .inactive
        }
    }

    var lowStatusEnum: PivotStatus {
        switch lowStatus?.lowercased() {
        case "support": return .support
        case "resistance": return .resistance
        case "active": return .active
        default: return .inactive
        }
    }
}

/// Multi-timeframe pivot levels response
struct PivotLevelsResponse: Codable {
    let period5: PivotLevelPeriodResponse?
    let period25: PivotLevelPeriodResponse?
    let period50: PivotLevelPeriodResponse?
    let period100: PivotLevelPeriodResponse?

    /// All periods in order
    var allPeriods: [(name: String, period: PivotLevelPeriodResponse?)] {
        [
            ("5 Bar", period5),
            ("25 Bar", period25),
            ("50 Bar", period50),
            ("100 Bar", period100)
        ]
    }

    /// Get nearest support from all periods
    var nearestSupport: Double? {
        let supports = [period5?.low, period25?.low, period50?.low, period100?.low]
            .compactMap { $0 }
        return supports.max()  // Highest low = nearest support
    }

    /// Get nearest resistance from all periods
    var nearestResistance: Double? {
        let resistances = [period5?.high, period25?.high, period50?.high, period100?.high]
            .compactMap { $0 }
        return resistances.min()  // Lowest high = nearest resistance
    }
}

/// Polynomial regression S/R response
struct PolynomialSRResponse: Codable {
    let support: Double?
    let resistance: Double?
    let supportSlope: Double?
    let resistanceSlope: Double?
    let forecastSupport: [Double]?
    let forecastResistance: [Double]?

    /// Support trend direction
    var supportTrend: TrendDirection {
        guard let slope = supportSlope else { return .flat }
        if slope > 0.01 { return .rising }
        if slope < -0.01 { return .falling }
        return .flat
    }

    /// Resistance trend direction
    var resistanceTrend: TrendDirection {
        guard let slope = resistanceSlope else { return .flat }
        if slope > 0.01 { return .rising }
        if slope < -0.01 { return .falling }
        return .flat
    }

    /// Check if S/R is converging (squeeze)
    var isConverging: Bool {
        guard let support = support, let resistance = resistance,
              supportTrend == .rising && resistanceTrend == .falling else {
            return false
        }
        let range = resistance - support
        return range > 0 && range / support < 0.05  // Less than 5% range
    }

    /// Check if S/R is diverging (expansion)
    var isDiverging: Bool {
        supportTrend == .falling && resistanceTrend == .rising
    }
}

/// Trend direction for polynomial slopes
enum TrendDirection {
    case rising
    case falling
    case flat

    var displayName: String {
        switch self {
        case .rising: return "Rising"
        case .falling: return "Falling"
        case .flat: return "Flat"
        }
    }

    var icon: String {
        switch self {
        case .rising: return "arrow.up.right"
        case .falling: return "arrow.down.right"
        case .flat: return "arrow.right"
        }
    }

    var color: String {
        switch self {
        case .rising: return "green"
        case .falling: return "red"
        case .flat: return "gray"
        }
    }
}

/// Individual logistic regression level
struct LogisticLevelResponse: Codable, Identifiable {
    let level: Double
    let probability: Double
    let timesRespected: Int?

    var id: Double { level }

    /// Probability as percentage string
    var probabilityText: String {
        "\(Int(probability * 100))%"
    }

    /// Confidence level based on probability
    var confidence: ConfidenceLevel {
        if probability >= 0.7 { return .high }
        if probability >= 0.5 { return .medium }
        return .low
    }
}

/// Confidence level for ML predictions
enum ConfidenceLevel {
    case low
    case medium
    case high

    var displayName: String {
        switch self {
        case .low: return "Low"
        case .medium: return "Medium"
        case .high: return "High"
        }
    }

    var color: String {
        switch self {
        case .low: return "gray"
        case .medium: return "orange"
        case .high: return "green"
        }
    }
}

/// Logistic regression S/R response
struct LogisticSRResponse: Codable {
    let supportLevels: [LogisticLevelResponse]?
    let resistanceLevels: [LogisticLevelResponse]?
    let signals: [String]?

    /// Top support level by probability
    var topSupport: LogisticLevelResponse? {
        supportLevels?.max(by: { $0.probability < $1.probability })
    }

    /// Top resistance level by probability
    var topResistance: LogisticLevelResponse? {
        resistanceLevels?.max(by: { $0.probability < $1.probability })
    }

    /// Check if there are active signals
    var hasSignals: Bool {
        !(signals?.isEmpty ?? true)
    }

    /// Parse signals into structured format
    var parsedSignals: [SRSignal] {
        signals?.compactMap { SRSignal(rawValue: $0) } ?? []
    }
}

/// S/R signal types from logistic indicator
enum SRSignal: String {
    case supportRetest = "support_retest"
    case resistanceRetest = "resistance_retest"
    case supportBreak = "support_break"
    case resistanceBreak = "resistance_break"
    case supportRespected = "support_respected"
    case resistanceRespected = "resistance_respected"

    var displayName: String {
        switch self {
        case .supportRetest: return "Support Retest"
        case .resistanceRetest: return "Resistance Retest"
        case .supportBreak: return "Support Break"
        case .resistanceBreak: return "Resistance Break"
        case .supportRespected: return "Support Respected"
        case .resistanceRespected: return "Resistance Respected"
        }
    }

    var icon: String {
        switch self {
        case .supportRetest, .resistanceRetest: return "arrow.uturn.down"
        case .supportBreak, .resistanceBreak: return "arrow.down.to.line"
        case .supportRespected, .resistanceRespected: return "checkmark.shield"
        }
    }

    var color: String {
        switch self {
        case .supportRetest, .supportRespected: return "green"
        case .resistanceRetest, .resistanceRespected: return "red"
        case .supportBreak: return "red"
        case .resistanceBreak: return "green"
        }
    }

    var isBullish: Bool {
        switch self {
        case .supportRetest, .supportRespected, .resistanceBreak: return true
        case .resistanceRetest, .resistanceRespected, .supportBreak: return false
        }
    }
}

/// Bias type for S/R analysis
enum BiasType: String, Codable {
    case bullish = "Bullish"
    case bearish = "Bearish"
    case neutral = "Neutral"

    var color: String {
        switch self {
        case .bullish: return "green"
        case .bearish: return "red"
        case .neutral: return "gray"
        }
    }

    var icon: String {
        switch self {
        case .bullish: return "arrow.up.circle.fill"
        case .bearish: return "arrow.down.circle.fill"
        case .neutral: return "minus.circle.fill"
        }
    }
}

// MARK: - API Response Models

/// Response from the support-resistance Edge Function
/// Updated for new 3-indicator structure
struct SupportResistanceResponse: Codable {
    let symbol: String
    let currentPrice: Double
    let lastUpdated: String?

    // New indicator responses
    let pivotLevels: PivotLevelsResponse?
    let polynomial: PolynomialSRResponse?
    let logistic: LogisticSRResponse?

    // Summary fields
    let nearestSupport: Double?
    let nearestResistance: Double?
    let supportDistancePct: Double?
    let resistanceDistancePct: Double?
    let bias: String?

    enum CodingKeys: String, CodingKey {
        case symbol
        case currentPrice
        case lastUpdated
        case pivotLevels
        case polynomial
        case logistic
        case nearestSupport
        case nearestResistance
        case supportDistancePct
        case resistanceDistancePct
        case bias
    }

    /// Computed property to create SRLevels from response
    var levels: SRLevels {
        // Collect all support/resistance levels from all indicators
        var allSupports: [Double] = []
        var allResistances: [Double] = []

        // From pivot levels
        if let pivots = pivotLevels {
            if let p5Low = pivots.period5?.low { allSupports.append(p5Low) }
            if let p25Low = pivots.period25?.low { allSupports.append(p25Low) }
            if let p50Low = pivots.period50?.low { allSupports.append(p50Low) }
            if let p100Low = pivots.period100?.low { allSupports.append(p100Low) }
            if let p5High = pivots.period5?.high { allResistances.append(p5High) }
            if let p25High = pivots.period25?.high { allResistances.append(p25High) }
            if let p50High = pivots.period50?.high { allResistances.append(p50High) }
            if let p100High = pivots.period100?.high { allResistances.append(p100High) }
        }

        // From polynomial
        if let poly = polynomial {
            if let support = poly.support { allSupports.append(support) }
            if let resistance = poly.resistance { allResistances.append(resistance) }
        }

        // From logistic
        if let log = logistic {
            allSupports.append(contentsOf: log.supportLevels?.map { $0.level } ?? [])
            allResistances.append(contentsOf: log.resistanceLevels?.map { $0.level } ?? [])
        }

        return SRLevels(
            nearestSupport: nearestSupport,
            nearestResistance: nearestResistance,
            supportDistancePct: supportDistancePct,
            resistanceDistancePct: resistanceDistancePct,
            allSupports: allSupports.sorted(by: >),  // Highest first
            allResistances: allResistances.sorted()   // Lowest first
        )
    }

    /// Computed density based on number of levels
    var density: Int {
        var count = 0
        if let pivots = pivotLevels {
            if pivots.period5 != nil { count += 2 }
            if pivots.period25 != nil { count += 2 }
            if pivots.period50 != nil { count += 2 }
            if pivots.period100 != nil { count += 2 }
        }
        if polynomial?.support != nil { count += 1 }
        if polynomial?.resistance != nil { count += 1 }
        count += logistic?.supportLevels?.count ?? 0
        count += logistic?.resistanceLevels?.count ?? 0
        return count
    }

    var biasType: BiasType {
        BiasType(rawValue: bias ?? "Neutral") ?? .neutral
    }

    var biasDescription: String {
        guard let supportDist = supportDistancePct,
              let resistanceDist = resistanceDistancePct else {
            return "No clear S/R bias"
        }

        if supportDist < 1.0 {
            return "Very close to support - strong bounce potential"
        } else if resistanceDist < 1.0 {
            return "Very close to resistance - rejection likely"
        } else if supportDist < resistanceDist {
            return "Closer to support than resistance"
        } else {
            return "Closer to resistance than support"
        }
    }

    var srRatio: Double? {
        guard let supportDist = supportDistancePct,
              let resistanceDist = resistanceDistancePct,
              resistanceDist > 0 else {
            return nil
        }
        return supportDist / resistanceDist
    }

    var densityInfo: SRDensityInfo {
        SRDensityInfo(density: density)
    }

    var chartOverlay: SRChartOverlay {
        SRChartOverlay(srLevels: levels, currentPrice: currentPrice)
    }

    /// Check if any indicator has active signals
    var hasActiveSignals: Bool {
        logistic?.hasSignals ?? false
    }

    /// Get all active signals
    var activeSignals: [SRSignal] {
        logistic?.parsedSignals ?? []
    }

    /// Summary of polynomial trends
    var polynomialTrendSummary: String? {
        guard let poly = polynomial else { return nil }
        let supportTrend = poly.supportTrend.displayName
        let resistanceTrend = poly.resistanceTrend.displayName

        if poly.isConverging {
            return "Converging (Squeeze) - Support \(supportTrend), Resistance \(resistanceTrend)"
        } else if poly.isDiverging {
            return "Diverging (Expansion) - Support \(supportTrend), Resistance \(resistanceTrend)"
        } else {
            return "Support \(supportTrend), Resistance \(resistanceTrend)"
        }
    }
}
