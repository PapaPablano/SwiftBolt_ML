import Foundation

struct Symbol: Codable, Identifiable, Hashable {
    let id: UUID
    let ticker: String
    let assetType: String
    let description: String
    let avgDailyVolumeAll: Double?
    let avgDailyVolume10d: Double?
    let avgLastPriceAll: Double?
    let avgLastPrice10d: Double?

    enum CodingKeys: String, CodingKey {
        case id
        case ticker
        case assetType = "asset_type"
        case description
        case avgDailyVolumeAll
        case avgDailyVolume10d
        case avgLastPriceAll
        case avgLastPrice10d
    }

    // Convenience initializer for minimal symbol creation (e.g., from watchlist)
    init(
        ticker: String,
        assetType: String = "stock",
        description: String = "",
        avgDailyVolumeAll: Double? = nil,
        avgDailyVolume10d: Double? = nil,
        avgLastPriceAll: Double? = nil,
        avgLastPrice10d: Double? = nil
    ) {
        self.id = UUID()
        self.ticker = ticker
        self.assetType = assetType
        self.description = description
        self.avgDailyVolumeAll = avgDailyVolumeAll
        self.avgDailyVolume10d = avgDailyVolume10d
        self.avgLastPriceAll = avgLastPriceAll
        self.avgLastPrice10d = avgLastPrice10d
    }

    // Full initializer
    init(
        id: UUID,
        ticker: String,
        assetType: String,
        description: String,
        avgDailyVolumeAll: Double? = nil,
        avgDailyVolume10d: Double? = nil,
        avgLastPriceAll: Double? = nil,
        avgLastPrice10d: Double? = nil
    ) {
        self.id = id
        self.ticker = ticker
        self.assetType = assetType
        self.description = description
        self.avgDailyVolumeAll = avgDailyVolumeAll
        self.avgDailyVolume10d = avgDailyVolume10d
        self.avgLastPriceAll = avgLastPriceAll
        self.avgLastPrice10d = avgLastPrice10d
    }
}
