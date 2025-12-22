import SwiftUI

// MARK: - Forecast Explainer View

struct ForecastExplainerView: View {
    let explanation: ForecastExplanation
    @State private var isExpanded = false
    
    private var predictionColor: Color {
        switch explanation.prediction.lowercased() {
        case "bullish", "buy":
            return .green
        case "bearish", "sell":
            return .red
        default:
            return .orange
        }
    }
    
    private var predictionIcon: String {
        switch explanation.prediction.lowercased() {
        case "bullish", "buy":
            return "brain.head.profile"
        case "bearish", "sell":
            return "brain.head.profile"
        default:
            return "brain.head.profile"
        }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Compact header
            Button(action: { isExpanded.toggle() }) {
                HStack(spacing: 12) {
                    // Icon
                    Image(systemName: predictionIcon)
                        .foregroundStyle(.purple)
                        .font(.title3)
                    
                    VStack(alignment: .leading, spacing: 2) {
                        HStack(spacing: 6) {
                            Text("Why This Prediction")
                                .font(.caption.bold())
                                .foregroundStyle(.primary)
                            
                            Divider()
                                .frame(height: 12)
                            
                            Text(explanation.prediction.uppercased())
                                .font(.caption.bold())
                                .foregroundStyle(predictionColor)
                        }
                        
                        Text(explanation.summary.prefix(60) + (explanation.summary.count > 60 ? "..." : ""))
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                    }
                    
                    Spacer()
                    
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .buttonStyle(.plain)
            
            // Expanded details
            if isExpanded {
                Divider()
                    .padding(.vertical, 8)
                
                ExplanationDetailsView(explanation: explanation, predictionColor: predictionColor)
                    .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color(nsColor: .controlBackgroundColor))
                .shadow(color: .black.opacity(0.1), radius: 4, x: 0, y: 2)
        )
        .animation(.easeInOut(duration: 0.2), value: isExpanded)
    }
}

// MARK: - Explanation Details View

struct ExplanationDetailsView: View {
    let explanation: ForecastExplanation
    let predictionColor: Color
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Full summary
            Text(explanation.summary)
                .font(.caption)
                .foregroundStyle(.primary)
                .padding(8)
                .background(Color.gray.opacity(0.1))
                .cornerRadius(6)
            
            // Signal breakdown
            if !explanation.signalBreakdown.isEmpty {
                SignalBreakdownSection(breakdown: explanation.signalBreakdown)
            }
            
            // Top features
            if !explanation.topFeatures.isEmpty {
                TopFeaturesSection(features: explanation.topFeatures)
            }
            
            // Risk factors
            if !explanation.riskFactors.isEmpty {
                RiskFactorsSection(risks: explanation.riskFactors)
            }
            
            // Evidence
            EvidenceSection(
                supporting: explanation.supportingEvidence,
                contradicting: explanation.contradictingEvidence
            )
            
            // Recommendation
            RecommendationBanner(
                recommendation: explanation.recommendation,
                color: predictionColor
            )
        }
    }
}

// MARK: - Signal Breakdown Section

struct SignalBreakdownSection: View {
    let breakdown: [SignalCategory]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Signal Breakdown")
                .font(.caption.bold())
                .foregroundStyle(.secondary)
            
            ForEach(breakdown, id: \.category) { category in
                SignalCategoryRow(category: category)
            }
        }
    }
}

struct SignalCategoryRow: View {
    let category: SignalCategory
    
    private var signalColor: Color {
        switch category.signal.lowercased() {
        case "bullish", "buy":
            return .green
        case "bearish", "sell":
            return .red
        default:
            return .orange
        }
    }
    
    private var categoryIcon: String {
        switch category.category.lowercased() {
        case "trend":
            return "chart.line.uptrend.xyaxis"
        case "momentum":
            return "speedometer"
        case "volatility":
            return "waveform.path.ecg"
        case "volume":
            return "chart.bar.fill"
        default:
            return "chart.pie"
        }
    }
    
    var body: some View {
        HStack {
            Image(systemName: categoryIcon)
                .font(.caption)
                .foregroundStyle(.secondary)
                .frame(width: 16)
            
            Text(category.category.capitalized)
                .font(.caption)
                .frame(width: 70, alignment: .leading)
            
            HStack(spacing: 4) {
                Circle()
                    .fill(signalColor)
                    .frame(width: 6, height: 6)
                Text(category.signal.uppercased())
                    .font(.caption2.bold())
                    .foregroundStyle(signalColor)
            }
            .frame(width: 70, alignment: .leading)
            
            Spacer()
            
            // Strength bar
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Color.gray.opacity(0.2))
                    
                    RoundedRectangle(cornerRadius: 2)
                        .fill(signalColor.opacity(0.7))
                        .frame(width: geometry.size.width * category.strength)
                }
            }
            .frame(width: 50, height: 4)
            
            Text("\(Int(category.strength * 100))%")
                .font(.caption2.monospacedDigit())
                .foregroundStyle(.secondary)
                .frame(width: 30, alignment: .trailing)
        }
    }
}

