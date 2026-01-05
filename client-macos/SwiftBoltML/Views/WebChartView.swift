import SwiftUI
import WebKit
import Combine

/// SwiftUI wrapper for Lightweight Charts via WKWebView
/// Provides TradingView-style charting with Swift↔JS bridge
struct WebChartView: NSViewRepresentable {
    @ObservedObject var viewModel: ChartViewModel
    @StateObject private var bridge = ChartBridge()

    /// Coordinator handles WKWebView lifecycle and data updates
    class Coordinator: NSObject, WKNavigationDelegate {
        var parent: WebChartView
        var cancellables = Set<AnyCancellable>()
        var hasLoadedInitialData = false

        init(_ parent: WebChartView) {
            self.parent = parent
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            print("[WebChartView] Navigation finished")
        }

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            print("[WebChartView] Navigation failed: \(error.localizedDescription)")
        }

        func setupDataBindings() {
            // Subscribe to chart data changes
            parent.viewModel.$chartData
                .receive(on: DispatchQueue.main)
                .sink { [weak self] chartData in
                    guard let self = self,
                          self.parent.bridge.isReady,
                          let data = chartData else { return }

                    self.updateChart(with: data)
                }
                .store(in: &cancellables)

            // Subscribe to bridge ready state
            parent.bridge.$isReady
                .receive(on: DispatchQueue.main)
                .sink { [weak self] isReady in
                    guard let self = self, isReady else { return }

                    // Load initial data when bridge becomes ready
                    if !self.hasLoadedInitialData,
                       let data = self.parent.viewModel.chartData {
                        self.updateChart(with: data)
                        self.hasLoadedInitialData = true
                    }
                }
                .store(in: &cancellables)
        }

        private func updateChart(with data: ChartResponse) {
            let bridge = parent.bridge

            // Set candlestick data
            bridge.setCandles(from: data.bars)

            // Set ML forecast if available
            if let mlSummary = data.mlSummary,
               let firstHorizon = mlSummary.horizons.first {
                bridge.setForecast(
                    from: firstHorizon,
                    direction: mlSummary.overallLabel ?? "neutral"
                )

                // Add S/R levels if available
                if let srLevels = mlSummary.srLevels {
                    bridge.setSRLevels(
                        support: srLevels.nearestSupport,
                        resistance: srLevels.nearestResistance
                    )
                }
            }

            // Set indicators based on config
            let config = parent.viewModel.indicatorConfig

            if config.showSMA20 {
                bridge.setIndicator(
                    id: "sma20",
                    name: "SMA(20)",
                    data: parent.viewModel.sma20,
                    color: "#4db8ff"
                )
            }

            if config.showSMA50 {
                bridge.setIndicator(
                    id: "sma50",
                    name: "SMA(50)",
                    data: parent.viewModel.sma50,
                    color: "#ffa600"
                )
            }

            if config.showEMA9 {
                bridge.setIndicator(
                    id: "ema9",
                    name: "EMA(9)",
                    data: parent.viewModel.ema9,
                    color: "#00ffbf"
                )
            }

            if config.showEMA21 {
                bridge.setIndicator(
                    id: "ema21",
                    name: "EMA(21)",
                    data: parent.viewModel.ema21,
                    color: "#ff80b3"
                )
            }

            if config.showSMA200 {
                bridge.setIndicator(
                    id: "sma200",
                    name: "SMA(200)",
                    data: parent.viewModel.sma200,
                    color: "#ff5555"
                )
            }

            // Bollinger Bands
            if config.showBollingerBands {
                bridge.setIndicator(
                    id: "bb_upper",
                    name: "BB Upper",
                    data: parent.viewModel.bollingerUpper,
                    color: "#9966ff"
                )
                bridge.setIndicator(
                    id: "bb_middle",
                    name: "BB Middle",
                    data: parent.viewModel.bollingerMiddle,
                    color: "#9966ff"
                )
                bridge.setIndicator(
                    id: "bb_lower",
                    name: "BB Lower",
                    data: parent.viewModel.bollingerLower,
                    color: "#9966ff"
                )
            }

            // SuperTrend with trend-based coloring
            if config.showSuperTrend {
                bridge.setSuperTrend(
                    data: parent.viewModel.superTrendLine,
                    trend: parent.viewModel.superTrendTrend
                )
            }

            // Add SuperTrend AI signals if enabled
            if config.showSignalMarkers {
                let signals = parent.viewModel.superTrendAISignals
                if !signals.isEmpty {
                    bridge.setSignals(signals)
                }
            }

            // Volume sub-panel
            if config.showVolume {
                bridge.setVolume(bars: data.bars)
            } else {
                bridge.hidePanel("volume")
            }

            // Oscillator sub-panels
            if config.showRSI {
                bridge.setRSI(data: parent.viewModel.rsi)
            } else {
                bridge.hidePanel("rsi")
            }

            if config.showMACD {
                bridge.setMACD(
                    line: parent.viewModel.macdLine,
                    signal: parent.viewModel.macdSignal,
                    histogram: parent.viewModel.macdHistogram
                )
            } else {
                bridge.hidePanel("macd")
            }

            if config.showStochastic {
                bridge.setStochastic(
                    k: parent.viewModel.stochasticK,
                    d: parent.viewModel.stochasticD
                )
            } else {
                bridge.hidePanel("stochastic")
            }

            if config.showKDJ {
                bridge.setKDJ(
                    k: parent.viewModel.kdjK,
                    d: parent.viewModel.kdjD,
                    j: parent.viewModel.kdjJ
                )
            } else {
                bridge.hidePanel("kdj")
            }

            if config.showADX {
                bridge.setADX(
                    adx: parent.viewModel.adxLine,
                    plusDI: parent.viewModel.plusDI,
                    minusDI: parent.viewModel.minusDI
                )
            } else {
                bridge.hidePanel("adx")
            }

            if config.showATR {
                bridge.setATR(data: parent.viewModel.atr)
            } else {
                bridge.hidePanel("atr")
            }

            print("[WebChartView] Chart updated with \(data.bars.count) bars")
        }
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    func makeNSView(context: Context) -> WKWebView {
        // Configure WKWebView
        let config = WKWebViewConfiguration()

        // Enable developer extras for debugging (optional, remove in production)
        config.preferences.setValue(true, forKey: "developerExtrasEnabled")

        // Register message handler for JS → Swift communication
        config.userContentController.add(bridge, name: "bridge")

        // Create webview
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = context.coordinator

        // Attach bridge to webview
        bridge.attach(to: webView)

        // Allow file:// URL access for local resources
        if #available(macOS 13.3, *) {
            webView.isInspectable = true  // Enable Web Inspector
        }

