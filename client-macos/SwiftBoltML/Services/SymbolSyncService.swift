import Foundation

enum SymbolSyncSource: String {
    case watchlist = "watchlist"
    case recentSearch = "recent_search"
    case chartView = "chart_view"
}

struct SymbolSyncRequest: Codable {
    let symbols: [String]
    let source: String
    let timeframes: [String]
}

struct SymbolSyncResponse: Codable {
    let success: Bool
    let symbols_tracked: Int
    let symbols_requested: Int
    let timeframes: Int
    let jobs_updated: Int
    let priority: Int
    let source: String
}

class SymbolSyncService {
    static let shared = SymbolSyncService()
    
    private init() {
        // Use existing Config class for Supabase configuration
    }
    
    func syncSymbols(
        symbols: [String],
        source: SymbolSyncSource,
        timeframes: [String] = ["m15", "h1", "h4", "d1", "w1"]
    ) async throws -> SymbolSyncResponse {
        guard !symbols.isEmpty else {
            throw NSError(domain: "SymbolSync", code: 400, userInfo: [
                NSLocalizedDescriptionKey: "No symbols provided"
            ])
        }
        
        let url = Config.functionURL("sync-user-symbols")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body = SymbolSyncRequest(
            symbols: symbols,
            source: source.rawValue,
            timeframes: timeframes
        )
        request.httpBody = try JSONEncoder().encode(body)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw NSError(domain: "SymbolSync", code: 500, userInfo: [
                NSLocalizedDescriptionKey: "Invalid response"
            ])
        }
        
        guard httpResponse.statusCode == 200 else {
            let errorMessage = String(data: data, encoding: .utf8) ?? "Unknown error"
            throw NSError(domain: "SymbolSync", code: httpResponse.statusCode, userInfo: [
                NSLocalizedDescriptionKey: "Sync failed: \(errorMessage)"
            ])
        }
        
        let syncResponse = try JSONDecoder().decode(SymbolSyncResponse.self, from: data)
        return syncResponse
    }
    
    func syncSymbol(
        _ symbol: String,
        source: SymbolSyncSource,
        timeframes: [String] = ["m15", "h1", "h4", "d1", "w1"]
    ) async throws -> SymbolSyncResponse {
        return try await syncSymbols(symbols: [symbol], source: source, timeframes: timeframes)
    }
    
    func syncSymbolInBackground(
        _ symbol: String,
        source: SymbolSyncSource,
        timeframes: [String] = ["m15", "h1", "h4", "d1", "w1"]
    ) {
        Task {
            do {
                let response = try await syncSymbol(symbol, source: source, timeframes: timeframes)
                print("[SymbolSync] ✅ Synced \(symbol) (\(source.rawValue)): \(response.jobs_updated) jobs created/updated")
            } catch {
                print("[SymbolSync] ⚠️ Failed to sync \(symbol): \(error.localizedDescription)")
            }
        }
    }
    
    func syncSymbolsInBackground(
        _ symbols: [String],
        source: SymbolSyncSource,
        timeframes: [String] = ["m15", "h1", "h4", "d1", "w1"]
    ) {
        Task {
            do {
                let response = try await syncSymbols(symbols: symbols, source: source, timeframes: timeframes)
                print("[SymbolSync] ✅ Synced \(symbols.count) symbols (\(source.rawValue)): \(response.jobs_updated) jobs created/updated")
            } catch {
                print("[SymbolSync] ⚠️ Failed to sync symbols: \(error.localizedDescription)")
            }
        }
    }
}
