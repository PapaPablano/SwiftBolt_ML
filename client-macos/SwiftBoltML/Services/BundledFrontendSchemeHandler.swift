import WebKit
import os

/// Serves the bundled React frontend (FrontendDist/) via a custom URL scheme.
///
/// URL format: `frontend://localhost/<path>?<query>`
/// Paths without a file extension fall back to `index.html` so the React SPA
/// can handle client-side routing via `window.location.pathname`.
final class BundledFrontendSchemeHandler: NSObject, WKURLSchemeHandler {

    private static let bundleDir: URL? = Bundle.main.url(
        forResource: "FrontendDist", withExtension: nil
    )

    private let logger = Logger(subsystem: "com.swiftbolt.ml", category: "BundledFrontend")

    // MARK: - WKURLSchemeHandler

    func webView(_ webView: WKWebView, start urlSchemeTask: WKURLSchemeTask) {
        guard let bundleDir = Self.bundleDir else {
            fail(urlSchemeTask, message: "FrontendDist not found in app bundle")
            return
        }

        let urlPath = urlSchemeTask.request.url?.path ?? "/"
        // Drop leading "/" then resolve against the bundle directory.
        let relativePath = urlPath.hasPrefix("/") ? String(urlPath.dropFirst()) : urlPath

        let targetURL: URL
        // Paths with no extension (SPA routes) → serve index.html.
        // Paths with an extension → serve the file if it exists, else index.html.
        if relativePath.isEmpty || !relativePath.contains(".") {
            targetURL = bundleDir.appendingPathComponent("index.html")
        } else {
            let candidate = bundleDir.appendingPathComponent(relativePath)
            targetURL = FileManager.default.fileExists(atPath: candidate.path)
                ? candidate
                : bundleDir.appendingPathComponent("index.html")
        }

        guard let data = try? Data(contentsOf: targetURL) else {
            fail(urlSchemeTask, message: "Could not read \(targetURL.lastPathComponent)")
            return
        }

        let mime = Self.mimeType(for: targetURL)
        let response = URLResponse(
            url: urlSchemeTask.request.url!,
            mimeType: mime,
            expectedContentLength: data.count,
            textEncodingName: Self.isTextMIME(mime) ? "utf-8" : nil
        )
        urlSchemeTask.didReceive(response)
        urlSchemeTask.didReceive(data)
        urlSchemeTask.didFinish()
    }

    func webView(_ webView: WKWebView, stop urlSchemeTask: WKURLSchemeTask) {}

    // MARK: - Helpers

    private func fail(_ task: WKURLSchemeTask, message: String) {
        logger.error("BundledFrontend error: \(message, privacy: .public)")
        task.didFailWithError(NSError(
            domain: "BundledFrontendSchemeHandler",
            code: -1,
            userInfo: [NSLocalizedDescriptionKey: message]
        ))
    }

    private static func mimeType(for url: URL) -> String {
        switch url.pathExtension.lowercased() {
        case "html":         return "text/html"
        case "css":          return "text/css"
        case "js", "mjs":    return "application/javascript"
        case "json", "map":  return "application/json"
        case "png":          return "image/png"
        case "jpg", "jpeg":  return "image/jpeg"
        case "svg":          return "image/svg+xml"
        case "ico":          return "image/x-icon"
        case "woff":         return "font/woff"
        case "woff2":        return "font/woff2"
        case "ttf":          return "font/ttf"
        default:             return "application/octet-stream"
        }
    }

    private static func isTextMIME(_ mime: String) -> Bool {
        mime.hasPrefix("text/")
            || mime == "application/javascript"
            || mime == "application/json"
    }
}
