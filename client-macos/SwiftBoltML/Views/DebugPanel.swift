import SwiftUI

struct DebugPanel: View {
    @EnvironmentObject var appViewModel: AppViewModel

    private var chartViewModel: ChartViewModel {
        appViewModel.chartViewModel
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("🔍 Debug Panel")
                .font(.headline)
                .padding(.bottom, 4)

            Divider()

            Group {
                Text("AppViewModel State:")
                    .font(.subheadline.bold())
                Text("  • selectedSymbol: \(appViewModel.selectedSymbol?.ticker ?? "nil")")
                    .monospaced()
                Text("  • selectedSymbol.assetType: \(appViewModel.selectedSymbol?.assetType ?? "nil")")
                    .monospaced()
            }

            Divider()

            Group {
                Text("ChartViewModel State:")
                    .font(.subheadline.bold())
                Text("  • selectedSymbol: \(chartViewModel.selectedSymbol?.ticker ?? "nil")")
                    .monospaced()
                Text("  • timeframe: \(chartViewModel.timeframe)")
                    .monospaced()
                Text("  • isLoading: \(chartViewModel.isLoading ? "true" : "false")")
                    .monospaced()
                    .foregroundColor(chartViewModel.isLoading ? .orange : .primary)
                Text("  • errorMessage: \(chartViewModel.errorMessage ?? "nil")")
                    .monospaced()
                    .foregroundColor(chartViewModel.errorMessage != nil ? .red : .primary)
                Text("  • chartData: \(chartViewModel.chartData == nil ? "nil" : "non-nil")")
                    .monospaced()
                    .foregroundColor(chartViewModel.chartData != nil ? .green : .red)
                Text("  • bars.count: \(chartViewModel.bars.count)")
                    .monospaced()
                    .foregroundColor(chartViewModel.bars.isEmpty ? .red : .green)
            }

            if !chartViewModel.bars.isEmpty {
                Divider()

                Group {
                    Text("Latest Bar:")
                        .font(.subheadline.bold())
                    if let latestBar = chartViewModel.bars.last {
                        Text("  • ts: \(latestBar.ts, format: .iso8601)")
                            .monospaced()
                            .font(.caption)
                        Text("  • open: \(latestBar.open, format: .number.precision(.fractionLength(2)))")
                            .monospaced()
                            .font(.caption)
                        Text("  • close: \(latestBar.close, format: .number.precision(.fractionLength(2)))")
                            .monospaced()
                            .font(.caption)
                    }
                }
            }

            Divider()

            Group {
                Text("NewsViewModel State:")
                    .font(.subheadline.bold())
                Text("  • isLoading: \(appViewModel.newsViewModel.isLoading ? "true" : "false")")
                    .monospaced()
                Text("  • newsItems.count: \(appViewModel.newsViewModel.newsItems.count)")
                    .monospaced()
            }

            Divider()

            HStack {
                Button("Force Refresh") {
                    Task {
                        await appViewModel.refreshData()
                    }
                }
                .buttonStyle(.borderedProminent)

                Button("Clear Selection") {
                    appViewModel.clearSelection()
                }
                .buttonStyle(.bordered)
            }
        }
        .padding()
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .font(.caption)
    }
}

#Preview {
    DebugPanel()
        .environmentObject(AppViewModel())
        .frame(width: 400)
}