        // Load bundled HTML
        loadChart(in: webView)

        // Setup data bindings
        context.coordinator.setupDataBindings()

        return webView
    }

    func updateNSView(_ webView: WKWebView, context: Context) {
        // Updates are handled via Combine subscriptions in Coordinator
    }

    private func loadChart(in webView: WKWebView) {
        // First try to find the resources in the app bundle
        if let htmlURL = Bundle.main.url(
            forResource: "index",
            withExtension: "html",
            subdirectory: "WebChart"
        ) {
            let directoryURL = htmlURL.deletingLastPathComponent()
            webView.loadFileURL(htmlURL, allowingReadAccessTo: directoryURL)
            print("[WebChartView] Loading chart from bundle: \(htmlURL)")
            return
        }

        // Fallback: try to find in Resources folder (for development)
        let resourcesPath = "/Users/ericpeterson/SwiftBolt_ML/client-macos/SwiftBoltML/Resources/WebChart"
        let htmlPath = "\(resourcesPath)/index.html"

        if FileManager.default.fileExists(atPath: htmlPath) {
            let htmlURL = URL(fileURLWithPath: htmlPath)
            let directoryURL = htmlURL.deletingLastPathComponent()
            webView.loadFileURL(htmlURL, allowingReadAccessTo: directoryURL)
            print("[WebChartView] Loading chart from development path: \(htmlURL)")
            return
        }

        print("[WebChartView] ERROR: Could not find chart HTML file")
    }

    /// Cleanup when view is dismantled
    static func dismantleNSView(_ nsView: WKWebView, coordinator: Coordinator) {
        // Remove message handler to prevent memory leaks
        nsView.configuration.userContentController.removeScriptMessageHandler(forName: "bridge")
        coordinator.cancellables.removeAll()
    }
}

// MARK: - Preview

#Preview {
    WebChartView(viewModel: ChartViewModel())
        .frame(width: 800, height: 500)
}

// MARK: - Convenience Modifiers

extension WebChartView {
    /// Add a custom event handler
    func onChartEvent(_ handler: @escaping (ChartEvent) -> Void) -> some View {
        self.onReceive(bridge.eventPublisher) { event in
            handler(event)
        }
    }
}

// MARK: - Optional: Standalone Preview Container

/// For testing the web chart in isolation
struct WebChartPreviewContainer: View {
    @StateObject private var viewModel = ChartViewModel()

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text("Lightweight Charts Preview")
                    .font(.headline)
                Spacer()
                Button("Load Sample Data") {
                    loadSampleData()
                }
                .buttonStyle(.borderedProminent)
            }
            .padding()

            Divider()

            // Chart
            WebChartView(viewModel: viewModel)
        }
        .frame(minWidth: 600, minHeight: 400)
    }

    private func loadSampleData() {
        // Generate sample candlestick data
        var bars: [OHLCBar] = []
        var price: Double = 100.0
        let baseDate = Date().addingTimeInterval(-86400 * 100)  // 100 days ago

        for i in 0..<100 {
            let date = baseDate.addingTimeInterval(Double(i) * 86400)
            let change = Double.random(in: -3...3)
            let open = price
            price += change
            let close = price
            let high = max(open, close) + Double.random(in: 0...2)
            let low = min(open, close) - Double.random(in: 0...2)
            let volume = Double.random(in: 1_000_000...10_000_000)

            bars.append(OHLCBar(
                ts: date,
                open: open,
                high: high,
                low: low,
                close: close,
                volume: volume
            ))
        }

        // For preview, just print the sample bar count
        print("[Preview] Would load \(bars.count) sample bars")
    }
}

#Preview("Standalone Container") {
    WebChartPreviewContainer()
}
