import Foundation

enum APIError: LocalizedError {
    case invalidURL
    case invalidResponse
    case httpError(statusCode: Int, message: String?)
    case decodingError(Error)
    case networkError(Error)
    case rateLimitExceeded(retryAfter: Int?)
    case authenticationError(message: String)
    case invalidSymbol(symbol: String)
    case serviceUnavailable(message: String)

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid URL"
        case .invalidResponse:
            return "Invalid response from server"
        case .httpError(let statusCode, let message):
            return "HTTP error \(statusCode): \(message ?? "Unknown error")"
        case .decodingError(let error):
            return "Failed to decode response: \(error.localizedDescription)"
        case .networkError(let error):
            return "Network error: \(error.localizedDescription)"
        case .rateLimitExceeded(let retryAfter):
            if let seconds = retryAfter {
                return "Rate limit exceeded. Retry after \(seconds) seconds"
            }
            return "Rate limit exceeded. Please try again later"
        case .authenticationError(let message):
            return "Authentication error: \(message)"
        case .invalidSymbol(let symbol):
            return "Invalid or unknown symbol: \(symbol)"
        case .serviceUnavailable(let message):
            return "Service temporarily unavailable: \(message)"
        }
    }

    var isRetryable: Bool {
        switch self {
        case .rateLimitExceeded, .serviceUnavailable, .networkError:
            return true
        case .authenticationError, .invalidSymbol, .invalidURL, .invalidResponse, .httpError, .decodingError:
            return false
        }
    }

    /// True when the error is serviceUnavailable with "Supabase host unreachable" (offline mode).
    static func isSupabaseUnreachable(_ error: Error) -> Bool {
        guard case .serviceUnavailable(let message) = error as? APIError else { return false }
        return message.contains("Supabase host unreachable")
    }
}

/// Shared backoff for FastAPI (localhost:8000) to avoid repeated timeout/connection-lost
/// console spam when the backend is not running. Skip requests for a short period after failure.
enum FastAPIBackoff {
    private static let lock = NSLock()
    private static var lastFailure: Date?
    private static let backoffDuration: TimeInterval = 45

    static func shouldSkip(url: URL?) -> Bool {
        guard let url else { return false }
        let base = Config.fastAPIURL
        let sameHost = url.host == base.host && (url.port ?? 80) == (base.port ?? 80)
        guard sameHost else { return false }
        lock.lock()
        defer { lock.unlock() }
        guard let last = lastFailure else { return false }
        return Date().timeIntervalSince(last) < backoffDuration
    }

    static func recordFailure(url: URL?) {
        guard let url else { return }
        let base = Config.fastAPIURL
        let sameHost = url.host == base.host && (url.port ?? 80) == (base.port ?? 80)
        guard sameHost else { return }
        lock.lock()
        lastFailure = Date()
        lock.unlock()
    }

    static func clearSuccess(url: URL?) {
        guard let url else { return }
        let base = Config.fastAPIURL
        let sameHost = url.host == base.host && (url.port ?? 80) == (base.port ?? 80)
        guard sameHost else { return }
        lock.lock()
        lastFailure = nil
        lock.unlock()
    }
}

final class APIClient {
    static let shared = APIClient()

    private let baseURL: URL
    private let functionsBase: URL
    private let session: URLSession
    
    // Request deduplication: track in-flight requests by URL
    // Use actor for thread-safe access in async contexts (Swift 6 compatible)
    private actor RequestDeduplicator {
        private var inFlightRequests: [String: Task<Data, Error>] = [:]
        
        func getExistingTask(for key: String) -> Task<Data, Error>? {
            return inFlightRequests[key]
        }
        
        func storeTask(_ task: Task<Data, Error>, for key: String) {
            inFlightRequests[key] = task
        }
        
        func removeTask(for key: String) {
            inFlightRequests.removeValue(forKey: key)
        }
    }
    
    private let requestDeduplicator = RequestDeduplicator()

    private init() {
        self.baseURL = Config.supabaseURL
        self.functionsBase = Config.functionsBaseURL
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 60
        config.timeoutIntervalForResource = 120
        config.waitsForConnectivity = false
        config.httpMaximumConnectionsPerHost = 6
        self.session = URLSession(configuration: config)
    }
    
    /// Helper to build Edge Function URLs without duplicating paths
    private func functionURL(_ name: String) -> URL {
        Config.functionURL(name)
    }

    private struct OptionsChainPersistResponse: Decodable {
        let underlying: String
    }

    private struct ValidationAuditPayload: Encodable {
        let symbol: String
        let confidence: Double
        let weights: ValidationWeights
        let timestamp: Int
        let clientState: [String: String]?

        enum CodingKeys: String, CodingKey {
            case symbol
            case confidence
            case weights
            case timestamp
            case clientState = "client_state"
        }
    }

    private struct ValidationAuditResponse: Decodable {
        let success: Bool
    }

    private func makeRequest(endpoint: String, queryItems: [URLQueryItem]? = nil, method: String = "GET", body: [String: Any]? = nil) throws -> URLRequest {
        guard var components = URLComponents(string: baseURL.appendingPathComponent(endpoint).absoluteString) else {
            throw APIError.invalidURL
        }

        if let queryItems = queryItems, !queryItems.isEmpty {
            components.queryItems = queryItems
        }

        guard let url = components.url else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        if let body = body {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
        }

        return request
    }

    func performRequest<T: Decodable>(_ request: URLRequest) async throws -> T {
        guard let url = request.url else {
            throw APIError.invalidURL
        }

        // Skip FastAPI requests during backoff to reduce timeout/connection-lost console spam
        if FastAPIBackoff.shouldSkip(url: url) {
            throw APIError.serviceUnavailable(message: "Backend at \(Config.fastAPIURL.absoluteString) is unavailable. Start the FastAPI server to enable options, multi-leg, and real-time features.")
        }

        // Short-circuit Supabase when host can't resolve (DNS -1003); treat as offline
        if url.host == Config.supabaseURL.host && !SupabaseConnectivity.isReachable {
            throw APIError.serviceUnavailable(message: "Supabase host unreachable (DNS). Using offline/cached data.")
        }
        
        let requestKey = url.absoluteString
        
        // Check for duplicate in-flight request
        if let existingTask = await requestDeduplicator.getExistingTask(for: requestKey) {
            print("[DEBUG] 🔄 Deduplicating API request: \(requestKey)")
            // Return existing request result
            let data = try await existingTask.value
            let decoder = JSONDecoder()
            return try decoder.decode(T.self, from: data)
        }
        
        print("[DEBUG] API Request: \(requestKey)")

        // Create new request task
        let task = Task<Data, Error> { [requestDeduplicator] in
            defer {
                // Cleanup in background - don't await in defer
                Task.detached {
                    await requestDeduplicator.removeTask(for: requestKey)
                }
            }
            
            let data: Data
            let response: URLResponse

            do {
                (data, response) = try await session.data(for: request)
            } catch let urlError as URLError where urlError.code == .cancelled {
                print("[DEBUG] Network request cancelled")
                throw CancellationError()
            } catch {
                if let urlError = error as? URLError {
                    switch urlError.code {
                    case .cannotFindHost, .dnsLookupFailed:
                        if request.url?.host == Config.supabaseURL.host {
                            SupabaseConnectivity.recordUnreachable()
                        }
                    case .timedOut, .networkConnectionLost, .cannotConnectToHost, .notConnectedToInternet:
                        FastAPIBackoff.recordFailure(url: request.url)
                    default:
                        break
                    }
                }
                print("[DEBUG] Network error: \(error)")
                throw APIError.networkError(error)
            }
            
            guard let httpResponse = response as? HTTPURLResponse else {
                throw APIError.invalidResponse
            }
            
            print("[DEBUG] API Response status: \(httpResponse.statusCode)")
            if (200...299).contains(httpResponse.statusCode) {
                FastAPIBackoff.clearSuccess(url: request.url)
            }
            guard (200...299).contains(httpResponse.statusCode) else {
                let message = String(data: data, encoding: .utf8)
                print("[DEBUG] API Error response: \(message ?? "nil")")
                
                // Parse specific error types from backend
                switch httpResponse.statusCode {
                case 401, 403:
                    throw APIError.authenticationError(message: message ?? "Authentication failed")
                case 404:
                    // Try to extract symbol from error message
                    if let msg = message, msg.contains("Symbol") {
                        let symbol = msg.components(separatedBy: " ").first(where: { $0.uppercased() == $0 && $0.count <= 5 }) ?? "unknown"
                        throw APIError.invalidSymbol(symbol: symbol)
                    }
                    throw APIError.httpError(statusCode: httpResponse.statusCode, message: message)
                case 429:
                    // Parse Retry-After header if present
                    let retryAfter = httpResponse.value(forHTTPHeaderField: "Retry-After").flatMap(Int.init)
                    throw APIError.rateLimitExceeded(retryAfter: retryAfter)
                case 500...599:
                    throw APIError.serviceUnavailable(message: message ?? "Server error")
                default:
                    throw APIError.httpError(statusCode: httpResponse.statusCode, message: message)
                }
            }
            
            return data
        }
        
        // Store task for deduplication
        await requestDeduplicator.storeTask(task, for: requestKey)
        
        let data = try await task.value
        
        // Debug: print raw response
        if let jsonString = String(data: data, encoding: .utf8) {
            print("[DEBUG] API Response body: \(jsonString.prefix(500))")
            #if DEBUG
            if let urlString = request.url?.absoluteString, urlString.contains("/ml-dashboard") {
                do {
                    if let obj = try JSONSerialization.jsonObject(with: data) as? [String: Any] {
                        let hasValidation = obj["validationMetrics"] != nil
                        print("[DEBUG] ml-dashboard has validationMetrics: \(hasValidation)")
                        if let vm = obj["validationMetrics"] as? [String: Any] {
                            let sharpe = vm["sharpe_ratio"] ?? "nil"
                            let kendall = vm["kendall_tau"] ?? "nil"
                            let ttest = vm["t_test_p_value"] ?? "nil"
                            let mc = vm["monte_carlo_luck"] ?? "nil"
                            print("[DEBUG] validationMetrics(sharpe_ratio=\(sharpe), kendall_tau=\(kendall), monte_carlo_luck=\(mc), t_test_p_value=\(ttest))")
                        }
                    }
                } catch {
                    print("[DEBUG] ml-dashboard JSON parse error: \(error)")
                }
            }
            #endif
        }

        do {
            let decoder = JSONDecoder()
            return try decoder.decode(T.self, from: data)
        } catch {
            print("[DEBUG] Decoding error: \(error)")
            throw APIError.decodingError(error)
        }
    }

