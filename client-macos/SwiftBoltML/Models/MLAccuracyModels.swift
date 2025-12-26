import Foundation

// MARK: - Horizon Accuracy Response

/// Response from /ml-dashboard?action=horizon_accuracy
struct HorizonAccuracyResponse: Decodable {
    let daily: HorizonAccuracyDetail?
    let weekly: HorizonAccuracyDetail?
    let modelComparison: [ModelComparisonData]?
    let topSymbolsDaily: [SymbolAccuracyData]?
    let topSymbolsWeekly: [SymbolAccuracyData]?
    let currentWeights: [ModelWeightData]?
    let generatedAt: String?

    enum CodingKeys: String, CodingKey {
        case daily
        case weekly
        case modelComparison = "model_comparison"
        case topSymbolsDaily = "top_symbols_daily"
        case topSymbolsWeekly = "top_symbols_weekly"
        case currentWeights = "current_weights"
        case generatedAt = "generated_at"
    }
}

// MARK: - Horizon Accuracy Detail

struct HorizonAccuracyDetail: Decodable {
    let horizon: String
    let totalForecasts: Int
    let correctForecasts: Int?
    let accuracyPct: Double
    let avgErrorPct: Double?
    let maxErrorPct: Double?
    let bullishAccuracyPct: Double?
    let bearishAccuracyPct: Double?
    let neutralAccuracyPct: Double?
    let rfAccuracyPct: Double?
    let gbAccuracyPct: Double?
    let bullishPredictions: Int?
    let bearishPredictions: Int?
    let neutralPredictions: Int?
    let firstEvaluation: String?
    let lastEvaluation: String?

    enum CodingKeys: String, CodingKey {
        case horizon
        case totalForecasts = "total_forecasts"
        case correctForecasts = "correct_forecasts"
        case accuracyPct = "accuracy_pct"
        case avgErrorPct = "avg_error_pct"
        case maxErrorPct = "max_error_pct"
        case bullishAccuracyPct = "bullish_accuracy_pct"
        case bearishAccuracyPct = "bearish_accuracy_pct"
        case neutralAccuracyPct = "neutral_accuracy_pct"
        case rfAccuracyPct = "rf_accuracy_pct"
        case gbAccuracyPct = "gb_accuracy_pct"
        case bullishPredictions = "bullish_predictions"
        case bearishPredictions = "bearish_predictions"
        case neutralPredictions = "neutral_predictions"
        case firstEvaluation = "first_evaluation"
        case lastEvaluation = "last_evaluation"
    }

    var accuracyColor: String {
        if accuracyPct >= 60 { return "green" }
        if accuracyPct >= 45 { return "orange" }
        return "red"
    }
}

// MARK: - Model Comparison Data

struct ModelComparisonData: Decodable, Identifiable {
    let horizon: String
    let totalEvaluations: Int?
    let rfAccuracyPct: Double?
    let rfCorrectCount: Int?
    let gbAccuracyPct: Double?
    let gbCorrectCount: Int?
    let agreementPct: Double?
    let accuracyWhenAgreePct: Double?
    let accuracyWhenDisagreePct: Double?
    let recommendedRfWeight: Double?
    let recommendedGbWeight: Double?

    var id: String { horizon }

    enum CodingKeys: String, CodingKey {
        case horizon
        case totalEvaluations = "total_evaluations"
        case rfAccuracyPct = "rf_accuracy_pct"
        case rfCorrectCount = "rf_correct_count"
        case gbAccuracyPct = "gb_accuracy_pct"
        case gbCorrectCount = "gb_correct_count"
        case agreementPct = "agreement_pct"
        case accuracyWhenAgreePct = "accuracy_when_agree_pct"
        case accuracyWhenDisagreePct = "accuracy_when_disagree_pct"
        case recommendedRfWeight = "recommended_rf_weight"
        case recommendedGbWeight = "recommended_gb_weight"
    }
}

// MARK: - Symbol Accuracy Data

