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
            if indicatorsContainer.contains(key) {
                if try indicatorsContainer.decodeNil(forKey: key) {
                    indicatorsDict[key.stringValue] = nil
                } else {
                    indicatorsDict[key.stringValue] = try? indicatorsContainer.decode(Double.self, forKey: key)
                }
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
    /// For "SuperTrend AI Factor" we show one row; prefer this key when multiple exist.
    private static let superTrendFactorKeyOrder = ["supertrend_adaptive_factor", "supertrend_factor", "target_factor"]

    /// Resolve which factor key to show (one of supertrend_adaptive_factor, supertrend_factor, target_factor).
    private func preferredSuperTrendFactorKey() -> String? {
        for k in Self.superTrendFactorKeyOrder {
            guard let key = indicators.keys.first(where: { $0.lowercased() == k }),
                  indicators[key] != nil else { continue }
            return key
        }
        return nil
    }

    /// Group indicators by category for organized display
    var indicatorsByCategory: [IndicatorCategory: [IndicatorItem]] {
        var grouped: [IndicatorCategory: [IndicatorItem]] = [:]
        let preferredFactorKey = preferredSuperTrendFactorKey()

        for (key, value) in indicators {
            if let category = IndicatorCategory.category(for: key),
               let doubleValue = value {
                let formatted = IndicatorCategory.formattedName(for: key)
                if formatted == "SuperTrend AI Factor", let pref = preferredFactorKey, key.lowercased() != pref.lowercased() {
                    continue
                }
                let item = IndicatorItem(name: key, value: doubleValue, formattedName: formatted, allIndicators: indicators)
                grouped[category, default: []].append(item)
            }
        }

        for category in grouped.keys {
            grouped[category]?.sort { $0.formattedName < $1.formattedName }
        }
        return grouped
    }

    /// Get all indicators as a flat list (one SuperTrend AI Factor row when multiple keys exist)
    var allIndicators: [IndicatorItem] {
        let preferredFactorKey = preferredSuperTrendFactorKey()
        return indicators.compactMap { key, value -> IndicatorItem? in
            guard let doubleValue = value else { return nil }
            let formatted = IndicatorCategory.formattedName(for: key)
            if formatted == "SuperTrend AI Factor", let pref = preferredFactorKey, key.lowercased() != pref.lowercased() {
                return nil
            }
            return IndicatorItem(
                name: key,
                value: doubleValue,
                formattedName: formatted,
                allIndicators: indicators
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
    /// Full indicator dict for context-dependent interpretation (volume+price, ADX+DI, MACD prev). Nil = use value-only fallbacks.
    var allIndicators: [String: Double?]? = nil
    
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
        // Ratio/percent indicators: show with % (price_vs_sma is decimal e.g. 0.02 = 2%)
        if name.lowercased().contains("price_vs_sma") {
            return String(format: "%.2f%%", value * 100)
        }
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
        
        // Volatility indicators (incl. SuperTrend AI factor)
        if lower.contains("bollinger") || lower.contains("atr") || lower.contains("volatility") ||
           lower.contains("adx") || lower.contains("supertrend") || lower == "target_factor" {
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
        // SuperTrend AI adaptive factor (K-means) — single clear label for panel
        if lower == "supertrend_factor" || lower == "supertrend_adaptive_factor" || lower == "target_factor" {
            return "SuperTrend AI Factor"
        }
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
// Thresholds aligned with docs/technicalsummary.md (Refined Bull/Bear/Neutral)

extension IndicatorItem {
    /// Look up another indicator value (case-insensitive key).
    private func indicator(_ key: String) -> Double? {
        guard let all = allIndicators else { return nil }
        let k = key.lowercased()
        for (name, val) in all {
            if name.lowercased() == k, let v = val { return v }
        }
        return nil
    }

    /// Get interpretation/signal for the indicator value (uses allIndicators when available).
    var interpretation: IndicatorInterpretation {
        let lower = name.lowercased()

        // RSI (14) — trending-market bands per technical summary
        if lower.contains("rsi") {
            if value > 70 { return .strongBullish }
            if value > 60 { return .bullish }
            if value > 40 { return .neutral }
            if value > 30 { return .bearish }
            return .strongBearish
        }

        // MACD histogram — Strong vs Regular using previous bar when available
        if lower.contains("macd_hist") {
            let prevHist = indicator("macd_hist_prev")
            if let prev = prevHist {
                let increasing = value > prev
                if value > 0 {
                    return increasing ? .strongBullish : .bullish
                }
                if value < 0 {
                    return increasing ? .bearish : .strongBearish
                }
                return .neutral
            }
            // Fallback: no previous histogram
            if value > 0 { return .bullish }
            if value < 0 { return .bearish }
            return .neutral
        }

        // Price vs SMA — 5-level distance bands (>+5%, +2–5%, ±2%, -2–-5%, <-5%)
        if lower.contains("price_vs_sma") {
            if value > 0.05 { return .strongBullish }
            if value > 0.02 { return .bullish }
            if value >= -0.02 && value <= 0.02 { return .neutral }
            if value < -0.05 { return .strongBearish }
            if value < -0.02 { return .bearish }
            return .neutral
        }

        // Volume ratio — MUST use price direction (technical summary)
        if lower.contains("volume_ratio") {
            let priceChange = indicator("returns_1d") ?? indicator("return_1d")
            if let dir = priceChange {
                if value > 2.0 {
                    if dir > 0 { return .strongBullish }
                    if dir < 0 { return .strongBearish }
                    return .neutral
                }
                if value > 1.5 {
                    if dir > 0 { return .bullish }
                    if dir < 0 { return .bearish }
                    return .neutral
                }
            }
            if value < 0.5 { return .neutral }
            return .neutral
        }

        // MFI (14) — 30–70 Neutral, 70–80 Bearish, >80 Strong Bearish
        if lower.contains("mfi") {
            if value < 20 { return .strongBullish }
            if value < 30 { return .bullish }
            if value <= 70 { return .neutral }
            if value <= 80 { return .bearish }
            return .strongBearish
        }

        // Williams %R
        if lower.contains("williams") || lower.contains("williams_r") {
            if value < -80 { return .bullish }
            if value < -50 { return .bullish }
            if value < -20 { return .neutral }
            return .bearish
        }

        // CCI
        if lower.contains("cci") {
            if value < -200 { return .strongBullish }
            if value < -100 { return .bullish }
            if value >= -100 && value <= 100 { return .neutral }
            if value <= 200 { return .bearish }
            return .strongBearish
        }

        // SuperTrend AI Factor (K-means adaptive ATR multiplier, 1.0–5.0) — informational
        if lower == "supertrend_factor" || lower == "supertrend_adaptive_factor" || lower == "target_factor" {
            return .neutral
        }

        // ADX + +DI/-DI — direction from DI spread when available
        if lower.contains("adx") {
            guard let plusDI = indicator("plus_di"), let minusDI = indicator("minus_di") else {
                return .neutral
            }
            let diSpread = plusDI - minusDI
            if value < 20 { return .neutral }
            if value < 25 { return .neutral }
            if value > 40 {
                if diSpread > 5 { return .strongBullish }
                if diSpread < -5 { return .strongBearish }
                return .neutral
            }
            if diSpread > 0 { return .bullish }
            if diSpread < 0 { return .bearish }
            return .neutral
        }

        return .neutral
    }
}

enum IndicatorInterpretation {
    case strongBullish
    case bullish
    case neutral
    case bearish
    case strongBearish
    case overbought  // legacy / display alias
    case oversold   // legacy / display alias
    
    var color: String {
        switch self {
        case .strongBullish: return "green"
        case .bullish: return "green"
        case .neutral: return "gray"
        case .bearish: return "red"
        case .strongBearish: return "red"
        case .overbought: return "orange"
        case .oversold: return "blue"
        }
    }
    
    var label: String {
        switch self {
        case .strongBullish: return "Strong Bullish"
        case .bullish: return "Bullish"
        case .neutral: return "Neutral"
        case .bearish: return "Bearish"
        case .strongBearish: return "Strong Bearish"
        case .overbought: return "Overbought"
        case .oversold: return "Oversold"
        }
    }
}