    func persistOptionsChainSnapshot(symbol: String) async throws {
        let functionURL = functionURL("options-chain")
        guard var components = URLComponents(
            url: functionURL,
            resolvingAgainstBaseURL: false
        ) else {
            throw APIError.invalidURL
        }

        components.queryItems = [
            URLQueryItem(name: "underlying", value: symbol),
            URLQueryItem(name: "persist", value: "1"),
        ]

        guard let url = components.url else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue(
            "Bearer \(Config.supabaseAnonKey)",
            forHTTPHeaderField: "Authorization"
        )
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let _: OptionsChainPersistResponse = try await performRequest(request)
    }

    /// Enhanced performRequest with response header logging for chart data debugging
    func performRequestWithHeaderLogging<T: Decodable>(_ request: URLRequest, symbol: String, timeframe: String) async throws -> T {
        // Use the same deduplication logic as performRequest
        guard let url = request.url else {
            throw APIError.invalidURL
        }

        if url.host == Config.supabaseURL.host && !SupabaseConnectivity.isReachable {
            throw APIError.serviceUnavailable(message: "Supabase host unreachable (DNS). Using offline/cached data.")
        }
        
        let requestKey = url.absoluteString
        
        // Check for duplicate in-flight request
        if let existingTask = await requestDeduplicator.getExistingTask(for: requestKey) {
            print("[DEBUG] 🔄 Deduplicating API request (with header logging): \(requestKey)")
            // Return existing request result
            let data = try await existingTask.value
            let decoder = JSONDecoder()
            return try decoder.decode(T.self, from: data)
        }
        
        print("[DEBUG] API Request: \(requestKey)")

        // Create new request task
        let task = Task<Data, Error> { [requestDeduplicator] in
            defer {
                // Cleanup in background - don't await in defer
                Task.detached {
                    await requestDeduplicator.removeTask(for: requestKey)
                }
            }
            
            let data: Data
            let response: URLResponse

            do {
                (data, response) = try await session.data(for: request)
            } catch let urlError as URLError where urlError.code == .cancelled {
                print("[DEBUG] Network request cancelled")
                throw CancellationError()
            } catch {
                if let urlError = error as? URLError,
                   (urlError.code == .cannotFindHost || urlError.code == .dnsLookupFailed),
                   request.url?.host == Config.supabaseURL.host {
                    SupabaseConnectivity.recordUnreachable()
                }
                print("[DEBUG] Network error: \(error)")
                throw APIError.networkError(error)
            }

            guard let httpResponse = response as? HTTPURLResponse else {
                throw APIError.invalidResponse
            }

            // Log response headers for cache debugging
            logResponseHeaders(httpResponse, symbol: symbol, timeframe: timeframe)

            print("[DEBUG] API Response status: \(httpResponse.statusCode)")

            guard (200...299).contains(httpResponse.statusCode) else {
                let message = String(data: data, encoding: .utf8)
                print("[DEBUG] API Error response: \(message ?? "nil")")
                
                // Parse specific error types from backend
                switch httpResponse.statusCode {
                case 401, 403:
                    throw APIError.authenticationError(message: message ?? "Authentication failed")
                case 404:
                    // Try to extract symbol from error message
                    if let msg = message, msg.contains("Symbol") {
                        let symbol = msg.components(separatedBy: " ").first(where: { $0.uppercased() == $0 && $0.count <= 5 }) ?? "unknown"
                        throw APIError.invalidSymbol(symbol: symbol)
                    }
                    throw APIError.httpError(statusCode: httpResponse.statusCode, message: message)
                case 429:
                    // Parse Retry-After header if present
                    let retryAfter = httpResponse.value(forHTTPHeaderField: "Retry-After").flatMap(Int.init)
                    throw APIError.rateLimitExceeded(retryAfter: retryAfter)
                case 500...599:
                    throw APIError.serviceUnavailable(message: message ?? "Server error")
                default:
                    throw APIError.httpError(statusCode: httpResponse.statusCode, message: message)
                }
            }
            
            return data
        }
        
        // Store task for deduplication
        await requestDeduplicator.storeTask(task, for: requestKey)
        
        let data = try await task.value

        // Debug: print raw response
        if let jsonString = String(data: data, encoding: .utf8) {
            print("[DEBUG] API Response body: \(jsonString.prefix(500))")
            #if DEBUG
            if let urlString = request.url?.absoluteString, urlString.contains("/ml-dashboard") {
                do {
                    if let obj = try JSONSerialization.jsonObject(with: data) as? [String: Any] {
                        let hasValidation = obj["validationMetrics"] != nil
                        print("[DEBUG] ml-dashboard has validationMetrics: \(hasValidation)")
                        if let vm = obj["validationMetrics"] as? [String: Any] {
                            let sharpe = vm["sharpe_ratio"] ?? "nil"
                            let kendall = vm["kendall_tau"] ?? "nil"
                            let ttest = vm["t_test_p_value"] ?? "nil"
                            let mc = vm["monte_carlo_luck"] ?? "nil"
                            print("[DEBUG] validationMetrics(sharpe_ratio=\(sharpe), kendall_tau=\(kendall), monte_carlo_luck=\(mc), t_test_p_value=\(ttest))")
                        }
                    }
                } catch {
                    print("[DEBUG] ml-dashboard JSON parse error: \(error)")
                }
            }
            #endif
        }

        do {
            let decoder = JSONDecoder()
            return try decoder.decode(T.self, from: data)
        } catch {
            print("[DEBUG] Decoding error: \(error)")
            throw APIError.decodingError(error)
        }
    }

    /// Log response headers for cache debugging
    private func logResponseHeaders(_ response: HTTPURLResponse, symbol: String, timeframe: String) {
        let cacheControl = response.value(forHTTPHeaderField: "Cache-Control") ?? "not-set"
        let etag = response.value(forHTTPHeaderField: "ETag") ?? "none"
        let age = response.value(forHTTPHeaderField: "Age") ?? "0"
        let via = response.value(forHTTPHeaderField: "Via") ?? "direct"
        let cfCacheStatus = response.value(forHTTPHeaderField: "CF-Cache-Status") ?? "none"

        print("[DEBUG] 📊 Response Headers for \(symbol)/\(timeframe)")
        print("[DEBUG] - Status: \(response.statusCode)")
        print("[DEBUG] - Cache-Control: \(cacheControl)")
        print("[DEBUG] - Age: \(age)s")
        print("[DEBUG] - Via: \(via)")
        print("[DEBUG] - ETag: \(etag)")
        print("[DEBUG] - CF-Cache-Status: \(cfCacheStatus)")

        // Warn if stale intraday data (age > 5 minutes)
        let isIntraday = timeframe == "m15" || timeframe == "h1" || timeframe == "h4"
        if isIntraday, let ageValue = Int(age), ageValue > 300 {
            print("[DEBUG] ⚠️ STALE DATA FROM CDN: age=\(ageValue)s (max 300s), via=\(via)")
        }
    }

    // Generic GET method
    func get<R: Decodable>(endpoint: String, queryParams: [String: String] = [:]) async throws -> R {
        guard var components = URLComponents(string: baseURL.appendingPathComponent(endpoint).absoluteString) else {
            throw APIError.invalidURL
        }

        if !queryParams.isEmpty {
            components.queryItems = queryParams.map { URLQueryItem(name: $0.key, value: $0.value) }
        }

        guard let url = components.url else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        return try await performRequest(request)
    }

    /// Fetch real-time quotes for the given symbols (used for live price header)
    func fetchQuotes(symbols: [String]) async throws -> QuotesResponse {
        guard !symbols.isEmpty else {
            throw APIError.invalidURL
        }

        guard var components = URLComponents(url: functionURL("quotes"), resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }
        components.queryItems = [URLQueryItem(name: "symbols", value: symbols.joined(separator: ","))]

        guard let url = components.url else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.cachePolicy = .reloadIgnoringLocalCacheData

        return try await performRequest(request)
    }

    // Generic POST method
    func post<T: Encodable, R: Decodable>(endpoint: String, body: T) async throws -> R {
        guard let components = URLComponents(string: baseURL.appendingPathComponent(endpoint).absoluteString) else {
            throw APIError.invalidURL
        }

        guard let url = components.url else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let encoder = JSONEncoder()
        request.httpBody = try encoder.encode(body)

        return try await performRequest(request)
    }

