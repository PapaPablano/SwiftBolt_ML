import Foundation
import SwiftUI

// MARK: - Unified Indicators Service
/// Bridges Technical Indicators data with Strategy Builder conditions
class UnifiedIndicatorsService: ObservableObject {
    static let shared = UnifiedIndicatorsService()
    
    @Published var currentIndicators: TechnicalIndicatorsResponse?
    @Published var selectedSymbol: String = "AAPL"
    @Published var selectedTimeframe: String = "d1"
    
    private let apiClient = APIClient.shared
    
    // MARK: - Indicator Registry with Strategy Conditions
    
    /// All available indicators mapped to their strategy condition configurations
    let indicatorRegistry: [IndicatorRegistryItem] = [
        // SuperTrend AI
        IndicatorRegistryItem(
            name: "SuperTrend AI",
            technicalKey: "supertrend_adaptive_factor",
            category: .supertrend,
            defaultCondition: .init(op: ">", value: 1.0, label: "Bullish (AI > 1)"),
            alternativeConditions: [
                .init(op: "<", value: 1.0, label: "Bearish (AI < 1)"),
                .init(op: ">", value: 2.0, label: "Strong Bullish (AI > 2)"),
                .init(op: ">", value: 3.0, label: "Very Strong (AI > 3)")
            ]
        ),
        IndicatorRegistryItem(
            name: "SuperTrend Trend",
            technicalKey: "supertrend_trend",
            category: .supertrend,
            defaultCondition: .init(op: "==", value: 1.0, label: "Uptrend"),
            alternativeConditions: [
                .init(op: "==", value: -1.0, label: "Downtrend")
            ]
        ),
        IndicatorRegistryItem(
            name: "SuperTrend Signal",
            technicalKey: "supertrend_signal",
            category: .supertrend,
            defaultCondition: .init(op: "==", value: 1.0, label: "Buy Signal"),
            alternativeConditions: [
                .init(op: "==", value: -1.0, label: "Sell Signal")
            ]
        ),
        
        // Momentum
        IndicatorRegistryItem(
            name: "RSI",
            technicalKey: "rsi_14",
            category: .momentum,
            defaultCondition: .init(op: "<", value: 30.0, label: "Oversold (< 30)"),
            alternativeConditions: [
                .init(op: ">", value: 70.0, label: "Overbought (> 70)"),
                .init(op: ">", value: 60.0, label: "Bullish (> 60)"),
                .init(op: "<", value: 40.0, label: "Bearish (< 40)"),
                .init(op: "<", value: 20.0, label: "Deep Oversold (< 20)")
            ]
        ),
        IndicatorRegistryItem(
            name: "MACD",
            technicalKey: "macd",
            category: .momentum,
            defaultCondition: .init(op: ">", value: 0.0, label: "Positive (Bullish)"),
            alternativeConditions: [
                .init(op: "<", value: 0.0, label: "Negative (Bearish)"),
                .init(op: "crosses_above", value: 0.0, label: "Crosses Above Zero"),
                .init(op: "crosses_below", value: 0.0, label: "Crosses Below Zero")
            ]
        ),
        IndicatorRegistryItem(
            name: "MACD Histogram",
            technicalKey: "macd_hist",
            category: .momentum,
            defaultCondition: .init(op: ">", value: 0.0, label: "Positive"),
            alternativeConditions: [
                .init(op: "<", value: 0.0, label: "Negative"),
                .init(op: ">", value: 0.05, label: "Strong Bullish"),
                .init(op: "<", value: -0.05, label: "Strong Bearish")
            ]
        ),
        IndicatorRegistryItem(
            name: "KDJ K",
            technicalKey: "kdj_k",
            category: .momentum,
            defaultCondition: .init(op: "<", value: 20.0, label: "Oversold (< 20)"),
            alternativeConditions: [
                .init(op: ">", value: 80.0, label: "Overbought (> 80)"),
                .init(op: ">", value: 50.0, label: "Above Midline")
            ]
        ),
        IndicatorRegistryItem(
            name: "MFI",
            technicalKey: "mfi_14",
            category: .momentum,
            defaultCondition: .init(op: "<", value: 20.0, label: "Oversold (< 20)"),
            alternativeConditions: [
                .init(op: ">", value: 80.0, label: "Overbought (> 80)")
            ]
        ),
        IndicatorRegistryItem(
            name: "1D Returns",
            technicalKey: "returns_1d",
            category: .momentum,
            defaultCondition: .init(op: ">", value: 0.0, label: "Positive Return"),
            alternativeConditions: [
                .init(op: "<", value: 0.0, label: "Negative Return"),
                .init(op: ">", value: 0.02, label: "Strong +2%"),
                .init(op: "<", value: -0.02, label: "Weak -2%")
            ]
        ),
        
        // Trend
        IndicatorRegistryItem(
            name: "ADX",
            technicalKey: "adx",
            category: .trend,
            defaultCondition: .init(op: ">", value: 25.0, label: "Trending (> 25)"),
            alternativeConditions: [
                .init(op: "<", value: 25.0, label: "Weak Trend (< 25)"),
                .init(op: ">", value: 40.0, label: "Strong Trend (> 40)")
            ]
        ),
        IndicatorRegistryItem(
            name: "Price vs SMA 20",
            technicalKey: "price_vs_sma_20",
            category: .trend,
            defaultCondition: .init(op: ">", value: 0.0, label: "Above SMA (Bullish)"),
            alternativeConditions: [
                .init(op: "<", value: 0.0, label: "Below SMA (Bearish)"),
                .init(op: ">", value: 0.05, label: "5% Above SMA"),
                .init(op: "<", value: -0.05, label: "5% Below SMA")
            ]
        ),
        
        // Volatility
        IndicatorRegistryItem(
            name: "ATR",
            technicalKey: "atr_14",
            category: .volatility,
            defaultCondition: .init(op: ">", value: 2.0, label: "High Volatility (> 2)"),
            alternativeConditions: [
                .init(op: "<", value: 1.0, label: "Low Volatility (< 1)")
            ]
        ),
        IndicatorRegistryItem(
            name: "Bollinger Band Width",
            technicalKey: "bb_width",
            category: .volatility,
            defaultCondition: .init(op: "<", value: 0.1, label: "Squeeze (< 0.1)"),
            alternativeConditions: [
                .init(op: ">", value: 0.2, label: "Expansion (> 0.2)")
            ]
        ),
        
        // Volume
        IndicatorRegistryItem(
            name: "Volume Ratio",
            technicalKey: "volume_ratio",
            category: .volume,
            defaultCondition: .init(op: ">", value: 1.5, label: "High Volume (> 1.5x)"),
            alternativeConditions: [
                .init(op: ">", value: 2.0, label: "Very High (> 2x)"),
                .init(op: "<", value: 0.5, label: "Low Volume (< 0.5x)")
            ]
        ),
        IndicatorRegistryItem(
            name: "OBV",
            technicalKey: "obv",
            category: .volume,
            defaultCondition: .init(op: ">", value: 0.0, label: "Rising"),
            alternativeConditions: [
                .init(op: "<", value: 0.0, label: "Falling")
            ]
        )
    ]
    
