import SwiftUI

/// Overview Tab - Primary contract analysis view
/// Shows Momentum Framework scores, GA confidence, and quick facts
struct OverviewTabView: View {
    let rank: OptionRank
    let symbol: String
    
    @EnvironmentObject var appViewModel: AppViewModel
    
    var body: some View {
        VStack(spacing: 20) {
            // Momentum Framework Breakdown
            momentumFrameworkSection
            
            Divider()
            
            // GA Confidence (if strategy available)
            if let strategy = appViewModel.selectedContractState.gaStrategy {
                gaConfidenceSection(strategy: strategy)
                Divider()
            }
            
            // Quick Facts Grid
            quickFactsSection
            
            Divider()
            
            // Contract Summary
            summarySection
        }
    }
    
    // MARK: - Momentum Framework Section
    
    @ViewBuilder
    private var momentumFrameworkSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Momentum Framework Breakdown")
                .font(.headline)
            
            // Momentum Score
            ScoreBar(
                label: "Momentum Score",
                score: rank.momentumScore ?? 0,
                color: .green
            )
            
            // Value Score
            ScoreBar(
                label: "Value Score",
                score: rank.valueScore ?? 0,
                color: .blue
            )
            
            // Greeks Score
            ScoreBar(
                label: "Greeks Score",
                score: rank.greeksScore ?? 0,
                color: .orange
            )
            
            // Composite explanation
            Text(compositeExplanation)
                .font(.caption)
                .foregroundStyle(.secondary)
                .padding(.top, 4)
        }
    }
    
    // MARK: - GA Confidence Section
    
    @ViewBuilder
    private func gaConfidenceSection(strategy: GAStrategy) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("GA Strategy Alignment")
                .font(.headline)
            
            HStack(spacing: 12) {
                // Confidence circle
                ZStack {
                    Circle()
                        .stroke(Color.gray.opacity(0.2), lineWidth: 8)
                        .frame(width: 60, height: 60)
                    
                    Circle()
                        .trim(from: 0, to: gaConfidence(strategy))
                        .stroke(gaConfidenceColor(strategy), lineWidth: 8)
                        .frame(width: 60, height: 60)
                        .rotationEffect(.degrees(-90))
                    
                    Text("\(Int(gaConfidence(strategy) * 100))%")
                        .font(.caption)
                        .fontWeight(.bold)
                }
                
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text("GA Confidence")
                            .font(.subheadline)
                            .fontWeight(.semibold)
                        
                        if rank.passesGAFilters(strategy.genes) {
                            Image(systemName: "checkmark.seal.fill")
                                .foregroundColor(.green)
                                .font(.caption)
                        }
                    }
                    
                    Text(gaConfidenceLabel(strategy))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    
                    Text("Strategy Quality: \(strategy.fitness.qualityLabel)")
                        .font(.caption2)
                        .foregroundColor(strategy.fitness.qualityColor)
                }
                
                Spacer()
            }
        }
    }
    
    // MARK: - Quick Facts Section
    
    @ViewBuilder
    private var quickFactsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Quick Facts")
                .font(.headline)
            
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                QuickFactRow(
                    icon: "waveform.path.ecg",
                    label: "IV Rank",
                    value: formatIVRank(),
                    color: ivRankColor
                )
                
                QuickFactRow(
                    icon: "arrow.left.arrow.right",
                    label: "Spread Quality",
                    value: spreadQuality,
                    color: spreadColor
                )
                
                QuickFactRow(
                    icon: "person.3",
                    label: "Open Interest",
                    value: formatOI(),
                    color: oiColor
                )
                
                QuickFactRow(
                    icon: "chart.bar",
                    label: "Volume",
                    value: formatVolume(),
                    color: volumeColor
                )
                
                QuickFactRow(
                    icon: "drop",
                    label: "Liquidity",
                    value: rank.liquidityLabel,
                    color: rank.liquidityColor
                )
                
                QuickFactRow(
                    icon: "calendar",
                    label: "DTE",
                    value: "\(rank.daysToExpiry ?? 0) days",
                    color: dteColor
                )
            }
        }
    }
    
    // MARK: - Summary Section
    
    @ViewBuilder
    private var summarySection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Summary")
                .font(.headline)
            
            Text(contractSummary)
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
    
    // MARK: - Helper Methods
    
    private func gaConfidence(_ strategy: GAStrategy) -> Double {
        return rank.gaConfidence(strategy.genes)
    }
    
    private func gaConfidenceColor(_ strategy: GAStrategy) -> Color {
        let confidence = gaConfidence(strategy)
        if confidence >= 0.75 { return .green }
        if confidence >= 0.5 { return .blue }
        if confidence >= 0.3 { return .orange }
        return .red
    }
    
    private func gaConfidenceLabel(_ strategy: GAStrategy) -> String {
        if rank.passesGAFilters(strategy.genes) {
            return "Passes all GA filters"
        } else {
            return "Outside optimal parameters"
        }
    }
    
    private var compositeExplanation: String {
        let composite = rank.effectiveCompositeRank
        if composite >= 75 {
            return "Strong buy signal with excellent momentum, value, and Greeks alignment."
        } else if composite >= 60 {
            return "Good buy opportunity with favorable metrics across most categories."
        } else if composite >= 45 {
            return "Neutral position with mixed signals. Consider other factors."
        } else {
            return "Weak signals suggest caution. Multiple metrics indicate unfavorable conditions."
        }
    }
    
    private var contractSummary: String {
        var parts: [String] = []
        
        // Price assessment
        if let spreadPct = rank.spreadPctDisplay {
            if spreadPct < 2.0 {
                parts.append("tight spread (\(spreadPct, specifier: "%.1f")%)")
            } else if spreadPct > 5.0 {
                parts.append("wide spread (\(spreadPct, specifier: "%.1f")%)")
            }
        }
        
        // Liquidity
        if rank.isLowLiquidity {
            parts.append("low liquidity")
        } else {
            parts.append("good liquidity")
        }
        
        // Momentum
        if let ret7d = rank.underlying7dReturn {
            if ret7d > 2.0 {
                parts.append("strong underlying momentum")
            } else if ret7d < -2.0 {
                parts.append("weak underlying momentum")
            }
        }
        
        if parts.isEmpty {
            return "This \(symbol) \(rank.side.rawValue) option expires in \(rank.daysToExpiry ?? 0) days with a composite rank of \(rank.compositeScoreDisplay)/100."
        } else {
            return "This \(symbol) \(rank.side.rawValue) ranks \(rank.compositeScoreDisplay)/100 with " + parts.joined(separator: ", ") + "."
        }
    }
    
    // Formatting helpers
    private func formatIVRank() -> String {
        guard let ivr = rank.ivRank else { return "N/A" }
        return "\(Int(ivr))%"
    }
    
    private var spreadQuality: String {
        guard let spreadPct = rank.spreadPctDisplay else { return "Unknown" }
        if spreadPct < 2.0 { return "Excellent (\(spreadPct, specifier: "%.1f")%)" }
        if spreadPct < 5.0 { return "Good (\(spreadPct, specifier: "%.1f")%)" }
        if spreadPct < 10.0 { return "Fair (\(spreadPct, specifier: "%.1f")%)" }
        return "Poor (\(spreadPct, specifier: "%.1f")%)"
    }
    
    private func formatOI() -> String {
        guard let oi = rank.openInterest else { return "N/A" }
        if oi >= 1000 { return String(format: "%.1fK", Double(oi) / 1000.0) }
        return "\(oi)"
    }
    
    private func formatVolume() -> String {
        guard let vol = rank.volume else { return "N/A" }
        if vol >= 1000 { return String(format: "%.1fK", Double(vol) / 1000.0) }
        return "\(vol)"
    }
    
    // Color helpers
    private var ivRankColor: Color {
        guard let ivr = rank.ivRank else { return .secondary }
        if ivr >= 70 { return .red }
        if ivr >= 50 { return .orange }
        if ivr >= 30 { return .blue }
        return .green
    }
    
    private var spreadColor: Color {
        guard let spreadPct = rank.spreadPctDisplay else { return .secondary }
        if spreadPct < 2.0 { return .green }
        if spreadPct < 5.0 { return .blue }
        if spreadPct < 10.0 { return .orange }
        return .red
    }
    
    private var oiColor: Color {
        guard let oi = rank.openInterest else { return .secondary }
        if oi >= 1000 { return .green }
        if oi >= 500 { return .blue }
        if oi >= 100 { return .orange }
        return .red
    }
    
    private var volumeColor: Color {
        guard let vol = rank.volume else { return .secondary }
        if vol >= 500 { return .green }
        if vol >= 100 { return .blue }
        if vol >= 10 { return .orange }
        return .red
    }
    
    private var dteColor: Color {
        guard let dte = rank.daysToExpiry else { return .secondary }
        if dte <= 7 { return .red }
        if dte <= 30 { return .orange }
        if dte <= 60 { return .blue }
        return .green
    }
}

