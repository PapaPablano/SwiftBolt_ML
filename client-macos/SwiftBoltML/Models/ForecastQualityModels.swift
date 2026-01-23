import Foundation

// MARK: - Forecast Quality Request

struct ForecastQualityRequest: Codable {
    let symbol: String
    let horizon: String?
    let timeframe: String?
}

// MARK: - Forecast Quality Response

struct ForecastQualityResponse: Decodable {
    let symbol: String
    let horizon: String
    let timeframe: String
    let qualityScore: Double
    let confidence: Double
    let modelAgreement: Double
    let issues: [QualityIssue]
    let timestamp: String
}

struct QualityIssue: Decodable {
    let level: String
    let type: String
    let message: String
    let action: String
}
