import Foundation
import os.log

// MARK: - Supabase Strategy Models

/// Matches the `strategy_user_strategies` DB row shape returned by the `strategies` edge function.
struct SupabaseStrategy: Codable, Identifiable {
    let id: UUID
    let userId: String
    var name: String
    var description: String?
    var config: StrategyConfig
    var isActive: Bool
    let createdAt: String
    var updatedAt: String

    enum CodingKeys: String, CodingKey {
        case id
        case userId = "user_id"
        case name
        case description
        case config
        case isActive = "is_active"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

/// The JSONB `config` column shape expected by the backend.
struct StrategyConfig: Codable {
    var entryConditions: [SupabaseCondition]
    var exitConditions: [SupabaseCondition]
    var filters: [SupabaseCondition]
    var parameters: [String: AnyCodableValue]

    enum CodingKeys: String, CodingKey {
        case entryConditions = "entry_conditions"
        case exitConditions = "exit_conditions"
        case filters
        case parameters
    }
}

/// A single condition in the Supabase schema.
struct SupabaseCondition: Codable {
    var type: String
    var name: String
    var `operator`: String?
    var value: AnyCodableValue?
    var params: [String: AnyCodableValue]?
}

/// Simple wrapper for JSON values that can be String, Double, Int, or Bool.
enum AnyCodableValue: Codable, Hashable {
    case string(String)
    case double(Double)
    case int(Int)
    case bool(Bool)

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let v = try? container.decode(Bool.self) { self = .bool(v); return }
        if let v = try? container.decode(Int.self) { self = .int(v); return }
        if let v = try? container.decode(Double.self) { self = .double(v); return }
        if let v = try? container.decode(String.self) { self = .string(v); return }
        throw DecodingError.typeMismatch(AnyCodableValue.self, .init(codingPath: decoder.codingPath, debugDescription: "Unsupported value type"))
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let v): try container.encode(v)
        case .double(let v): try container.encode(v)
        case .int(let v): try container.encode(v)
        case .bool(let v): try container.encode(v)
        }
    }
}

// MARK: - Condition Mapping

/// Maps Swift-side operator strings to the Supabase operator format.
/// The server-side `strategy-translator.ts` handles further normalization.
func mapOperator(_ op: String) -> String {
    switch op.lowercased() {
    case "above", ">": return ">"
    case "below", "<": return "<"
    case "crosses_above", "cross_up": return "cross_up"
    case "crosses_below", "cross_down": return "cross_down"
    case "equal", "equals", "==", "=": return "=="
    default: return op.lowercased()
    }
}

/// Converts a native `StrategyCondition` to the Supabase `SupabaseCondition` format.
func toSupabaseCondition(_ condition: StrategyCondition) -> SupabaseCondition {
    let indicator = condition.indicator.lowercased().replacingOccurrences(of: " ", with: "_")
    return SupabaseCondition(
        type: indicator,
        name: indicator,
        operator: mapOperator(condition.operator),
        value: .double(condition.value),
        params: condition.parameters?.compactMapValues { .string($0) }
    )
}

/// Converts a Supabase condition back to the native `StrategyCondition`.
func fromSupabaseCondition(_ condition: SupabaseCondition) -> StrategyCondition {
    let value: Double
    switch condition.value {
    case .double(let v): value = v
    case .int(let v): value = Double(v)
    case .string(let v): value = Double(v) ?? 0
    default: value = 0
    }

    let params: [String: String]? = condition.params?.compactMapValues { val in
        switch val {
        case .string(let s): return s
        case .double(let d): return String(d)
        case .int(let i): return String(i)
        case .bool(let b): return String(b)
        }
    }

    return StrategyCondition(
        indicator: condition.name.uppercased(),
        operator: condition.operator ?? ">",
        value: value,
        parameters: params
    )
}

// MARK: - Strategy Service

/// Communicates with the `strategies` Supabase Edge Function for CRUD operations.
/// Auth headers are provided automatically by the Supabase Swift SDK.
final class StrategyService {
    static let shared = StrategyService()
    private static let logger = Logger(subsystem: "com.swiftboltml", category: "StrategyService")

    private init() {}

    // MARK: - List