// MARK: - Score Bar Component

private struct ScoreBar: View {
    let label: String
    let score: Double
    let color: Color
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(label)
                    .font(.subheadline)
                Spacer()
                Text("\(Int(score))")
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundColor(color)
            }
            
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    Rectangle()
                        .fill(Color.gray.opacity(0.2))
                        .frame(height: 8)
                        .cornerRadius(4)
                    
                    Rectangle()
                        .fill(color)
                        .frame(width: geometry.size.width * (score / 100.0), height: 8)
                        .cornerRadius(4)
                }
            }
            .frame(height: 8)
        }
    }
}

// MARK: - Quick Fact Row Component

private struct QuickFactRow: View {
    let icon: String
    let label: String
    let value: String
    let color: Color
    
    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: icon)
                .font(.caption)
                .foregroundColor(color)
                .frame(width: 20)
            
            VStack(alignment: .leading, spacing: 2) {
                Text(label)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                Text(value)
                    .font(.caption)
                    .fontWeight(.medium)
                    .foregroundColor(color)
            }
            
            Spacer()
        }
        .padding(8)
        .background(Color(nsColor: .controlBackgroundColor))
        .cornerRadius(6)
    }
}

// MARK: - Preview

#Preview {
    ScrollView {
        OverviewTabView(
            rank: OptionRank.example,
            symbol: "AAPL"
        )
        .environmentObject(AppViewModel())
        .padding()
    }
    .frame(width: 450)
}
