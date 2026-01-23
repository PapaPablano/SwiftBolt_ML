import SwiftUI

/// Contract Tab - Complete contract specifications and metadata
/// Displays all contract fields in an organized two-column layout
struct ContractTabView: View {
    let rank: OptionRank
    let symbol: String
    
    var body: some View {
        VStack(spacing: 20) {
            // Basics Section
            basicsSection
            
            Divider()
            
            // Pricing Section
            pricingSection
            
            Divider()
            
            // Greeks Section
            greeksSection
            
            Divider()
            
            // Volume & Open Interest
            volumeOISection
            
            Divider()
            
            // IV Metrics
            ivMetricsSection
            
            Divider()
            
            // Liquidity & Data Quality
            liquiditySection
            
            Divider()
            
            // Metadata
            metadataSection
        }
    }
    
    // MARK: - Sections
    
    @ViewBuilder
    private var basicsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Basics")
                .font(.headline)
            
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                DetailField(label: "Contract Symbol", value: rank.contractSymbol, copyable: true)
                DetailField(label: "Strike", value: "$\(rank.strike, specifier: "%.2f")")
                DetailField(label: "Expiration", value: rank.expiry)
                DetailField(label: "Side", value: rank.side.rawValue.uppercased())
                
                if let dte = rank.daysToExpiry {
                    DetailField(label: "Days to Expiry", value: "\(dte)")
                }
                
