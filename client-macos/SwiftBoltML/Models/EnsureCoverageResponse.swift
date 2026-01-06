import Foundation

struct EnsureCoverageResponse: Codable {
    let jobDefId: String
    let symbol: String
    let timeframe: String
    let status: String
    let coverageStatus: CoverageStatus
    
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
    
    enum CodingKeys: String, CodingKey {
        case jobDefId = "job_def_id"
        case symbol
        case timeframe
        case status
        case coverageStatus = "coverage_status"
    }
}
