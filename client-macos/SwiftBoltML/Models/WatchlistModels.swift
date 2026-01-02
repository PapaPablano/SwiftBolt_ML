import Foundation

// MARK: - Watchlist Sync Request

struct WatchlistSyncRequest: Codable {
    let action: WatchlistAction
    let symbol: String?
    let watchlistId: String?

    enum WatchlistAction: String, Codable {
        case add
        case remove
        case list
    }
}

// MARK: - Watchlist Sync Response

struct WatchlistSyncResponse: Codable {
    let success: Bool
    let message: String?
    let symbol: String?
    let watchlistId: String?
    let items: [WatchlistItemResponse]?
    let jobStatus: [JobStatus]?
    // OHLC averages returned by "add" action
    let avgDailyVolumeAll: Double?
    let avgDailyVolume10d: Double?
    let avgLastPriceAll: Double?
    let avgLastPrice10d: Double?
}

struct WatchlistItemResponse: Codable {
    let symbol: String
    let addedAt: String
    let jobStatus: WatchlistJobStatus?
    let avgDailyVolumeAll: Double?
    let avgDailyVolume10d: Double?
    let avgLastPriceAll: Double?
    let avgLastPrice10d: Double?

    var addedDate: Date? {
        ISO8601DateFormatter().date(from: addedAt)
    }
}

struct WatchlistJobStatus: Codable {
    let forecast: String?
    let ranking: String?

    var forecastStatus: JobStatusState {
        JobStatusState(rawValue: forecast ?? "unknown") ?? .unknown
    }

    var rankingStatus: JobStatusState {
        JobStatusState(rawValue: ranking ?? "unknown") ?? .unknown
    }
}

// MARK: - Job Status

struct JobStatus: Codable {
    let jobType: String
    let status: String
    let createdAt: String?
    let completedAt: String?
    let errorMessage: String?

    var statusState: JobStatusState {
        JobStatusState(rawValue: status) ?? .unknown
    }

    var isForecast: Bool {
        jobType == "forecast"
    }

    var isRanking: Bool {
        jobType == "ranking"
    }
}

enum JobStatusState: String, Codable {
    case pending
    case running
    case completed
    case failed
    case unknown

    var displayName: String {
        switch self {
        case .pending: return "Pending"
        case .running: return "Running"
        case .completed: return "Completed"
        case .failed: return "Failed"
        case .unknown: return "Unknown"
        }
    }

    var color: String {
        switch self {
        case .pending: return "gray"
        case .running: return "blue"
        case .completed: return "green"
        case .failed: return "red"
        case .unknown: return "gray"
        }
    }
}

// MARK: - Strike Analysis Models

struct StrikeAnalysisRequest: Codable {
    let symbol: String
    let strike: Double
    let side: String
    let lookbackDays: Int?
}

struct StrikeAnalysisResponse: Codable {
    let symbol: String
    let strike: Double
    let side: String
    let lookbackDays: Int
    let expirations: [StrikeExpiryData]
    let priceHistory: [StrikePriceHistoryPoint]
    let overallStats: StrikeOverallStats
    let metadata: StrikeAnalysisMetadata
}

struct StrikeExpiryData: Codable, Identifiable {
    let expiry: String
    let currentMark: Double?
    let avgMark: Double?
    let pctDiffFromAvg: Double?
    let sampleCount: Int
    let minMark: Double?
    let maxMark: Double?
    let currentIv: Double?
    let avgIv: Double?
    let isDiscount: Bool
    let discountPct: Double?

    var id: String { expiry }

    var expiryDate: Date? {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.date(from: expiry)
    }

    var daysToExpiry: Int? {
        guard let date = expiryDate else { return nil }
        return Calendar.current.dateComponents([.day], from: Date(), to: date).day
    }
}

struct StrikePriceHistoryPoint: Codable, Identifiable {
    let snapshotAt: String
    let mark: Double?
    let impliedVol: Double?

    var id: String { snapshotAt }

    var date: Date? {
        // Try standard ISO8601 first
        let isoFormatter = ISO8601DateFormatter()
        isoFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = isoFormatter.date(from: snapshotAt) {
            return date
        }
        // Fallback without fractional seconds
        isoFormatter.formatOptions = [.withInternetDateTime]
        return isoFormatter.date(from: snapshotAt)
    }

    enum CodingKeys: String, CodingKey {
        case snapshotAt = "snapshot_at"
        case mark
        case impliedVol = "implied_vol"
    }
}

struct StrikeOverallStats: Codable {
    let avgMark: Double?
    let minMark: Double?
    let maxMark: Double?
    let sampleCount: Int
}

struct StrikeAnalysisMetadata: Codable {
    let queriedAt: String
    let expirationsFound: Int
    let hasHistoricalData: Bool
}

// MARK: - Strike Analysis Computed Properties

extension StrikeAnalysisResponse {
    var isCall: Bool { side == "call" }
    
    var bestDiscount: StrikeExpiryData? {
        expirations
            .filter { $0.isDiscount && $0.discountPct != nil }
            .max(by: { ($0.discountPct ?? 0) < ($1.discountPct ?? 0) })
    }
    
    var discountExpirations: [StrikeExpiryData] {
        expirations.filter { $0.isDiscount }
    }
    
    var currentVsAvgPct: Double? {
        guard let current = expirations.first?.currentMark,
              let avg = overallStats.avgMark,
              avg > 0 else { return nil }
        return ((current - avg) / avg) * 100
    }
}

extension StrikeExpiryData {
    var formattedExpiry: String {
        guard let date = expiryDate else { return expiry }
        let formatter = DateFormatter()
        formatter.dateFormat = "MMM d"
        return formatter.string(from: date)
    }
}
