import SwiftUI
import WebKit

/// View for displaying 3D Greeks surface visualization using Plotly
struct GreeksSurfaceView: View {
    @StateObject private var viewModel = GreeksSurfaceViewModel()
    let symbol: String
    let underlyingPrice: Double
    let volatility: Double
    let riskFreeRate: Double
    
    @State private var optionType: String = "call"
    @State private var showControls = true
    
    var body: some View {
        VStack(spacing: 0) {
            // Header
            headerView
            
            Divider()
            
            // Content
            if viewModel.isLoading {
                loadingView
            } else if let error = viewModel.error {
                errorView(error)
            } else if let surfaceData = viewModel.surfaceData {
                surfaceVisualizationView(surfaceData)
            } else {
                emptyStateView
            }
        }
        .background(Color(nsColor: .windowBackgroundColor))
        .onAppear {
            Task {
                await viewModel.fetchSurface(
                    symbol: symbol,
                    underlyingPrice: underlyingPrice,
                    volatility: volatility,
                    riskFreeRate: riskFreeRate,
                    optionType: optionType
                )
            }
        }
        .onChange(of: optionType) {
            Task {
                await viewModel.fetchSurface(
                    symbol: symbol,
                    underlyingPrice: underlyingPrice,
                    volatility: volatility,
                    riskFreeRate: riskFreeRate,
                    optionType: optionType
                )
            }
        }
    }
    
    // MARK: - Header
    
    private var headerView: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("Greeks Surface")
                    .font(.title2.bold())
                Text("\(symbol) - \(optionType.capitalized)")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            // Option type selector
            Picker("Option Type", selection: $optionType) {
                Text("Call").tag("call")
                Text("Put").tag("put")
            }
            .pickerStyle(.segmented)
            .frame(width: 150)
            
            // Greek selector
            if viewModel.surfaceData != nil {
                Picker("Greek", selection: $viewModel.selectedGreek) {
                    ForEach(GreeksSurfaceViewModel.GreekType.allCases, id: \.self) { greek in
                        Text(greek.rawValue).tag(greek)
                    }
                }
                .pickerStyle(.menu)
                .frame(width: 120)
            }
        }
        .padding()
    }
    
    // MARK: - Loading
    
    private var loadingView: some View {
        VStack(spacing: 16) {
            ProgressView()
            Text("Calculating Greeks surface...")
                .font(.subheadline)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
    
    // MARK: - Error
    
    private func errorView(_ error: String) -> some View {
        let errorObj = NSError(domain: "GreeksSurface", code: 0, userInfo: [NSLocalizedDescriptionKey: error])
        let formatted = ErrorFormatter.userFriendlyMessage(from: errorObj)
        return StandardErrorView(
            title: formatted.title,
            message: formatted.message,
            icon: formatted.icon,
            retryAction: {
                Task {
                    await viewModel.fetchSurface(
                        symbol: symbol,
                        underlyingPrice: underlyingPrice,
                        volatility: volatility,
                        riskFreeRate: riskFreeRate,
                        optionType: optionType
                    )
                }
            }
        )
    }
    
    // MARK: - Empty State
    
    private var emptyStateView: some View {
        StandardEmptyView(
            title: "No Surface Data",
            message: "Enter parameters and click calculate to generate a 3D Greeks surface.",
            icon: "square.stack.3d.up",
            actionLabel: "Calculate Surface",
            action: {
                Task {
                    await viewModel.fetchSurface(
                        symbol: symbol,
                        underlyingPrice: underlyingPrice,
                        volatility: volatility,
                        riskFreeRate: riskFreeRate,
                        optionType: optionType
                    )
                }
            }
        )
    }
    
    // MARK: - Surface Visualization
    
    private func surfaceVisualizationView(_ data: GreeksSurfaceResponse) -> some View {
        VStack(spacing: 0) {
            // 3D Surface Plot
            GreeksSurfaceWebView(
                surfaceData: data,
                selectedGreek: viewModel.selectedGreek
            )
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            
            // Info panel
            infoPanel(data)
        }
    }
    
    private func infoPanel(_ data: GreeksSurfaceResponse) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Divider()
            
            HStack(spacing: 24) {
                InfoItem(label: "Underlying Price", value: String(format: "$%.2f", data.underlyingPrice))
                InfoItem(label: "Volatility", value: String(format: "%.1f%%", data.volatility * 100))
                InfoItem(label: "Risk-Free Rate", value: String(format: "%.2f%%", data.riskFreeRate * 100))
                InfoItem(label: "Strikes", value: "\(data.strikes.count) points")
                InfoItem(label: "Times", value: "\(data.times.count) points")
                
                Spacer()
                
                Text(viewModel.selectedGreek.description)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .padding()
        }
        .background(Color(nsColor: .controlBackgroundColor))
    }
    
    private struct InfoItem: View {
        let label: String
        let value: String
        
        var body: some View {
            VStack(alignment: .leading, spacing: 2) {
                Text(label)
                    .font(.caption)
                    .foregroundColor(.secondary)
                Text(value)
                    .font(.subheadline.bold())
            }
        }
    }
}

