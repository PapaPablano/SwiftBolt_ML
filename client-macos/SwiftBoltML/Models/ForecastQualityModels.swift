import Foundation

// MARK: - Forecast Quality Request

struct ForecastQualityRequest: Codable {
    let symbol: String
    let horizon: String?
    let timeframe: String?
}

// MARK: - Forecast Quality Response

struct ForecastQualityResponse: Codable {
    let symbol: String
    let horizon: String
    let timeframe: String
    let qualityScore: Double
    let confidence: Double
    let modelAgreement: Double
    let issues: [QualityIssue]
    let timestamp: String
}

struct QualityIssue: Codable {
    let level: String
    let type: String
    let message: String
    let action: String
}
