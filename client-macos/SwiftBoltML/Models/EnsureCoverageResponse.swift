import Foundation

struct EnsureCoverageResponse: Codable {
    let jobDefId: String
    let symbol: String
    let timeframe: String
    let status: String
    let coverageStatus: CoverageStatus
    let backfillProgress: BackfillProgress?

    struct CoverageStatus: Codable {
        let fromTs: String?
        let toTs: String?
        let lastSuccessAt: String?
        let gapsFound: Int

        enum CodingKeys: String, CodingKey {
            case fromTs = "from_ts"
            case toTs = "to_ts"
            case lastSuccessAt = "last_success_at"
            case gapsFound = "gaps_found"
        }
    }

    struct BackfillProgress: Codable {
        let totalSlices: Int
        let completedSlices: Int
        let runningSlices: Int
        let queuedSlices: Int
        let failedSlices: Int
        let progressPercent: Int
        let barsWritten: Int

        enum CodingKeys: String, CodingKey {
            case totalSlices = "total_slices"
            case completedSlices = "completed_slices"
            case runningSlices = "running_slices"
            case queuedSlices = "queued_slices"
            case failedSlices = "failed_slices"
            case progressPercent = "progress_percent"
            case barsWritten = "bars_written"
        }
    }

    enum CodingKeys: String, CodingKey {
        case jobDefId = "job_def_id"
        case symbol
        case timeframe
        case status
        case coverageStatus = "coverage_status"
        case backfillProgress = "backfill_progress"
    }
}
