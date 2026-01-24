import SwiftUI

/// Why Ranked Tab - Explains ranking methodology and GA strategy alignment
/// Shows signal contributions, quality adjustments, and GA optimization details
struct WhyRankedTabView: View {
    let rank: OptionRank
    let strategy: GAStrategy?
    let rankingMode: RankingMode?  // New parameter to show mode-specific breakdown
    
    var body: some View {
        VStack(spacing: 20) {
            // Signal Contributions
            signalContributionsSection
            
            Divider()
            
            // Quality Adjustments
            qualityAdjustmentsSection
            
            // GA Strategy Section (if available)
            if let strategy = strategy {
                Divider()
                gaStrategySection(strategy: strategy)
            }
            
            Divider()
            
            // Active Signals
            if rank.hasSignals {
                activeSignalsSection
                Divider()
            }
            
            // Explanation
            explanationSection
        }
    }
    
    // MARK: - Signal Contributions
    
    @ViewBuilder
    private var signalContributionsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Signal Contributions")
                    .font(.headline)
                Spacer()
                if let mode = rankingMode {
                    Label(mode.displayName, systemImage: mode.icon)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            
            // Mode-specific component breakdown
            if let mode = rankingMode {
                switch mode {
                case .entry:
                    entryModeContributions
                case .exit:
                    exitModeContributions
                case .monitor:
                    monitorModeContributions
                }
            } else {
                // Fallback to monitor mode if no mode specified
                monitorModeContributions
            }
        }
    }
    
    @ViewBuilder
    private var entryModeContributions: some View {
        // ENTRY MODE: Value 40%, Catalyst 35%, Greeks 25%
        ContributionRow(
            label: "Entry Value Score",
            score: rank.entryValueScore ?? rank.valueScore ?? 0,
            weight: 0.40,
            color: .blue
        )
        
        ContributionRow(
            label: "Catalyst Score",
            score: rank.catalystScore ?? rank.momentumScore ?? 0,
            weight: 0.35,
            color: .purple
        )
        
        ContributionRow(
            label: "Greeks Score",
            score: rank.greeksScore ?? 0,
            weight: 0.25,
            color: .orange
        )
        
        // Total Entry Rank
        HStack {
            Text("Total Entry Rank")
                .font(.subheadline)
                .fontWeight(.semibold)
            Spacer()
            Text("\(Int(rank.entryRank ?? rank.effectiveCompositeRank))/100")
                .font(.title3)
                .fontWeight(.bold)
                .foregroundColor(rank.compositeColor)
        }
        .padding(.top, 8)
        
        // Also show monitor rank for comparison
        Text("Monitor Rank: \(Int(rank.effectiveCompositeRank))/100")
            .font(.caption)
            .foregroundStyle(.secondary)
    }
    
    @ViewBuilder
    private var exitModeContributions: some View {
        // EXIT MODE: Profit 50%, Deterioration 30%, Time 20%
        ContributionRow(
            label: "Profit Protection",
            score: rank.profitProtectionScore ?? 50,
            weight: 0.50,
            color: .green
        )
        
        ContributionRow(
            label: "Deterioration Score",
            score: rank.deteriorationScore ?? 50,
            weight: 0.30,
            color: .red
        )
        
        ContributionRow(
            label: "Time Urgency",
            score: rank.timeUrgencyScore ?? 50,
            weight: 0.20,
            color: .orange
        )
        
        // Total Exit Rank
        HStack {
            Text("Total Exit Rank")
                .font(.subheadline)
                .fontWeight(.semibold)
            Spacer()
            Text("\(Int(rank.exitRank ?? rank.effectiveCompositeRank))/100")
                .font(.title3)
                .fontWeight(.bold)
                .foregroundColor(rank.compositeColor)
        }
        .padding(.top, 8)
        
        // Also show monitor rank for comparison
        Text("Monitor Rank: \(Int(rank.effectiveCompositeRank))/100")
            .font(.caption)
            .foregroundStyle(.secondary)
    }
    
    @ViewBuilder
    private var monitorModeContributions: some View {
        // MONITOR MODE: Momentum 40%, Value 35%, Greeks 25%
        ContributionRow(
            label: "Momentum Score",
            score: rank.momentumScore ?? 0,
            weight: MOMENTUM_WEIGHT,
            color: .green
        )
        
        ContributionRow(
            label: "Value Score",
            score: rank.valueScore ?? 0,
            weight: VALUE_WEIGHT,
            color: .blue
        )
        
        ContributionRow(
            label: "Greeks Score",
            score: rank.greeksScore ?? 0,
            weight: GREEKS_WEIGHT,
            color: .orange
        )
        
        // Total Composite Rank
        HStack {
            Text("Total Composite Rank")
                .font(.subheadline)
                .fontWeight(.semibold)
            Spacer()
            Text("\(rank.compositeScoreDisplay)/100")
                .font(.title3)
                .fontWeight(.bold)
                .foregroundColor(rank.compositeColor)
        }
        .padding(.top, 8)
    }
    
    // MARK: - Quality Adjustments
    
    @ViewBuilder
    private var qualityAdjustmentsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Quality Adjustments")
                .font(.headline)
            
            AdjustmentRow(
                label: "Liquidity Confidence",
                value: rank.liquidityLabel,
                isPassing: (rank.liquidityConfidence ?? 0) >= 0.5,
                detail: rank.liquidityConfidence.map { String(format: "%.2f", $0) } ?? "N/A"
            )
            
            AdjustmentRow(
                label: "Spread Quality",
                value: spreadQualityLabel,
                isPassing: (rank.spreadPctDisplay ?? 100) < 5.0,
                detail: rank.spreadPctDisplay.map { String(format: "%.1f%%", $0) } ?? "N/A"
            )
            
            AdjustmentRow(
                label: "Quote Freshness",
                value: freshnessLabel,
                isPassing: (rank.markAgeSeconds ?? 9999) < 600,
                detail: rank.markAgeLabel
            )
            
            if let oi = rank.openInterest {
                AdjustmentRow(
                    label: "Open Interest",
                    value: oi >= 100 ? "Adequate" : "Low",
                    isPassing: oi >= 100,
                    detail: "\(oi)"
                )
            }
        }
    }
    
    // MARK: - GA Strategy Section
    
    @ViewBuilder
    private func gaStrategySection(strategy: GAStrategy) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("GA Strategy Analysis")
                .font(.headline)
            
            // Tier 1: Fitness Metrics
            fitnessMetricsGrid(strategy: strategy)
            
            // Tier 2: Entry/Exit Rules
            entryExitRules(genes: strategy.genes)
            
            // Tier 3: Risk Management
            riskManagementBox(genes: strategy.genes)
            
            // Backtest Context
            backtestContext(strategy: strategy)
        }
    }
    
    @ViewBuilder
    private func fitnessMetricsGrid(strategy: GAStrategy) -> some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
            GAMetricCard(
                title: "Win Rate",
                value: strategy.fitness.winRateDisplay,
                color: strategy.fitness.winRate >= 0.6 ? .green : .orange
            )
            
            GAMetricCard(
                title: "Sharpe Ratio",
                value: strategy.fitness.sharpeDisplay,
                color: strategy.fitness.sharpeRatio >= 1.0 ? .green : .orange
            )
            
            GAMetricCard(
                title: "Max Drawdown",
                value: strategy.fitness.maxDrawdownDisplay,
                color: strategy.fitness.maxDrawdown <= 0.15 ? .green : .red
            )
            
            GAMetricCard(
                title: "Quality",
                value: "\(strategy.fitness.qualityScore)/100",
                color: strategy.fitness.qualityColor
            )
        }
    }
    
    @ViewBuilder
    private func entryExitRules(genes: StrategyGenes) -> some View {
        VStack(spacing: 12) {
            // Entry Conditions
            GroupBox("Entry Conditions") {
                VStack(spacing: 8) {
                    RuleRow(
                        icon: "chart.line.uptrend.xyaxis",
                        label: "Composite Rank",
                        value: "≥ \(Int(genes.minCompositeRank))",
                        passed: rank.effectiveCompositeRank >= genes.minCompositeRank
                    )
                    
                    RuleRow(
                        icon: "arrow.up.arrow.down",
                        label: "IV Rank Range",
                        value: genes.ivRankRangeDisplay,
                        passed: isIVRankInRange(genes: genes)
                    )
                    
                    RuleRow(
                        icon: "flag.fill",
                        label: "Signal Filter",
                        value: genes.signalFilterDisplay,
                        passed: matchesSignalFilter(genes: genes)
                    )
                    
                    RuleRow(
                        icon: "clock.fill",
                        label: "Entry Hours",
                        value: genes.entryHoursDisplay,
                        passed: nil
                    )
                }
                .padding(8)
            }
            
            // Exit Conditions
            GroupBox("Exit Conditions") {
                VStack(spacing: 8) {
                    RuleRow(
                        icon: "arrow.up.right",
                        label: "Profit Target",
                        value: genes.profitTargetDisplay,
                        passed: nil
                    )
                    
                    RuleRow(
                        icon: "arrow.down.right",
                        label: "Stop Loss",
                        value: genes.stopLossDisplay,
                        passed: nil
                    )
                    
                    RuleRow(
                        icon: "hourglass",
                        label: "Hold Time",
                        value: genes.holdTimeDisplay,
                        passed: nil
                    )
                    
                    RuleRow(
                        icon: "waveform.path.ecg",
                        label: "Greeks Exits",
                        value: "Δ<\(String(format: "%.2f", genes.deltaExit))",
                        passed: nil
                    )
                }
                .padding(8)
            }
        }
    }
    
    @ViewBuilder
    private func riskManagementBox(genes: StrategyGenes) -> some View {
        GroupBox("Risk Management") {
            HStack(spacing: 16) {
                VStack {
                    Text(String(format: "%.1f%%", genes.positionSizePct))
                        .font(.title3)
                        .fontWeight(.bold)
                    Text("Position Size")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity)
                
                Divider()
                
                VStack {
                    Text("\(genes.maxConcurrentTrades)")
                        .font(.title3)
                        .fontWeight(.bold)
                    Text("Max Concurrent")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity)
                
                Divider()
                
                VStack {
                    Text("\(genes.maxTradesPerSymbol)")
                        .font(.title3)
                        .fontWeight(.bold)
                    Text("Max Per Symbol")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity)
            }
            .padding(8)
        }
    }
    
    @ViewBuilder
    private func backtestContext(strategy: GAStrategy) -> some View {
        HStack(spacing: 6) {
            Image(systemName: "chart.bar.doc.horizontal")
                .font(.caption)
                .foregroundStyle(.secondary)
            Text("Optimized over \(strategy.trainingDays) days • \(strategy.trainingSamples) trades • \(strategy.generationsRun) generations")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
    
    // MARK: - Active Signals
    
    @ViewBuilder
    private var activeSignalsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Active Signals")
                .font(.headline)
            
            FlowLayout(spacing: 8) {
                ForEach(rank.activeSignals, id: \.self) { signal in
                    Text(signal)
                        .font(.caption)
                        .fontWeight(.semibold)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(signalColor(for: signal).opacity(0.2))
                        .foregroundColor(signalColor(for: signal))
                        .cornerRadius(8)
                }
            }
            
            Text(signalExplanation)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
    
    // MARK: - Explanation
    
    @ViewBuilder
    private var explanationSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Ranking Explanation")
                .font(.headline)
            
            Text(rankingExplanation)
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
    
    // MARK: - Helper Methods
    
    private var spreadQualityLabel: String {
        guard let spreadPct = rank.spreadPctDisplay else { return "Unknown" }
        if spreadPct < 2.0 { return "Excellent" }
        if spreadPct < 5.0 { return "Good" }
        if spreadPct < 10.0 { return "Fair" }
        return "Poor"
    }
    
    private var freshnessLabel: String {
        guard let seconds = rank.markAgeSeconds, seconds >= 0 else { return "Unknown" }
        if seconds < 120 { return "Fresh" }
        if seconds < 600 { return "Recent" }
        return "Stale"
    }
    
    private func isIVRankInRange(genes: StrategyGenes) -> Bool? {
        guard let ivRank = rank.ivRank else { return nil }
        return ivRank >= genes.ivRankMin && ivRank <= genes.ivRankMax
    }
    
    private func matchesSignalFilter(genes: StrategyGenes) -> Bool? {
        let filter = genes.signalFilter.lowercased()
        if filter == "any" { return true }
        
        switch filter {
        case "buy": return rank.signalBuy == true
        case "discount": return rank.signalDiscount == true
        case "runner": return rank.signalRunner == true
        case "greeks": return rank.signalGreeks == true
        default: return nil
        }
    }
    
    private func signalColor(for signal: String) -> Color {
        switch signal {
        case "BUY": return .green
        case "DISCOUNT": return .blue
        case "RUNNER": return .purple
        case "GREEKS": return .orange
        default: return .gray
        }
    }
    
    private var signalExplanation: String {
        var explanations: [String] = []
        
        if rank.signalBuy == true {
            explanations.append("BUY: Strong composite rank with favorable momentum")
        }
        if rank.signalDiscount == true {
            explanations.append("DISCOUNT: Trading below historical average")
        }
        if rank.signalRunner == true {
            explanations.append("RUNNER: Momentum indicators suggest continuation")
        }
        if rank.signalGreeks == true {
            explanations.append("GREEKS: Greeks positioning favorable for direction")
        }
        
        return explanations.joined(separator: " • ")
    }
    
    private var rankingExplanation: String {
        var explanation = "This contract ranks \(rank.compositeScoreDisplay)/100"
        
        // Add momentum context
        if let momentum = rank.momentumScore, momentum >= 70 {
            explanation += " with strong momentum alignment"
        }
        
        // Add underlying context
        if let ret7d = rank.underlying7dReturn {
            if ret7d > 2.0 {
                explanation += ". The underlying has shown positive 7-day momentum (+\(String(format: "%.1f%%", ret7d)))"
            } else if ret7d < -2.0 {
                explanation += ". Note: The underlying has shown negative 7-day momentum (\(String(format: "%.1f%%", ret7d)))"
            }
        }
        
        // Add volatility context
        if let vol = rank.underlying7dVolatility {
            if vol < 20.0 {
                explanation += " with low volatility (\(String(format: "%.1f%%", vol)))"
            } else if vol > 35.0 {
                explanation += " with elevated volatility (\(String(format: "%.1f%%", vol)))"
            }
        }
        
        return explanation + "."
    }
}

// MARK: - Supporting Components

private struct ContributionRow: View {
    let label: String
    let score: Double
    let weight: Double
    let color: Color
    
    private var contribution: Double {
        (score / 100.0) * weight * 100.0
    }
    
    var body: some View {
        HStack {
            Text(label)
                .font(.subheadline)
            Spacer()
            Text("\(Int(score))/100")
                .font(.caption)
                .foregroundStyle(.secondary)
            Text("×")
                .font(.caption)
                .foregroundStyle(.secondary)
            Text("\(Int(weight * 100))%")
                .font(.caption)
                .foregroundStyle(.secondary)
            Text("=")
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(String(format: "+%.1f", contribution))
                .font(.subheadline)
                .fontWeight(.semibold)
                .foregroundColor(color)
                .frame(width: 50, alignment: .trailing)
        }
    }
}

// MARK: - Framework Weight Constants
// Updated 2026-01-23: Standardized weights across all systems
private let MOMENTUM_WEIGHT = 0.40  // 40%
private let VALUE_WEIGHT = 0.35     // 35%
private let GREEKS_WEIGHT = 0.25    // 25%

private struct AdjustmentRow: View {
    let label: String
    let value: String
    let isPassing: Bool
    let detail: String
    
    var body: some View {
        HStack {
            Image(systemName: isPassing ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                .foregroundColor(isPassing ? .green : .orange)
                .font(.caption)
            
            Text(label)
                .font(.subheadline)
            
            Spacer()
            
            VStack(alignment: .trailing, spacing: 2) {
                Text(value)
                    .font(.subheadline)
                    .fontWeight(.medium)
                Text(detail)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

private struct GAMetricCard: View {
    let title: String
    let value: String
    let color: Color
    
    var body: some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.title3)
                .fontWeight(.bold)
                .foregroundColor(color)
            Text(title)
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(12)
        .background(color.opacity(0.1))
        .cornerRadius(8)
    }
}

private struct RuleRow: View {
    let icon: String
    let label: String
    let value: String
    let passed: Bool?
    
    var body: some View {
        HStack {
            Image(systemName: icon)
                .font(.caption)
                .foregroundStyle(.secondary)
                .frame(width: 20)
            
            Text(label)
                .font(.caption)
                .foregroundStyle(.secondary)
            
            Spacer()
            
            Text(value)
                .font(.caption)
                .fontWeight(.medium)
            
            if let passed = passed {
                Image(systemName: passed ? "checkmark.circle.fill" : "xmark.circle")
                    .foregroundColor(passed ? .green : .red)
                    .font(.caption)
            }
        }
    }
}

// MARK: - Flow Layout for Chips

private struct FlowLayout: Layout {
    var spacing: CGFloat = 8
    
    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let result = FlowResult(
            in: proposal.replacingUnspecifiedDimensions().width,
            subviews: subviews,
            spacing: spacing
        )
        return result.size
    }
    
    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let result = FlowResult(
            in: bounds.width,
            subviews: subviews,
            spacing: spacing
        )
        for (index, subview) in subviews.enumerated() {
            subview.place(at: CGPoint(x: bounds.minX + result.frames[index].minX, y: bounds.minY + result.frames[index].minY), proposal: .unspecified)
        }
    }
    
    struct FlowResult {
        var size: CGSize = .zero
        var frames: [CGRect] = []
        
        init(in maxWidth: CGFloat, subviews: Subviews, spacing: CGFloat) {
            var currentX: CGFloat = 0
            var currentY: CGFloat = 0
            var lineHeight: CGFloat = 0
            
            for subview in subviews {
                let size = subview.sizeThatFits(.unspecified)
                
                if currentX + size.width > maxWidth && currentX > 0 {
                    currentX = 0
                    currentY += lineHeight + spacing
                    lineHeight = 0
                }
                
                frames.append(CGRect(x: currentX, y: currentY, width: size.width, height: size.height))
                lineHeight = max(lineHeight, size.height)
                currentX += size.width + spacing
            }
            
            self.size = CGSize(width: maxWidth, height: currentY + lineHeight)
        }
    }
}

// MARK: - Preview

#Preview {
    ScrollView {
        WhyRankedTabView(
            rank: OptionRank.example,
            strategy: GAStrategy.example,
            rankingMode: .entry
        )
        .padding()
    }
    .frame(width: 450)
}