    // MARK: - Fetch Current Indicators
    
    func fetchIndicators(symbol: String, timeframe: String) async throws {
        let apiTimeframe = Timeframe(from: timeframe)?.apiToken ?? "d1"
        let response = try await apiClient.fetchTechnicalIndicators(symbol: symbol, timeframe: apiTimeframe)
        await MainActor.run {
            self.currentIndicators = response
            self.selectedSymbol = symbol
            self.selectedTimeframe = timeframe
        }
    }
    
    // MARK: - Strategy Condition Suggestions
    
    /// Get suggested conditions based on current indicator values and their bullish/bearish interpretations
    func getSuggestedConditions() -> [SuggestedCondition] {
        guard let indicators = currentIndicators?.allIndicators else { return [] }
        
        var suggestions: [SuggestedCondition] = []
        
        for indicator in indicators {
            // Find matching registry item
            guard let registryItem = indicatorRegistry.first(where: { 
                indicator.name.lowercased() == $0.technicalKey.lowercased() 
            }) else { continue }
            
            // Get interpretation
            let interp = indicator.interpretation
            
            // Suggest condition based on current interpretation
            let suggestedOp: String
            let suggestedValue: Double
            let reason: String
            
            switch interp {
            case .strongBullish, .bullish, .overbought:
                suggestedOp = ">"
                suggestedValue = indicator.value * 0.95 // Slightly below current
                reason = "Currently \(interp.displayName) at \(indicator.displayValue)"
                
            case .strongBearish, .bearish, .oversold:
                suggestedOp = "<"
                suggestedValue = indicator.value * 1.05 // Slightly above current
                reason = "Currently \(interp.displayName) at \(indicator.displayValue)"
                
            case .neutral:
                // For neutral, suggest waiting for breakout
                suggestedOp = ">"
                suggestedValue = indicator.value * 1.1
                reason = "Currently neutral - wait for breakout above \(String(format: "%.2f", suggestedValue))"
            }
            
            suggestions.append(SuggestedCondition(
                indicator: registryItem,
                currentValue: indicator.value,
                currentInterpretation: interp,
                suggestedOperator: suggestedOp,
                suggestedValue: suggestedValue,
                reason: reason
            ))
        }
        
        return suggestions.sorted {
            let lhsPriority = ($0.currentInterpretation == .bullish || $0.currentInterpretation == .strongBullish) ? 0 : 1
            let rhsPriority = ($1.currentInterpretation == .bullish || $1.currentInterpretation == .strongBullish) ? 0 : 1
            return lhsPriority < rhsPriority
        }
    }
    
