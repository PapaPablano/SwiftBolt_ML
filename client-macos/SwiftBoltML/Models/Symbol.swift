import Foundation

struct ExpiryInfo: Codable, Hashable {
    let month: Int
    let year: Int
    let lastTradeDate: String?
    
    enum CodingKeys: String, CodingKey {
        case month
        case year
        case lastTradeDate = "last_trade_date"
    }
}

struct Symbol: Codable, Identifiable, Hashable {
    let id: UUID
    let ticker: String
    let assetType: String
    let description: String
    let avgDailyVolumeAll: Double?
    let avgDailyVolume10d: Double?
    let avgLastPriceAll: Double?
    let avgLastPrice10d: Double?
    
    // Futures-specific fields
    var requiresExpiryPicker: Bool?
    var rootSymbol: String?
    var isContinuous: Bool?
    var expiryInfo: ExpiryInfo?

    enum CodingKeys: String, CodingKey {
        case id
        case ticker
        case assetType = "asset_type"
        case description
        case avgDailyVolumeAll
        case avgDailyVolume10d
        case avgLastPriceAll
        case avgLastPrice10d
        case requiresExpiryPicker = "requires_expiry_picker"
        case rootSymbol = "root_symbol"
        case isContinuous = "is_continuous"
        case expiryInfo = "expiry_info"
    }
    
    var isFuturesRoot: Bool {
        return requiresExpiryPicker == true
    }
    
    var isFuturesContract: Bool {
        return assetType == "future" && !isFuturesRoot
    }

    // Convenience initializer for minimal symbol creation (e.g., from watchlist)
    init(
        ticker: String,
        assetType: String = "stock",
        description: String = "",
        avgDailyVolumeAll: Double? = nil,
        avgDailyVolume10d: Double? = nil,
        avgLastPriceAll: Double? = nil,
        avgLastPrice10d: Double? = nil,
        requiresExpiryPicker: Bool? = nil,
        rootSymbol: String? = nil,
        isContinuous: Bool? = nil,
        expiryInfo: ExpiryInfo? = nil
    ) {
        self.id = UUID()
        self.ticker = ticker
        self.assetType = assetType
        self.description = description
        self.avgDailyVolumeAll = avgDailyVolumeAll
        self.avgDailyVolume10d = avgDailyVolume10d
        self.avgLastPriceAll = avgLastPriceAll
        self.avgLastPrice10d = avgLastPrice10d
        self.requiresExpiryPicker = requiresExpiryPicker
        self.rootSymbol = rootSymbol
        self.isContinuous = isContinuous
        self.expiryInfo = expiryInfo
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
        avgLastPrice10d: Double? = nil,
        requiresExpiryPicker: Bool? = nil,
        rootSymbol: String? = nil,
        isContinuous: Bool? = nil,
        expiryInfo: ExpiryInfo? = nil
    ) {
        self.id = id
        self.ticker = ticker
        self.assetType = assetType
        self.description = description
        self.avgDailyVolumeAll = avgDailyVolumeAll
        self.avgDailyVolume10d = avgDailyVolume10d
        self.avgLastPriceAll = avgLastPriceAll
        self.avgLastPrice10d = avgLastPrice10d
        self.requiresExpiryPicker = requiresExpiryPicker
        self.rootSymbol = rootSymbol
        self.isContinuous = isContinuous
        self.expiryInfo = expiryInfo
    }
}

// MARK: - Futures Contract Model

/// Represents a futures contract with expiry information
struct FuturesContract: Codable, Identifiable, Hashable {
    let id: String
    let symbol: String
    let contractCode: String
    let expiryMonth: Int
    let expiryYear: Int
    let lastTradeDate: String?
    let isContinuous: Bool
    let continuousAlias: String?
    let isSpot: Bool?  // Is this the front month?
    
    enum CodingKeys: String, CodingKey {
        case id
        case symbol
        case contractCode = "contract_code"
        case expiryMonth = "expiry_month"
        case expiryYear = "expiry_year"
        case lastTradeDate = "last_trade_date"
        case isContinuous = "is_continuous"
        case continuousAlias = "continuous_alias"
        case isSpot = "is_spot"
    }
    
    var displayName: String {
        if let alias = continuousAlias {
            return "\(alias) - \(contractCode)"
        }
        return "\(symbol) - \(monthName) \(expiryYear)"
    }
    
    private var monthName: String {
        let months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        guard expiryMonth >= 1 && expiryMonth <= 12 else { return "Unknown" }
        return months[expiryMonth - 1]
    }
    
    var isFrontMonth: Bool {
        return isSpot == true
    }
}

/// Response structure for futures chain API
struct FuturesChainResponse: Codable {
    let success: Bool
    let contracts: [FuturesContract]
}
