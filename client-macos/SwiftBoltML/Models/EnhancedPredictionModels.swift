import Foundation

// MARK: - Multi-Timeframe Consensus Models

struct MultiTimeframeConsensus: Codable {
    let signal: String
    let confidence: Double
    let bullishCount: Int
    let bearishCount: Int
    let dominantTf: String?
    let signalValue: Double?
    let timeframeBreakdown: [TimeframeSignal]
    
    enum CodingKeys: String, CodingKey {
        case signal
        case confidence = "consensus_confidence"
        case bullishCount = "bullish_count"
        case bearishCount = "bearish_count"
        case dominantTf = "dominant_tf"
        case signalValue = "signal_value"
        case timeframeBreakdown = "timeframe_breakdown"
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        signal = try container.decode(String.self, forKey: .signal)
        confidence = try container.decodeIfPresent(Double.self, forKey: .confidence) ?? 0.0
        bullishCount = try container.decodeIfPresent(Int.self, forKey: .bullishCount) ?? 0
        bearishCount = try container.decodeIfPresent(Int.self, forKey: .bearishCount) ?? 0
        dominantTf = try container.decodeIfPresent(String.self, forKey: .dominantTf)
        signalValue = try container.decodeIfPresent(Double.self, forKey: .signalValue)
        timeframeBreakdown = try container.decodeIfPresent([TimeframeSignal].self, forKey: .timeframeBreakdown) ?? []
    }
    
    init(signal: String, confidence: Double, bullishCount: Int, bearishCount: Int, dominantTf: String?, signalValue: Double?, timeframeBreakdown: [TimeframeSignal]) {
        self.signal = signal
        self.confidence = confidence
        self.bullishCount = bullishCount
        self.bearishCount = bearishCount
        self.dominantTf = dominantTf
        self.signalValue = signalValue
        self.timeframeBreakdown = timeframeBreakdown
    }
}

struct TimeframeSignal: Codable {
    let timeframe: String
    let signal: String
    let rsi: Double?
}

// MARK: - Forecast Explanation Models

struct ForecastExplanation: Codable {
    let summary: String
    let topFeatures: [FeatureContribution]
    let signalBreakdown: [SignalCategory]
    let riskFactors: [String]
    let supportingEvidence: [String]
    let contradictingEvidence: [String]
    let recommendation: String
    let prediction: String
    
    enum CodingKeys: String, CodingKey {
        case summary
        case topFeatures = "top_features"
        case signalBreakdown = "signal_breakdown"
        case riskFactors = "risk_factors"
        case supportingEvidence = "supporting_evidence"
        case contradictingEvidence = "contradicting_evidence"
        case recommendation
        case prediction
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        summary = try container.decodeIfPresent(String.self, forKey: .summary) ?? ""
        topFeatures = try container.decodeIfPresent([FeatureContribution].self, forKey: .topFeatures) ?? []
        signalBreakdown = try container.decodeIfPresent([SignalCategory].self, forKey: .signalBreakdown) ?? []
        riskFactors = try container.decodeIfPresent([String].self, forKey: .riskFactors) ?? []
        supportingEvidence = try container.decodeIfPresent([String].self, forKey: .supportingEvidence) ?? []
        contradictingEvidence = try container.decodeIfPresent([String].self, forKey: .contradictingEvidence) ?? []
        recommendation = try container.decodeIfPresent(String.self, forKey: .recommendation) ?? ""
        prediction = try container.decodeIfPresent(String.self, forKey: .prediction) ?? "neutral"
    }
    
    init(summary: String, topFeatures: [FeatureContribution], signalBreakdown: [SignalCategory], riskFactors: [String], supportingEvidence: [String], contradictingEvidence: [String], recommendation: String, prediction: String) {
        self.summary = summary
        self.topFeatures = topFeatures
        self.signalBreakdown = signalBreakdown
        self.riskFactors = riskFactors
        self.supportingEvidence = supportingEvidence
        self.contradictingEvidence = contradictingEvidence
        self.recommendation = recommendation
        self.prediction = prediction
    }
}

struct FeatureContribution: Codable {
    let name: String
    let value: Double?
    let direction: String
    let description: String
}

struct SignalCategory: Codable {
    let category: String
    let signal: String
    let strength: Double
    let description: String
}

// MARK: - Data Quality Models

struct DataQualityReport: Codable {
    let healthScore: Double
    let totalRows: Int
    let totalColumns: Int
    let totalNans: Int
    let columnsWithIssues: Int
    let severity: String
    let columnIssues: [ColumnIssue]
    let warnings: [String]
    let isClean: Bool
    
    enum CodingKeys: String, CodingKey {
        case healthScore = "health_score"
        case totalRows = "total_rows"
        case totalColumns = "total_columns"
        case totalNans = "total_nans"
        case columnsWithIssues = "columns_with_issues"
        case severity
        case columnIssues = "column_issues"
        case warnings
        case isClean = "is_clean"
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        healthScore = try container.decodeIfPresent(Double.self, forKey: .healthScore) ?? 1.0
        totalRows = try container.decodeIfPresent(Int.self, forKey: .totalRows) ?? 0
        totalColumns = try container.decodeIfPresent(Int.self, forKey: .totalColumns) ?? 0
        totalNans = try container.decodeIfPresent(Int.self, forKey: .totalNans) ?? 0
        columnsWithIssues = try container.decodeIfPresent(Int.self, forKey: .columnsWithIssues) ?? 0
        severity = try container.decodeIfPresent(String.self, forKey: .severity) ?? "clean"
        columnIssues = try container.decodeIfPresent([ColumnIssue].self, forKey: .columnIssues) ?? []
        warnings = try container.decodeIfPresent([String].self, forKey: .warnings) ?? []
        isClean = try container.decodeIfPresent(Bool.self, forKey: .isClean) ?? true
    }
    
    init(healthScore: Double, totalRows: Int, totalColumns: Int, totalNans: Int, columnsWithIssues: Int, severity: String, columnIssues: [ColumnIssue], warnings: [String], isClean: Bool) {
        self.healthScore = healthScore
        self.totalRows = totalRows
        self.totalColumns = totalColumns
        self.totalNans = totalNans
        self.columnsWithIssues = columnsWithIssues
        self.severity = severity
        self.columnIssues = columnIssues
        self.warnings = warnings
        self.isClean = isClean
    }
}

struct ColumnIssue: Codable {
    let column: String
    let nanCount: Int
    let nanPct: Double
    let severity: String
    
    enum CodingKeys: String, CodingKey {
        case column
        case nanCount = "nan_count"
        case nanPct = "nan_pct"
        case severity
    }
}
