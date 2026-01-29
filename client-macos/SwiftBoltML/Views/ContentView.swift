import SwiftUI

// #region agent log
func _agentLog(_ message: String, location: String, data: [String: String] = [:], hypothesisId: String = "") {
    let logPath = "/Users/ericpeterson/SwiftBolt_ML/.cursor/debug.log"
    var payload: [String: Any] = [
        "timestamp": Int(Date().timeIntervalSince1970 * 1000),
        "location": location,
        "message": message,
        "data": data,
        "sessionId": "debug-session",
        "hypothesisId": hypothesisId
    ]
    if let json = try? JSONSerialization.data(withJSONObject: payload),
       let line = String(data: json, encoding: .utf8) {
        if !FileManager.default.fileExists(atPath: logPath) { FileManager.default.createFile(atPath: logPath, contents: nil) }
        if let handle = FileHandle(forWritingAtPath: logPath) {
            handle.seekToEndOfFile()
            handle.write((line + "\n").data(using: .utf8)!)
            handle.closeFile()
        }
    }
}
// #endregion

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
        // #region agent log
        let _ = _agentLog("ContentView body", location: "ContentView.swift:body", data: ["activeSection": "\(activeSection)"], hypothesisId: "B")
        // #endregion
        return NavigationSplitView {
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
        .onChange(of: activeSection) { oldValue, newValue in
            // #region agent log
            _agentLog("activeSection changed", location: "ContentView.swift:onChange(activeSection)", data: ["old": "\(oldValue)", "new": "\(newValue)"], hypothesisId: "B")
            // #endregion
        }
        .onChange(of: appViewModel.selectedSymbol) { oldValue, newValue in
            print("[DEBUG] ========================================")
            print("[DEBUG] ContentView detected selectedSymbol change")
            print("[DEBUG] - Old: \(oldValue?.ticker ?? "nil")")
            print("[DEBUG] - New: \(newValue?.ticker ?? "nil")")
            print("[DEBUG] ========================================")
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
        // #region agent log
        let _ = _agentLog("DetailView body", location: "ContentView.swift:DetailView", data: ["selectedDetailTab": "\(appViewModel.selectedDetailTab)", "hasSymbol": "\(appViewModel.selectedSymbol != nil)"], hypothesisId: "A")
        // #endregion
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
                }
                .frame(minWidth: 300, idealWidth: 400, maxWidth: 600)
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
