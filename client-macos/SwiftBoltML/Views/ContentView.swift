import SwiftUI

enum StrategyPlatformSection: Hashable {
    case builder
    case paperTrading
    case backtesting
    case liveTrading
}

enum SidebarSection: Hashable {
    case stocks
    case portfolio
    case multileg
    case predictions
    case tradestation
    case strategyPlatform(StrategyPlatformSection)
    #if DEBUG
    case devtools
    #endif
}

struct ContentView: View {
    @StateObject private var appViewModel = AppViewModel()
    @State private var activeSection: SidebarSection = .stocks

    var body: some View {
        NavigationSplitView {
            SidebarView(activeSection: $activeSection)
                .environmentObject(appViewModel)
        } detail: {
            VStack(spacing: 0) {
                if appViewModel.supabaseUnreachable {
                    SupabaseConnectivityBanner()
                        .environmentObject(appViewModel)
                }

                // ZStack keeps the chart's WKWebView alive across tab switches.
                // Non-chart tabs use opacity(0) so the JS context continues running.
                ZStack {
                    // Chart (always mounted, hidden when another section is active)
                    DetailView()
                        .environmentObject(appViewModel)
                        .opacity(activeSection == .stocks ? 1 : 0)
                        .allowsHitTesting(activeSection == .stocks)

                    // Strategy Builder (always mounted, shares chart overlay via notifications)
                    IntegratedStrategyBuilder(symbol: appViewModel.selectedSymbol?.ticker)
                        .opacity(activeSection == .tradestation ? 1 : 0)
                        .allowsHitTesting(activeSection == .tradestation)

                    // Other sections: only mounted when active
                    if activeSection == .predictions {
                        PredictionsView()
                            .environmentObject(appViewModel)
                    }
                    if activeSection == .portfolio {
                        Text("Portfolio")
                    }
                    if activeSection == .multileg {
                        MultiLegStrategyListView()
                            .environmentObject(appViewModel)
                    }
                    if activeSection == .strategyPlatform(.builder) {
                        StrategyBuilderWebView(symbol: appViewModel.selectedSymbol?.ticker)
                    }
                    if activeSection == .strategyPlatform(.paperTrading) {
                        PaperTradingDashboardView()
                    }
                    if activeSection == .strategyPlatform(.backtesting) {
                        BacktestResultsWebView(symbol: appViewModel.selectedSymbol?.ticker)
                    }
                    #if DEBUG
                    if activeSection == .devtools {
                        DevToolsView()
                    }
                    #endif
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .frame(minWidth: 1200, minHeight: 800)
        .task {
            await appViewModel.checkSupabaseConnectivity()
        }
        .onChange(of: appViewModel.selectedSymbol) { _, _ in
            // Defer to avoid publishing changes from within view updates
            DispatchQueue.main.async { activeSection = .stocks }
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
                Section {
                    NavigationLink(value: SidebarSection.tradestation) {
                        Label("Strategy Builder", systemImage: "chart.line.uptrend.xyaxis")
                    }
                } header: {
                    Text("Strategy")
                }

                Section {
                    NavigationLink(value: SidebarSection.strategyPlatform(.builder)) {
                        Label("Strategy Builder", systemImage: "checklist")
                    }
                    NavigationLink(value: SidebarSection.strategyPlatform(.paperTrading)) {
                        Label("Paper Trading", systemImage: "dollarsign.circle")
                    }
                    NavigationLink(value: SidebarSection.strategyPlatform(.backtesting)) {
                        Label("Backtesting", systemImage: "clock.arrow.2.circlepath")
                    }
                    NavigationLink(value: SidebarSection.strategyPlatform(.liveTrading)) {
                        Label("Live Trading", systemImage: "bolt.fill")
                    }
                } header: {
                    Text("Strategy Platform")
                }

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
            .frame(minHeight: 180)
        }
        .navigationTitle("SwiftBolt ML")
    }
}

struct DetailView: View {
    @EnvironmentObject var appViewModel: AppViewModel

    var body: some View {
        if appViewModel.selectedSymbol != nil {
            // Horizontal split: Chart on left, News/Options/Analysis on right
            HSplitView {
                ChartView()
                    .environmentObject(appViewModel)
                    .frame(minWidth: 600)

                NavigationStack {
                    VStack(spacing: 0) {
                        Picker("", selection: deferredBinding(get: { appViewModel.selectedDetailTab }, set: { appViewModel.selectedDetailTab = $0 })) {
                            Text("News").tag(0)
                            Text("Options").tag(1)
                            Text("Analysis").tag(2)
                            Text("Strategy Builder").tag(3)
                        }
                        .pickerStyle(.menu)
                        .padding()
                        .frame(minWidth: 160)

                        if appViewModel.selectedDetailTab == 0 {
                            NewsListView()
                                .environmentObject(appViewModel)
                        } else if appViewModel.selectedDetailTab == 1 {
                            OptionsChainView()
                                .environmentObject(appViewModel)
                        } else if appViewModel.selectedDetailTab == 2 {
                            AnalysisView()
                                .environmentObject(appViewModel)
                        } else {
                            IntegratedStrategyBuilder(symbol: appViewModel.selectedSymbol?.ticker)
                        }
                    }
                }
                .frame(minWidth: 320, idealWidth: 420, maxWidth: 600)
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

/// Shown when Supabase host can't resolve (DNS -1003). Explains offline mode and offers retry.
struct SupabaseConnectivityBanner: View {
    @EnvironmentObject var appViewModel: AppViewModel

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "wifi.slash")
                .foregroundStyle(.secondary)
            Text("Supabase unreachable (DNS). Using offline/cached data.")
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
            Spacer()
            Button("Retry") {
                Task {
                    SupabaseConnectivity.resetCache()
                    await appViewModel.checkSupabaseConnectivity()
                }
            }
            .buttonStyle(.bordered)
            .controlSize(.small)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(Color.orange.opacity(0.15))
    }
}

#Preview {
    ContentView()
}
