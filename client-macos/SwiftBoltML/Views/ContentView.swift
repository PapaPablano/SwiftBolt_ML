import SwiftUI

struct ContentView: View {
    var body: some View {
        NavigationSplitView {
            List {
                NavigationLink(destination: Text("Watchlist")) {
                    Label("Watchlist", systemImage: "star.fill")
                }
                NavigationLink(destination: Text("Portfolio")) {
                    Label("Portfolio", systemImage: "chart.pie.fill")
                }
                NavigationLink(destination: Text("Predictions")) {
                    Label("Predictions", systemImage: "waveform.path.ecg")
                }

                #if DEBUG
                Section("Development") {
                    NavigationLink(destination: DevToolsView()) {
                        Label("Dev Tools", systemImage: "wrench.and.screwdriver.fill")
                    }
                }
                #endif
            }
            .navigationTitle("SwiftBolt ML")
            .listStyle(.sidebar)
        } detail: {
            VStack(spacing: 16) {
                Image(systemName: "chart.line.uptrend.xyaxis")
                    .font(.system(size: 64))
                    .foregroundStyle(.secondary)
                Text("Select an item from the sidebar")
                    .font(.title2)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

#Preview {
    ContentView()
}
