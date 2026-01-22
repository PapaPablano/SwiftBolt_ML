import Foundation

// MARK: - Technical Indicators Response

struct TechnicalIndicatorsResponse: Decodable {
    let symbol: String
    let timeframe: String
    let timestamp: String
    let indicators: [String: Double?]
    let price: PriceData
    let barsUsed: Int
    let cached: Bool?
    let error: String?
    
    enum CodingKeys: String, CodingKey {
        case symbol
        case timeframe
        case timestamp
        case indicators
        case price
        case barsUsed = "bars_used"
        case cached
        case error
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        symbol = try container.decode(String.self, forKey: .symbol)
        timeframe = try container.decode(String.self, forKey: .timeframe)
        timestamp = try container.decode(String.self, forKey: .timestamp)
        price = try container.decode(PriceData.self, forKey: .price)
        barsUsed = try container.decode(Int.self, forKey: .barsUsed)
        cached = try container.decodeIfPresent(Bool.self, forKey: .cached)
        error = try container.decodeIfPresent(String.self, forKey: .error)
        
        // Decode indicators as dictionary with optional doubles
        let indicatorsContainer = try container.nestedContainer(keyedBy: DynamicCodingKeys.self, forKey: .indicators)
        var indicatorsDict: [String: Double?] = [:]
        for key in indicatorsContainer.allKeys {
            if indicatorsContainer.contains(key) && !indicatorsContainer.decodeNil(forKey: key) {
                indicatorsDict[key.stringValue] = try? indicatorsContainer.decode(Double.self, forKey: key)
            } else {
                indicatorsDict[key.stringValue] = nil
            }
        }
        indicators = indicatorsDict
    }
    
    private struct DynamicCodingKeys: CodingKey {
        var stringValue: String
        var intValue: Int?
        
        init?(stringValue: String) {
            self.stringValue = stringValue
        }
        
        init?(intValue: Int) {
            return nil
        }
    }
    
    struct PriceData: Decodable {
        let open: Double
        let high: Double
        let low: Double
        let close: Double
        let volume: Double
    }
}


// MARK: - Indicator Categories

extension TechnicalIndicatorsResponse {
    /// Group indicators by category for organized display
    var indicatorsByCategory: [IndicatorCategory: [IndicatorItem]] {
        var grouped: [IndicatorCategory: [IndicatorItem]] = [:]
        
        for (key, value) in indicators {
            if let category = IndicatorCategory.category(for: key),
               let doubleValue = value {
                let item = IndicatorItem(name: key, value: doubleValue, formattedName: IndicatorCategory.formattedName(for: key))
                grouped[category, default: []].append(item)
            }
        }
        
        // Sort items within each category
        for category in grouped.keys {
            grouped[category]?.sort { $0.formattedName < $1.formattedName }
        }
        
        return grouped
    }
    
    /// Get all indicators as a flat list
    var allIndicators: [IndicatorItem] {
        indicators.compactMap { key, value in
            guard let doubleValue = value else { return nil }
            return IndicatorItem(
                name: key,
                value: doubleValue,
                formattedName: IndicatorCategory.formattedName(for: key)
            )
        }.sorted { $0.formattedName < $1.formattedName }
    }
}

// MARK: - Indicator Item

struct IndicatorItem: Identifiable {
    let id = UUID()
    let name: String
    let value: Double
    let formattedName: String
    
    var formattedValue: String {
        if abs(value) >= 1000 {
            return String(format: "%.2f", value)
        } else if abs(value) >= 1 {
            return String(format: "%.2f", value)
        } else {
            return String(format: "%.4f", value)
        }
    }
    
    var displayValue: String {
        // Add percentage sign for certain indicators
        if name.contains("rsi") || name.contains("mfi") || name.contains("returns") || name.contains("ratio") {
            return "\(formattedValue)%"
        }
        return formattedValue
    }
}

// MARK: - Indicator Category

enum IndicatorCategory: String, CaseIterable {
    case momentum
    case volatility
    case volume
    case trend
    case price
    case other
    
