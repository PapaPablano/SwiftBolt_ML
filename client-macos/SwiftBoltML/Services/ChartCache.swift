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
        do {
            let data = try Data(contentsOf: url)
            let bars = try JSONDecoder().decode([OHLCBar].self, from: data)
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
