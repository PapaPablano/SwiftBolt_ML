//
//  BackfillService.swift
//  SwiftBoltML
//
//  Handles user-initiated backfill requests for watchlist symbols
//  Automatically triggered when symbols are added to watchlists
//

import Foundation
import Supabase

@MainActor
class BackfillService: ObservableObject {
    private let supabase: SupabaseClient

    @Published var isLoading = false
    @Published var error: String?

    init(supabase: SupabaseClient) {
        self.supabase = supabase
    }

    // MARK: - User-Facing Functions

    /// Request backfill for a specific symbol (manual UI trigger)
    /// - Parameters:
    ///   - ticker: Stock ticker symbol (e.g., "AAPL")
    ///   - timeframes: Array of timeframes to backfill (default: ["h1"])
    /// - Returns: Result with job details or error
    func requestBackfill(
        for ticker: String,
        timeframes: [String] = ["h1"]
    ) async throws -> BackfillResult {
        isLoading = true
        defer { isLoading = false }

        do {
            let result = try await supabase.rpc(
                "request_symbol_backfill",
                params: [
                    "p_ticker": ticker,
                    "p_timeframes": timeframes
                ]
            ).execute()

            let response = try JSONDecoder().decode(BackfillResult.self, from: result.data)
            return response

        } catch {
            self.error = "Failed to request backfill: \(error.localizedDescription)"
            throw error
        }
    }

    /// Get backfill status for a symbol (for UI progress display)
    /// - Parameter ticker: Stock ticker symbol
    /// - Returns: Array of backfill job statuses (one per timeframe)
    func getBackfillStatus(for ticker: String) async throws -> [BackfillStatus] {
        let result = try await supabase.rpc(
            "get_symbol_backfill_status",
            params: ["p_ticker": ticker]
        ).execute()

        let statuses = try JSONDecoder().decode([BackfillStatus].self, from: result.data)
        return statuses
    }

    /// Check if a symbol has backfill data available
    /// - Parameter ticker: Stock ticker symbol
    /// - Returns: True if backfill is complete or in progress
    func hasBackfillData(for ticker: String) async -> Bool {
        do {
            let statuses = try await getBackfillStatus(for: ticker)
            return !statuses.isEmpty
        } catch {
            return false
        }
    }

    /// Get progress percentage for a symbol's backfill
    /// - Parameter ticker: Stock ticker symbol
    /// - Returns: Progress percentage (0-100), or nil if no backfill
    func getBackfillProgress(for ticker: String) async -> Int? {
        do {
            let statuses = try await getBackfillStatus(for: ticker)
            guard !statuses.isEmpty else { return nil }

            // Return average progress across all timeframes
            let totalProgress = statuses.reduce(0) { $0 + $1.progress }
            return totalProgress / statuses.count
        } catch {
            return nil
        }
    }
}

// MARK: - Data Models

struct BackfillResult: Codable {
    let symbolId: String
    let ticker: String
    let jobs: [BackfillJob]

    enum CodingKeys: String, CodingKey {
        case symbolId = "symbol_id"
        case ticker
        case jobs
    }
}

struct BackfillJob: Codable {
    let ticker: String
    let timeframe: String
    let jobId: String?
    let status: String
    let error: String?

    enum CodingKeys: String, CodingKey {
        case ticker
        case timeframe
        case jobId = "job_id"
        case status
        case error
    }
}

struct BackfillStatus: Codable, Identifiable {
    let timeframe: String
    let status: String
    let progress: Int
    let totalChunks: Int
    let doneChunks: Int
    let pendingChunks: Int
    let errorChunks: Int
    let createdAt: Date
    let updatedAt: Date

    var id: String { timeframe }

    enum CodingKeys: String, CodingKey {
        case timeframe
        case status
        case progress
        case totalChunks = "total_chunks"
        case doneChunks = "done_chunks"
        case pendingChunks = "pending_chunks"
        case errorChunks = "error_chunks"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

// MARK: - Extensions

extension BackfillStatus {
    var progressPercentage: Double {
        Double(progress)
    }

    var isComplete: Bool {
        status == "done"
    }

    var isInProgress: Bool {
        status == "running" || (status == "pending" && doneChunks > 0)
    }

    var hasErrors: Bool {
        errorChunks > 0
    }

    var statusColor: String {
        switch status {
        case "done":
            return "green"
        case "running":
            return "blue"
        case "error":
            return "red"
        default:
            return "gray"
        }
    }
}