    static func category(for indicatorName: String) -> IndicatorCategory? {
        let lower = indicatorName.lowercased()
        
        // Momentum indicators
        if lower.contains("rsi") || lower.contains("macd") || lower.contains("stochastic") || 
           lower.contains("kdj") || lower.contains("mfi") || lower.contains("returns") {
            return .momentum
        }
        
        // Volatility indicators
        if lower.contains("bollinger") || lower.contains("atr") || lower.contains("volatility") || 
           lower.contains("adx") || lower.contains("supertrend") {
            return .volatility
        }
        
        // Volume indicators
        if lower.contains("volume") || lower.contains("obv") || lower.contains("mfi") {
            return .volume
        }
        
        // Trend indicators
        if lower.contains("sma") || lower.contains("ema") || lower.contains("ma") || 
           lower.contains("trend") || lower.contains("adx") {
            return .trend
        }
        
        // Price indicators
        if lower.contains("price") || lower.contains("close") || lower.contains("open") || 
           lower.contains("high") || lower.contains("low") {
            return .price
        }
        
        return .other
    }
    
    static func formattedName(for indicatorName: String) -> String {
        let lower = indicatorName.lowercased()
        
        // Common replacements
        var formatted = indicatorName
            .replacingOccurrences(of: "_", with: " ")
            .replacingOccurrences(of: "rsi", with: "RSI")
            .replacingOccurrences(of: "macd", with: "MACD")
            .replacingOccurrences(of: "sma", with: "SMA")
            .replacingOccurrences(of: "ema", with: "EMA")
            .replacingOccurrences(of: "atr", with: "ATR")
            .replacingOccurrences(of: "adx", with: "ADX")
            .replacingOccurrences(of: "mfi", with: "MFI")
            .replacingOccurrences(of: "obv", with: "OBV")
            .replacingOccurrences(of: "kdj", with: "KDJ")
            .replacingOccurrences(of: "supertrend", with: "SuperTrend")
        
        // Capitalize first letter
        if !formatted.isEmpty {
            formatted = formatted.prefix(1).uppercased() + formatted.dropFirst()
        }
        
        return formatted
    }
    
    var displayName: String {
        switch self {
        case .momentum: return "Momentum"
        case .volatility: return "Volatility"
        case .volume: return "Volume"
        case .trend: return "Trend"
        case .price: return "Price"
        case .other: return "Other"
        }
    }
    
    var icon: String {
        switch self {
        case .momentum: return "arrow.up.arrow.down"
        case .volatility: return "waveform.path"
        case .volume: return "chart.bar"
        case .trend: return "chart.line.uptrend.xyaxis"
        case .price: return "dollarsign.circle"
        case .other: return "list.bullet"
        }
    }
}

// MARK: - Indicator Interpretation

extension IndicatorItem {
    /// Get interpretation/signal for the indicator value
    var interpretation: IndicatorInterpretation {
        let lower = name.lowercased()
        
        // RSI interpretation
        if lower.contains("rsi") {
            if value > 70 {
                return .overbought
            } else if value < 30 {
                return .oversold
            } else {
                return .neutral
            }
        }
        
        // MACD interpretation
        if lower.contains("macd_hist") {
            if value > 0 {
                return .bullish
            } else {
                return .bearish
            }
        }
        
        // Price vs SMA interpretation
        if lower.contains("price_vs_sma") {
            if value > 0.02 { // > 2% above SMA
                return .bullish
            } else if value < -0.02 { // < -2% below SMA
                return .bearish
            } else {
                return .neutral
            }
        }
        
        // Volume ratio interpretation
        if lower.contains("volume_ratio") {
            if value > 1.5 {
                return .bullish // High volume
            } else if value < 0.5 {
                return .bearish // Low volume
            } else {
                return .neutral
            }
        }
        
        return .neutral
    }
}

enum IndicatorInterpretation {
    case bullish
    case bearish
    case neutral
    case overbought
    case oversold
    
    var color: String {
        switch self {
        case .bullish: return "green"
        case .bearish: return "red"
        case .neutral: return "gray"
        case .overbought: return "orange"
        case .oversold: return "blue"
        }
    }
    
    var label: String {
        switch self {
        case .bullish: return "Bullish"
        case .bearish: return "Bearish"
        case .neutral: return "Neutral"
        case .overbought: return "Overbought"
        case .oversold: return "Oversold"
        }
    }
}
