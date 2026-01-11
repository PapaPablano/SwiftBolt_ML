import SwiftUI

struct MarketStatusBadge: View {
    @ObservedObject var marketService: MarketStatusService
    
    var body: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(marketService.isMarketOpen ? Color.green : Color.red)
                .frame(width: 8, height: 8)
            
            Text(marketService.isMarketOpen ? "Market Open" : "Market Closed")
                .font(.caption)
                .foregroundColor(.secondary)
            
            if let nextEvent = marketService.nextEvent {
                Text("• \(timeUntil(nextEvent))")
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(Color.gray.opacity(0.1))
        .cornerRadius(12)
    }
    
    private func timeUntil(_ date: Date) -> String {
        let interval = date.timeIntervalSinceNow
        let hours = Int(interval / 3600)
        let minutes = Int((interval.truncatingRemainder(dividingBy: 3600)) / 60)
        
        if interval < 0 {
            return "updating..."
        } else if hours > 0 {
            return "\(hours)h \(minutes)m"
        } else {
            return "\(minutes)m"
        }
    }
}

#Preview {
    VStack(spacing: 16) {
        MarketStatusBadge(
            marketService: {
                let service = MarketStatusService(
                    supabaseURL: "https://example.supabase.co",
                    supabaseKey: "test-key"
                )
                service.isMarketOpen = true
                service.nextEvent = Date().addingTimeInterval(3600 * 2.5) // 2.5 hours from now
                return service
            }()
        )
        
        MarketStatusBadge(
            marketService: {
                let service = MarketStatusService(
                    supabaseURL: "https://example.supabase.co",
                    supabaseKey: "test-key"
                )
                service.isMarketOpen = false
                service.nextEvent = Date().addingTimeInterval(3600 * 15) // 15 hours from now
                return service
            }()
        )
    }
    .padding()
}