    /// Create a strategy condition from a registry item with current value
    func createCondition(from registryItem: IndicatorRegistryItem, usingCurrentValue: Bool = false) -> StrategyCondition {
        let value: Double
        
        if usingCurrentValue,
           let indicators = currentIndicators?.indicators,
           let currentVal = indicators[registryItem.technicalKey] {
            value = currentVal ?? registryItem.defaultCondition.value
        } else {
            value = registryItem.defaultCondition.value
        }
        
        return StrategyCondition(
            id: UUID(),
            indicator: registryItem.name,
            operator: registryItem.defaultCondition.op,
            value: value,
            parameters: ["source_key": registryItem.technicalKey]
        )
    }
}

// MARK: - Supporting Types

struct IndicatorRegistryItem: Identifiable, Hashable {
    let id = UUID()
    let name: String
    let technicalKey: String
    let category: StrategyIndicatorCategory
    let defaultCondition: ConditionPreset
    let alternativeConditions: [ConditionPreset]
    
    var allConditions: [ConditionPreset] {
        [defaultCondition] + alternativeConditions
    }
}

struct ConditionPreset: Hashable {
    let op: String
    let value: Double
    let label: String
}

struct SuggestedCondition: Identifiable {
    let id = UUID()
    let indicator: IndicatorRegistryItem
    let currentValue: Double
    let currentInterpretation: IndicatorInterpretation
    let suggestedOperator: String
    let suggestedValue: Double
    let reason: String
}

// MARK: - IndicatorInterpretation Extension

extension IndicatorInterpretation {
    var displayName: String {
        switch self {
        case .strongBullish: return "Strong Bullish"
        case .bullish: return "Bullish"
        case .overbought: return "Overbought"
        case .neutral: return "Neutral"
        case .bearish: return "Bearish"
        case .oversold: return "Oversold"
        case .strongBearish: return "Strong Bearish"
        }
    }
    
    var signalColor: Color {
        switch self {
        case .strongBullish: return .green
        case .bullish, .overbought: return .green.opacity(0.7)
        case .neutral: return .gray
        case .bearish, .oversold: return .red.opacity(0.7)
        case .strongBearish: return .red
        }
    }
}
