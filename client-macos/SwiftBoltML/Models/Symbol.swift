import Foundation

struct Symbol: Codable, Identifiable, Hashable {
    let id: UUID
    let ticker: String
    let assetType: String
    let description: String

    enum CodingKeys: String, CodingKey {
        case id
        case ticker
        case assetType = "asset_type"
        case description
    }
}
