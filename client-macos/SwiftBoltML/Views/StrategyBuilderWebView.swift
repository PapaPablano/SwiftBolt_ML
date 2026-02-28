import SwiftUI
import WebKit
import os

// MARK: - Load State

enum WebViewLoadState: Equatable {
    case loading
    case loaded
    case failed(String)

    var isFailed: Bool {
        if case .failed = self { return true }
        return false
    }
}

// MARK: - Strategy Builder WebView

/// Embeds the React Strategy Condition Builder via WKWebView.
/// Provides a JS bridge so the native app can pass the selected symbol and receive condition updates.
struct StrategyBuilderWebView: View {
    let symbol: String?

    @State private var loadState: WebViewLoadState = .loading

    var body: some View {
        ZStack {
            // Always render the WebView in the background so it loads immediately;
            // overlay with progress/error UI as needed.
            if !loadState.isFailed {
                StrategyBuilderWebViewRepresentable(symbol: symbol, loadState: $loadState)
            }

            switch loadState {
            case .loading:
                ProgressView("Loading Strategy Builder…")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(.background)
            case .loaded:
                EmptyView()
            case .failed(let message):
                WebViewFallbackView(title: "Strategy Builder Unavailable", message: message) {
                    loadState = .loading
                }
            }
        }
        .navigationTitle("Condition Builder")
    }
}

// MARK: - Strategy Builder NSViewRepresentable

private struct StrategyBuilderWebViewRepresentable: NSViewRepresentable {
    let symbol: String?
    @Binding var loadState: WebViewLoadState

    private let logger = Logger(subsystem: "com.swiftbolt.ml", category: "StrategyBuilderWebView")

    func makeCoordinator() -> Coordinator {
        Coordinator(parent: self)
    }

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.userContentController.add(context.coordinator, name: "strategyBuilder")

        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = context.coordinator

        let urlString = frontendURL(path: "/strategy-builder")
        if let url = URL(string: urlString) {
            webView.load(URLRequest(url: url))
        }
        return webView
    }

    func updateNSView(_ webView: WKWebView, context: Context) {
        guard let symbol else { return }
        let escaped = symbol.replacingOccurrences(of: "'", with: "\\'")
        webView.evaluateJavaScript("window.postMessage({ type: 'symbolChanged', symbol: '\(escaped)' }, '*');")
    }

    // MARK: - Coordinator

    @MainActor
    class Coordinator: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
        var parent: StrategyBuilderWebViewRepresentable
        private let logger = Logger(subsystem: "com.swiftbolt.ml", category: "StrategyBuilderWebView")

        init(parent: StrategyBuilderWebViewRepresentable) {
            self.parent = parent
        }

        func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
            parent.loadState = .loading
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            parent.loadState = .loaded
            if let symbol = parent.symbol {
                let escaped = symbol.replacingOccurrences(of: "'", with: "\\'")
                webView.evaluateJavaScript("window.postMessage({ type: 'symbolChanged', symbol: '\(escaped)' }, '*');")
            }
        }

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            logger.error("Navigation failed: \(error.localizedDescription)")
            parent.loadState = .failed(error.localizedDescription)
        }

        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            logger.error("Provisional navigation failed: \(error.localizedDescription)")
            parent.loadState = .failed(error.localizedDescription)
        }

        // React → Native messages
        nonisolated func userContentController(
            _ controller: WKUserContentController,
            didReceive message: WKScriptMessage
        ) {
            guard message.name == "strategyBuilder",
                  let body = message.body as? [String: Any],
                  let eventType = body["type"] as? String else { return }
            let logger = Logger(subsystem: "com.swiftbolt.ml", category: "StrategyBuilderWebView")
            logger.debug("Received JS event: \(eventType, privacy: .public)")
            // Future: handle "conditionUpdated", "strategyActivated", "backtestRequested"
        }
    }
}

// MARK: - Backtest Results WebView

