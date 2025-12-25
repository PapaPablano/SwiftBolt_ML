import SwiftUI

struct SupportResistanceView: View {
    @ObservedObject var analysisViewModel: AnalysisViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Section header
            HStack {
                Image(systemName: "chart.line.uptrend.xyaxis")
                    .foregroundStyle(.cyan)
                Text("Support & Resistance")
                    .font(.headline)
                
                Spacer()
                
                if analysisViewModel.isLoadingSR {
                    ProgressView()
                        .scaleEffect(0.7)
                }
            }
            
            if analysisViewModel.isLoadingSR {
                ProgressView("Loading S/R levels...")
                    .frame(maxWidth: .infinity)
                    .padding()
            } else if let sr = analysisViewModel.supportResistance {
                // Main S/R content
                SRLevelsContent(sr: sr)
            } else if analysisViewModel.srError != nil {
                // Error state
                HStack {
                    Image(systemName: "exclamationmark.triangle")
                        .foregroundStyle(.orange)
                    Text("S/R data unavailable")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .padding()
            } else {
                Text("Select a symbol to view S/R levels")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity)
                    .padding()
            }
        }
        .padding()
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

// MARK: - S/R Levels Content

struct SRLevelsContent: View {
    let sr: SupportResistanceResponse
    
    var body: some View {
        VStack(spacing: 12) {
            // Key metrics row
            HStack(spacing: 16) {
                // Current Price
                SRMetricCard(
                    title: "Price",
                    value: String(format: "$%.2f", sr.currentPrice),
                    color: .primary
                )
                
                // Nearest Support
                if let support = sr.nearestSupport {
                    SRMetricCard(
                        title: "Support",
                        value: String(format: "$%.2f", support),
                        subtitle: sr.supportDistancePct.map { String(format: "%.1f%% below", $0) },
                        color: .green
                    )
                }
                
                // Nearest Resistance
                if let resistance = sr.nearestResistance {
                    SRMetricCard(
                        title: "Resistance",
                        value: String(format: "$%.2f", resistance),
                        subtitle: sr.resistanceDistancePct.map { String(format: "%.1f%% above", $0) },
                        color: .red
                    )
                }
            }
            
            Divider()
            
            // Bias indicator
            BiasIndicator(sr: sr)
            
            Divider()
            
            // Pivot Points
            if let pivots = sr.pivotPoints {
                PivotPointsRow(pivots: pivots, currentPrice: sr.currentPrice)
            }
            
            // Fibonacci Levels
            if let fib = sr.fibonacci {
                FibonacciRow(fib: fib, currentPrice: sr.currentPrice)
            }
        }
    }
}

// MARK: - S/R Metric Card

struct SRMetricCard: View {
    let title: String
    let value: String
    var subtitle: String? = nil
    let color: Color
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
            
            Text(value)
                .font(.subheadline.bold())
                .foregroundStyle(color)
            
