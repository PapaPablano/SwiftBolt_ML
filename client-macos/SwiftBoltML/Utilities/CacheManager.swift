import Foundation

// MARK: - Cache Freshness Tiers

/// Cache freshness levels with defined TTL thresholds.
/// Based on the staleness specification from the improvement plan.
enum CacheFreshness: Comparable {
    case fresh      // < 5 min - Use directly, no fetch needed
    case warm       // 5-30 min - Use + background refresh
    case stale      // 30 min - 6 hr - Show warning, prompt refresh
    case critical   // > 6 hr - Force refresh, block until fresh

    init(age: TimeInterval) {
        switch age {
        case ..<300:      self = .fresh     // 5 min
        case ..<1800:     self = .warm      // 30 min
        case ..<21600:    self = .stale     // 6 hr
        default:          self = .critical
        }
    }

    var shouldBackgroundRefresh: Bool {
        self == .warm
    }

    var shouldShowWarning: Bool {
        self == .stale || self == .critical
    }

    var shouldBlockUntilRefresh: Bool {
        self == .critical
    }

    var description: String {
        switch self {
        case .fresh: return "Fresh (< 5 min)"
        case .warm: return "Warm (5-30 min)"
        case .stale: return "Stale (30 min - 6 hr)"
        case .critical: return "Critical (> 6 hr)"
        }
    }

    var icon: String {
        switch self {
        case .fresh: return "✅"
        case .warm: return "🟡"
        case .stale: return "⚠️"
        case .critical: return "🔴"
        }
    }
}

// MARK: - Cache Entry

/// A cached item with timestamp for freshness tracking.
struct CacheEntry<T: Codable>: Codable {
    let data: T
    let timestamp: Date
    let key: String

    var age: TimeInterval {
        Date().timeIntervalSince(timestamp)
    }

    var freshness: CacheFreshness {
        CacheFreshness(age: age)
    }

    var isExpired: Bool {
        freshness == .critical
    }
}

// MARK: - Cache Manager

/// Thread-safe cache manager with TTL-based freshness tracking.
/// Supports both in-memory and persistent (UserDefaults) caching.
actor CacheManager {
    static let shared = CacheManager()

    private var memoryCache: [String: Data] = [:]
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()

    // MARK: - Memory Cache Operations

    /// Get cached value with freshness status.
    func get<T: Codable>(_ key: String, type: T.Type) -> (value: T, freshness: CacheFreshness)? {
        guard let data = memoryCache[key] else { return nil }

        do {
            let entry = try decoder.decode(CacheEntry<T>.self, from: data)
            return (entry.data, entry.freshness)
        } catch {
            print("[CacheManager] Failed to decode cache entry for key '\(key)': \(error)")
            memoryCache.removeValue(forKey: key)
            return nil
        }
    }

    /// Set cached value with current timestamp.
    func set<T: Codable>(_ key: String, value: T) {
        let entry = CacheEntry(data: value, timestamp: Date(), key: key)

        do {
            let data = try encoder.encode(entry)
            memoryCache[key] = data
        } catch {
            print("[CacheManager] Failed to encode cache entry for key '\(key)': \(error)")
        }
    }

    /// Remove cached value.
    func remove(_ key: String) {
        memoryCache.removeValue(forKey: key)
    }

    /// Clear all cached values.
    func clear() {
        memoryCache.removeAll()
    }

    /// Get freshness status for a key without decoding the value.
    func freshness(for key: String) -> CacheFreshness? {
        guard let data = memoryCache[key] else { return nil }

        // Decode just enough to get timestamp
        struct TimestampOnly: Codable {
            let timestamp: Date
        }

        do {
            let entry = try decoder.decode(TimestampOnly.self, from: data)
            return CacheFreshness(age: Date().timeIntervalSince(entry.timestamp))
        } catch {
            return nil
        }
    }

    // MARK: - Persistent Cache Operations (UserDefaults)

    /// Get cached value from persistent storage.
    func getPersistent<T: Codable>(_ key: String, type: T.Type) -> (value: T, freshness: CacheFreshness)? {
        guard let data = UserDefaults.standard.data(forKey: "cache_\(key)") else { return nil }

        do {
            let entry = try decoder.decode(CacheEntry<T>.self, from: data)
            return (entry.data, entry.freshness)
        } catch {
            print("[CacheManager] Failed to decode persistent cache for key '\(key)': \(error)")
            UserDefaults.standard.removeObject(forKey: "cache_\(key)")
            return nil
        }
    }

    /// Set cached value in persistent storage.
    func setPersistent<T: Codable>(_ key: String, value: T) {
        let entry = CacheEntry(data: value, timestamp: Date(), key: key)

        do {
            let data = try encoder.encode(entry)
            UserDefaults.standard.set(data, forKey: "cache_\(key)")
        } catch {
            print("[CacheManager] Failed to encode persistent cache for key '\(key)': \(error)")
        }
    }

    /// Remove persistent cached value.
    func removePersistent(_ key: String) {
        UserDefaults.standard.removeObject(forKey: "cache_\(key)")
    }

    // MARK: - Cache Statistics

    /// Get cache statistics for debugging.
    func statistics() -> CacheStatistics {
        var stats = CacheStatistics()
        stats.memoryEntryCount = memoryCache.count
        stats.memorySize = memoryCache.values.reduce(0) { $0 + $1.count }
        return stats
    }
}

// MARK: - Cache Statistics

struct CacheStatistics {
    var memoryEntryCount: Int = 0
    var memorySize: Int = 0

    var memorySizeFormatted: String {
        ByteCountFormatter.string(fromByteCount: Int64(memorySize), countStyle: .memory)
    }
}

// MARK: - Cache Keys

/// Centralized cache key definitions for type safety.
enum CacheKey {
    static func chart(symbol: String, timeframe: String) -> String {
        "chart_\(symbol)_\(timeframe)"
    }

    static func options(symbol: String) -> String {
        "options_\(symbol)"
    }

    static func forecast(symbol: String) -> String {
        "forecast_\(symbol)"
    }

    static func watchlist(userId: String) -> String {
        "watchlist_\(userId)"
    }

    static func symbolSearch(query: String) -> String {
        "search_\(query.lowercased())"
    }
}

// MARK: - TTL Specification Table
/*
 | Data Type       | Fresh    | Warm     | Stale    | Critical | Notes                    |
 |-----------------|----------|----------|----------|----------|--------------------------|
 | Chart Data      | < 5 min  | 5-30 min | 30m-6h   | > 6 hr   | Standard TTL             |
 | Options Chain   | < 5 min  | 5-30 min | 30m-6h   | > 6 hr   | Standard TTL             |
 | ML Forecasts    | < 1 hr   | 1-6 hr   | 6-24 hr  | > 24 hr  | Longer TTL (computed)    |
 | Symbol Search   | < 1 hr   | 1-24 hr  | 24-48 hr | > 48 hr  | Very long TTL (static)   |
 | Watchlist       | < 1 min  | 1-5 min  | 5-30 min | > 30 min | Short TTL (user data)    |
 */
