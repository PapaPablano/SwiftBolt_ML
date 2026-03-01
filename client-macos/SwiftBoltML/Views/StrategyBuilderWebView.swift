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
struct StrategyBuilderWebView: View {
    let symbol: String?

    @State private var loadState: WebViewLoadState = .loading

    var body: some View {
        FrontendWebEmbedView(
            path: "/strategy-builder",
            messageName: "strategyBuilder",
            navigationTitle: "Condition Builder",
            loadingLabel: "Loading Strategy Builder…",
            symbol: symbol
        )
    }
}

// MARK: - Backtest Results WebView

/// Embeds the React Backtest Results Panel via WKWebView.
struct BacktestResultsWebView: View {
    let symbol: String?

    var body: some View {
        FrontendWebEmbedView(
            path: "/backtesting",
            messageName: "backtestPanel",
            navigationTitle: "Backtesting",
            loadingLabel: "Loading Backtest Panel…",
            symbol: symbol
        )
    }
}

// MARK: - Generic Frontend Embed View

/// Reusable SwiftUI wrapper for embedding any React frontend route in a WKWebView.
struct FrontendWebEmbedView: View {
    let path: String
    let messageName: String
    let navigationTitle: String
    let loadingLabel: String
    let symbol: String?

    @State private var loadState: WebViewLoadState = .loading

    var body: some View {
        ZStack {
            if !loadState.isFailed {
                FrontendWebViewRepresentable(
                    path: path,
                    messageName: messageName,
                    symbol: symbol,
                    loadState: $loadState
                )
            }

            switch loadState {
            case .loading:
                ProgressView(loadingLabel)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(.background)
            case .loaded:
                EmptyView()
            case .failed(let message):
                WebViewFallbackView(title: "\(navigationTitle) Unavailable", message: message) {
                    loadState = .loading
                }
            }
        }
        .navigationTitle(navigationTitle)
    }
}

// MARK: - NSViewRepresentable (single, parameterized)

private struct FrontendWebViewRepresentable: NSViewRepresentable {
    let path: String
    let messageName: String
    let symbol: String?
    @Binding var loadState: WebViewLoadState

    func makeCoordinator() -> Coordinator {
        Coordinator(messageName: messageName, loadState: $loadState)
    }

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        // Use a weak proxy to avoid the retain cycle:
        // WKUserContentController holds script handlers strongly.
        let proxy = WeakScriptHandler(context.coordinator)
        config.userContentController.add(proxy, name: messageName)
        // Prevent the WebView from navigating outside app-bound domains
        config.limitsNavigationsToAppBoundDomains = true

        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = context.coordinator