// MARK: - Top Features Section

struct TopFeaturesSection: View {
    let features: [FeatureContribution]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Key Drivers")
                .font(.caption.bold())
                .foregroundStyle(.secondary)
            
            ForEach(features.prefix(3), id: \.name) { feature in
                FeatureRow(feature: feature)
            }
        }
    }
}

struct FeatureRow: View {
    let feature: FeatureContribution
    
    private var directionColor: Color {
        switch feature.direction.lowercased() {
        case "bullish":
            return .green
        case "bearish":
            return .red
        default:
            return .gray
        }
    }
    
    var body: some View {
        HStack {
            Circle()
                .fill(directionColor)
                .frame(width: 6, height: 6)
            
            Text(feature.description)
                .font(.caption2)
                .foregroundStyle(.primary)
                .lineLimit(1)
            
            Spacer()
        }
        .padding(.vertical, 2)
    }
}

// MARK: - Risk Factors Section

struct RiskFactorsSection: View {
    let risks: [String]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 4) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.caption)
                    .foregroundStyle(.yellow)
                Text("Risk Factors")
                    .font(.caption.bold())
                    .foregroundStyle(.secondary)
            }
            
            ForEach(risks, id: \.self) { risk in
                HStack(alignment: .top, spacing: 6) {
                    Text("•")
                        .font(.caption2)
                        .foregroundStyle(.yellow)
                    Text(risk)
                        .font(.caption2)
                        .foregroundStyle(.primary)
                }
            }
        }
        .padding(8)
        .background(Color.yellow.opacity(0.1))
        .cornerRadius(6)
    }
}

// MARK: - Evidence Section

struct EvidenceSection: View {
    let supporting: [String]
    let contradicting: [String]
    
    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            // Supporting
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 4) {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.caption2)
                        .foregroundStyle(.green)
                    Text("Supporting")
                        .font(.caption2.bold())
                        .foregroundStyle(.green)
                }
                
                ForEach(supporting.prefix(2), id: \.self) { evidence in
                    Text("• " + evidence)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            
            // Contradicting
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 4) {
                    Image(systemName: "xmark.circle.fill")
                        .font(.caption2)
                        .foregroundStyle(.red)
                    Text("Contradicting")
                        .font(.caption2.bold())
                        .foregroundStyle(.red)
                }
                
                ForEach(contradicting.prefix(2), id: \.self) { evidence in
                    Text("• " + evidence)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

// MARK: - Recommendation Banner

struct RecommendationBanner: View {
    let recommendation: String
    let color: Color
    
    var body: some View {
        HStack {
            Image(systemName: "lightbulb.fill")
                .font(.caption)
                .foregroundStyle(color)
            
            Text(recommendation)
                .font(.caption.bold())
                .foregroundStyle(.primary)
            
            Spacer()
        }
        .padding(10)
        .background(color.opacity(0.15))
        .cornerRadius(8)
    }
}

// MARK: - Preview
// Note: Data models (ForecastExplanation, FeatureContribution, SignalCategory) are defined in Models/EnhancedPredictionModels.swift

#Preview {
    ForecastExplainerView(explanation: ForecastExplanation(
        summary: "AAPL shows a BULLISH outlook with high confidence (78%). 3/4 indicator categories support this view. Key driver: RSI at 68 indicates overbought but strengthening momentum.",
        topFeatures: [
            FeatureContribution(name: "rsi_14_d1", value: 68.0, direction: "bullish", description: "RSI at 68 indicates overbought but strengthening"),
            FeatureContribution(name: "macd_d1", value: 1.2, direction: "bullish", description: "MACD at 1.20 shows bullish momentum"),
            FeatureContribution(name: "adx_d1", value: 32.0, direction: "neutral", description: "ADX at 32 indicates strong trend")
        ],
        signalBreakdown: [
            SignalCategory(category: "trend", signal: "bullish", strength: 0.8, description: "Trend indicators are strongly bullish"),
            SignalCategory(category: "momentum", signal: "bullish", strength: 0.65, description: "Momentum is moderately positive"),
            SignalCategory(category: "volatility", signal: "neutral", strength: 0.5, description: "Volatility analysis based on 2 indicators"),
            SignalCategory(category: "volume", signal: "neutral", strength: 0.45, description: "Volume analysis based on 1 indicator")
        ],
        riskFactors: [
            "RSI overbought (>70) - reversal risk",
            "Extended rally (8 days up)"
        ],
        supportingEvidence: [
            "Trend: Trend indicators are strongly bullish",
            "Momentum: Momentum is moderately positive"
        ],
        contradictingEvidence: [
            "No significant contradicting signals"
        ],
        recommendation: "Strong buy signal - consider entering long position",
        prediction: "bullish"
    ))
    .padding()
    .frame(width: 400)
}
