import Foundation

enum APIError: LocalizedError {
    case invalidURL
    case invalidResponse
    case httpError(statusCode: Int, message: String?)
    case decodingError(Error)
    case networkError(Error)

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
        }
    }
}

actor APIClient {
    static let shared = APIClient()

    private let baseURL: String
    private let session: URLSession

    private init() {
        self.baseURL = Config.supabaseURL
        self.session = URLSession.shared
    }

    private func makeRequest(endpoint: String, queryItems: [URLQueryItem]? = nil) throws -> URLRequest {
        guard var components = URLComponents(string: "\(baseURL)/\(endpoint)") else {
            throw APIError.invalidURL
        }

        if let queryItems = queryItems, !queryItems.isEmpty {
            components.queryItems = queryItems
        }

        guard let url = components.url else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        return request
    }

    private func performRequest<T: Decodable>(_ request: URLRequest) async throws -> T {
        print("[DEBUG] API Request: \(request.url?.absoluteString ?? "nil")")

        let data: Data
        let response: URLResponse

        do {
            (data, response) = try await session.data(for: request)
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
            throw APIError.httpError(statusCode: httpResponse.statusCode, message: message)
        }

        // Debug: print raw response
        if let jsonString = String(data: data, encoding: .utf8) {
            print("[DEBUG] API Response body: \(jsonString.prefix(500))")
        }

        do {
            let decoder = JSONDecoder()
            return try decoder.decode(T.self, from: data)
        } catch {
            print("[DEBUG] Decoding error: \(error)")
            throw APIError.decodingError(error)
        }
    }

    func searchSymbols(query: String) async throws -> [Symbol] {
        let request = try makeRequest(
            endpoint: "symbols-search",
            queryItems: [URLQueryItem(name: "q", value: query)]
        )
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

    func fetchNews(symbol: String? = nil) async throws -> NewsResponse {
        var queryItems: [URLQueryItem] = []
        if let symbol = symbol {
            queryItems.append(URLQueryItem(name: "symbol", value: symbol))
        }

        let request = try makeRequest(
            endpoint: "news",
            queryItems: queryItems.isEmpty ? nil : queryItems
        )
        return try await performRequest(request)
    }
}