struct SymbolAccuracyData: Decodable, Identifiable {
    let symbol: String
    let horizon: String
    let totalForecasts: Int
    let accuracyPct: Double
    let avgErrorPct: Double?
    let bullishAccuracyPct: Double?
    let bearishAccuracyPct: Double?
    let lastEvaluation: String?

    var id: String { "\(symbol)-\(horizon)" }

    enum CodingKeys: String, CodingKey {
        case symbol
        case horizon
        case totalForecasts = "total_forecasts"
        case accuracyPct = "accuracy_pct"
        case avgErrorPct = "avg_error_pct"
        case bullishAccuracyPct = "bullish_accuracy_pct"
        case bearishAccuracyPct = "bearish_accuracy_pct"
        case lastEvaluation = "last_evaluation"
    }
}

// MARK: - Model Weight Data

struct ModelWeightData: Decodable, Identifiable {
    let id: String?
    let horizon: String
    let rfWeight: Double
    let gbWeight: Double
    let lastUpdated: String?
    let updateReason: String?
    let rfAccuracy30d: Double?
    let gbAccuracy30d: Double?

    var identifier: String { id ?? horizon }

    enum CodingKeys: String, CodingKey {
        case id
        case horizon
        case rfWeight = "rf_weight"
        case gbWeight = "gb_weight"
        case lastUpdated = "last_updated"
        case updateReason = "update_reason"
        case rfAccuracy30d = "rf_accuracy_30d"
        case gbAccuracy30d = "gb_accuracy_30d"
    }

    var rfWeightPct: Int { Int(rfWeight * 100) }
    var gbWeightPct: Int { Int(gbWeight * 100) }
}

// MARK: - Forecast Evaluation

struct ForecastEvaluation: Decodable, Identifiable {
    let id: String
    let symbol: String
    let horizon: String
    let predictedLabel: String
    let predictedValue: Double
    let predictedConfidence: Double
    let forecastDate: String
    let evaluationDate: String
    let realizedPrice: Double
    let realizedReturn: Double
    let realizedLabel: String
    let directionCorrect: Bool
    let priceError: Double
    let priceErrorPct: Double
    let rfCorrect: Bool?
    let gbCorrect: Bool?

    enum CodingKeys: String, CodingKey {
        case id
        case symbol
        case horizon
        case predictedLabel = "predicted_label"
        case predictedValue = "predicted_value"
        case predictedConfidence = "predicted_confidence"
        case forecastDate = "forecast_date"
        case evaluationDate = "evaluation_date"
        case realizedPrice = "realized_price"
        case realizedReturn = "realized_return"
        case realizedLabel = "realized_label"
        case directionCorrect = "direction_correct"
        case priceError = "price_error"
        case priceErrorPct = "price_error_pct"
        case rfCorrect = "rf_correct"
        case gbCorrect = "gb_correct"
    }

    var returnPct: Double { realizedReturn * 100 }

    var predictionColor: String {
        switch predictedLabel.lowercased() {
        case "bullish": return "green"
        case "bearish": return "red"
        default: return "orange"
        }
    }

    var resultColor: String {
        directionCorrect ? "green" : "red"
    }
}

// MARK: - Model Weights API Response

struct ModelWeightsResponse: Decodable {
    let weights: [ModelWeightInfo]

    init(from decoder: Decoder) throws {
        // Handle array response
        let container = try decoder.singleValueContainer()
        weights = try container.decode([ModelWeightInfo].self)
    }
}

struct ModelWeightInfo: Decodable, Identifiable {
    let horizon: String
    let rfWeightPct: Double
    let gbWeightPct: Double
    let rfAccuracy30dPct: Double?
    let gbAccuracy30dPct: Double?
    let lastUpdated: String
    let updateReason: String

    var id: String { horizon }

    enum CodingKeys: String, CodingKey {
        case horizon
        case rfWeightPct = "rf_weight_pct"
        case gbWeightPct = "gb_weight_pct"
        case rfAccuracy30dPct = "rf_accuracy_30d_pct"
        case gbAccuracy30dPct = "gb_accuracy_30d_pct"
        case lastUpdated = "last_updated"
        case updateReason = "update_reason"
    }
}