    func listStrategies() async throws -> [SupabaseStrategy] {
        let url = Config.functionURL("strategies")
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        try await addAuthHeaders(&request)

        let (data, response) = try await URLSession.shared.data(for: request)
        try validateResponse(response)

        struct ListResponse: Decodable {
            let strategies: [SupabaseStrategy]
        }
        // List endpoint returns partial rows (no config), decode what we get
        let decoded = try JSONDecoder().decode(ListResponse.self, from: data)
        return decoded.strategies
    }

    // MARK: - Get Single

    func getStrategy(id: UUID) async throws -> SupabaseStrategy {
        guard var components = URLComponents(url: Config.functionURL("strategies"), resolvingAgainstBaseURL: false) else {
            throw StrategyServiceError.invalidURL
        }
        components.queryItems = [URLQueryItem(name: "id", value: id.uuidString)]

        guard let url = components.url else { throw StrategyServiceError.invalidURL }
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        try await addAuthHeaders(&request)

        let (data, response) = try await URLSession.shared.data(for: request)
        try validateResponse(response)

        struct SingleResponse: Decodable {
            let strategy: SupabaseStrategy
        }
        return try JSONDecoder().decode(SingleResponse.self, from: data).strategy
    }

    // MARK: - Create

    func createStrategy(name: String, config: StrategyConfig) async throws -> SupabaseStrategy {
        let url = Config.functionURL("strategies")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        try await addAuthHeaders(&request)

        let body: [String: Any] = [
            "name": name,
            "config": try JSONSerialization.jsonObject(with: JSONEncoder().encode(config))
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)
        try validateResponse(response)

        struct CreateResponse: Decodable {
            let strategy: SupabaseStrategy
        }
        return try JSONDecoder().decode(CreateResponse.self, from: data).strategy
    }

    // MARK: - Update

    func updateStrategy(id: UUID, name: String?, config: StrategyConfig?) async throws -> SupabaseStrategy {
        guard var components = URLComponents(url: Config.functionURL("strategies"), resolvingAgainstBaseURL: false) else {
            throw StrategyServiceError.invalidURL
        }
        components.queryItems = [URLQueryItem(name: "id", value: id.uuidString)]

        guard let url = components.url else { throw StrategyServiceError.invalidURL }
        var request = URLRequest(url: url)
        request.httpMethod = "PUT"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        try await addAuthHeaders(&request)

        var body: [String: Any] = [:]
        if let name { body["name"] = name }
        if let config { body["config"] = try JSONSerialization.jsonObject(with: JSONEncoder().encode(config)) }
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)
        try validateResponse(response)

        struct UpdateResponse: Decodable {
            let strategy: SupabaseStrategy
        }
        return try JSONDecoder().decode(UpdateResponse.self, from: data).strategy
    }

    // MARK: - Delete

    func deleteStrategy(id: UUID) async throws {
        guard var components = URLComponents(url: Config.functionURL("strategies"), resolvingAgainstBaseURL: false) else {
            throw StrategyServiceError.invalidURL
        }
        components.queryItems = [URLQueryItem(name: "id", value: id.uuidString)]

        guard let url = components.url else { throw StrategyServiceError.invalidURL }
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        try await addAuthHeaders(&request)

        let (_, response) = try await URLSession.shared.data(for: request)
        try validateResponse(response)
    }

    // MARK: - Helpers

    /// Adds JWT auth headers from the current Supabase session.
    private func addAuthHeaders(_ request: inout URLRequest) async throws {
        let session = try await SupabaseService.shared.client.auth.session
        request.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
    }

    private func validateResponse(_ response: URLResponse) throws {
        guard let httpResponse = response as? HTTPURLResponse else {
            throw StrategyServiceError.invalidResponse
        }
        guard (200...299).contains(httpResponse.statusCode) else {
            if httpResponse.statusCode == 401 {
                throw StrategyServiceError.authRequired
            }
            throw StrategyServiceError.httpError(httpResponse.statusCode)
        }
    }
}

// MARK: - Errors

enum StrategyServiceError: LocalizedError {
    case invalidURL
    case invalidResponse
    case authRequired
    case httpError(Int)

    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid URL"
        case .invalidResponse: return "Invalid response from server"
        case .authRequired: return "Authentication required. Please sign in."
        case .httpError(let code): return "Server error (\(code))"
        }
    }
}
