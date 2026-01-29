import SwiftUI

struct HydrationBanner: View {
    let isHydrating: Bool
    let progress: Int
    
    var body: some View {
        if isHydrating {
            HStack(spacing: 8) {
                ProgressView()
                    .frame(width: 32, height: 32)
                
                Text("Hydrating intraday… \(progress)%")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(Color.blue.opacity(0.1))
            .cornerRadius(8)
            .transition(.opacity)
        }
    }
}

#Preview {
    VStack(spacing: 20) {
        HydrationBanner(isHydrating: true, progress: 45)
        HydrationBanner(isHydrating: true, progress: 85)
        HydrationBanner(isHydrating: false, progress: 100)
    }
    .padding()
}
