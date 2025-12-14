import SwiftUI

struct ContentView: View {
    @StateObject private var appViewModel = AppViewModel()

    var body: some View {
        NavigationSplitView {
            SidebarView()
                .environmentObject(appViewModel)
        } detail: {
            DetailView()
                .environmentObject(appViewModel)
        }
        .frame(minWidth: 1200, minHeight: 800)
        .onChange(of: appViewModel.selectedSymbol) { oldValue, newValue in
            print("[DEBUG] ========================================")
            print("[DEBUG] ContentView detected selectedSymbol change")
            print("[DEBUG] - Old: \(oldValue?.ticker ?? "nil")")
            print("[DEBUG] - New: \(newValue?.ticker ?? "nil")")
            print("[DEBUG] ========================================")
        }
        #if DEBUG
        .onAppear {
            print("[DEBUG] ========================================")
            print("[DEBUG] ContentView.onAppear - Bootstrapping with AAPL")
            print("[DEBUG] ========================================")
            appViewModel.bootstrapForDebug()
        }
        #endif
    }
}

struct SidebarView: View {
    @EnvironmentObject var appViewModel: AppViewModel

    var body: some View {
        VStack(spacing: 0) {
            SymbolSearchView()
                .environmentObject(appViewModel)

            Divider()

            WatchlistView()
                .environmentObject(appViewModel)
                .frame(maxHeight: .infinity)

            Divider()

            List {
                Section("Navigation") {
                    NavigationLink(destination: Text("Portfolio")) {
                        Label("Portfolio", systemImage: "chart.pie.fill")
                    }
                    NavigationLink(destination: Text("Predictions")) {
                        Label("Predictions", systemImage: "waveform.path.ecg")
                    }
                }

                #if DEBUG
                Section("Development") {
                    NavigationLink(destination: DevToolsView()) {
                        Label("Dev Tools", systemImage: "wrench.and.screwdriver.fill")
                    }
                }
                #endif
            }
            .listStyle(.sidebar)
        }
        .navigationTitle("SwiftBolt ML")
    }
}

struct DetailView: View {
    @EnvironmentObject var appViewModel: AppViewModel
    @State private var selectedTab = 0

    var body: some View {
        if appViewModel.selectedSymbol != nil {
            // Horizontal split: Chart on left, News on right
            HSplitView {
                ChartView()
                    .environmentObject(appViewModel)
                    .frame(minWidth: 600)

                VStack(spacing: 0) {
                    Picker("", selection: $selectedTab) {
                        Text("News").tag(0)
                        Text("Analysis").tag(1)
                    }
                    .pickerStyle(.segmented)
                    .padding()
                    .frame(maxWidth: 300)

                    if selectedTab == 0 {
                        NewsListView()
                            .environmentObject(appViewModel)
                    } else {
                        Text("Analysis coming soon...")
                            .foregroundStyle(.secondary)
                            .frame(maxWidth: .infinity, maxHeight: .infinity)
                    }
                }
                .frame(minWidth: 300, idealWidth: 400, maxWidth: 500)
            }
        } else {
            EmptyStateView()
        }
    }
}

struct EmptyStateView: View {
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "chart.line.uptrend.xyaxis")
                .font(.system(size: 64))
                .foregroundStyle(.secondary)
            Text("Search for a symbol to get started")
                .font(.title2)
                .foregroundStyle(.secondary)
            Text("Use the search bar in the sidebar to find stocks, futures, or options")
                .font(.subheadline)
                .foregroundStyle(.tertiary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

#Preview {
    ContentView()
}
