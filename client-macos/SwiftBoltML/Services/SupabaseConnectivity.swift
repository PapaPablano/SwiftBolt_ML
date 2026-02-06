import Foundation

/// One-time DNS/connectivity check for the Supabase host. When host can't be resolved (e.g. -1003),
/// we treat as offline and short-circuit Supabase-backed calls to avoid log spam and cascade failures.
enum SupabaseConnectivity {
    private static let lock = NSLock()
    private static var _cachedReachable: Bool? = nil

    /// Until we've run a check, assume reachable so we don't block. After first check, use cached result.
    static var isReachable: Bool {
        lock.withLock { _cachedReachable ?? true }
    }

    /// Run a single sanity check: one request to the Supabase host. On -1003 (cannot find host), mark unreachable.
    /// Call at app startup so the banner and short-circuit take effect early.
    static func performCheck() async -> Bool {
        let url = Config.supabaseURL
        let host = url.host ?? ""

        let cached = lock.withLock { _cachedReachable }
        if let cached = cached {
            return cached
        }

        var request = URLRequest(url: url)
        request.httpMethod = "HEAD"
        request.timeoutInterval = 5
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")

        let reachable: Bool
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            if let http = response as? HTTPURLResponse, (200...399).contains(http.statusCode) {
                reachable = true
            } else {
                reachable = true
            }
        } catch let urlError as URLError {
            if urlError.code == .cannotFindHost || urlError.code == .dnsLookupFailed {
                reachable = false
                print("[SupabaseConnectivity] Host unreachable (DNS): \(host) — \(urlError.localizedDescription)")
            } else {
                reachable = true
            }
        } catch {
            reachable = true
        }

        lock.withLock { _cachedReachable = reachable }
        return reachable
    }

    /// Mark unreachable (e.g. when a request fails with -1003). Subsequent Supabase requests will short-circuit.
    static func recordUnreachable() {
        lock.withLock { _cachedReachable = false }
    }

    /// Reset cached result (e.g. for manual retry).
    static func resetCache() {
        lock.withLock { _cachedReachable = nil }
    }
}
