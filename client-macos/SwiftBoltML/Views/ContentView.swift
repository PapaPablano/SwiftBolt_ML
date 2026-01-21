import SwiftUI

enum SidebarSection: Hashable {
    case stocks
    case portfolio
    case multileg
    case predictions
    case devtools
}

struct ContentView: View {
    @StateObject private var appViewModel = AppViewModel()
    @State private var activeSection: SidebarSection = .stocks

    var body: some View {
        NavigationSplitView {
            SidebarView(activeSection: $activeSection)
                .environmentObject(appViewModel)
        } detail: {
            switch activeSection {
            case .predictions:
                PredictionsView()
                    .environmentObject(appViewModel)
            case .portfolio:
                Text("Portfolio")
            case .multileg:
                MultiLegStrategyListView()
                    .environmentObject(appViewModel)
            default:
                DetailView()
                    .environmentObject(appViewModel)
            }
        }
        .frame(minWidth: 1200, minHeight: 800)
        .onChange(of: appViewModel.selectedSymbol) { oldValue, newValue in
            print("[DEBUG] ========================================")
            print("[DEBUG] ContentView detected selectedSymbol change")
            print("[DEBUG] - Old: \(oldValue?.ticker ?? "nil")")
            print("[DEBUG] - New: \(newValue?.ticker ?? "nil")")
            print("[DEBUG] ========================================")
            // Always return to stock detail when a symbol is selected
            activeSection = .stocks
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
    @Binding var activeSection: SidebarSection

    var body: some View {
        VStack(spacing: 0) {
            SymbolSearchView()
                .environmentObject(appViewModel)

            Divider()

            WatchlistView()
                .environmentObject(appViewModel)
                .frame(maxHeight: .infinity)

            Divider()

            List(selection: $activeSection) {
                Section("Navigation") {
                    NavigationLink(value: SidebarSection.portfolio) {
                        Label("Portfolio", systemImage: "chart.pie.fill")
                    }
                    NavigationLink(value: SidebarSection.multileg) {
                        Label("Multi-Leg", systemImage: "square.stack.3d.up")
                    }
                    NavigationLink(value: SidebarSection.predictions) {
                        Label("Predictions", systemImage: "waveform.path.ecg")
                    }
                }

                #if DEBUG
                Section("Development") {
                    NavigationLink(value: SidebarSection.devtools) {
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

    var body: some View {
        if appViewModel.selectedSymbol != nil {
            // Horizontal split: Chart on left, News on right
            HSplitView {
                ChartView()
                    .environmentObject(appViewModel)
                    .frame(minWidth: 600)

                VStack(spacing: 0) {
                    Picker("", selection: $appViewModel.selectedDetailTab) {
                        Text("News").tag(0)
                        Text("Options").tag(1)
                        Text("Analysis").tag(2)
                    }
                    .pickerStyle(.segmented)
                    .padding()
                    .frame(maxWidth: 300)

                    if appViewModel.selectedDetailTab == 0 {
                        NewsListView()
                            .environmentObject(appViewModel)
                    } else if appViewModel.selectedDetailTab == 1 {
                        OptionsChainView()
                            .environmentObject(appViewModel)
                    } else {
                        AnalysisView()
                            .environmentObject(appViewModel)
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