            if let subtitle = subtitle {
                Text(subtitle)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(8)
        .background(color.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

// MARK: - Bias Indicator

struct BiasIndicator: View {
    let sr: SupportResistanceResponse
    
    private var biasColor: Color {
        switch sr.bias {
        case "Bullish": return .green
        case "Bearish": return .red
        default: return .orange
        }
    }
    
    private var biasIcon: String {
        switch sr.bias {
        case "Bullish": return "arrow.up.right.circle.fill"
        case "Bearish": return "arrow.down.right.circle.fill"
        default: return "arrow.left.and.right.circle.fill"
        }
    }
    
    var body: some View {
        HStack {
            Image(systemName: biasIcon)
                .font(.title2)
                .foregroundStyle(biasColor)
            
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text("S/R Bias:")
                        .font(.subheadline)
                    Text(sr.bias)
                        .font(.subheadline.bold())
                        .foregroundStyle(biasColor)
                    
                    if let ratio = sr.srRatio {
                        Text(String(format: "(%.2f)", ratio))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
                
                Text(sr.biasDescription)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            
            Spacer()
        }
        .padding(10)
        .background(biasColor.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

// MARK: - Pivot Points Row

struct PivotPointsRow: View {
    let pivots: PivotPoints
    let currentPrice: Double
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Pivot Points")
                .font(.caption.bold())
                .foregroundStyle(.secondary)
            
            HStack(spacing: 6) {
                PivotBadge(label: "S3", value: pivots.s3, currentPrice: currentPrice, isSupport: true)
                PivotBadge(label: "S2", value: pivots.s2, currentPrice: currentPrice, isSupport: true)
                PivotBadge(label: "S1", value: pivots.s1, currentPrice: currentPrice, isSupport: true)
                PivotBadge(label: "PP", value: pivots.pp, currentPrice: currentPrice, isPivot: true)
                PivotBadge(label: "R1", value: pivots.r1, currentPrice: currentPrice, isSupport: false)
                PivotBadge(label: "R2", value: pivots.r2, currentPrice: currentPrice, isSupport: false)
                PivotBadge(label: "R3", value: pivots.r3, currentPrice: currentPrice, isSupport: false)
            }
        }
    }
}

struct PivotBadge: View {
    let label: String
    let value: Double
    let currentPrice: Double
    var isSupport: Bool = false
    var isPivot: Bool = false
    
    private var color: Color {
        if isPivot {
            return .orange
        }
        return isSupport ? .green : .red
    }
    
    private var isNearPrice: Bool {
        abs(value - currentPrice) / currentPrice < 0.02
    }
    
    var body: some View {
        VStack(spacing: 2) {
            Text(label)
                .font(.caption2.bold())
                .foregroundStyle(color)
            
            Text(String(format: "%.0f", value))
                .font(.caption2)
                .foregroundStyle(.primary)
        }
        .padding(.horizontal, 6)
        .padding(.vertical, 4)
        .background(isNearPrice ? color.opacity(0.2) : Color(nsColor: .windowBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 4))
        .overlay(
            RoundedRectangle(cornerRadius: 4)
                .stroke(isNearPrice ? color : Color.clear, lineWidth: 1)
        )
    }
}

// MARK: - Fibonacci Row

struct FibonacciRow: View {
    let fib: FibonacciLevels
    let currentPrice: Double
    
    private var labeledLevels: [(String, Double)] {
        [
            ("0.236", fib.fib236),
            ("0.382", fib.fib382),
            ("0.500", fib.fib500),
            ("0.618", fib.fib618),
            ("0.786", fib.fib786)
        ]
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Fibonacci")
                    .font(.caption.bold())
                    .foregroundStyle(.secondary)
                
                Spacer()
                
                Text(fib.trend.capitalized)
                    .font(.caption)
                    .foregroundStyle(fib.trend == "uptrend" ? .green : .red)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background((fib.trend == "uptrend" ? Color.green : Color.red).opacity(0.15))
                    .clipShape(Capsule())
            }
            
            // Show key Fibonacci levels
            HStack(spacing: 4) {
                ForEach(labeledLevels.prefix(5), id: \.0) { level in
                    FibBadge(
                        name: level.0,
                        value: level.1,
                        currentPrice: currentPrice
                    )
                }
            }
        }
    }
}

struct FibBadge: View {
    let name: String
    let value: Double
    let currentPrice: Double
    
    private var isNearPrice: Bool {
        abs(value - currentPrice) / currentPrice < 0.02
    }
    
    private var color: Color {
        value < currentPrice ? .green : .red
    }
    
    var body: some View {
        VStack(spacing: 2) {
            Text(name)
                .font(.system(size: 9))
                .foregroundStyle(.secondary)
            
            Text(String(format: "%.0f", value))
                .font(.caption2)
                .foregroundStyle(color)
        }
        .padding(.horizontal, 4)
        .padding(.vertical, 3)
        .background(isNearPrice ? color.opacity(0.2) : Color(nsColor: .windowBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 4))
        .overlay(
            RoundedRectangle(cornerRadius: 4)
                .stroke(isNearPrice ? color : Color.clear, lineWidth: 1)
        )
    }
}

#Preview {
    SupportResistanceView(analysisViewModel: AnalysisViewModel())
        .frame(width: 400)
        .padding()
}
