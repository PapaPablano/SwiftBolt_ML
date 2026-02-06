import Foundation

struct ChartResponse: Codable, Equatable {
    let symbol: String
    let assetType: String
    let timeframe: String
    let bars: [OHLCBar]
    let mlSummary: MLSummary?
    let indicators: IndicatorData?
    let superTrendAI: SuperTrendAIData?
    let dataQuality: DataQuality?
    let refresh: ChartReadRefresh?

    enum CodingKeys: String, CodingKey {
        case symbol
        case assetType = "assetType"
        case timeframe
        case bars
        case mlSummary
        case indicators
        case superTrendAI = "supertrend_ai"
        case dataQuality
        case refresh
    }
}

struct ChartReadRefresh: Codable, Equatable {
    let attempted: Bool
    let timeframe: String
    let symbol: String
    let enqueuedTimeframes: [String]?
    let insertedSlices: Int?
    let error: String?
}

// MARK: - SuperTrend AI Data

/// Full SuperTrend AI data from backend with signals and metadata
struct SuperTrendAIData: Codable, Equatable {
    let factor: Double
    let performanceIndex: Double
    let signalStrength: Int  // 0-10
    let currentTrend: String  // "BULLISH" or "BEARISH"
    let currentStopLevel: Double
    let trendDurationBars: Int
    let signals: [SignalMetadata]

    enum CodingKeys: String, CodingKey {
        case factor
        case performanceIndex = "performance_index"
        case signalStrength = "signal_strength"
        case currentTrend = "current_trend"
        case currentStopLevel = "current_stop_level"
        case trendDurationBars = "trend_duration_bars"
        case signals
    }
}

/// Metadata for individual SuperTrend signals
struct SignalMetadata: Codable, Equatable, Identifiable {
    var id: String { "\(date)-\(type)" }

    let date: String
    let type: String  // "BUY" or "SELL"
    let price: Double
    let confidence: Int  // 0-10
    let stopLevel: Double
    let targetPrice: Double
    let atrAtSignal: Double

    enum CodingKeys: String, CodingKey {
        case date
        case type
        case price
        case confidence
        case stopLevel = "stop_level"
        case targetPrice = "target_price"
        case atrAtSignal = "atr_at_signal"
    }
}

// MARK: - Indicator Data

/// Pre-computed indicator data from backend (optional)
struct IndicatorData: Codable, Equatable {
    // SuperTrend AI results (legacy - use SuperTrendAIData for full data)
    let supertrendFactor: Double?
    let supertrendPerformance: Double?
    let supertrendSignal: Int?  // 1 = bullish, -1 = bearish

    // Trend analysis
    let trendLabel: String?  // bullish, neutral, bearish
    let trendConfidence: Int?
    let stopLevel: Double?
    let trendDurationBars: Int?

    // Key indicator values (latest)
    let rsi: Double?
    let adx: Double?
    let macdHistogram: Double?
    let kdjJ: Double?

    enum CodingKeys: String, CodingKey {
        case supertrendFactor = "supertrend_factor"
        case supertrendPerformance = "supertrend_performance"
        case supertrendSignal = "supertrend_signal"
        case trendLabel = "trend_label"
        case trendConfidence = "trend_confidence"
        case stopLevel = "stop_level"
        case trendDurationBars = "trend_duration_bars"
        case rsi
        case adx
        case macdHistogram = "macd_histogram"
        case kdjJ = "kdj_j"
    }
}

struct MLSummary: Codable, Equatable {
    let overallLabel: String?
    let confidence: Double
    let horizons: [ForecastSeries]
    let srLevels: SRLevels?
    let srDensity: Int?

    // Enhanced ensemble fields (optional - present when ENABLE_ENHANCED_ENSEMBLE=true)
    let ensembleType: String?  // "RF+GB" or "Enhanced5"
    let modelAgreement: Double?  // 0-1, how much models agree
    let trainingStats: TrainingStats?

    var isEnhancedEnsemble: Bool {
        ensembleType == "Enhanced5"
    }
}

