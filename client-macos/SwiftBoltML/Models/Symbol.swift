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

    // Convenience initializer for minimal symbol creation (e.g., from watchlist)
    init(ticker: String, assetType: String = "stock", description: String = "") {
        self.id = UUID()
        self.ticker = ticker
        self.assetType = assetType
        self.description = description
    }

    // Full initializer
    init(id: UUID, ticker: String, assetType: String, description: String) {
        self.id = id
        self.ticker = ticker
        self.assetType = assetType
        self.description = description
    }
}
