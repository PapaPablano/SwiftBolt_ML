import SwiftUI

// MARK: - Inline Expiry Picker

struct FuturesExpiryPickerInline: View {
    let rootSymbol: String
    let contracts: [FuturesContract]
    let onSelect: (String) -> Void
    
    private var frontMonthContract: FuturesContract? {
        contracts.first { $0.isFrontMonth }
    }
    
    private var datedContracts: [FuturesContract] {
        // Filter out front month if it exists, show rest
        if frontMonthContract != nil {
            return Array(contracts.dropFirst().prefix(5))
        }
        return Array(contracts.prefix(6))
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Front Month (Recommended/Default)
            if let frontMonth = frontMonthContract {
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text("Front Month (Recommended)")
                            .font(.caption)
                            .fontWeight(.semibold)
                            .foregroundColor(.green)
                        
                        Spacer()
                        
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundColor(.green)
                            .font(.caption)
                    }
                    
                    Button(action: {
                        onSelect(frontMonth.symbol)
                    }) {
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(frontMonth.displayName)
                                    .font(.system(size: 13, weight: .medium))
                                
                                if let lastTrade = frontMonth.lastTradeDate {
                                    Text("Last trade: \(formatDate(lastTrade))")
                                        .font(.caption2)
                                        .foregroundColor(.secondary)
                                }
                            }
                            
                            Spacer()
                            
                            Text("Default")
                                .font(.caption2)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 2)
                                .background(Color.green.opacity(0.2))
                                .foregroundColor(.green)
                                .clipShape(Capsule())
                        }
                        .padding(.vertical, 6)
                        .padding(.horizontal, 8)
                        .background(Color.green.opacity(0.1))
                        .cornerRadius(6)
                    }
                    .buttonStyle(PlainButtonStyle())
                }
                
                Divider()
                    .padding(.vertical, 4)
            }
            
            // Continuous section
            VStack(alignment: .leading, spacing: 4) {
                Text("Continuous (Auto-rolling)")
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundColor(.secondary)
                
                HStack(spacing: 8) {
                    Button("\(rootSymbol)1! (Front)") {
                        onSelect("\(rootSymbol)1!")
                    }
                    .buttonStyle(FuturesExpiryButtonStyle(isPrimary: true))
                    
                    Button("\(rootSymbol)2!") {
                        onSelect("\(rootSymbol)2!")
                    }
                    .buttonStyle(FuturesExpiryButtonStyle(isPrimary: false))
                }
            }
            
            // Other dated contracts
            if !datedContracts.isEmpty {
                Divider()
                    .padding(.vertical, 4)
                
                VStack(alignment: .leading, spacing: 4) {
                    Text("Other Contracts")
                        .font(.caption)
                        .fontWeight(.semibold)
                        .foregroundColor(.secondary)
                    
                    LazyVStack(alignment: .leading, spacing: 2) {
                        ForEach(datedContracts) { contract in
                            Button(action: {
                                onSelect(contract.symbol)
                            }) {
                                HStack {
                                    Text(contract.displayName)
                                        .font(.system(size: 12))
                                    
                                    Spacer()
                                    
                                    if let lastTrade = contract.lastTradeDate {
                                        Text("Last: \(formatDate(lastTrade))")
                                            .font(.caption2)
                                            .foregroundColor(.secondary)
                                    }
                                }
                            }
                            .buttonStyle(PlainButtonStyle())
                            .padding(.vertical, 4)
                        }
                    }
                }
            }
        }
    }
    
    private func formatDate(_ dateString: String) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        if let date = formatter.date(from: dateString) {
            formatter.dateFormat = "MMM d"
            return formatter.string(from: date)
        }
        return dateString
    }
}

// MARK: - Button Style

struct FuturesExpiryButtonStyle: ButtonStyle {
    let isPrimary: Bool
    
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 12, weight: isPrimary ? .semibold : .medium))
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(
                isPrimary 
                    ? Color.accentColor.opacity(configuration.isPressed ? 0.3 : 0.2)
                    : Color.secondary.opacity(configuration.isPressed ? 0.2 : 0.1)
            )
            .foregroundColor(isPrimary ? .accentColor : .primary)
            .cornerRadius(6)
    }
}

// MARK: - Preview

#Preview {
    FuturesExpiryPickerInline(
        rootSymbol: "GC",
        contracts: [
            FuturesContract(
                id: "1",
                symbol: "GCZ25",
                contractCode: "Z25",
                expiryMonth: 12,
                expiryYear: 2025,
                lastTradeDate: "2025-12-29",
                isContinuous: false,
                continuousAlias: nil,
                isSpot: true
            ),
            FuturesContract(
                id: "2",
                symbol: "GCG26",
                contractCode: "G26",
                expiryMonth: 2,
                expiryYear: 2026,
                lastTradeDate: "2026-02-25",
                isContinuous: false,
                continuousAlias: nil,
                isSpot: false
            ),
            FuturesContract(
                id: "3",
                symbol: "GCJ26",
                contractCode: "J26",
                expiryMonth: 4,
                expiryYear: 2026,
                lastTradeDate: "2026-04-28",
                isContinuous: false,
                continuousAlias: nil,
                isSpot: false
            )
        ],
        onSelect: { symbol in
            print("Selected: \(symbol)")
        }
    )
    .padding()
}