// MARK: - Training Stats (Enhanced Ensemble)

struct TrainingStats: Codable, Equatable {
    // Basic stats
    let trainingTimeSeconds: Double?
    let nSamples: Int?
    let nFeatures: Int?

    // Model weights
    let rfWeight: Double?
    let gbWeight: Double?
    let modelWeights: [String: Double]?

    // Enhanced ensemble specific
    let enhancedEnsemble: Bool?
    let nModels: Int?
    let componentPredictions: [String: String]?
    let forecastReturn: Double?
    let forecastVolatility: Double?
    let ciLower: Double?
    let ciUpper: Double?

    enum CodingKeys: String, CodingKey {
        case trainingTimeSeconds = "training_time_seconds"
        case nSamples = "n_samples"
        case nFeatures = "n_features"
        case rfWeight = "rf_weight"
        case gbWeight = "gb_weight"
        case modelWeights = "model_weights"
        case enhancedEnsemble = "enhanced_ensemble"
        case nModels = "n_models"
        case componentPredictions = "component_predictions"
        case forecastReturn = "forecast_return"
        case forecastVolatility = "forecast_volatility"
        case ciLower = "ci_lower"
        case ciUpper = "ci_upper"
    }

    /// Returns sorted model weights for display
    var sortedWeights: [(model: String, weight: Double)] {
        guard let weights = modelWeights else {
            // Fallback to RF/GB weights
            var result: [(String, Double)] = []
            if let rf = rfWeight { result.append(("rf", rf)) }
            if let gb = gbWeight { result.append(("gb", gb)) }
            return result.sorted { $0.1 > $1.1 }
        }
        return weights.map { ($0.key, $0.value) }.sorted { $0.1 > $1.1 }
    }

    /// Model display name
    func displayName(for model: String) -> String {
        switch model.lowercased() {
        case "rf": return "Random Forest"
        case "gb": return "Gradient Boost"
        case "arima_garch": return "ARIMA-GARCH"
        case "prophet": return "Prophet"
        case "lstm": return "LSTM"
        default: return model.uppercased()
        }
    }
}

struct ForecastSeries: Codable, Equatable {
    let horizon: String
    let points: [ForecastPoint]
    let targets: ForecastTargets?
}

struct ForecastTargets: Codable, Equatable {
    let tp1: Double?
    let tp2: Double?
    let tp3: Double?
    let stopLoss: Double?
    let qualityScore: Double?
    let confluenceScore: Double?

    enum CodingKeys: String, CodingKey {
        case tp1
        case tp2
        case tp3
        case stopLoss = "stop_loss"
        case qualityScore = "quality_score"
        case confluenceScore = "confluence_score"
    }
}

struct ForecastPoint: Codable, Equatable {
    let ts: Int
    let value: Double
    let lower: Double
    let upper: Double

    enum CodingKeys: String, CodingKey {
        case ts, value, lower, upper, price
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        // Handle ts as either Int or String
        if let intValue = try? container.decode(Int.self, forKey: .ts) {
            ts = intValue
        } else if let stringValue = try? container.decode(String.self, forKey: .ts) {
            // Try parsing as integer timestamp
            if let parsed = Int(stringValue) {
                ts = parsed
            } else {
                // Try parsing as ISO8601 date string
                let formatter = ISO8601DateFormatter()
                formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
                if let date = formatter.date(from: stringValue) {
                    ts = Int(date.timeIntervalSince1970)
                } else {
                    // Try without fractional seconds
                    formatter.formatOptions = [.withInternetDateTime]
                    if let date = formatter.date(from: stringValue) {
                        ts = Int(date.timeIntervalSince1970)
                    } else {
                        throw DecodingError.dataCorruptedError(forKey: .ts, in: container, debugDescription: "Cannot parse ts as Int or Date string: \(stringValue)")
                    }
                }
            }
        } else {
            throw DecodingError.dataCorruptedError(forKey: .ts, in: container, debugDescription: "ts must be Int or String")
        }

