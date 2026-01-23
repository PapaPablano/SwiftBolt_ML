import Foundation

// MARK: - Model Training Request

struct ModelTrainingRequest: Codable {
    let symbol: String
    let timeframe: String?
    let lookbackDays: Int?
}

// MARK: - Model Training Response

struct ModelTrainingResponse: Decodable {
    let symbol: String
    let timeframe: String
    let lookbackDays: Int
    let status: String
    let trainingMetrics: TrainingMetrics
    let modelInfo: ModelInfo
    let ensembleWeights: [String: Double]
    let featureImportance: [String: Double]
}

struct TrainingMetrics: Decodable {
    let trainAccuracy: Double
    let validationAccuracy: Double
    let testAccuracy: Double
    let trainSamples: Int
    let validationSamples: Int
    let testSamples: Int
}

struct ModelInfo: Decodable {
    let modelHash: String
    let featureCount: Int
    let trainedAt: String
}
