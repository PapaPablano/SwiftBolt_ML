import SwiftUI

/// Key Metrics Strip - Displays essential contract metrics as compact chips
/// Provides at-a-glance information without scrolling
struct KeyMetricsStrip: View {
    let rank: OptionRank
    
    // Layout configuration
    private let columns = [
        GridItem(.flexible(), spacing: 8),
        GridItem(.flexible(), spacing: 8),
        GridItem(.flexible(), spacing: 8),
        GridItem(.flexible(), spacing: 8)
    ]
    
    var body: some View {
        LazyVGrid(columns: columns, spacing: 8) {
            // Row 1: Pricing metrics
            MetricChip(
                label: "Mark",
                value: formatPrice(rank.derivedMark),
                color: .primary
            )
            
            MetricChip(
                label: "Bid/Ask",
                value: formatBidAsk(),
                color: .secondary
            )
            
            MetricChip(
                label: "Spread",
                value: formatSpread(),
                color: spreadColor,
                help: "Bid-Ask spread as percentage of mark price"
            )
            
            MetricChip(
                label: "IV Rank",
                value: formatIVRank(),
                color: ivRankColor,
                help: "Implied Volatility rank (0-100)"
            )
            
            // Row 2: Greeks and liquidity
            MetricChip(
                label: "Delta",
                value: formatDelta(),
                color: deltaColor
            )
            
            MetricChip(
                label: "OI",
                value: formatOpenInterest(),
                color: oiColor,
                help: "Open Interest"
            )
            
            MetricChip(
                label: "Volume",
                value: formatVolume(),
                color: volumeColor
            )
            
            MetricChip(
                label: "DTE",
                value: formatDTE(),
                color: dteColor,
                help: "Days to Expiration"
            )
        }
    }
    
    // MARK: - Formatting Helpers
    
    private func formatPrice(_ price: Double?) -> String {
        guard let price = price else { return "—" }
        return "$\(price, specifier: "%.2f")"
    }
    
    private func formatBidAsk() -> String {
        guard let bid = rank.bid, let ask = rank.ask else { return "—" }
        return "$\(bid, specifier: "%.2f") / $\(ask, specifier: "%.2f")"
    }
    
    private func formatSpread() -> String {
        guard let spreadPct = rank.spreadPctDisplay else { return "—" }
        return "\(spreadPct, specifier: "%.1f")%"
    }
    
    private func formatIVRank() -> String {
        guard let ivRank = rank.ivRank else { return "—" }
        return "\(Int(ivRank))%"
    }
    
    private func formatDelta() -> String {
        guard let delta = rank.delta else { return "—" }
        return "\(delta, specifier: "%.3f")"
    }
    
    private func formatOpenInterest() -> String {
        guard let oi = rank.openInterest else { return "—" }
        if oi >= 1000 {
            return String(format: "%.1fK", Double(oi) / 1000.0)
        }
        return "\(oi)"
    }
    
    private func formatVolume() -> String {
        guard let volume = rank.volume else { return "—" }
        if volume >= 1000 {
            return String(format: "%.1fK", Double(volume) / 1000.0)
        }
        return "\(volume)"
    }
    
    private func formatDTE() -> String {
        guard let dte = rank.daysToExpiry else { return "—" }
        return "\(dte)"
    }
    
    // MARK: - Color Logic
    
    private var spreadColor: Color {
        guard let spreadPct = rank.spreadPctDisplay else { return .secondary }
        if spreadPct < 2.0 { return .green }
        if spreadPct < 5.0 { return .orange }
        return .red
    }
    
    private var ivRankColor: Color {
        guard let ivRank = rank.ivRank else { return .secondary }
        if ivRank >= 70 { return .red }
        if ivRank >= 50 { return .orange }
        if ivRank >= 30 { return .blue }
        return .green
    }
    
    private var deltaColor: Color {
        guard let delta = rank.delta else { return .secondary }
        let absDelta = abs(delta)
        if absDelta >= 0.7 { return .green }
        if absDelta >= 0.5 { return .blue }
        if absDelta >= 0.3 { return .orange }
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
        guard let volume = rank.volume else { return .secondary }
        if volume >= 500 { return .green }
        if volume >= 100 { return .blue }
        if volume >= 10 { return .orange }
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

// MARK: - Metric Chip Component

private struct MetricChip: View {
    let label: String
    let value: String
    var color: Color = .primary
    var help: String? = nil
    
    var body: some View {
        VStack(spacing: 2) {
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.caption)
                .fontWeight(.medium)
                .foregroundColor(color)
                .lineLimit(1)
                .minimumScaleFactor(0.8)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 6)
        .padding(.horizontal, 4)
        .background(Color(nsColor: .controlBackgroundColor))
        .cornerRadius(6)
        .help(help ?? label)
    }
}

// MARK: - Preview

#Preview {
    VStack(spacing: 20) {
        KeyMetricsStrip(rank: OptionRank.example)
            .padding()
        
        Divider()
        
        // Example with missing data
        KeyMetricsStrip(rank: {
            var rank = OptionRank.example
            return rank
        }())
        .padding()
    }
    .frame(width: 450)
}
