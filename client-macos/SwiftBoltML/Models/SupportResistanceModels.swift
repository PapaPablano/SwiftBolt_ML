import Foundation

// MARK: - Support & Resistance Response

struct SupportResistanceResponse: Codable {
    let symbol: String
    let currentPrice: Double
    let lastUpdated: String
    let nearestSupport: Double?
    let nearestResistance: Double?
    let supportDistancePct: Double?
    let resistanceDistancePct: Double?
    let pivotPoints: PivotPoints
    let fibonacci: FibonacciLevels
    let zigzagSwings: [SwingPoint]
    let allSupports: [Double]
    let allResistances: [Double]
    let priceData: SRPriceData
}

struct PivotPoints: Codable {
    let PP: Double
    let R1: Double
    let R2: Double
    let R3: Double
    let S1: Double
    let S2: Double
    let S3: Double
}

struct FibonacciLevels: Codable {
    let trend: String
    let rangeHigh: Double
    let rangeLow: Double
    
    // Fibonacci levels as strings since JSON keys have decimals
    private enum CodingKeys: String, CodingKey {
        case trend, rangeHigh, rangeLow
        case fib0 = "0.0"
        case fib236 = "23.6"
        case fib382 = "38.2"
        case fib500 = "50.0"
        case fib618 = "61.8"
        case fib786 = "78.6"
        case fib100 = "100.0"
    }
    
    let fib0: Double
    let fib236: Double
    let fib382: Double
    let fib500: Double
    let fib618: Double
    let fib786: Double
    let fib100: Double
    
    var levels: [(name: String, value: Double)] {
        [
            ("0.0%", fib0),
            ("23.6%", fib236),
            ("38.2%", fib382),
            ("50.0%", fib500),
            ("61.8%", fib618),
            ("78.6%", fib786),
            ("100.0%", fib100)
        ]
    }
}

struct SwingPoint: Codable, Identifiable {
    let type: String // "high" or "low"
    let price: Double
    let ts: String
    let index: Int
    
    var id: String { "\(type)-\(index)" }
    
    var isHigh: Bool { type == "high" }
}

struct SRPriceData: Codable {
    let high: Double
    let low: Double
    let close: Double
    let periodHigh: Double
    let periodLow: Double
}

// MARK: - Computed Properties

extension SupportResistanceResponse {
    var srRatio: Double? {
        guard let supportDist = supportDistancePct,
              let resistanceDist = resistanceDistancePct,
              supportDist > 0 else {
            return nil
        }
        return resistanceDist / supportDist
    }
    
    var bias: String {
        guard let ratio = srRatio else { return "Unknown" }
        if ratio > 1.5 {
            return "Bullish"
        } else if ratio < 0.67 {
            return "Bearish"
        } else {
            return "Neutral"
        }
    }
    
    var biasDescription: String {
        guard let ratio = srRatio else { return "Unable to determine bias" }
        if ratio > 1.5 {
            return "More room to upside than downside"
        } else if ratio < 0.67 {
            return "More room to downside than upside"
        } else {
            return "Balanced risk/reward"
        }
    }
}