        if let decodedValue = try? container.decode(Double.self, forKey: .value) {
            value = decodedValue
        } else if let decodedPrice = try? container.decode(Double.self, forKey: .price) {
            value = decodedPrice
        } else {
            throw DecodingError.dataCorruptedError(forKey: .value, in: container, debugDescription: "Missing value/price for forecast point")
        }

        lower = (try? container.decode(Double.self, forKey: .lower)) ?? value
        upper = (try? container.decode(Double.self, forKey: .upper)) ?? value
    }

    init(ts: Int, value: Double, lower: Double, upper: Double) {
        self.ts = ts
        self.value = value
        self.lower = lower
        self.upper = upper
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(ts, forKey: .ts)
        try container.encode(value, forKey: .value)
        try container.encode(lower, forKey: .lower)
        try container.encode(upper, forKey: .upper)
    }
}

// MARK: - Binary Forecast API Response

/// Response from POST /api/v1/forecast/binary.
struct BinaryForecastResponse: Decodable {
    struct Horizon: Decodable {
        let horizon_days: Int
        let label: String
        let confidence: Double
        let probabilities: [String: Double]

        init(horizon_days: Int, label: String, confidence: Double, probabilities: [String: Double]) {
            self.horizon_days = horizon_days
            self.label = label
            self.confidence = confidence
            self.probabilities = probabilities
        }
    }
    let symbol: String
    let horizons: [Horizon]

    init(symbol: String, horizons: [Horizon]) {
        self.symbol = symbol
        self.horizons = horizons
    }
}

// MARK: - Binary Forecast Overlay

/// Single up/down forecast for chart overlay (from FastAPI /forecast or Supabase ml_binary_forecasts).
struct BinaryForecastOverlay: Codable, Equatable {
    let symbol: String
    let horizonDays: Int
    let label: String       // "up" or "down"
    let confidence: Double
    let probUp: Double
    let probDown: Double
    let forecastDate: Date

    enum CodingKeys: String, CodingKey {
        case symbol
        case horizonDays = "horizon_days"
        case label
        case predicted_label
        case confidence
        case probUp = "prob_up"
        case probDown = "prob_down"
        case forecastDate = "forecast_date"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        symbol = try container.decode(String.self, forKey: .symbol)
        horizonDays = try container.decode(Int.self, forKey: .horizonDays)

        if let decodedLabel = try container.decodeIfPresent(String.self, forKey: .label) {
            label = decodedLabel
        } else if let decodedPredicted = try container.decodeIfPresent(String.self, forKey: .predicted_label) {
            label = decodedPredicted
        } else {
            throw DecodingError.keyNotFound(
                CodingKeys.label,
                DecodingError.Context(codingPath: container.codingPath, debugDescription: "Missing label/predicted_label")
            )
        }

        confidence = try container.decode(Double.self, forKey: .confidence)
        probUp = try container.decode(Double.self, forKey: .probUp)
        probDown = try container.decode(Double.self, forKey: .probDown)
        let dateStr = try container.decode(String.self, forKey: .forecastDate)
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        forecastDate = formatter.date(from: dateStr) ?? ISO8601DateFormatter().date(from: dateStr) ?? Date()
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(symbol, forKey: .symbol)
        try container.encode(horizonDays, forKey: .horizonDays)
        try container.encode(label, forKey: .label)
        try container.encode(confidence, forKey: .confidence)
        try container.encode(probUp, forKey: .probUp)
        try container.encode(probDown, forKey: .probDown)

        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let iso = formatter.string(from: forecastDate)
        try container.encode(iso, forKey: .forecastDate)
    }

    init(symbol: String, horizonDays: Int, label: String, confidence: Double, probUp: Double, probDown: Double, forecastDate: Date) {
        self.symbol = symbol
        self.horizonDays = horizonDays
        self.label = label
        self.confidence = confidence
        self.probUp = probUp
        self.probDown = probDown
        self.forecastDate = forecastDate
    }
}
