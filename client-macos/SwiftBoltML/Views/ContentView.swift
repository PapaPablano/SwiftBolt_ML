import SwiftUI

// Sidebar section enums are in SidebarModels.swift

// MARK: - Content View

struct ContentView: View {
    @StateObject private var appViewModel = AppViewModel()
    @StateObject private var paperTradingService = PaperTradingService()
    @State private var activeSection: SidebarSection = .research(.chartsAndAnalysis)

    var body: some View {
        NavigationSplitView {
            SidebarView(activeSection: $activeSection)
                .environmentObject(appViewModel)
                .environmentObject(paperTradingService)
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
                        .opacity(activeSection == .research(.chartsAndAnalysis) ? 1 : 0)
                        .allowsHitTesting(activeSection == .research(.chartsAndAnalysis))

                    // Strategy Builder: single canonical entry point
                    if activeSection == .buildAndTest(.strategyBuilder) {
                        IntegratedStrategyBuilder(symbol: appViewModel.selectedSymbol?.ticker)
                    }

                    if activeSection == .research(.predictions) {
                        PredictionsView()
                            .environmentObject(appViewModel)
                    }
                    if activeSection == .trade(.portfolio) {
                        Text("Portfolio")
                    }
                    if activeSection == .buildAndTest(.multiLeg) {
                        MultiLegStrategyListView()
                            .environmentObject(appViewModel)
                    }
                    if activeSection == .trade(.paperTrading) {
                        PaperTradingDashboardView()
                            .environmentObject(paperTradingService)
                    }
                    if activeSection == .buildAndTest(.backtesting) {
                        BacktestResultsWebView(symbol: appViewModel.selectedSymbol?.ticker)
                    }
                    if activeSection == .trade(.liveTrading) {
                        Text("Live Trading")
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
            // Clamp stale selectedDetailTab values from the old 4-tab layout
            if appViewModel.selectedDetailTab > 2 {
                appViewModel.selectedDetailTab = 0
            }
            await appViewModel.checkSupabaseConnectivity()
            // Load paper trading positions eagerly so sidebar green dot
            // shows immediately, not only after navigating to Paper Trading
            await paperTradingService.loadData()
        }
        .onChange(of: appViewModel.selectedSymbol) { _, _ in
            DispatchQueue.main.async { activeSection = .research(.chartsAndAnalysis) }
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

// MARK: - Sidebar View

struct SidebarView: View {
    @EnvironmentObject var appViewModel: AppViewModel
    @EnvironmentObject var paperTradingService: PaperTradingService
    @Binding var activeSection: SidebarSection

    @StateObject private var marketService = MarketStatusService(
        supabaseURL: Config.supabaseURL.absoluteString,
        supabaseKey: Config.supabaseAnonKey
    )

    @AppStorage("sidebar.research.expanded") private var researchExpanded = true
    @AppStorage("sidebar.buildAndTest.expanded") private var buildAndTestExpanded = true
    @AppStorage("sidebar.trade.expanded") private var tradeExpanded = true
    #if DEBUG
    @AppStorage("sidebar.devtools.expanded") private var devtoolsExpanded = true
    #endif

    var body: some View {
        VStack(spacing: 0) {
            SymbolSearchView()
                .environmentObject(appViewModel)

            Divider()

            WatchlistView()
                .environmentObject(appViewModel)
                .frame(maxHeight: .infinity)

            Divider()

            // Status bar: active symbol + market status + connectivity
            SidebarStatusBar(
                appViewModel: appViewModel,
                marketService: marketService
            )

            Divider()

            List(selection: $activeSection) {
                DisclosureGroup(isExpanded: $researchExpanded) {
                    NavigationLink(value: SidebarSection.research(.chartsAndAnalysis)) {
                        Label("Charts & Analysis", systemImage: "chart.line.uptrend.xyaxis")
                    }
                    NavigationLink(value: SidebarSection.research(.predictions)) {
                        Label("Predictions", systemImage: "waveform.path.ecg")
                    }
                } label: {
                    Text("Research")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.secondary)
                }
                .selectionDisabled()

                DisclosureGroup(isExpanded: $buildAndTestExpanded) {
                    NavigationLink(value: SidebarSection.buildAndTest(.strategyBuilder)) {
                        Label("Strategy Builder", systemImage: "chart.line.uptrend.xyaxis")
                    }
                    NavigationLink(value: SidebarSection.buildAndTest(.backtesting)) {
                        Label("Backtesting", systemImage: "clock.arrow.2.circlepath")
                    }
                    NavigationLink(value: SidebarSection.buildAndTest(.multiLeg)) {
                        Label("Multi-Leg", systemImage: "square.stack.3d.up")
                    }
                } label: {
                    Text("Build & Test")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.secondary)
                }
                .selectionDisabled()

                DisclosureGroup(isExpanded: $tradeExpanded) {
                    NavigationLink(value: SidebarSection.trade(.paperTrading)) {
                        HStack {
                            Label("Paper Trading", systemImage: "dollarsign.circle")
                            Spacer()
                            if !paperTradingService.openPositions.isEmpty {
                                Circle()
                                    .fill(DesignTokens.Colors.success)
                                    .frame(width: 8, height: 8)
                            }
                        }
                    }
                    NavigationLink(value: SidebarSection.trade(.liveTrading)) {
                        Label("Live Trading", systemImage: "bolt.fill")
                    }
                    NavigationLink(value: SidebarSection.trade(.portfolio)) {
                        Label("Portfolio", systemImage: "chart.pie.fill")
                    }
                } label: {
                    Text("Trade")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.secondary)
                }
                .selectionDisabled()

                #if DEBUG
                DisclosureGroup(isExpanded: $devtoolsExpanded) {
                    NavigationLink(value: SidebarSection.devtools) {
                        Label("Dev Tools", systemImage: "wrench.and.screwdriver.fill")
                    }
                } label: {
                    Text("Development")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.secondary)
                }
                .selectionDisabled()
                #endif
            }
            .listStyle(.sidebar)
            .frame(minHeight: 220)
        }
        .navigationTitle("SwiftBolt ML")
        // MarketStatusService polls every 60s for the app's lifetime — intentionally
        // no onDisappear cleanup because SidebarView in NavigationSplitView never
        // disappears (the column hides but the view stays in the hierarchy).
        // The Timer is invalidated in deinit when the app terminates.
    }
}

// MARK: - Detail View

struct DetailView: View {
    @EnvironmentObject var appViewModel: AppViewModel

    var body: some View {
        if appViewModel.selectedSymbol != nil {
            HSplitView {
                ChartView()
                    .environmentObject(appViewModel)
                    .frame(minWidth: 600)

                NavigationStack {
                    VStack(spacing: 0) {
                        Picker("", selection: deferredBinding(
                            get: { appViewModel.selectedDetailTab },
                            set: { appViewModel.selectedDetailTab = $0 }
                        )) {
                            Text("News").tag(0)
                            Text("Options").tag(1)
                            Text("Analysis").tag(2)
                        }
                        .pickerStyle(.segmented)
                        .padding(.horizontal, DesignTokens.Spacing.lg)
                        .padding(.vertical, DesignTokens.Spacing.sm)

                        switch appViewModel.selectedDetailTab {
                        case 0:
                            NewsListView()
                                .environmentObject(appViewModel)
                        case 1:
                            OptionsChainView()
                                .environmentObject(appViewModel)
                        default:
                            AnalysisView()
                                .environmentObject(appViewModel)
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

// MARK: - Empty State

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

// MARK: - Connectivity Banner

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
