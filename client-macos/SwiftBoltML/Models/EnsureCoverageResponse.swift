import Foundation

struct EnsureCoverageResponse: Codable {
    let hasCoverage: Bool
    let jobId: String?
    let coverageFrom: String?
    let coverageTo: String?
}
