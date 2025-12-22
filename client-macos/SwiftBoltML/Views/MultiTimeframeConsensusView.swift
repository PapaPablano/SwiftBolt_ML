import SwiftUI

// MARK: - Multi-Timeframe Consensus View

struct MultiTimeframeConsensusView: View {
    let consensus: MultiTimeframeConsensus
    @State private var isExpanded = false
    
    private var signalColor: Color {
        switch consensus.signal.lowercased() {
        case "buy", "bullish":
            return .green
        case "sell", "bearish":
            return .red
        default:
            return .orange
        }
    }
    
    private var signalIcon: String {
        switch consensus.signal.lowercased() {
        case "buy", "bullish":
            return "arrow.up.circle.fill"
        case "sell", "bearish":
            return "arrow.down.circle.fill"
        default:
            return "minus.circle.fill"
        }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Compact header
            Button(action: { isExpanded.toggle() }) {
                HStack(spacing: 12) {
                    // Icon
                    Image(systemName: "chart.bar.xaxis")
                        .foregroundStyle(.blue)
                        .font(.title3)
                    
                    VStack(alignment: .leading, spacing: 2) {
                        HStack(spacing: 6) {
                            Text("Multi-TF Consensus")
                                .font(.caption.bold())
                                .foregroundStyle(.primary)
                            
                            Divider()
                                .frame(height: 12)
                            
                            Image(systemName: signalIcon)
                                .font(.caption)
                            Text(consensus.signal.uppercased())
                                .font(.caption.bold())
                        }
                        .foregroundStyle(signalColor)
                        
                        Text("\(consensus.bullishCount)/\(consensus.bullishCount + consensus.bearishCount) timeframes agree")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                    
                    Spacer()
                    
                    // Confidence
                    VStack(alignment: .trailing, spacing: 2) {
                        Text("\(Int(consensus.confidence * 100))%")
                            .font(.title3.bold())
                            .foregroundStyle(signalColor)
                        
                        Text("Consensus")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                    
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
                
                TimeframeBreakdownView(
                    breakdown: consensus.timeframeBreakdown,
                    dominantTf: consensus.dominantTf
                )
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

// MARK: - Timeframe Breakdown View

struct TimeframeBreakdownView: View {
    let breakdown: [TimeframeSignal]
    let dominantTf: String?
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Timeframe Alignment")
                .font(.caption.bold())
                .foregroundStyle(.secondary)
            
            ForEach(breakdown, id: \.timeframe) { tf in
                TimeframeRow(
                    signal: tf,
                    isDominant: tf.timeframe == dominantTf
                )
            }
        }
    }
}

struct TimeframeRow: View {
    let signal: TimeframeSignal
    let isDominant: Bool
    
    private var signalColor: Color {
        switch signal.signal.lowercased() {
        case "bullish", "buy":
            return .green
        case "bearish", "sell":
            return .red
        default:
            return .orange
        }
    }
    
    private var signalIcon: String {
        switch signal.signal.lowercased() {
        case "bullish", "buy":
            return "arrow.up"
        case "bearish", "sell":
            return "arrow.down"
        default:
            return "minus"
        }
    }
    
    var body: some View {
        HStack {
            // Timeframe label
            HStack(spacing: 4) {
                Text(signal.timeframe.uppercased())
                    .font(.caption.bold())
                    .frame(width: 35, alignment: .leading)
                
                if isDominant {
                    Image(systemName: "star.fill")
                        .font(.system(size: 8))
                        .foregroundStyle(.yellow)
                }
            }
            
            // Signal indicator
            HStack(spacing: 4) {
                Image(systemName: signalIcon)
                    .font(.caption2)
                Text(signal.signal.uppercased())
                    .font(.caption2.bold())
            }
            .foregroundStyle(signalColor)
            .frame(width: 70, alignment: .leading)
            
            Spacer()
            
            // RSI value if available
            if let rsi = signal.rsi {
                Text("RSI: \(Int(rsi))")
                    .font(.caption2.monospacedDigit())
                    .foregroundStyle(.secondary)
            }
            
            // Visual bar
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Color.gray.opacity(0.2))
                    
                    RoundedRectangle(cornerRadius: 2)
                        .fill(signalColor.opacity(0.7))
                        .frame(width: geometry.size.width * strengthPercentage)
                }
            }
            .frame(width: 50, height: 4)
        }
        .padding(.vertical, 2)
        .background(isDominant ? signalColor.opacity(0.1) : Color.clear)
        .cornerRadius(4)
    }
    
    private var strengthPercentage: Double {
        // Convert RSI to strength (0-100 -> 0-1)
        guard let rsi = signal.rsi else { return 0.5 }
        if rsi > 50 {
            return min(1.0, (rsi - 50) / 50)
        } else {
            return min(1.0, (50 - rsi) / 50)
        }
    }
}

// MARK: - Preview
// Note: Data models (MultiTimeframeConsensus, TimeframeSignal) are defined in Models/EnhancedPredictionModels.swift

#Preview {
    MultiTimeframeConsensusView(consensus: MultiTimeframeConsensus(
        signal: "buy",
        confidence: 0.75,
        bullishCount: 4,
        bearishCount: 1,
        dominantTf: "h1",
        signalValue: 0.65,
        timeframeBreakdown: [
            TimeframeSignal(timeframe: "m15", signal: "neutral", rsi: 52),
            TimeframeSignal(timeframe: "h1", signal: "bullish", rsi: 68),
            TimeframeSignal(timeframe: "d1", signal: "bullish", rsi: 62),
            TimeframeSignal(timeframe: "w1", signal: "bullish", rsi: 58)
        ]
    ))
    .padding()
    .frame(width: 350)
}