/// Embeds the React Backtest Results Panel via WKWebView.
struct BacktestResultsWebView: View {
    let symbol: String?

    @State private var loadState: WebViewLoadState = .loading

    var body: some View {
        ZStack {
            if !loadState.isFailed {
                BacktestResultsWebViewRepresentable(symbol: symbol, loadState: $loadState)
            }

            switch loadState {
            case .loading:
                ProgressView("Loading Backtest Panel…")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(.background)
            case .loaded:
                EmptyView()
            case .failed(let message):
                WebViewFallbackView(title: "Backtest Panel Unavailable", message: message) {
                    loadState = .loading
                }
            }
        }
        .navigationTitle("Backtesting")
    }
}

// MARK: - Backtest NSViewRepresentable

private struct BacktestResultsWebViewRepresentable: NSViewRepresentable {
    let symbol: String?
    @Binding var loadState: WebViewLoadState

    func makeCoordinator() -> Coordinator {
        Coordinator(parent: self)
    }

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.userContentController.add(context.coordinator, name: "backtestPanel")

        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = context.coordinator

        let urlString = frontendURL(path: "/backtesting")
        if let url = URL(string: urlString) {
            webView.load(URLRequest(url: url))
        }
        return webView
    }

    func updateNSView(_ webView: WKWebView, context: Context) {
        guard let symbol else { return }
        let escaped = symbol.replacingOccurrences(of: "'", with: "\\'")
        webView.evaluateJavaScript("window.postMessage({ type: 'symbolChanged', symbol: '\(escaped)' }, '*');")
    }

    @MainActor
    class Coordinator: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
        var parent: BacktestResultsWebViewRepresentable
        private let logger = Logger(subsystem: "com.swiftbolt.ml", category: "BacktestResultsWebView")

        init(parent: BacktestResultsWebViewRepresentable) {
            self.parent = parent
        }

        func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
            parent.loadState = .loading
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            parent.loadState = .loaded
            if let symbol = parent.symbol {
                let escaped = symbol.replacingOccurrences(of: "'", with: "\\'")
                webView.evaluateJavaScript("window.postMessage({ type: 'symbolChanged', symbol: '\(escaped)' }, '*');")
            }
        }

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            logger.error("Navigation failed: \(error.localizedDescription)")
            parent.loadState = .failed(error.localizedDescription)
        }

        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            logger.error("Provisional navigation failed: \(error.localizedDescription)")
            parent.loadState = .failed(error.localizedDescription)
        }

        nonisolated func userContentController(
            _ controller: WKUserContentController,
            didReceive message: WKScriptMessage
        ) {
            guard message.name == "backtestPanel",
                  let body = message.body as? [String: Any],
                  let eventType = body["type"] as? String else { return }
            let logger = Logger(subsystem: "com.swiftbolt.ml", category: "BacktestResultsWebView")
            logger.debug("Received JS event: \(eventType, privacy: .public)")
        }
    }
}

// MARK: - Fallback View

struct WebViewFallbackView: View {
    let title: String
    let message: String
    let onRetry: () -> Void

    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 48))
                .foregroundStyle(.orange)

            Text(title)
                .font(.title2.bold())

            Text(message)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 400)

            Text("Make sure the frontend dev server is running.\nSet FRONTEND_URL in your environment or run `npm run dev` in the frontend/ directory.")
                .font(.caption)
                .foregroundStyle(.tertiary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 400)

            Button("Retry") {
                onRetry()
            }
            .buttonStyle(.borderedProminent)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding()
    }
}

// MARK: - URL Helper

/// Returns the frontend base URL + path. Reads FRONTEND_URL from env; falls back to localhost:5173.
private func frontendURL(path: String) -> String {
    let base: String
    if let env = ProcessInfo.processInfo.environment["FRONTEND_URL"], !env.isEmpty {
        base = env.hasSuffix("/") ? String(env.dropLast()) : env
    } else {
        base = "http://localhost:5173"
    }
    return base + path
}
