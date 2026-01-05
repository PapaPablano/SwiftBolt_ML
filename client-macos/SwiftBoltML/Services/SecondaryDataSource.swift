import Foundation

/// Secondary data source for cross-validation
/// Uses Yahoo Finance as a free, reliable backup source
class SecondaryDataSource {
    
    static let shared = SecondaryDataSource()
    
    private init() {}
    
    // MARK: - Fetch Data
    
    /// Fetch OHLCV data from Yahoo Finance for validation
    func fetchBars(symbol: String, timeframe: String) async throws -> [OHLCBar] {
        // Convert timeframe to Yahoo Finance interval
        let interval = convertTimeframe(timeframe)
        let range = getRange(for: timeframe)
        
        // Build Yahoo Finance URL
        let period1 = Int(Date().addingTimeInterval(-range).timeIntervalSince1970)
        let period2 = Int(Date().timeIntervalSince1970)
        
        let urlString = "https://query1.finance.yahoo.com/v8/finance/chart/\(symbol)?interval=\(interval)&period1=\(period1)&period2=\(period2)"
        
        guard let url = URL(string: urlString) else {
            throw DataSourceError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.setValue("Mozilla/5.0", forHTTPHeaderField: "User-Agent")
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw DataSourceError.httpError(statusCode: (response as? HTTPURLResponse)?.statusCode ?? 0)
        }
        
        // Parse Yahoo Finance response
        return try parseYahooResponse(data)
    }
    
    // MARK: - Parsing
    
    private func parseYahooResponse(_ data: Data) throws -> [OHLCBar] {
        let decoder = JSONDecoder()
        let response = try decoder.decode(YahooFinanceResponse.self, from: data)
        
        guard let result = response.chart.result.first,
              let timestamps = result.timestamp,
              let quotes = result.indicators.quote.first else {
            throw DataSourceError.invalidResponse
        }
        
        var bars: [OHLCBar] = []
        
        for i in 0..<timestamps.count {
            guard let open = quotes.open?[i],
                  let high = quotes.high?[i],
                  let low = quotes.low?[i],
                  let close = quotes.close?[i],
                  let volume = quotes.volume?[i] else {
                continue
            }
            
            let bar = OHLCBar(
                ts: Date(timeIntervalSince1970: TimeInterval(timestamps[i])),
                open: open,
                high: high,
                low: low,
                close: close,
                volume: Double(volume)
            )
            bars.append(bar)
        }
        
        return bars
    }
    
    // MARK: - Helpers
    
    private func convertTimeframe(_ timeframe: String) -> String {
        switch timeframe.lowercased() {
        case "1m": return "1m"
        case "5m": return "5m"
        case "15m": return "15m"
        case "30m": return "30m"
        case "1h": return "1h"
        case "d1", "1d": return "1d"
        case "w1", "1w": return "1wk"
        case "m1", "1mo": return "1mo"
        default: return "1d"
        }
    }
    
    private func getRange(for timeframe: String) -> TimeInterval {
        switch timeframe.lowercased() {
        case "1m", "5m": return 7 * 24 * 3600  // 7 days
        case "15m", "30m": return 60 * 24 * 3600  // 60 days
        case "1h": return 730 * 24 * 3600  // 2 years
        case "d1", "1d": return 3 * 365 * 24 * 3600  // 3 years
        case "w1", "1w": return 10 * 365 * 24 * 3600  // 10 years
        default: return 3 * 365 * 24 * 3600
        }
    }
}

// MARK: - Yahoo Finance Response Models

private struct YahooFinanceResponse: Codable {
    let chart: Chart
}

private struct Chart: Codable {
    let result: [Result]
}

private struct Result: Codable {
    let timestamp: [Int]?
    let indicators: Indicators
}

private struct Indicators: Codable {
    let quote: [Quote]
}

private struct Quote: Codable {
    let open: [Double?]?
    let high: [Double?]?
    let low: [Double?]?
    let close: [Double?]?
    let volume: [Int?]?
}

// MARK: - Errors

enum DataSourceError: Error {
    case invalidURL
    case httpError(statusCode: Int)
    case invalidResponse
    case parsingError
}
