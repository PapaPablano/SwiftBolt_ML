import SwiftUI
import WebKit

/// View for displaying 3D volatility surface visualization using Plotly
struct VolatilitySurfaceView: View {
    @StateObject private var viewModel = VolatilitySurfaceViewModel()
    let symbol: String
    let slices: [VolatilitySurfaceSlice]
    
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
                    slices: slices
                )
            }
        }
    }
    
    // MARK: - Header
    
    private var headerView: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("Volatility Surface")
                    .font(.title2.bold())
                Text(symbol)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            Text("\(slices.count) slices")
                .font(.subheadline)
                .foregroundColor(.secondary)
        }
        .padding()
    }
    
    // MARK: - Loading
    
    private var loadingView: some View {
        VStack(spacing: 16) {
            ProgressView()
            Text("Fitting volatility surface...")
                .font(.subheadline)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
    
    // MARK: - Error
    
    private func errorView(_ error: String) -> some View {
        let errorObj = NSError(domain: "VolatilitySurface", code: 0, userInfo: [NSLocalizedDescriptionKey: error])
        let formatted = ErrorFormatter.userFriendlyMessage(from: errorObj)
        return StandardErrorView(
            title: formatted.title,
            message: formatted.message,
            icon: formatted.icon,
            retryAction: {
                Task {
                    await viewModel.fetchSurface(
                        symbol: symbol,
                        slices: slices
                    )
                }
            }
        )
    }
    
    // MARK: - Empty State
    
    private var emptyStateView: some View {
        StandardEmptyView(
            title: "No Surface Data",
            message: "Volatility surface will be generated from the provided slices.",
            icon: "chart.3d",
            actionLabel: "Generate Surface",
            action: {
                Task {
                    await viewModel.fetchSurface(
                        symbol: symbol,
                        slices: slices
                    )
                }
            }
        )
    }
    
    // MARK: - Surface Visualization
    
    private func surfaceVisualizationView(_ data: VolatilitySurfaceResponse) -> some View {
        VStack(spacing: 0) {
            // 3D Surface Plot
            VolatilitySurfaceWebView(surfaceData: data)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            
            // Info panel
            infoPanel(data)
        }
    }
    
    private func infoPanel(_ data: VolatilitySurfaceResponse) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Divider()
            
            HStack(spacing: 24) {
                InfoItem(label: "Strikes", value: "\(data.strikes.count) points")
                InfoItem(label: "Maturities", value: "\(data.maturities.count) points")
                InfoItem(label: "Strike Range", value: String(format: "$%.0f - $%.0f", data.strikeRange[0], data.strikeRange[1]))
                InfoItem(label: "Maturity Range", value: String(format: "%.0f - %.0f days", data.maturityRange[0], data.maturityRange[1]))
                
                Spacer()
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

struct VolatilitySurfaceWebView: NSViewRepresentable {
    let surfaceData: VolatilitySurfaceResponse
    
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
            print("[VolatilitySurfaceWebView] Plotly surface loaded")
        }
    }
    
    private func generatePlotlyHTML() -> String {
        // Convert Swift arrays to JavaScript arrays
        let strikesJS = surfaceData.strikes.map { String($0) }.joined(separator: ",")
        let maturitiesJS = surfaceData.maturities.map { String($0) }.joined(separator: ",")
        let ivDataJS = surfaceData.impliedVols.map { row in
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
                var maturities = [\(maturitiesJS)];
                var z = [
                    \(ivDataJS)
                ];
                
                var data = [{
                    type: 'surface',
                    x: strikes,
                    y: maturities,
                    z: z,
                    colorscale: 'Jet',
                    colorbar: {
                        title: 'Implied Volatility (%)'
                    }
                }];
                
                var layout = {
                    title: 'Implied Volatility Surface - \(surfaceData.symbol)',
                    scene: {
                        xaxis: { title: 'Strike Price' },
                        yaxis: { title: 'Days to Maturity' },
                        zaxis: { title: 'Implied Vol (%)' },
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
}