        if let url = URL(string: frontendURL(path: path)) {
            webView.load(URLRequest(url: url))
        }
        return webView
    }

    func updateNSView(_ webView: WKWebView, context: Context) {
        guard let symbol else { return }
        context.coordinator.currentSymbol = symbol
        injectSymbol(symbol, into: webView)
    }

    static func dismantleNSView(_ nsView: WKWebView, coordinator: Coordinator) {
        nsView.configuration.userContentController.removeAllScriptMessageHandlers()
    }

    // MARK: - Coordinator

    @MainActor
    class Coordinator: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
        private let messageName: String
        @Binding var loadState: WebViewLoadState
        private let logger: Logger
        /// Tracks the most recent symbol so it can be re-injected after page load.
        var currentSymbol: String?

        init(messageName: String, loadState: Binding<WebViewLoadState>) {
            self.messageName = messageName
            self._loadState = loadState
            self.logger = Logger(subsystem: "com.swiftbolt.ml", category: "WebView.\(messageName)")
        }

        // MARK: Navigation delegate

        func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
            loadState = .loading
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            loadState = .loaded
            // Re-inject symbol so React picks it up after the page finishes loading.
            if let symbol = currentSymbol {
                injectSymbol(symbol, into: webView)
            }
        }

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            logger.error("Navigation failed: \(error.localizedDescription)")
            loadState = .failed(error.localizedDescription)
        }

        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            logger.error("Provisional navigation failed: \(error.localizedDescription)")
            loadState = .failed(error.localizedDescription)
        }

        /// Restrict navigation to localhost / 127.0.0.1 only.
        func webView(
            _ webView: WKWebView,
            decidePolicyFor navigationAction: WKNavigationAction,
            decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
        ) {
            guard let host = navigationAction.request.url?.host,
                  allowedHosts.contains(host) else {
                logger.warning("Blocked navigation to: \(navigationAction.request.url?.absoluteString ?? "unknown", privacy: .public)")
                decisionHandler(.cancel)
                return
            }
            decisionHandler(.allow)
        }

        // MARK: Script message handler (React → Native)

        nonisolated func userContentController(
            _ controller: WKUserContentController,
            didReceive message: WKScriptMessage
        ) {
            guard let body = message.body as? [String: Any],
                  let eventType = body["type"] as? String else { return }
            let logger = Logger(subsystem: "com.swiftbolt.ml", category: "WebView.bridge")
            logger.debug("Received JS event: \(eventType, privacy: .public)")

            switch eventType {
            case "conditionUpdated":
                // Strategy conditions changed in React — notify native layer
                NotificationCenter.default.post(name: .strategyConditionsUpdated, object: nil)
            case "backtestRequested":
                if let strategyId = body["strategyId"] as? String {
                    NotificationCenter.default.post(
                        name: .backtestRequested,
                        object: nil,
                        userInfo: ["strategyId": strategyId]
                    )
                }
            default:
                break
            }
        }
    }
}

// MARK: - Weak Script Handler Proxy

/// Prevents WKUserContentController's strong reference from creating a retain cycle.
private final class WeakScriptHandler: NSObject, WKScriptMessageHandler {
    weak var delegate: WKScriptMessageHandler?

    init(_ delegate: WKScriptMessageHandler) {
        self.delegate = delegate
    }

    func userContentController(
        _ userContentController: WKUserContentController,
        didReceive message: WKScriptMessage
    ) {
        delegate?.userContentController(userContentController, didReceive: message)
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

            Button("Retry") { onRetry() }
                .buttonStyle(.borderedProminent)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding()
    }
}

// MARK: - Notification Names

extension Notification.Name {
    static let strategyConditionsUpdated = Notification.Name("strategyConditionsUpdated")
    static let backtestRequested = Notification.Name("backtestRequested")
}

// MARK: - Helpers

/// Allowed hosts for WebView navigation (localhost only in development).
/// Add production hostname here when deploying.
private let allowedHosts: Set<String> = ["localhost", "127.0.0.1"]

/// Injects the selected symbol into the React app via window.postMessage.
/// Uses JSONSerialization to safely encode all characters (backslash, quotes, Unicode).
private func injectSymbol(_ symbol: String, into webView: WKWebView) {
    let payload: [String: Any] = ["type": "symbolChanged", "symbol": symbol]
    guard let data = try? JSONSerialization.data(withJSONObject: payload),
          let json = String(data: data, encoding: .utf8) else { return }
    webView.evaluateJavaScript("window.postMessage(\(json), '*');")
}

/// Returns the validated frontend base URL + path.
/// Reads FRONTEND_URL from env; validates scheme and host; falls back to localhost:5173.
private func frontendURL(path: String) -> String {
    if let env = ProcessInfo.processInfo.environment["FRONTEND_URL"],
       !env.isEmpty,
       let components = URLComponents(string: env),
       let scheme = components.scheme,
       let host = components.host,
       ["http", "https"].contains(scheme),
       allowedHosts.contains(host) {
        let base = env.hasSuffix("/") ? String(env.dropLast()) : env
        return base + path
    }
    return "http://localhost:5173" + path
}