// MARK: - WebView for Plotly 3D Surface

struct GreeksSurfaceWebView: NSViewRepresentable {
    let surfaceData: GreeksSurfaceResponse
    let selectedGreek: GreeksSurfaceViewModel.GreekType
    
    func makeNSView(context: Context) -> WKWebView {
        let webView = WKWebView()
        webView.navigationDelegate = context.coordinator
        return webView
    }
    
    func updateNSView(_ webView: WKWebView, context: Context) {
        let html = generatePlotlyHTML()
        webView.loadHTMLString(html, baseURL: nil)
    }
    
    func makeCoordinator() -> Coordinator {
        Coordinator()
    }
    
    class Coordinator: NSObject, WKNavigationDelegate {
        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            print("[GreeksSurfaceWebView] Plotly surface loaded")
        }
    }
    
    private func generatePlotlyHTML() -> String {
        let greekGrid = getGreekGrid()
        
        // Convert Swift arrays to JavaScript arrays
        let strikesJS = surfaceData.strikes.map { String($0) }.joined(separator: ",")
        let timesJS = surfaceData.times.map { String($0) }.joined(separator: ",")
        let zDataJS = greekGrid.map { row in
            "[" + row.map { String($0) }.joined(separator: ",") + "]"
        }.joined(separator: ",\n        ")
        
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <style>
                body { margin: 0; padding: 0; }
                #plotly-div { width: 100%; height: 100vh; }
            </style>
        </head>
        <body>
            <div id="plotly-div"></div>
            <script>
                var strikes = [\(strikesJS)];
                var times = [\(timesJS)];
                var z = [
                    \(zDataJS)
                ];
                
                var data = [{
                    type: 'surface',
                    x: strikes,
                    y: times,
                    z: z,
                    colorscale: 'Viridis',
                    colorbar: {
                        title: '\(selectedGreek.rawValue)'
                    }
                }];
                
                var layout = {
                    title: '\(selectedGreek.rawValue) Surface (\(surfaceData.optionType.capitalized))',
                    scene: {
                        xaxis: { title: 'Strike Price' },
                        yaxis: { title: 'Time to Maturity (years)' },
                        zaxis: { title: '\(selectedGreek.rawValue)' },
                        camera: {
                            eye: { x: 1.5, y: 1.5, z: 1.5 }
                        }
                    },
                    margin: { l: 0, r: 0, t: 50, b: 0 },
                    autosize: true
                };
                
                Plotly.newPlot('plotly-div', data, layout, {responsive: true});
            </script>
        </body>
        </html>
        """
    }
    
    private func getGreekGrid() -> [[Double]] {
        switch selectedGreek {
        case .delta:
            return surfaceData.delta
        case .gamma:
            return surfaceData.gamma
        case .theta:
            return surfaceData.theta
        case .vega:
            return surfaceData.vega
        case .rho:
            return surfaceData.rho
        }
    }
}