                if let expiryDate = rank.expiryDate {
                    DetailField(label: "Expiry Date", value: "\(expiryDate, style: .date)")
                }
            }
        }
    }
    
    @ViewBuilder
    private var pricingSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Pricing")
                .font(.headline)
            
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                if let bid = rank.bid {
                    DetailField(label: "Bid", value: "$\(bid, specifier: "%.2f")", color: .red)
                }
                
                if let ask = rank.ask {
                    DetailField(label: "Ask", value: "$\(ask, specifier: "%.2f")", color: .green)
                }
                
                if let mark = rank.mark {
                    DetailField(label: "Mark", value: "$\(mark, specifier: "%.2f")", color: .blue)
                }
                
                if let derivedMark = rank.derivedMark {
                    DetailField(label: "Derived Mid", value: "$\(derivedMark, specifier: "%.2f")")
                }
                
                if let lastPrice = rank.lastPrice {
                    DetailField(label: "Last Price", value: "$\(lastPrice, specifier: "%.2f")")
                }
                
                if let spread = rank.spread {
                    DetailField(label: "Spread", value: "$\(spread, specifier: "%.2f")")
                }
                
                if let spreadPct = rank.spreadPctDisplay {
                    DetailField(
                        label: "Spread %",
                        value: "\(spreadPct, specifier: "%.2f")%",
                        color: spreadColor
                    )
                }
            }
        }
    }
    
    @ViewBuilder
    private var greeksSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Greeks")
                .font(.headline)
            
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                if let delta = rank.delta {
                    DetailField(label: "Delta", value: "\(delta, specifier: "%.4f")", color: deltaColor)
                }
                
                if let gamma = rank.gamma {
                    DetailField(label: "Gamma", value: "\(gamma, specifier: "%.4f")", color: .orange)
                }
                
                if let theta = rank.theta {
                    DetailField(label: "Theta", value: "\(theta, specifier: "%.4f")", color: .red)
                }
                
                if let vega = rank.vega {
                    DetailField(label: "Vega", value: "\(vega, specifier: "%.4f")", color: .purple)
                }
                
                if let rho = rank.rho {
                    DetailField(label: "Rho", value: "\(rho, specifier: "%.4f")", color: .blue)
                }
            }
        }
    }
    
    @ViewBuilder
    private var volumeOISection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Volume & Open Interest")
                .font(.headline)
            
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                if let volume = rank.volume {
                    DetailField(label: "Volume", value: "\(volume)", color: volumeColor)
                }
                
                if let oi = rank.openInterest {
                    DetailField(label: "Open Interest", value: "\(oi)", color: oiColor)
                }
                
                if let volOiRatio = rank.volOiRatio {
                    DetailField(label: "Vol/OI Ratio", value: "\(volOiRatio, specifier: "%.2f")")
                }
            }
        }
    }
    
    @ViewBuilder
    private var ivMetricsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Implied Volatility")
                .font(.headline)
            
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                if let iv = rank.impliedVol {
                    DetailField(label: "Implied Vol", value: "\(iv, specifier: "%.2f")%")
                }
                
                if let ivRank = rank.ivRank {
                    DetailField(
                        label: "IV Rank",
                        value: "\(Int(ivRank))%",
                        color: ivRankColor
                    )
                }
            }
        }
    }
    
    @ViewBuilder
    private var liquiditySection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Liquidity & Data Quality")
                .font(.headline)
            
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                if let liquidityConf = rank.liquidityConfidence {
                    DetailField(
                        label: "Liquidity Confidence",
                        value: "\(liquidityConf, specifier: "%.2f")",
                        color: rank.liquidityColor
                    )
                }
                
                DetailField(
                    label: "Liquidity Level",
                    value: rank.liquidityLabel,
                    color: rank.liquidityColor
                )
                
                if let priceProvider = rank.priceProvider {
                    DetailField(label: "Price Provider", value: priceProvider.uppercased())
                }
                
                if let oiProvider = rank.oiProvider {
                    DetailField(label: "OI Provider", value: oiProvider.uppercased())
                }
                
                if let historySamples = rank.historySamples {
                    DetailField(label: "History Samples", value: "\(historySamples)")
                }
                
                if let historyAvgMark = rank.historyAvgMark {
                    DetailField(label: "Historical Avg Mark", value: "$\(historyAvgMark, specifier: "%.2f")")
                }
                
                if let historyWindow = rank.historyWindowDays {
                    DetailField(label: "History Window", value: "\(historyWindow) days")
                }
                
                if let coverage = rank.historyCoverageLabel {
                    DetailField(label: "Coverage", value: coverage)
                }
            }
        }
    }
    
    @ViewBuilder
    private var metadataSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Metadata")
                .font(.headline)
            
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                DetailField(label: "Run At", value: rank.runAt)
                
                if let runDate = rank.runAtDate {
                    DetailField(label: "Run Date", value: "\(runDate, style: .date)")
                }
                
                DetailField(label: "Mark Age", value: rank.markAgeLabel, color: markAgeColor)
                
                // Scores
                if let composite = rank.compositeRank {
                    DetailField(
                        label: "Composite Rank",
                        value: "\(Int(composite))/100",
                        color: rank.compositeColor
                    )
                }
                
                if let momentum = rank.momentumScore {
                    DetailField(label: "Momentum Score", value: "\(Int(momentum))/100", color: .green)
                }
                
                if let value = rank.valueScore {
                    DetailField(label: "Value Score", value: "\(Int(value))/100", color: .blue)
                }
                
                if let greeks = rank.greeksScore {
                    DetailField(label: "Greeks Score", value: "\(Int(greeks))/100", color: .orange)
                }
            }
        }
    }
    
    // MARK: - Color Helpers
    
    private var spreadColor: Color {
        guard let spreadPct = rank.spreadPctDisplay else { return .secondary }
        if spreadPct < 2.0 { return .green }
        if spreadPct < 5.0 { return .blue }
        if spreadPct < 10.0 { return .orange }
        return .red
    }
    
    private var deltaColor: Color {
        guard let delta = rank.delta else { return .secondary }
        let absDelta = abs(delta)
        if absDelta >= 0.7 { return .green }
        if absDelta >= 0.5 { return .blue }
        return .orange
    }
    
    private var volumeColor: Color {
        guard let volume = rank.volume else { return .secondary }
        if volume >= 500 { return .green }
        if volume >= 100 { return .blue }
        if volume >= 10 { return .orange }
        return .red
    }
    
    private var oiColor: Color {
        guard let oi = rank.openInterest else { return .secondary }
        if oi >= 1000 { return .green }
        if oi >= 500 { return .blue }
        if oi >= 100 { return .orange }
        return .red
    }
    
    private var ivRankColor: Color {
        guard let ivRank = rank.ivRank else { return .secondary }
        if ivRank >= 70 { return .red }
        if ivRank >= 50 { return .orange }
        if ivRank >= 30 { return .blue }
        return .green
    }
    
    private var markAgeColor: Color {
        guard let seconds = rank.markAgeSeconds, seconds >= 0 else { return .gray }
        if seconds < 120 { return .green }
        if seconds < 600 { return .orange }
        return .red
    }
}

// MARK: - Detail Field Component

private struct DetailField: View {
    let label: String
    let value: String
    var color: Color = .primary
    var copyable: Bool = false
    
    @State private var copied = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.caption)
                .foregroundStyle(.secondary)
            
            HStack {
                Text(value)
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundColor(color)
                    .textSelection(.enabled)
                
                if copyable {
                    Button {
                        NSPasteboard.general.clearContents()
                        NSPasteboard.general.setString(value, forType: .string)
                        copied = true
                        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                            copied = false
                        }
                    } label: {
                        Image(systemName: copied ? "checkmark" : "doc.on.doc")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                    .buttonStyle(.plain)
                    .help("Copy to clipboard")
                }
            }
        }
        .padding(8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(nsColor: .controlBackgroundColor))
        .cornerRadius(6)
    }
}

// MARK: - Preview

#Preview {
    ScrollView {
        ContractTabView(
            rank: OptionRank.example,
            symbol: "AAPL"
        )
        .padding()
    }
    .frame(width: 450)
}
