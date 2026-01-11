import SwiftUI

struct SplitAdjustmentAlert: View {
    let action: CorporateAction
    let onDismiss: () -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundColor(.orange)
                
                Text("Stock Split Detected")
                    .font(.headline)
                
                Spacer()
                
                Button(action: onDismiss) {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.secondary)
                }
            }
            
            Text("\(action.symbol) had a \(formatRatio(action.ratio ?? 1)):1 split on \(formatDate(action.exDate))")
                .font(.subheadline)
                .foregroundColor(.secondary)
            
            Text("Historical prices have been automatically adjusted.")
                .font(.caption)
                .foregroundStyle(.tertiary)
        }
        .padding()
        .background(Color.orange.opacity(0.1))
        .cornerRadius(12)
        .padding(.horizontal)
    }
    
    private func formatRatio(_ ratio: Double) -> String {
        return String(format: "%.0f", ratio)
    }
    
    private func formatDate(_ dateString: String) -> String {
        let isoFormatter = ISO8601DateFormatter()
        if let date = isoFormatter.date(from: dateString) {
            let formatter = DateFormatter()
            formatter.dateStyle = .medium
            return formatter.string(from: date)
        }
        return dateString
    }
}

#Preview {
    VStack(spacing: 16) {
        SplitAdjustmentAlert(
            action: CorporateAction(
                symbol: "AAPL",
                type: "stock_split",
                exDate: "2024-08-01T00:00:00Z",
                ratio: 4.0,
                cashAmount: nil
            ),
            onDismiss: {}
        )
        
        SplitAdjustmentAlert(
            action: CorporateAction(
                symbol: "NVDA",
                type: "stock_split",
                exDate: "2024-06-10T00:00:00Z",
                ratio: 10.0,
                cashAmount: nil
            ),
            onDismiss: {}
        )
    }
    .padding()
}
