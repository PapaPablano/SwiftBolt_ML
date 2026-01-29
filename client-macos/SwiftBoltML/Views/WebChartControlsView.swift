import SwiftUI

/// Advanced controls for WebChart features
/// Provides toggles for Heikin-Ashi, Volume Profile, and other Phase 1 features
struct WebChartControlsView: View {
    @ObservedObject var viewModel: ChartViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Chart Options")
                .font(.headline)
                .foregroundColor(.secondary)
            
            Divider()
            
            // Heikin-Ashi Toggle
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Heikin-Ashi Candles")
                        .font(.subheadline)
                    Text("Smoothed trend visualization")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                Toggle("", isOn: Binding.deferred(get: { viewModel.useHeikinAshi }, set: { viewModel.useHeikinAshi = $0 }))
                    .toggleStyle(.switch)
                    .labelsHidden()
            }
            .padding(.vertical, 4)
            
            // Volume Profile Toggle
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Volume Profile")
                        .font(.subheadline)
                    Text("Show volume distribution by price")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                Toggle("", isOn: Binding.deferred(get: { viewModel.showVolumeProfile }, set: { viewModel.showVolumeProfile = $0 }))
                    .toggleStyle(.switch)
                    .labelsHidden()
                    .onChange(of: viewModel.showVolumeProfile) { _, newValue in
                        if newValue {
                            DispatchQueue.main.async { viewModel.calculateVolumeProfile() }
                        }
                    }
            }
            .padding(.vertical, 4)
            
            // Volume Profile Info
            if viewModel.showVolumeProfile && !viewModel.volumeProfile.isEmpty {
                HStack {
                    Image(systemName: "chart.bar.fill")
                        .foregroundColor(.green)
                    Text("\(viewModel.volumeProfile.count) price levels")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    if let poc = viewModel.volumeProfile.first(where: { $0["pointOfControl"] as? Bool == true }),
                       let price = poc["price"] as? Double {
                        Spacer()
                        Text("POC: $\(String(format: "%.2f", price))")
                            .font(.caption)
                            .foregroundColor(.orange)
                    }
                }
                .padding(.horizontal, 8)
                .padding(.vertical, 6)
                .background(Color.secondary.opacity(0.1))
                .cornerRadius(6)
            }
        }
        .padding()
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(8)
    }
}

#Preview {
    WebChartControlsView(viewModel: ChartViewModel())
        .frame(width: 300)
        .padding()
}
