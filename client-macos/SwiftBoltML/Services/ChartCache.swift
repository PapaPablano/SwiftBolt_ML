import Foundation

/// Lightweight on-disk cache for OHLC bars keyed by symbol + timeframe.
/// Uses JSON encoding and stores under Caches directory.
@MainActor
enum ChartCache {
    private static let directoryName = "ChartBarsCache"

    private static func cacheDirectory() -> URL? {
        do {
            let urls = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)
            guard let base = urls.first else { return nil }
            let dir = base.appendingPathComponent(directoryName, isDirectory: true)
            if !FileManager.default.fileExists(atPath: dir.path) {
                try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            }
            return dir
        } catch {
            print("[ChartCache] Failed to create cache dir: \(error)")
            return nil
        }
    }

    private static func fileURL(symbol: String, timeframe: Timeframe) -> URL? {
        guard let dir = cacheDirectory() else { return nil }
        let safeSymbol = symbol.replacingOccurrences(of: "/", with: "_")
        return dir.appendingPathComponent("\(safeSymbol)_\(timeframe.apiToken).json")
    }

    static func saveBars(symbol: String, timeframe: Timeframe, bars: [OHLCBar]) {
        guard let url = fileURL(symbol: symbol, timeframe: timeframe) else { return }
        do {
            let data = try JSONEncoder().encode(bars)
            try data.write(to: url, options: .atomic)
            print("[ChartCache] Saved \(bars.count) bars to \(url.lastPathComponent)")
        } catch {
            print("[ChartCache] Save error: \(error)")
        }
    }

    static func loadBars(symbol: String, timeframe: Timeframe) -> [OHLCBar]? {
        guard let url = fileURL(symbol: symbol, timeframe: timeframe) else { return nil }
        
        // Check cache age and invalidate if stale
        do {
            let attributes = try FileManager.default.attributesOfItem(atPath: url.path)
            if let modificationDate = attributes[.modificationDate] as? Date {
                let cacheAge = Date().timeIntervalSince(modificationDate)
                
                // Invalidate stale cache based on timeframe
                let maxAge: TimeInterval
                switch timeframe {
                case .m15, .h1, .h4:
                    maxAge = 24 * 3600 // 24 hours for intraday
                case .d1:
                    maxAge = 7 * 24 * 3600 // 7 days for daily
                case .w1:
                    maxAge = 30 * 24 * 3600 // 30 days for weekly
                }
                
                if cacheAge > maxAge {
                    print("[ChartCache] Cache expired for \(symbol) \(timeframe.apiToken) (age: \(Int(cacheAge/3600))h)")
                    try? FileManager.default.removeItem(at: url)
                    return nil
                }
            }
        } catch {
            // If we can't check age, try to load anyway
        }
        
        do {
            let data = try Data(contentsOf: url)
            let bars = try JSONDecoder().decode([OHLCBar].self, from: data)
            
            // Additional validation: check if newest bar is recent enough
            if let newestBar = bars.max(by: { $0.ts < $1.ts }) {
                let barAge = Date().timeIntervalSince(newestBar.ts)
                let maxBarAge: TimeInterval
                switch timeframe {
                case .m15, .h1, .h4:
                    maxBarAge = 48 * 3600 // 48 hours for intraday
                case .d1:
                    maxBarAge = 14 * 24 * 3600 // 14 days for daily
                case .w1:
                    maxBarAge = 60 * 24 * 3600 // 60 days for weekly
                }
                
                if barAge > maxBarAge {
                    print("[ChartCache] Data too old for \(symbol) \(timeframe.apiToken) (newest bar: \(Int(barAge/3600))h old)")
                    try? FileManager.default.removeItem(at: url)
                    return nil
                }
            }
            
            return bars
        } catch {
            return nil
        }
    }

    static func clear(symbol: String, timeframe: Timeframe) {
        guard let url = fileURL(symbol: symbol, timeframe: timeframe) else { return }
        do {
            try FileManager.default.removeItem(at: url)
        } catch {}
    }

    static func clearAll() {
        guard let dir = cacheDirectory() else { return }
        do {
            try FileManager.default.removeItem(at: dir)
        } catch {}
    }
}