    func searchSymbols(query: String) async throws -> [Symbol] {
        guard var components = URLComponents(url: functionURL("symbols-search"), resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }
        components.queryItems = [URLQueryItem(name: "q", value: query)]
        
        guard let url = components.url else {
            throw APIError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        return try await performRequest(request)
    }
    
    // MARK: - Futures Chain
    
    /// Fetch futures contract chain for a given root symbol
    /// - Parameter root: The futures root symbol (e.g., "GC", "ES")
    /// - Returns: Array of futures contracts
    func fetchFuturesChain(root: String) async throws -> [FuturesContract] {
        guard var components = URLComponents(url: functionURL("futures-chain"), resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }
        components.queryItems = [URLQueryItem(name: "root", value: root)]
        
        guard let url = components.url else {
            throw APIError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let response: FuturesChainResponse = try await performRequest(request)
        return response.contracts
    }

    func fetchChart(symbol: String, timeframe: String) async throws -> ChartResponse {
        let request = try makeRequest(
            endpoint: "chart",
            queryItems: [
                URLQueryItem(name: "symbol", value: symbol),
                URLQueryItem(name: "timeframe", value: timeframe)
            ]
        )
        return try await performRequest(request)
    }

    func fetchChartRead(symbol: String, timeframe: String = "d1", includeMLData: Bool = true) async throws -> ChartResponse {
        // Redirected from retired chart-read to the unified chart function.
        // Build URL with cache-buster to bypass CDN caching
        var urlComponents = URLComponents(url: functionURL("chart"), resolvingAgainstBaseURL: false)!
        let cacheBuster = Int(Date().timeIntervalSince1970)
        urlComponents.queryItems = [
            URLQueryItem(name: "t", value: "\(cacheBuster)"),
            URLQueryItem(name: "symbol", value: symbol),
            URLQueryItem(name: "timeframe", value: timeframe)
        ]

        let body: [String: Any] = [
            "symbol": symbol,
            "timeframe": timeframe,
            "includeMLData": includeMLData
        ]

        print("[DEBUG] 📊 Fetching chart (was chart-read): symbol=\(symbol), timeframe=\(timeframe), cacheBuster=\(cacheBuster)")

        guard let url = urlComponents.url else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let bodyData = try JSONSerialization.data(withJSONObject: body)
        request.httpBody = bodyData

        // Bypass network cache for all requests to ensure fresh data
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.setValue("no-cache, no-store, must-revalidate", forHTTPHeaderField: "Cache-Control")
        request.setValue(UUID().uuidString, forHTTPHeaderField: "X-Request-ID")

        return try await performRequestWithHeaderLogging(request, symbol: symbol, timeframe: timeframe)
    }

    func fetchChartReadPage(symbol: String, timeframe: String = "d1", before: Int, pageSize: Int = 400) async throws -> ChartResponse {
        // NOTE: fetchChartReadPage still calls chart-read for pagination; update separately when the
        // unified chart function gains cursor-based pagination support.
        var urlComponents = URLComponents(url: functionURL("chart-read"), resolvingAgainstBaseURL: false)!
        let cacheBuster = Int(Date().timeIntervalSince1970)
        urlComponents.queryItems = [
            URLQueryItem(name: "t", value: "\(cacheBuster)"),
            URLQueryItem(name: "symbol", value: symbol),
            URLQueryItem(name: "timeframe", value: timeframe),
            URLQueryItem(name: "before", value: "\(before)"),
            URLQueryItem(name: "pageSize", value: "\(pageSize)")
        ]

        let body: [String: Any] = [
            "symbol": symbol,
            "timeframe": timeframe,
            "includeMLData": false,
            "before": before,
            "pageSize": pageSize
        ]

        print("[DEBUG] 📊 Fetching chart-read page: symbol=\(symbol), timeframe=\(timeframe), before=\(before), pageSize=\(pageSize), cacheBuster=\(cacheBuster)")

        guard let url = urlComponents.url else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let bodyData = try JSONSerialization.data(withJSONObject: body)
        request.httpBody = bodyData

        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.setValue("no-cache, no-store, must-revalidate", forHTTPHeaderField: "Cache-Control")
        request.setValue(UUID().uuidString, forHTTPHeaderField: "X-Request-ID")

        return try await performRequestWithHeaderLogging(request, symbol: symbol, timeframe: timeframe)
    }
    
    func fetchChartV2(symbol: String, timeframe: String = "d1", days: Int = 60, includeForecast: Bool = true, forecastDays: Int = 10, forecastSteps: Int? = nil) async throws -> ChartDataV2Response {
        // Build URL with cache-buster to bypass CDN caching (for all timeframes)
        var urlComponents = URLComponents(url: functionURL("chart"), resolvingAgainstBaseURL: false)!
        let cacheBuster = Int(Date().timeIntervalSince1970)
        urlComponents.queryItems = [
            URLQueryItem(name: "t", value: "\(cacheBuster)"),
            URLQueryItem(name: "symbol", value: symbol),
            URLQueryItem(name: "timeframe", value: timeframe)
        ]

        var body: [String: Any] = [
            "symbol": symbol,
            "timeframe": timeframe,
            "days": days,
            "includeForecast": includeForecast,
            "forecastDays": forecastDays
        ]

        if let forecastSteps {
            body["forecastSteps"] = forecastSteps
        }

        print("[DEBUG] 📊 Fetching chart: symbol=\(symbol), timeframe=\(timeframe), cacheBuster=\(cacheBuster)")

        guard let url = urlComponents.url else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let bodyData = try JSONSerialization.data(withJSONObject: body)
        request.httpBody = bodyData
        print("[DEBUG] 📊 chart request: method=\(request.httpMethod ?? "nil"), bodyBytes=\(bodyData.count)")

        // Bypass network cache for all requests to ensure fresh data
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.setValue("no-cache, no-store, must-revalidate", forHTTPHeaderField: "Cache-Control")
        request.setValue(UUID().uuidString, forHTTPHeaderField: "X-Request-ID")

        return try await performRequestWithHeaderLogging(request, symbol: symbol, timeframe: timeframe)
    }
    
    // MARK: - Unified Chart Endpoint

    /// Fetch chart data from the unified GET /chart endpoint.
    ///
    /// This is the single canonical chart read path (unified chart endpoint).
    ///
    /// - Parameters:
    ///   - symbol: Ticker symbol (e.g. "AAPL", "/ES", "AAPL240119C00150000")
    ///   - timeframe: Bar interval API token (e.g. "d1", "h1", "m15", "w1")
    ///   - days: Number of calendar days of history to return (default 1825)
    ///   - includeForecast: Whether to append ML forecast bars (default true)
    ///   - useLayers: Whether to include optional `layers` field (default false)
    func fetchUnifiedChart(
        symbol: String,
        timeframe: String,
        days: Int = 1825,
        includeForecast: Bool = true,
        useLayers: Bool = false
    ) async throws -> UnifiedChartResponse {
        var components = URLComponents(url: functionURL("chart"), resolvingAgainstBaseURL: false)!
        components.queryItems = [
            URLQueryItem(name: "symbol", value: symbol),
            URLQueryItem(name: "timeframe", value: timeframe),
            URLQueryItem(name: "days", value: String(days)),
            URLQueryItem(name: "include_forecast", value: includeForecast ? "true" : "false"),
        ]
        if useLayers {
            components.queryItems?.append(URLQueryItem(name: "layers", value: "true"))
        }

        guard let url = components.url else { throw APIError.invalidURL }

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.setValue("no-cache, no-store, must-revalidate", forHTTPHeaderField: "Cache-Control")
        request.setValue(UUID().uuidString, forHTTPHeaderField: "X-Request-ID")

        print("[DEBUG] Fetching unified chart: symbol=\(symbol), timeframe=\(timeframe), days=\(days)")
        return try await performRequest(request)
    }

    /// Request binary (up/down) forecast from ML API and write to ml_forecasts for chart overlay.
    /// Call this then reload chart (e.g. loadChart) to show the new forecast.
    func refreshBinaryForecast(symbol: String, horizons: [Int] = [1, 5, 10]) async throws {
        let url = Config.fastAPIURL.appendingPathComponent("api/v1/forecast/binary")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body: [String: Any] = ["symbol": symbol.uppercased(), "horizons": horizons]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (_, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw APIError.invalidResponse
        }
    }

    /// Trigger intraday backfill for a symbol (runs in background, doesn't block)
    func triggerIntradayBackfill(symbol: String, backfillDays: Int = 10) async {
        do {
            let body: [String: Any] = [
                "symbol": symbol,
                "interval": "15min",
                "backfill_days": backfillDays
            ]

            var request = URLRequest(url: functionURL("intraday-update"))
            request.httpMethod = "POST"
            request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
            request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
            
            // Fire and forget - don't wait for response
            Task.detached {
                do {
                    let (_, response) = try await URLSession.shared.data(for: request)
                    if let httpResponse = response as? HTTPURLResponse {
                        print("[DEBUG] Intraday backfill triggered for \(symbol): HTTP \(httpResponse.statusCode)")
                    }
                } catch {
                    print("[DEBUG] Intraday backfill request failed for \(symbol): \(error.localizedDescription)")
                }
            }
        } catch {
            print("[DEBUG] Failed to create intraday backfill request for \(symbol): \(error.localizedDescription)")
        }
    }
    
    /// Trigger yfinance historical backfill for a symbol (runs in background, doesn't block)
    func triggerHistoricalBackfill(symbol: String, timeframes: [String] = ["d1", "h1", "w1"], force: Bool = false) async {
        do {
            let body: [String: Any] = [
                "symbol": symbol,
                "timeframes": timeframes,
                "force": force
            ]

            var request = URLRequest(url: functionURL("symbol-backfill"))
            request.httpMethod = "POST"
            request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
            request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
            
            // Fire and forget - don't wait for response
            Task.detached {
                do {
                    let (_, response) = try await URLSession.shared.data(for: request)
                    if let httpResponse = response as? HTTPURLResponse {
                        print("[DEBUG] Historical backfill triggered for \(symbol): HTTP \(httpResponse.statusCode)")
                    }
                } catch {
                    print("[DEBUG] Historical backfill request failed for \(symbol): \(error.localizedDescription)")
                }
            }
        } catch {
            print("[DEBUG] Failed to create historical backfill request for \(symbol): \(error.localizedDescription)")
        }
    }
    
    /// Trigger both intraday and historical backfill for a symbol
    func triggerCompleteBackfill(symbol: String) async {
        // Trigger both backfills in parallel using TaskGroup
        await withTaskGroup(of: Void.self) { group in
            group.addTask {
                await self.triggerIntradayBackfill(symbol: symbol, backfillDays: 10)
            }
            group.addTask {
                await self.triggerHistoricalBackfill(symbol: symbol)
            }
        }
        print("[DEBUG] Complete backfill triggered for \(symbol) (intraday + historical)")
    }
    
    /// SPEC-8: Ensure coverage for symbol/timeframe (non-blocking backfill orchestration)
    /// DEPRECATED: Spec8 is disabled, use reloadWatchlistData instead
    func ensureCoverage(symbol: String, timeframe: String, windowDays: Int = 7) async throws -> EnsureCoverageResponse {
        let body: [String: Any] = [
            "symbol": symbol,
            "timeframe": timeframe,
            "window_days": windowDays
        ]
        
        var request = URLRequest(url: functionURL("ensure-coverage"))
        request.httpMethod = "POST"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        print("[DEBUG] ensureCoverage: \(symbol)/\(timeframe) windowDays=\(windowDays)")
        return try await performRequest(request)
    }
    
    /// Reload all watchlist data using Alpaca-only strategy (replaces spec8)
    /// Multi-timeframe rule: Always processes all 5 timeframes together
    func reloadWatchlistData(forceRefresh: Bool = false, timeframes: [String] = ["m15", "h1", "h4", "d1", "w1"], symbols: [String]? = nil) async throws -> ReloadWatchlistResponse {
        let body: [String: Any] = [
            "forceRefresh": forceRefresh,
            "timeframes": timeframes,
            "symbols": symbols as Any
        ]
        
        var request = URLRequest(url: functionURL("reload-watchlist-data"))
        request.httpMethod = "POST"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        print("[DEBUG] reloadWatchlistData: forceRefresh=\(forceRefresh), timeframes=\(timeframes), symbols=\(symbols?.joined(separator: ",") ?? "all")")
        return try await performRequest(request)
    }

    func fetchNews(symbol: String? = nil) async throws -> NewsResponse {
        guard var components = URLComponents(url: functionURL("news"), resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }
        
        if let symbol = symbol {
            components.queryItems = [URLQueryItem(name: "symbol", value: symbol)]
        }
        
        guard let url = components.url else {
            throw APIError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        return try await performRequest(request)
    }

    func fetchOptionsChain(underlying: String, expiration: TimeInterval? = nil) async throws -> OptionsChainResponse {
        // Try FastAPI first for fresher options data (Docker/Tradier); fall back to Edge
        let fastAPIChainURL = Config.fastAPIURL.appendingPathComponent("api/v1/options-chain")
        if var components = URLComponents(url: fastAPIChainURL, resolvingAgainstBaseURL: false) {
            var queryItems = [URLQueryItem(name: "underlying", value: underlying)]
            if let expiration = expiration {
                queryItems.append(URLQueryItem(name: "expiration", value: String(Int(expiration))))
            }
            components.queryItems = queryItems
            if let url = components.url {
                var req = URLRequest(url: url)
                req.httpMethod = "GET"
                req.setValue("application/json", forHTTPHeaderField: "Content-Type")
                do {
                    let response: OptionsChainResponse = try await performRequest(req)
                    return response
                } catch {
                    // Fall through to Edge
                }
            }
        }
        guard var components = URLComponents(url: functionURL("options-chain"), resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }
        var queryItems: [URLQueryItem] = [URLQueryItem(name: "underlying", value: underlying)]
        if let expiration = expiration {
            queryItems.append(URLQueryItem(name: "expiration", value: String(Int(expiration))))
        }
        components.queryItems = queryItems
        guard let url = components.url else { throw APIError.invalidURL }
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        return try await performRequest(request)
    }

    func fetchOptionsRankings(symbol: String, expiry: String? = nil, side: OptionSide? = nil, mode: String? = nil, strategyIntent: StrategyIntent? = nil, limit: Int = 50) async throws -> OptionsRankingsResponse {
        var queryItems: [URLQueryItem] = [
            URLQueryItem(name: "symbol", value: symbol),
            URLQueryItem(name: "limit", value: String(limit))
        ]
        if let expiry = expiry { queryItems.append(URLQueryItem(name: "expiry", value: expiry)) }
        if let side = side { queryItems.append(URLQueryItem(name: "side", value: side.rawValue)) }
        if let mode = mode { queryItems.append(URLQueryItem(name: "mode", value: mode)) }
        if let intent = strategyIntent { queryItems.append(URLQueryItem(name: "strategy_intent", value: intent.rawValue)) }

        // Try FastAPI first (options-rankings from Supabase via FastAPI)
        let fastAPIRankingsURL = Config.fastAPIURL.appendingPathComponent("api/v1/options-rankings")
        if var components = URLComponents(url: fastAPIRankingsURL, resolvingAgainstBaseURL: false) {
            components.queryItems = queryItems
            if let url = components.url {
                var req = URLRequest(url: url)
                req.httpMethod = "GET"
                req.setValue("application/json", forHTTPHeaderField: "Content-Type")
                do {
                    let response: OptionsRankingsResponse = try await performRequest(req)
                    return response
                } catch {
                    // Fall through to Edge
                }
            }
        }

        guard var components = URLComponents(url: functionURL("options-rankings"), resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }
        components.queryItems = queryItems
        guard let url = components.url else { throw APIError.invalidURL }
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        return try await performRequest(request)
    }

    func fetchOptionsQuotes(symbol: String, contracts: [String]) async throws -> OptionsQuotesResponse {
        guard !contracts.isEmpty else {
            throw APIError.invalidURL
        }

        struct OptionsQuotesRequest: Encodable {
            let symbol: String
            let contracts: [String]
        }

        let body = OptionsQuotesRequest(symbol: symbol, contracts: contracts)
        let bodyData = try JSONEncoder().encode(body)

        // Try FastAPI first for fresher quotes (Docker/Tradier); fall back to Edge
        let fastAPIQuotesURL = Config.fastAPIURL.appendingPathComponent("api/v1/options-quotes")
        var req = URLRequest(url: fastAPIQuotesURL)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = bodyData
        do {
            let response: OptionsQuotesResponse = try await performRequest(req)
            return response
        } catch {
            // Fall through to Edge
        }

        var request = URLRequest(url: functionURL("options-quotes"))
        request.httpMethod = "POST"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = bodyData
        return try await performRequest(request)
    }

    func scanWatchlist(symbols: [String]) async throws -> ScannerWatchlistResponse {
        var request = URLRequest(url: functionURL("scanner-watchlist"))
        request.httpMethod = "POST"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = ["symbols": symbols]
        request.httpBody = try JSONEncoder().encode(body)

        return try await performRequest(request)
    }

    func triggerRankingJob(for symbol: String) async throws -> TriggerRankingResponse {
        let body = ["symbol": symbol]
        let bodyData = try JSONEncoder().encode(body)
        let fastAPIURL = Config.fastAPIURL.appendingPathComponent("api/v1/trigger-ranking-job")
        var fastAPIRequest = URLRequest(url: fastAPIURL)
        fastAPIRequest.httpMethod = "POST"
        fastAPIRequest.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        fastAPIRequest.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        fastAPIRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        fastAPIRequest.httpBody = bodyData
        do {
            let response: TriggerRankingResponse = try await performRequest(fastAPIRequest)
            return response
        } catch {
            // Fall back to Supabase Edge
        }
        var request = URLRequest(url: functionURL("trigger-ranking-job"))
        request.httpMethod = "POST"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = bodyData
        print("[API] Triggering ranking job for \(symbol)...")
        return try await performRequest(request)
    }
    
    func fetchEnhancedPrediction(symbol: String) async throws -> EnhancedPredictionResponse {
        guard var components = URLComponents(url: functionURL("enhanced-prediction"), resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }
        components.queryItems = [URLQueryItem(name: "symbol", value: symbol)]
        
        guard let url = components.url else {
            throw APIError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        return try await performRequest(request)
    }
    
    /// Refresh data for a symbol - fetches new bars and optionally queues ML/options jobs
    func refreshData(symbol: String, refreshML: Bool = true, refreshOptions: Bool = false) async throws -> RefreshDataResponse {
        var request = URLRequest(url: functionURL("refresh-data"))
        request.httpMethod = "POST"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = RefreshDataRequest(symbol: symbol, refreshML: refreshML, refreshOptions: refreshOptions)
        request.httpBody = try JSONEncoder().encode(body)

        return try await performRequest(request)
    }
    
    /// Comprehensive user-triggered refresh - orchestrates backfill, bars, ML, options, and S/R
    func userRefresh(symbol: String) async throws -> UserRefreshResponse {
        var request = URLRequest(url: functionURL("user-refresh"))
        request.httpMethod = "POST"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = ["symbol": symbol]
        request.httpBody = try JSONEncoder().encode(body)

        return try await performRequest(request)
    }

    /// Fetch consolidated chart data (new unified endpoint with all data in one call)
    /// Includes bars, forecasts, options ranks, and freshness indicators
    func fetchConsolidatedChart(symbol: String, timeframe: String = "d1", start: String? = nil, end: String? = nil, includeOptions: Bool = true, includeForecast: Bool = true, bearerToken: String = Config.supabaseAnonKey) async throws -> ConsolidatedChartResponse {
        guard var components = URLComponents(url: functionURL("chart"), resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }
        
        var queryItems = [
            URLQueryItem(name: "symbol", value: symbol),
            URLQueryItem(name: "timeframe", value: timeframe),
            URLQueryItem(name: "include_options", value: String(includeOptions)),
            URLQueryItem(name: "include_forecast", value: String(includeForecast))
        ]
        
        if let start = start {
            queryItems.append(URLQueryItem(name: "start", value: start))
        }
        if let end = end {
            queryItems.append(URLQueryItem(name: "end", value: end))
        }
        
        components.queryItems = queryItems
        
        guard let url = components.url else {
            throw APIError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(bearerToken)", forHTTPHeaderField: "Authorization")
        request.setValue(bearerToken, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.cachePolicy = .reloadIgnoringLocalCacheData
        
        return try await performRequest(request)
    }
    
    /// Fetch data health status for monitoring
    func fetchDataHealth(symbol: String? = nil, timeframe: String? = nil) async throws -> DataHealthResponse {
        guard var components = URLComponents(url: functionURL("data-health"), resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }
        
        var queryItems: [URLQueryItem] = []
        if let symbol = symbol {
            queryItems.append(URLQueryItem(name: "symbol", value: symbol))
        }
        if let timeframe = timeframe {
            queryItems.append(URLQueryItem(name: "timeframe", value: timeframe))
        }
        
        if !queryItems.isEmpty {
            components.queryItems = queryItems
        }
        
        guard let url = components.url else {
            throw APIError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        return try await performRequest(request)
    }

    /// Fetch ML dashboard data - aggregate metrics across all symbols
    func fetchMLDashboard() async throws -> MLDashboardResponse {
        var request = URLRequest(url: functionURL("ml-dashboard"))
        request.httpMethod = "GET"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        return try await performRequest(request)
    }

    /// Fetch unified validation data
    func fetchUnifiedValidation(symbol: String) async throws -> UnifiedValidator {
        guard var components = URLComponents(
            url: functionURL("get-unified-validation"),
            resolvingAgainstBaseURL: false
        ) else {
            throw APIError.invalidURL
        }

        components.queryItems = [URLQueryItem(name: "symbol", value: symbol.uppercased())]

        guard let url = components.url else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.cachePolicy = .reloadIgnoringLocalCacheData

        return try await performRequest(request)
    }

    /// Log validation audit
    func logValidationAudit(
        symbol: String,
        validator: UnifiedValidator,
        weights: ValidationWeights,
        clientState: [String: String]? = nil
    ) async {
        let payload = ValidationAuditPayload(
            symbol: symbol.uppercased(),
            confidence: validator.confidence,
            weights: weights,
            timestamp: Int(Date().timeIntervalSince1970),
            clientState: clientState
        )

        var request = URLRequest(url: functionURL("log-validation-audit"))
        request.httpMethod = "POST"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        do {
            let encoder = JSONEncoder()
            request.httpBody = try encoder.encode(payload)
            let _: ValidationAuditResponse = try await performRequest(request)
        } catch {
            #if DEBUG
            print("[ValidationAudit] Failed to log audit: \(error)")
            #endif
        }
    }

    /// Fetch Support & Resistance levels for a symbol (default 252 bars = 1 year of trading days)
    /// Tries FastAPI first for fresher data, falls back to Supabase if unavailable
    func fetchSupportResistance(symbol: String, lookback: Int = 252) async throws -> SupportResistanceResponse {
        // Try FastAPI first (primary source for fresher data)
        do {
            return try await fetchSupportResistanceFromFastAPI(symbol: symbol, lookback: lookback)
        } catch {
            #if DEBUG
            print("[APIClient] FastAPI S/R fetch failed, falling back to Supabase: \(error)")
            #endif
            // Fall back to Supabase
            return try await fetchSupportResistanceFromSupabase(symbol: symbol, lookback: lookback)
        }
    }

    /// Fetch Support & Resistance from FastAPI backend (primary source)
    private func fetchSupportResistanceFromFastAPI(symbol: String, lookback: Int = 252) async throws -> SupportResistanceResponse {
        var components = URLComponents(url: Config.fastAPIURL.appendingPathComponent("api/v1/support-resistance"), resolvingAgainstBaseURL: false)
        components?.queryItems = [
            URLQueryItem(name: "symbol", value: symbol),
            URLQueryItem(name: "timeframe", value: "d1"),
            URLQueryItem(name: "lookback", value: String(lookback))
        ]

        guard let url = components?.url else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 60

        return try await performRequest(request)
    }

    /// Fetch Support & Resistance from Supabase Edge Function (fallback)
    private func fetchSupportResistanceFromSupabase(symbol: String, lookback: Int = 252) async throws -> SupportResistanceResponse {
        guard var components = URLComponents(url: functionURL("support-resistance"), resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }

        components.queryItems = [
            URLQueryItem(name: "symbol", value: symbol),
            URLQueryItem(name: "lookback", value: String(lookback))
        ]

        guard let url = components.url else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        return try await performRequest(request)
    }
    
    /// Fetch strike analysis - historical price comparison for an options strike
    func fetchStrikeAnalysis(symbol: String, strike: Double, side: String, lookbackDays: Int = 30) async throws -> StrikeAnalysisResponse {
        guard var components = URLComponents(url: functionURL("strike-analysis"), resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }
        
        components.queryItems = [
            URLQueryItem(name: "symbol", value: symbol),
            URLQueryItem(name: "strike", value: String(strike)),
            URLQueryItem(name: "side", value: side),
            URLQueryItem(name: "lookbackDays", value: String(lookbackDays))
        ]
        
        guard let url = components.url else {
            throw APIError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        return try await performRequest(request)
    }

    // MARK: - ML Accuracy & Feedback Loop

    /// Fetch horizon accuracy data (1D vs 1W breakdown)
    func fetchHorizonAccuracy() async throws -> HorizonAccuracyResponse {
        guard var components = URLComponents(url: functionURL("ml-dashboard"), resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }
        components.queryItems = [URLQueryItem(name: "action", value: "horizon_accuracy")]
        
        guard let url = components.url else {
            throw APIError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        return try await performRequest(request)
    }

    /// Fetch current model weights (RF vs GB)
    func fetchModelWeights() async throws -> [ModelWeightInfo] {
        guard var components = URLComponents(url: functionURL("ml-dashboard"), resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }
        components.queryItems = [URLQueryItem(name: "action", value: "weights")]
        
        guard let url = components.url else {
            throw APIError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        return try await performRequest(request)
    }

    /// Fetch recent forecast evaluations
    func fetchEvaluations(horizon: String? = nil, symbol: String? = nil, limit: Int = 50) async throws -> [ForecastEvaluation] {
        guard var components = URLComponents(url: functionURL("ml-dashboard"), resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }
        
        var queryItems = [
            URLQueryItem(name: "action", value: "evaluations"),
            URLQueryItem(name: "limit", value: String(limit))
        ]

        if let horizon = horizon {
            queryItems.append(URLQueryItem(name: "horizon", value: horizon))
        }
        if let symbol = symbol {
            queryItems.append(URLQueryItem(name: "symbol", value: symbol))
        }
        
        components.queryItems = queryItems
        
        guard let url = components.url else {
            throw APIError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        return try await performRequest(request)
    }

    /// Fetch symbol accuracy by horizon
    func fetchSymbolAccuracy(horizon: String? = nil) async throws -> [SymbolAccuracyData] {
        guard var components = URLComponents(url: functionURL("ml-dashboard"), resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }
        
        var queryItems = [URLQueryItem(name: "action", value: "symbol_accuracy")]

        if let horizon = horizon {
            queryItems.append(URLQueryItem(name: "horizon", value: horizon))
        }
        
        components.queryItems = queryItems
        
        guard let url = components.url else {
            throw APIError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        return try await performRequest(request)
    }

    /// Fetch model comparison (RF vs GB performance)
    func fetchModelComparison() async throws -> [ModelComparisonData] {
        guard var components = URLComponents(url: functionURL("ml-dashboard"), resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }
        components.queryItems = [URLQueryItem(name: "action", value: "model_comparison")]
        
        guard let url = components.url else {
            throw APIError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        return try await performRequest(request)
    }

    // MARK: - GA Strategy Parameters

    /// Fetch GA-optimized strategy parameters for a symbol
    func fetchGAStrategy(symbol: String) async throws -> GAStrategyResponse {
        guard var components = URLComponents(url: functionURL("ga-strategy"), resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }
        components.queryItems = [URLQueryItem(name: "symbol", value: symbol)]
        
        guard let url = components.url else {
            throw APIError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        return try await performRequest(request)
    }

    /// Trigger GA optimization run for a symbol
    func triggerGAOptimization(symbol: String, generations: Int = 50, trainingDays: Int = 30) async throws -> TriggerOptimizationResponse {
        var request = URLRequest(url: functionURL("ga-strategy"))
        request.httpMethod = "POST"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = [
            "symbol": symbol,
            "generations": generations,
            "trainingDays": trainingDays
        ] as [String: Any]

        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        return try await performRequest(request)
    }

    // MARK: - Multi-Leg Options Strategy API

    /// List multi-leg strategies with optional filters
    func listMultiLegStrategies(
        status: StrategyStatus? = nil,
        underlyingSymbolId: String? = nil,
        strategyType: StrategyType? = nil,
        limit: Int = 50,
        offset: Int = 0
    ) async throws -> ListStrategiesResponse {
        var queryItems: [URLQueryItem] = [
            URLQueryItem(name: "limit", value: String(limit)),
            URLQueryItem(name: "offset", value: String(offset))
        ]
        if let status = status { queryItems.append(URLQueryItem(name: "status", value: status.rawValue)) }
        if let symbolId = underlyingSymbolId { queryItems.append(URLQueryItem(name: "underlyingSymbolId", value: symbolId)) }
        if let type = strategyType { queryItems.append(URLQueryItem(name: "strategyType", value: type.rawValue)) }

        // Try FastAPI first (proxy to Edge)
        let fastAPIListURL = Config.fastAPIURL.appendingPathComponent("api/v1/multi-leg-list")
        if var components = URLComponents(url: fastAPIListURL, resolvingAgainstBaseURL: false) {
            components.queryItems = queryItems
            if let url = components.url {
                var req = URLRequest(url: url)
                req.httpMethod = "GET"
                req.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
                req.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
                req.setValue("application/json", forHTTPHeaderField: "Content-Type")
                do {
                    let response: ListStrategiesResponse = try await performRequest(req)
                    return response
                } catch { /* fall through */ }
            }
        }

        guard var components = URLComponents(url: functionURL("multi-leg-list"), resolvingAgainstBaseURL: false) else { throw APIError.invalidURL }
        components.queryItems = queryItems
        guard let url = components.url else { throw APIError.invalidURL }
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        return try await performRequest(request)
    }

    /// Get detailed info for a single strategy including legs and alerts
    func getMultiLegStrategyDetail(strategyId: String) async throws -> StrategyDetailResponse {
        let queryItems = [URLQueryItem(name: "strategyId", value: strategyId)]
        let fastAPIDetailURL = Config.fastAPIURL.appendingPathComponent("api/v1/multi-leg-detail")
        if var components = URLComponents(url: fastAPIDetailURL, resolvingAgainstBaseURL: false) {
            components.queryItems = queryItems
            if let url = components.url {
                var req = URLRequest(url: url)
                req.httpMethod = "GET"
                req.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
                req.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
                req.setValue("application/json", forHTTPHeaderField: "Content-Type")
                do {
                    let response: StrategyDetailResponse = try await performRequest(req)
                    return response
                } catch { /* fall through */ }
            }
        }
        guard var components = URLComponents(url: functionURL("multi-leg-detail"), resolvingAgainstBaseURL: false) else { throw APIError.invalidURL }
        components.queryItems = queryItems
        guard let url = components.url else { throw APIError.invalidURL }
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        return try await performRequest(request)
    }

    /// Create a new multi-leg strategy with legs
    func createMultiLegStrategy(_ request: CreateStrategyRequest) async throws -> CreateStrategyResponse {
        let body = try JSONEncoder().encode(request)
        let fastAPICreateURL = Config.fastAPIURL.appendingPathComponent("api/v1/multi-leg-create")
        var req = URLRequest(url: fastAPICreateURL)
        req.httpMethod = "POST"
        req.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        req.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = body
        do {
            let response: CreateStrategyResponse = try await performRequest(req)
            return response
        } catch { /* fall through */ }
        var urlRequest = URLRequest(url: functionURL("multi-leg-create"))
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        urlRequest.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.httpBody = body
        return try await performRequest(urlRequest)
    }

    /// Update strategy metadata
    func updateMultiLegStrategy(strategyId: String, update: UpdateStrategyRequest) async throws -> MultiLegStrategy {
        let queryItems = [URLQueryItem(name: "strategyId", value: strategyId)]
        let body = try JSONEncoder().encode(update)
        let fastAPIUpdateURL = Config.fastAPIURL.appendingPathComponent("api/v1/multi-leg-update")
        if var components = URLComponents(url: fastAPIUpdateURL, resolvingAgainstBaseURL: false) {
            components.queryItems = queryItems
            if let url = components.url {
                var req = URLRequest(url: url)
                req.httpMethod = "PATCH"
                req.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
                req.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
                req.setValue("application/json", forHTTPHeaderField: "Content-Type")
                req.httpBody = body
                do {
                    let response: MultiLegStrategy = try await performRequest(req)
                    return response
                } catch { /* fall through */ }
            }
        }
        guard var components = URLComponents(url: functionURL("multi-leg-update"), resolvingAgainstBaseURL: false) else { throw APIError.invalidURL }
        components.queryItems = queryItems
        guard let url = components.url else { throw APIError.invalidURL }
        var request = URLRequest(url: url)
        request.httpMethod = "PATCH"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = body
        return try await performRequest(request)
    }

    /// Close a single leg of a strategy
    func closeMultiLegLeg(strategyId: String, request: CloseLegRequest) async throws -> CloseLegResponse {
        let queryItems = [URLQueryItem(name: "strategyId", value: strategyId)]
        let body = try JSONEncoder().encode(request)
        let fastAPICloseLegURL = Config.fastAPIURL.appendingPathComponent("api/v1/multi-leg-close-leg")
        if var components = URLComponents(url: fastAPICloseLegURL, resolvingAgainstBaseURL: false) {
            components.queryItems = queryItems
            if let url = components.url {
                var req = URLRequest(url: url)
                req.httpMethod = "POST"
                req.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
                req.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
                req.setValue("application/json", forHTTPHeaderField: "Content-Type")
                req.httpBody = body
                do {
                    let response: CloseLegResponse = try await performRequest(req)
                    return response
                } catch { /* fall through */ }
            }
        }
        guard var components = URLComponents(url: functionURL("multi-leg-close-leg"), resolvingAgainstBaseURL: false) else { throw APIError.invalidURL }
        components.queryItems = queryItems
        guard let url = components.url else { throw APIError.invalidURL }
        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        urlRequest.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.httpBody = body
        return try await performRequest(urlRequest)
    }

    /// Close an entire strategy (all legs at once)
    func closeMultiLegStrategy(_ request: CloseStrategyRequest) async throws -> CloseStrategyResponse {
        let body = try JSONEncoder().encode(request)
        let fastAPICloseURL = Config.fastAPIURL.appendingPathComponent("api/v1/multi-leg-close-strategy")
        var req = URLRequest(url: fastAPICloseURL)
        req.httpMethod = "POST"
        req.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        req.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = body
        do {
            let response: CloseStrategyResponse = try await performRequest(req)
            return response
        } catch { /* fall through */ }
        var urlRequest = URLRequest(url: functionURL("multi-leg-close-strategy"))
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        urlRequest.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.httpBody = body
        return try await performRequest(urlRequest)
    }

    /// Fetch strategy templates
    func fetchStrategyTemplates() async throws -> TemplatesResponse {
        let fastAPITemplatesURL = Config.fastAPIURL.appendingPathComponent("api/v1/multi-leg-templates")
        var req = URLRequest(url: fastAPITemplatesURL)
        req.httpMethod = "GET"
        req.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        req.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        do {
            let response: TemplatesResponse = try await performRequest(req)
            return response
        } catch { /* fall through */ }
        var request = URLRequest(url: functionURL("multi-leg-templates"))
        request.httpMethod = "GET"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        return try await performRequest(request)
    }

    /// Delete a multi-leg strategy permanently
    func deleteMultiLegStrategy(strategyId: String) async throws -> DeleteStrategyResponse {
        let queryItems = [URLQueryItem(name: "strategyId", value: strategyId)]
        let fastAPIDeleteURL = Config.fastAPIURL.appendingPathComponent("api/v1/multi-leg-delete")
        if var components = URLComponents(url: fastAPIDeleteURL, resolvingAgainstBaseURL: false) {
            components.queryItems = queryItems
            if let url = components.url {
                var req = URLRequest(url: url)
                req.httpMethod = "DELETE"
                req.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
                req.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
                req.setValue("application/json", forHTTPHeaderField: "Content-Type")
                do {
                    let response: DeleteStrategyResponse = try await performRequest(req)
                    return response
                } catch { /* fall through */ }
            }
        }
        guard var components = URLComponents(url: functionURL("multi-leg-delete"), resolvingAgainstBaseURL: false) else { throw APIError.invalidURL }
        components.queryItems = queryItems
        guard let url = components.url else { throw APIError.invalidURL }
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        return try await performRequest(request)
    }
    
    // MARK: - Technical Indicators

    /// Fetch technical indicators for a symbol/timeframe
    /// Calls FastAPI backend directly
    /// - May take up to 60 seconds for first calculation
    /// - Uses request deduplication to prevent duplicate calls
    func fetchTechnicalIndicators(symbol: String, timeframe: String = "d1", forceRefresh: Bool = false) async throws -> TechnicalIndicatorsResponse {
        guard let baseUrl = URL(string: "http://localhost:8000") else {
            throw APIError.invalidURL
        }

        let endpoint = baseUrl.appendingPathComponent("api/v1/technical-indicators")
        guard var components = URLComponents(url: endpoint, resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }

        components.queryItems = [
            URLQueryItem(name: "symbol", value: symbol.uppercased()),
            URLQueryItem(name: "timeframe", value: timeframe),
            URLQueryItem(name: "lookback", value: "500")
        ]

        guard let url = components.url else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.timeoutInterval = 90  // Allow time for FastAPI calculation (~60 seconds)

        do {
            return try await performRequest(request)
        } catch let error as NSError where error.code == NSURLErrorTimedOut {
            throw APIError.serviceUnavailable(message: "Technical indicators request timed out after 90 seconds.")
        } catch {
            throw APIError.serviceUnavailable(message: "Technical indicators service unavailable")
        }
    }
    
    // MARK: - Backtesting (unified job-based API)

    /// Queue a backtest job; returns job_id for polling
    func queueBacktestJob(request: BacktestRequest) async throws -> BacktestJobQueuedResponse {
        var urlRequest = URLRequest(url: functionURL("backtest-strategy"))
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        urlRequest.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")

        var jsonDict: [String: Any] = [
            "symbol": request.symbol,
            "strategy": request.strategy,
            "startDate": request.startDate,
            "endDate": request.endDate
        ]
        if let timeframe = request.timeframe {
            jsonDict["timeframe"] = timeframe
        }
        if let capital = request.initialCapital {
            jsonDict["initialCapital"] = capital
        }
        if let params = request.params {
            jsonDict["params"] = params
        }
        if let config = request.strategyConfig {
            jsonDict["strategy_config"] = config
        }
        urlRequest.httpBody = try JSONSerialization.data(withJSONObject: jsonDict)

        return try await performRequest(urlRequest)
    }

    /// Get backtest job status and result (when completed)
    func getBacktestJobStatus(jobId: String) async throws -> BacktestJobStatusResponse {
        guard var components = URLComponents(url: functionURL("backtest-strategy"), resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }
        components.queryItems = [URLQueryItem(name: "id", value: jobId)]

        var urlRequest = URLRequest(url: components.url!)
        urlRequest.httpMethod = "GET"
        urlRequest.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        urlRequest.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")

        return try await performRequest(urlRequest)
    }

    /// Cancel a running backtest job (PATCH). Returns true if the server accepted the cancellation.
    @discardableResult
    func cancelBacktestJob(jobId: String) async -> Bool {
        do {
            var urlRequest = URLRequest(url: functionURL("backtest-strategy"))
            urlRequest.httpMethod = "PATCH"
            urlRequest.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
            urlRequest.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
            urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
            urlRequest.httpBody = try JSONSerialization.data(withJSONObject: ["job_id": jobId, "status": "cancelled"])
            let (_, response) = try await URLSession.shared.data(for: urlRequest)
            if let http = response as? HTTPURLResponse {
                return (200...204).contains(http.statusCode)
            }
            return false
        } catch {
            return false
        }
    }

    // MARK: - Strategy Persistence (PostgREST REST API)

    private var strategyTableURL: URL {
        Config.supabaseURL.appendingPathComponent("rest/v1/strategy_user_strategies")
    }

    private func strategyHeaders(prefer: String = "return=representation") -> [String: String] {
        [
            "apikey": Config.supabaseAnonKey,
            "Authorization": "Bearer \(Config.supabaseAnonKey)",
            "Content-Type": "application/json",
            "Prefer": prefer,
        ]
    }

    private struct StrategyRowCondition: Decodable {
        let id: String?
        let indicator: String
        let operatorType: String
        let value: Double
        let parameters: [String: String]?
        enum CodingKeys: String, CodingKey {
            case id, indicator, value, parameters
            case operatorType = "operator"
        }
    }

    private struct StrategyRowConditionGroup: Decodable {
        let conditions: [StrategyRowCondition]
    }

    private struct StrategyRowConfig: Decodable {
        // Groups (preferred — OR logic)
        let entryConditionGroups: [StrategyRowConditionGroup]?
        let exitConditionGroups: [StrategyRowConditionGroup]?
        // Flat conditions (backward compat — wrapped into single group)
        let entryConditions: [StrategyRowCondition]?
        let exitConditions: [StrategyRowCondition]?
        let positionSize: Double?
        let stopLoss: Double?
        let takeProfit: Double?
        let direction: String?
        let positionSizing: String?
        enum CodingKeys: String, CodingKey {
            case entryConditionGroups = "entry_condition_groups"
            case exitConditionGroups = "exit_condition_groups"
            case entryConditions = "entry_conditions"
            case exitConditions = "exit_conditions"
            case positionSize = "position_size"
            case stopLoss = "stop_loss"
            case takeProfit = "take_profit"
            case direction
            case positionSizing = "position_sizing"
        }
    }

    private struct StrategyRow: Decodable {
        let id: String
        let userId: String?
        let name: String
        let description: String?
        let config: StrategyRowConfig?
        let isActive: Bool?
        let createdAt: String?
        let updatedAt: String?
        enum CodingKeys: String, CodingKey {
            case id, name, description, config
            case userId = "user_id"
            case isActive = "is_active"
            case createdAt = "created_at"
            case updatedAt = "updated_at"
        }
        func toStrategy() -> Strategy {
            let cfg = config
            func makeCondition(_ c: StrategyRowCondition) -> StrategyCondition {
                StrategyCondition(
                    id: UUID(uuidString: c.id ?? "") ?? UUID(),
                    indicator: c.indicator,
                    operator: c.operatorType,
                    value: c.value,
                    parameters: c.parameters
                )
            }
            func makeGroups(groups: [StrategyRowConditionGroup]?, flat: [StrategyRowCondition]?) -> [ConditionGroup] {
                if let groups = groups, !groups.isEmpty {
                    return groups.map { g in
                        ConditionGroup(conditions: g.conditions.map(makeCondition))
                    }
                }
                // Backward compat: wrap flat conditions in single group
                let conditions = (flat ?? []).map(makeCondition)
                return conditions.isEmpty ? [] : [ConditionGroup(conditions: conditions)]
            }
            return Strategy(
                id: id,
                userId: userId,
                name: name,
                description: description,
                entryGroups: makeGroups(groups: cfg?.entryConditionGroups, flat: cfg?.entryConditions),
                exitGroups: makeGroups(groups: cfg?.exitConditionGroups, flat: cfg?.exitConditions),
                positionSize: cfg?.positionSize ?? 10.0,
                stopLoss: cfg?.stopLoss ?? 2.0,
                takeProfit: cfg?.takeProfit ?? 4.0,
                direction: cfg?.direction ?? "long_only",
                positionSizing: cfg?.positionSizing ?? "percent_of_equity",
                isActive: isActive ?? true
            )
        }
    }

    private func conditionDict(_ c: StrategyCondition) -> [String: Any] {
        var d: [String: Any] = [
            "id": c.id.uuidString,
            "indicator": c.indicator,
            "operator": c.`operator`,
            "value": c.value,
        ]
        if let params = c.parameters { d["parameters"] = params }
        return d
    }

    private func conditionGroupDict(_ group: ConditionGroup) -> [String: Any] {
        ["conditions": group.conditions.map(conditionDict)]
    }

    private func strategyBody(_ strategy: Strategy) throws -> Data {
        let configDict: [String: Any] = [
            "entry_condition_groups": strategy.entryGroups.map(conditionGroupDict),
            "exit_condition_groups": strategy.exitGroups.map(conditionGroupDict),
            // Also send flat for backward compat
            "entry_conditions": strategy.entryConditions.map(conditionDict),
            "exit_conditions": strategy.exitConditions.map(conditionDict),
            "position_size": strategy.positionSize,
            "stop_loss": strategy.stopLoss,
            "take_profit": strategy.takeProfit,
            "direction": strategy.direction,
            "position_sizing": strategy.positionSizing,
        ]
        var body: [String: Any] = [
            "id": strategy.id,
            "name": strategy.name,
            "config": configDict,
            "is_active": strategy.isActive,
        ]
        if let desc = strategy.description { body["description"] = desc }
        return try JSONSerialization.data(withJSONObject: body)
    }

    /// Fetch anon strategies (user_id IS NULL) from PostgREST.
    func fetchStrategies() async -> [Strategy] {
        guard var components = URLComponents(url: strategyTableURL, resolvingAgainstBaseURL: false) else {
            return []
        }
        components.queryItems = [URLQueryItem(name: "user_id", value: "is.null")]
        var req = URLRequest(url: components.url!)
        req.httpMethod = "GET"
        for (k, v) in strategyHeaders(prefer: "return=representation") { req.setValue(v, forHTTPHeaderField: k) }
        do {
            let (data, response) = try await URLSession.shared.data(for: req)
            guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
                return []
            }
            let rows = try JSONDecoder().decode([StrategyRow].self, from: data)
            return rows.map { $0.toStrategy() }
        } catch {
            print("[Strategies] Fetch error: \(error)")
            return []
        }
    }

    /// Upsert (create or update) a strategy via PostgREST ON CONFLICT on id.
    @discardableResult
    func upsertStrategy(_ strategy: Strategy) async -> Bool {
        var req = URLRequest(url: strategyTableURL)
        req.httpMethod = "POST"
        for (k, v) in strategyHeaders(prefer: "resolution=merge-duplicates,return=representation") {
            req.setValue(v, forHTTPHeaderField: k)
        }
        do {
            req.httpBody = try strategyBody(strategy)
            let (_, response) = try await URLSession.shared.data(for: req)
            guard let http = response as? HTTPURLResponse else { return false }
            return (200...299).contains(http.statusCode)
        } catch {
            print("[Strategies] Upsert error: \(error)")
            return false
        }
    }

    /// Delete a strategy by id via PostgREST.
    @discardableResult
    func deleteStrategy(id: String) async -> Bool {
        guard var components = URLComponents(url: strategyTableURL, resolvingAgainstBaseURL: false) else {
            return false
        }
        components.queryItems = [URLQueryItem(name: "id", value: "eq.\(id)")]
        var req = URLRequest(url: components.url!)
        req.httpMethod = "DELETE"
        for (k, v) in strategyHeaders(prefer: "return=representation") { req.setValue(v, forHTTPHeaderField: k) }
        do {
            let (_, response) = try await URLSession.shared.data(for: req)
            guard let http = response as? HTTPURLResponse else { return false }
            return (200...299).contains(http.statusCode)
        } catch {
            print("[Strategies] Delete error: \(error)")
            return false
        }
    }

    // MARK: - Walk-Forward Optimization
    
    /// Run walk-forward optimization for ML forecasters
    func runWalkForward(request: WalkForwardRequest) async throws -> WalkForwardResponse {
        var urlRequest = URLRequest(url: functionURL("walk-forward-optimize"))
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        urlRequest.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        // Build JSON request
        var jsonDict: [String: Any] = [
            "symbol": request.symbol,
            "horizon": request.horizon
        ]
        
        if let forecaster = request.forecaster {
            jsonDict["forecaster"] = forecaster
        }
        if let timeframe = request.timeframe {
            jsonDict["timeframe"] = timeframe
        }
        if let windows = request.windows {
            var windowsDict: [String: Any] = [:]
            if let trainWindow = windows.trainWindow {
                windowsDict["trainWindow"] = trainWindow
            }
            if let testWindow = windows.testWindow {
                windowsDict["testWindow"] = testWindow
            }
            if let stepSize = windows.stepSize {
                windowsDict["stepSize"] = stepSize
            }
            if !windowsDict.isEmpty {
                jsonDict["windows"] = windowsDict
            }
        }
        
        urlRequest.httpBody = try JSONSerialization.data(withJSONObject: jsonDict)
        
        return try await performRequest(urlRequest)
    }
    
    // MARK: - Model Training
    
    /// Train ML model for a symbol/timeframe
    func trainModel(request: ModelTrainingRequest) async throws -> ModelTrainingResponse {
        var urlRequest = URLRequest(url: functionURL("train-model"))
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        urlRequest.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        // Build JSON request
        var jsonDict: [String: Any] = [
            "symbol": request.symbol
        ]
        
        if let timeframe = request.timeframe {
            jsonDict["timeframe"] = timeframe
        }
        if let lookbackDays = request.lookbackDays {
            jsonDict["lookbackDays"] = lookbackDays
        }
        
        urlRequest.httpBody = try JSONSerialization.data(withJSONObject: jsonDict)
        
        return try await performRequest(urlRequest)
    }
    
    // MARK: - Forecast Quality
    
    /// Get forecast quality metrics for a symbol
    func fetchForecastQuality(request: ForecastQualityRequest) async throws -> ForecastQualityResponse {
        var urlRequest = URLRequest(url: functionURL("forecast-quality"))
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        urlRequest.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        // Build JSON request
        var jsonDict: [String: Any] = [
            "symbol": request.symbol
        ]
        
        if let horizon = request.horizon {
            jsonDict["horizon"] = horizon
        }
        if let timeframe = request.timeframe {
            jsonDict["timeframe"] = timeframe
        }
        
        urlRequest.httpBody = try JSONSerialization.data(withJSONObject: jsonDict)
        
        return try await performRequest(urlRequest)
    }
    
    // MARK: - Greeks Surface
    
    /// Get 3D Greeks surface data for visualization
    func fetchGreeksSurface(request: GreeksSurfaceRequest) async throws -> GreeksSurfaceResponse {
        var urlRequest = URLRequest(url: functionURL("greeks-surface"))
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        urlRequest.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        // Build JSON request
        var jsonDict: [String: Any] = [
            "symbol": request.symbol,
            "underlyingPrice": request.underlyingPrice,
            "volatility": request.volatility
        ]
        
        if let riskFreeRate = request.riskFreeRate {
            jsonDict["riskFreeRate"] = riskFreeRate
        }
        if let optionType = request.optionType {
            jsonDict["optionType"] = optionType
        }
        if let strikeRange = request.strikeRange {
            jsonDict["strikeRange"] = strikeRange
        }
        if let timeRange = request.timeRange {
            jsonDict["timeRange"] = timeRange
        }
        if let nStrikes = request.nStrikes {
            jsonDict["nStrikes"] = nStrikes
        }
        if let nTimes = request.nTimes {
            jsonDict["nTimes"] = nTimes
        }
        if let greek = request.greek {
            jsonDict["greek"] = greek
        }
        
        urlRequest.httpBody = try JSONSerialization.data(withJSONObject: jsonDict)
        
        return try await performRequest(urlRequest)
    }
    
    // MARK: - Volatility Surface
    
    /// Get 3D volatility surface data for visualization
    func fetchVolatilitySurface(request: VolatilitySurfaceRequest) async throws -> VolatilitySurfaceResponse {
        var urlRequest = URLRequest(url: functionURL("volatility-surface"))
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        urlRequest.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        // Build JSON request
        var jsonDict: [String: Any] = [
            "symbol": request.symbol,
            "slices": request.slices.map { slice in
                var sliceDict: [String: Any] = [
                    "maturityDays": slice.maturityDays,
                    "strikes": slice.strikes,
                    "impliedVols": slice.impliedVols
                ]
                if let forwardPrice = slice.forwardPrice {
                    sliceDict["forwardPrice"] = forwardPrice
                }
                return sliceDict
            }
        ]
        
        if let nStrikes = request.nStrikes {
            jsonDict["nStrikes"] = nStrikes
        }
        if let nMaturities = request.nMaturities {
            jsonDict["nMaturities"] = nMaturities
        }
        
        urlRequest.httpBody = try JSONSerialization.data(withJSONObject: jsonDict)
        
        return try await performRequest(urlRequest)
    }
    
    // MARK: - Portfolio Optimization
    
    /// Optimize portfolio allocation
    func optimizePortfolio(request: PortfolioOptimizeRequest) async throws -> PortfolioOptimizeResponse {
        var urlRequest = URLRequest(url: functionURL("portfolio-optimize"))
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        urlRequest.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        // Build JSON request
        var jsonDict: [String: Any] = [
            "symbols": request.symbols,
            "method": request.method.rawValue
        ]
        
        if let timeframe = request.timeframe {
            jsonDict["timeframe"] = timeframe
        }
        if let lookbackDays = request.lookbackDays {
            jsonDict["lookbackDays"] = lookbackDays
        }
        if let riskFreeRate = request.riskFreeRate {
            jsonDict["riskFreeRate"] = riskFreeRate
        }
        if let targetReturn = request.targetReturn {
            jsonDict["targetReturn"] = targetReturn
        }
        if let minWeight = request.minWeight {
            jsonDict["minWeight"] = minWeight
        }
        if let maxWeight = request.maxWeight {
            jsonDict["maxWeight"] = maxWeight
        }
        
        urlRequest.httpBody = try JSONSerialization.data(withJSONObject: jsonDict)
        
        return try await performRequest(urlRequest)
    }
    
    // MARK: - Stress Testing
    
    /// Run stress test on portfolio
    func runStressTest(request: StressTestRequest) async throws -> StressTestResponse {
        var urlRequest = URLRequest(url: functionURL("stress-test"))
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        urlRequest.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        // Build JSON request
        var jsonDict: [String: Any] = [
            "positions": request.positions,
            "prices": request.prices
        ]
        
        if let scenario = request.scenario {
            jsonDict["scenario"] = scenario.rawValue
        }
        if let customShocks = request.customShocks {
            jsonDict["customShocks"] = customShocks
        }
        if let varLevel = request.varLevel {
            jsonDict["varLevel"] = varLevel
        }
        
        urlRequest.httpBody = try JSONSerialization.data(withJSONObject: jsonDict)
        
        return try await performRequest(urlRequest)
    }
}

// MARK: - Refresh Data Request/Response

struct RefreshDataRequest: Encodable {
    let symbol: String
    let refreshML: Bool
    let refreshOptions: Bool
}

struct RefreshDataResponse: Decodable {
    let symbol: String
    let success: Bool
    let dataRefresh: [TimeframeRefresh]
    let mlJobQueued: Bool
    let optionsJobQueued: Bool
    let errors: [String]
    let message: String
    
    struct TimeframeRefresh: Decodable {
        let timeframe: String
        let existingBars: Int
        let newBars: Int
        let latestTimestamp: String?
    }
}

// MARK: - User Refresh Response (Comprehensive)

struct UserRefreshResponse: Decodable {
    let symbol: String
    let success: Bool
    let steps: [RefreshStep]
    let summary: RefreshSummary
    let queuedJobs: [String]?
    let warnings: [String]?
    let nextExpectedUpdate: String?
    let message: String
    let durationMs: Int
    
    struct RefreshStep: Decodable {
        let step: String
        let status: String
        let message: String?
    }
    
    struct RefreshSummary: Decodable {
        let backfillNeeded: Bool
        let backfillQueued: Bool
        let barsUpdated: Int
        let mlJobQueued: Bool
        let optionsJobQueued: Bool
        let srCalculated: Bool
    }
}

// MARK: - Consolidated Chart Response (New unified endpoint)

struct ConsolidatedChartResponse: Decodable {
    let symbol: String
    let timeframe: String
    let bars: [ChartBar]
    let forecast: ForecastData?
    let optionsRanks: [OptionsRankItem]?
    let meta: ChartMeta
    let freshness: ChartFreshness
    
    struct ChartBar: Decodable {
        let ts: String
        let open: Double
        let high: Double
        let low: Double
        let close: Double
        let volume: Double
        let provider: String
        let dataStatus: String
    }
    
    struct ForecastData: Decodable {
        let label: String
        let confidence: Double
        let horizon: String
        let runAt: String
        let points: [ForecastPointItem]
        
        struct ForecastPointItem: Decodable {
            let ts: String
            let value: Double
            let lower: Double
            let upper: Double
        }
    }
    
    struct OptionsRankItem: Decodable {
        let expiry: String
        let strike: Double
        let side: String
        let mlScore: Double
        let impliedVol: Double
        let delta: Double
        let gamma: Double
        let theta: Double
        let vega: Double
        let openInterest: Double
        let volume: Double
        let runAt: String
    }
    
    struct ChartMeta: Decodable {
        let lastBarTs: String?
        let dataStatus: String
        let isMarketOpen: Bool
        let latestForecastRunAt: String?
        let hasPendingSplits: Bool
        let pendingSplitInfo: String?
        let totalBars: Int
        let requestedRange: RequestedRange
        
        struct RequestedRange: Decodable {
            let start: String
            let end: String
        }
    }
    
    struct ChartFreshness: Decodable {
        let ageMinutes: Int?
        let slaMinutes: Int
        let isWithinSla: Bool
    }
}

// MARK: - Data Health Response

struct DataHealthResponse: Decodable {
    let success: Bool
    let summary: HealthSummary
    let healthStatuses: [HealthStatus]
    
    struct HealthSummary: Decodable {
        let totalChecks: Int
        let healthy: Int
        let warning: Int
        let critical: Int
        let staleData: Int
        let staleForecast: Int
        let staleOptions: Int
        let pendingSplits: Int
        let marketOpen: Bool
        let checkedAt: String
    }
    
    struct HealthStatus: Decodable {
        let symbol: String
        let timeframe: String
        let coverage: CoverageInfo
        let freshness: FreshnessInfo
        let jobs: JobsInfo
        let forecast: ForecastInfo
        let options: OptionsInfo
        let market: MarketInfo
        let overallHealth: String
        let checkedAt: String
        
        struct CoverageInfo: Decodable {
            let hasCoverage: Bool
            let fromTs: String?
            let toTs: String?
            let lastSuccessAt: String?
            let lastRowsWritten: Int?
            let lastProvider: String?
        }
        
        struct FreshnessInfo: Decodable {
            let isStale: Bool
            let ageHours: Double?
            let slaHours: Double
            let lastBarTs: String?
        }
        
        struct JobsInfo: Decodable {
            let latestStatus: String?
            let latestRunAt: String?
            let pendingJobs: Int
            let failedJobsLast24h: Int
        }
        
        struct ForecastInfo: Decodable {
            let latestRunAt: String?
            let isStale: Bool
            let ageHours: Double?
        }
        
        struct OptionsInfo: Decodable {
            let latestSnapshotAt: String?
            let isStale: Bool
            let ageHours: Double?
        }
        
        struct MarketInfo: Decodable {
            let isOpen: Bool
            let hasPendingSplits: Bool
            let pendingSplitCount: Int
        }
    }
}

// MARK: - Enhanced Prediction Response

struct EnhancedPredictionResponse: Decodable {
    let symbol: String
    let timestamp: String?
    let prediction: String
    let confidence: Double
    let priceTarget: Double?
    let multiTimeframe: MultiTimeframeConsensus?
    let explanation: ForecastExplanation?
    let dataQuality: DataQualityReport?
    
    enum CodingKeys: String, CodingKey {
        case symbol
        case timestamp
        case prediction
        case confidence
        case priceTarget = "price_target"
        case multiTimeframe = "multi_timeframe"
        case explanation
        case dataQuality = "data_quality"
    }
}
