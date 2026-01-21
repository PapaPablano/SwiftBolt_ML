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
}

final class APIClient {
    static let shared = APIClient()

    private let baseURL: URL
    private let functionsBase: URL
    private let session: URLSession

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
        print("[DEBUG] API Request: \(request.url?.absoluteString ?? "nil")")

        let data: Data
        let response: URLResponse

        do {
            (data, response) = try await session.data(for: request)
        } catch let urlError as URLError where urlError.code == .cancelled {
            print("[DEBUG] Network request cancelled")
            throw CancellationError()
        } catch {
            print("[DEBUG] Network error: \(error)")
            throw APIError.networkError(error)
        }

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

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
        print("[DEBUG] API Request: \(request.url?.absoluteString ?? "nil")")

        let data: Data
        let response: URLResponse

        do {
            (data, response) = try await session.data(for: request)
        } catch let urlError as URLError where urlError.code == .cancelled {
            print("[DEBUG] Network request cancelled")
            throw CancellationError()
        } catch {
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
        // Build URL with cache-buster to bypass CDN caching
        var urlComponents = URLComponents(url: functionURL("chart-read"), resolvingAgainstBaseURL: false)!
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

        print("[DEBUG] 📊 Fetching chart-read: symbol=\(symbol), timeframe=\(timeframe), cacheBuster=\(cacheBuster)")

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
        var urlComponents = URLComponents(url: functionURL("chart-data-v2"), resolvingAgainstBaseURL: false)!
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
        print("[DEBUG] 📊 chart-data-v2 request: method=\(request.httpMethod ?? "nil"), bodyBytes=\(bodyData.count)")

        // Bypass network cache for all requests to ensure fresh data
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.setValue("no-cache, no-store, must-revalidate", forHTTPHeaderField: "Cache-Control")
        request.setValue(UUID().uuidString, forHTTPHeaderField: "X-Request-ID")

        return try await performRequestWithHeaderLogging(request, symbol: symbol, timeframe: timeframe)
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
        guard var components = URLComponents(url: functionURL("options-chain"), resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }
        
        var queryItems: [URLQueryItem] = [
            URLQueryItem(name: "underlying", value: underlying)
        ]
        
        if let expiration = expiration {
            queryItems.append(URLQueryItem(name: "expiration", value: String(Int(expiration))))
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

    func fetchOptionsRankings(symbol: String, expiry: String? = nil, side: OptionSide? = nil, mode: String? = nil, limit: Int = 50) async throws -> OptionsRankingsResponse {
        guard var components = URLComponents(url: functionURL("options-rankings"), resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }
        
        var queryItems: [URLQueryItem] = [
            URLQueryItem(name: "symbol", value: symbol),
            URLQueryItem(name: "limit", value: String(limit))
        ]

        if let expiry = expiry {
            queryItems.append(URLQueryItem(name: "expiry", value: expiry))
        }

        if let side = side {
            queryItems.append(URLQueryItem(name: "side", value: side.rawValue))
        }

        if let mode = mode {
            queryItems.append(URLQueryItem(name: "mode", value: mode))
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

    func fetchOptionsQuotes(symbol: String, contracts: [String]) async throws -> OptionsQuotesResponse {
        guard !contracts.isEmpty else {
            throw APIError.invalidURL
        }

        struct OptionsQuotesRequest: Encodable {
            let symbol: String
            let contracts: [String]
        }

        var request = URLRequest(url: functionURL("options-quotes"))
        request.httpMethod = "POST"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body = OptionsQuotesRequest(symbol: symbol, contracts: contracts)
        request.httpBody = try JSONEncoder().encode(body)
        
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
        var request = URLRequest(url: functionURL("trigger-ranking-job"))
        request.httpMethod = "POST"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = ["symbol": symbol]
        request.httpBody = try JSONEncoder().encode(body)

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
    
    /// Fetch Support & Resistance levels for a symbol (default 252 bars = 1 year of trading days)
    func fetchSupportResistance(symbol: String, lookback: Int = 252) async throws -> SupportResistanceResponse {
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
        guard var components = URLComponents(url: functionURL("multi-leg-list"), resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }

        var queryItems: [URLQueryItem] = [
            URLQueryItem(name: "limit", value: String(limit)),
            URLQueryItem(name: "offset", value: String(offset))
        ]

        if let status = status {
            queryItems.append(URLQueryItem(name: "status", value: status.rawValue))
        }
        if let symbolId = underlyingSymbolId {
            queryItems.append(URLQueryItem(name: "underlyingSymbolId", value: symbolId))
        }
        if let type = strategyType {
            queryItems.append(URLQueryItem(name: "strategyType", value: type.rawValue))
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

    /// Get detailed info for a single strategy including legs and alerts
    func getMultiLegStrategyDetail(strategyId: String) async throws -> StrategyDetailResponse {
        guard var components = URLComponents(url: functionURL("multi-leg-detail"), resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }

        components.queryItems = [URLQueryItem(name: "strategyId", value: strategyId)]

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

    /// Create a new multi-leg strategy with legs
    func createMultiLegStrategy(_ request: CreateStrategyRequest) async throws -> CreateStrategyResponse {
        var urlRequest = URLRequest(url: functionURL("multi-leg-create"))
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        urlRequest.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let encoder = JSONEncoder()
        urlRequest.httpBody = try encoder.encode(request)

        return try await performRequest(urlRequest)
    }

    /// Update strategy metadata
    func updateMultiLegStrategy(strategyId: String, update: UpdateStrategyRequest) async throws -> MultiLegStrategy {
        guard var components = URLComponents(url: functionURL("multi-leg-update"), resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }

        components.queryItems = [URLQueryItem(name: "strategyId", value: strategyId)]

        guard let url = components.url else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "PATCH"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let encoder = JSONEncoder()
        request.httpBody = try encoder.encode(update)

        return try await performRequest(request)
    }

    /// Close a single leg of a strategy
    func closeMultiLegLeg(strategyId: String, request: CloseLegRequest) async throws -> CloseLegResponse {
        guard var components = URLComponents(url: functionURL("multi-leg-close-leg"), resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }

        components.queryItems = [URLQueryItem(name: "strategyId", value: strategyId)]

        guard let url = components.url else {
            throw APIError.invalidURL
        }

        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        urlRequest.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let encoder = JSONEncoder()
        urlRequest.httpBody = try encoder.encode(request)

        return try await performRequest(urlRequest)
    }

    /// Close an entire strategy (all legs at once)
    func closeMultiLegStrategy(_ request: CloseStrategyRequest) async throws -> CloseStrategyResponse {
        var urlRequest = URLRequest(url: functionURL("multi-leg-close-strategy"))
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        urlRequest.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let encoder = JSONEncoder()
        urlRequest.httpBody = try encoder.encode(request)

        return try await performRequest(urlRequest)
    }

    /// Fetch strategy templates
    func fetchStrategyTemplates() async throws -> TemplatesResponse {
        var request = URLRequest(url: functionURL("multi-leg-templates"))
        request.httpMethod = "GET"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        return try await performRequest(request)
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
