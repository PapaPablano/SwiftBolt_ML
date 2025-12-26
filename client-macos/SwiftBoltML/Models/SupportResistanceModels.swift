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

// MARK: - API Response Models

/// Response from the support-resistance Edge Function
/// API returns flat structure with S/R data at root level
struct SupportResistanceResponse: Codable {
    let symbol: String
    let currentPrice: Double
    let lastUpdated: String?
    let nearestSupport: Double?
    let nearestResistance: Double?
    let supportDistancePct: Double?
    let resistanceDistancePct: Double?
    let pivotPoints: PivotPoints?
    let fibonacci: FibonacciLevels?
    let allSupports: [Double]?
    let allResistances: [Double]?

    enum CodingKeys: String, CodingKey {
        case symbol
        case currentPrice
        case lastUpdated
        case nearestSupport
        case nearestResistance
        case supportDistancePct
        case resistanceDistancePct
        case pivotPoints
        case fibonacci
        case allSupports
        case allResistances
    }

    /// Computed property to create SRLevels from flat response
    var levels: SRLevels {
        SRLevels(
            nearestSupport: nearestSupport,
            nearestResistance: nearestResistance,
            supportDistancePct: supportDistancePct,
            resistanceDistancePct: resistanceDistancePct,
            allSupports: allSupports,
            allResistances: allResistances
        )
    }
    
    /// Computed density based on number of levels
    var density: Int {
        (allSupports?.count ?? 0) + (allResistances?.count ?? 0)
    }

    var bias: String {
        guard let supportDist = supportDistancePct,
              let resistanceDist = resistanceDistancePct else {
            return "Neutral"
        }

        if supportDist < resistanceDist {
            return "Bullish"  // Closer to support, likely to bounce up
        } else if resistanceDist < supportDist {
            return "Bearish"  // Closer to resistance, likely to reject down
        } else {
            return "Neutral"
        }
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
}

// MARK: - Pivot Points

struct PivotPoints: Codable {
    let pp: Double
    let r1: Double
    let r2: Double
    let r3: Double
    let s1: Double
    let s2: Double
    let s3: Double

    enum CodingKeys: String, CodingKey {
        case pp = "PP"
        case r1 = "R1"
        case r2 = "R2"
        case r3 = "R3"
        case s1 = "S1"
        case s2 = "S2"
        case s3 = "S3"
    }

    var allLevels: [Double] {
        [s3, s2, s1, pp, r1, r2, r3]
    }
}

// MARK: - Fibonacci Levels

struct FibonacciLevels: Codable {
    let trend: String  // "uptrend" or "downtrend"
    let fib0: Double?
    let fib236: Double?
    let fib382: Double?
    let fib500: Double?
    let fib618: Double?
    let fib786: Double?
    let fib100: Double?
    let rangeHigh: Double?
    let rangeLow: Double?

    enum CodingKeys: String, CodingKey {
        case trend
        case fib0 = "0.0"
        case fib236 = "23.6"
        case fib382 = "38.2"
        case fib500 = "50.0"
        case fib618 = "61.8"
        case fib786 = "78.6"
        case fib100 = "100.0"
        case rangeHigh
        case rangeLow
    }

    var allLevels: [Double] {
        [fib0, fib236, fib382, fib500, fib618, fib786, fib100].compactMap { $0 }
    }
}
