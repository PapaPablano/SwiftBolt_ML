import Foundation
import os.log

// MARK: - Backtest Service

/// Submits strategy backtests to the `backtest-strategy` edge function and polls
/// for results using exponential backoff (1s -> 2s -> 4s -> 8s -> 15s cap).
/// Reuses existing Codable types from `BacktestingModels.swift`.
final class BacktestService {
    static let shared = BacktestService()
    private static let logger = Logger(subsystem: "com.swiftboltml", category: "BacktestService")

    private let maxTimeout: TimeInterval = 120
    private let maxPollInterval: TimeInterval = 15

    private init() {}

    // MARK: - Submit

    /// Submit a strategy backtest job. Returns the job ID for polling.
    func submitBacktest(
        symbol: String,
        strategyConfig: StrategyConfig,
        startDate: String,
        endDate: String,
        initialCapital: Double = 10_000,
        timeframe: String = "d1"
    ) async throws -> String {
        let url = Config.functionURL("backtest-strategy")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")

        // Include JWT if authenticated (backtest-strategy allows anonymous but benefits from user_id)
        if let session = try? await SupabaseService.shared.client.auth.session {
            request.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")
        } else {
            request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        }

        let configData = try JSONEncoder().encode(strategyConfig)
        let configJSON = try JSONSerialization.jsonObject(with: configData)

        let body: [String: Any] = [
            "symbol": symbol.uppercased(),
            "startDate": startDate,
            "endDate": endDate,
            "timeframe": timeframe,
            "initialCapital": initialCapital,
            "strategy_config": configJSON
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)
        try validateResponse(response)

        let queued = try JSONDecoder().decode(BacktestJobQueuedResponse.self, from: data)
        Self.logger.info("Backtest job queued: \(queued.jobId)")
        return queued.jobId
    }

    // MARK: - Poll with Exponential Backoff

    /// Poll for backtest results. Uses exponential backoff: 1s -> 2s -> 4s -> 8s -> 15s cap.
    /// Throws on timeout (120s) or job failure.
    func pollBacktest(jobId: String) async throws -> BacktestResultPayload {
        var interval: TimeInterval = 1
        let start = Date()

        while Date().timeIntervalSince(start) < maxTimeout {
            try Task.checkCancellation()
            try await Task.sleep(for: .seconds(interval))

            let status = try await fetchJobStatus(jobId: jobId)
            let statusEnum = BacktestJobStatus(apiStatus: status.status)

            switch statusEnum {
            case .completed:
                guard let result = status.result else {
                    throw BacktestServiceError.missingResult
                }
                Self.logger.info("Backtest completed: \(result.metrics.totalTrades) trades")
                return result

            case .failed:
                throw BacktestServiceError.jobFailed(status.error ?? "Unknown error")

            default:
                // Exponential backoff: double interval up to max
                interval = min(interval * 2, maxPollInterval)
                #if DEBUG
                Self.logger.debug("Polling backtest \(jobId): \(status.status), next in \(interval)s")
                #endif
            }
        }

        throw BacktestServiceError.timeout
    }

    // MARK: - Private

    private func fetchJobStatus(jobId: String) async throws -> BacktestJobStatusResponse {
        guard var components = URLComponents(url: Config.functionURL("backtest-strategy"), resolvingAgainstBaseURL: false) else {
            throw BacktestServiceError.invalidURL
        }
        components.queryItems = [URLQueryItem(name: "id", value: jobId)]

        guard let url = components.url else {
            throw BacktestServiceError.invalidURL
        }
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")
        if let session = try? await SupabaseService.shared.client.auth.session {
            request.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")
        } else {
            request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        }

        let (data, response) = try await URLSession.shared.data(for: request)
        try validateResponse(response)
        return try JSONDecoder().decode(BacktestJobStatusResponse.self, from: data)
    }

    private func validateResponse(_ response: URLResponse) throws {
        guard let httpResponse = response as? HTTPURLResponse else {
            throw BacktestServiceError.invalidResponse
        }
        guard (200...299).contains(httpResponse.statusCode) else {
            throw BacktestServiceError.httpError(httpResponse.statusCode)
        }
    }
}

// MARK: - Errors

enum BacktestServiceError: LocalizedError {
    case invalidURL
    case invalidResponse
    case httpError(Int)
    case jobFailed(String)
    case missingResult
    case timeout

    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid URL"
        case .invalidResponse: return "Invalid response from server"
        case .httpError(let code): return "Server error (\(code))"
        case .jobFailed(let msg): return "Backtest failed: \(msg)"
        case .missingResult: return "Backtest completed but no results returned"
        case .timeout: return "Backtest timed out after 120 seconds"
        }
    }
}
