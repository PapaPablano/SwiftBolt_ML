import SwiftUI

/// Header component for the Contract Workbench
/// Displays composite rank badge, contract details, freshness, and action buttons
struct ContractWorkbenchHeader: View {
    let rank: OptionRank
    let symbol: String
    let onClose: () -> Void
    let onAddToStrategy: () -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Top row: Badge + Contract Info + Actions
            HStack(alignment: .top, spacing: 12) {
                // Composite Rank Badge
                VStack(spacing: 4) {
                    Text("\(rank.compositeScoreDisplay)")
                        .font(.system(size: 36, weight: .bold, design: .rounded))
                        .foregroundColor(rank.compositeColor)
                    Text("RANK")
                        .font(.system(size: 9, weight: .semibold))
                        .foregroundStyle(.secondary)
                }
                .frame(width: 70, height: 70)
                .background(rank.compositeColor.opacity(0.15))
                .cornerRadius(12)
                
                // Contract Details
                VStack(alignment: .leading, spacing: 6) {
                    // Signal label
                    HStack(spacing: 6) {
                        Circle()
                            .fill(rank.compositeColor)
                            .frame(width: 8, height: 8)
                        Text(rank.scoreLabel)
                            .font(.caption)
                            .fontWeight(.semibold)
                            .foregroundColor(rank.compositeColor)
                    }
                    
                    // Contract description
                    HStack(spacing: 4) {
                        Text(symbol)
                            .font(.title3)
                            .fontWeight(.bold)
                        Text("$\(rank.strike, specifier: "%.2f")")
                            .font(.title3)
                            .fontWeight(.bold)
                        Text(rank.side.rawValue.uppercased())
                            .font(.title3)
                            .fontWeight(.bold)
                            .foregroundColor(rank.side == .call ? .green : .red)
                    }
                    
                    // Expiry
                    if let expiryDate = rank.expiryDate, let dte = rank.daysToExpiry {
                        HStack(spacing: 4) {
                            Image(systemName: "calendar")
                                .font(.caption2)
                            Text("Expires \(expiryDate, style: .date)")
                                .font(.caption)
                            Text("•")
                                .font(.caption2)
                            Text("\(dte) DTE")
                                .font(.caption)
                        }
                        .foregroundStyle(.secondary)
                    }
                }
                
                Spacer()
                
                // Actions
                VStack(spacing: 8) {
                    // Freshness indicator
                    freshnessIndicator
                    
                    HStack(spacing: 6) {
                        // Add to Strategy button
                        Button {
                            onAddToStrategy()
                        } label: {
                            Image(systemName: "plus.circle")
                                .font(.title3)
                        }
                        .buttonStyle(.plain)
                        .help("Add to Multi-Leg Strategy")
                        
                        // Close button
                        Button {
                            onClose()
                        } label: {
                            Image(systemName: "xmark.circle.fill")
                                .font(.title3)
                                .foregroundStyle(.secondary)
                        }
                        .buttonStyle(.plain)
                        .help("Close Workbench")
                    }
                }
            }
            
            // Active signals badges (if any)
            if rank.hasSignals {
                HStack(spacing: 6) {
                    ForEach(rank.activeSignals, id: \.self) { signal in
                        Text(signal)
                            .font(.caption2)
                            .fontWeight(.semibold)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(signalColor(for: signal).opacity(0.2))
                            .foregroundColor(signalColor(for: signal))
                            .cornerRadius(6)
                    }
                }
            }
        }
    }
    
    // MARK: - Freshness Indicator
    
    @ViewBuilder
    private var freshnessIndicator: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(freshnessColor)
                .frame(width: 6, height: 6)
            Text(freshnessLabel)
                .font(.caption2)
                .foregroundColor(freshnessColor)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(freshnessColor.opacity(0.1))
        .cornerRadius(6)
    }
    
    private var freshnessLabel: String {
        guard let seconds = rank.markAgeSeconds, seconds >= 0 else {
            return "Unknown"
        }
        
        if seconds < 120 {
            return "Fresh: \(rank.markAgeLabel)"
        } else if seconds < 600 {
            return "Recent: \(rank.markAgeLabel)"
        } else {
            return "Stale: \(rank.markAgeLabel)"
        }
    }
    
    private var freshnessColor: Color {
        guard let seconds = rank.markAgeSeconds, seconds >= 0 else {
            return .gray
        }
        
        if seconds < 120 {
            return .green
        } else if seconds < 600 {
            return .orange
        } else {
            return .red
        }
    }
    
    // MARK: - Helper Methods
    
    private func signalColor(for signal: String) -> Color {
        switch signal {
        case "BUY": return .green
        case "DISCOUNT": return .blue
        case "RUNNER": return .purple
        case "GREEKS": return .orange
        default: return .gray
        }
    }
}

// MARK: - Preview

#Preview {
    VStack {
        ContractWorkbenchHeader(
            rank: OptionRank.example,
            symbol: "AAPL",
            onClose: {},
            onAddToStrategy: {}
        )
        .padding()
        
        Divider()
        
        // Example with different signal
        ContractWorkbenchHeader(
            rank: OptionRank.example,
            symbol: "TSLA",
            onClose: {},
            onAddToStrategy: {}
        )
        .padding()
    }
    .frame(width: 450)
}
